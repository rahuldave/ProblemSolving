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
