"""Walk a student through a question or a word problem, one step at a time.

A QuestionSession keeps the set of routes (ways through the question's methods) that are still consistent with what
the student has written. The first step, and the second where methods share a first step, are classified against the
generated first-step trees (trees/<question>.json); later steps against the next step of each route still alive.
A WordProblemSession runs the extraction decisions first, then a QuestionSession on the extracted numbers, then any
follow-up step, then asks for the answer in the story's terms.
"""

import copy
import json
import random
import re
from fractions import Fraction

import build as engine

from .classifier import Classifier, RuleClassifier, is_wildcard
from .models import Candidate, ChoiceAnswer, Feedback
from .parse import ParseError, parse, parse_all

_trees = {}


def tree(qid):
    if qid not in _trees:
        _trees[qid] = json.loads((engine.ROOT / "trees" / f"{qid}.json").read_text())
    return _trees[qid]


def _ev(expr, values):
    """Evaluate a tree expression; '(a, b)' is a plot point."""
    expr = expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        return tuple(_ev(p, values) for p in engine.split_top(expr[1:-1]))
    return engine.ev(expr, values)


def tree_candidates(entries, values, prefix):
    out = []
    for i, e in enumerate(entries):
        try:
            operands = [_ev(a, values) for a in e["match"]["args"]]
        except (KeyError, engine.NotApplicable, ZeroDivisionError):
            continue
        out.append(Candidate(id=f"{prefix}{i}", op=e["match"]["op"], operands=operands, methods=e["methods"],
                             mental=e.get("mental", False), source="tree", note=e.get("feedback", "")))
    return out


def step_candidate(cid, route, pos):
    """The candidate for one route's visible step number `pos`."""
    v, env, trace, vis = route
    st, args, result = trace[vis[pos]]
    search = None
    if "search" in st:
        names = st["args"]
        base = args[1 - names.index(st["search"]["var"])]
        search = {"base": base, "target": result}
    text = engine.say(st.get("say"), env)
    loc = st.get("loc", ())
    says = []  # inside calls: lead with what the innermost two calls are for, so the first and second fraction's
    for depth in range(len(loc) - 1):  # steps don't read the same
        call = next((c for c in v["calls"] if tuple(c["loc"]) == tuple(loc[:depth + 1])), None)
        if call and call["say"]:
            says.append(engine.say(call["say"], env))
    if says:
        lead = ", ".join(x if i == 0 else x[:1].lower() + x[1:] for i, x in enumerate(says[-2:]))
        text = f"{lead}: {text[:1].lower()}{text[1:]}"
    return Candidate(id=cid, op=st["op"], operands=list(args), result=result,
                     expression=engine.expression(st, args, result), say=text, methods=[v["method"]], search=search)


def written(step) -> str:
    """How a typed step reads back: 4 × 18 = 72."""
    if step.kind == "plot":
        return "plot " + ", ".join(f"({x}, {y})" for x, y in step.points)
    if step.kind == "compare":
        return f"{step.left} {step.relation} {step.right}"
    if step.kind == "ratio_compare":
        return f"{step.left[0]}:{step.left[1]} {step.relation} {step.right[0]}:{step.right[1]}"
    sym = {"add": "+", "subtract": "−", "multiply": "×", "divide": "÷"}
    lhs = f"{step.name.upper()}({step.left}, {step.right})" if step.kind == "function" else f"{step.left} {sym[step.op]} {step.right}"
    return lhs + (f" = {step.result}" if step.result is not None else "")


def bindings(qid, values):
    """The question's values, plus the core question's names for them when it is a question in context (percent-of's
    a, b, d are p, 100, n), so a method's idea inherited through the reduction reads with numbers."""
    out = dict(values)
    red = engine.Q[qid].get("reduces_to")
    for k, v in (red["with"].items() if red else ()):
        if isinstance(v, str) and v in values:
            out.setdefault(k, values[v])
        elif not isinstance(v, str):
            out.setdefault(k, engine.fmt(engine.num(v)))
    return out


def method_text(qid, mid, field, values):
    """A method's idea (or best_when) with the numbers filled in. A text that still names a value afterwards, or
    a best_when that states something about the values (it may not hold for these), is dropped: ""."""
    m = engine.methods_of(qid)[mid]
    raw = m.get(field, "") or ""
    if field == "best_when" and re.search(r"\{\w+\}", raw):
        return ""
    text = engine.render(raw, bindings(qid, values))
    return "" if re.search(r"\{\w+\}", text) else text


def answer_options(qid):
    """The possible categorical answers to a question, or None when the answer is a number."""
    red = engine.Q[qid].get("reduces_to")
    if red and red.get("answer_map"):
        return list(dict.fromkeys(red["answer_map"].values()))
    found = []

    def walk(items):
        for s in items:
            if s["op"] == "compare":
                found.extend(s["meaning"].values())
            for br in s.get("branches", []):
                walk(br)

    for m in engine.methods_of(qid).values():
        walk(m["steps"])
    return [v for v in dict.fromkeys(found) if v != "not equal"] or None


def prompt_text(ask):
    """The terminal form of ask(): the question, numbered options, and any note."""
    lines = [ask["text"]] + [f"  [{i}] {o}" for i, o in enumerate(ask["options"], 1)]
    if ask.get("note"):
        lines.append(f"({ask['note']})")
    return "\n".join(l for l in lines if l)


COMMANDS = "Commands: `hint` for a nudge (twice for more), `where` to see your steps, `done` if you think you've finished, `quit`."


class QuestionSession:
    """Each live route keeps its own position, so one step can advance a route while another route is still
    building up (5 × 2 = 10 on the way to 5 × 8 = 40), and a step done in the head can be skipped."""

    def __init__(self, qid, values, classifier: Classifier | None = None, ask_final=True):
        self.qid, self.q = qid, engine.Q[qid]
        self.values = {k: engine.fmt(engine.num(v)) for k, v in values.items()}
        self.methods = engine.methods_of(qid)
        self.classifier = classifier or RuleClassifier()
        self.routes, _ = engine.routes_for(qid, self.values)
        self.expanded = len(self.routes)  # routes past this one are re-runs with the student's own choices
        self.live = {r: 0 for r in range(len(self.routes))}  # route → number of its visible steps done
        self.choices = {}  # route → the student's own picks it was re-run with (run(choices=…))
        self.named = None  # the methods the last accepted step was a step of (None: every live method)
        self.tries = {}    # (route, position) → build-up steps written toward that step (6 × 2 = 12 toward 6 × 3)
        self.tree_entries = tree(qid)["first_steps"]  # the first steps are classified against the tree
        self.slips = 0
        self.hints = 0
        self.history = []
        self.ask_final = ask_final and self.q["outputs"] == ["answer"]
        self.phase = "steps"
        self.result = None
        self.finished = None

    def fresh(self, ask_final=None):
        """A new session on the same question and values, sharing the expanded routes (no re-expansion)."""
        new = copy.copy(self)
        new.routes = self.routes[:self.expanded]
        new.live = {r: 0 for r in range(self.expanded)}
        new.choices, new.named, new.tries, new.history = {}, None, {}, []
        new.tree_entries = tree(self.qid)["first_steps"]
        new.slips = new.hints = 0
        new.phase, new.result, new.finished = "steps", None, None
        if ask_final is not None:
            new.ask_final = ask_final and self.q["outputs"] == ["answer"]
        return new

    # ------------------------------------------------------------ what to show

    def title(self):
        return engine.render(self.q["prompt"], self.values)

    def ask(self):
        """What to ask next: {text, options, allow_step}. Options are picked by number."""
        if self.phase == "answer":
            return {"text": "What's your answer?", "options": answer_options(self.qid) or [], "allow_step": False}
        if self.phase == "done":
            return {"text": "", "options": [], "allow_step": False}
        return {"text": "What's your first step?" if not self.history else "What's your next step?",
                "options": [], "allow_step": True}

    def prompt(self):
        return prompt_text(self.ask())

    def live_methods(self):
        return sorted({self.routes[r][0]["method"] for r in self.live})

    def named_methods(self):
        """The live methods the student's steps so far are steps of. A route that is only building up toward its
        step (8 × 12 = 96 on the way to 8 × 125 = 1000) stays live, but isn't named."""
        live = self.live_methods()
        return [m for m in live if self.named is None or m in self.named] or live

    def names(self, mids):
        return " or ".join(self.methods[m]["name"] for m in sorted(mids))

    def next_step(self, r, offset=0, at=None):
        route = self.routes[r]
        at = (self.live[r] if at is None else at) + offset
        return step_candidate("x", route, at) if len(route[3]) > at else None

    def candidates(self, pool=None):
        """What the student's step is classified against: the tree's entries for the first steps, then the next
        step of every live route (or of the routes in `pool`, route → position)."""
        if self.tree_entries is not None:
            return tree_candidates(self.tree_entries, {k: engine.num(v) for k, v in self.values.items()}, "t")
        pool = self.live if pool is None else pool
        seen = {}
        for r, at in pool.items():
            c = self.next_step(r, 0, at)
            if c:
                key = (c.op, c.expression)
                if key in seen:
                    seen[key].methods = sorted(set(seen[key].methods) | set(c.methods))
                else:
                    seen[key] = c.model_copy(update={"id": f"r{len(seen)}"})
        return list(seen.values())

    # ------------------------------------------------------------ input

    def submit(self, text):
        """Typed text: parse it, then submit the reading that fits."""
        if self.phase == "done":
            return [Feedback(kind="info", message="This one is finished.")]
        if self.phase == "answer":
            return self.submit_answer(text)
        try:
            readings = [r for r in parse_all(text) if r.kind not in ("choice", "value")]
        except ParseError as e:
            return [Feedback(kind="error", message=str(e))]
        if not readings:
            return [Feedback(kind="error", message="That looks like an answer. Write the step that gets you there, "
                                                   "like `4 x 18 = 72`, or type `done` if you've finished.")]
        return self.submit_readings(readings)

    def submit_readings(self, readings):
        """`4/3 = 4/3` can be a division or a comparison: use the reading that fits."""
        first = None
        for step in readings:
            fb = self.submit_input(step)
            if any(f.kind in ("correct", "slip", "on_track") for f in fb):
                return fb
            first = first or fb
        return first

    def submit_input(self, inp):
        """A typed StudentInput (from the parser, a structured UI, or a model): a step, a choice or a value."""
        if self.phase == "done":
            return [Feedback(kind="info", message="This one is finished.")]
        if self.phase == "answer":
            return self.answer_input(inp, None)
        if inp.kind in ("choice", "value"):
            return [Feedback(kind="error", message="That looks like an answer. Write the step that gets you there, "
                                                   "or say you're done if you've finished.")]
        return self.submit_step(inp)

    def submit_step(self, step):
        kept = len(self.routes)
        out = self._submit_step(step)
        if not any(r >= kept for r in self.live):  # drop re-run routes the step didn't keep
            del self.routes[kept:]
            for r in [r for r in self.choices if r >= kept]:
                del self.choices[r]
        return out

    def _submit_step(self, step):
        pool = {**self.live, **self._rechosen(step)}  # routes re-run with the student's own factor or power of ten
        cands = self.candidates(pool)
        cls = self.classifier.classify(step, cands)
        if cls.status == "none":
            extra = f" (Also, {written(step).split(' = ')[0]} is {cls.expected_result}.)" if cls.arithmetic_ok is False else ""
            return [Feedback(kind="unknown", message=f"I don't recognize “{written(step)}” as a next step here.{extra} "
                                                     "Type `hint` for a nudge.")]
        if cls.status == "match":  # every entry the step fits names a method the graph draws on this step; the
            # exact one only decides the arithmetic feedback. The routes then filter by the actual numbers.
            chosen = [c for c in cands if self.classifier.classify(step, [c]).status == "match"]
        else:
            chosen = [c for c in cands if c.id in cls.matched]
        allowed = set().union(*(set(c.methods) for c in chosen))
        mental = set().union(*(set(c.methods) for c in chosen if c.mental))

        advanced, waiting, skipped = {}, {}, set()
        for r, at in pool.items():
            mid = self.routes[r][0]["method"]
            if mid not in allowed:
                continue
            for offset in ((0, 1) if mid in mental and at == 0 else (0,)):
                c = self.next_step(r, offset, at)
                res = self.classifier.classify(step, [c]) if c else None
                if res and res.status == "match":
                    advanced[r] = at + offset + 1
                    if offset:
                        skipped.add(r)
                    break
                if res and res.status == "on_track" and not offset:
                    waiting[r] = at
        if not advanced and not waiting:
            return [Feedback(kind="unknown", message=f"“{written(step)}” is how {self.names(allowed)} starts, but those "
                                                     "numbers don't lead anywhere here. Type `hint` for a nudge.")]
        if cls.arithmetic_ok is False:
            self.slips += 1
            if self.slips < 2:
                return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”. Try it again.")]
            slip = [Feedback(kind="slip", message=f"It's {cls.expected_result}. Let's carry on with that.")]
        else:
            slip = []
        if not advanced:
            self.live = waiting
            self.named = {self.routes[r][0]["method"] for r in waiting}
            for r, at in waiting.items():
                self.tries[(r, at)] = self.tries.get((r, at), []) + [written(step)]
            target = next(self.next_step(r).search["target"] for r in waiting)
            return [Feedback(kind="on_track", message=f"Good, keep building: {written(step)}. "
                                                      f"Keep going until you reach {engine.fmt(target)}.")]

        before = set(self.named_methods())
        alive_methods = {self.routes[r][0]["method"] for r in advanced}
        if self.tree_entries is not None:  # go down the tree while the method is still open, then leave it
            nexts = [n for c in chosen if c.id.startswith("t") for n in self.tree_entries[int(c.id[1:])].get("next", [])
                     if set(n["methods"]) & alive_methods]
            self.tree_entries = nexts if len(alive_methods) > 1 and nexts and not self.history and not skipped else None
        r0 = min(advanced, key=lambda r: (r in skipped, r))
        done = step_candidate("x", self.routes[r0], advanced[r0] - 1)
        self.live = {**waiting, **advanced}
        self.named = alive_methods
        self.slips = self.hints = 0
        self.history.append(done.expression)
        out = slip
        if r0 in skipped:
            skipped_step = step_candidate("x", self.routes[r0], advanced[r0] - 2)
            out.append(Feedback(kind="info", message=f"You did {skipped_step.expression} in your head. Fine."))
        out.append(Feedback(kind="correct", message=f"✓ {done.expression}  ({done.say})"))
        after = set(self.named_methods())
        if len(after) == 1 and after != before:
            m = self.methods[next(iter(after))]
            out.append(Feedback(kind="method", message=f"You're using: {m['name']}. {method_text(self.qid, next(iter(after)), 'idea', self.values)}"))
        elif len(after) > 1 and after != before:
            out.append(Feedback(kind="method", message=f"That step starts {self.names(after)}. Your next step will tell which."))
        if all(self.next_step(r) is None for r in advanced):
            out += self.finish_steps()
        return out

    def _rechosen(self, step):
        """Live routes re-run with the student's own choice where the method lets them choose: any common factor
        in a round of dividing out factors (72 ÷ 8, not only 72 ÷ 2), any power of ten when scaling to one
        (4 × 250 = 1000, not only 4 × 25 = 100). Returns {new route: position}; the new routes are appended to
        self.routes and only stay if the step advances them."""
        if step.kind != "arithmetic":
            return {}
        out, seen = {}, set()
        for r, at in list(self.live.items()):
            alt = self._rechoose(r, at, step)
            if alt is None:
                continue
            route, choices = alt
            key = tuple(engine.expression(*route[2][i]) for i in route[3])
            if key in seen:
                continue
            seen.add(key)
            self.routes.append(route)
            self.choices[len(self.routes) - 1] = choices
            out[len(self.routes) - 1] = at
        return out

    def _rechoose(self, r, at, step):
        v, env, trace, vis = self.routes[r]
        if at >= len(vis):
            return None
        i = vis[at]
        st, args, result = trace[i]
        if st["op"] != step.op or not isinstance(result, Fraction):
            return None
        var, upto = None, i  # the variable the student chooses, and where this choice is made in the trace
        if "search" in st and "until_power_of_ten" in st["search"]:
            var = st["search"]["var"]
        else:
            prev = vis[at - 1] if at else -1
            pick = next((j for j in range(i - 1, prev, -1) if trace[j][0]["op"] == "pick"), None)
            if pick is not None and trace[pick][0]["var"] in st["args"]:
                var, upto = trace[pick][0]["var"], pick
        if var is None or var not in st["args"]:
            return None
        pos = st["args"].index(var)
        a, b = step.left, step.right
        orders = [(a, b), (b, a)] if st["op"] in ("multiply", "add") else [(a, b)]
        mine = next((o[pos].value for o in orders if o[1 - pos].close_to(args[1 - pos])), None)
        if mine is None or mine == args[pos] or mine.denominator != 1 or mine <= 1:
            return None
        earlier = []
        for j in range(upto):
            t = trace[j]
            if t[0]["op"] == "pick" and t[0]["var"] == var:
                earlier.append(Fraction(t[2]))
            elif "search" in t[0] and t[0]["search"]["var"] == var:
                earlier.append(t[1][t[0]["args"].index(var)])
        choices = {**self.choices.get(r, {}), var: earlier + [mine]}
        try:
            env2, trace2 = engine.run(v["steps"], self.values, choices)
        except (engine.NotApplicable, KeyError, ZeroDivisionError):
            return None
        vis2 = [k for k, t in enumerate(trace2) if engine.visible(t[0])]
        if len(vis2) <= at or any(engine.expression(*trace2[vis2[k]]) != engine.expression(*trace[vis[k]])
                                  for k in range(at)):
            return None
        return (v, env2, trace2, vis2), choices

    def finish_steps(self):
        finished = [r for r in self.live if self.next_step(r) is None]
        if not finished:
            return [Feedback(kind="info", message="There's at least one more step. Type `hint` if you're stuck.")]
        self.live = {r: self.live[r] for r in finished}
        self.result = engine.outputs_of(self.qid, self.routes[finished[0]][1])
        if self.ask_final:
            self.phase = "answer"
            return [Feedback(kind="info", message="That's all the steps.")]
        self.phase = "done"
        return [Feedback(kind="done", message="That's all the steps.")]

    def submit_answer(self, text):
        opts = answer_options(self.qid)
        try:
            inp = parse(text, choices=len(opts or []))
        except ParseError:
            inp = None
        return self.answer_input(inp, text)

    def answer_input(self, inp, text):
        """The final answer: a choice among answer_options, or a value. `text` is the raw entry, if there was one."""
        expected = self.result
        opts = answer_options(self.qid)
        if opts:
            given = opts[inp.index - 1] if inp and inp.kind == "choice" and inp.index <= len(opts) else (text or "").strip().lower()
            if expected == "not equal":
                self.phase = "done"
                return [Feedback(kind="done", message="Simplifying shows they aren't equal, but not which is bigger. "
                                                      "Try another method to decide.")]
            ok = given == expected
        else:
            if not inp or inp.kind != "value":
                return [Feedback(kind="error", message="Write the answer as a number.")]
            ok = inp.value.close_to(expected)
        if not ok:
            return [Feedback(kind="unknown", message=f"Not quite. Look at your last step: {self.history[-1]}.")]
        self.phase = "done"
        return [Feedback(kind="done", message=f"✓ Correct: {engine.show(expected)}. "
                                              f"You used {self.names(self.named_methods())}.")]

    # ------------------------------------------------------------ help

    def hint(self):
        self.hints += 1
        if self.phase == "answer":
            return [Feedback(kind="hint", message=f"Your last step was {self.history[-1]}. What does it tell you?")]
        nexts = {}
        named = set(self.named_methods())
        for r in self.live:
            c = self.next_step(r)
            if c and self.routes[r][0]["method"] in named:
                nexts.setdefault(self.routes[r][0]["method"], c)
        if not nexts:
            return [Feedback(kind="hint", message="You've done every step. Type `done`.")]
        show_expr = self.hints >= 2
        lines = [(self.methods[m]["name"], c.say + (f" ({c.expression})" if show_expr else "")) for m, c in sorted(nexts.items())]
        if len(lines) == 1:
            return [Feedback(kind="hint", message="Next: " + lines[0][1])]
        return [Feedback(kind="hint", message="Some ways to go:\n  " + "\n  ".join(f"{n}: {t}" for n, t in lines[:6])
                         + ("\n  …" if len(lines) > 6 else ""))]

    def where(self):
        done = "\n  ".join(self.history) or "(no steps yet)"
        return [Feedback(kind="info", message=f"Your steps so far:\n  {done}\nStill possible: {self.names(self.named_methods())}")]

    # ------------------------------------------------------------ structured input (boxes mode)

    def choose_method(self, mid):
        """The student picks a method up front: keep only that method's live routes (all of them, if it has several)."""
        if self.phase != "steps":
            return [Feedback(kind="error", message="There are no steps left to choose a method for.")]
        live = {r: at for r, at in self.live.items() if self.routes[r][0]["method"] == mid}
        if not live:
            return [Feedback(kind="error", message=f"{mid!r} isn't one of the methods still open here.")]
        self.live = live
        self.named = {mid}
        if self.tree_entries is not None:  # still classifying against the tree: keep only this method's entries
            self.tree_entries = [e for e in self.tree_entries if mid in e["methods"]] or None
        m = self.methods[mid]
        return [Feedback(kind="method", message=f"You're using: {m['name']}. {method_text(self.qid, mid, 'idea', self.values)}")]

    def next_steps(self):
        """The next visible step of every live route: [(route index, step dict, Candidate)]."""
        out = []
        for r, at in self.live.items():
            v, env, trace, vis = self.routes[r]
            if at < len(vis):
                out.append((r, trace[vis[at]][0], step_candidate("x", self.routes[r], at)))
        return out


class WordProblemSession:
    """The extraction decisions (in any order, as the graph's `all` block allows), the steps on a decision's ✓ edge
    (90 ÷ 60 = 1.5), then a QuestionSession on the extracted numbers, any follow-up step, and the story's answer."""

    def __init__(self, wid, classifier: Classifier | None = None):
        self.wid, self.wp = wid, engine.WP[wid]
        self.classifier = classifier or RuleClassifier()
        ok, self.info = engine.check_word_problem(self.wp)
        self.plan, self.run = self.info["plan"], self.info["run"]
        self.decided = set()
        self.di = None
        self.order = {}
        for di, dec in enumerate(self.wp["extract"]):
            idx = list(range(len(dec["options"])))
            random.Random(f"{wid}:{di}").shuffle(idx)
            self.order[di] = idx
        self.pre_todo = []    # steps on a settled decision's ✓ edge still to write: indexes into run["before"]
        self.pre_done = set()
        self._proto = None
        self.question = None
        self.then_pos = 0
        self.phase = "extract"
        self.pending = self._next_decision()

    # ------------------------------------------------------------ what to show

    def intro(self):
        return f"{self.wp['title']}\n\n{self.wp['text']}\n"

    def open_decisions(self):
        """The decisions still to make, the current one first: the student may take them in any order."""
        rest = [di for di, dec in enumerate(self.wp["extract"])
                if di not in self.decided and not all(o.get("correct") for o in dec["options"])]
        return sorted(rest, key=lambda di: di != self.di)

    def options_of(self, di):
        dec = self.wp["extract"][di]
        return [dec["options"][j]["say"] for j in self.order[di]]

    def _pre_steps(self, di):
        """The steps on decision di's ✓ edge (90 ÷ 60 = 1.5), as indexes into run["before"], not yet written."""
        correct = next(o for o in self.wp["extract"][di]["options"] if o.get("correct"))
        outs = {s["out"] for s in correct.get("steps", [])}
        return [i for i, e in enumerate(self.run["before"]) if e[0]["out"] in outs and i not in self.pre_done]

    def _next_decision(self):
        """Move to the next undecided decision; decisions without traps are simply announced. A settled decision's
        own steps are asked for first."""
        out = []
        if self.pre_todo:
            return out
        for di, dec in enumerate(self.wp["extract"]):
            if di in self.decided:
                continue
            if all(o.get("correct") for o in dec["options"]):
                self.decided.add(di)
                out.append(Feedback(kind="info", message=f"{dec['say']} {dec['options'][0]['say']}."))
                self.pre_todo = self._pre_steps(di)
                if self.pre_todo:
                    self.di = di
                    return out + [self._ask_pre()]
                continue
            if self.di not in self.open_decisions():
                self.di = di
            return out
        self.di = None
        return out + self._start_solving()

    def _ask_pre(self):
        st = self.run["before"][self.pre_todo[0]][0]
        return Feedback(kind="info", message=f"Write that step: {engine.say(st.get('say'), self.run['env'])}.")

    def _probe(self):
        """A fresh QuestionSession on the correct reading's numbers (expanded once, then copied)."""
        if self._proto is None:
            values = {k: engine.fmt(v) for k, v in self.run["inputs"].items()}
            self._proto = QuestionSession(self.plan["question"], values, self.classifier, ask_final=False)
        return self._proto.fresh()

    def _start_solving(self):
        self.phase = "solve"
        self.question = self._probe()
        lines = engine.bind_lines(self.wp, self.plan, self.run)
        return [Feedback(kind="info", message="So the story gives: " + "; ".join(lines) + ".\n"
                                              f"Now solve: {self.question.title()}")]

    def ask(self):
        """What to ask next: {text, options, allow_step, note, decisions}. Options are picked by number; while the
        story is being read, `decisions` lists every open decision (the current one first), each answerable."""
        if self.phase == "extract":
            if self.pre_todo:
                st = self.run["before"][self.pre_todo[0]][0]
                return {"text": engine.say(st.get("say"), self.run["env"]), "options": [], "allow_step": True,
                        "note": "Write the step, like `90 / 60 = 1.5`."}
            dec = self.wp["extract"][self.di]
            decisions = [{"decision": di, "letter": LETTERS[n], "text": self.wp["extract"][di]["say"],
                          "options": self.options_of(di)} for n, di in enumerate(self.open_decisions())]
            note = "Pick one, or just start solving by writing your first step."
            if len(decisions) > 1:
                note += " The other decisions can be answered in any order (type `b2` for option 2 of decision b)."
            return {"text": dec["say"], "options": self.options_of(self.di), "allow_step": True, "note": note,
                    "decisions": decisions}
        if self.phase == "solve":
            return self.question.ask()
        if self.phase == "then":
            return {"text": "What's the next step?", "options": [], "allow_step": True}
        if self.phase == "answer":
            return {"text": "So what's the answer to the story?", "options": self._final_options() or [], "allow_step": False}
        return {"text": "", "options": [], "allow_step": False}

    def prompt(self):
        ask = self.ask()
        text = prompt_text(ask)
        for d in ask.get("decisions", [])[1:]:
            text += f"\n({d['letter']}) {d['text']}\n" + "\n".join(f"  [{d['letter']}{i}] {o}" for i, o in enumerate(d["options"], 1))
        return text

    def _final_options(self):
        final = self.run["final"]
        if not isinstance(final, str):
            return None
        return list(dict.fromkeys((self.plan["answer_map"] or {}).values())) or [final]

    # ------------------------------------------------------------ input

    def submit(self, text):
        """Typed text: parse it for the current phase, then submit it."""
        if self.phase == "extract":
            if self.pre_todo:
                try:
                    inp = parse(text)
                except ParseError as e:
                    return [Feedback(kind="error", message=str(e))]
                return self.submit_input(inp)
            m = re.fullmatch(r"\s*([a-z])\s*(\d+)\s*", text.lower())
            ask = self.ask()
            if m and m[1] in [d["letter"] for d in ask["decisions"]]:  # b2: option 2 of decision b
                di = next(d["decision"] for d in ask["decisions"] if d["letter"] == m[1])
                return self.submit_input(ChoiceAnswer(index=max(1, int(m[2])), decision=di))
            try:
                inp = parse(text, choices=len(self.wp["extract"][self.di]["options"]))
            except ParseError as e:
                return [Feedback(kind="error", message=str(e))]
            return self.submit_input(inp)
        if self.phase == "solve":
            return self._solved(self.question.submit(text))
        if self.phase == "then":
            try:
                step = parse(text)
            except ParseError as e:
                return [Feedback(kind="error", message=str(e))]
            return self.submit_input(step)
        if self.phase == "answer":
            return self._answer(text)
        return [Feedback(kind="info", message="This one is finished.")]

    def submit_input(self, inp):
        """A typed StudentInput (from the parser, a structured UI, or a model)."""
        if self.phase == "extract":
            return self._pre(inp) if self.pre_todo else self._extract(inp)
        if self.phase == "solve":
            return self._solved(self.question.submit_input(inp))
        if self.phase == "then":
            return self._then(inp)
        if self.phase == "answer":
            return self._answer_input(inp, None)
        return [Feedback(kind="info", message="This one is finished.")]

    def _solved(self, out):
        if self.question.phase == "done":
            out += self._after_question()
        return out

    def decide(self, di, index):
        """Answer decision di (any open one) with option `index` as shown (1-based)."""
        return self._extract(ChoiceAnswer(index=index, decision=di))

    def _extract(self, inp):
        if inp.kind == "choice":
            di = self.di if inp.decision is None else inp.decision
            if di not in self.open_decisions():
                return [Feedback(kind="error", message="That decision is settled already." if 0 <= di < len(self.wp["extract"])
                                 else "There's no such decision.")]
            dec = self.wp["extract"][di]
            if inp.index > len(dec["options"]):
                return [Feedback(kind="error", message=f"Pick a number from 1 to {len(dec['options'])}.")]
            o = dec["options"][self.order[di][inp.index - 1]]
            if o.get("correct"):
                self.decided.add(di)
                out = [Feedback(kind="correct", message=f"✓ {o['say']}.")]
                self.pre_todo = self._pre_steps(di)
                if self.pre_todo:
                    self.di = di
                    return out + [self._ask_pre()]
                return out + self._next_decision()
            t = next(t for t in self.info["traps"] if t["option"] is o)
            self.di = di
            return [Feedback(kind="trap", message=f"Not quite. {o['trap']} {self._trap_result(t)}")]
        if inp.kind == "value":
            return [Feedback(kind="error", message="Pick an option by its number, or write a step like `4 x 18 = 72`.")]
        return self._jump(inp)

    def _trap_result(self, t):
        """What a trap's reading leads to. When it gives the same answer, say so: the answer can't catch it."""
        if t["same_as_correct"]:
            return (f"That reading happens to give the same answer, {engine.show(t['run']['final'])}, but for the wrong "
                    "reason, so the answer can't show the mistake. Try again.")
        return f"That reading gives {engine.show(t['run']['final'])}. Try again."

    def _pre(self, step):
        """A step on a settled decision's ✓ edge (90 ÷ 60 = 1.5)."""
        if step.kind in ("choice", "value"):
            return [Feedback(kind="error", message="Write the step, like `90 / 60 = 1.5`.")]
        i = self.pre_todo[0]
        st, args, result = self.run["before"][i]
        c = Candidate(id="pre", op=st["op"], operands=list(args), result=result,
                      expression=engine.expression(st, args, result))
        cls = self.classifier.classify(step, [c])
        if cls.status != "match":
            return [Feedback(kind="unknown", message="That's not the step I expected. Type `hint` for a nudge.")]
        if cls.arithmetic_ok is False:
            return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”.")]
        self.pre_todo.pop(0)
        self.pre_done.add(i)
        out = [Feedback(kind="correct", message=f"✓ {c.expression}  ({engine.say(st.get('say'), self.run['env'])})")]
        return out + ([self._ask_pre()] if self.pre_todo else self._next_decision())

    def _pre_for(self, step):
        """(decision, before index) when the step is one on the ✓ edge of a decision not yet settled."""
        for di in self.open_decisions():
            for i in self._pre_steps(di):
                st, args, result = self.run["before"][i]
                c = Candidate(id="pre", op=st["op"], operands=list(args), result=result)
                if self.classifier.classify(step, [c]).status == "match":
                    return di, i
        return None

    def _jump(self, step):
        """The student skipped the decisions and started computing. Work out which reading their step comes from:
        a step of a decision's own (90 ÷ 60, the conversion), a first step of the correct reading, or a trap's."""
        pre = self._pre_for(step)
        if pre:
            di, i = pre
            o = next(o for o in self.wp["extract"][di]["options"] if o.get("correct"))
            self.decided.add(di)
            self.pre_todo = [i] + [j for j in self._pre_steps(di) if j != i]
            self.di = di
            dec = self.wp["extract"][di]
            fb = [Feedback(kind="info", message=f"That step settles it: {dec['say']} {o['say']}.")] + self._pre(step)
            return fb
        cands = self._probe().candidates()
        cls = self.classifier.classify(step, cands)
        exact = cls.status == "match" and any(not is_wildcard(c) for c in cands if c.id in cls.matched)
        trap = self._trap_for(step)
        if exact or (cls.status == "match" and not trap):
            rest = [self.wp["extract"][di] for di in range(len(self.wp["extract"])) if di not in self.decided]
            self.decided = set(range(len(self.wp["extract"])))
            self.pre_todo = []
            out = [Feedback(kind="info", message="That step means you read the story right: "
                                                 + "; ".join(next(o["say"] for o in d["options"] if o.get("correct")) for d in rest) + ".")]
            out += self._start_solving()
            out += self.question.submit_step(step)
            if self.question.phase == "done":
                out += self._after_question()
            return out
        if trap:
            self.di = trap["decision"]
            same = (" It happens to give the same answer, for the wrong reason." if trap["same_as_correct"] else
                    f" That gives {engine.show(trap['run']['final'])}.")
            return [Feedback(kind="trap", message=f"“{written(step)}” looks like this reading: {trap['option']['trap']}"
                                                  f"{same} Let's sort out this decision first.")]
        return [Feedback(kind="unknown", message=f"I can't tell which reading “{written(step)}” comes from. "
                                                 "Pick an option, or type `hint`.")]

    def _trap_for(self, step):
        """The trap whose giveaway steps include this step, if any: the trap's own steps on its branch (18 + 6 = 24),
        and the first steps of its question, plots and comparisons included."""
        correct = set(self.run["firsts"])
        for t in self.info["traps"]:
            if t["decision"] in self.decided:
                continue
            keys = list(t["pre_firsts"])
            if all(isinstance(v, str) for v in t["plan"]["binds"].values()):
                keys += [k for k in t["run"]["firsts"] if k not in correct]
            for key in keys:
                c = _key_candidate(key)
                if c and self.classifier.classify(step, [c]).status == "match":
                    return t
        return None

    def _after_question(self):
        """The walked route's answer, not the default route's: an equality-only method (simplify) can't say which
        is better, so the student tries another method."""
        result = self.question.result
        if result == "not equal":
            self.question = self._probe()
            return [Feedback(kind="info", message="Simplifying shows they aren't equal, but not which is bigger. "
                                                  "Try another method to decide: what's your first step?")]
        out = [Feedback(kind="info", message=f"The question's answer is {engine.show(result)}.")]
        if self.run["after"]:
            self.phase = "then"
            return out + [Feedback(kind="info", message="One more step to answer the story.")]
        self.phase = "answer"
        return out

    def _then(self, step):
        if step.kind in ("choice", "value"):
            return [Feedback(kind="error", message="Write the step, like `80 - 12 = 68`.")]
        st, args, result = self.run["after"][self.then_pos]
        c = Candidate(id="then", op=st["op"], operands=list(args), result=result,
                      expression=engine.expression(st, args, result))
        cls = self.classifier.classify(step, [c])
        if cls.status != "match":
            return [Feedback(kind="unknown", message="That's not the step I expected. Type `hint` for a nudge.")]
        if cls.arithmetic_ok is False:
            return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”.")]
        self.then_pos += 1
        out = [Feedback(kind="correct", message=f"✓ {c.expression}")]
        if self.then_pos >= len(self.run["after"]):
            self.phase = "answer"
        return out

    def _answer(self, text):
        try:
            inp = parse(text, choices=len(self._final_options() or []))
        except ParseError:
            inp = None
        return self._answer_input(inp, text)

    def _answer_input(self, inp, text):
        final = self.run["final"]
        opts = self._final_options()
        if opts:
            given = opts[inp.index - 1] if inp and inp.kind == "choice" and inp.index <= len(opts) else (text or "").strip()
            ok = given.lower() == final.lower()
        else:
            ok = bool(inp) and inp.kind == "value" and inp.value.close_to(engine.num(final))
        if not ok:
            return [Feedback(kind="unknown", message="Not quite. Check what the question asks for: "
                                                     f"{self.wp['asks']['text']}.")]
        self.phase = "done"
        return [Feedback(kind="done", message=f"✓ {self.wp['answer_text']}")]

    # ------------------------------------------------------------ help

    def hint(self):
        if self.phase == "extract":
            if self.pre_todo:
                st = self.run["before"][self.pre_todo[0]][0]
                return [Feedback(kind="hint", message=f"Next: {engine.say(st.get('say'), self.run['env'])}")]
            dec = self.wp["extract"][self.di]
            c = engine.EXTRACTION["concepts"][dec["concept"]]
            cues = f" Look for: {', '.join(c['cues'])}." if c.get("cues") else ""
            same = any(t["decision"] == self.di and t["same_as_correct"] for t in self.info["traps"])
            warn = " Careful: a wrong reading here gives the same answer, so the answer alone won't tell." if same else ""
            return [Feedback(kind="hint", message=f"{c['name']}: {c['does']}{cues}{warn}")]
        if self.phase == "solve":
            return self.question.hint()
        if self.phase == "then":
            st = self.run["after"][self.then_pos][0]
            return [Feedback(kind="hint", message=f"Next: {engine.say(st.get('say'), self.run['env'])}")]
        if self.phase == "answer":
            return [Feedback(kind="hint", message=f"The question asks: {self.wp['asks']['text']}.")]
        return []

    def where(self):
        if self.question:
            return self.question.where()
        return [Feedback(kind="info", message=f"Decisions made: {len(self.decided)} of {len(self.wp['extract'])}.")]

    def done_command(self):
        if self.phase == "solve":
            return self._solved(self.question.finish_steps())
        return [Feedback(kind="info", message="Not yet.")]

    # ------------------------------------------------------------ structured input (boxes mode)

    def choose_method(self, mid):
        if self.phase != "solve":
            return [Feedback(kind="error", message="Choose a method once the story's numbers are settled.")]
        return self.question.choose_method(mid)

    def then_step(self):
        """The follow-up step still to do, as (step dict, args, result), or None."""
        if self.phase == "then" and self.then_pos < len(self.run["after"]):
            return self.run["after"][self.then_pos]
        return None

    def pre_step(self):
        """The step on a settled decision's ✓ edge still to write, as (step dict, args, result), or None."""
        return self.run["before"][self.pre_todo[0]] if self.phase == "extract" and self.pre_todo else None


LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _key_candidate(key):
    """A Candidate from a giveaway's label key (op, formatted values, result): numbers, ratios (3:4) and points."""
    op, vals, res = key
    part = lambda v: tuple(Fraction(x) for x in v.split(":")) if ":" in v else Fraction(v)
    try:
        operands = [part(v) for v in vals]
    except (ValueError, ZeroDivisionError):
        return None
    if op == "compare":
        return Candidate(id="trap", op="compare", operands=operands, result=res, source="trap")
    return Candidate(id="trap", op=op, operands=operands, source="trap")


def catalog():
    """Every practice item: word problems first, then each question's examples."""
    items = [(wid, f"Word problem: {wp['title']}", lambda wid=wid: WordProblemSession(wid)) for wid, wp in engine.WP.items()]
    for qid, q in engine.Q.items():
        for i, ex in enumerate(q["examples"], 1):
            items.append((f"{qid}:{i}", f"{q['title']}: {engine.render(q['prompt'], ex['values'])}",
                          lambda qid=qid, ex=ex: QuestionSession(qid, ex["values"])))
    return items
