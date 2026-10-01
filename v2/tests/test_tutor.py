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
    assert s.live_methods() == ["cross_multiply"]
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
    assert s.phase == "solve" and s.question.live_methods() == ["cross_multiply"]


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
