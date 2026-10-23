"""The web API drives the same sessions as the terminal app."""

from fastapi.testclient import TestClient

from tutor.web import app

client = TestClient(app)


def test_page_and_problem_list():
    assert "Problem solving, step by step" in client.get("/").text
    items = client.get("/api/problems").json()
    assert {"lemonade-more-sugar", "compare-fractions:1"} <= {i["key"] for i in items}


def test_question_session_to_the_end():
    s = client.post("/api/sessions", json={"problem": "missing-value:1"}).json()
    assert s["ask"]["allow_step"] and s["story"] == "Solve 3/5 = x/40."
    sid = s["id"]
    r = client.post(f"/api/sessions/{sid}/input", json={"text": "3 x 40 = 120"}).json()
    assert [f["kind"] for f in r["feedback"]] == ["correct", "method"]
    r = client.post(f"/api/sessions/{sid}/input", json={"text": "120 / 5 = 24"}).json()
    assert r["ask"]["text"] == "What's your answer?"
    r = client.post(f"/api/sessions/{sid}/input", json={"text": "24"}).json()
    assert r["done"]


def test_word_problem_options_and_commands():
    s = client.post("/api/sessions", json={"problem": "lemonade-more-sugar"}).json()
    assert s["ask"]["options"] and s["map"].endswith("word-problems/lemonade-more-sugar.html")
    r = client.post(f"/api/sessions/{s['id']}/hint").json()
    assert r["feedback"][0]["kind"] == "hint"
    r = client.post(f"/api/sessions/{s['id']}/input", json={"text": "6 x 18 = 108"}).json()
    assert r["feedback"][0]["kind"] == "trap"


def test_unknown_session_and_problem():
    assert client.post("/api/sessions/nope/input", json={"text": "1"}).status_code == 404
    assert client.post("/api/sessions", json={"problem": "nope"}).status_code == 404


# ---------------------------------------------------------------- the statement log (tutor/log.py)

def lines_for(sid):
    from tutor import log
    return [l for l in log.read() if l["session"] == sid]


def test_every_statement_is_logged_and_reads_back():
    sid = client.post("/api/sessions", json={"problem": "lemonade-more-sugar"}).json()["id"]
    client.post(f"/api/sessions/{sid}/hint")
    client.post(f"/api/sessions/{sid}/input", json={"text": "18 / 6 = 3"})
    client.post(f"/api/sessions/{sid}/step", json={"kind": "value", "value": {"text": "12"}})
    client.post(f"/api/sessions/{sid}/done")
    got = lines_for(sid)
    assert [l["endpoint"] for l in got] == ["start", "hint", "input", "step", "done"]
    typed = got[2]
    assert typed["problem"] == "lemonade-more-sugar" and typed["text"] == "18 / 6 = 3"
    assert typed["parsed"][0]["kind"] == "arithmetic" and typed["before"]["phase"] == "extract"
    assert typed["after"]["question"]["named"] == ["scale_factor"]
    assert "correct" in [f["kind"] for f in typed["feedback"]] and typed["time"].endswith("+00:00")
    value = got[3]
    assert value["input"] == {"kind": "value", "value": {"text": "12"}} and value["after"]["phase"] == "done"
    assert not any(k in l for l in got for k in ("name", "email", "ip"))


def test_choosing_a_method_is_logged():
    sid = client.post("/api/sessions", json={"problem": "missing-value:1"}).json()["id"]
    client.post(f"/api/sessions/{sid}/method", json={"method": "scale_factor"})
    (line,) = [l for l in lines_for(sid) if l["endpoint"] == "method"]
    assert line["method"] == "scale_factor" and line["before"]["routes"] > line["after"]["routes"]
    assert line["after"]["named"] == ["scale_factor"]


def test_what_claude_read_is_logged(monkeypatch):
    from test_ai import fake, step
    from tutor import ai
    monkeypatch.setattr(ai, "api_key", lambda: "sk-test")
    monkeypatch.setattr(ai, "_client", fake({"inputs": [step("multiply", "3", "40", "120")], "note": ""}))
    monkeypatch.setattr(ai, "_client_key", ai._FIXED)
    sid = client.post("/api/sessions", json={"problem": "missing-value:1"}).json()["id"]
    client.post(f"/api/sessions/{sid}/say", json={"text": "3 times 40 is 120"})
    (line,) = [l for l in lines_for(sid) if l["endpoint"] == "say"]
    assert line["text"] == "3 times 40 is 120" and line["interpreted"] == ["3 × 40 = 120"]
    assert line["inputs"][0]["op"] == "multiply" and line["checked"] == [True]


def test_a_long_text_is_cut_in_the_log():
    from tutor import log
    sid = client.post("/api/sessions", json={"problem": "missing-value:1"}).json()["id"]
    client.post(f"/api/sessions/{sid}/input", json={"text": "x" * 100_000})
    (line,) = [l for l in lines_for(sid) if l["endpoint"] == "input"]
    assert len(line["text"]) == log.MAX_TEXT


def test_a_log_that_cant_be_written_doesnt_stop_the_student(monkeypatch, tmp_path):
    monkeypatch.setenv("TUTOR_LOG", str(tmp_path))  # a directory: opening it to append fails
    sid = client.post("/api/sessions", json={"problem": "missing-value:1"}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/input", json={"text": "3 x 40 = 120"})
    assert r.status_code == 200 and r.json()["feedback"][0]["kind"] == "correct"
