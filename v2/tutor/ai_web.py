"""Routes for the model mode: free text read by Claude into the same typed inputs.

    POST /api/sessions/{sid}/say  {"text": "..."}  → {**state, "interpreted": [...], "checked": [...], "note": ..., "error": ...}
                                                     (429 with a friendly detail past the rate limit; the text is cut
                                                     to ai.MAX_TEXT characters)
    GET  /api/ai/status                            → {"configured": bool, "model": ...}

The model call happens outside the session lock: the request is built under the lock, Claude reads it without the
lock held, and the inputs are fed to the session under the lock again.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException
from pydantic import BaseModel

from . import ai

PER_SESSION = (20, 600)   # at most 20 readings per session in 10 minutes
GLOBAL = (300, 3600)      # and 300 in an hour in all
MAX_TRACKED = 5000        # sessions remembered by the per-session limit
BUSY = "Claude has read a lot of messages just now. Wait a few minutes, or switch to typing the step."


class RateLimit:
    """A sliding-window count of model calls, per session and in total, in this process."""

    def __init__(self, per_session=PER_SESSION, overall=GLOBAL, clock=time.monotonic):
        self.per_session, self.overall, self.clock = per_session, overall, clock
        self.calls = defaultdict(deque)
        self.all = deque()
        self.lock = threading.Lock()

    def allow(self, sid: str) -> bool:
        now = self.clock()
        with self.lock:
            mine = self.calls.get(sid, deque())  # a refused call adds no key
            for q, (_, window) in ((mine, self.per_session), (self.all, self.overall)):
                while q and q[0] <= now - window:
                    q.popleft()
            if len(mine) >= self.per_session[0] or len(self.all) >= self.overall[0]:
                return False
            mine.append(now)
            self.calls[sid] = mine
            self.all.append(now)
            if len(self.calls) > MAX_TRACKED:
                self.prune(now)
            return True

    def prune(self, now=None):
        """Forget sessions with no call in their window, then, if there are still too many, the oldest ones."""
        now = self.clock() if now is None else now
        window = self.per_session[1]
        for k in list(self.calls):
            q = self.calls[k]
            while q and q[0] <= now - window:
                q.popleft()
            if not q:
                del self.calls[k]
        if len(self.calls) > MAX_TRACKED:
            for k in sorted(self.calls, key=lambda k: self.calls[k][-1])[:len(self.calls) - MAX_TRACKED]:
                del self.calls[k]


LIMIT = RateLimit()


class Said(BaseModel):
    text: str


def register(app):
    @app.post("/api/sessions/{sid}/say")
    def say(sid: str, body: Said):
        from .web import LOCK, lookup, state

        entry = lookup(sid)
        s = entry["session"]
        text = body.text.strip()[:ai.MAX_TEXT]
        if not text:
            return {**state(sid, entry, []), "interpreted": [], "checked": [], "note": "Say your step or your answer.",
                    "error": None}
        if not ai.configured():
            return {**state(sid, entry, []), "interpreted": [], "checked": [], "note": ai.UNREACHABLE,
                    "error": "not_configured"}
        if not LIMIT.allow(sid):
            raise HTTPException(429, BUSY)
        with LOCK:
            req = ai.request(s, text)
            ids = ai.decision_ids(s)  # the decisions as this request numbers them
        reading = ai.call(req)
        with LOCK:
            feedback, shown, checked = (ai.feed(s, reading.inputs, reading.decisions, ids) if reading.inputs
                                        else ([], [], []))
        return {**state(sid, entry, feedback), "interpreted": shown, "checked": checked, "note": reading.note,
                "error": reading.error}

    @app.get("/api/ai/status")
    def status():
        return {"configured": ai.configured(), "model": ai.MODEL}
