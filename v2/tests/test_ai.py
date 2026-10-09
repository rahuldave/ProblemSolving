"""Talk it through, offline: a fake client returns canned structured outputs, so nothing here touches the network."""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from tutor import ai
from tutor.evals import run as evalrun
from tutor.evals.states import expected, reach
from tutor.models import ChoiceAnswer
from tutor.parse import parse
from tutor.session import QuestionSession, WordProblemSession
from tutor.web import app


class FakeMessages:
    def __init__(self, outputs, stop_reason="end_turn", error=None, fallback=False):
        self.outputs, self.stop_reason, self.error, self.fallback = list(outputs), stop_reason, error, fallback
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        out = self.outputs.pop(0)
        content = [SimpleNamespace(type="thinking", thinking="")]
        if self.fallback:
            content += [SimpleNamespace(type="text", text='{"inputs": [{"kind": "val'), SimpleNamespace(type="fallback")]
        content.append(SimpleNamespace(type="text", text=json.dumps(out)))
        usage = SimpleNamespace(input_tokens=300, output_tokens=40, cache_creation_input_tokens=0,
                                cache_read_input_tokens=3600)
        return SimpleNamespace(content=content, stop_reason=self.stop_reason, usage=usage)


def fake(*outputs, **kw):
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(outputs, **kw)))


def step(op, left, right, result=None):
    return {"kind": "arithmetic", "op": op, "left": left, "right": right, "result": result}


def kinds(fb):
    return [f.kind for f in fb]


# ---------------------------------------------------------------- the context for each phase

def test_context_extraction_lists_story_and_decisions_in_shown_order():
    s = WordProblemSession("lemonade-more-sugar")
    ctx = ai.context(s)
    assert s.wp["text"] in ctx and "6 cups of water; 4 spoons of sugar" in ctx
    dec = s.wp["extract"][s.di]
    shown = [dec["options"][j]["say"] for j in s.order[s.di]]
    assert f"Decision 1 (being asked now): {dec['say']}" in ctx
    assert all(f"[{i}] {o}" in ctx for i, o in enumerate(shown, 1))
    assert "Decision 2 (also open)" in ctx  # the other decisions are listed too: any order
    assert "in any order" in ctx and "start calculating" in ctx


def test_context_solve_binds_question_letters_steps_and_methods():
    s = reach("lemonade-more-sugar", {"method": "cross_multiply", "steps": 1})
    ctx = ai.context(s)
    assert "Solve 4/6 = x/18." in ctx and "a: 4 spoons of sugar" in ctx and "x is the unknown" in ctx
    assert "Steps so far: 4 × 18 = 72" in ctx and "Methods still possible: Cross-multiply and divide" in ctx
    assert "for a number" in ctx


def test_context_question_answer_phase_lists_options():
    s = reach("compare-fractions:1", {"method": "cross_multiply", "steps": "all"})
    assert s.phase == "answer"
    ctx = ai.context(s)
    assert "Phase: final answer" in ctx and "[1] first" in ctx and "[3] equal" in ctx


def test_context_word_problem_answer_and_then_phases():
    s = reach("lemonade-in-all", {"method": "scale_factor", "steps": 2})
    assert s.phase == "then" and "one more step" in ai.context(s)
    s = reach("free-throws", {"method": "cross_multiply", "steps": "all"})
    ctx = ai.context(s)
    assert "Phase: final answer" in ctx and "[1] Maya" in ctx and "who has the better shooting rate" in ctx.lower()


def test_request_shape():
    req = ai.request(QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40}), "3 x 40 = 120")
    assert req["model"] == "claude-opus-5-5" and req["fallbacks"] == "default"
    assert req["betas"] == ["server-side-fallback-2026-07-01"]
    assert req["output_config"]["effort"] == "low" and req["output_config"]["format"]["type"] == "json_schema"
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"} and req["system"][0]["text"] == ai.SYSTEM
    assert "thinking" not in req
    assert "<message>\n3 x 40 = 120\n</message>" in req["messages"][0]["content"]


# ---------------------------------------------------------------- reading and feeding

def test_inputs_are_fed_in_order():
    s = WordProblemSession("lemonade-more-sugar")
    c = fake({"inputs": [{"kind": "choice", "decision": 3, "index": 2}, step("divide", "18", "6", "3")], "note": ""})
    r = ai.say(s, "18 is just the extra, so 6 goes into 18 three times", c)
    assert r["interpreted"] == ["18 is the extra glasses", "18 ÷ 6 = 3"]
    # the choice answers a later decision at once (any order); the step fills the rest in and starts solving
    assert r["checked"] == [True, True] and s.phase == "solve" and s.question.history == ["18 ÷ 6 = 3"]
    c = fake({"inputs": [step("multiply", "4", "3", "12"), {"kind": "value", "value": "12"}], "note": ""})
    r = ai.say(s, "4 times 3 is 12 so he needs 12", c)
    assert r["checked"] == [True, True] and s.phase == "done" and kinds(r["feedback"])[-1] == "done"


def test_two_decisions_in_one_message():
    s = WordProblemSession("lemonade-more-sugar")
    first = s.di
    c = fake({"inputs": [{"kind": "choice", "decision": 1, "index": 2}, {"kind": "choice", "decision": 2, "index": 2}],
              "note": ""})
    r = ai.say(s, "sugar with glasses, and sugar over glasses on both sides", c)
    assert r["checked"] == [True, True] and kinds(r["feedback"]) == ["correct", "correct"]
    assert first in s.decided and len(s.decided) == 3  # the announced decision plus the two picked


def test_feeding_stops_at_the_first_rejected_input():
    s = reach("lemonade-more-sugar", {"decide": "all"})
    c = fake({"inputs": [step("add", "4", "18", "22"), step("divide", "18", "6", "3")], "note": ""})
    r = ai.say(s, "4 plus 18 is 22 then 18 / 6 = 3", c)
    assert r["checked"] == [True, False] and kinds(r["feedback"]) == ["unknown"]
    assert s.question.history == []


def test_trap_choice_stops_and_explains():
    s = WordProblemSession("lemonade-more-sugar")
    trap = next(i for i, j in enumerate(s.order[s.di], 1) if not s.wp["extract"][s.di]["options"][j].get("correct"))
    c = fake({"inputs": [{"kind": "choice", "decision": 1, "index": trap}, step("multiply", "4", "18", "72")], "note": ""})
    r = ai.say(s, "sugar and water", c)
    assert kinds(r["feedback"]) == ["trap"] and r["checked"] == [True, False] and s.phase == "extract"


def test_nothing_readable_returns_the_note():
    s = QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40})
    r = ai.say(s, "what's for lunch", fake({"inputs": [], "note": "Which two numbers are you working with?"}))
    assert r["feedback"] == [] and r["interpreted"] == [] and r["note"].startswith("Which two")


def test_invalid_input_is_dropped_with_the_rest():
    s = QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40})
    rd = ai.interpret(s, "x", fake({"inputs": [step("multiply", "3", "40", "120"), step("divide", "lots", "5")],
                                    "note": ""}))
    assert len(rd.inputs) == 1 and len(rd.raw) == 2


def test_fallback_text_after_switch_point_is_used():
    s = QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40})
    rd = ai.interpret(s, "3 x 40", fake({"inputs": [step("multiply", "3", "40")], "note": ""}, fallback=True))
    assert rd.error is None and rd.inputs[0].result is None and rd.inputs[0].left.text == "3"


@pytest.mark.parametrize("error", [
    anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")),
    anthropic.RateLimitError("slow down", response=httpx2.Response(
        429, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), body=None),
    anthropic.InternalServerError("boom", response=httpx2.Response(
        500, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), body=None),
])
def test_api_errors_degrade_gracefully(error):
    s = QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40})
    r = ai.say(s, "3 times 40", fake(error=error))
    assert r["note"] == ai.UNREACHABLE and r["error"] and r["feedback"] == [] and s.history == []


def test_refusal_is_handled():
    s = QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40})
    rd = ai.interpret(s, "x", fake({"inputs": [], "note": ""}, stop_reason="refusal"))
    assert rd.error == "refusal" and rd.inputs == [] and rd.note


# ---------------------------------------------------------------- credentials

def test_env_file_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nANTHROPIC_API_KEY=from-file  # my key\nexport ANTHROPIC_KEY='quoted # not a comment'\n"
                   "OTHER_SECRET=never-loaded\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "already-set")
    monkeypatch.delenv("ANTHROPIC_KEY", raising=False)
    monkeypatch.delenv("OTHER_SECRET", raising=False)
    ai.load_env(env)
    import os
    assert os.environ["ANTHROPIC_API_KEY"] == "already-set" and os.environ["ANTHROPIC_KEY"] == "quoted # not a comment"
    assert "OTHER_SECRET" not in os.environ  # only the key names are read from .env
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # an empty variable counts as unset
    ai.load_env(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "from-file"  # and the inline comment is stripped


# ---------------------------------------------------------------- the web routes

web = TestClient(app)


def no_key(monkeypatch):
    monkeypatch.setattr(ai, "api_key", lambda: None)


def test_status_endpoint(monkeypatch):
    no_key(monkeypatch)
    assert web.get("/api/ai/status").json() == {"configured": False, "model": "claude-opus-5-5"}
    monkeypatch.setattr(ai, "api_key", lambda: "sk-test")
    assert web.get("/api/ai/status").json()["configured"] is True


def test_say_route_with_fake_client(monkeypatch):
    monkeypatch.setattr(ai, "api_key", lambda: "sk-test")
    monkeypatch.setattr(ai, "_client", fake({"inputs": [step("multiply", "3", "40", "120")], "note": ""}))
    monkeypatch.setattr(ai, "_client_key", ai._FIXED)
    sid = web.post("/api/sessions", json={"problem": "missing-value:1"}).json()["id"]
    r = web.post(f"/api/sessions/{sid}/say", json={"text": "3 times 40 is 120"}).json()
    assert r["interpreted"] == ["3 × 40 = 120"] and r["checked"] == [True]
    assert [f["kind"] for f in r["feedback"]] == ["correct", "method"] and r["phase"] == "steps"
    # the other commands still work beside /say
    assert web.post(f"/api/sessions/{sid}/hint").json()["feedback"][0]["kind"] == "hint"


def test_say_route_without_key(monkeypatch):
    no_key(monkeypatch)
    sid = web.post("/api/sessions", json={"problem": "missing-value:1"}).json()["id"]
    r = web.post(f"/api/sessions/{sid}/say", json={"text": "3 times 40"}).json()
    assert r["error"] == "not_configured" and r["note"] == ai.UNREACHABLE
    assert web.post("/api/sessions/nope/say", json={"text": "1"}).status_code == 404


# ---------------------------------------------------------------- the eval set

def test_every_eval_case_resolves():
    assert evalrun.dry(evalrun.load()) == 0


def test_eval_scoring_normalizes():
    s = reach("lemonade-more-sugar", {"decide": "all"})
    k = evalrun.normalize_key
    assert k(parse("18 x 4 = 72")) == k(parse("4 x 18 = 72"))
    assert k(parse("18 / 6 = 3")) != k(parse("6 / 18 = 3"))
    assert k(parse("3/4 > 5/7")) == k(parse("5/7 < 3/4"))
    assert k(parse("4 / 6 = 0.667")) != k(parse("4 / 6 = 2/3"))
    assert expected(s, ["value:12"]) == [("value", 12)]


def test_eval_case_scored_with_fake_client():
    case = {"id": "t", "category": "find_method", "problem": "lemonade-more-sugar", "at": {"decide": "all"},
            "say": "6 goes into 18 three times", "expect": ["18 / 6 = 3"], "method": "scale_factor"}
    r = evalrun.run_case(case, fake({"inputs": [step("divide", "18", "6", "3")], "note": ""}))
    assert r["ok"] and r["method_ok"] and r["methods"]["got"] == ["scale_factor"]
    r = evalrun.run_case(case, fake({"inputs": [step("divide", "6", "18", "3")], "note": ""}))
    assert not r["ok"]


# ---------------------------------------------------------------- reading decisions in any order, the prompt

def test_a_later_decision_on_its_own_is_answered():
    s = WordProblemSession("lemonade-more-sugar")
    first = s.di
    later = s.open_decisions()[1]
    opts = s.options_of(later)
    good = next(i for i, j in enumerate(s.order[later], 1) if s.wp["extract"][later]["options"][j].get("correct"))
    r = ai.say(s, "the 18 is the extra", fake({"inputs": [{"kind": "choice", "decision": 2, "index": good}], "note": ""}))
    assert r["checked"] == [True] and kinds(r["feedback"]) == ["correct"] and r["interpreted"] == [opts[good - 1]]
    assert later in s.decided and first not in s.decided and s.di == first


def test_a_choice_for_no_listed_decision_is_reported_not_dropped():
    s = WordProblemSession("lemonade-more-sugar")
    r = ai.say(s, "the ninth one", fake({"inputs": [{"kind": "choice", "decision": 9, "index": 1}], "note": ""}))
    assert r["checked"] == [False] and kinds(r["feedback"]) == ["error"] and "which decision" in r["feedback"][0].message
    assert not s.decided - {di for di, d in enumerate(s.wp["extract"]) if all(o.get("correct") for o in d["options"])}


def test_prompt_promises_only_what_the_graph_accepts():
    assert "the 4 ÷ 6 they did in their head isn't returned" not in ai.SYSTEM
    assert '"two thirds of 18 is 12" is just 2/3 × 18 = 12' in ai.SYSTEM
    assert "never names a number" in ai.SYSTEM  # the note can't hint at the pairing


@pytest.mark.parametrize("cid", ["head-02", "head-03", "head-04", "head-05"])
def test_in_head_cases_land_on_the_graph(cid):
    """The expected reading of each in-head case is accepted by the session, step by step (the graph has a node for
    it). head-01 (two thirds of 18) stays a faithful reading the graph has no node for."""
    case = next(c for c in evalrun.load() if c["id"] == cid)
    s = reach(case["problem"], case["at"])
    inputs = [parse(x) for x in case["expect"]]
    fb, shown, checked = ai.feed(s, inputs)
    assert all(checked) and any(f.kind == "correct" for f in fb), (cid, [f.message for f in fb])
    assert not any(f.kind in ("unknown", "error", "trap") for f in fb), (cid, [f.message for f in fb])


def test_rate_limit_per_session_and_overall():
    from tutor.ai_web import RateLimit
    now = [0.0]
    lim = RateLimit(per_session=(2, 600), overall=(3, 3600), clock=lambda: now[0])
    assert lim.allow("a") and lim.allow("a") and not lim.allow("a")
    assert lim.allow("b") and not lim.allow("c")  # 3 in the hour in all
    now[0] = 601
    assert not lim.allow("a")  # the session window is open again, but the hour isn't
    now[0] = 3601
    assert lim.allow("a")


def test_say_route_is_rate_limited_and_capped(monkeypatch):
    from tutor import ai_web
    monkeypatch.setattr(ai, "api_key", lambda: "sk-test")
    c = fake({"inputs": [], "note": "Which numbers?"}, {"inputs": [], "note": "Which numbers?"})
    monkeypatch.setattr(ai, "_client", c)
    monkeypatch.setattr(ai, "_client_key", ai._FIXED)
    monkeypatch.setattr(ai_web, "LIMIT", ai_web.RateLimit(per_session=(1, 600)))
    sid = web.post("/api/sessions", json={"problem": "missing-value:1"}).json()["id"]
    assert web.post(f"/api/sessions/{sid}/say", json={"text": "x" * 5000}).status_code == 200
    sent = c.beta.messages.calls[0]["messages"][0]["content"]
    assert "x" * ai.MAX_TEXT in sent and "x" * (ai.MAX_TEXT + 1) not in sent
    assert c.beta.messages.calls[0]["max_tokens"] == ai.MAX_TOKENS <= 2000
    r = web.post(f"/api/sessions/{sid}/say", json={"text": "again"})
    assert r.status_code == 429 and "Wait a few minutes" in r.json()["detail"]


def test_bad_numbers_from_the_model_are_dropped():
    s = QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40})
    rd = ai.interpret(s, "x", fake({"inputs": [step("divide", "1/0", "2"), step("multiply", "1e10000000", "2")], "note": ""}))
    assert rd.inputs == [] and rd.note


# ---------------------------------------------------------------- second review

def test_env_file_with_bom_bad_bytes_and_unclosed_quote(tmp_path, monkeypatch):
    import os
    env = tmp_path / ".env"
    env.write_bytes("﻿ANTHROPIC_API_KEY=\"unterminated # note\n".encode() + b"\xff\xfe junk\n")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ai.load_env(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "unterminated"
    ai.load_env(tmp_path / "missing" / ".env")  # no file: nothing happens


def test_client_is_rebuilt_when_the_key_changes(monkeypatch):
    keys = iter(["sk-one", "sk-one", "sk-two"])
    monkeypatch.setattr(ai, "api_key", lambda: next(keys))
    monkeypatch.setattr(ai, "_client", None)
    monkeypatch.setattr(ai, "_client_key", None)
    a = ai.get_client()
    assert ai.get_client() is a
    b = ai.get_client()
    assert b is not a and ai._client_key == "sk-two"


def test_any_client_exception_gives_the_generic_note():
    s = QuestionSession("missing-value", {"a": 3, "b": 5, "d": 40})
    r = ai.say(s, "3 times 40", fake(error=RuntimeError("boom")))
    assert r["note"] == ai.UNREACHABLE and r["error"] == "unexpected" and r["feedback"] == []


def test_choices_resolve_by_the_decisions_the_request_showed():
    s = WordProblemSession("lemonade-more-sugar")
    ids = ai.decision_ids(s)  # taken when the request is built
    first, second = ids[0], ids[1]
    good = next(i for i, j in enumerate(s.order[second], 1) if s.wp["extract"][second]["options"][j].get("correct"))
    s.decide(first, next(i for i, j in enumerate(s.order[first], 1) if s.wp["extract"][first]["options"][j].get("correct")))
    # the session moved on while Claude was reading: "decision 2" still means the second one shown
    fb, shown, checked = ai.feed(s, [ChoiceAnswer(index=good)], [2], ids)
    assert checked == [True] and second in s.decided and kinds(fb)[0] == "correct"


def test_rate_limiter_forgets_idle_sessions(monkeypatch):
    from tutor import ai_web
    monkeypatch.setattr(ai_web, "MAX_TRACKED", 3)
    now = [0.0]
    lim = ai_web.RateLimit(per_session=(5, 600), overall=(1000, 3600), clock=lambda: now[0])
    for i in range(3):
        assert lim.allow(f"s{i}")
    now[0] = 700  # their windows have passed
    assert lim.allow("new") and lim.allow("new2")
    assert set(lim.calls) <= {"s0", "s1", "s2", "new", "new2"} and len(lim.calls) <= 3 + 1
    lim.prune()
    assert set(lim.calls) == {"new", "new2"}
    for i in range(10):
        lim.allow(f"x{i}")
    assert len(lim.calls) <= 4  # capped
