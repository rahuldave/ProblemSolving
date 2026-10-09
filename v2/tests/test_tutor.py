"""Tests for the tutor prototype: parsing, classification, and whole sessions.

The 'automatic student' tests walk every method of every example (and every word problem) through the tutor by
typing each step of a route, and check that the tutor accepts every step and ends with the right answer.
"""

import pytest

import build as engine
from tutor.__main__ import run
from tutor.classifier import RuleClassifier
from tutor.models import Candidate
from tutor.parse import ParseError, parse
from tutor.session import QuestionSession, WordProblemSession, answer_options

SYM = {"add": "+", "subtract": "-", "multiply": "x", "divide": "/"}


def typed(entry):
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


def kinds(feedbacks):
    return [f.kind for f in feedbacks]


# ---------------------------------------------------------------- parsing

@pytest.mark.parametrize("text, kind, op", [
    ("4 x 18 = 72", "arithmetic", "multiply"), ("72 / 6 = 12", "arithmetic", "divide"),
    ("72/6 = 12", "arithmetic", "divide"), ("2/3 × 18 = 12", "arithmetic", "multiply"),
    ("12 - 4 = 8", "arithmetic", "subtract"), ("gcf(6, 8) = 2", "function", None), ("lcm 4 7", "function", None),
    ("21 > 20", "compare", None), ("0.75 < 5/7", "compare", None), ("plot (3, 4) (5, 7)", "plot", None),
])
def test_parse(text, kind, op):
    step = parse(text)
    assert step.kind == kind
    if op:
        assert step.op == op


def test_parse_choice_and_value():
    assert parse("2", choices=3).kind == "choice"
    assert parse("2").kind == "value"
    with pytest.raises(ParseError):
        parse("first do the thing")


def test_rounded_decimal_counts_as_exact():
    step = parse("4 / 6 = 0.667")
    from fractions import Fraction
    assert step.result.close_to(Fraction(2, 3))
    assert not parse("4 / 6 = 0.6").result.close_to(Fraction(2, 3))


# ---------------------------------------------------------------- classifier

def test_exact_match_beats_wildcard():
    from fractions import Fraction
    exact = Candidate(id="a", op="multiply", operands=[Fraction(4), Fraction(5)], methods=["cross"])
    wild = Candidate(id="b", op="multiply", operands=[Fraction(4), ("int",)], methods=["listing"])
    cls = RuleClassifier().classify(parse("5 x 4 = 20"), [wild, exact])
    assert cls.status == "match" and cls.matched == ["a"] and cls.arithmetic_ok


def test_build_up_is_on_track_only_below_target():
    from fractions import Fraction
    c = Candidate(id="t", op="multiply", operands=[Fraction(5), Fraction(8)], result=Fraction(40),
                  search={"base": Fraction(5), "target": Fraction(40)})
    assert RuleClassifier().classify(parse("5 x 2 = 10"), [c]).status == "on_track"
    assert RuleClassifier().classify(parse("5 x 9 = 45"), [c]).status == "none"


# ---------------------------------------------------------------- sessions

VALUES = {qid: q["examples"][0]["values"] for qid, q in engine.Q.items()}


def test_shared_first_step_then_second_step_decides():
    s = QuestionSession("compare-fractions", VALUES["compare-fractions"])
    fb = s.submit("3 x 7 = 21")
    assert "correct" in kinds(fb) and set(s.live_methods()) == {"cross_multiply", "match_denominator"}
    s.submit("21 / 4 = 5.25")
    assert s.live_methods() == ["match_denominator"]


def test_either_order_inside_all_block():
    s = QuestionSession("compare-fractions", VALUES["compare-fractions"])
    s.submit("5 x 4 = 20")
    assert s.named_methods() == ["cross_multiply"]
    assert "correct" in kinds(s.submit("3 x 7 = 21"))


def test_arithmetic_slip_then_retry():
    s = QuestionSession("missing-value", VALUES["missing-value"])
    assert kinds(s.submit("3 x 40 = 100")) == ["slip"]
    assert "correct" in kinds(s.submit("3 x 40 = 120"))


def test_unrecognized_step():
    s = QuestionSession("missing-value", VALUES["missing-value"])
    assert kinds(s.submit("3 + 40 = 43")) == ["unknown"]


def test_mental_conversion_in_percent():
    s = QuestionSession("percent-of", VALUES["percent-of"])
    fb = s.submit("0.15 x 80 = 12")
    assert kinds(fb)[:2] == ["info", "correct"] and s.phase == "answer"
    assert kinds(s.submit("12")) == ["done"]


def test_ratio_table_build_up_and_unit_rate_share_a_start():
    s = QuestionSession("missing-value", VALUES["missing-value"])
    s.submit("5 x 2 = 10")
    assert set(s.live_methods()) == {"ratio_table", "unit_rate"}
    assert kinds(s.submit("5 x 4 = 20")) == ["on_track"]
    s.submit("5 x 8 = 40")
    assert s.live_methods() == ["ratio_table"]


def test_word_problem_trap_by_choice():
    s = WordProblemSession("lemonade-more-sugar")
    dec = s.wp["extract"][s.di]
    trap_pos = next(i for i, j in enumerate(s.order[s.di], 1) if not dec["options"][j].get("correct"))
    assert kinds(s.submit(str(trap_pos))) == ["trap"]


def test_word_problem_trap_by_first_step():
    s = WordProblemSession("lemonade-more-sugar")
    fb = s.submit("6 x 18 = 108")
    assert kinds(fb) == ["trap"] and "Flips" in fb[0].message and s.phase == "extract"


def test_word_problem_correct_first_step_skips_decisions():
    s = WordProblemSession("lemonade-more-sugar")
    s.submit("4 x 18 = 72")
    assert s.phase == "solve" and s.question.named_methods() == ["cross_multiply"]


# ---------------------------------------------------------------- the automatic student

def one_route_per_method(session):
    seen, out = set(), []
    for r, route in enumerate(session.routes):
        if route[0]["method"] not in seen:
            seen.add(route[0]["method"])
            out.append(r)
    return out


EXAMPLES = [(qid, i) for qid, q in engine.Q.items() for i in range(len(q["examples"]))]


@pytest.mark.parametrize("qid, i", EXAMPLES, ids=[f"{q}:{i + 1}" for q, i in EXAMPLES])
def test_every_method_can_be_walked(qid, i):
    values = engine.Q[qid]["examples"][i]["values"]
    for r in one_route_per_method(QuestionSession(qid, values)):
        s = QuestionSession(qid, values)
        v, env, trace, vis = s.routes[r]
        for t in vis:
            fb = s.submit(typed(trace[t]))
            assert "correct" in kinds(fb), (v["method"], typed(trace[t]), fb)
        assert s.phase in ("answer", "done"), v["method"]
        if s.phase == "answer":
            opts = answer_options(qid)
            answer = str(opts.index(s.result) + 1) if opts and s.result in opts else engine.show(s.result)
            if s.result == "not equal":
                answer = "1"
            assert "done" in kinds(s.submit(answer)), (v["method"], answer)


@pytest.mark.parametrize("wid", list(engine.WP))
def test_every_word_problem_can_be_walked(wid):
    s = WordProblemSession(wid)
    while s.phase == "extract":
        if s.pre_step():  # a step on a decision's ✓ edge (90 ÷ 60 = 1.5)
            assert "correct" in kinds(s.submit(typed(s.pre_step())))
            continue
        dec = s.wp["extract"][s.di]
        pick = next(i for i, j in enumerate(s.order[s.di], 1) if dec["options"][j].get("correct"))
        assert "correct" in kinds(s.submit(str(pick)))
    q = s.question
    v, env, trace, vis = q.routes[next(iter(q.live))]
    for t in vis:
        assert "correct" in kinds(s.submit(typed(trace[t]))), typed(trace[t])
    for entry in s.run["after"]:
        assert "correct" in kinds(s.submit(typed(entry)))
    assert s.phase == "answer"
    opts = s._final_options()
    final = s.run["final"]
    answer = str(opts.index(final) + 1) if opts else engine.show(final)
    assert kinds(s.submit(answer)) == ["done"]


def test_cli_script_runs(capsys):
    run(QuestionSession("missing-value", VALUES["missing-value"]), ["hint", "3 x 40 = 120", "120 / 5 = 24", "24"])
    out = capsys.readouterr().out
    assert "Correct: 24" in out


# ---------------------------------------------------------------- the graph's edges, typed

def question_of(key):
    """A fresh QuestionSession for a problem key; for a word problem, on the correct reading's numbers."""
    if key in engine.WP:
        return WordProblemSession(key)._probe()
    qid, i = key.split(":")
    return QuestionSession(qid, engine.Q[qid]["examples"][int(i) - 1]["values"])


PROBLEMS = list(engine.WP) + [f"{qid}:{i + 1}" for qid, q in engine.Q.items() for i in range(len(q["examples"]))]


def graph_edges(q):
    """The "Which first step?" edges of the question's graph, grouped as question_graph groups them (first steps
    merged across methods, and a step after one done in the head), each with the "Which next step?" edges under it:
    [(steps to type, methods on the edge)]."""
    mental = {engine.key_of({"op": m["op"], "args": m["args"]}) for m in q.q.get("mental_first_steps", [])}
    groups = {}
    for v, env, trace, vis in q.routes[:q.expanded]:
        sig = engine.signatures([t[0] for t in trace], 1)[0]
        starts = [(0, ())] + ([(1, (engine.expression(*trace[vis[0]]),))] if len(vis) > 1 and engine.key_of(sig) in mental else [])
        for at, after in starts:
            g = groups.setdefault((engine.label_key(*trace[vis[at]]), after), {"entry": trace[vis[at]], "methods": set(), "next": {}})
            g["methods"].add(v["method"])
            if len(vis) > at + 1:
                n = g["next"].setdefault(engine.label_key(*trace[vis[at + 1]]), {"entry": trace[vis[at + 1]], "methods": set()})
                n["methods"].add(v["method"])
    out = []
    for g in groups.values():
        out.append(([g["entry"]], g["methods"]))
        if len(g["methods"]) > 1:
            out += [([g["entry"], n["entry"]], n["methods"]) for n in g["next"].values()]
    return out


@pytest.mark.parametrize("key", PROBLEMS)
def test_every_first_and_next_step_edge_names_the_graphs_methods(key):
    """Typed into a fresh session, each first-step edge (and each "Which next step?" edge under a shared first step)
    names exactly the methods on the graph's edge: no method dropped by an exact match beating a wildcard, none
    added from a route that is only building up."""
    proto = question_of(key)
    for steps, methods in graph_edges(proto):
        q = proto.fresh()
        for entry in steps:
            fb = q.submit(typed(entry))
            assert "correct" in kinds(fb), (key, typed(entry), [f.message for f in fb])
        named = set(q.named_methods())
        drawn = named & {q.routes[r][0]["method"] for r in q.live if r < q.expanded}
        assert drawn == methods, (key, [typed(e) for e in steps], q.named_methods(), methods)
        # beyond the drawn routes, only a route re-run with the student's own common factor (72 ÷ 6 starts
        # dividing out factors, as the tree's common_factor wildcard says) may be named
        assert named - drawn <= {q.routes[r][0]["method"] for r in q.live if r >= q.expanded}


@pytest.mark.parametrize("key, steps, named", [
    ("train-minutes", ["150 / 3 = 50"], {"simplify_then_scale", "unit_rate"}),
    ("train-minutes", ["150 / 3 = 50", "3 / 3 = 1"], {"simplify_then_scale"}),
    ("add-fractions:2", ["5 x 2 = 10"], {"bow_tie", "decimal"}),
    ("add-fractions:2", ["5 x 2 = 10", "1 x 2 = 2"], {"decimal"}),
    ("add-fractions:2", ["3 x 5 = 15", "2 x 5 = 10"], {"bow_tie", "common_denominator"}),
    ("common-multiple:2", ["4 x 7 = 28"], {"list_multiples", "product"}),
])
def test_a_shared_first_step_keeps_every_method_the_graph_draws(key, steps, named):
    q = question_of(key)
    if key in engine.WP:
        q = q.fresh()
    for t in steps:
        assert "correct" in kinds(q.submit(t)), t
    assert set(q.named_methods()) == named


@pytest.mark.parametrize("key, steps", [
    ("simplify-fraction:2", ["72 / 8 = 9", "96 / 8 = 12", "9 / 3 = 3", "12 / 3 = 4"]),
    ("simplify-fraction:2", ["72 / 4 = 18", "96 / 4 = 24", "18 / 2 = 9", "24 / 2 = 12", "9 / 3 = 3", "12 / 3 = 4"]),
    ("simplify-fraction:2", ["72 / 24 = 3", "96 / 24 = 4"]),
    ("to-decimal:1", ["4 x 250 = 1000", "3 x 250 = 750", "750 / 1000 = 0.75"]),
    ("proportion-check:1", ["72 / 8 = 9", "96 / 8 = 12"]),
])
def test_any_common_factor_and_any_power_of_ten(key, steps):
    """The tree says any common factor (and the method's idea says any shared factor), and the step says 10, 100
    or 1000: the session re-runs the route with the student's own choice."""
    q = question_of(key)
    for t in steps:
        fb = q.submit(t)
        assert "correct" in kinds(fb), (t, [f.message for f in fb])
    if key != "proportion-check:1":
        assert q.phase in ("answer", "done")
    assert kinds(question_of("simplify-fraction:2").submit("72 / 5 = 14.4")) == ["unknown"]  # not a factor


def test_mental_step_is_shown_once_and_only_where_declared():
    q = question_of("percent-of:1")
    fb = q.submit("0.15 x 80 = 12")
    assert kinds(fb)[:2] == ["info", "correct"] and "15 ÷ 100 = 0.15 in your head" in fb[0].message


# ---------------------------------------------------------------- word problems: the extract frame

def correct_index(s, di):
    return next(i for i, j in enumerate(s.order[di], 1) if s.wp["extract"][di]["options"][j].get("correct"))


@pytest.mark.parametrize("wid, text, step_say", [("train-minutes", "90 / 60 = 1.5", "Convert minutes to hours"),
                                                  ("pancakes-dozen", "2 x 12 = 24", "A dozen is 12")])
def test_a_step_on_a_correct_edge_typed_during_extraction(wid, text, step_say):
    s = WordProblemSession(wid)
    fb = s.submit(text)
    assert kinds(fb) == ["info", "correct"] and step_say in fb[1].message, [f.message for f in fb]
    assert s.phase == "extract" and s.question is None  # read as the conversion, not as a solving step
    assert s.pre_step() is None


@pytest.mark.parametrize("wid", ["train-minutes", "pancakes-dozen"])
def test_a_correct_pick_asks_for_the_step_on_its_edge(wid):
    s = WordProblemSession(wid)
    di = next(di for di, d in enumerate(s.wp["extract"])
              if any(o.get("correct") and o.get("steps") for o in d["options"]))
    fb = s.decide(di, correct_index(s, di))
    assert kinds(fb) == ["correct", "info"] and s.pre_step()
    st, args, result = s.pre_step()
    assert s.ask()["text"] == engine.say(st["say"], s.run["env"])
    assert kinds(s.submit("1 + 1 = 2")) == ["unknown"]
    assert "correct" in kinds(s.submit(typed(s.pre_step())))
    assert s.pre_step() is None and di in s.decided


@pytest.mark.parametrize("wid, text, concept", [
    ("lemonade-more-sugar", "18 + 6 = 24", "delta_vs_total"), ("jacket-sale", "80 - 15 = 65", "question_type"),
    ("walk-to-school", "60 - 10 = 50", "distractor"), ("pizza-shared", "5 + 3 = 8", "question_type"),
    ("sweeter-lemonade", "plot (6, 4) (14, 10)", "direction"), ("free-throws", "plot (1, 4) (2, 7)", "direction"),
])
def test_trap_branch_steps_and_plots_give_the_trap_away(wid, text, concept):
    s = WordProblemSession(wid)
    fb = s.submit(text)
    assert kinds(fb) == ["trap"] and s.phase == "extract", [f.message for f in fb]
    assert s.wp["extract"][s.di]["concept"] == concept


def test_trap_steps_are_in_the_graph_label():
    traps = {t["option"]["say"]: t for t in WordProblemSession("lemonade-more-sugar").info["traps"]}
    assert any("6 + 18 = 24" in t["tells"] for t in traps.values())
    assert "80 − 15 = 65" in next(t for t in WordProblemSession("jacket-sale").info["traps"] if t["decision"] == 0)["tells"]


@pytest.mark.parametrize("wid", ["lemonade-more-sugar", "sweeter-lemonade"])
def test_a_same_answer_trap_says_the_answer_is_the_same(wid):
    s = WordProblemSession(wid)
    t = next(t for t in s.info["traps"] if t["same_as_correct"])
    idx = next(i for i, j in enumerate(s.order[t["decision"]], 1) if s.wp["extract"][t["decision"]]["options"][j] is t["option"])
    fb = s.decide(t["decision"], idx)
    assert kinds(fb) == ["trap"]
    assert "happens to give the same answer" in fb[0].message and "That reading gives" not in fb[0].message
    assert "gives the same answer" in s.hint()[0].message  # the hint warns too (caught_by_answer: false)


@pytest.mark.parametrize("wid", ["free-throws", "sweeter-lemonade"])
def test_an_equality_only_route_doesnt_name_a_winner(wid):
    s = WordProblemSession(wid)
    while s.phase == "extract":
        s.decide(s.di, correct_index(s, s.di))
    q = s.question
    r = next(r for r in q.live if q.routes[r][0]["method"] == "simplify")
    v, env, trace, vis = q.routes[r]
    fb = []
    for t in vis:
        fb = s.submit(typed(trace[t]))
        assert "correct" in kinds(fb)
    text = " ".join(f.message for f in fb)
    assert "aren't equal" in text and "The question's answer is" not in text
    assert s.phase == "solve" and s.question.history == []  # try another method
    r = next(r for r in s.question.live if s.question.routes[r][0]["method"] == "cross_multiply")
    v, env, trace, vis = s.question.routes[r]
    for t in vis:
        fb = s.submit(typed(trace[t]))
    assert f"The question's answer is {s.run['result']}." in [f.message for f in fb]


def test_decisions_in_any_order():
    s = WordProblemSession("lemonade-more-sugar")
    first, later = s.open_decisions()[:2]
    assert [d["decision"] for d in s.ask()["decisions"]] == s.open_decisions()
    assert kinds(s.decide(later, correct_index(s, later))) == ["correct"]
    assert later in s.decided and s.di == first
    letter = s.ask()["decisions"][1]["letter"]  # typed: b2 is option 2 of the second listed decision
    nxt = s.ask()["decisions"][1]["decision"]
    assert "correct" in kinds(s.submit(f"{letter}{correct_index(s, nxt)}")) and nxt in s.decided
    assert kinds(s.decide(later, 1)) == ["error"]  # settled already
    while s.phase == "extract":
        assert "correct" in kinds(s.decide(s.di, correct_index(s, s.di)))
    assert s.phase == "solve"


def test_web_stage_is_done_at_the_end():
    from tutor.web import stage
    q = question_of("percent-of:1")
    q.submit("0.15 x 80 = 12")
    q.submit("12")
    assert q.phase == "done" and stage(q) == "done"


# ---------------------------------------------------------------- typed numbers are bounded

@pytest.mark.parametrize("text", ["1e10000000", "1/0", "3/0.0", "1" * 31, "0x10", "inf", "nan"])
def test_number_rejects_what_the_parser_never_writes(text):
    from pydantic import ValidationError
    from tutor.models import Number
    with pytest.raises(ValidationError):
        Number(text=text)


def test_number_caches_its_value_and_places():
    from fractions import Fraction
    from tutor.models import Number
    n = Number(text="0.667")
    assert n.value is n.value and n.places == 3 and Number(text="2/3").places is None
    assert Number(text="2/3").value == Fraction(2, 3)


# ---------------------------------------------------------------- second review

@pytest.mark.parametrize("text, value", [("3/0.5", 6), (".5/.25", 2), ("2/3", "2/3"), ("5.", 5), ("-1.5", "-3/2")])
def test_decimal_denominators_have_their_value(text, value):
    from fractions import Fraction
    from tutor.models import Number, number_value
    assert Number(text=text).value == Fraction(value) == number_value(text)


def test_unicode_digits_are_not_numbers():
    from pydantic import ValidationError
    from tutor.models import Number
    with pytest.raises(ValidationError):
        Number(text="٣")


def test_a_trap_step_after_settling_its_decision_reopens_it():
    s = WordProblemSession("lemonade-more-sugar")
    corr = next(di for di, d in enumerate(s.wp["extract"]) if d["concept"] == "correspondence")
    s.decide(corr, correct_index(s, corr))
    assert corr in s.decided
    fb = s.submit("6 x 18 = 108")  # a tell of the flipped-ratio trap: contradicts the pick
    assert kinds(fb) == ["trap"] and "doesn't fit what you chose" in fb[0].message
    assert corr not in s.decided and s.di == corr and s.phase == "extract"


def test_a_trap_pick_isnt_credited_by_a_later_step():
    s = WordProblemSession("lemonade-more-sugar")
    trap = next(i for i, j in enumerate(s.order[s.di], 1) if not s.wp["extract"][s.di]["options"][j].get("correct"))
    first = s.di
    assert kinds(s.submit(str(trap))) == ["trap"]
    assert kinds(s.submit("6 x 18 = 108")) == ["trap"]
    assert first not in s.decided and s.phase == "extract"


@pytest.mark.parametrize("text", ["6 x 7 = 42", "4 x 7 = 28"])
def test_a_wildcard_only_step_doesnt_credit_the_reading(text):
    s = WordProblemSession("lemonade-more-sugar")
    before = set(s.decided)
    fb = s.submit(text)
    assert kinds(fb) == ["unknown"] and "can't tell which reading" in fb[0].message
    assert s.decided == before and s.phase == "extract"


def test_letter_zero_is_an_error():
    s = WordProblemSession("lemonade-more-sugar")
    letter = s.ask()["decisions"][0]["letter"]
    before = set(s.decided)
    assert kinds(s.submit(f"{letter}0")) == ["error"] and s.decided == before


def test_power_of_ten_rerun_only_10_100_1000():
    q = question_of("to-decimal:1")
    assert "correct" not in kinds(q.submit("4 x 2500 = 10000"))
    with pytest.raises(engine.NotApplicable):
        v = next(v for v in engine.variants_of("to-decimal") if v["method"] == "power_of_ten")
        k = next(st["search"]["var"] for st in v["steps"] if "search" in st)
        engine.run(v["steps"], {"x": 3, "y": 4}, {k: [engine.num(2500)]})
    assert "correct" in kinds(question_of("to-decimal:1").submit("4 x 250 = 1000"))


def test_method_isnt_announced_while_another_is_building_up():
    q = question_of("compare-fractions:1")
    fb = q.submit("5 x 4 = 20")  # cross-multiply, while other methods may still be building up toward 4 × k
    assert set(q.live_methods()) - {"cross_multiply"}
    msgs = [f.message for f in fb if f.kind == "method"]
    assert msgs and msgs[0].startswith("That's Cross-multiply so far") and "You're using" not in msgs[0]
    fb = q.submit("3 x 7 = 21")
    assert q.live_methods() == ["cross_multiply"]
    assert [f.message for f in fb if f.kind == "method"] == ["You're using: Cross-multiply."]
