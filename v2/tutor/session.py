"""Walk a student through a question or a word problem, one step at a time.

A QuestionSession keeps the set of routes (ways through the question's methods) that are still consistent with what
the student has written. The first step, and the second where methods share a first step, are classified against the
generated first-step trees (trees/<question>.json); later steps against the next step of each route still alive.
A WordProblemSession runs the extraction decisions first, then a QuestionSession on the extracted numbers, then any
follow-up step, then asks for the answer in the story's terms.
"""

import json
import random
from fractions import Fraction

import build as engine

from .classifier import Classifier, RuleClassifier, is_wildcard
from .models import Candidate, Feedback
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
    for depth in range(len(loc) - 1):  # inside a call: lead with what the call is for
        call = next((c for c in v["calls"] if tuple(c["loc"]) == tuple(loc[:depth + 1])), None)
        if call and call["say"]:
            text = f"{engine.say(call['say'], env)}: {text[:1].lower()}{text[1:]}"
            break
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
        self.live = {r: 0 for r in range(len(self.routes))}  # route → number of its visible steps done
        self.tree_entries = tree(qid)["first_steps"]  # the first steps are classified against the tree
        self.slips = 0
        self.hints = 0
        self.history = []
        self.ask_final = ask_final and self.q["outputs"] == ["answer"]
        self.phase = "steps"
        self.result = None
        self.finished = None

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

    def names(self, mids):
        return " or ".join(self.methods[m]["name"] for m in sorted(mids))

    def next_step(self, r, offset=0):
        route, at = self.routes[r], self.live[r] + offset
        return step_candidate("x", route, at) if len(route[3]) > at else None

    def candidates(self):
        """What the student's step is classified against: the tree's entries for the first steps, then the next
        step of every live route."""
        if self.tree_entries is not None:
            return tree_candidates(self.tree_entries, {k: engine.num(v) for k, v in self.values.items()}, "t")
        seen = {}
        for r in self.live:
            c = self.next_step(r)
            if c:
                key = (c.op, c.expression)
                if key in seen:
                    seen[key].methods = sorted(set(seen[key].methods) | set(c.methods))
                else:
                    seen[key] = c.model_copy(update={"id": f"r{len(seen)}"})
        return list(seen.values())

    # ------------------------------------------------------------ input

    def submit(self, text):
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
        first = None
        for step in readings:  # `4/3 = 4/3` can be a division or a comparison: use the reading that fits
            fb = self.submit_step(step)
            if any(f.kind in ("correct", "slip", "on_track") for f in fb):
                return fb
            first = first or fb
        return first

    def submit_step(self, step):
        cands = self.candidates()
        cls = self.classifier.classify(step, cands)
        if cls.status == "none":
            extra = f" (Also, {written(step).split(' = ')[0]} is {cls.expected_result}.)" if cls.arithmetic_ok is False else ""
            return [Feedback(kind="unknown", message=f"I don't recognize “{written(step)}” as a next step here.{extra} "
                                                     "Type `hint` for a nudge.")]
        chosen = [c for c in cands if c.id in cls.matched]
        allowed = set().union(*(set(c.methods) for c in chosen))
        mental = any(c.mental for c in chosen)

        advanced, waiting = {}, {}
        for r, at in self.live.items():
            if self.routes[r][0]["method"] not in allowed:
                continue
            for offset in ((1,) if mental and at == 0 else (0,)):
                c = self.next_step(r, offset)
                res = self.classifier.classify(step, [c]) if c else None
                if res and res.status == "match":
                    advanced[r] = at + offset + 1
                elif res and res.status == "on_track":
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
            target = next(self.next_step(r).search["target"] for r in waiting)
            return [Feedback(kind="on_track", message=f"Good, keep building: {written(step)}. "
                                                      f"Keep going until you reach {engine.fmt(target)}.")]

        before = set(self.live_methods())
        if self.tree_entries is not None:  # go down the tree while the method is still open, then leave it
            alive_methods = {self.routes[r][0]["method"] for r in advanced}
            nexts = [n for c in chosen if c.id.startswith("t") for n in self.tree_entries[int(c.id[1:])].get("next", [])
                     if set(n["methods"]) & alive_methods]
            self.tree_entries = nexts if len(alive_methods) > 1 and nexts and not self.history and not mental else None
        r0 = next(iter(advanced))
        done = step_candidate("x", self.routes[r0], advanced[r0] - 1)
        self.live = {**waiting, **advanced}
        self.slips = self.hints = 0
        self.history.append(done.expression)
        out = slip
        if mental:
            skipped = step_candidate("x", self.routes[r0], advanced[r0] - 2)
            out.append(Feedback(kind="info", message=f"You did {skipped.expression} in your head. Fine."))
        out.append(Feedback(kind="correct", message=f"✓ {done.expression}  ({done.say})"))
        after = set(self.live_methods())
        if len(after) == 1 and after != before:
            m = self.methods[next(iter(after))]
            out.append(Feedback(kind="method", message=f"You're using: {m['name']}. {engine.render(m.get('idea', ''), self.values)}"))
        elif len(after) > 1 and after != before:
            out.append(Feedback(kind="method", message=f"That step starts {self.names(after)}. Your next step will tell which."))
        if all(self.next_step(r) is None for r in self.live):
            out += self.finish_steps()
        return out

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
        expected = self.result
        opts = answer_options(self.qid)
        try:
            inp = parse(text, choices=len(opts or []))
        except ParseError:
            inp = None
        if opts:
            given = opts[inp.index - 1] if inp and inp.kind == "choice" and inp.index <= len(opts) else text.strip().lower()
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
                                              f"You used {self.names(self.live_methods())}.")]

    # ------------------------------------------------------------ help

    def hint(self):
        self.hints += 1
        if self.phase == "answer":
            return [Feedback(kind="hint", message=f"Your last step was {self.history[-1]}. What does it tell you?")]
        nexts = {}
        for r in self.live:
            c = self.next_step(r)
            if c:
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
        return [Feedback(kind="info", message=f"Your steps so far:\n  {done}\nStill possible: {self.names(self.live_methods())}")]


class WordProblemSession:
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
        self.question = None
        self.then_pos = 0
        self.phase = "extract"
        self.pending = self._next_decision()

    # ------------------------------------------------------------ what to show

    def intro(self):
        return f"{self.wp['title']}\n\n{self.wp['text']}\n"

    def _next_decision(self):
        """Move to the next undecided decision; decisions without traps are simply announced."""
        out = []
        for di, dec in enumerate(self.wp["extract"]):
            if di in self.decided:
                continue
            if all(o.get("correct") for o in dec["options"]):
                self.decided.add(di)
                out.append(Feedback(kind="info", message=f"{dec['say']} {dec['options'][0]['say']}."))
                continue
            self.di = di
            return out
        self.di = None
        return out + self._start_solving()

    def _start_solving(self):
        self.phase = "solve"
        values = {k: engine.fmt(v) for k, v in self.run["inputs"].items()}
        self.question = QuestionSession(self.plan["question"], values, self.classifier, ask_final=False)
        lines = engine.bind_lines(self.wp, self.plan, self.run)
        return [Feedback(kind="info", message="So the story gives: " + "; ".join(lines) + ".\n"
                                              f"Now solve: {self.question.title()}")]

    def ask(self):
        """What to ask next: {text, options, allow_step, note}. Options are picked by number."""
        if self.phase == "extract":
            dec = self.wp["extract"][self.di]
            return {"text": dec["say"], "options": [dec["options"][j]["say"] for j in self.order[self.di]],
                    "allow_step": True, "note": "Pick one, or just start solving by writing your first step."}
        if self.phase == "solve":
            return self.question.ask()
        if self.phase == "then":
            return {"text": "What's the next step?", "options": [], "allow_step": True}
        if self.phase == "answer":
            return {"text": "So what's the answer to the story?", "options": self._final_options() or [], "allow_step": False}
        return {"text": "", "options": [], "allow_step": False}

    def prompt(self):
        return prompt_text(self.ask())

    def _final_options(self):
        final = self.run["final"]
        if not isinstance(final, str):
            return None
        return list(dict.fromkeys((self.plan["answer_map"] or {}).values())) or [final]

    # ------------------------------------------------------------ input

    def submit(self, text):
        if self.phase == "extract":
            return self._extract(text)
        if self.phase == "solve":
            out = self.question.submit(text)
            if self.question.phase == "done":
                out += self._after_question()
            return out
        if self.phase == "then":
            return self._then(text)
        if self.phase == "answer":
            return self._answer(text)
        return [Feedback(kind="info", message="This one is finished.")]

    def _extract(self, text):
        dec = self.wp["extract"][self.di]
        try:
            inp = parse(text, choices=len(dec["options"]))
        except ParseError as e:
            return [Feedback(kind="error", message=str(e))]
        if inp.kind == "choice":
            if inp.index > len(dec["options"]):
                return [Feedback(kind="error", message=f"Pick a number from 1 to {len(dec['options'])}.")]
            o = dec["options"][self.order[self.di][inp.index - 1]]
            if o.get("correct"):
                self.decided.add(self.di)
                return [Feedback(kind="correct", message=f"✓ {o['say']}.")] + self._next_decision()
            t = next(t for t in self.info["traps"] if t["option"] is o)
            return [Feedback(kind="trap", message=f"Not quite. {o['trap']} That reading gives {engine.show(t['run']['final'])}. "
                                                  "Try again.")]
        if inp.kind == "value":
            return [Feedback(kind="error", message="Pick an option by its number, or write a step like `4 x 18 = 72`.")]
        return self._jump(inp)

    def _jump(self, step):
        """The student skipped the decisions and started computing. Work out which reading their step comes from."""
        values = {k: engine.fmt(v) for k, v in self.run["inputs"].items()}
        probe = QuestionSession(self.plan["question"], values, self.classifier, ask_final=False)
        cands = probe.candidates()
        cls = self.classifier.classify(step, cands)
        exact = cls.status == "match" and any(not is_wildcard(c) for c in cands if c.id in cls.matched)
        trap = self._trap_for(step)
        if exact or (cls.status == "match" and not trap):
            rest = [self.wp["extract"][di] for di in range(len(self.wp["extract"])) if di not in self.decided]
            self.decided = set(range(len(self.wp["extract"])))
            out = [Feedback(kind="info", message="That step means you read the story right: "
                                                 + "; ".join(next(o["say"] for o in d["options"] if o.get("correct")) for d in rest) + ".")]
            out += self._start_solving()
            out += self.question.submit_step(step)
            if self.question.phase == "done":
                out += self._after_question()
            return out
        if trap:
            self.di = trap["decision"]
            return [Feedback(kind="trap", message=f"“{written(step)}” looks like this reading: {trap['option']['trap']} "
                                                  f"That gives {engine.show(trap['run']['final'])}. Let's sort out this decision first.")]
        return [Feedback(kind="unknown", message=f"I can't tell which reading “{written(step)}” comes from. "
                                                 "Pick an option, or type `hint`.")]

    def _trap_for(self, step):
        """The trap whose giveaway first steps include this step, if any."""
        correct = set(self.run["firsts"])
        for t in self.info["traps"]:
            for key, expr in t["run"]["firsts"].items():
                if key in correct or any(not isinstance(v, str) for v in t["plan"]["binds"].values()):
                    continue
                op, vals, res = key
                if op in ("plot", "compare"):
                    continue
                c = Candidate(id="trap", op=op, operands=[Fraction(v) for v in vals], source="trap")
                if self.classifier.classify(step, [c]).status == "match":
                    return t
        return None

    def _after_question(self):
        out = [Feedback(kind="info", message=f"The question's answer is {engine.show(self.run['result'])}.")]
        if self.run["after"]:
            self.phase = "then"
            return out + [Feedback(kind="info", message="One more step to answer the story.")]
        self.phase = "answer"
        return out

    def _then(self, text):
        try:
            step = parse(text)
        except ParseError as e:
            return [Feedback(kind="error", message=str(e))]
        if step.kind in ("choice", "value"):
            return [Feedback(kind="error", message="Write the step, like `80 - 12 = 68`.")]
        st, args, result = self.run["after"][self.then_pos]
        c = Candidate(id="then", op=st["op"], operands=list(args), result=result,
                      expression=engine.expression(st, args, result))
        if step.kind in ("choice", "value"):
            return [Feedback(kind="error", message="Write the step, like `80 - 12 = 68`.")]
        cls = self.classifier.classify(step, [c])
        if cls.status != "match":
            return [Feedback(kind="unknown", message=f"That's not the step I expected. Type `hint` for a nudge.")]
        if cls.arithmetic_ok is False:
            return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”.")]
        self.then_pos += 1
        out = [Feedback(kind="correct", message=f"✓ {c.expression}")]
        if self.then_pos >= len(self.run["after"]):
            self.phase = "answer"
        return out

    def _answer(self, text):
        final = self.run["final"]
        opts = self._final_options()
        try:
            inp = parse(text, choices=len(opts or []))
        except ParseError:
            inp = None
        if opts:
            given = opts[inp.index - 1] if inp and inp.kind == "choice" and inp.index <= len(opts) else text.strip()
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
            dec = self.wp["extract"][self.di]
            c = engine.EXTRACTION["concepts"][dec["concept"]]
            cues = f" Look for: {', '.join(c['cues'])}." if c.get("cues") else ""
            return [Feedback(kind="hint", message=f"{c['name']}: {c['does']}{cues}")]
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
            out = self.question.finish_steps()
            if self.question.phase == "done":
                out += self._after_question()
            return out
        return [Feedback(kind="info", message="Not yet.")]


def catalog():
    """Every practice item: word problems first, then each question's examples."""
    items = [(wid, f"Word problem: {wp['title']}", lambda wid=wid: WordProblemSession(wid)) for wid, wp in engine.WP.items()]
    for qid, q in engine.Q.items():
        for i, ex in enumerate(q["examples"], 1):
            items.append((f"{qid}:{i}", f"{q['title']}: {engine.render(q['prompt'], ex['values'])}",
                          lambda qid=qid, ex=ex: QuestionSession(qid, ex["values"])))
    return items
