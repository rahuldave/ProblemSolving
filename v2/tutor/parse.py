"""Turn what a student types into a typed StudentInput.

    4 x 18 = 72      4*18      72 / 6 = 12      2/3 × 18 = 12      12 - 4 = 8
    gcf(6, 8) = 2    lcm 4 7 = 28
    21 > 20          0.75 < 5/7       3:4 ≠ 5:7
    plot (3, 4) (5, 7)
    2                (a choice, when options are listed; otherwise a final answer)
"""

import re

from pydantic import TypeAdapter, ValidationError

from .models import StudentInput

NUM = r"(?:\d+(?:\.\d+)?|\.\d+)(?:/(?:\d+(?:\.\d+)?))?"  # a fraction is written without spaces: 2/3
OPS = {"×": "multiply", "x": "multiply", "*": "multiply", "+": "add", "−": "subtract", "-": "subtract",
       "÷": "divide", "/": "divide"}
ADAPTER = TypeAdapter(StudentInput)

HELP = ("Write one step, like `4 x 18 = 72`, `72 / 6 = 12`, `gcf(6, 8) = 2`, `lcm(4, 7) = 28`, `21 > 20` or "
        "`plot (3, 4) (5, 7)`; or a number to pick an option.")


class ParseError(ValueError):
    pass


def _num(s):
    return {"text": re.sub(r"\s+", "", s)}


def _split_binary(expr):
    """Split `a op b`, where a and b may be fractions like 2/3. A slash is the operator only if nothing else is;
    a slash with spaces around it (40 / 5/3) is preferred over one without."""
    expr = expr.strip().lower()
    for i, ch in enumerate(expr):
        if ch in OPS and ch != "/" and i > 0:
            left, right = expr[:i].strip(), expr[i + 1:].strip()
            if re.fullmatch(NUM, left) and re.fullmatch(NUM, right):
                return OPS[ch], left, right
    spaced = [m.start() for m in re.finditer(r"\s/\s", expr)]
    positions = [i + 1 for i in spaced] + [i for i, ch in enumerate(expr) if ch == "/" and i + 1 not in spaced]
    for i in positions:
        left, right = expr[:i].strip(), expr[i + 1:].strip()
        if re.fullmatch(NUM, left) and re.fullmatch(NUM, right):
            return "divide", left, right
    return None


def parse_all(text: str, choices: int = 0):
    """Every reading of the text, most likely first. `4/3 = 4/3` reads as a division and as a comparison."""
    t = text.strip().lower().replace("$", "").replace(",", " ").replace("!=", "≠").replace("<>", "≠")
    if not t:
        raise ParseError(HELP)
    out = []
    try:
        if re.fullmatch(r"\d+", t) and choices:
            out.append({"kind": "choice", "index": int(t)})
        elif re.fullmatch(NUM, t):
            out.append({"kind": "value", "value": _num(t)})
        if t.startswith("plot"):
            pts = re.findall(rf"\(\s*({NUM})\s*[ ,]\s*({NUM})\s*\)", t)
            if not pts:
                raise ParseError("Write points like `plot (3, 4) (5, 7)`.")
            out.append({"kind": "plot", "points": [(_num(a), _num(b)) for a, b in pts]})
        m = re.fullmatch(rf"(gcf|gcd|hcf|lcm)\s*\(?\s*({NUM})\s*[ ,]\s*({NUM})\s*\)?\s*(?:=\s*({NUM}))?", t)
        if m:
            data = {"kind": "function", "name": "lcm" if m[1] == "lcm" else "gcf", "left": _num(m[2]), "right": _num(m[3])}
            if m[4]:
                data["result"] = _num(m[4])
            out.append(data)
        m = re.fullmatch(r"(\d+)\s*:\s*(\d+)\s*(=|≠)\s*(\d+)\s*:\s*(\d+)", t)
        if m:
            out.append({"kind": "ratio_compare", "left": (_num(m[1]), _num(m[2])), "relation": m[3],
                        "right": (_num(m[4]), _num(m[5]))})
        lhs, _, rhs = t.partition("=")
        split = _split_binary(lhs)
        if split and (not rhs or re.fullmatch(NUM, rhs.strip())):  # 72 / 6 = 12 reads first as a division
            op, a, b = split
            data = {"kind": "arithmetic", "op": op, "left": _num(a), "right": _num(b)}
            if rhs.strip():
                data["result"] = _num(rhs)
            out.append(data)
        m = re.fullmatch(rf"({NUM})\s*(<|>|=)\s*({NUM})", t)
        if m:
            out.append({"kind": "compare", "left": _num(m[1]), "relation": m[2], "right": _num(m[3])})
        readings = [ADAPTER.validate_python(d) for d in out]
    except ValidationError as e:
        raise ParseError(f"I couldn't read that: {e.errors()[0]['msg']}. {HELP}") from e
    if not readings:
        raise ParseError(f"I couldn't read “{text.strip()}”. {HELP}")
    return readings


def parse(text: str, choices: int = 0):
    """The most likely reading of the text, as a validated StudentInput. `choices` is how many options are on offer."""
    return parse_all(text, choices)[0]
