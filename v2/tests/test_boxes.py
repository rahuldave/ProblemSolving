"""The choice and box inputs: specs (kernels inside components), choosing a method, and whole problems walked
through the boxes.

The walks use only the HTTP API the page uses (GET /boxes, POST /method, POST /step, POST /input). The session object
is looked at only to learn the right answers, the way a student who knows the method would fill the boxes.
"""

import copy
import json
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

import build as engine
from tutor import skills, web
from tutor.session import QuestionSession, WordProblemSession, answer_options, catalog

TYPED = web.TYPED
MAKERS = {k: m for k, _, m in catalog()}
SYM = {"add": "+", "subtract": "-", "multiply": "x", "divide": "/"}


def typed_text(entry):
    """What a student would type for a route step."""
    st, args, result = entry
    f = engine.fmt
    if st["op"] == "plot":
        return "plot " + " ".join(f"({f(x)}, {f(y)})" for x, y in args)
    if st["op"] == "compare":
        return f"{f(args[0])} {result} {f(args[1])}"
    if st["op"] in ("gcf", "lcm"):
        return f"{st['op']}({f(args[0])}, {f(args[1])}) = {f(result)}"
    return f"{f(args[0])} {SYM[st['op']]} {f(args[1])} = {f(result)}"

client = TestClient(web.app)

TEXT_FIELDS = {"say", "prompt", "idea", "best_when", "name", "options", "note", "id", "text", "labels", "role", "from",
               "with", "inputs", "component"}
VALUE_KEYS = {"operands", "result", "results", "expression", "values", "args", "answer", "value", "target", "base"}


def kinds(state):
    return [f["kind"] for f in state["feedback"]]


def start(key):
    s = client.post("/api/sessions", json={"problem": key}).json()
    return s["id"], web.SESSIONS[s["id"]]["session"]


def spec(sid):
    sp = client.get(f"/api/sessions/{sid}/boxes").json()
    assert_no_values(sp)
    return sp


def step(sid, inp):
    r = client.post(f"/api/sessions/{sid}/step", json=inp)
    assert r.status_code == 200, r.text
    return r.json()


def typed(sid, text):
    r = client.post(f"/api/sessions/{sid}/input", json={"text": text}).json()
    assert_no_values(spec(sid))
    return r


def choose(sid, method):
    r = client.post(f"/api/sessions/{sid}/method", json={"method": method})
    assert r.status_code == 200, r.text
    return r.json()


def assert_no_values(sp):
    """A spec holds shapes, ops, say texts and labels: no value keys, and no numbers outside the text fields."""
    def walk(x):
        if isinstance(x, dict):
            assert not VALUE_KEYS & set(x), x
            for k, v in x.items():
                if k not in TEXT_FIELDS:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        else:
            assert not any(ch.isdigit() for ch in json.dumps(x)), x
            assert not isinstance(x, (int, float)) or isinstance(x, bool), x
    walk(sp)


def kernels(sp):
    return [k for f in sp.get("frames", []) for k in f["kernels"]]


def frame(sp, component):
    found = [f for f in sp["frames"] if f["component"] == component]
    assert found, (component, [f["component"] for f in sp["frames"]])
    return found[0]


# ---------------------------------------------------------------- filling a kernel the way the page does

N = lambda v: {"text": engine.fmt(v)}


def fits(k, st, args):
    op = "ratio_compare" if st["op"] == "compare" and isinstance(args[0], tuple) else st["op"]
    return k["kernel"] == op and len(k["slots"]) == len(args)


def fill(k, st, args, result):
    """The StudentInput the kernel builds when the student types this step's numbers into it."""
    kind = k["kernel"]
    if kind == "plot":
        return {"kind": "plot", "points": [[N(x), N(y)] for x, y in args]}
    if kind == "compare":
        return {"kind": "compare", "left": N(args[0]), "relation": result, "right": N(args[1])}
    if kind == "ratio_compare":
        return {"kind": "ratio_compare", "left": [N(a) for a in args[0]], "relation": result, "right": [N(a) for a in args[1]]}
    if kind in ("gcf", "lcm"):
        return {"kind": "function", "name": kind, "left": N(args[0]), "right": N(args[1]), "result": N(result)}
    return {"kind": "arithmetic", "op": kind, "left": N(args[0]), "right": N(args[1]), "result": N(result)}


def kernel_for_step(sp, st, args):
    found = [k for k in kernels(sp) if fits(k, st, args)]
    assert found, (st["op"], st.get("say"), sp)
    return found[0]


def answer(sid, sp, expected, opts):
    (k,) = kernels(sp)
    assert k["kernel"] == "answer"
    if k["options"]:
        assert k["options"] == opts
        index = opts.index(expected) + 1 if expected in opts else 1  # "not equal": any choice ends it
        return step(sid, {"kind": "choice", "index": index})
    assert opts is None
    return step(sid, {"kind": "value", "value": {"text": engine.fmt(expected)}})


def pick_correct_decisions(sid, s: WordProblemSession):
    while s.phase == "extract":
        sp = spec(sid)
        if s.pre_step():  # a step on a decision's ✓ edge: a plain kernel
            assert sp["stage"] == "steps" and sp["phase"] == "extract" and sp["frames"][0]["component"] is None
            st, args, result = s.pre_step()
            assert "correct" in kinds(step(sid, fill(kernel_for_step(sp, st, args), st, args, result)))
            continue
        assert sp["stage"] == "extract" and "frames" not in sp
        dec = s.wp["extract"][s.di]
        index = next(i for i, j in enumerate(s.order[s.di], 1) if dec["options"][j].get("correct"))
        assert "correct" in kinds(step(sid, {"kind": "choice", "index": index}))


def walk_steps(sid, q: QuestionSession, r, stop=None, build_up=False):
    """Fill each spec with route r's steps (r must stay live); stop before the step where stop(st) is true."""
    v, env, trace, vis = q.routes[r]
    seen_on_track = False
    for i in vis:
        st, args, result = trace[i]
        if stop and stop(st, v):
            return st
        sp = spec(sid)
        assert sp["stage"] == "steps", sp
        k = kernel_for_step(sp, st, args)
        if build_up and st.get("search") and v["method"] == "ratio_table" and args[1] > 2:
            out = step(sid, fill(k, st, [args[0], Fraction(2)], args[0] * 2))
            assert kinds(out) == ["on_track"], out
            seen_on_track = True
        out = step(sid, fill(k, st, args, result))
        assert "correct" in kinds(out), (v["method"], engine.expression(st, args, result), out)
        assert r in q.live or q.phase != "steps"
    return seen_on_track


def walk_route(sid, q: QuestionSession, method, build_up=False):
    """Choose `method` from the method cards, then fill each spec with the steps of its first live route."""
    if len(q.live_methods()) > 1:
        sp = spec(sid)
        assert sp["stage"] == "find_method" and "frames" not in sp
        assert {m["id"] for m in sp["methods"]} == set(q.live_methods())
    choose(sid, method)
    assert q.live_methods() == [method]
    assert spec(sid)["method"]["id"] == method
    return walk_steps(sid, q, min(q.live), build_up=build_up)


# ---------------------------------------------------------------- whole problems

def one_route_per_method(qid, values):
    routes, _ = engine.routes_for(qid, {k: engine.fmt(engine.num(v)) for k, v in values.items()})
    return list(dict.fromkeys(rt[0]["method"] for rt in routes))


LEMONADE_METHODS = ["cross_multiply", "scale_factor", "unit_rate", "inverse_rate", "ratio_table", "simplify_then_scale"]


@pytest.mark.parametrize("method", LEMONADE_METHODS)
def test_lemonade_more_sugar_every_method(method):
    sid, s = start("lemonade-more-sugar")
    assert spec(sid)["phase"] == "extract"
    pick_correct_decisions(sid, s)
    sp = spec(sid)
    assert sp["stage"] == "find_method" and {m["id"] for m in sp["methods"]} == set(LEMONADE_METHODS)
    walk_route(sid, s.question, method)
    sp = spec(sid)
    assert sp["phase"] == "answer"
    assert kinds(answer(sid, sp, s.run["final"], None)) == ["done"]


MISSING = [(i, m) for i, ex in enumerate(engine.Q["missing-value"]["examples"])
           for m in one_route_per_method("missing-value", ex["values"])]


@pytest.mark.parametrize("i, method", MISSING, ids=[f"{i + 1}-{m}" for i, m in MISSING])
def test_missing_value_every_method(i, method):
    sid, q = start(f"missing-value:{i + 1}")
    walk_route(sid, q, method, build_up=True)
    sp = spec(sid)
    assert sp["phase"] == "answer"
    assert kinds(answer(sid, sp, q.result, None)) == ["done"]


EXAMPLES = [(qid, i, m) for qid, q in engine.Q.items() for i, ex in enumerate(q["examples"])
            for m in one_route_per_method(qid, ex["values"])]


@pytest.mark.parametrize("qid, i, method", EXAMPLES, ids=[f"{q}:{i + 1}-{m}" for q, i, m in EXAMPLES])
def test_every_question_method_through_boxes(qid, i, method):
    sid, q = start(f"{qid}:{i + 1}")
    walk_route(sid, q, method)
    sp = spec(sid)
    if q.phase == "answer":
        assert kinds(answer(sid, sp, q.result, answer_options(qid)))[-1] == "done"
    else:
        assert q.phase == "done" and sp["stage"] == "done" and sp["frames"] == []


@pytest.mark.parametrize("wid", list(engine.WP))
def test_every_word_problem_through_boxes(wid):
    sid, s = start(wid)
    pick_correct_decisions(sid, s)
    q = s.question
    walk_route(sid, q, q.routes[min(q.live)][0]["method"])
    for st, args, result in s.run["after"]:
        sp = spec(sid)
        assert sp["phase"] == "then" and sp["frames"][0]["component"] is None
        assert "correct" in kinds(step(sid, fill(kernel_for_step(sp, st, args), st, args, result)))
    sp = spec(sid)
    assert sp["phase"] == "answer"
    assert kinds(answer(sid, sp, s.run["final"], s._final_options())) == ["done"]


def test_method_found_from_typed_first_step_then_boxes():
    # skip the decisions by typing a first step; the session finds the method, then the boxes take over
    sid, s = start("lemonade-more-sugar")
    assert spec(sid)["stage"] == "extract"
    assert "correct" in kinds(typed(sid, "6 x 3 = 18")) and s.phase == "solve"
    sp = spec(sid)
    assert sp["stage"] == "steps" and sp["method"]["id"] == "ratio_table"
    f = frame(sp, "missing-value/ratio_table")
    assert f["done"] == [{"role": "bk", "text": "6 × 3 = 18"}]
    assert [k["role"] for k in f["kernels"]] == ["answer"]
    assert "correct" in kinds(step(sid, {"kind": "arithmetic", "op": "multiply", "left": {"text": "4"},
                                         "right": {"text": "3"}, "result": {"text": "12"}}))
    sp = spec(sid)
    assert sp["stage"] == "steps" and sp["phase"] == "answer"
    assert kinds(step(sid, {"kind": "value", "value": {"text": "12"}})) == ["done"]
    assert spec(sid)["stage"] == "done"


def test_typed_first_step_with_two_methods_left_shows_method_cards():
    sid, q = start("compare-fractions:1")  # 3 × 7 = 21 starts cross-multiply or rewriting over the other bottom
    sp = spec(sid)
    assert sp["stage"] == "find_method" and sp["allow_step"] and "first step" in sp["prompt"]
    typed(sid, "3 x 7 = 21")
    sp = spec(sid)
    assert sp["stage"] == "find_method" and {m["id"] for m in sp["methods"]} == {"cross_multiply", "match_denominator"}
    assert "next step" in sp["prompt"]  # the graph's "Which next step?"
    typed(sid, "21 / 4 = 5.25")
    sp = spec(sid)
    assert sp["stage"] == "steps" and sp["method"]["id"] == "match_denominator"


def test_a_build_up_route_is_live_but_not_named():
    sid, q = start("missing-value:1")  # 5 × 2 = 10 is unit rate's power of ten (the graph); a ratio table may
    typed(sid, "5 x 2 = 10")           # still be building toward 5 × 8 = 40, so it stays live, unnamed
    sp = spec(sid)
    assert sp["stage"] == "steps" and sp["method"]["id"] == "unit_rate"
    assert "ratio_table" in q.live_methods() and q.named_methods() == ["unit_rate"]
    assert all(f["component"] != "missing-value/ratio_table" for f in sp["frames"])
    assert kinds(typed(sid, "5 x 4 = 20")) == ["on_track"]
    sp = spec(sid)
    assert sp["method"]["id"] == "ratio_table"
    f = frame(sp, "missing-value/ratio_table")
    assert f["done"] == [{"role": "bk", "text": "5 × 4 = 20", "try": True}]  # the table shows the try


# ---------------------------------------------------------------- components: the same wherever the skill is used

def in_frame(st, v, comp_id, nested):
    _, comp, level = skills.frame_of(st, v)
    return comp is not None and comp.id == comp_id and (level > 0) == nested


def first_frame_step(qid, values, comp_id, nested):
    """(route index, step) of the earliest step in a `comp_id` frame (inside a call if `nested`), over all routes."""
    routes, _ = engine.routes_for(qid, {k: engine.fmt(engine.num(v)) for k, v in values.items()})
    best = None
    for r, (v, env, trace, vis) in enumerate(routes):
        for p, t in enumerate(vis):
            if in_frame(trace[t][0], v, comp_id, nested):
                if best is None or p < best[0]:
                    best = (p, r)
                break
    return best


def frame_at(key, comp_id, nested):
    """Start problem `key`, walk to the first step of a `comp_id` frame, and return that frame's spec."""
    qid, i = key.split(":")
    values = engine.Q[qid]["examples"][int(i) - 1]["values"]
    found = first_frame_step(qid, values, comp_id, nested)
    if not found:
        return None
    _, r = found
    sid, q = start(key)
    choose(sid, q.routes[r][0]["method"])
    walk_steps(sid, q, r, stop=lambda st, v: in_frame(st, v, comp_id, nested))
    return frame(spec(sid), comp_id)


def shape(f):
    """What must agree wherever a component is drawn: its layout and its next kernels (not the labels' words)."""
    return {"component": f["component"], "inputs": f["inputs"], "steps": f["steps"], "labels": sorted(f["labels"]),
            "kernels": sorted((k["kernel"], k.get("role"), len(k["slots"])) for k in f["kernels"])}


def standalone_key(qid, mid):
    for i, ex in enumerate(engine.Q[qid]["examples"], 1):
        if first_frame_step(qid, ex["values"], f"{qid}/{mid}", False):
            return f"{qid}:{i}"
    return None


def nested_key(comp_id):
    """The problem (question example) where the component's frame comes earliest inside a call."""
    best = None
    for qid, q in engine.Q.items():
        for i, ex in enumerate(q["examples"], 1):
            found = first_frame_step(qid, ex["values"], comp_id, True)
            if found and (best is None or found[0] < best[0]):
                best = (found[0], f"{qid}:{i}")
    return best and best[1]


@pytest.mark.parametrize("qid, mid", list(skills.COMPONENTS), ids=[c.id for c in skills.COMPONENTS.values()])
def test_component_is_the_same_where_called_and_alone(qid, mid):
    comp_id = f"{qid}/{mid}"
    alone, nested = standalone_key(qid, mid), nested_key(comp_id)
    assert nested, comp_id
    if not alone:  # compare-fractions' own examples have no whole-number ratio table
        assert engine.Q[qid]["kind"] != "skill", comp_id
        return
    a, b = frame_at(alone, comp_id, False), frame_at(nested, comp_id, True)
    assert shape(a) == shape(b), (alone, nested)
    if engine.Q[qid]["kind"] == "skill":  # alone, a skill's labels are its own input descriptions
        assert a["labels"] == engine.Q[qid]["inputs"]


def test_every_skill_method_has_a_component():
    for qid, q in engine.Q.items():
        if q["kind"] == "skill":
            for mid in q["methods"]:
                assert (qid, mid) in skills.COMPONENTS


def test_labels_come_from_the_story():
    sid, s = start("lemonade-more-sugar")
    pick_correct_decisions(sid, s)
    choose(sid, "unit_rate")
    f = frame(spec(sid), "to-decimal/divide")  # 4/6 with x = a (spoons), y = b (glasses)
    assert f["labels"] == {"x": "spoons", "y": "glasses"} and f["inputs"] == ["x", "y"]
    sid, s = start("lemonade-more-sugar")
    pick_correct_decisions(sid, s)
    choose(sid, "inverse_rate")  # 6/4: the call binds x = b, y = a
    assert frame(spec(sid), "to-decimal/divide")["labels"] == {"x": "glasses", "y": "spoons"}
    sid, q = start("missing-value:1")
    choose(sid, "ratio_table")
    f = frame(spec(sid), "missing-value/ratio_table")
    assert f["labels"] == engine.Q["missing-value"]["inputs"]


def test_roles_come_from_the_method_steps():
    # simplify-fraction/gcf: g, then the top (x1, from x) and bottom (y1, from y) in either order
    sid, q = start("simplify-fraction:1")
    choose(sid, "gcf")
    f = frame(spec(sid), "simplify-fraction/gcf")
    assert [(s["role"], s["op"], s["from"]) for s in f["steps"]] == [("g", "gcf", "x"), ("x1", "divide", "x"),
                                                                     ("y1", "divide", "y")]
    assert [k["role"] for k in f["kernels"]] == ["g"]
    step(sid, {"kind": "function", "name": "gcf", "left": {"text": "6"}, "right": {"text": "8"}, "result": {"text": "2"}})
    f = frame(spec(sid), "simplify-fraction/gcf")
    assert sorted(k["role"] for k in f["kernels"]) == ["x1", "y1"] and f["done"] == [{"role": "g", "text": "GCF(6, 8) = 2"}]
    step(sid, {"kind": "arithmetic", "op": "divide", "left": {"text": "8"}, "right": {"text": "2"}, "result": {"text": "4"}})
    assert [k["role"] for k in frame(spec(sid), "simplify-fraction/gcf")["kernels"]] == ["x1"]
    # repeated: the rounds' top and bottom divisions, found by their place in the repeat
    sid, q = start("simplify-fraction:2")  # 72/96
    choose(sid, "repeated")
    roles = []
    for _ in range(4):
        (k,) = frame(spec(sid), "simplify-fraction/repeated")["kernels"]
        roles.append(k["role"])
        r = min(q.live)
        v, env, trace, vis = q.routes[r]
        st, args, result = trace[vis[q.live[r]]]
        step(sid, fill(k, st, args, result))
    assert roles == ["x1", "y1", "x1", "y1"]
    # cross-products: both diagonals, either order, named by the inputs they multiply
    sid, q = start("cross-products:1")
    f = frame(spec(sid), "cross-products/diagonals")
    assert [(s["role"], s["from"], s["with"]) for s in f["steps"]] == [("p1", "a", "d"), ("p2", "c", "b")]
    assert sorted(k["role"] for k in f["kernels"]) == ["p1", "p2"]


def test_fraction_slots_come_from_the_operand():
    sid, s = start("lemonade-more-sugar")
    pick_correct_decisions(sid, s)
    choose(sid, "unit_rate")
    step(sid, {"kind": "arithmetic", "op": "divide", "left": {"text": "4"}, "right": {"text": "6"}, "result": {"text": "0.667"}})
    (f,) = spec(sid)["frames"]
    assert f["component"] is None and f["done"] == []  # 2/3 × 18 is missing-value's own step
    assert f["kernels"] == [{"kernel": "multiply", "slots": ["fraction", "number"], "say": "Scale up to 18"}]
    # a categorical answer is the answer kernel with options
    sid, q = start("compare-fractions:1")
    walk_route(sid, q, "cross_multiply")
    assert kernels(spec(sid)) == [{"kernel": "answer", "options": answer_options("compare-fractions")}]


# ---------------------------------------------------------------- choosing a method, ratio tables

def test_choose_method_narrows_live_routes():
    sid, s = start("lemonade-more-sugar")
    pick_correct_decisions(sid, s)
    q = s.question
    inverse = [r for r in q.live if q.routes[r][0]["method"] == "inverse_rate"]
    assert len(inverse) == 2  # 6 ÷ 4 = 1.5, or scale 4 up to 100 first
    r = choose(sid, "inverse_rate")
    assert kinds(r) == ["method"] and "Inverse rate" in r["feedback"][0]["message"]
    assert sorted(q.live) == sorted(inverse) and q.live_methods() == ["inverse_rate"]
    sp = spec(sid)
    assert "methods" not in sp and sp["method"]["id"] == "inverse_rate"
    assert [f["component"] for f in sp["frames"]] == ["to-decimal/divide", "to-decimal/power_of_ten"]
    # a step of another method is no longer accepted
    out = step(sid, {"kind": "arithmetic", "op": "multiply", "left": {"text": "4"}, "right": {"text": "18"},
                     "result": {"text": "72"}})
    assert "correct" not in kinds(out)


def test_choose_method_errors():
    sid, s = start("lemonade-more-sugar")
    assert client.post(f"/api/sessions/{sid}/method", json={"method": "scale_factor"}).status_code == 422
    pick_correct_decisions(sid, s)
    assert client.post(f"/api/sessions/{sid}/method", json={"method": "nope"}).status_code == 422
    assert client.get("/api/sessions/nope/boxes").status_code == 404


def test_ratio_table_build_up_is_on_track():
    sid, s = start("lemonade-more-sugar")
    pick_correct_decisions(sid, s)
    choose(sid, "ratio_table")
    f = frame(spec(sid), "missing-value/ratio_table")
    assert [(st["role"], st["from"], st["search"]) for st in f["steps"]] == [("bk", "b", True), ("answer", "a", False)]
    # b (6 glasses) and d (18 more glasses) share the unit, so they are named by what they count
    assert f["labels"]["a"] == "spoons" and f["labels"]["b"] == "lemonade" and f["labels"]["d"] == "extra lemonade"
    assert [k["role"] for k in f["kernels"]] == ["bk"]
    mul = lambda a, b, c: {"kind": "arithmetic", "op": "multiply", "left": {"text": a}, "right": {"text": b},
                           "result": {"text": c}}
    assert kinds(step(sid, mul("6", "2", "12"))) == ["on_track"]
    f = frame(spec(sid), "missing-value/ratio_table")
    assert [k["role"] for k in f["kernels"]] == ["bk"] and f["done"] == [{"role": "bk", "text": "6 × 2 = 12", "try": True}]
    assert "correct" in kinds(step(sid, mul("6", "3", "18")))
    f = frame(spec(sid), "missing-value/ratio_table")
    assert [k["role"] for k in f["kernels"]] == ["answer"]
    assert f["done"] == [{"role": "bk", "text": "6 × 2 = 12", "try": True}, {"role": "bk", "text": "6 × 3 = 18"}]
    assert "correct" in kinds(step(sid, mul("4", "3", "12")))


def test_session_choose_method_keeps_tree_entries_for_that_method():
    q = QuestionSession("percent-of", engine.Q["percent-of"]["examples"][0]["values"])
    q.choose_method("decimal")
    assert q.live_methods() == ["decimal"]
    assert all("decimal" in e["methods"] for e in q.tree_entries or [])
    assert "correct" in kinds_fb(q.submit("0.15 x 80 = 12"))  # 15 ÷ 100 done in the head


def kinds_fb(fb):
    return [f.kind for f in fb]


# ---------------------------------------------------------------- Type and Boxes agree on every route

def snap(obj):
    """A copy of a session's state, deep enough that going on from it leaves the original as it was."""
    new = copy.copy(obj)
    for k, v in vars(new).items():
        if isinstance(v, (dict, list, set)):
            setattr(new, k, copy.copy(v))
        elif isinstance(v, QuestionSession):
            setattr(new, k, snap(v))
    return new


def as_typed(entry):
    st, args, result = entry
    f = engine.fmt
    if st["op"] == "compare" and isinstance(args[0], tuple):
        return f"{f(args[0][0])}:{f(args[0][1])} {result} {f(args[1][0])}:{f(args[1][1])}"
    return typed_text(entry)


def qof(s):
    return s.question if isinstance(s, WordProblemSession) else s


def decided(key):
    """A session on `key` with the story read the correct way (picks and the steps on the ✓ edges)."""
    s = MAKERS[key]()
    while isinstance(s, WordProblemSession) and s.phase == "extract":
        if s.pre_step():
            assert "correct" in kinds_fb(s.submit(as_typed(s.pre_step())))
            continue
        dec = s.wp["extract"][s.di]
        s.submit(str(next(i for i, j in enumerate(s.order[s.di], 1) if dec["options"][j].get("correct"))))
    return s


def box_input(s, entry):
    """Boxes: the kernel of the current spec that fits this step, filled with its numbers."""
    st, args, result = entry
    sp = skills.spec(s)
    assert sp["stage"] == "steps", (sp["stage"], engine.expression(*entry))
    return fill(kernel_for_step(sp, st, args), st, args, result)


def finish_both(T, B, key):
    """After the steps: the follow-up steps and the answer, in both ways, ending in the same state."""
    if isinstance(T, WordProblemSession):
        for entry in T.run["after"]:
            assert "correct" in kinds_fb(T.submit(as_typed(entry)))
            assert "correct" in kinds_fb(B.submit_input(TYPED.validate_python(box_input(B, entry))))
        final, opts = T.run["final"], T._final_options()
    else:
        final, opts = T.result, answer_options(T.qid)
    assert T.phase == B.phase
    if T.phase == "answer":
        if opts:
            index = opts.index(final) + 1 if final in opts else 1
            fbT, fbB = T.submit(str(index)), B.submit_input(TYPED.validate_python({"kind": "choice", "index": index}))
        else:
            fbT = T.submit(engine.show(final))
            fbB = B.submit_input(TYPED.validate_python({"kind": "value", "value": {"text": engine.fmt(final)}}))
        assert kinds_fb(fbT) == kinds_fb(fbB) and kinds_fb(fbT)[-1] == "done", (key, fbT, fbB)
    assert T.phase == B.phase == "done"


def agree_on_every_route(key):
    """Walk every distinct route (by its steps) of the problem in the Type way (typed text) and the Boxes way (the
    method card, then each step's kernel), sharing prefixes, and check after every step that both are on the same
    routes of that method at the same positions, then that both end the same way."""
    T0 = decided(key)
    q0 = qof(T0)
    by_method = {}
    for r, (v, env, trace, vis) in enumerate(q0.routes):
        steps = tuple(trace[i] for i in vis)
        by_method.setdefault(v["method"], {}).setdefault(tuple(engine.expression(*e) for e in steps), steps)
    walked = 0
    for mid, seqs in by_method.items():
        B0 = snap(T0)
        assert kinds_fb(B0.choose_method(mid)) == ["method"]
        trie = {"kids": {}, "end": False}
        for sig, steps in seqs.items():
            node = trie
            for e, entry in zip(sig, steps):
                node = node["kids"].setdefault(e, {"entry": entry, "kids": {}, "end": False})
            node["end"] = True

        def walk(node, T, B, depth):
            nonlocal walked
            if node["end"]:  # a route ends here (it may also be the start of a longer one)
                walked += 1
                t, b = snap(T), snap(B)
                if qof(t) is not None and t.phase in ("steps", "solve"):  # the student says they're done
                    for x in (t, b):
                        x.done_command() if isinstance(x, WordProblemSession) else x.finish_steps()
                finish_both(t, b, key)
            for expr, child in node["kids"].items():
                t, b = snap(T), snap(B)
                fbT = t.submit(as_typed(child["entry"]))
                fbB = b.submit_input(TYPED.validate_python(box_input(b, child["entry"])))
                assert "correct" in kinds_fb(fbT), (key, mid, depth, expr, fbT)
                assert "correct" in kinds_fb(fbB), (key, mid, depth, expr, fbB)
                qt, qb = qof(t), qof(b)
                if any("Try another method" in f.message for f in fbT):  # equality only: the word problem's
                    assert any("Try another method" in f.message for f in fbB)  # question starts again
                    assert qt.live == qb.live and not qt.history and not qb.history and not child["kids"]
                    walked += 1
                    continue
                if qt is not None and qt.phase == "steps":
                    mine = {r: at for r, at in qt.live.items() if qt.routes[r][0]["method"] == mid}
                    assert mine == qb.live, (key, mid, depth, expr)
                    assert mid in qt.named_methods() and qb.named_methods() == [mid]
                assert t.phase == b.phase and (qt is None or qt.phase == qb.phase)
                walk(child, t, b, depth + 1)

        walk(trie, T0, B0, 0)
    assert walked == sum(len(seqs) for seqs in by_method.values())
    return walked


PROBLEMS = list(engine.WP) + [f"{qid}:{i + 1}" for qid, q in engine.Q.items() for i in range(len(q["examples"]))]


@pytest.mark.parametrize("key", PROBLEMS)
def test_type_and_boxes_agree_on_every_route(key):
    assert agree_on_every_route(key) > 0


# ---------------------------------------------------------------- the graph's other ways in, through the boxes

def test_mental_step_has_its_own_kernel():
    for key in ("percent-of:1", "jacket-sale", "walk-to-school"):
        sid, s = start(key)
        if isinstance(s, WordProblemSession):
            pick_correct_decisions(sid, s)
        choose(sid, "decimal")
        sp = spec(sid)
        mental = [f for f in sp["frames"] if f["id"] == "mental"]
        assert len(mental) == 1 and mental[0]["kernels"][0]["kernel"] == "multiply", key
        assert "in your head" in mental[0]["kernels"][0]["say"]
        q = s.question if isinstance(s, WordProblemSession) else s
        r = min(q.live)
        v, env, trace, vis = q.routes[r]
        st, args, result = trace[vis[1]]
        out = step(sid, fill(mental[0]["kernels"][0], st, args, result))
        assert kinds(out)[:2] == ["info", "correct"], (key, out)
        assert all(f["id"] != "mental" for f in spec(sid).get("frames", []))


def test_choices_list_every_open_decision_and_take_any():
    sid, s = start("lemonade-more-sugar")
    sp = spec(sid)
    assert sp["stage"] == "extract" and sp["allow_step"]
    assert [int(d["id"]) for d in sp["decisions"]] == s.open_decisions()
    later = s.open_decisions()[-1]
    d = next(d for d in sp["decisions"] if int(d["id"]) == later)
    good = next(i for i, j in enumerate(s.order[later], 1) if s.wp["extract"][later]["options"][j].get("correct"))
    assert d["options"] == s.options_of(later)
    assert kinds(step(sid, {"kind": "choice", "index": good, "decision": later})) == ["correct"]
    assert later in s.decided and str(later) not in [d["id"] for d in spec(sid)["decisions"]]
    # a giveaway typed instead of a pick: the trap's decision comes first
    r = typed(sid, "6 x 18 = 108")
    assert kinds(r) == ["trap"] and spec(sid)["decisions"][0]["id"] == str(s.di)


def test_choices_take_a_typed_step_at_the_method_stage():
    sid, s = start("lemonade-more-sugar")
    pick_correct_decisions(sid, s)
    sp = spec(sid)
    assert sp["stage"] == "find_method" and sp["allow_step"]
    typed(sid, "6 x 3 = 18")  # no card: the tree finds the method from the step
    sp = spec(sid)
    assert sp["stage"] == "steps" and sp["method"]["id"] == "ratio_table"


def test_extraction_step_on_the_correct_edge_is_a_kernel():
    sid, s = start("train-minutes")
    di = next(di for di, d in enumerate(s.wp["extract"]) if any(o.get("correct") and o.get("steps") for o in d["options"]))
    good = next(i for i, j in enumerate(s.order[di], 1) if s.wp["extract"][di]["options"][j].get("correct"))
    step(sid, {"kind": "choice", "index": good, "decision": di})
    sp = spec(sid)
    assert sp["stage"] == "steps" and sp["phase"] == "extract" and sp["prompt"] == "Convert minutes to hours"
    (k,) = kernels(sp)
    assert k["kernel"] == "divide"
    out = step(sid, {"kind": "arithmetic", "op": "divide", "left": {"text": "90"}, "right": {"text": "60"},
                     "result": {"text": "1.5"}})
    assert "correct" in kinds(out) and spec(sid)["stage"] == "extract"


def test_each_ratio_table_call_has_its_own_frame_and_numbers():
    """Two missing-value ratio-table calls in one route (pizza-shared's common denominator): the frames have
    different ids, and the second table starts with only its own steps."""
    sid, s = start("pizza-shared")
    pick_correct_decisions(sid, s)
    q = s.question
    r = next(r for r, (v, env, trace, vis) in enumerate(q.routes) if r in q.live and v["method"] == "common_denominator"
             and sum(1 for c in v["calls"] if c["question"] == "missing-value"
                     and "ratio_table" in str([t[0].get("loc") for t in trace])) >= 1
             and len({t[0]["loc"][:2] for i, t in enumerate(trace) if i in vis and any(l[1] == "ratio_table" for l in t[0]["loc"])}) >= 2)
    choose(sid, "common_denominator")
    v, env, trace, vis = q.routes[r]
    ids = set()
    for i in vis:
        st, args, result = trace[i]
        sp = spec(sid)
        for f in sp["frames"]:
            if f["component"] == "missing-value/ratio_table":
                ids.add(f["id"])
                rows = {d["role"] for d in f["done"]}
                assert len(f["done"]) <= 2 and rows <= {"bk", "answer"}, f["done"]
        assert "correct" in kinds(step(sid, fill(kernel_for_step(sp, st, args), st, args, result)))
    assert len(ids) >= 2


def test_labels_and_says_tell_the_inputs_and_fractions_apart():
    sid, s = start("free-throws")
    pick_correct_decisions(sid, s)
    choose(sid, "cross_multiply")
    f = frame(spec(sid), "cross-products/diagonals")
    assert len(set(f["labels"].values())) == 4 and "Maya's made shots" in f["labels"].values()
    sid, s = start("cereal-boxes")
    pick_correct_decisions(sid, s)
    choose(sid, "price_per_unit")
    says = [k["say"] for f in spec(sid)["frames"] for k in f["kernels"]]
    assert len(says) == len(set(says)) and any("first fraction" in x for x in says) and any("second" in x for x in says)


def test_list_multiples_has_its_own_component():
    sid, q = start("common-multiple:1")
    choose(sid, "list_multiples")
    assert kinds(step(sid, {"kind": "arithmetic", "op": "multiply", "left": {"text": "4"}, "right": {"text": "2"},
                            "result": {"text": "8"}})) == ["on_track"]
    f = frame(spec(sid), "common-multiple/list_multiples")
    assert f["done"] == [{"role": "answer", "text": "4 × 2 = 8", "try": True}]
    js = (web.STATIC / "modes" / "components.js").read_text()
    assert '"common-multiple/list_multiples": listMultiples' in js and "tables[" not in js


def test_method_cards_fill_in_or_drop_the_text():
    for key in ("percent-of:1", "percent-of:2", "jacket-sale", "proportion-check:2", "better-buy:1"):
        sid, s = start(key)
        if isinstance(s, WordProblemSession):
            pick_correct_decisions(sid, s)
        for m in spec(sid)["methods"]:
            text = m["idea"] + m.get("best_when", "")
            assert "{" not in text and "lowest terms" not in m.get("best_when", ""), (key, m)
    sid, s = start("percent-of:2")
    assert "15/100" not in json.dumps(spec(sid))  # example 2 is 35% of 60


def test_add_kernel_joins_says_case_insensitively():
    ks = []
    skills.add_kernel(ks, {"kernel": "divide", "slots": ["number", "number"], "say": "Divide the top"})
    skills.add_kernel(ks, {"kernel": "divide", "slots": ["number", "number"], "say": "divide the top"})
    assert ks == [{"kernel": "divide", "slots": ["number", "number"], "say": "Divide the top"}]


def test_bad_numbers_are_a_422_not_a_500():
    sid, q = start("missing-value:1")
    for bad in ("1/0", "1e10000000", "9" * 5000):
        r = client.post(f"/api/sessions/{sid}/step", json={"kind": "arithmetic", "op": "multiply", "left": {"text": bad},
                                                            "right": {"text": "2"}})
        assert r.status_code == 422, (bad, r.status_code)
    r = client.post(f"/api/sessions/{sid}/input", json={"text": "3 x 1/0 = 5"})
    assert r.status_code == 200 and kinds(r.json()) == ["error"]
    assert client.get("/api/sessions/" + sid + "/boxes").status_code == 200


def test_page_scripts_ignore_replies_for_another_session():
    page = (web.STATIC / "index.html").read_text()
    assert "if (sent !== sid) return null;" in page and "asker.bxToken = null;" in page
    ai_js = (web.STATIC / "modes" / "ai.js").read_text()
    assert "busy.has(sid)" in ai_js and "if (ctx.sid !== sid) return;" in ai_js
