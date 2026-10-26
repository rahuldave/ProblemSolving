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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, TypeAdapter, ValidationError

import build as engine

from . import log
from .models import StudentInput
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


TYPED = TypeAdapter(StudentInput)


def map_url(key: str) -> str:
    if key in engine.WP:
        return f"{SITE}/word-problems/{key}.html"
    return f"{SITE}/questions/{key.split(':')[0]}.html"


def stage(s) -> str:
    """Where the student is: reading the story (extract), finding the method (find_method), or doing its steps."""
    if s.phase == "done":
        return "done"
    if isinstance(s, WordProblemSession):
        if s.phase == "extract":
            return "extract"
        if s.phase != "solve":
            return "steps"
        s = s.question
    return "find_method" if s.phase == "steps" and len(s.named_methods()) > 1 else "steps"


def state(sid: str, entry: dict, feedback) -> dict:
    s = entry["session"]
    return {"id": sid, "problem": entry["key"], "feedback": [f.model_dump() for f in feedback],
            "ask": s.ask(), "phase": s.phase, "stage": stage(s), "done": s.phase == "done"}


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


app.mount("/static", StaticFiles(directory=STATIC), name="static")


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
    log.write(sid, body.problem, "start", {}, log.state(session), getattr(session, "pending", []))
    if isinstance(session, WordProblemSession):
        head = {"title": session.wp["title"], "story": session.wp["text"]}
    else:
        head = {"title": title.split(": ", 1)[0], "story": session.title()}
    return {**state(sid, entry, getattr(session, "pending", [])), **head, "map": map_url(body.problem)}


@app.post("/api/sessions/{sid}/input")
def submit(sid: str, body: Entry):
    entry = lookup(sid)
    s = entry["session"]
    with LOCK:
        before = log.state(s)
        s.read = None
        feedback = s.submit(body.text)
        after, parsed = log.state(s), log.parsed(s)
    log.write(sid, entry["key"], "input", before, after, feedback, text=body.text, parsed=parsed)
    return state(sid, entry, feedback)


@app.post("/api/sessions/{sid}/step")
def submit_typed(sid: str, body: dict):
    """A typed StudentInput (a step, a choice or a value) from a structured UI: no parsing."""
    entry = lookup(sid)
    try:
        inp = TYPED.validate_python(body)
        if getattr(inp, "typed", False):  # a structured input isn't typed text: its fractions are one number
            inp = inp.model_copy(update={"typed": False})
    except ValidationError as e:
        raise HTTPException(422, e.errors()[0]["msg"])
    s = entry["session"]
    with LOCK:
        before = log.state(s)
        feedback = s.submit_input(inp)
        after = log.state(s)
    log.write(sid, entry["key"], "step", before, after, feedback, input=inp.model_dump(mode="json"))
    return state(sid, entry, feedback)


def command(sid: str, command: str):
    entry = lookup(sid)
    s = entry["session"]
    with LOCK:
        before = log.state(s)
        if command == "hint":
            feedback = s.hint()
        elif command == "where":
            feedback = s.where()
        else:
            feedback = s.done_command() if isinstance(s, WordProblemSession) else s.finish_steps()
        after = log.state(s)
    if command != "where":  # where only shows the steps back
        log.write(sid, entry["key"], command, before, after, feedback)
    return state(sid, entry, feedback)


def _command_route(name):
    def route(sid: str):
        return command(sid, name)
    return route


for _cmd in ("hint", "where", "done"):  # one route each, so other modes can add /api/sessions/{sid}/<their own>
    app.post(f"/api/sessions/{{sid}}/{_cmd}", name=_cmd)(_command_route(_cmd))


@app.get("/healthz")
def health():
    return {"ok": True}




# The other input modes add their own routes: boxes for each skill (skills_web) and a model reading free text (ai_web).
from . import ai_web, skills_web  # noqa: E402

skills_web.register(app)
ai_web.register(app)
