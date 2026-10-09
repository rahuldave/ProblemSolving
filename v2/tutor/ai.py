"""Talk it through: Claude reads a student's free text into the tutor's typed inputs.

Claude only interprets. It turns "6 goes into 18 three times, so 4 times 3 is 12" into
[18 ÷ 6 = 3, 4 × 3 = 12] and never says whether that's right. The deterministic session (session.py) still walks
the graph and gives all the feedback, exactly as it does for typed steps and boxes.

    context(session)            the compact description of where the student is, for the model
    interpret(session, text)    one model call → Reading(inputs, note, usage, error)
    feed(session, inputs)       submit the inputs in order, stopping at the first one the session doesn't accept
    say(session, text)          interpret + feed, for the web route

Credentials: ANTHROPIC_API_KEY from the environment, else from the repo's git-ignored .env (which may also spell it
ANTHROPIC_KEY). An already-set environment variable always wins. The key is never printed or logged.
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

import build as engine

from .models import Feedback, StudentInput
from .session import QuestionSession, WordProblemSession, answer_options, written

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
ACCEPTED = {"correct", "slip", "on_track", "done"}  # feedback kinds that mean the session took the input
UNREACHABLE = "I couldn't reach the helper; try typing the step."
MAX_TEXT = 500     # characters of a message sent to Claude
MAX_TOKENS = 1500  # a reading is a short JSON list of inputs
TIMEOUT = 20.0     # seconds per request
TYPED = TypeAdapter(StudentInput)

# Price per million tokens for claude-opus-5-5 (input, output, cache write 5m, cache read).
PRICE = {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20}


# ---------------------------------------------------------------- credentials

KEY_NAMES = ("ANTHROPIC_API_KEY", "ANTHROPIC_KEY")


def load_env(path: Path = ENV_FILE, names=KEY_NAMES) -> None:
    """Read the API key lines (only `names`) from .env into os.environ, without overriding a variable that is
    already set to something non-empty. Inline ` # comments` are stripped, a byte-order mark and an unclosed quote
    are tolerated, and an unreadable file counts as no file (so /say and /status never fail on it)."""
    try:
        if not path.is_file():
            return
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        v = v.strip()
        if v[:1] and v[:1] in "\"'":
            end = v[1:].find(v[0])
            v = v[1:1 + end] if end >= 0 else v[1:].split(" #", 1)[0].strip()  # an unclosed quote: drop it
        else:
            v = v.split(" #", 1)[0].strip()
        if k in names and v and not os.environ.get(k):
            os.environ[k] = v


def api_key() -> str | None:
    load_env()
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_KEY") or None


def configured() -> bool:
    return bool(api_key())


_client = None
_client_key = None
_FIXED = object()  # a client set with set_client() is kept whatever the key


def get_client():
    """The shared SDK client, made on first use and made again when the key changes. Tests replace it with
    set_client()."""
    global _client, _client_key
    key = api_key()
    if _client is None or (_client_key is not _FIXED and _client_key != key):
        import anthropic
        _client = anthropic.Anthropic(api_key=key, timeout=TIMEOUT, max_retries=1)
        _client_key = key
    return _client


def set_client(client) -> None:
    global _client, _client_key
    _client, _client_key = client, (_FIXED if client is not None else None)


# ---------------------------------------------------------------- the prompt

SYSTEM = """\
You read a student's free-text message in a step-by-step math tutor and rewrite it as the tutor's typed inputs. \
You are a careful reader, not a teacher: never judge, correct, finish or improve the student's work. If the student \
writes a wrong step or wrong arithmetic, transcribe it exactly as they wrote it; the tutor checks it afterwards. \
The tutor (not you) decides what is right, gives feedback and hints.

Each request gives the current state of the problem (the story or question, what is being asked now, and the work so \
far) and then the student's message. Return JSON: {"inputs": [...], "note": "..."}.

## Input kinds

- {"kind": "arithmetic", "op": "add"|"subtract"|"multiply"|"divide", "left": "...", "right": "...", "result": "..."|null}
  One calculation. Keep the order the student said it in: "18 divided by 6" is left 18, right 6. \
"6 goes into 18 three times" is 18 ÷ 6 = 3. "split 12 into 3 groups of 4" is 12 ÷ 3 = 4. "times", "of", "groups of", \
"lots of" mean multiply; "plus", "and" (when combining) mean add; "minus", "take away", "less" mean subtract; \
"over", "divided by", "split into", "shared between", "per", "goes into" (reversed) mean divide. "Half of 18" is \
18 ÷ 2. "Double 6" is 6 × 2. "Triple 4" is 4 × 3. Moving the decimal point one place left is ÷ 10 (two places, \
÷ 100); one place right is × 10. result is the number the student says it equals, or null if they \
didn't say one. Never compute a result the student didn't give.
- {"kind": "function", "name": "gcf"|"lcm", "left": "...", "right": "...", "result": "..."|null}
  Greatest common factor / divisor ("biggest number that goes into both") or least common multiple ("smallest \
number both go into", "least common denominator" of two denominators).
- {"kind": "compare", "left": "...", "relation": "<"|">"|"=", "right": "..."}  Two numbers compared ("21 is bigger \
than 20").
- {"kind": "ratio_compare", "left": ["a", "b"], "relation": "="|"≠", "right": ["c", "d"]}  Two ratios said to be \
the same or not the same ("3 to 4 isn't the same as 5 to 7").
- {"kind": "plot", "points": [["x", "y"], ...]}  Points plotted on a graph.
- {"kind": "choice", "decision": d, "index": n}  Picking option [n] of decision d, using the numbers shown in the \
request. Decision 1 is the one being asked now; the other open decisions are numbered 2, 3, … and can be answered \
too. For final-answer options there is only decision 1.
- {"kind": "value", "value": "..."}  A final answer that is a number.

## Numbers

Every number is a string: a whole number ("12"), a decimal ("0.667", "4.5") or a fraction "a/b" ("2/3"). Write \
words as numbers ("two thirds" → "2/3", "a dozen" → "12", "one and a half" → "1.5" or "3/2" — use a decimal when \
the student said a decimal, a fraction when they said a fraction). Keep a rounded decimal exactly as the student \
rounded it ("about 0.67" → "0.67"). Mixed numbers become improper fractions ("1 and 7/12" → "19/12"). Percents \
become decimals ("15%" → "0.15") unless the student writes them as a division by 100 ("15 over 100" → 15 ÷ 100). \
Drop units and currency ("$4.50" → "4.5"). Fix obvious typos ("18 / 6 = 3" typed as "18 /6 =3", "tims", "devide").

## How to read the message

- Several steps in one message: return them all, in the order the student did them. "18 ÷ 6 is 3 and 3 × 4 is 12" \
is two arithmetic inputs.
- Only return calculations the student states. A step they did in their head and don't mention is not added: \
"two thirds of 18 is 12" is just 2/3 × 18 = 12 (not the 4 ÷ 6 behind the 2/3), and "15% of 80 is 12" is \
0.15 × 80 = 12. The tutor, not you, decides whether skipping a step is fine.
- A separate statement of a quantity the student found, naming it and its value but not the numbers it comes \
from ("it's 3 times as many glasses", "the scale factor is 8", "it's 12 dollars off"), states that calculation \
when the request's numbers make it one clear step: return it with the student's value, where they said it. With 6 \
and 18 glasses, "3 times as many glasses" is 18 ÷ 6 = 3; with 3/5 = x/40, "the scale factor is 8" is 40 ÷ 5 = 8; \
with 15% off $80, "12 dollars off" is 0.15 × 80 = 12. If more than one calculation fits, leave it out.
- A final answer is a separate statement of what the question asks for, like "x is 12", "so the answer is 12" or \
"so he needs 12 spoons" after the work: add a value (or, when the final answer is one of listed answer options, a \
choice of that option). A number that is just the result of a calculation the student states ("15% of 80 is 12", \
"72 ÷ 6 = 12", "it's 12 dollars off") is that calculation's result, not also a final answer. Don't add a final \
answer the student didn't give.
- When options are listed for a decision, a message that agrees with one option, in any words, is a choice of that \
option, even if that option is a wrong reading. Pick the option that matches what the student means, not the one \
you think is right. If the message fits more than one option, or none, don't guess.
- When decisions are listed, the student may answer any of them, in any order, and several at once; return one \
choice per decision answered (with that decision's number), in the order the student answered them. They may also skip the decisions and start calculating: then \
return the calculation, not a choice. They may do both ("18 is just the extra, so 18 ÷ 6 = 3").
- When the student restates what a letter or quantity is, without calculating or choosing, there is nothing to \
return.

## When there is nothing to read

If the message is off-topic, a question to the tutor ("what do I do?", "is it 12?"), unreadable, or too vague to \
turn into a definite input, return "inputs": [] and put one short, friendly clarifying question in "note" that \
helps the student say their step (for example "Which two numbers are you dividing?"). The note only asks them to \
say it more clearly: it never names a number, a quantity, which numbers go together, a reading of the story, a \
method, a step or the answer, not even as a question ("Did you mean sugar with glasses?" is a hint). The tutor \
has its own hints. When you do return inputs, "note" is "".
"""

NUM = {"type": "string", "description": "A number: 12, 0.667 or 2/3."}
PAIR = {"type": "array", "items": NUM, "description": "Exactly two numbers."}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


INPUT_SCHEMAS = [
    _obj({"kind": {"type": "string", "enum": ["arithmetic"]},
          "op": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
          "left": NUM, "right": NUM, "result": {"anyOf": [NUM, {"type": "null"}]}}),
    _obj({"kind": {"type": "string", "enum": ["function"]}, "name": {"type": "string", "enum": ["gcf", "lcm"]},
          "left": NUM, "right": NUM, "result": {"anyOf": [NUM, {"type": "null"}]}}),
    _obj({"kind": {"type": "string", "enum": ["compare"]}, "left": NUM,
          "relation": {"type": "string", "enum": ["<", ">", "="]}, "right": NUM}),
    _obj({"kind": {"type": "string", "enum": ["ratio_compare"]}, "left": PAIR,
          "relation": {"type": "string", "enum": ["=", "≠"]}, "right": PAIR}),
    _obj({"kind": {"type": "string", "enum": ["plot"]}, "points": {"type": "array", "items": PAIR}}),
    _obj({"kind": {"type": "string", "enum": ["choice"]}, "decision": {"type": "integer"}, "index": {"type": "integer"}}),
    _obj({"kind": {"type": "string", "enum": ["value"]}, "value": NUM}),
]
SCHEMA = _obj({"inputs": {"type": "array", "items": {"anyOf": INPUT_SCHEMAS}}, "note": {"type": "string"}})


# ---------------------------------------------------------------- the context for the current phase

def _numbered(options) -> list[str]:
    return [f"  [{i}] {o}" for i, o in enumerate(options, 1)]


def _remaining_decisions(s: WordProblemSession) -> list[int]:
    """The open decisions, the one being asked first (ones with no trap are only announced, so never asked). The
    student may answer any of them, in any order."""
    return [] if s.pre_step() else s.open_decisions()


def _story(s: WordProblemSession) -> list[str]:
    lines = [f"Story: {s.wp['text']}", "Quantities in the story: " + "; ".join(q["text"] for q in s.wp["quantities"])]
    return lines


def _question_lines(q: QuestionSession, letters: list[str] | None, final_ask: dict | None) -> list[str]:
    lines = [f"The question being solved: {q.title()}"]
    if letters:
        unknown = " x is the unknown." if "x/" in q.title() else ""
        lines.append("What the letters stand for: " + "; ".join(letters) + "." + unknown)
    lines.append("Steps so far: " + ("; ".join(q.history) if q.history else "none yet"))
    lines.append("Methods still possible: " + ", ".join(q.methods[m]["name"] for m in q.live_methods()))
    if final_ask:
        if final_ask["options"]:
            lines.append(f"When the steps are done the tutor asks \"{final_ask['text']}\" with these answer options:")
            lines += _numbered(final_ask["options"])
        else:
            lines.append(f"When the steps are done the tutor asks \"{final_ask['text']}\" for a number.")
    return lines


def _final_ask_question(q: QuestionSession) -> dict | None:
    if not q.ask_final:
        return None
    return {"text": "What's your answer?", "options": answer_options(q.qid) or []}


def context(session) -> str:
    """A compact, plain-text description of the current state, for the model."""
    if isinstance(session, WordProblemSession):
        s = session
        lines = [f"Word problem: {s.wp['title']}"] + _story(s)
        if s.phase == "extract":
            lines.append("Phase: reading the story (choosing how to read it), before any calculating.")
            made = [f"{s.wp['extract'][di]['say']} {next(o['say'] for o in s.wp['extract'][di]['options'] if o.get('correct'))}"
                    for di in sorted(s.decided)]
            if made:
                lines.append("Already settled: " + " / ".join(made))
            rest = _remaining_decisions(s)
            for n, di in enumerate(rest):
                dec = s.wp["extract"][di]
                head = "Decision 1 (being asked now)" if n == 0 else f"Decision {n + 1} (also open)"
                lines.append(f"{head}: {dec['say']}")
                lines += _numbered(dec["options"][j]["say"] for j in s.order[di])
            pre = s.pre_step()
            if pre:
                lines.append("Being asked now: write this step of reading the story: "
                             f"{engine.say(pre[0].get('say'), s.run['env'])} (a calculation, returned as a step).")
            else:
                lines.append("The student may answer the decisions above in any order, or skip them and start "
                             "calculating with the story's numbers (a calculation is returned as a step, not a choice).")
            final = s._final_options()
            lines.append(f"The story asks: {s.wp['asks']['text']}.")
            if final:
                lines.append("At the end the tutor will ask for one of: " + ", ".join(final) + ".")
        elif s.phase in ("solve", "then"):
            letters = engine.bind_lines(s.wp, s.plan, s.run)
            final = s._final_options()
            final_ask = {"text": "So what's the answer to the story?", "options": final or []}
            lines.append("Phase: calculating. The reading of the story is settled.")
            lines += _question_lines(s.question, letters, None if s.run["after"] else final_ask)
            if s.phase == "then":
                lines.append(f"The question's answer was {engine.show(s.run['result'])}. The student now does one more "
                             "step to answer the story.")
            lines.append(f"The story asks: {s.wp['asks']['text']}.")
        elif s.phase == "answer":
            ask = s.ask()
            lines.append(f"Phase: final answer. The question's answer was {engine.show(s.run['result'])}.")
            lines.append(f"The story asks: {s.wp['asks']['text']} ({s.wp['asks'].get('unit', '')}).".replace(" ()", ""))
            if ask["options"]:
                lines.append(f"The tutor asks \"{ask['text']}\" with these options (answer with a choice):")
                lines += _numbered(ask["options"])
            else:
                lines.append(f"The tutor asks \"{ask['text']}\". Answer with a value (a number).")
        else:
            lines.append("Phase: finished.")
        return "\n".join(lines)

    q = session
    lines = [f"Question: {q.title()}"]
    if q.phase == "steps":
        lines.append("Phase: calculating.")
        lines += _question_lines(q, None, _final_ask_question(q))
    elif q.phase == "answer":
        lines.append("Phase: final answer. Steps done: " + "; ".join(q.history))
        opts = answer_options(q.qid)
        if opts:
            lines.append("The tutor asks \"What's your answer?\" with these options (answer with a choice):")
            lines += _numbered(opts)
        else:
            lines.append("The tutor asks \"What's your answer?\". Answer with a value (a number).")
    else:
        lines.append("Phase: finished.")
    return "\n".join(lines)


# ---------------------------------------------------------------- the model call

@dataclass
class Reading:
    inputs: list = field(default_factory=list)  # validated StudentInputs, in the student's order
    decisions: list = field(default_factory=list)  # for each input: the decision number a choice answers (1 = now)
    note: str = ""
    error: str | None = None  # set when the helper couldn't be reached or gave nothing usable
    usage: dict = field(default_factory=dict)
    seconds: float = 0.0
    raw: list = field(default_factory=list)  # the inputs as the model returned them (for evals)


def request(session, text: str) -> dict:
    """The keyword arguments for client.beta.messages.create."""
    user = f"{context(session)}\n\nThe student's message:\n<message>\n{text[:MAX_TEXT]}\n</message>"
    return dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": user}],
    )


def _usage(resp) -> dict:
    u = getattr(resp, "usage", None)
    if u is None:
        return {}
    out = {k: getattr(u, k, 0) or 0 for k in
           ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
    out["cost_usd"] = cost(out)
    return out


def cost(u: dict) -> float:
    return (u.get("input_tokens", 0) * PRICE["input"] + u.get("output_tokens", 0) * PRICE["output"]
            + u.get("cache_creation_input_tokens", 0) * PRICE["cache_write"]
            + u.get("cache_read_input_tokens", 0) * PRICE["cache_read"]) / 1e6


def _final_text(resp) -> str:
    """The JSON text: text blocks after the last fallback switch point, if the server fell back."""
    blocks = list(resp.content or [])
    last = max((i for i, b in enumerate(blocks) if getattr(b, "type", "") == "fallback"), default=-1)
    return "".join(b.text for b in blocks[last + 1:] if getattr(b, "type", "") == "text")


def to_input(raw: dict):
    """One model-returned input → (a validated StudentInput, the decision number for a choice or None).
    Numbers come back as plain strings; the models wrap them as Number({"text": ...}) and pairs as tuples."""
    d = dict(raw)
    kind = d.get("kind")
    n = lambda v: {"text": str(v)}
    decision = None
    if kind in ("arithmetic", "function"):
        d["left"], d["right"] = n(d["left"]), n(d["right"])
        if d.get("result") is None:
            d.pop("result", None)
        else:
            d["result"] = n(d["result"])
    elif kind == "compare":
        d["left"], d["right"] = n(d["left"]), n(d["right"])
    elif kind == "ratio_compare":
        d["left"], d["right"] = (tuple(n(x) for x in d["left"]), tuple(n(x) for x in d["right"]))
    elif kind == "plot":
        d["points"] = [tuple(n(x) for x in p) for p in d["points"]]
    elif kind == "value":
        d["value"] = n(d["value"])
    elif kind == "choice":
        decision = int(d.pop("decision", 1) or 1)
    return TYPED.validate_python(d), decision


def interpret(session, text: str, client=None) -> Reading:
    """Ask Claude to read the message. Never raises for API trouble: returns a Reading with `error` set."""
    return call(request(session, text), client)


def call(req: dict, client=None) -> Reading:
    """Send a request built by request(). Split from interpret() so the web route can build the request while it
    holds the session lock and wait for the model without it."""
    import anthropic

    t0 = time.monotonic()
    try:
        client = client or get_client()
        resp = client.beta.messages.create(**req)
    except anthropic.AuthenticationError:
        return Reading(note=UNREACHABLE, error="authentication")
    except anthropic.RateLimitError:
        return Reading(note=UNREACHABLE, error="rate_limited")
    except anthropic.APIStatusError as e:
        return Reading(note=UNREACHABLE, error=f"api_status_{e.status_code}")
    except anthropic.APIConnectionError:  # includes timeouts
        return Reading(note=UNREACHABLE, error="connection")
    except anthropic.AnthropicError:  # e.g. no credentials at all
        return Reading(note=UNREACHABLE, error="client")
    except Exception:  # anything else from the client or the network stack: the generic note, never a 500
        return Reading(note=UNREACHABLE, error="unexpected")
    seconds = time.monotonic() - t0
    usage = _usage(resp)
    if resp.stop_reason == "refusal":
        return Reading(note="I couldn't read that one. Try saying your step another way, or type it.",
                       error="refusal", usage=usage, seconds=seconds)
    if resp.stop_reason == "max_tokens":
        return Reading(note="I couldn't read that one. Try saying one step at a time.", error="max_tokens",
                       usage=usage, seconds=seconds)
    try:
        data = json.loads(_final_text(resp))
        raw = list(data.get("inputs") or [])
        note = str(data.get("note") or "")
    except (json.JSONDecodeError, AttributeError, TypeError):
        return Reading(note=UNREACHABLE, error="bad_json", usage=usage, seconds=seconds)
    inputs, decisions = [], []
    for r in raw:  # keep the inputs up to the first one that doesn't validate
        try:
            inp, dec = to_input(r)
        except (ValidationError, TypeError, ValueError, KeyError):
            break
        inputs.append(inp)
        decisions.append(dec)
    if raw and not inputs:
        note = note or "I couldn't turn that into a step. Which numbers are you working with?"
    return Reading(inputs=inputs, decisions=decisions, note=note if not inputs else "", usage=usage,
                   seconds=seconds, raw=raw)


# ---------------------------------------------------------------- feeding the session

def describe(session, inp, di=None) -> str:
    """How an input reads back to the student. A choice reads as its option's text: decision `di`'s options while
    reading the story, else the current ask's."""
    if inp.kind == "choice":
        if di is not None and isinstance(session, WordProblemSession):
            opts = [session.wp["extract"][di]["options"][j]["say"] for j in session.order[di]]
        else:
            opts = session.ask().get("options") or []
        return opts[inp.index - 1] if 1 <= inp.index <= len(opts) else f"option {inp.index}"
    if inp.kind == "value":
        return f"the answer is {inp.value}"
    return written(inp)


def decision_ids(session) -> list[int]:
    """The decisions as the request numbers them (1 = being asked now, then the other open ones): decision index of
    each number. Taken when the request is built, so a reply is resolved by the decisions it was shown, even if the
    session moved on while Claude was reading."""
    if not (isinstance(session, WordProblemSession) and session.phase == "extract"):
        return []
    return list(_remaining_decisions(session))


def _decision_ids(session, decisions, ids=None):
    """Map the model's decision numbers to the word problem's decision indexes, through `ids` (decision_ids() at
    request time; now, if not given)."""
    if not (isinstance(session, WordProblemSession) and session.phase == "extract"):
        return [None] * len(decisions)
    rest = decision_ids(session) if ids is None else ids
    return [rest[d - 1] if d is not None and 1 <= d <= len(rest) else None for d in decisions]


def feed(session, inputs, decisions=None, ids=None) -> tuple[list[Feedback], list[str], list[bool]]:
    """Submit the inputs in order, stopping after the first one the session doesn't accept.

    While the story is being read, a choice answers the decision it names (any open one: the graph lets the
    decisions be taken in any order). A choice for a decision that is settled, or that isn't listed, isn't
    submitted, and the student is told. Returns (all feedback, the readable form of every input, whether the
    session was given each one)."""
    reading = isinstance(session, WordProblemSession) and session.phase == "extract"
    dis = _decision_ids(session, decisions or [None] * len(inputs), ids)
    out = []
    shown = [describe(session, inp, di) for inp, di in zip(inputs, dis)]
    checked = [False] * len(inputs)
    for k, (inp, di, d) in enumerate(zip(inputs, dis, decisions or [None] * len(inputs))):
        if session.phase == "done":
            break
        if inp.kind == "choice" and reading and session.phase == "extract":
            if d is not None and di is None:
                out.append(Feedback(kind="error", message=f"I couldn't tell which decision “{shown[k]}” answers. "
                                                          "Pick it from the options."))
                continue
            if di is not None and di in session.decided:
                out.append(Feedback(kind="info", message=f"That decision is settled already, so I left out “{shown[k]}”."))
                continue
            if di is not None:
                inp = inp.model_copy(update={"decision": di})
        elif inp.kind == "choice" and reading:  # the decisions are done; a leftover choice has nothing to answer
            out.append(Feedback(kind="info", message=f"The story is read already, so I left out “{shown[k]}”."))
            continue
        fb = session.submit_input(inp)
        checked[k] = True
        out += fb
        if not any(f.kind in ACCEPTED for f in fb):
            break
    return out, shown, checked


def say(session, text: str, client=None) -> dict:
    """Interpret a message and feed it to the session: {feedback, interpreted, checked, note, error}."""
    ids = decision_ids(session)
    reading = interpret(session, text, client)
    feedback, shown, checked = feed(session, reading.inputs, reading.decisions, ids) if reading.inputs else ([], [], [])
    return {"feedback": feedback, "interpreted": shown, "checked": checked, "note": reading.note,
            "error": reading.error}
