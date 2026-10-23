"""Walk a student through a question or a word problem, one step at a time.

A QuestionSession keeps the set of routes (ways through the question's methods) that are still consistent with what
the student has written. The first step, and the second where methods share a first step, are classified against the
generated first-step trees (trees/<question>.json); later steps against the next step of each route still alive.
A step that is no live route's next step is matched further along each route, against every quantity on it
(paths.py): the steps it skips become done in the head. A bare number is a statement too: the answer, or a quantity
on some route. A WordProblemSession runs the extraction decisions first, then a QuestionSession on the extracted
numbers, then any follow-up step, then asks for the answer in the story's terms. A statement made before the
decisions settles them when it fits the correct reading, and names the trap when it fits only a trap's reading.
"""

import copy
import json
import random
import re
from fractions import Fraction

import build as engine

from .classifier import Classifier, RuleClassifier, is_wildcard, step_op
from .models import Candidate, ChoiceAnswer, Feedback, Number, ValueAnswer
from .parse import ParseError, parse, parse_all
from .paths import QuestionIndex, word_problem_index

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
        self.announced = None  # the method last announced as "You're using"
        self.so_far = None  # the method announced as "That's X so far", while another was still building up
        self.tries = {}    # (route, position) → build-up steps written toward that step (6 × 2 = 12 toward 6 × 3)
        self.tree_entries = tree(qid)["first_steps"]  # the first steps are classified against the tree
        self.paths = QuestionIndex(qid, self.values, self.routes)  # every quantity on every route
        self.inhead = {}   # route → its visible positions taken as done in the head
        self.owed = {}     # route → visible positions it skipped that the later step didn't need: still to write
        self.said = []     # the statements taken so far, in order: the shadow is worked out from them
        self.shadow = {}   # route → position, while a statement is matched against the shadow (_shadow)
        self.chosen = None  # the method picked from the cards (boxes), if any
        self.last_match = None  # how the last accepted step fitted: "exact", "wildcard" (a tree wildcard) or "skip"
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
        new.choices, new.named, new.tries, new.history, new.announced = {}, None, {}, [], None
        new.inhead, new.owed, new.said, new.shadow, new.chosen, new.last_match = {}, {}, [], {}, None, None
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
            readings = [r for r in parse_all(text) if r.kind != "choice"]
        except ParseError as e:
            return [Feedback(kind="error", message=str(e))]
        steps = [r for r in readings if r.kind != "value"]
        values = [r for r in readings if r.kind == "value"]
        fb = self.submit_readings(steps) if steps else None
        if values and (fb is None or not any(f.kind in ("correct", "slip", "on_track") for f in fb)):
            # a bare number (19/12 is a number too, not only 19 ÷ 12): the answer, or a quantity on some route
            fv = self.submit_value(values[0])
            if fb is None or any(f.kind in ("correct", "done") for f in fv):
                return fv
        return fb

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
        if inp.kind == "choice":
            return [Feedback(kind="error", message="There's nothing to pick here. Write a step, like `4 x 18 = 72`.")]
        if inp.kind == "value":
            return self.submit_value(inp)
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
        self._current = step
        pool = {**self.live, **self._rechosen(step)}  # routes re-run with the student's own factor or power of ten
        cands = self.candidates(pool)
        cls = self.classifier.classify(step, cands)
        chosen, advanced, waiting, skipped = [], {}, {}, set()
        if cls.status == "match":  # every entry the step fits names a method the graph draws on this step; the
            # exact one only decides the arithmetic feedback. The routes then filter by the actual numbers.
            chosen = [c for c in cands if self.classifier.classify(step, [c]).status == "match"]
        elif cls.status == "on_track":
            chosen = [c for c in cands if c.id in cls.matched]
        allowed = set().union(*(set(c.methods) for c in chosen))
        mental = set().union(*(set(c.methods) for c in chosen if c.mental))
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
        # a step that is no live route's next step may be one further along a live route (the steps before it done
        # in the head), or else along a route of the shadow
        far = {} if advanced else self._reach(step, self.live)
        # a build-up (6 × 2 = 12 toward 18) stays one; the routes it fits further along stay live beside it, not
        # named. Only a build-up toward a power of ten, which the question doesn't name, loses to a route's answer
        # (4 × 3 = 12 is scale factor's answer, not the start of 4 × 25 = 100).
        beside = {}
        if waiting:
            toward = all("until" not in self.routes[r][2][self.routes[r][3][at]][0].get("search", {"until": 1})
                         for r, at in waiting.items())
            beside = {r: p for r, p in far.items() if not toward or p < len(self.routes[r][3]) - 1}
            far = {r: p for r, p in far.items() if r not in beside}
        if not advanced and not waiting and not far:
            far = self._reach(step, self._shadow())
        if not advanced and far:
            for r, at in waiting.items():
                self.tries[(r, at)] = self.tries.get((r, at), []) + [written(step)]
            return self._skipped_to(step, far, waiting)
        if not advanced and not waiting:
            if cls.status == "none":
                extra = f" (Also, {written(step).split(' = ')[0]} is {cls.expected_result}.)" if cls.arithmetic_ok is False else ""
                return [Feedback(kind="unknown", message=f"I don't recognize “{written(step)}” as a step here.{extra} "
                                                         "Type `hint` for a nudge.")]
            exact = set().union(*(set(c.methods) for c in chosen if not is_wildcard(c))) & set(self.live_methods())
            if not exact:  # only a wildcard fits (any whole number in a build-up): that names no method
                return [Feedback(kind="unknown", message=f"I don't recognize “{written(step)}” as a step here. "
                                                         "Type `hint` for a nudge.")]
            return [Feedback(kind="unknown", message=f"“{written(step)}” is how {self.names(exact)} starts, but those "
                                                     "numbers don't lead anywhere here. Type `hint` for a nudge.")]
        if cls.arithmetic_ok is False:
            self.slips += 1
            if self.slips < 2:
                return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”. Try it again.")]
            slip = [Feedback(kind="slip", message=f"It's {cls.expected_result}. Let's carry on with that.")]
        else:
            slip = []
        if not advanced:
            for r, p in beside.items():
                self.inhead.setdefault(r, set()).update(range(self.live[r], p))
            self.live = {**{r: p + 1 for r, p in beside.items()}, **waiting}
            self.named = {self.routes[r][0]["method"] for r in waiting}
            for r, at in waiting.items():
                self.tries[(r, at)] = self.tries.get((r, at), []) + [written(step)]
            target = next(self.next_step(r).search["target"] for r in waiting)
            self.last_match = "skip" if beside else "exact"
            return [Feedback(kind="on_track", message=f"Good, keep building: {written(step)}. "
                                                      f"Keep going until you reach {engine.fmt(target)}.")]

        before = set(self.named_methods())
        alive_methods = {self.routes[r][0]["method"] for r in advanced}
        self.last_match = "exact" if any(not is_wildcard(c) and set(c.methods) & alive_methods for c in chosen) else "wildcard"
        if self.tree_entries is not None:  # go down the tree while the method is still open, then leave it
            nexts = [n for c in chosen if c.id.startswith("t") for n in self.tree_entries[int(c.id[1:])].get("next", [])
                     if set(n["methods"]) & alive_methods]
            self.tree_entries = nexts if len(alive_methods) > 1 and nexts and not self.history and not skipped else None
        r0 = min(advanced, key=lambda r: (r in skipped, r))
        for r in skipped:
            self.inhead.setdefault(r, set()).add(0)
        out = slip
        if r0 in skipped:
            skipped_step = step_candidate("x", self.routes[r0], advanced[r0] - 2)
            out.append(Feedback(kind="info", message=f"You did {skipped_step.expression} in your head. Fine."))
        return self._advance(advanced, waiting, r0, before, out)

    def _at(self, r):
        return self.live[r] if r in self.live else self.shadow[r]

    def _shadow(self):
        """The routes that fit every statement so far but aren't live, each at its own position: {route: position}.
        A statement that was some live route's next step left them out (5 × 12 = 60 starts cross-multiply, and is
        common denominator's step after LCM(6, 4) = 12 done in the head). They are worked out from the statements
        only when no live route fits one, so a student who writes every step never pays for them."""
        pool = {r: 0 for r in range(self.expanded) if self.chosen in (None, self.routes[r][0]["method"])}
        head, owed = {r: set() for r in pool}, {}
        for inp in self.said:
            reach = self._reach(inp, pool, prune=False, owed=owed)  # every route that fits, not only the tightest
            moved = {r: self._move(r, pool[r], p, owed.get(r, frozenset())) for r, p in reach.items()}
            for r, (at, o, h) in moved.items():
                head[r] |= h
                owed[r] = o
            pool = {r: at for r, (at, o, h) in moved.items()}
        self.shadow = {r: at for r, at in pool.items() if r not in self.live}
        for r in self.shadow:
            self.inhead[r], self.owed[r] = head[r], owed.get(r, frozenset())
        return self.shadow

    def _ended(self, r):
        """A route is finished when its last step is done and no skipped step is still to write."""
        return self.next_step(r) is None and not self.owed.get(r)

    def _move(self, r, at, p, owed):
        """Route r at position `at` (owing the steps `owed`) fits its step p: (new position, steps still owed, steps
        done in the head). An owed step written leaves the position. Of the steps p skips, the ones p needs were done
        in the head, and the others are still to write (6 ÷ 2 = 3 before 6 × 3 = 18 in walk-to-school)."""
        if p < at:
            return at, owed - {p}, set()
        loose = set(self.paths.head(self.routes[r], at, p))
        return p + 1, frozenset(owed | loose), set(range(at, p)) - loose

    def _apply(self, far):
        """Move the routes in `far` (route → the position of the step the statement fits): {route: new position}."""
        out = {}
        for r, p in far.items():
            at, o, h = self._move(r, self._at(r), p, self.owed.get(r, frozenset()))
            self.inhead.setdefault(r, set()).update(h)
            self.owed[r] = o
            out[r] = at
        return out

    def _advance(self, advanced, others, r0, before, out, skipped_to=False, shown=None, pos=None):
        """Move the routes the step fits on: `advanced` (route → its new position) are named for it, `others` stay
        live without being named. r0 is the route whose step is shown; `before` the methods named until now;
        `skipped_to` says the step was found further along the routes; `shown` replaces the step shown; `pos`
        (route → position) is where the step was found, when that isn't just before the new position (an owed step)."""
        done = step_candidate("x", self.routes[r0], pos[r0] if pos else advanced[r0] - 1)
        alive_methods = {self.routes[r][0]["method"] for r in advanced}
        self.said.append(self._current)
        self.shadow = {}
        self.live = {**others, **advanced}
        self.named = alive_methods
        self.slips = self.hints = 0
        self.history.append(shown or done.expression)
        out.append(Feedback(kind="correct", message=f"✓ {shown}" if shown else f"✓ {done.expression}  ({done.say})"))
        after = set(self.named_methods())
        if len(after) == 1 and after != before:
            mid = next(iter(after))
            m = self.methods[mid]
            idea = method_text(self.qid, mid, 'idea', self.values)
            if set(self.live_methods()) - after and not all(self._ended(r) for r in advanced):
                # another method is still building up toward its step (and this one isn't finished)
                out.append(Feedback(kind="method", message=f"That's {m['name']} so far. {idea}"))
                self.so_far = mid
            else:
                out.append(Feedback(kind="method", message=f"You're using: {m['name']}. {idea}"))
                self.announced = mid
        elif len(after) == 1 and self.so_far in after and self.announced not in after and not set(self.live_methods()) - after:
            m = self.methods[next(iter(after))]  # the build-ups have gone: now it's settled
            out.append(Feedback(kind="method", message=f"You're using: {m['name']}."))
            self.announced = next(iter(after))
        elif len(after) > 1 and after != before:
            finishing = any(self._ended(r) for r in advanced) if skipped_to else all(self._ended(r) for r in advanced)
            out.append(Feedback(kind="method", message=f"That step fits {self.names(after)}." if finishing or skipped_to
                                else f"That step starts {self.names(after)}. Your next step will tell which."))
        # every route the step moved has ended; after a skip, one ended route is enough (4/3 < 1.4 ends unit rate,
        # while the graph route still owes its plot)
        if all(self._ended(r) for r in advanced) or (skipped_to and any(self._ended(r) for r in advanced)):
            out += self.finish_steps()
        return out

    # ------------------------------------------------------------ statements further along a route

    def _fitter(self, inp, exact=False):
        """Does a statement fit a route's trace entry? A step by its operation and numbers (the arithmetic is
        checked apart), a bare number by its value. `exact`: the numbers as typed, without rounding."""
        if inp.kind == "value":
            n = inp.value
            if exact:
                return lambda e: isinstance(e[2], Fraction) and n.value == e[2]
            return lambda e: isinstance(e[2], Fraction) and n.close_to(e[2])
        if exact and inp.kind in ("arithmetic", "function"):
            def same(e):
                x, y = e[1] if e[1] and len(e[1]) == 2 else (None, None)
                a, b = inp.left.value, inp.right.value
                return ((a, b) == (x, y) or (e[0]["op"] in ("add", "multiply", "gcf", "lcm") and (a, b) == (y, x))) \
                    and self._fits(inp, e)
            return same
        return lambda e: self._fits(inp, e)

    def _fits(self, step, entry):
        """Does a typed step fit a route's trace entry (its operation and numbers; the arithmetic is checked apart)?"""
        st, args, result = entry
        if st["op"] != step_op(step) or not engine.visible(st):
            return False
        if step.kind in ("arithmetic", "function") and any(
                "/" in n.text and any(isinstance(x, Fraction) and "." in engine.fmt(x) and n.value == x for x in args)
                for n in (step.left, step.right)):  # a fraction where the route writes a decimal: another method
            return False
        c = Candidate(id="x", op=st["op"], operands=list(args), result=result)
        return self.classifier.classify(step, [c]).status == "match"

    def _reach(self, inp, pool, prune=True, owed=None):
        """_further for a statement: the routes where it fits with its numbers exactly (6 ÷ 0.4), or else as rounded
        (0.67 for 2/3). A rounded number never wins over an exact one (0.4 isn't 0.375 when 0.4 is on a route)."""
        return (self._further(self._fitter(inp, exact=True), pool, prune, owed)
                or self._further(self._fitter(inp), pool, prune, owed))

    def _further(self, fits, pool, prune=True, owed=None):
        """The routes in `pool` (route → position) with a visible step that `fits`: a step it still owes, or the
        earliest at or after its position. {route: that step's position}. The steps it skips that it needs become
        done in the head; the others stay to write. With `prune`, a route that skips a step out of order (5 × 4
        before 3 × 7 in one order of an `all` block) counts only when no route of its method skips fewer."""
        owed = self.owed if owed is None else owed
        found, memo = {}, {}
        for r, at in pool.items():
            route = self.routes[r]
            v, env, trace, vis = route
            steps = self.paths.path(route)
            p = None
            for j in sorted(owed.get(r, ())):
                if fits(trace[vis[j]]):
                    p = j
                    break
            if p is not None:
                found[r] = (p, 0)
                continue
            for j in range(at, len(vis)):
                q = steps[j]  # routes share most of their quantities: test each one once
                if q not in memo:
                    memo[q] = fits(trace[vis[j]])
                if memo[q]:
                    p = j
                    break
            if p is not None:
                found[r] = (p, len(self.paths.head(route, at, p)))
        if not prune:
            return {r: p for r, (p, loose) in found.items()}
        best = {}
        for r, (p, loose) in found.items():
            m = self.routes[r][0]["method"]
            best[m] = min(best.get(m, loose), loose)
        return {r: p for r, (p, loose) in found.items() if loose == best[self.routes[r][0]["method"]]}

    def _head_text(self, far):
        """What the found routes did in the head, said once when they agree on it."""
        said = {tuple(step_candidate("x", self.routes[r], j).expression
                      for j in range(self._at(r), p) if j not in self.paths.head(self.routes[r], self._at(r), p))
                for r, p in far.items()}
        if () in said:  # some route fits with nothing done in the head
            return None
        if len(said) == 1:
            steps = next(iter(said))
            return f"You did {' and '.join(steps)} in your head." if len(steps) <= 2 else \
                f"You did {len(steps)} steps in your head: {', '.join(steps)}."
        return "You did the steps before it in your head."

    def _skipped_to(self, step, far, others=None):
        """A step that is no live route's next step but is a later step of some: the steps before it were done in
        the head. `others` (route → position) stay live without being named: routes the step builds up on."""
        r0 = min(far)
        c = step_candidate("x", self.routes[r0], far[r0])
        cls = self.classifier.classify(step, [c])
        if cls.arithmetic_ok is False:
            self.slips += 1
            if self.slips < 2:
                return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”. Try it again.")]
            out = [Feedback(kind="slip", message=f"It's {cls.expected_result}. Let's carry on with that.")]
        else:
            out = []
        before = set(self.named_methods())
        head = self._head_text(far)
        if head:
            out.append(Feedback(kind="info", message=head))
        moved = self._apply(far)
        self.tree_entries = None
        self.last_match = "skip"
        return self._advance(moved, others or {}, r0, before, out, skipped_to=True, pos=far)

    def submit_value(self, inp):
        """A bare number while the steps are open: the answer (every step done in the head), or a quantity on some
        live route. A number that fits quantities on several routes keeps them all, each at its own position."""
        n = inp.value
        self._current = inp
        ends = lambda pool: {r: len(self.routes[r][3]) for r in pool  # the routes this number is the answer of
                             if isinstance(self.routes[r][1].get("answer"), Fraction) and n.close_to(self.routes[r][1]["answer"])}
        if self.q["outputs"] == ["answer"]:
            fin = ends(self.live) or ends(self._shadow())
            if fin:
                return self._answered(fin, n)
        if any(n.close_to(engine.num(v)) for v in self.values.values()):
            return [Feedback(kind="info", message=f"{n} is one of the numbers in the question. Write a step with it, "
                                                  "like `4 x 18 = 72`, or a number you worked out.")]
        far = self._reach(inp, self.live) or self._reach(inp, self._shadow())
        if not far:
            return [Feedback(kind="unknown", message=f"I don't see where {n} comes from here. Write the step that "
                                                     "gives it, like `4 x 18 = 72`, or type `hint`.")]
        before = set(self.named_methods())
        steps = {step_candidate("x", self.routes[r], p).expression for r, p in far.items()}
        out = []
        if len(steps) > 1:
            out.append(Feedback(kind="info", message=f"{n} fits more than one step: " + "; ".join(sorted(steps))
                                + ". Your next step will tell which."))
        else:
            head = self._head_text(far)
            if head:
                out.append(Feedback(kind="info", message=head))
        moved = self._apply(far)
        self.tree_entries = None
        self.last_match = "skip"
        r0 = min(far)
        return self._advance(moved, {}, r0, before, out, skipped_to=True, shown=str(n) if len(steps) > 1 else None,
                             pos=far)

    def _answered(self, fin, n):
        """The student gave the answer: the routes it ends finish, with the steps not written done in the head."""
        before = set(self.named_methods())
        named = {self.routes[r][0]["method"] for r in fin}
        named = (named & before) or named
        for r, end in fin.items():  # the answer itself is stated, not done in the head; owed steps were too
            self.inhead.setdefault(r, set()).update(set(range(self._at(r), end - 1)) | self.owed.get(r, frozenset()))
            self.owed[r] = frozenset()
        self.live = fin
        self.shadow = {}
        self.said.append(ValueAnswer(value=n))
        self.named = named
        self.tree_entries = None
        self.last_match = "skip"
        r0 = min(fin, key=lambda r: (self.routes[r][0]["method"] not in named, r))
        self.result = engine.outputs_of(self.qid, self.routes[r0][1])
        how = f"You used {self.names(self.named_methods())}." if self.history and len(self.named_methods()) == 1 \
            else "You did the working in your head."
        self.history.append(str(n))
        self.phase = "done"
        return [Feedback(kind="done", message=f"✓ Correct: {engine.show(self.result)}. {how}")]

    def ambiguity(self):
        """What the statements so far leave open, for a later question back to the student (PATHS.md, step 5):
        the methods still named when there are several, and each live route's steps taken as done in the head.
        {"methods": [...], "head": [{"route", "method", "steps": [expressions]}]}"""
        named = self.named_methods()
        head = [{"route": r, "method": self.routes[r][0]["method"],
                 "steps": [step_candidate("x", self.routes[r], j).expression for j in sorted(self.inhead[r])]}
                for r in self.live if self.inhead.get(r)]
        owed = [{"route": r, "method": self.routes[r][0]["method"],
                 "steps": [step_candidate("x", self.routes[r], j).expression for j in sorted(self.owed[r])]}
                for r in self.live if self.owed.get(r)]
        return {"methods": named if len(named) > 1 else [], "head": head, "owed": owed}

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
            self.owed[len(self.routes) - 1] = self.owed.get(r, frozenset())
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
        finished = [r for r in self.live if self._ended(r)]
        if not finished:
            return [Feedback(kind="info", message="There's at least one more step. Type `hint` if you're stuck.")]
        named = set(self.named_methods())  # a route kept live but not named isn't the one the student walked
        finished.sort(key=lambda r: self.routes[r][0]["method"] not in named)
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
            owed = sorted(self.owed.get(r, ()))  # a step skipped out of order comes first
            c = step_candidate("x", self.routes[r], owed[0]) if owed else self.next_step(r)
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
        self.chosen = mid
        self.named = {mid}
        self.announced = mid
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
        self.info = story(wid)
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
        self.settled_by_work = set()  # decisions a statement settled, not a pick: a same-numbers trap stays open
        self.open_traps = []  # traps a statement fitted as well as the correct reading did (12: the savings, or a step)
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
            if type(self.classifier) is RuleClassifier:  # the usual classifier: share the expansion between sessions
                if self.wid not in _probes:
                    _probes[self.wid] = self._question_on(self.run["inputs"])
                self._proto = _probes[self.wid]
            else:
                self._proto = self._question_on(self.run["inputs"])
        return self._proto.fresh()

    def _question_on(self, inputs):
        values = {k: engine.fmt(v) for k, v in inputs.items()}
        return QuestionSession(self.plan["question"], values, self.classifier, ask_final=False)

    def _start_solving(self, question=None):
        self.phase = "solve"
        self.question = question or self._probe()
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
                if not 1 <= int(m[2]) <= len(self.wp["extract"][di]["options"]):
                    return [Feedback(kind="error", message=f"Pick a number from 1 to {len(self.wp['extract'][di]['options'])}.")]
                return self.submit_input(ChoiceAnswer(index=int(m[2]), decision=di))
            n = len(self.wp["extract"][self.di]["options"])
            if re.fullmatch(r"\s*\d+\s*", text) and not 1 <= int(text) <= n:
                n = 0  # 12 isn't an option number: it's a number the student found
            try:
                inp = parse(text, choices=n)
            except ParseError as e:
                return [Feedback(kind="error", message=str(e))]
            return self.submit_input(inp)
        if self.phase == "solve":
            try:
                inp = parse(text)
            except ParseError:
                inp = None
            if inp is not None and inp.kind == "value":
                return self.submit_input(inp)
            return self._solved(self.question.submit(text), inp)
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
            if self._story_answer_fits(inp):
                return self._story_answer(inp)  # any follow-up step done in the head too (80 − 12 = 68)
            t = self._exact_trap(inp)
            if t:  # 0.8 is the trap's 4/5 exactly, and only a rounding of the correct 0.75 or 0.833
                return [Feedback(kind="trap", message=f"“{_shown(inp)}” fits this reading: {t['option']['trap']}"
                                                      f"{self._trap_tail(t)}")]
            return self._solved(self.question.submit_input(inp), inp)
        if self.phase == "then":
            return self._then(inp)
        if self.phase == "answer":
            return self._answer_input(inp, None)
        return [Feedback(kind="info", message="This one is finished.")]

    def _solved(self, out, inp=None):
        """After the question's feedback. A number that ends the question and is the story's answer too ends the
        story; a statement the question doesn't take may still be a step of a trap's reading."""
        if inp is not None and any(f.kind in ("correct", "done") for f in out):
            self._narrow(inp)
        if self.question.phase == "done":
            return out + self._after_question()
        if inp is not None and inp.kind != "value" and [f.kind for f in out] == ["unknown"]:
            k = self._after_index(inp)
            if k is not None:
                return self._skip_to_then(inp, k)
        if inp is not None and [f.kind for f in out] == ["unknown"]:
            t = next(iter(self._traps_of_answer(inp)), None) or self._trap_quantity(inp)
            if t:
                return [Feedback(kind="trap", message=f"“{_shown(inp)}” fits this reading: {t['option']['trap']}"
                                                      f"{self._trap_tail(t)}")]
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
            return self._value_first(inp)
        return self._jump(inp)

    def _trap_result(self, t):
        """What a trap's reading leads to. When it gives the same answer, say so: the answer can't catch it."""
        if t["same_as_correct"]:
            return (f"That reading happens to give the same answer, {engine.show(t['run']['final'])}, but for the wrong "
                    "reason, so the answer can't show the mistake. Try again.")
        return f"That reading gives {engine.show(t['run']['final'])}. Try again."

    def _pre(self, step):
        """A step on a settled decision's ✓ edge (90 ÷ 60 = 1.5): that step, its value, or a later step with it done
        in the head."""
        if step.kind == "choice":
            return [Feedback(kind="error", message="Write the step, like `90 / 60 = 1.5`.")]
        i = self.pre_todo[0]
        st, args, result = self.run["before"][i]
        c = Candidate(id="pre", op=st["op"], operands=list(args), result=result,
                      expression=engine.expression(st, args, result))
        if step.kind == "value":
            if isinstance(result, Fraction) and step.value.close_to(result):
                self.pre_todo.pop(0)
                self.pre_done.add(i)
                out = [Feedback(kind="correct", message=f"✓ {c.expression}  ({engine.say(st.get('say'), self.run['env'])})")]
                return out + ([self._ask_pre()] if self.pre_todo else self._next_decision())
            if self._story_answer_fits(step):
                return self._story_answer(step)
            return self._value_first(step, pre=True)
        cls = self.classifier.classify(step, [c])
        if cls.status != "match":
            return self._jump(step, pre=True)
        if cls.arithmetic_ok is False:
            return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”.")]
        self.pre_todo.pop(0)
        self.pre_done.add(i)
        out = [Feedback(kind="correct", message=f"✓ {c.expression}  ({engine.say(st.get('say'), self.run['env'])})")]
        return out + ([self._ask_pre()] if self.pre_todo else self._next_decision())

    def _pre_for(self, inp):
        """(decision, before index) when the step (or its value) is one on the ✓ edge of a decision not yet settled."""
        for di in self.open_decisions():
            for i in self._pre_steps(di):
                st, args, result = self.run["before"][i]
                if inp.kind == "value":
                    if isinstance(result, Fraction) and inp.value.close_to(result):
                        return di, i
                    continue
                c = Candidate(id="pre", op=st["op"], operands=list(args), result=result)
                if self.classifier.classify(inp, [c]).status == "match":
                    return di, i
        return None

    def _settle_pre(self, inp, pre):
        di, i = pre
        o = next(o for o in self.wp["extract"][di]["options"] if o.get("correct"))
        also = [t for t in self._also_fit(inp) if t["decision"] == di]  # a trap of this decision computes it too
        self.decided.add(di)
        self.pre_todo = [i] + [j for j in self._pre_steps(di) if j != i]
        self.di = di
        dec = self.wp["extract"][di]
        self.open_traps += [t for t in also if not any(t is u for u in self.open_traps)]
        out = [Feedback(kind="info", message=f"That {'fits' if also else 'settles it'}: {dec['say']} {o['say']}.")]
        out += self._pre(inp)
        out += [Feedback(kind="info", message=f"Careful: “{_shown(inp)}” is also in this reading: {t['option']['trap']}")
                for t in also]
        return out

    def _settle(self, what="step", probe=None, still_open=()):
        """The student's statement fits the correct reading: every open decision is settled (the steps on their ✓
        edges were done in the head), and solving starts. The decisions of the traps in `still_open`, which the
        statement fits too, aren't said to be read right; open_readings() keeps them."""
        self.open_traps = list(still_open)
        shut = {t["decision"] for t in still_open}
        rest = [self.wp["extract"][di] for di in range(len(self.wp["extract"])) if di not in self.decided | shut]
        self.settled_by_work |= set(range(len(self.wp["extract"]))) - self.decided
        self.decided = set(range(len(self.wp["extract"])))
        self.pre_todo = []
        out = [Feedback(kind="info", message=f"That {what} means you read the story right: "
                                             + "; ".join(next(o["say"] for o in d["options"] if o.get("correct")) for d in rest)
                                             + ".")] if rest else []
        return out + self._start_solving(probe)

    def _jump(self, step, pre=False):
        """The student skipped the decisions and started computing. Work out which reading their step comes from:
        a step of a decision's own (90 ÷ 60, the conversion), a step of the correct reading (the next step of one of
        its routes, or one further along with the steps before it done in the head), or a trap's. `pre`: the step
        came while a settled decision's own step was asked for."""
        found = None if pre else self._pre_for(step)
        if found:
            return self._settle_pre(step, found)
        probe = self._probe()
        trap = self._trap_for(step)
        fb = probe.submit_step(step)  # credit the reading only if the step is a step of one of its routes
        took = any(f.kind in ("correct", "slip") for f in fb) or \
            (probe.last_match == "skip" and any(f.kind == "on_track" for f in fb))  # a build-up or a later step
        if took and any(f.kind == "slip" for f in fb) and getattr(step, "result", None) is not None:
            said = ValueAnswer(value=step.result)  # 0.35 × 60 = 17.5: 17.5 is the take-them-out reading's answer
            t = next(iter(self._traps_of_answer(said)), None) or self._trap_quantity(said)
            if t:
                return self._name_trap(t, written(step))
        if took and (probe.last_match != "wildcard" or not trap):
            # a step of the correct reading that is a trap's giveaway too (2 × 2 = 4 with 24 ÷ 12 = 2 in the head)
            # is right so far, and the trap's decision stays open
            out = self._settle("step", probe, still_open=([trap] if trap else []) + self._also_fit(step, trap))
            if trap:
                fb = fb + [Feedback(kind="info", message=f"Careful: “{written(step)}” is also how this reading goes: "
                                                         f"{trap['option']['trap']}")]
            out += fb
            if self.question.phase == "done":
                out += self._after_question()
            return out
        k = self._after_index(step)
        if k is not None:  # the follow-up step (80 − 12 = 68): the question was done in the head
            t = self._slip_trap(step, self.run["after"][k][2])
            if t:  # 80 − 12 = 65: the right step, landing on the $15-off reading's answer
                return self._name_trap(t, written(step))
            return self._settle("step", probe) + self._skip_to_then(step, k)
        trap = trap or self._trap_quantity(step)
        if trap:
            return self._name_trap(trap, written(step))
        if pre:
            return [Feedback(kind="unknown", message="That's not the step I expected. Type `hint` for a nudge.")]
        return [Feedback(kind="unknown", message=f"I can't tell which reading “{written(step)}” comes from. "
                                                 "Pick an option, or type `hint`.")]

    def _also_fit(self, inp, *known):
        """The traps of open decisions whose reading the statement fits as well (50 is 150 ÷ 3 whether or not 90
        minutes is converted first): their decisions stay open."""
        ix = self.paths()
        return [t for n, t in enumerate(self.info["traps"]) if t["decision"] not in self.decided
                and not any(t is k for k in known) and self._fits_reading(inp, ix.readings[1 + n])]

    def _after_index(self, step):
        """The follow-up step of the correct reading (80 − 12 = 68) this step is, from the current one on, or None."""
        for k in range(self.then_pos, len(self.run["after"])):
            st, args, result = self.run["after"][k]
            c = Candidate(id="then", op=st["op"], operands=list(args), result=result)
            if self.classifier.classify(step, [c]).status == "match":
                return k
        return None

    def _skip_to_then(self, step, k):
        """A follow-up step written while the question is open: the question's answer was found in the head."""
        q, res = self.question, self.run["result"]
        fin = {r: len(q.routes[r][3]) for r in q.live
               if engine.same_answer(engine.outputs_of(q.qid, q.routes[r][1]), res)} or \
            {r: len(q.routes[r][3]) for r in q.live}
        q._answered(fin, Number(text=engine.fmt(res)))
        self.phase, self.then_pos = "then", k
        return [Feedback(kind="info", message=f"You found the question's answer, {engine.show(res)}, in your head.")] \
            + self._then(step)

    def _trap_tail(self, t):
        return (" It happens to give the same answer, for the wrong reason." if t["same_as_correct"] else
                f" That gives {engine.show(t['run']['final'])}.")

    def _name_trap(self, trap, shown, also=()):
        """A statement of a trap's reading: move to that trap's decision, reopening it if the student settled it.
        `also`: other traps the statement fits as well (two misreadings that both stop at 12)."""
        di = trap["decision"]
        same = self._trap_tail(trap) + "".join(f" Or this reading: {t['option']['trap']}" for t in also)
        if di in self.decided:  # a statement of a trap's reading contradicts what the student chose: reopen it
            self.decided.discard(di)
            self.di = di
            self.pre_todo = []
            chose = next(o["say"] for o in self.wp["extract"][di]["options"] if o.get("correct"))
            return [Feedback(kind="trap", message=f"“{shown}” looks like this reading: {trap['option']['trap']}"
                                                  f"{same} That doesn't fit what you chose ({chose}), so let's "
                                                  "look at that decision again.")]
        self.di = di
        return [Feedback(kind="trap", message=f"“{shown}” looks like this reading: {trap['option']['trap']}"
                                              f"{same} Let's sort out this decision first.")]

    def _trap_for(self, step):
        """The trap whose giveaway steps include this step, if any: the trap's own steps on its branch (18 + 6 = 24),
        and the first steps of its question, plots and comparisons included."""
        correct = set(self.run["firsts"])
        for t in self.info["traps"]:  # a settled decision counts too: the step then contradicts it
            keys = list(t["pre_firsts"])
            if all(isinstance(v, str) for v in t["plan"]["binds"].values()):
                keys += [k for k in t["run"]["firsts"] if k not in correct]
            for key in keys:
                c = _key_candidate(key)
                if c and self.classifier.classify(step, [c]).status == "match":
                    return t
        return None

    # ------------------------------------------------------------ statements against every reading's paths

    def paths(self):
        """Every reading of the story with its paths and quantities (paths.WordProblemIndex)."""
        return word_problem_index(self.wid, self.info)

    def _fits_quantity(self, inp, q, exact=False):
        if inp.kind == "value":
            return isinstance(q.value, Fraction) and (inp.value.value == q.value if exact else inp.value.close_to(q.value))
        if q.op is None or q.op != step_op(inp):
            return False
        c = Candidate(id="q", op=q.op, operands=list(q.operands), result=q.value)
        return self.classifier.classify(inp, [c]).status == "match"

    def _fits_reading(self, inp, reading, exact=False):
        ix = self.paths().index
        return any(self._fits_quantity(inp, ix.q[q], exact) for q in reading.quantities())

    def _trap_quantity(self, inp):
        """The trap with a quantity on its paths that this statement fits, when the correct reading has no quantity
        it fits: a step further along (108 ÷ 4 = 27) or a number (4.5)."""
        ix = self.paths()
        if self._fits_reading(inp, ix.readings[0]):
            return None
        for rd in ix.readings[1:]:
            if self._fits_reading(inp, rd):
                return self.info["traps"][rd.trap]
        return None

    def _narrow(self, inp):
        """Keep open only the traps whose reading has this statement too (50 × 1.5 = 75 uses the converted 1.5)."""
        ix = self.paths()
        keep = []
        for t in self.open_traps:
            n = next(n for n, x in enumerate(self.info["traps"]) if x is t)
            if self._fits_reading(inp, ix.readings[1 + n]):
                keep.append(t)
        self.open_traps = keep

    def _slip_trap(self, step, expected):
        """The trap whose answer a wrong result lands on (80 − 12 = 65 where 68 is right; 65 is the $15-off answer)."""
        res = getattr(step, "result", None)
        if res is None or not isinstance(expected, Fraction) or res.close_to(expected):
            return None
        return next(iter(self._traps_of_answer(ValueAnswer(value=res))), None)

    def _exact_trap(self, inp):
        """A trap whose answer is exactly this number, when the correct reading has it only as a rounding."""
        if inp.kind != "value":
            return None
        t = next((t for t in self._traps_of_answer(inp) if inp.value.value == engine.num(t["run"]["final"])), None)
        if t and not self._fits_reading(inp, self.paths().readings[0], exact=True):
            return t
        return None

    def _traps_of_answer(self, inp):
        """The traps whose wrong answer is this number (27, 16, 8, 18). A trap with the correct answer can't show."""
        if inp.kind != "value":
            return []
        return [t for t in self.info["traps"] if not t["same_as_correct"] and not isinstance(t["run"]["final"], str)
                and inp.value.close_to(t["run"]["final"])]

    def _story_answer_fits(self, inp):
        final = self.run["final"]
        return inp.kind == "value" and not isinstance(final, str) and inp.value.close_to(final)

    def open_readings(self):
        """The traps the statements so far haven't ruled out, for a later question back (PATHS.md, step 6): the
        traps of the decisions still open, and once the story is settled by the work, the traps with the correct
        reading's numbers (sugar with the 6 cups of water instead of the 6 glasses), which no number can show."""
        if self.phase == "done":  # the answer is in: only the traps with that answer, which it can't rule out
            return [t for t in self.info["traps"] if engine.same_answer(t["run"]["final"], self.run["final"]) and (
                any(t is u for u in self.open_traps)
                or (self.settled_by_work and t["decision"] in self.settled_by_work and self._same_numbers(t)))]
        by_work = self.question is not None and self.settled_by_work
        return [t for t in self.info["traps"] if t["decision"] not in self.decided or t in self.open_traps
                or (by_work and t["decision"] in self.settled_by_work and self._same_numbers(t))]

    def _same_numbers(self, t):
        """Does the trap's reading compute what the correct reading computes, number for number?"""
        ix = self.paths()
        rd = ix.readings[1 + next(n for n, x in enumerate(self.info["traps"]) if x is t)]
        return ix.labels(rd) <= ix.labels(ix.readings[0]) and engine.same_answer(t["run"]["final"], self.run["final"])

    def _value_first(self, inp, pre=False):
        """A bare number before the story's decisions are settled. In order: the story's answer (everything done in
        the head), a trap's wrong answer, a number from the story, the value of a step on an open decision's ✓ edge,
        a quantity of the correct reading (that settles the decisions), a quantity only a trap's reading has."""
        n = inp.value
        if self._story_answer_fits(inp):
            return self._story_answer(inp)
        traps = self._traps_of_answer(inp)
        given = any(n.close_to(engine.num(q["value"])) for q in self.wp["quantities"])
        correct = not given and self._fits_reading(inp, self.paths().readings[0])  # 18 restates a given
        if traps and not correct:
            return self._name_trap(traps[0], str(n), traps[1:])
        t = self._exact_trap(inp)
        if t and not given:  # 0.8: the trap's 4/5 exactly, the correct reading's 0.75 or 0.833 only rounded
            return self._name_trap(t, str(n))
        if given:
            return [Feedback(kind="info", message=f"{n} is one of the numbers in the story. Pick an option, or write "
                                                  "a step with it, like `4 x 18 = 72`.")]
        found = None if pre else self._pre_for(inp)
        if found:
            return self._settle_pre(inp, found)
        if correct:
            out = self._settle("number", still_open=traps + self._also_fit(inp, *traps))
            fb = self.question.submit_value(inp)
            if traps:  # right so far, and also where a trap's reading stops (12, before 80 − 12 = 68)
                fb.append(Feedback(kind="info", message=f"Careful: {n} is also where "
                                   + ("this reading stops: " if len(traps) == 1 else "these readings stop: ")
                                   + " ".join(t["option"]["trap"] for t in traps)))
            return self._solved(out + fb, inp)
        trap = self._trap_quantity(inp)
        if trap:
            return self._name_trap(trap, str(n))
        if pre:
            return [Feedback(kind="error", message="Write the step, like `90 / 60 = 1.5`.")]
        return [Feedback(kind="unknown", message=f"I can't tell where {n} comes from. Pick an option, or write the "
                                                 "step that gives it.")]

    def _story_answer(self, inp):
        """The student gave the story's answer: whatever is left (the decisions, the question, the follow-up steps)
        was done in the head. A trap with the same answer (sugar with the 6 cups of water) can't be ruled out by it:
        its decision isn't said to be read right, and it stays in open_readings() for a question back."""
        same = [t for t in self.info["traps"] if t["same_as_correct"]
                and (t["decision"] not in self.decided or t["decision"] in self.settled_by_work)]
        if self.phase == "extract":
            still = same + [t for t in self._also_fit(inp, *same)  # a trap with another answer is ruled out by it
                            if engine.same_answer(t["run"]["final"], self.run["final"])]
            out = self._settle("answer", still_open=still)
        else:
            out = []
        # the story's answer rules out every trap with another answer; the same-answer ones stay open
        self.open_traps = [t for t in self.open_traps + same if engine.same_answer(t["run"]["final"], self.run["final"])]
        self.open_traps = [t for i, t in enumerate(self.open_traps) if not any(t is u for u in self.open_traps[:i])]
        q = self.question
        if q.phase != "done":
            res = self.run["result"]
            fin = {r: len(q.routes[r][3]) for r in q.live
                   if engine.same_answer(engine.outputs_of(q.qid, q.routes[r][1]), res)} or \
                {r: len(q.routes[r][3]) for r in q.live}
            q._answered(fin, inp.value)
        self.then_pos = len(self.run["after"])
        self.phase = "done"
        named = q.named_methods()
        how = f". You used {q.names(named)}." if len(named) == 1 and len(q.history) > 1 else ""
        for t in same:
            out.append(Feedback(kind="info", message=f"Careful: {inp.value} is also the answer if the story is read "
                                                     f"this way: {t['option']['trap']} The answer alone can't show "
                                                     "which way you read it."))
        return out + [Feedback(kind="done", message=f"✓ {self.wp['answer_text']}{how}")]

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
        if step.kind == "value":
            if self._story_answer_fits(step):
                return self._story_answer(step)
            for k in range(self.then_pos, len(self.run["after"])):
                st, args, result = self.run["after"][k]
                if isinstance(result, Fraction) and step.value.close_to(result):
                    self.then_pos = k + 1
                    self.open_traps = []
                    if self.then_pos >= len(self.run["after"]):
                        self.phase = "answer"
                    return [Feedback(kind="correct", message=f"✓ {engine.expression(st, args, result)}")]
        if step.kind == "value" and self._traps_of_answer(step):
            t = self._traps_of_answer(step)[0]
            return [Feedback(kind="trap", message=f"“{step.value}” fits this reading: {t['option']['trap']}"
                                                  f"{self._trap_tail(t)}")]
        if step.kind in ("choice", "value"):
            return [Feedback(kind="error", message="Write the step that answers the story, or type `hint`.")]
        st, args, result = self.run["after"][self.then_pos]
        c = Candidate(id="then", op=st["op"], operands=list(args), result=result,
                      expression=engine.expression(st, args, result))
        cls = self.classifier.classify(step, [c])
        if cls.status != "match":
            return [Feedback(kind="unknown", message="That's not the step I expected. Type `hint` for a nudge.")]
        if cls.arithmetic_ok is False:
            t = self._slip_trap(step, result)
            if t:
                return [Feedback(kind="trap", message=f"“{written(step)}” fits this reading: {t['option']['trap']}"
                                                      f"{self._trap_tail(t)}")]
            return [Feedback(kind="slip", message=f"Right step, but check the arithmetic in “{written(step)}”.")]
        self.then_pos += 1
        self.open_traps = []
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
            t = next(iter(self._traps_of_answer(inp)), None) if inp else None
            if t:
                return [Feedback(kind="trap", message=f"“{inp.value}” fits this reading: {t['option']['trap']}"
                                                      f"{self._trap_tail(t)}")]
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
_stories, _probes = {}, {}  # word problem → check_word_problem's analysis; → its question on the correct numbers


def story(wid):
    """build.check_word_problem's analysis of a word problem (its plan, run and traps), worked out once. Sessions
    only read it."""
    if wid not in _stories:
        _stories[wid] = engine.check_word_problem(engine.WP[wid])[1]
    return _stories[wid]


def _shown(inp):
    return str(inp.value) if inp.kind == "value" else written(inp)


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
