"""Matching a statement anywhere on a path (tutor/PATHS.md, steps 2 and 3): the index of quantities, the statements a
student makes when she skips steps or writes only the answer, and the traps a wrong answer gives away."""

from fractions import Fraction

import pytest

import build as engine
from tutor.models import Number, ValueAnswer
from tutor.parse import parse
from tutor.paths import used_before

from tutor.session import QuestionSession, WordProblemSession, answer_options

from test_tutor import EXAMPLES, kinds, one_route_per_method, typed


def session(qid, i):
    return QuestionSession(qid, engine.Q[qid]["examples"][i]["values"])


def finish(s, qid):
    """Give the final answer when the session asks for it; True when the session is done."""
    if s.phase == "answer":
        opts = answer_options(qid)
        answer = str(opts.index(s.result) + 1) if opts and s.result in opts else engine.show(s.result)
        if s.result == "not equal":
            answer = "1"
        assert "done" in kinds(s.submit(answer)), answer
    return s.phase == "done"


# ---------------------------------------------------------------- the index

@pytest.mark.parametrize("qid, i", EXAMPLES, ids=[f"{q}:{i + 1}" for q, i in EXAMPLES])
def test_every_visible_step_of_every_route_is_in_the_index(qid, i):
    s = session(qid, i)
    ix = s.paths
    for r, route in enumerate(s.routes):
        v, env, trace, vis = route
        steps = ix.path(route)
        assert len(steps) == len(vis)
        for pos, (t, q) in enumerate(zip(vis, steps)):
            quantity = ix.index.q[q]
            assert quantity.label == engine.label_key(*trace[t]), (v["method"], pos)  # the diagrams' label
            assert quantity.role in ("working", "answer")
            assert all(p in ix.index.q for p in quantity.parents if not isinstance(p, tuple))
    assert {q.role for q in ix.index.q.values()} >= {"given"}
    if engine.Q[qid]["outputs"] == ["answer"]:
        assert {"goal", "setup", "answer"} <= {q.role for q in ix.index.q.values()}


@pytest.mark.parametrize("qid, i", EXAMPLES, ids=[f"{q}:{i + 1}" for q, i in EXAMPLES])
def test_orders_of_an_all_block_share_their_quantities(qid, i):
    """Routes that are the same steps of the same structure in another order (an `all` block's branches swapped)
    have the same quantities: no ordering adds any, and there are fewer quantities than steps written over all the
    routes."""
    s = session(qid, i)
    ix = s.paths
    by_steps = {}
    total = 0
    for route in s.routes:
        v, env, trace, vis = route
        key = (v["method"], tuple(sorted((repr(trace[t][0].get("loc")), engine.expression(*trace[t])) for t in vis)))
        by_steps.setdefault(key, []).append(set(ix.path(route)))
        total += len(vis)
    for key, sets in by_steps.items():
        assert all(x == sets[0] for x in sets), key
    made = {q for route in s.routes for q in ix.path(route)}
    assert len(made) <= total
    if len(s.routes) > len(by_steps):  # some route is another's reordering
        assert len(made) < total


def test_missing_value_routes_6_and_7_share_all_quantities():
    s = session("missing-value", 0)
    a, b = (s.routes[r] for r in (6, 7))
    assert a[0]["method"] == b[0]["method"] == "simplify_then_scale"
    assert set(s.paths.path(a)) == set(s.paths.path(b)) and s.paths.path(a) != s.paths.path(b)


@pytest.mark.parametrize("wid", list(engine.WP))
def test_every_reading_of_a_word_problem_is_in_its_index(wid):
    """The correct reading and every trap's: the steps on its branch, its question's routes (unless its numbers
    are counts written as count/1, which build.py doesn't read as methods) and its follow-up steps."""
    s = WordProblemSession(wid)
    ix = s.paths()
    assert [r.trap for r in ix.readings] == [None] + list(range(len(s.info["traps"])))
    for rd in ix.readings:
        t = None if rd.trap is None else s.info["traps"][rd.trap]
        run = t["run"] if t else s.run
        plan = t["plan"] if t else s.plan
        labels = ix.labels(rd)
        for e in used_before(plan, run) + run["after"]:  # the edge steps this reading uses
            assert engine.label_key(*e) in labels
        if not plan["answer"] and all(isinstance(v, str) for v in plan["binds"].values()):
            routes, _ = engine.routes_for(plan["question"], run["inputs"])
            for v, env, trace, vis in routes:
                assert {engine.label_key(*trace[t]) for t in vis} <= labels
        assert rd.roles[rd.answer] == "answer"
        if not isinstance(rd.final, str):
            assert ix.index.q[rd.answer].value == rd.final


# ---------------------------------------------------------------- the replays (PATHS.md, "What the student met")

def messages(fb):
    return " ".join(f.message for f in fb)


def test_replay_a_bare_answer_at_the_start_of_a_word_problem():
    s = WordProblemSession("lemonade-more-sugar")
    fb = s.submit("12")
    assert kinds(fb)[-1] == "done" and s.phase == "done", messages(fb)
    assert "Pick a number" not in messages(fb) and "read the story right" in messages(fb)


def test_replay_the_claude_reader_sends_the_answer_as_a_value():
    s = WordProblemSession("lemonade-more-sugar")
    fb = s.submit_input(ValueAnswer(value=Number(text="12")))
    assert kinds(fb)[-1] == "done" and s.phase == "done", messages(fb)


@pytest.mark.parametrize("text, head", [("4*3=12", "steps before it"), ("72/6=12", "4 × 18 = 72"),
                                        ("2/3*18=12", "4 ÷ 6 ≈ 0.667")])
def test_replay_a_last_step_at_the_start_of_a_word_problem(text, head):
    s = WordProblemSession("lemonade-more-sugar")
    fb = s.submit(text)
    assert "can't tell which reading" not in messages(fb)
    assert "read the story right" in fb[0].message and "correct" in kinds(fb), messages(fb)
    assert head in messages(fb) and "in your head" in messages(fb)
    assert s.phase == "answer" and kinds(s.submit("12")) == ["done"]


def test_replay_a_step_then_the_answer():
    s = WordProblemSession("lemonade-more-sugar")
    assert "correct" in kinds(s.submit("18/6=3"))
    fb = s.submit("12")
    assert kinds(fb)[-1] == "done" and "looks like an answer" not in messages(fb) and s.phase == "done"
    assert "Scale factor" in fb[-1].message and "water" in messages(fb)  # 12 is the water reading's answer too


def test_replay_the_last_step_of_scale_factor_is_not_inverse_rate():
    """3 × 8 = 24 for 3/5 = x/40 is the last step of Scale factor (and of the ratio table), with 40 ÷ 5 = 8 done in
    the head. The tree's `a × any whole number` wildcard for inverse rate's build-up to a power of ten fitted it, and
    the session named that method although no route of it goes that way."""
    s = session("missing-value", 0)
    fb = s.submit("3*8=24")
    assert "Inverse rate" not in messages(fb)
    assert "correct" in kinds(fb) and {"scale_factor", "ratio_table"} <= set(s.named_methods())
    assert "inverse_rate" not in s.named_methods() and s.phase == "answer"
    heads = {h["method"]: h["steps"] for h in s.ambiguity()["head"]}
    assert heads["scale_factor"] == ["40 ÷ 5 = 8"] and heads["ratio_table"] == ["5 × 8 = 40"]


def test_a_wildcard_alone_never_names_a_method():
    s = session("missing-value", 0)
    fb = s.submit("3 x 7 = 21")
    assert kinds(fb) == ["unknown"] and "starts" not in fb[0].message


@pytest.mark.parametrize("text", ["120/5=24", "24"])
def test_replay_missing_value_short_cuts(text):
    s = session("missing-value", 0)
    fb = s.submit(text)
    assert "correct" in kinds(fb) or "done" in kinds(fb), messages(fb)
    assert finish(s, "missing-value")


def test_a_bare_answer_finishes_and_leaves_the_methods_open():
    s = session("missing-value", 0)
    fb = s.submit("24")
    assert kinds(fb) == ["done"] and "in your head" in fb[0].message
    assert len(s.ambiguity()["methods"]) > 1  # the hook for asking how (PATHS.md, step 5)


def test_a_bare_working_quantity_is_a_step():
    s = session("missing-value", 0)
    fb = s.submit("120")
    assert kinds(fb)[0] == "correct" and "3 × 40 = 120" in fb[0].message and s.named_methods() == ["cross_multiply"]
    assert kinds(s.submit("120 / 5 = 24"))[0] == "correct" and s.phase == "answer"


def test_a_bare_number_on_several_routes_keeps_them_open():
    s = WordProblemSession("lemonade-more-sugar")
    fb = s.submit("3")
    assert "fits more than one step" in messages(fb) and s.phase == "solve"
    assert len(s.question.ambiguity()["methods"]) > 1
    fb = s.submit("4 x 3 = 12")
    assert "correct" in kinds(fb) and s.question.named_methods() == ["scale_factor"]


@pytest.mark.parametrize("text, kind", [("40", "info"), ("17", "unknown")])
def test_a_given_or_an_unknown_number_isnt_taken(text, kind):
    s = session("missing-value", 0)
    assert kinds(s.submit(text)) == [kind] and s.history == [] and s.phase == "steps"


def test_an_out_of_range_number_isnt_an_option_number():
    s = WordProblemSession("lemonade-more-sugar")
    n = len(s.ask()["options"])
    fb = s.submit(str(n + 5))
    assert "Pick a number" not in messages(fb)
    assert kinds(s.submit("1")) in (["correct"], ["trap"], ["correct", "info"])  # 1 is still an option number


def test_a_route_left_out_by_a_next_step_comes_back():
    """6 × 96 = 576 starts cross-multiply, so common denominator (LCM(8, 96) = 96 in the head, then 6 × 96) isn't
    live after it. When 72 × 96 = 6912 fits no live route, the routes that fit every statement come back."""
    q = session("proportion-check", 0)
    for t in ["6 x 96 = 576", "576 / 8 = 72", "72 x 96 = 6912"]:
        assert "correct" in kinds(q.submit(t)), t
    assert q.named_methods() == ["common_denominator"]
    heads = [h["steps"] for h in q.ambiguity()["head"] if h["method"] == "common_denominator"]
    assert ["LCM(8, 96) = 96"] in heads  # (another route finds the common denominator by GCF(8, 96) = 8 first)


def test_a_skipped_step_with_a_slip_is_a_slip():
    s = session("missing-value", 0)
    assert kinds(s.submit("120 / 5 = 25")) == ["slip"] and s.history == []
    assert "correct" in kinds(s.submit("120 / 5 = 24"))


def test_a_number_that_is_both_right_so_far_and_a_traps_answer():
    """12 in the jacket sale is the discount (right so far) and the savings reading's answer: the trap is named and
    its decision stays open."""
    s = WordProblemSession("jacket-sale")
    fb = s.submit("12")
    trap = next(t for t in s.info["traps"] if engine.same_answer(t["run"]["final"], 12))
    assert trap["option"]["trap"] in messages(fb) and s.phase == "then"
    assert trap in s.open_readings()
    assert kinds(s.submit("68")) == ["done"] and s.open_readings() == []


def test_a_same_numbers_trap_stays_open_after_the_work_settles_the_story():
    s = WordProblemSession("lemonade-more-sugar")
    s.submit("72/6=12")
    assert [t["option"]["say"] for t in s.open_readings()] == ["4 spoons of sugar with 6 cups of water",
                                                               "18 is the total, so subtract the sugar used"]


def test_the_story_answer_in_the_solve_phase_does_the_follow_up_in_the_head():
    s = WordProblemSession("jacket-sale")
    while s.phase == "extract":
        s.decide(s.di, next(i for i, j in enumerate(s.order[s.di], 1)
                            if s.wp["extract"][s.di]["options"][j].get("correct")))
    assert kinds(s.submit("68")) == ["done"]


def test_a_step_of_the_correct_reading_that_a_trap_starts_with_too():
    """2 × 2 = 4 is scale factor's last step (24 ÷ 12 = 2 in the head) and the first step of the reading that takes
    2 dozen as 2 pancakes: right so far, with that trap left open."""
    s = WordProblemSession("pancakes-dozen")
    fb = s.submit("2 x 2 = 4")
    trap = next(t for t in s.info["traps"] if "2 pancakes" in t["option"]["trap"])
    assert "correct" in kinds(fb) and "Careful" in messages(fb) and trap["option"]["trap"] in messages(fb)
    assert trap in s.open_readings() and s.phase == "answer"


def test_a_value_on_a_decisions_edge_settles_it():
    s = WordProblemSession("train-minutes")
    fb = s.submit("1.5")
    assert "settles it" in fb[0].message and "correct" in kinds(fb) and s.pre_step() is None


def test_a_later_step_while_the_edge_step_is_asked():
    s = WordProblemSession("train-minutes")
    di = next(di for di, d in enumerate(s.wp["extract"]) if any(o.get("correct") and o.get("steps") for o in d["options"]))
    s.decide(di, next(i for i, j in enumerate(s.order[di], 1) if s.wp["extract"][di]["options"][j].get("correct")))
    assert s.pre_step()
    fb = s.submit("50 x 1.5 = 75")
    assert "correct" in kinds(fb) and s.phase in ("answer", "done"), messages(fb)


# ---------------------------------------------------------------- traps given away by their answer

TRAPS = [(wid, n) for wid, wp in engine.WP.items() for n, t in enumerate(engine.check_word_problem(wp)[1]["traps"])
         if not t["same_as_correct"] and not isinstance(t["run"]["final"], str)]


@pytest.mark.parametrize("wid, n", TRAPS, ids=[f"{w}:{n}" for w, n in TRAPS])
def test_a_traps_answer_written_first_names_the_trap(wid, n):
    s = WordProblemSession(wid)
    t = s.info["traps"][n]
    fb = s.submit(engine.fmt(t["run"]["final"]))
    assert any(f.kind in ("trap", "info") and t["option"]["trap"] in f.message for f in fb), messages(fb)


# ---------------------------------------------------------------- the automatic students who skip

def walk_skipping(s, qid, vis, trace, skip):
    """Type every visible step but `skip` (the last one: give the answer as a number instead)."""
    for k, t in enumerate(vis):
        if k == skip:
            continue
        fb = s.submit(typed(trace[t]))
        assert any(x in kinds(fb) for x in ("correct", "done", "on_track")), (qid, skip, typed(trace[t]), messages(fb))
        if s.phase != "steps":
            break


def needed(proto, route):
    """The visible positions of a route that the next step is computed from: the steps a student can do in her head
    and still write what comes after (PATHS.md: done in the head is what the statement needs). A step the next one
    doesn't need, like one of simplify's two outputs, has to be written."""
    steps = proto.paths.path(route)
    return {j for j in range(len(steps) - 1) if steps[j] in proto.paths.index.ancestors(steps[j + 1])}


@pytest.mark.parametrize("qid, i", EXAMPLES, ids=[f"{q}:{i + 1}" for q, i in EXAMPLES])
def test_a_student_who_skips_one_step_reaches_the_answer(qid, i):
    """Each step a later step needs is skipped in turn; the last step is skipped by writing the answer as a number."""
    proto = session(qid, i)
    for r in one_route_per_method(proto):
        v, env, trace, vis = proto.routes[r]
        last = len(vis) - 1
        answer = env.get("answer")
        number = engine.Q[qid]["outputs"] == ["answer"] and isinstance(answer, Fraction)
        for skip in sorted(needed(proto, proto.routes[r]) | ({last} if number and last else set())):
            s = proto.fresh()
            walk_skipping(s, qid, vis, trace, skip)
            if skip == last and s.phase == "steps":
                assert kinds(s.submit(engine.fmt(answer))) == ["done"], (qid, v["method"])
            assert finish(s, qid), (qid, v["method"], skip, s.phase)


@pytest.mark.parametrize("qid, i", EXAMPLES, ids=[f"{q}:{i + 1}" for q, i in EXAMPLES])
def test_a_student_who_writes_only_the_answer_reaches_it(qid, i):
    """A number answer is written as the number; an answer that is a comparison or a pair of outputs is the
    route's last step (21 > 20), with every step before it done in the head."""
    s = session(qid, i)
    answer = s.routes[0][1].get("answer")
    if engine.Q[qid]["outputs"] == ["answer"] and isinstance(answer, Fraction):
        fb = s.submit(engine.fmt(answer))
        assert kinds(fb) == ["done"], messages(fb)
        return
    for r in one_route_per_method(s):
        q = s.fresh()
        v, env, trace, vis = q.routes[r]
        if len([o for o in engine.Q[qid]["outputs"]]) > 1:
            continue  # two outputs: the last step gives only one of them
        fb = q.submit(typed(trace[vis[-1]]))
        assert "correct" in kinds(fb), (v["method"], messages(fb))
        assert finish(q, qid), (v["method"], q.phase)


@pytest.mark.parametrize("wid", list(engine.WP))
def test_a_student_who_writes_only_the_story_answer_reaches_it(wid):
    s = WordProblemSession(wid)
    final = s.run["final"]
    if isinstance(final, str):  # a categorical answer: the question's last step, then the answer
        q = s._probe()
        v, env, trace, vis = q.routes[0]
        fb = s.submit(typed(trace[vis[-1]]))
        assert "correct" in kinds(fb), messages(fb)
        if s.phase == "solve":  # an equality-only route (simplify): try another method
            return
        opts = s._final_options()
        assert kinds(s.submit(str(opts.index(final) + 1))) == ["done"]
        return
    fb = s.submit(engine.fmt(final))
    assert kinds(fb)[-1] == "done" and s.phase == "done", messages(fb)


@pytest.mark.parametrize("wid", list(engine.WP))
def test_a_student_who_skips_the_decisions_and_one_step_reaches_the_story_answer(wid):
    """No decision picked: the work settles the reading. Each step of the correct route that a later step needs is
    skipped in turn. A student whose last step leaves the tutor waiting (25 × 3.5 = 87.5 is cross-multiply's first
    step, and already the answer) writes the answer."""
    proto = WordProblemSession(wid)
    q = proto._probe()
    final = proto.run["final"]
    for r in one_route_per_method(q):
        v, env, trace, vis = q.routes[r]
        for skip in sorted(needed(q, q.routes[r])):
            s = WordProblemSession(wid)
            for k, t in enumerate(vis):
                if k == skip:
                    continue
                fb = s.submit(typed(trace[t]))
                assert any(x in kinds(fb) for x in ("correct", "done", "on_track")), (wid, v["method"], skip, typed(trace[t]),
                                                                          messages(fb))
            if s.phase == "solve" and s.question.history and not isinstance(final, str):
                assert kinds(s.submit(engine.fmt(final)))[-1] == "done", (wid, v["method"], skip)
            for entry in s.run["after"]:
                if s.phase == "then":
                    assert "correct" in kinds(s.submit(typed(entry)))
            if s.phase == "answer":
                opts = s._final_options()
                answer = str(opts.index(s.run["final"]) + 1) if opts else engine.show(s.run["final"])
                assert kinds(s.submit(answer)) == ["done"]
            # an equality-only route (simplify: 3:4 ≠ 5:7) can't say which is better: the student tries another
            assert s.phase == "done" or (s.phase == "solve" and not s.question.history), (wid, v["method"], skip)


# ---------------------------------------------------------------- the first review's findings

def test_a_build_up_stays_a_build_up():
    """4 × 2 = 8 builds multiples of 4 toward 28. It is also distance from 1's 2 × 4 = 8 further along, but it isn't
    that route's answer: the build-up is what the tutor says, and the other route stays live beside it."""
    s = session("compare-fractions", 0)
    fb = s.submit("4 x 2 = 8")
    assert kinds(fb) == ["on_track"] and "in your head" not in messages(fb)
    assert "distance_from_one" not in s.named_methods()


def test_an_exact_number_beats_a_rounded_one():
    """6 ÷ 0.4 = 15 (2 ÷ 5 = 0.4 in the head) isn't 6 ÷ 0.375 with 0.4 read as a rounded 0.375."""
    s = session("compare-fractions", 1)
    assert "correct" in kinds(s.submit("3 x 2 = 6"))
    fb = s.submit("6 / 0.4 = 15")
    assert "slip" not in kinds(fb) and "6 ÷ 0.4 = 15" in messages(fb), messages(fb)


def test_the_shadow_replays_without_pruning():
    """The shadow keeps every route that fits the statements so far; proportion-check's common denominator comes
    back after two cross-multiply steps (test_a_route_left_out_by_a_next_step_comes_back), and a third statement
    still finds it."""
    q = session("proportion-check", 0)
    for t in ["6 x 96 = 576", "576 / 8 = 72", "72 x 96 = 6912", "6912 / 96 = 72", "72 = 72"]:
        assert "correct" in kinds(q.submit(t)), t
    assert q.phase == "answer"


@pytest.mark.parametrize("key, first, then", [("simplify-fraction:2", "96 / 2 = 48", "72 / 2 = 36"),
                                              ("percent-of:1", "8 x 1 = 8", "8 / 2 = 4")])
def test_only_a_step_the_statement_needs_is_done_in_the_head(key, first, then):
    """96 ÷ 2 = 48 doesn't need 72 ÷ 2 = 36: that step isn't done in the head, it is still to write, and it is
    accepted when written after."""
    qid, i = key.split(":")
    s = session(qid, int(i) - 1)
    fb = s.submit(first)
    shown = then.split(" =")[0].replace("/", "÷").replace(" x ", " × ")
    assert "correct" in kinds(fb) and not any("in your head" in f.message and shown in f.message for f in fb)
    assert any(shown in step for h in s.ambiguity()["owed"] for step in h["steps"])  # still to write
    assert "correct" in kinds(s.submit(then))


def test_a_number_a_trap_computes_too_leaves_its_decision_open():
    """50 is 150 ÷ 3 whether or not the 90 minutes are converted first."""
    s = WordProblemSession("train-minutes")
    fb = s.submit("50")
    assert "correct" in kinds(fb)
    assert "Use 90 as it is" in [t["option"]["say"] for t in s.open_readings()]
    assert "read the story right" not in messages(fb) or "Use 90" not in messages(fb)


@pytest.mark.parametrize("wid, step, answer", [("jacket-sale", "80 - 12 = 68", "68"),
                                               ("lemonade-in-all", "12 - 4 = 8", "8")])
def test_the_follow_up_step_written_first(wid, step, answer):
    s = WordProblemSession(wid)
    fb = s.submit(step)
    assert "correct" in kinds(fb) and "in your head" in messages(fb), messages(fb)
    assert kinds(s.submit(answer)) == ["done"]
    s = WordProblemSession(wid)
    while s.phase == "extract":
        s.decide(s.di, next(i for i, j in enumerate(s.order[s.di], 1)
                            if s.wp["extract"][s.di]["options"][j].get("correct")))
    assert "correct" in kinds(s.submit(step)) and s.phase == "answer"


# ---------------------------------------------------------------- statements a trap's reading makes too

TYPED_OPS = {"add", "subtract", "multiply", "divide", "gcf", "lcm"}


def shared_statements():
    """(word problem, trap index, statement) for every number and every step that the correct reading and a trap's
    reading both compute (numbers from the story left out: they are refused as givens)."""
    out = []
    for wid in engine.WP:
        s = WordProblemSession(wid)
        ix = s.paths()
        correct = ix.readings[0]
        givens = {engine.num(q["value"]) for q in s.wp["quantities"]}
        labels = ix.labels(correct)
        for n in range(len(s.info["traps"])):
            rd = ix.readings[1 + n]
            for v in sorted(set(ix.values(correct)) & set(ix.values(rd)) - givens):
                out.append((wid, n, ("value", engine.fmt(v))))
            steps = {ix.index.q[q].label: ix.index.q[q] for q in rd.quantities()
                     if ix.index.q[q].label in labels and ix.index.q[q].op in TYPED_OPS}
            for label in sorted(steps):
                q = steps[label]
                out.append((wid, n, ("step", typed(({"op": q.op}, q.operands, q.value)))))
    return out


SHARED = shared_statements()


@pytest.mark.parametrize("wid, n, statement", SHARED, ids=[f"{w}:{n}:{s[1]}" for w, n, s in SHARED])
def test_a_statement_a_trap_makes_too_never_rules_the_trap_out(wid, n, statement):
    """Written first, a number or step that a trap's reading computes as well is no proof the story was read right:
    the trap stays in open_readings() (or is named), unless the statement is the story's answer and the trap has
    another answer."""
    s = WordProblemSession(wid)
    t = s.info["traps"][n]
    kind, text = statement
    inp = ValueAnswer(value=Number(text=text)) if kind == "value" else parse(text)
    fb = s.submit_input(inp)
    final = s.run["final"]
    ruled_out = (kind == "value" and not isinstance(final, str) and Number(text=text).close_to(engine.num(final))
                 and not engine.same_answer(t["run"]["final"], final))
    kept = any(t is u for u in s.open_readings())
    assert kept or ruled_out or any(f.kind == "trap" for f in fb), messages(fb)
    if kept and t["decision"] in s.decided:  # accepted: its decision isn't claimed as read right
        right = next(o["say"] for o in s.wp["extract"][t["decision"]]["options"] if o.get("correct"))
        for f in fb:
            if "read the story right: " in f.message:
                assert right not in f.message.split("read the story right: ", 1)[1].rstrip(".").split("; ")


def test_a_bare_answer_a_same_answer_trap_gives_too():
    s = WordProblemSession("lemonade-more-sugar")
    fb = s.submit_input(ValueAnswer(value=Number(text="12")))
    assert s.phase == "done" and "4 spoons of sugar with 6 glasses" not in fb[0].message
    assert [t["option"]["say"] for t in s.open_readings()] == ["4 spoons of sugar with 6 cups of water"]
    assert any(f.message.startswith("Careful") and "water" in f.message for f in fb)


# ---------------------------------------------------------------- the third review's findings

@pytest.mark.parametrize("key", ["missing-value", "lemonade-more-sugar", "lemonade-in-all"])
@pytest.mark.parametrize("text", ["6 x 2 = 12", "2 x 6 = 12"])
def test_a_ratio_table_build_up_isnt_taken_as_an_answer(key, text):
    """6 × 2 = 12 builds 6 toward 18. It is also simplify-then-scale's last step (2 × 6 = 12), but a build-up toward
    a number of the question stays one, and the next build-up step is still taken."""
    if key in engine.WP:
        s = WordProblemSession(key)
        while s.phase == "extract":
            s.decide(s.di, next(i for i, j in enumerate(s.order[s.di], 1)
                                if s.wp["extract"][s.di]["options"][j].get("correct")))
        q = s.question
    else:
        s = q = QuestionSession("missing-value", {"a": 4, "b": 6, "d": 18})
    assert kinds(s.submit(text)) == ["on_track"]
    assert q.phase == "steps"
    assert "correct" in kinds(s.submit("6 x 3 = 18"))


def test_a_fraction_isnt_the_decimal_methods_step():
    """5/6 + 3/4 = 19/12 adds the fractions directly: no route does that (the decimal route adds 5/6 + 0.75)."""
    s = session("add-fractions", 0)
    fb = s.submit("5/6 + 3/4 = 19/12")
    assert kinds(fb) == ["unknown"] and "Convert to decimals" not in messages(fb)
    p = WordProblemSession("pizza-shared")
    fb = p.submit("5/6 + 3/4 = 8/10")
    assert "read the story right" not in messages(fb)


def test_a_slip_onto_a_traps_answer_names_the_trap():
    """0.35 × 60 = 17.5 is the right step with the take-them-out reading's answer as its result."""
    s = WordProblemSession("walk-to-school")
    fb = s.submit("0.35 x 60 = 17.5")
    assert kinds(fb) == ["trap"] and "read the story right" not in messages(fb), messages(fb)


@pytest.mark.parametrize("pick", [False, True])
def test_a_traps_exact_answer_isnt_a_rounding_of_the_right_one(pick):
    """0.8 is the add-tops-and-bottoms reading's 4/5 exactly; the correct reading has 0.75 and 0.833 only."""
    s = WordProblemSession("pizza-shared")
    if pick:
        while s.phase == "extract":
            s.decide(s.di, next(i for i, j in enumerate(s.order[s.di], 1)
                                if s.wp["extract"][s.di]["options"][j].get("correct")))
    fb = s.submit_input(ValueAnswer(value=Number(text="0.8")))
    assert kinds(fb) == ["trap"], messages(fb)


@pytest.mark.parametrize("wid, steps, gone", [
    ("lemonade-more-sugar", ["18/6=3", "4*3=12", "12"], "18 is the total, so subtract the sugar used"),
    ("train-minutes", ["150/3=50", "50*1.5=75", "75"], "Use 90 as it is"),
])
def test_the_answer_rules_out_traps_with_other_answers(wid, steps, gone):
    s = WordProblemSession(wid)
    for t in steps:
        s.submit(t)
    assert s.phase == "done"
    assert gone not in [t["option"]["say"] for t in s.open_readings()]


def test_the_work_narrows_the_open_traps():
    """50 × 1.5 = 75 uses the converted 1.5: "use 90 as it is" is ruled out before the answer."""
    s = WordProblemSession("train-minutes")
    s.submit("50")
    assert "Use 90 as it is" in [t["option"]["say"] for t in s.open_readings()]
    s.submit("50 x 1.5 = 75")
    assert "Use 90 as it is" not in [t["option"]["say"] for t in s.open_readings()]


def test_the_students_own_factor_after_a_step_she_must_write():
    """36 ÷ 12 = 3 right after 72 ÷ 2 = 36 skips 96 ÷ 2 = 48, which it doesn't need: that step is still to write, so
    the statement is refused, as on main. After 96 ÷ 2 = 48 her own factor 12 is taken."""
    s = session("simplify-fraction", 1)
    assert "correct" in kinds(s.submit("72 / 2 = 36"))
    assert kinds(s.submit("36 / 12 = 3")) == ["unknown"]
    assert "correct" in kinds(s.submit("96 / 2 = 48"))
    assert "correct" in kinds(s.submit("36 / 12 = 3"))


@pytest.mark.parametrize("text", ["0.7", "0.8"])
def test_a_tie_isnt_a_rounding(text):
    """0.75 rounds to 0.8, never to 0.7; 0.8 is right only as that rounding."""
    s = session("to-decimal", 0)
    fb = s.submit(text)
    assert ("done" in kinds(fb)) == (text == "0.8"), messages(fb)


# ---------------------------------------------------------------- the fourth review's findings

def test_a_step_out_of_order_leaves_the_skipped_step_to_write():
    """walk-to-school's route takes 5% (6 ÷ 2 = 3) before 30% (6 × 3 = 18). 6 × 3 = 18 doesn't need 6 ÷ 2 = 3: it
    is taken, 6 ÷ 2 = 3 stays to write, and the sum is taken after both. No step is refused and then credited."""
    s = WordProblemSession("walk-to-school")
    fb = []
    for t in ["60 / 10 = 6", "6 x 3 = 18", "6 / 2 = 3", "18 + 3 = 21"]:
        fb = s.submit(t)
        assert "correct" in kinds(fb), (t, messages(fb))
        assert "6 × 3 = 18" not in " ".join(f.message for f in fb if "in your head" in f.message)
    assert s.phase in ("answer", "done")


def test_a_bare_number_the_reading_has_is_taken_by_the_question_too():
    s = WordProblemSession("walk-to-school")
    fb = s.submit_input(ValueAnswer(value=Number(text="18")))
    assert "I don't see where" not in messages(fb), messages(fb)


@pytest.mark.parametrize("pre", [[], ["12"]])
def test_a_follow_up_slip_onto_a_traps_answer_names_it(pre):
    """80 − 12 = 65: the right follow-up step with the $15-off reading's answer."""
    s = WordProblemSession("jacket-sale")
    for t in pre:
        s.submit(t)
    fb = s.submit("80 - 12 = 65")
    assert kinds(fb) == ["trap"] and "read the story right" not in messages(fb), messages(fb)


@pytest.mark.parametrize("wid, phase_steps, wrong", [("jacket-sale", ["12"], "65")])
def test_a_traps_answer_in_the_follow_up_phase_is_named(wid, phase_steps, wrong):
    s = WordProblemSession(wid)
    for t in phase_steps:
        s.submit(t)
    assert s.phase == "then"
    assert kinds(s.submit(wrong)) == ["trap"]
