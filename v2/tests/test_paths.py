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


@pytest.mark.parametrize("text, ok", [("0.7", False), ("0.8", False), ("0.75", True)])
def test_a_decimal_that_ends_is_written_exactly(text, ok):
    """3/4 is 0.75, which ends within two places: 0.7 and 0.8 are not roundings of it."""
    s = session("to-decimal", 0)
    fb = s.submit(text)
    assert ("done" in kinds(fb)) == ok, messages(fb)


@pytest.mark.parametrize("key, text, ok", [
    ("to-decimal:2", "0.6", False), ("to-decimal:2", "0.625", True),  # to-decimal: a decimal that ends, exactly
    ("add-fractions:1", "1.58", True), ("missing-value:2", "0.67", False),
])
def test_rounded_bare_numbers(key, text, ok):
    """A rounded decimal is a rounding only when the exact decimal doesn't end within one more place. 1.58 rounds
    19/12 = 1.58333…; 0.67 is no answer of 4/6 = x/15 (10)."""
    qid, i = key.split(":")
    if int(i) > len(engine.Q[qid]["examples"]):
        pytest.skip("no such example")
    s = session(qid, int(i) - 1)
    answer = s.routes[0][1].get("answer")
    fb = s.submit(text)
    if ok:
        assert "done" in kinds(fb), (answer, messages(fb))
    else:
        assert "done" not in kinds(fb), (answer, messages(fb))


def test_a_rounded_decimal_isnt_taken_for_one_that_ends():
    """15 ÷ 100 = 0.15 ends: 0.2 isn't it, so 0.2 × 80 = 16 isn't the next step of a rounding."""
    s = session("percent-of", 0)
    assert "correct" not in kinds(s.submit("0.2"))


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


# ---------------------------------------------------------------- the fifth review's findings

def run_all(s, steps):
    for t in steps:
        fb = s.submit(t)
        assert any(k in kinds(fb) for k in ("correct", "on_track", "done")), (t, messages(fb))
    return s


@pytest.mark.parametrize("key, steps", [
    ("walk-to-school", ["60/10=6", "6x3=18", "18+3=21"]),
    ("simplify-fraction:2", ["96/2=48", "48/2=24", "24/2=12", "12/3=4", "9/3=3"]),
    ("compare-fractions:2", ["5x2=10", "2x2=4", "4/10=0.4", "8x5=40", "3x40=120", "120/8=15", "0.4x40=16", "15<16"]),
    ("compare-fractions:1", ["7/5=1.4", "lcm(4,7)=28", "28/4=7", "28/1.4=20", "3x7=21", "21>20"]),
    ("add-fractions:2", ["2/3=2/3", "3x5=15", "5/1=5", "2/3x15=10", "15/5=3", "10+3=13", "gcf(13,15)=1", "15/1=15",
                         "13/1=13"]),
])
def test_owed_steps_a_later_step_needs_dont_block_the_finish(key, steps):
    """A step skipped out of order is owed; a later step that needs it shows it was done in the head, and a route
    that ends with nothing owed finishes the steps even while a sibling expansion still owes some."""
    s = WordProblemSession(key) if key in engine.WP else session(key.split(":")[0], int(key.split(":")[1]) - 1)
    run_all(s, steps)
    q = s.question if key in engine.WP else s
    assert q.phase in ("answer", "done"), (q.phase, q.ambiguity())


def test_boxes_draw_an_owed_step():
    from tutor import skills
    s = session("simplify-fraction", 1)
    run_all(s, ["96/2=48"])
    owed = [x for h in s.ambiguity()["owed"] for x in h["steps"]]
    assert "72 ÷ 2 = 36" in owed
    spec = skills.spec(s)
    done = [d["text"] for f in spec.get("frames", []) for d in f["done"]]
    assert "72 ÷ 2 = 36" not in done
    assert any(k["kernel"] == "divide" for f in spec.get("frames", []) for k in f["kernels"])


def test_done_after_done_stays_done():
    s = session("missing-value", 0)
    s.submit("24")
    assert s.phase == "done"
    s.finish_steps()
    assert s.phase == "done"


def test_a_rounded_step_onto_a_traps_answer_is_that_trap():
    """3 ÷ 4 is 0.75, which ends within two places, so 0.8 is no rounding of it: a slip, onto the
    add-tops-and-bottoms reading's answer 4/5, which names that trap."""
    s = WordProblemSession("pizza-shared")
    assert kinds(s.submit("3 / 4 = 0.8")) == ["trap"]


@pytest.mark.parametrize("seq", [["gcf(8,3)=1", "3/1=3", "gcf(3,2)=1"]])
def test_an_owed_step_is_not_used_up_by_a_repeat_of_its_value(seq):
    """3 ÷ 1 = 3 is on the route twice: after GCF(3, 2), not written, and after GCF(8, 3), written. It is the
    second, so GCF(3, 2) stays to write and is taken."""
    s = session("compare-fractions", 1)
    run_all(s, seq)


@pytest.mark.parametrize("wid, text", [("walk-to-school", "60/100=1"), ("walk-to-school", "18+3=1"),
                                       ("pancakes-dozen", "12/2=3"), ("train-minutes", "150/3=4.5")])
def test_a_slip_onto_a_number_of_a_traps_working_is_still_a_slip(wid, text):
    """Only a slip onto a trap's answer names the trap; a wrong result that is some number on its working isn't."""
    s = WordProblemSession(wid)
    assert "trap" not in kinds(s.submit(text))


def test_a_step_done_in_the_head_can_be_written_after():
    q = WordProblemSession("walk-to-school")._probe()
    assert "correct" in kinds(q.submit("6 x 3 = 18"))
    fb = q.submit("60 / 10 = 6")
    assert "correct" in kinds(fb), messages(fb)


def topological(route, ix, rnd):
    """The route's visible steps in a random order that writes each step after the steps it needs."""
    steps = ix.path(route)
    left, out = list(range(len(steps))), []
    while left:
        ready = [j for j in left if not any(steps[k] in ix.index.ancestors(steps[j]) for k in left if k != j)]
        j = rnd.choice(ready)
        out.append(j)
        left.remove(j)
    return out


@pytest.mark.parametrize("qid, i", EXAMPLES, ids=[f"{q}:{i + 1}" for q, i in EXAMPLES])
def test_a_student_who_writes_the_steps_in_any_order_that_works_reaches_the_answer(qid, i):
    """Each route's steps in three random orders that respect what each step needs: every step is taken and the
    steps finish."""
    import random
    proto = session(qid, i)
    rnd = random.Random(f"{qid}:{i}")  # one route per method, and six more at random (any expansion of a method)
    routes = one_route_per_method(proto) + rnd.sample(range(proto.expanded), min(6, proto.expanded))
    for r in routes:
        v, env, trace, vis = proto.routes[r]
        for seed in range(3):
            s = proto.fresh()
            order = topological(proto.routes[r], proto.paths, random.Random(f"{qid}:{i}:{r}:{seed}"))
            for j in order:
                if s.phase != "steps":
                    break
                fb = s.submit(typed(trace[vis[j]]))
                assert any(k in kinds(fb) for k in ("correct", "on_track", "done")), \
                    (v["method"], [typed(trace[vis[x]]) for x in order], typed(trace[vis[j]]), messages(fb))
            assert finish(s, qid), (v["method"], [typed(trace[vis[x]]) for x in order], s.phase, s.ambiguity())


# ---------------------------------------------------------------- the seventh review's findings

@pytest.mark.parametrize("key, steps", [
    ("add-fractions:1", ["gcf(6,4)=2", "3x4=12", "6/2=3", "3/4=0.75", "0.75x12=9"]),
    ("better-buy:2", ["gcf(6,10)=2", "3x10=30", "6/2=3", "4.2/6=0.7", "0.7x30=21", "10/7.5=4/3"]),
    ("compare-fractions:1", ["gcf(4,7)=1", "4x7=28", "7x4=28", "5x4=20", "28/4=7", "3x7=21", "21>20"]),
    ("better-buy:1", ["20x3=60", "gcf(12,20)=4", "12/4=3", "3x20=60"]),
])
def test_head_steps_written_out_and_repeated_steps_keep_the_route(key, steps):
    qid, i = key.split(":")
    s = session(qid, int(i) - 1)
    for t in steps:
        fb = s.submit(t)
        assert "correct" in kinds(fb) or "done" in kinds(fb), (t, messages(fb))


# ---------------------------------------------------------------- the eighth review's findings

@pytest.mark.parametrize("key, steps", [
    ("compare-fractions:1", ["gcf(3,4)=1", "3/1=3", "4/1=4", "5/1=5", "gcf(5,7)=1", "28/4=7", "3x7=21", "28/7=4",
                             "5x4=20", "21>20"]),
    ("compare-fractions:2", ["3/8=0.375", "2x2=4", "5x2=10", "4/10=0.4", "6/0.4=15"]),
    ("better-buy:2", ["4.2x5=21", "7.5/10=0.75", "6x5=30", "gcf(6,10)=2"]),
    ("compare-fractions:2", ["8x5=40", "gcf(8,5)=1", "8/1=8", "8x5=40", "2x40=80", "80/5=16", "15<16"]),
    ("compare-fractions:1", ["5x3=15", "gcf(3,5)=1", "3/1=3", "7x3=21", "3x5=15", "4x15=60", "60/3=20", "20<21"]),
])
def test_a_head_step_written_out_keeps_the_other_readings(key, steps):
    """A step written out after it was done in the head stays a statement the shadow's routes can fit, and the
    routes where it is a later step stay beside the ones that had it in the head."""
    qid, i = key.split(":")
    s = session(qid, int(i) - 1)
    for t in steps:
        fb = s.submit(t)
        assert any(k in kinds(fb) for k in ("correct", "on_track", "done")), (t, messages(fb))


def test_a_head_step_written_out_names_the_method_it_leaves():
    s = session("better-buy", 0)
    run_all(s, ["20x3=60"])
    fb = s.submit("gcf(12,20)=4")
    assert "correct" in kinds(fb) and any(f.kind == "method" and "Common quantity" in f.message for f in fb), \
        messages(fb)


# ---------------------------------------------------------------- the ninth review's findings

def test_a_repeated_line_doesnt_switch_the_method():
    s = session("add-fractions", 0)
    run_all(s, ["5x4=20", "3x6=18", "20+18=38", "gcf(38,24)=2", "6x4=24"])
    fb = s.submit("6x4=24")
    assert "correct" not in kinds(fb) and "already" in messages(fb)
    run_all(s, ["38/2=19", "24/2=12"])
    assert "bow_tie" in s.named_methods()


def test_a_route_with_an_expression_twice_takes_it_twice():
    """add-fractions 2/3 + 1/5, a common-denominator route writes 3 × 5 = 15 twice (the LCM, then the bottom)."""
    s = session("add-fractions", 1)
    route = next(r for r in s.routes if r[0]["method"] == "common_denominator"
                 and [engine.expression(*r[2][i]) for i in r[3]][:2] == ["3 × 5 = 15", "5 × 3 = 15"])
    v, env, trace, vis = route
    for t in vis:
        fb = s.submit(typed(trace[t]))
        assert any(k in kinds(fb) for k in ("correct", "done")), (typed(trace[t]), messages(fb))
    assert finish(s, "add-fractions")


@pytest.mark.parametrize("key, steps", [
    ("better-buy:2", ["6 x 5 = 30", "10 x 3 = 30", "10 x 3 = 30", "7.5 x 3 = 22.5", "4.2 / 6 = 0.7", "0.7 x 30 = 21",
                      "21 < 22.5"]),
    ("compare-fractions:1", ["4 x 7 = 28", "7 / 5 = 1.4", "gcf(4, 7) = 1", "4 / 1 = 4", "4 x 7 = 28", "28 / 1.4 = 20",
                             "4 x 25 = 100", "3 x 25 = 75", "75 / 100 = 0.75", "0.75 x 28 = 21", "21 > 20"]),
])
def test_a_repeated_line_keeps_the_route_the_student_is_on(key, steps):
    """A repeat that a route of the same method has again may go to that route, but the routes the student is on
    stay beside it, so her next steps are still taken."""
    qid, i = key.split(":")
    s = session(qid, int(i) - 1)
    for t in steps:
        fb = s.submit(t)
        assert any(k in kinds(fb) for k in ("correct", "on_track", "done", "info")), (t, messages(fb))
        assert "unknown" not in kinds(fb), (t, messages(fb))
    assert s.phase in ("answer", "done")


def test_a_head_step_written_out_that_ends_a_route_finishes():
    s = QuestionSession("missing-value", {"a": "25", "b": "1", "d": "3.5"})
    run_all(s, ["25x3.5=87.5", "25/1=25"])
    assert s.phase in ("answer", "done")


def test_a_head_step_written_out_counts_once():
    s = session("add-fractions", 0)
    run_all(s, ["lcm(6,4)=12", "5x12=60", "3x12=36", "36/4=9", "10+9=19", "60/6=10"])
    assert "correct" not in kinds(s.submit("60/6=10"))
    assert s.history.count("60 ÷ 6 = 10") == 1


# ---------------------------------------------------------------- the PR validation's findings

@pytest.mark.parametrize("key, text", [("missing-value:1", "3*40/5=24"), ("percent-of:1", "80*15/100=12"),
                                       ("percent-of:1", "15*80/100=12")])
def test_two_steps_in_one_are_not_one_step(key, text):
    """3 × 40/5 = 24 reads left to right as 3 × 40, then ÷ 5. It isn't scale factor's 3 × 8 = 24: a fraction she
    writes stands only for a fraction. It is refused, with the two steps named, until expressions are read (step 4)."""
    qid, i = key.split(":")
    s = session(qid, int(i) - 1)
    fb = s.submit(text)
    assert kinds(fb) == ["unknown"] and "two steps" in fb[0].message and s.history == []


def test_two_steps_in_one_in_a_word_problem():
    s = WordProblemSession("lemonade-more-sugar")
    fb = s.submit("4*18/6=12")
    assert kinds(fb) == ["unknown"] and s.phase == "extract"


def test_a_leading_fraction_is_one_number():
    s = WordProblemSession("lemonade-more-sugar")
    assert "correct" in kinds(s.submit("4/6*18=12"))


def test_the_history_holds_what_she_wrote():
    """Her history has her own statements; steps done in the head are marked."""
    s = session("missing-value", 0)
    run_all(s, ["120 / 5 = 24"])
    assert s.history == ["(in your head) 3 × 40 = 120", "120 / 5 = 24"] or \
        s.history == ["(in your head) 3 × 40 = 120", "120 ÷ 5 = 24"]
    s = session("missing-value", 0)
    run_all(s, ["120"])
    assert s.history == ["120"]


@pytest.mark.parametrize("i, text", [(0, "3/4"), (1, "3/4")])
def test_simplifys_answer_as_a_fraction(i, text):
    """Simplify 6/8 (and 72/96): the answer 3/4 is the pair x1 = 3, y1 = 4."""
    s = session("simplify-fraction", i)
    fb = s.submit(text)
    assert "done" in kinds(fb) and s.phase == "done", messages(fb)


def picked(wid):
    """A word problem with every decision picked right."""
    s = WordProblemSession(wid)
    while s.phase == "extract":
        if s.pre_step():  # a step on a decision's edge (2 × 12 = 24)
            s.submit(typed(s.pre_step()))
            continue
        s.decide(s.di, next(i for i, j in enumerate(s.order[s.di], 1)
                            if s.wp["extract"][s.di]["options"][j].get("correct")))
    return s


@pytest.mark.parametrize("wid, pre, text, phase", [
    ("lemonade-more-sugar", ["4*18=72", "72/6=12"], "12-4=8", "answer"),
    ("jacket-sale", ["0.15*80=12"], "80-15=65", "then"),
    ("lemonade-more-sugar", [], "18", "solve"),
    ("lemonade-more-sugar", ["4*18=72"], "4*24=96", "solve"),
])
def test_a_trap_is_named_in_every_phase(wid, pre, text, phase):
    s = picked(wid)
    for t in pre:
        s.submit(t)
    assert s.phase == phase
    fb = s.submit(text)
    assert "trap" in kinds(fb), messages(fb)


def test_a_traps_answer_the_right_reading_has_too_gets_the_note_while_solving():
    """6 in pancakes-dozen is a quantity of the right reading and where the eggs reading stops: before the decisions
    it is taken with a note, and so it is after them."""
    s = picked("pancakes-dozen")
    fb = s.submit("6")
    assert any(f.message.startswith("Careful") for f in fb) or "trap" in kinds(fb), messages(fb)


# ---------------------------------------------------------------- PR validation, round A

@pytest.mark.parametrize("key, steps", [
    ("missing-value:1", ["3 / 5 = 0.6", "3/5 x 40 = 24"]),
    ("proportion-check:1", ["6 / 8 = 0.75", "3/4 x 96 = 72"]),
    ("add-fractions:1", ["lcm(6, 4) = 12", "3 / 4 = 0.75", "3/4 x 12 = 9"]),
    ("compare-fractions:1", ["3/4 > 5/7"]),
    ("compare-fractions:2", ["3/8 < 2/5"]),
    ("missing-value:1", ["3/5 x 40 = 24"]),
])
def test_a_fraction_written_first_is_one_number(key, steps):
    qid, i = key.split(":")
    s = session(qid, int(i) - 1)
    for t in steps:
        fb = s.submit(t)
        assert "correct" in kinds(fb) or "done" in kinds(fb), (t, messages(fb))


@pytest.mark.parametrize("text", ["24", "96"])
def test_a_traps_quantity_is_named_while_solving(text):
    s = picked("lemonade-more-sugar")
    assert "trap" in kinds(s.submit(text))


def test_the_log_reading_is_reset_for_text_that_doesnt_parse():
    s = picked("lemonade-more-sugar")
    s.submit("4 x 18 = 72")
    s.read = None
    s.submit("hello there")
    assert s.read is None


def test_a_rounded_result_that_ends_is_asked_for_exactly():
    s = session("better-buy", 0)
    fb = s.submit("4.5 / 20 = 0.23")
    assert kinds(fb) == ["slip"] and "exactly" in fb[0].message and "0.225" in fb[0].message


def test_a_slip_onto_a_traps_answer_while_solving_names_it():
    s = picked("pizza-shared")
    assert kinds(s.submit("3 / 4 = 0.8")) == ["trap"]


def test_simplify_doesnt_take_an_unsimplified_pair():
    s = session("simplify-fraction", 0)
    x, y = (s.values[k] for k in ("x", "y"))
    assert "done" not in kinds(s.submit(f"{x}/{y}"))
