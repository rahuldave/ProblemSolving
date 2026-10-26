"""Every quantity on every path, so a statement can be matched wherever it falls on a path (PATHS.md).

A path is one route that build.py expands (for a word problem, a route of one reading of the story, the correct one
or a trap's). A quantity is a value a path computes or reads: its name, its value, its role, the step that makes it
and its parents. Two paths that compute a quantity the same way share it: a quantity is keyed by its operation and
its parents' keys, down to the givens, so the order of an `all` block adds no new quantities.

The index is built from the same expansion as the diagrams (build.routes_for), one route at a time as the tutor needs
it, so the tutor and the diagrams agree.
"""

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

import build as engine

ROLES = ("given", "goal", "setup", "working", "answer")


@dataclass
class Quantity:
    id: int
    name: str                 # the variable the step writes, without its call prefix (k, p, answer), or the given's
    value: Any                # a Fraction; a relation for a comparison; None for a plot or the setup
    role: str                 # one of ROLES
    op: str | None = None     # the step that makes it; None for a given, the goal and the setup
    operands: list = field(default_factory=list)
    parents: tuple = ()       # the quantities the step reads (givens and constants included)
    say: str = ""
    expression: str = ""      # 4 × 18 = 72
    label: tuple = ()         # build.label_key: (op, operand texts, result text)
    made: list = field(default_factory=list)  # [(path, visible position)] where a path writes it as a step


def _short(name):
    return name.rsplit(".", 1)[-1].rsplit(":", 1)[-1]


class Index:
    """The quantities of one or more paths. `path(pid, trace, leaves)` indexes a path's trace (once per pid) and
    returns its visible steps as quantity ids, in order; `leaves` names the keys of the path's inputs."""

    def __init__(self):
        self.keys = {}        # structural key → quantity id
        self.q = {}           # quantity id → Quantity
        self.paths = {}       # path id → [quantity id of each visible step]
        self._anc = {}

    def _intern(self, key, make):
        if key not in self.keys:
            qid = len(self.keys)
            self.keys[key] = qid
            self.q[qid] = make(qid)
        return self.keys[key]

    def given(self, name, value, role="given"):
        """A given (or a constant written in a step): keyed by its name."""
        return self._intern(("given", name), lambda i: Quantity(i, name, value, role))

    def constant(self, value):
        return self._intern(("const", value), lambda i: Quantity(i, engine.fmt(value), value, "given"))

    def goal(self, names, value, prompt):
        """The unknown the question asks for, and the setup that links it to the givens."""
        g = self._intern(("goal", tuple(names)), lambda i: Quantity(i, ", ".join(names), value, "goal"))
        s = self._intern(("setup", prompt), lambda i: Quantity(i, prompt, None, "setup"))
        return g, s

    def _arg(self, a, keyof):
        if isinstance(a, list):
            return ("pair", tuple(self._arg(x, keyof) for x in a))
        if isinstance(a, (int, float)):
            return self.constant(Fraction(a))
        return keyof[a]

    def walk(self, trace, keyof, outputs=(), pid=None, env=None):
        """Index trace entries (step, args, result) in order; keyof maps a variable to its quantity id and is updated.
        Returns the visible steps' quantity ids. The quantities written to `outputs` are answers."""
        steps = []
        for st, args, result in trace:
            op = st["op"]
            if op == "init":
                for k, v in st["init"].items():
                    keyof[k] = self._arg(v, keyof)
                continue
            if op == "pick":  # the student's own common factor: a chosen number, like a given
                keyof[st["var"]] = self._intern(("pick", Fraction(result)),
                                                lambda i: Quantity(i, _short(st["var"]), Fraction(result), "working"))
                continue
            if op == "map":
                keyof[st["out"]] = keyof[st["args"][0]]
                continue
            if "search" in st:  # the multiplier a build-up searches for is chosen too
                var = st["search"]["var"]
                k = args[st["args"].index(var)]
                keyof[var] = self._intern(("chosen", k), lambda i: Quantity(i, _short(var), k, "working"))
            parents = tuple(self._arg(a, keyof) for a in st["args"])
            sig = tuple(sorted(parents, key=repr)) if op in engine.COMMUTATIVE or op == "plot" else parents
            label = engine.label_key(st, args, result)
            text = engine.expression(st, args, result) if op in engine.SYMBOL or op in ("plot", "compare", "gcf", "lcm") \
                else f"{op}({', '.join(map(engine.fmt, args))}) = {engine.fmt(result)}"  # a hidden step (floor_div)
            say = engine.say(st.get("say"), env) if env is not None else st.get("say", "")
            qid = self._intern((op, sig), lambda i: Quantity(i, _short(st.get("out", op)), result, "working", op,
                                                              list(args), parents, say, text, label))
            if "out" in st:
                keyof[st["out"]] = qid
            if "search" in st:  # the multiplier found by the build-up comes from it (5 × 8 = 40 gives 3 × 8 its 8)
                var, k = st["search"]["var"], keyof[st["search"]["var"]]
                keyof[var] = self._intern(("found", qid), lambda i: Quantity(i, _short(var), self.q[k].value, "working",
                                                                             parents=(qid,)))
            if engine.visible(st):
                if pid is not None:
                    self.q[qid].made.append((pid, len(steps)))
                steps.append(qid)
        for o in outputs:
            if o in keyof and self.q[keyof[o]].role != "given":
                self.q[keyof[o]].role = "answer"
        return steps

    def path(self, pid, route, leaves, outputs):
        """A route (variant, env, trace, visible indexes) of a question: its visible steps' quantity ids."""
        if pid not in self.paths:
            self.paths[pid] = self.walk(route[2], dict(leaves), outputs, pid, route[1])
        return self.paths[pid]

    def ancestors(self, qid):
        """Every quantity this one is computed from, through any number of steps."""
        if qid not in self._anc:
            out = set()
            for p in self.q[qid].parents:
                p = p[1] if isinstance(p, tuple) else (p,)
                for x in p:
                    out |= {x} | self.ancestors(x)
            self._anc[qid] = frozenset(out)
        return self._anc[qid]

    def by_value(self, value):
        """The quantities with this value (a student's Number, compared by its rounding rules)."""
        return [q for q in self.q.values() if isinstance(q.value, Fraction) and value.close_to(q.value)]


# ---------------------------------------------------------------- a question's paths

class QuestionIndex:
    """The paths of one question on one set of values: the session's routes, indexed as it needs them."""

    def __init__(self, qid, values, routes):
        self.qid = qid
        q = engine.Q[qid]
        self.index = Index()
        self.outputs = q["outputs"]
        self.leaves = {k: self.index.given(k, engine.num(v)) for k, v in values.items()}
        self._routes = {id(r[2]): (r[2], pid) for pid, r in enumerate(routes)}  # id(trace) → (trace, path id)
        self.goal = None

    def path(self, route):
        """The route's visible steps as quantity ids. A route re-run with the student's own choice (72 ÷ 8) is
        indexed each time, not kept: it lives only as long as one session."""
        trace = route[2]
        known = self._routes.get(id(trace))
        if known is None:
            steps = self.index.walk(trace, dict(self.leaves), self.outputs, None, route[1])
        else:
            steps = self.index.path(known[1], route, self.leaves, self.outputs)
        if self.goal is None and self.outputs == ["answer"]:
            self.goal = self.index.goal(self.outputs, route[1].get("answer"),
                                        engine.render(engine.Q[self.qid]["prompt"],
                                                      {k: self.index.q[v].value for k, v in self.leaves.items()}))
        return steps

    def head(self, route, at, p):
        """The visible positions in [at, p) of a route that its step p doesn't need: steps skipped out of order."""
        steps = self.path(route)
        need = self.index.ancestors(steps[p])
        return [j for j in range(at, p) if steps[j] not in need]


# ---------------------------------------------------------------- a word problem's readings

@dataclass
class Reading:
    name: str                 # "correct", or "trap <n>" for the n-th trap of check_word_problem
    trap: int | None          # n: the trap's index in check_word_problem's traps
    paths: list               # [[quantity id of each visible step]]
    final: Any                # the story's answer on this reading
    answer: int | None        # its quantity
    roles: dict = field(default_factory=dict)  # quantity id → role on this reading

    def quantities(self):
        return {q for p in self.paths for q in p}


class WordProblemIndex:
    """Every reading of a story, each with its paths: the steps on its decisions' edges (18 + 6 = 24), the routes of
    its question on its numbers, and its follow-up steps (12 − 4 = 8). The givens are the story's quantities, so a
    quantity two readings compute the same way is one quantity."""

    def __init__(self, wid, info):
        self.wid, wp = wid, engine.WP[wid]
        self.index = Index()
        self.story = {q["id"]: self.index.given(q["id"], engine.num(q["value"])) for q in wp["quantities"]}
        self.readings = [self._reading("correct", None, info["plan"], info["run"])]
        for n, t in enumerate(info["traps"]):
            self.readings.append(self._reading(f"trap {n}", n, t["plan"], t["run"]))

    def _reading(self, name, trap, plan, run):
        ix = self.index
        keyof = dict(self.story)
        pre = ix.walk(used_before(plan, run), keyof, env=run["env"])
        paths = [pre] if pre else []
        if plan["answer"]:
            answer = keyof[plan["answer"]]
        else:
            q = plan["question"]
            leaves = {k: keyof[v] if isinstance(v, str) else ix.constant(engine.num(v)) for k, v in plan["binds"].items()}
            answer = ix._intern(("answer", q, tuple(sorted(leaves.items()))),
                                lambda i: Quantity(i, "result", run["mapped"], "working"))
            if all(isinstance(v, str) for v in plan["binds"].values()):  # a count written as count/1 isn't a real
                routes, _ = engine.routes_for(q, run["inputs"])            # reading of the methods (build.py)
                outs = engine.Q[q]["outputs"]
                for route in routes:
                    paths.append(pre + ix.walk(route[2], dict(leaves), outs, env=route[1]))
            keyof["result"] = answer
            after = ix.walk(run["after"], keyof, env=run["env"])
            if after:
                paths = [p + after for p in paths] or [after]
                answer = after[-1]
        roles = {q: ix.q[q].role for p in paths for q in p}
        roles.update({q: "given" for q in self.story.values()})
        roles[answer] = "answer"
        return Reading(name, trap, paths, run["final"], answer, roles)

    def labels(self, reading):
        return {self.index.q[q].label for q in reading.quantities()}

    def values(self, reading):
        out = [self.index.q[q].value for q in reading.quantities()]
        return [v for v in out if isinstance(v, Fraction)]


def used_before(plan, run):
    """The steps on the decisions' edges that this reading uses. A trap's plan keeps the correct options' steps
    (90 ÷ 60 = 1.5) even when its own option binds the number they make away (use 90 as it is)."""
    need = {v for v in plan["binds"].values() if isinstance(v, str)} | {plan["answer"]} | \
        {a for st in plan["then"] for a in st["args"] if isinstance(a, str)}
    kept = []
    for entry in reversed(run["before"]):
        if entry[0]["out"] in need:
            kept.append(entry)
            need |= {a for a in entry[0]["args"] if isinstance(a, str)}
    return kept[::-1]


_wp_indexes = {}


def word_problem_index(wid, info):
    if wid not in _wp_indexes:
        _wp_indexes[wid] = WordProblemIndex(wid, info)
    return _wp_indexes[wid]
