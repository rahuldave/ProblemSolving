"""Routes for the choice (setup) and box (steps) inputs.

    GET  /api/sessions/{sid}/boxes    what to draw now: {"stage": "extract" | "find_method" | "steps" | "done", …}
                                      (tutor/skills.py documents the spec)
    POST /api/sessions/{sid}/method   {"method": "scale_factor"}: keep only that method's live routes (all of them)

Extraction choices and each widget's typed StudentInput go to the shared POST /api/sessions/{sid}/step.
"""

from fastapi import HTTPException
from pydantic import BaseModel


class Choose(BaseModel):
    method: str


def register(app):
    @app.get("/api/sessions/{sid}/boxes")
    def boxes(sid: str):
        from . import skills
        from .web import LOCK, lookup
        entry = lookup(sid)
        with LOCK:
            return skills.spec(entry["session"])

    @app.post("/api/sessions/{sid}/method")
    def choose_method(sid: str, body: Choose):
        from .web import LOCK, lookup, state
        entry = lookup(sid)
        with LOCK:
            feedback = entry["session"].choose_method(body.method)
        if feedback and feedback[0].kind == "error":
            raise HTTPException(422, feedback[0].message)
        return state(sid, entry, feedback)
