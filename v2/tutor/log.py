"""One line of JSON for each statement a student submits (PATHS.md, "Logging").

A line holds the session id, the problem, the endpoint, the phase, the text or the typed input, how the text parses,
the consistent set (the live routes and the methods they name, the story's settled decisions) before and after, the
feedback, and the time. It holds nothing about the student: the session id is a random number.

The file is $TUTOR_LOG, or v2/logs/statements.jsonl (git-ignored). On the dokku server the container's files go when
it restarts, so keeping the log needs a storage mount. Writing a line never fails a request.
"""

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import build as engine

from .parse import ParseError, parse_all
from .session import QuestionSession, WordProblemSession

DEFAULT = engine.ROOT / "logs" / "statements.jsonl"
_lock = threading.Lock()


def path() -> Path:
    return Path(os.environ.get("TUTOR_LOG") or DEFAULT)


def _question_state(q: QuestionSession) -> dict:
    return {"phase": q.phase, "routes": len(q.live), "shadow": len(q.shadow), "methods": q.live_methods(),
            "named": q.named_methods(), "steps": list(q.history)}


def snapshot(session) -> dict:
    """The consistent set: for a question, its live routes and methods; for a story, its decisions as well."""
    if isinstance(session, WordProblemSession):
        out = {"phase": session.phase, "decided": sorted(session.decided), "asking": session.di,
               "open_readings": [t["option"]["say"] for t in session.open_readings()]}
        if session.question is not None:
            out["question"] = _question_state(session.question)
        return out
    return _question_state(session)


def parsed(session, text: str):
    """How the text parses, with the options on offer now (12 is a choice only when there are 12 options)."""
    try:
        choices = len(session.ask().get("options") or [])
        return [r.model_dump(mode="json") for r in parse_all(text, choices)]
    except ParseError as e:
        return {"error": str(e)}
    except Exception as e:  # the log never fails a request
        return {"error": repr(e)}


def write(sid: str, problem: str, endpoint: str, before: dict, after: dict, feedback, **extra) -> None:
    """Append one line. `before` and `after` are state() snapshots taken under the session lock; `extra` holds what
    the endpoint had: text, input, parsed, method, interpreted, …"""
    try:
        line = {"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "session": sid,
                "problem": problem, "endpoint": endpoint, **extra, "before": before, "after": after,
                "feedback": [{"kind": f.kind, "message": f.message} for f in feedback]}
        text = json.dumps(line, ensure_ascii=False, default=str)
        p = path()
        with _lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")
    except Exception as e:  # a full disk or a bad path must not stop the student
        print(f"tutor log: {e!r}", file=sys.stderr)


def state(session) -> dict:
    """snapshot(), or the error that stopped it: the log never fails a request."""
    try:
        return snapshot(session)
    except Exception as e:
        return {"error": repr(e)}


def read(p: Path | None = None) -> list[dict]:
    """Every line of the log, for tests and for reading it back."""
    p = p or path()
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
