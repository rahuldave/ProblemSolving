"""Reach real tutor states for the eval cases, the way the automatic student in tests/test_tutor.py does: pick the
correct option of each decision, then type each step of one route of a chosen method."""

import build as engine

from ..parse import parse
from ..session import QuestionSession, WordProblemSession, catalog

SYM = {"add": "+", "subtract": "-", "multiply": "x", "divide": "/"}
MAKERS = {key: make for key, _, make in catalog()}


def typed(entry):
    """What a student would type for a route step (as in tests/test_tutor.py)."""
    st, args, result = entry
    f = engine.fmt
    if st["op"] == "plot":
        return "plot " + " ".join(f"({f(x)}, {f(y)})" for x, y in args)
    if st["op"] == "compare":
        return f"{f(args[0])} {result} {f(args[1])}"
    if st["op"] in ("gcf", "lcm"):
        return f"{st['op']}({f(args[0])}, {f(args[1])}) = {f(result)}"
    return f"{f(args[0])} {SYM[st['op']]} {f(args[1])} = {f(result)}"


def _ok(fb, what):
    assert any(f.kind in ("correct", "done") for f in fb), (what, [f.message for f in fb])


def reach(problem: str, at: dict):
    """A session for `problem` in the state `at` describes:
    {}                                  the start (the first decision, or the first step)
    {"decide": n}                       after n correct picks (n may be "all")
    {"method": m, "steps": k}           after deciding everything, k steps of method m's first route ("all" = finish
                                        the route and any follow-up steps, so the final answer is next)
    """
    s = MAKERS[problem]()
    wp = isinstance(s, WordProblemSession)
    decide = at.get("decide", "all" if "method" in at else 0)
    if wp:
        n = 0
        while s.phase == "extract" and (decide == "all" or n < decide or s.pre_step()):
            if s.pre_step():  # a settled decision's own step (90 ÷ 60 = 1.5)
                _ok(s.submit(typed(s.pre_step())), "pre-step")
                continue
            dec = s.wp["extract"][s.di]
            pick = next(i for i, j in enumerate(s.order[s.di], 1) if dec["options"][j].get("correct"))
            _ok(s.submit(str(pick)), "pick")
            n += 1
    if "method" in at:
        q = s.question if wp else s
        r = next(r for r in q.live if q.routes[r][0]["method"] == at["method"])
        v, env, trace, vis = q.routes[r]
        k = len(vis) if at["steps"] == "all" else at["steps"]
        for t in vis[:k]:
            _ok(s.submit(typed(trace[t])), typed(trace[t]))
        if wp and at["steps"] == "all":
            for entry in s.run["after"]:
                _ok(s.submit(typed(entry)), typed(entry))
    return s


def expected(s, items: list[str]) -> list[tuple]:
    """The expected inputs, written compactly, as normalized keys (see run.normalize):
    "pick:<option text>"   a choice of that option, in whichever remaining decision it belongs to
    "answer:<option>"      a final-answer choice
    "value:<n>"            a final-answer number
    anything else          a step in the parser's notation, e.g. "18 / 6 = 3" or "18 / 6" (no result said)
    """
    from .run import normalize_key
    out = []
    for it in items:
        if it.startswith("pick:"):
            text = it[5:]
            hits = []
            for d, di in enumerate(_remaining(s), 1):
                opts = [s.wp["extract"][di]["options"][j]["say"] for j in s.order[di]]
                hits += [("choice", d, i) for i, o in enumerate(opts, 1) if o == text]
            assert len(hits) == 1, (it, hits)
            out.append(hits[0])
        elif it.startswith("answer:"):
            opts = s.ask()["options"] if s.phase in ("answer",) else _final_options(s)
            out.append(("choice", 1, opts.index(it[7:]) + 1))
        elif it.startswith("value:"):
            from fractions import Fraction
            out.append(("value", Fraction(it[6:])))
        else:
            out.append(normalize_key(parse(it)))
    return out


def _remaining(s):
    from ..ai import _remaining_decisions
    return _remaining_decisions(s) if isinstance(s, WordProblemSession) and s.phase == "extract" else []


def _final_options(s):
    if isinstance(s, WordProblemSession):
        return s._final_options() or []
    from ..session import answer_options
    return answer_options(s.qid) or []
