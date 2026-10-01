"""Web front end for the tutor: the same sessions as the terminal app, behind a small JSON API and one page.

    uv run uvicorn tutor.web:app --reload        # from v2/, then open http://127.0.0.1:8000

Sessions live in memory (one process), keyed by an id the page keeps; the oldest are dropped past MAX_SESSIONS.
"""

import threading
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import build as engine

from .session import QuestionSession, WordProblemSession, catalog

SITE = "https://rahuldave.com/ProblemSolving"
MAX_SESSIONS = 2000
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app):
    """Expand every question's routes in the background so the first student doesn't wait."""
    threading.Thread(target=lambda: [engine.variants_of(q) for q in engine.Q], daemon=True).start()
    yield


app = FastAPI(title="Problem solving, step by step", lifespan=lifespan)
ITEMS = {key: (title, make) for key, title, make in catalog()}
SESSIONS: "OrderedDict[str, dict]" = OrderedDict()
LOCK = threading.Lock()


class Start(BaseModel):
    problem: str


class Entry(BaseModel):
    text: str


def map_url(key: str) -> str:
    if key in engine.WP:
        return f"{SITE}/word-problems/{key}.html"
    return f"{SITE}/questions/{key.split(':')[0]}.html"


def state(sid: str, entry: dict, feedback) -> dict:
    s = entry["session"]
    return {"id": sid, "problem": entry["key"], "feedback": [f.model_dump() for f in feedback],
            "ask": s.ask(), "phase": s.phase, "done": s.phase == "done"}


def lookup(sid: str) -> dict:
    with LOCK:
        entry = SESSIONS.get(sid)
        if entry:
            SESSIONS.move_to_end(sid)
    if not entry:
        raise HTTPException(404, "That session has expired; start the problem again.")
    return entry


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/problems")
def problems():
    out = []
    for key, (title, _) in ITEMS.items():
        if key in engine.WP:
            group, label = "Word problems", engine.WP[key]["title"]
        else:
            qid = key.split(":")[0]
            q = engine.Q[qid]
            group = {"core": "Questions", "applied": "Questions in context", "skill": "Skills"}[q["kind"]]
            label = title.split(": ", 1)[1]
        out.append({"key": key, "group": group, "label": label, "map": map_url(key)})
    order = ["Word problems", "Questions", "Questions in context", "Skills"]
    return sorted(out, key=lambda it: order.index(it["group"]))


@app.post("/api/sessions")
def start(body: Start):
    if body.problem not in ITEMS:
        raise HTTPException(404, f"No problem {body.problem!r}.")
    title, make = ITEMS[body.problem]
    session = make()
    sid = uuid.uuid4().hex
    entry = {"key": body.problem, "session": session, "created": time.time()}
    with LOCK:
        SESSIONS[sid] = entry
        while len(SESSIONS) > MAX_SESSIONS:
            SESSIONS.popitem(last=False)
    if isinstance(session, WordProblemSession):
        head = {"title": session.wp["title"], "story": session.wp["text"]}
    else:
        head = {"title": title.split(": ", 1)[0], "story": session.title()}
    return {**state(sid, entry, getattr(session, "pending", [])), **head, "map": map_url(body.problem)}


@app.post("/api/sessions/{sid}/input")
def submit(sid: str, body: Entry):
    entry = lookup(sid)
    with LOCK:
        feedback = entry["session"].submit(body.text)
    return state(sid, entry, feedback)


@app.post("/api/sessions/{sid}/{command}")
def command(sid: str, command: str):
    entry = lookup(sid)
    s = entry["session"]
    with LOCK:
        if command == "hint":
            feedback = s.hint()
        elif command == "where":
            feedback = s.where()
        elif command == "done":
            feedback = s.done_command() if isinstance(s, WordProblemSession) else s.finish_steps()
        else:
            raise HTTPException(404, f"Unknown command {command!r}.")
    return state(sid, entry, feedback)


@app.get("/healthz")
def health():
    return {"ok": True}


