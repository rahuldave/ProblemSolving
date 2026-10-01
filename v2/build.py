"""Build v2: expand skills, `all` blocks and reductions; check every method and word problem; derive first-step
trees for a classifier (trees/); draw every diagram in one graph grammar with a legend (svg/); write the markdown
pages (graphs/, ../REPORT.md) and the website (../docs/).

Usage: python3 build.py             # validate, generate trees, markdown, svg graphs (mmdc), website (quarto)
       python3 build.py --demo      # also run the student-step classifier demo
       python3 build.py --no-site   # skip the Quarto website
"""

import hashlib
import itertools
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).parent
VOCAB = json.loads((ROOT / "vocabulary.json").read_text())
EXTRACTION = json.loads((ROOT / "extraction.json").read_text())
Q = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "questions").glob("*.json"))}
WP = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "word-problems").glob("*.json"))}
OPERATION = VOCAB["classification"]["levels"][0]["from_op"]
COMMUTATIVE = {"add", "multiply", "gcf", "lcm", "plot"}
SYMBOL = {"add": "+", "subtract": "−", "multiply": "×", "divide": "÷"}
BOOKKEEPING = {"map", "init", "pick"}


class NotApplicable(Exception):
    pass


# ================================================================ methods

_methods_cache = {}


def methods_of(qid):
    """Method id → method. An applied question's reductions become methods that `use` the core question."""
    if qid in _methods_cache:
        return _methods_cache[qid]
    q = Q[qid]
    out = {}
    red = q.get("reduces_to")
    if red:
        core = Q[red["question"]]
        chosen = red["methods"]
        for cid in (core["methods"] if chosen == "all" else chosen):
            over = {} if chosen == "all" else chosen[cid]
            cm = core["methods"][cid]
            target = "core_answer" if red.get("answer_map") else "answer"
            steps = [{"op": "use", "question": red["question"], "method": cid, "with": red["with"],
                      "out": {"answer": target}, "say": red.get("say", "")}]
            if red.get("answer_map"):
                steps.append({"op": "map", "args": ["core_answer"], "out": "answer", "table": red["answer_map"], "hidden": True})
            m = {k: v for k, v in cm.items() if k != "steps"}
            m.update({k: over[k] for k in ("name", "idea") if k in over})
            m.update(steps=steps, core_method=cid, display_level=1)
            out[over.get("id", cid)] = m
    for mid, m in q.get("methods", {}).items():
        out[mid] = {**m, "display_level": 0}
    _methods_cache[qid] = out
    return out


def default_method(qid):
    return Q[qid].get("default_method") or next(iter(methods_of(qid)))


def method_items(qid, mid):
    """The steps to draw for a method: an applied method is drawn as its core method."""
    m = methods_of(qid)[mid]
    if m["display_level"] == 0:
        return m["steps"]
    return Q[Q[qid]["reduces_to"]["question"]]["methods"][m["core_method"]]["steps"]


# ================================================================ expansion
# A variant is one way through a method: every `use` replaced by one of the callee's methods and every `all` block
# put in one order. Each flat step carries `loc`: a tuple of frames (question, method, index path), one frame per
# call level, so a step can be traced back to the structure it came from.

def local(name, rename, prefix):
    if isinstance(name, list):
        return [local(n, rename, prefix) for n in name]
    if not isinstance(name, str):
        return name
    return rename.get(name, prefix + name)


def rename_text(text, rename, prefix):
    return re.sub(r"\{([^{}]+)\}", lambda m: "{" + str(local(m[1], rename, prefix)) + "}", text or "")


def rename_step(step, rename, prefix, loc):
    L = lambda n: local(n, rename, prefix)
    new = dict(step, loc=loc)
    for key in ("args", "out"):
        if key in step:
            new[key] = L(step[key])
    if "search" in step:
        s = dict(step["search"], var=L(step["search"]["var"]))
        for key in ("until", "until_divisible_by", "until_power_of_ten"):
            if key in s:
                s[key] = L(s[key])
        new["search"] = s
    if step["op"] == "repeat":
        new["init"] = {L(k): L(v) for k, v in step["init"].items()}
        new["choose"] = dict(step["choose"], var=L(step["choose"]["var"]), of=L(step["choose"]["of"]))
        new["steps"] = [rename_step(s, rename, prefix, loc) for s in step["steps"]]
    if "say" in step:
        new["say"] = rename_text(step["say"], rename, prefix)
    return new


def expand(qid, forced, rename, prefix, loc, stack, defaults_only):
    """Yield (method id, flat steps, calls) for every combination of choices inside the question."""
    methods = methods_of(qid)
    default = default_method(qid)
    if forced:
        ids = [forced if forced in methods else next(k for k, m in methods.items() if m.get("core_method") == forced)]
    elif defaults_only:
        ids = [default]
    else:
        ids = sorted(methods, key=lambda m: m != default)
    for mid in ids:
        for steps, calls in expand_items(qid, mid, methods[mid]["steps"], rename, f"{prefix}{mid}.", loc, (),
                                         stack + [qid], defaults_only):
            yield mid, steps, calls


def expand_items(qid, mid, items, rename, prefix, loc, ip0, stack, defaults_only):
    partials = [([], [])]
    for i, item in enumerate(items):
        ip = ip0 + (i,)
        here = loc + ((qid, mid, ip),)
        if item["op"] == "use":
            child = item["question"]
            cwith = {k: local(v, rename, prefix) for k, v in item["with"].items()}
            couts = {k: local(v, rename, prefix) for k, v in item["out"].items()}
            call = {"loc": here, "question": child, "with": cwith, "out": couts,
                    "say": rename_text(item.get("say"), rename, prefix)}
            cprefix = f"{prefix}{'.'.join(map(str, ip))}:"
            options = [(s, [call] + c) for _, s, c in expand(child, item.get("method"), {**cwith, **couts}, cprefix,
                                                            here, stack, defaults_only or child in stack)]
        elif item["op"] == "all":
            alts = [expand_items(qid, mid, br, rename, prefix, loc, ip + (b,), stack, defaults_only)
                    for b, br in enumerate(item["branches"])]
            options = []
            for order in itertools.permutations(range(len(alts))):
                for combo in itertools.product(*(alts[b] for b in order)):
                    options.append((sum((c[0] for c in combo), []), sum((c[1] for c in combo), [])))
        else:
            options = [([rename_step(item, rename, prefix, here)], [])]
        partials = [(s + s2, c + c2) for s, c in partials for s2, c2 in options]
    return partials


_variants_cache = {}


def variants_of(qid):
    if qid not in _variants_cache:
        q = Q[qid]
        rename = {k: k for k in list(q["inputs"]) + q["outputs"]}
        _variants_cache[qid] = [{"method": mid, "steps": steps, "calls": calls}
                                for mid, steps, calls in expand(qid, None, rename, "", (), [], False)]
    return _variants_cache[qid]


# ================================================================ evaluation

def num(v):
    return Fraction(str(v))


def val(arg, env):
    if isinstance(arg, list):
        return tuple(val(a, env) for a in arg)
    if isinstance(arg, (int, float)):
        return Fraction(arg)
    return env[arg]


def whole(*xs):
    if any(not isinstance(x, Fraction) or x.denominator != 1 for x in xs):
        raise NotApplicable("needs whole numbers")
    return [int(x) for x in xs]


def apply_op(op, x, y):
    if op == "add":
        return x + y
    if op == "subtract":
        return x - y
    if op == "multiply":
        return x * y
    if op == "divide":
        if y == 0:
            raise NotApplicable("division by zero")
        return x / y
    a, b = whole(x, y)
    return Fraction({"gcf": math.gcd(a, b), "lcm": math.lcm(a, b), "floor_div": a // b, "mod": a % b}[op])


def smallest_common_prime(x, y):
    g = math.gcd(*whole(x, y))
    return next((p for p in range(2, g + 1) if g % p == 0), None)


def run(steps, values):
    env = {k: num(v) for k, v in values.items()}
    trace = []
    for st in steps:
        exec_step(st, env, trace)
    env.pop("__trivial__", None)
    return env, trace


def exec_step(st, env, trace):
    """Run one flat step, appending (step, argument values, result) to the trace."""
    op = st["op"]
    if op == "plot":
        trace.append((st, [val(a, env) for a in st["args"]], None))
        return
    if op == "repeat":
        for k, v in st["init"].items():
            env[k] = val(v, env)
        trace.append(({"op": "init", "init": st["init"], "loc": st.get("loc", ())}, None, None))
        ch = st["choose"]
        if smallest_common_prime(*(val(a, env) for a in ch["of"])) is None:
            raise NotApplicable("already in lowest terms; nothing to divide out")
        while (f := smallest_common_prime(*(val(a, env) for a in ch["of"]))) is not None:
            env[ch["var"]] = Fraction(f)
            trace.append(({"op": "pick", **ch, "loc": st.get("loc", ())}, None, f))
            for sub in st["steps"]:
                exec_step(sub, env, trace)
        return
    if op == "map":
        env[st["out"]] = st["table"].get(env[st["args"][0]], env[st["args"][0]])
        trace.append((st, None, env[st["out"]]))
        return
    if op == "compare":
        x, y = (val(a, env) for a in st["args"])
        rel = "=" if x == y else ("≠" if isinstance(x, tuple) else ("<" if x < y else ">"))
        env[st["out"]] = st["meaning"].get(rel) or st["meaning"]["≠"]
        trace.append((st, [x, y], rel))
        return
    if "search" in st:
        s, var = st["search"], st["search"]["var"]
        base = val(next(a for a in st["args"] if a != var), env)
        k = None
        if "until" in s:
            k = val(s["until"][1], env) / base
        elif "until_power_of_ten" in s:
            k = next((Fraction(10 ** n) / base for n in range(1, 16) if (Fraction(10 ** n) / base).denominator == 1), None)
        elif "until_divisible_by" in s:
            b, dv = whole(base, val(s["until_divisible_by"][1], env))
            k = Fraction(dv // math.gcd(b, dv))
        if k is None or k.denominator != 1 or k < 1:
            raise NotApplicable(f"no whole-number {var.split('.')[-1]} works")
        env[var] = k
        if k == 1:  # a search that lands on × 1 is a non-step
            env.setdefault("__trivial__", set()).add(var)
            st = dict(st, hidden=True)
    if set(a for a in st.get("args", []) if isinstance(a, str)) & env.get("__trivial__", set()):
        st = dict(st, hidden=True)
    x, y = (val(a, env) for a in st["args"])
    result = apply_op(op, x, y)
    if st.get("requires_nonnegative") and result < 0:
        raise NotApplicable(f"{result} is negative")
    if st.get("requires_integer") and result.denominator != 1:
        raise NotApplicable(f"{result} is not whole")
    env[st["out"]] = result
    trace.append((st, [x, y], result))


def visible(st):
    return not st.get("hidden") and st["op"] not in BOOKKEEPING


def outputs_of(qid, env):
    outs = Q[qid]["outputs"]
    return env[outs[0]] if outs == ["answer"] else {o: env[o] for o in outs}


def answer_ok(got, expected, method):
    if isinstance(expected, dict):
        return all(answer_ok(got[k], v, method) for k, v in expected.items())
    if isinstance(got, str):
        return got == expected or (method.get("decides") == "equality_only" and got == "not equal"
                                   and expected in ("first", "second"))
    exp = num(expected)
    if method.get("answer_relation") == "multiple":
        return (got / exp).denominator == 1
    return got == exp


# ================================================================ first-step trees (for the classifier)

def signatures(steps, limit=2):
    """Symbolic form of the first `limit` visible steps, e.g. multiply(divide(a, b), d)."""
    sym, out = {}, []

    def S(a):
        if isinstance(a, list):
            return "(" + ", ".join(S(x) for x in a) + ")"
        if not isinstance(a, str):
            return str(a)
        return sym.get(a, a)

    for st in steps:
        if len(out) >= limit:
            break
        op = st["op"]
        if op == "init":
            sym.update({k: S(v) for k, v in st["init"].items()})
            continue
        if op == "pick":
            sym[st["var"]] = f"common_factor({', '.join(S(a) for a in st['of'])})"
            continue
        if op == "repeat":  # static walk: one round of the loop
            out += signatures([{"op": "init", "init": st["init"]}, {"op": "pick", **st["choose"]}] + st["steps"],
                              limit - len(out))
            continue
        if "search" in st:
            sym[st["search"]["var"]] = "int"
        args = [S(a) for a in st.get("args", [])]
        if op in COMMUTATIVE:
            args = sorted(args)
        if "out" in st:
            sym[st["out"]] = f"{op}({', '.join(args)})"
        if visible(st):
            out.append({"op": op, "args": args, "step": st})
    return out


def key_of(sig):
    return f"{sig['op']}({', '.join(sig['args'])})"


def classify_sig(qid, sig):
    q = Q[qid]
    text = " ".join(sig["args"])
    operation = "factor" if "common_factor" in text else OPERATION.get(sig["op"], sig["op"])
    names = set(re.findall(r"[A-Za-z_]\w*", text)) & set(q["inputs"])
    groups = {g for g, members in q.get("quantities", {}).items() if names & set(members)}
    return {"operation": operation, "scope": "across" if len(groups) > 1 else "within"}


def context_of(st, depth):
    """The questions a flat step sits inside, below the drawn method (outermost first)."""
    return [Q[q]["title"] for q, _, _ in st.get("loc", ())[depth:]]


def build_tree(qid):
    methods = methods_of(qid)
    mental = {key_of({"op": m["op"], "args": sorted(m["args"]) if m["op"] in COMMUTATIVE else m["args"]})
              for m in Q[qid].get("mental_first_steps", [])}
    entries = {}

    def add(sig, nxt, v, is_mental):
        key = ("mental:" if is_mental else "") + key_of(sig)
        e = entries.setdefault(key, {"sig": sig, "mental": is_mental, "methods": {}, "next": {}})
        depth = methods[v["method"]]["display_level"] + 1
        e["methods"].setdefault(v["method"], set()).add(" › ".join(context_of(sig["step"], depth)))
        if nxt:
            n = e["next"].setdefault(key_of(nxt), {"sig": nxt, "methods": {}})
            n["methods"].setdefault(v["method"], set()).add(" › ".join(context_of(nxt["step"], depth)))

    for v in variants_of(qid):
        sigs = signatures(v["steps"])
        add(sigs[0], sigs[1] if len(sigs) > 1 else None, v, False)
        if len(sigs) > 1 and key_of(sigs[0]) in mental:
            add(sigs[1], None, v, True)

    def node(e, top):
        names = sorted(e["methods"])
        out = {"match": {"op": e["sig"]["op"], "args": e["sig"]["args"]}}
        if top:
            out["class"] = classify_sig(qid, e["sig"])
        out["methods"] = names
        ctx = {m: sorted(x for x in e["methods"][m] if x) for m in names if any(e["methods"][m])}
        if ctx:
            out["inside"] = ctx
        if top and e["mental"]:
            out["mental"] = True
            out["feedback"] = "The student did the conversion in their head first."
        elif len(names) == 1:
            out["feedback"] = f"This starts: {methods[names[0]]['name']}."
        else:
            out["feedback"] = "This step starts several methods: " + ", ".join(methods[n]["name"] for n in names) + "."
        if top and len(names) > 1 and e["next"]:
            out["next"] = [node(n, False) for n in sorted(e["next"].values(), key=lambda n: key_of(n["sig"]))]
        if not top and len(names) > 1:
            out["note"] = "Same first two steps; ask the student what they plan to do next."
        return out

    order = sorted(entries.values(), key=lambda e: (e["mental"], *classify_sig(qid, e["sig"]).values(), key_of(e["sig"])))
    return {"question": qid, "generated_by": "build.py", "first_steps": [node(e, True) for e in order]}


# ================================================================ labels

def terminates(v):
    d = v.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    return d == 1


def fmt(v):
    if isinstance(v, str):
        return v
    if isinstance(v, tuple):
        return ":".join(fmt(x) for x in v)
    if v.denominator == 1:
        return str(v.numerator)
    if terminates(v):
        return format(Decimal(v.numerator) / Decimal(v.denominator), "f")
    return f"{v.numerator}/{v.denominator}"


def approx(v):
    return fmt(v) if not isinstance(v, Fraction) or terminates(v) else f"≈ {float(v):.3f}"


def expression(st, args, result):
    """The worked expression for a step: 4 × 18 = 72, GCF(6, 8) = 2, 21 > 20, (3, 4), (5, 7)."""
    op = st["op"]
    if op == "plot":
        return ", ".join(f"({fmt(x)}, {fmt(y)})" for x, y in args)
    if op == "compare":
        return f"{fmt(args[0])} {result} {fmt(args[1])}"
    if op in ("gcf", "lcm"):
        return f"{op.upper()}({fmt(args[0])}, {fmt(args[1])}) = {fmt(result)}"
    if op == "divide" and not terminates(result):
        return f"{fmt(args[0])} ÷ {fmt(args[1])} {approx(result)}"
    return f"{fmt(args[0])} {SYMBOL[op]} {fmt(args[1])} = {fmt(result)}"


def label_key(st, args, result):
    vals = tuple(map(fmt, args or []))
    return (st["op"], tuple(sorted(vals)) if st["op"] in COMMUTATIVE else vals, fmt(result) if result is not None else "")


def say(text, env):
    """Fill {name} placeholders in a sentence with values."""
    def one(m):
        name = m[1]
        if name in env:
            return fmt(env[name])
        return name if re.fullmatch(r"[\d.]+", name) else m[0]
    return re.sub(r"\{([^{}]+)\}", one, text or "")


def render(template, values):
    return re.sub(r"\{(\w+)\}", lambda m: fmt(num(values[m[1]])) if m[1] in values else m[0], template)


def step_lines(entry, env, tags=()):
    st, args, result = entry
    lines = [say(st.get("say"), env), expression(st, args, result)]
    return [l for l in lines if l] + [f"[{t}]" for t in tags if t]


def call_lines(call, env):
    child = Q[call["question"]]
    ins = {k: fmt(val(v, env)) for k, v in call["with"].items()}
    show_ = approx if child.get("output_format") == "decimal" else fmt
    outs = " and ".join(show_(env[v]) for v in call["out"].values())
    prompt = re.sub(r"\{(\w+)\}", lambda m: ins.get(m[1], m[0]), child["prompt"]).rstrip(".?")
    return [l for l in (say(call["say"], env), f"{prompt} → {outs}") if l]


# ================================================================ mermaid builder (the graph grammar)

CLASSDEFS = {
    "start": "fill:#fde4e1,stroke:#c4554a,color:#222",
    "end": "fill:#d4f0da,stroke:#2f8a45,color:#222,font-weight:bold",
    "step": "fill:#ffffff,stroke:#7a8599,color:#222",
    "first": "fill:#e3edfd,stroke:#5b7fd1,color:#222",
    "call": "fill:#e3f4e6,stroke:#3f9a55,color:#222",
    "choice": "fill:#fff1cc,stroke:#c99a1a,color:#222",
    "all": "fill:#efe6fb,stroke:#8b63c9,color:#222",
    "wrong": "fill:#ffffff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33",
    "skill": "fill:#e3f4e6,stroke:#3f9a55,color:#222",
    "core": "fill:#fff1cc,stroke:#c99a1a,color:#222",
    "applied": "fill:#e3edfd,stroke:#5b7fd1,color:#222",
}
SHAPES = {"start": ("([", "])"), "end": ("([", "])"), "wrong": ("([", "])"), "step": ("[", "]"), "first": ("[", "]"),
          "call": ("[[", "]]"), "choice": ("{{", "}}"), "all": ("{", "}"),
          "skill": ("[", "]"), "core": ("[", "]"), "applied": ("[", "]")}
ARROWS = {"seq": "-->", "option": "-->", "trap": "-.->", "data": "==>", "dotted": "-.->"}


def esc(s):
    # plain-text labels show entities literally, so use look-alike characters for < and >
    return str(s).replace('"', "#quot;").replace("<", "＜").replace(">", "＞")


class Mermaid:
    """Collects nodes, frames and edges, then writes one flowchart. Node kinds and edge kinds are the grammar."""

    def __init__(self, prefix="n"):
        self.prefix, self.count = prefix, itertools.count()
        self.nodes, self.edges, self.frames, self.seen = [], [], {}, set()

    def node(self, kind, lines, frame=None):
        nid = f"{self.prefix}{next(self.count)}"
        lines = [lines] if isinstance(lines, str) else lines
        self.nodes.append((nid, kind, "<br/>".join(esc(l) for l in lines), frame))
        return nid

    def frame(self, title, parent=None):
        fid = f"{self.prefix}f{len(self.frames)}"
        self.frames[fid] = (title, parent)
        return fid

    def edge(self, a, b, label=None, kind="seq"):
        lab = "<br/>".join(esc(l) for l in label) if isinstance(label, list) else (esc(label) if label else None)
        if (a, b, lab, kind) not in self.seen:
            self.seen.add((a, b, lab, kind))
            self.edges.append((a, b, lab, kind))

    def emit(self):
        out = ["flowchart LR"]

        def block(parent, indent):
            for nid, kind, text, fr in self.nodes:
                if fr == parent:
                    o, c = SHAPES[kind]
                    out.append(f'{indent}{nid}{o}"{text}"{c}')
            for fid, (title, par) in self.frames.items():
                if par == parent:
                    out.extend([f'{indent}subgraph {fid}["{esc(title)}"]', f"{indent}  direction LR"])
                    block(fid, indent + "  ")
                    out.append(f"{indent}end")

        block(None, "  ")
        for a, b, lab, kind in self.edges:
            out.append(f'  {a} {ARROWS[kind]}{f"|{chr(34)}{lab}{chr(34)}|" if lab else ""} {b}')
        for i, (_, _, _, kind) in enumerate(self.edges):
            if kind == "trap":
                out.append(f"  linkStyle {i} stroke:#c4554a,color:#c4554a")
            elif kind == "data":
                out.append(f"  linkStyle {i} stroke:#3f9a55,stroke-width:3px")
        used = sorted({k for _, k, _, _ in self.nodes})
        out += [f"  classDef k_{k} {CLASSDEFS[k]}" for k in used]  # prefixed: `call` is a mermaid keyword
        for k in used:
            out.append(f"  class {','.join(n for n, kind, _, _ in self.nodes if kind == k)} k_{k}")
        for fid in self.frames:
            out.append(f"  style {fid} fill:#fafafa,stroke:#b8bcc6")
        return "\n".join(out)


def draw_blocks(g, blocks, frame):
    """Draw a list of blocks (step, call, or all-of-branches) as a chain; returns (entry, exit) node ids."""
    entry = exit_ = None
    for b in blocks:
        if b[0] == "all":
            split, join = g.node("all", "all", frame), g.node("all", "all", frame)
            for br in b[1]:
                e, x = draw_blocks(g, br, frame)
                g.edge(split, e)
                g.edge(x, join)
            e, x = split, join
        else:
            e = x = g.node(b[0], b[1], frame)
        if exit_:
            g.edge(exit_, e)
        else:
            entry = e
        exit_ = x
    return entry, exit_


# ================================================================ question graphs

def routes_for(qid, values):
    """Every way through the question that works for these values: (variant, env, trace, visible indexes)."""
    routes, applicable = [], set()
    for v in variants_of(qid):
        try:
            env, trace = run(v["steps"], values)
        except (NotApplicable, KeyError):
            continue
        vis = [i for i, t in enumerate(trace) if visible(t[0])]
        if vis:
            routes.append((v, env, trace, vis))
            applicable.add(v["method"])
    return routes, applicable


def rest_blocks(qid, route, consumed):
    """What is left of a route's method after its first `consumed` visible steps, in the method's own structure:
    calls not yet started stay collapsed, a call already started is walked through its own method, and `all`
    branches not yet started stay an all-block."""
    v, env, trace, vis = route
    d = methods_of(qid)[v["method"]]["display_level"]
    upto = vis[consumed - 1]
    calls = {tuple(c["loc"]): c for c in v["calls"]}
    where = [t[0].get("loc", ()) for t in trace]

    def walk(items, ip0, depth, base):
        def inside(t, ip):
            w = where[t]
            return len(w) > depth and w[:depth] == base and w[depth][2][:len(ip)] == ip

        blocks = []
        for i, item in enumerate(items):
            ip = ip0 + (i,)
            idxs = [t for t in range(len(trace)) if inside(t, ip)]
            if not idxs:
                continue
            if item["op"] == "all":
                seq, untouched = [], []
                for b, br in enumerate(item["branches"]):
                    bidx = [t for t in idxs if where[t][depth][2][len(ip)] == b]
                    if not bidx or max(bidx) <= upto:
                        continue
                    sub = walk(br, ip + (b,), depth, base)
                    if min(bidx) <= upto:
                        seq += sub
                    elif sub:
                        untouched.append(sub)
                blocks += seq + (untouched[0] if len(untouched) == 1 else [("all", untouched)] if untouched else [])
            elif item["op"] == "use":
                frame = where[idxs[0]][depth]
                if idxs[0] > upto:
                    blocks.append(("call", call_lines(calls[base + (frame,)], env)))
                elif max(idxs) > upto:
                    child, cmid, _ = where[idxs[0]][depth + 1]
                    blocks += walk(methods_of(child)[cmid]["steps"], (), depth + 1, base + (frame,))
            else:
                tag = ["in: " + " › ".join(context_of(trace[idxs[0]][0], d + 1))] if depth > d else []
                blocks += [("step", step_lines(trace[t], env, tag)) for t in idxs if t > upto and visible(trace[t][0])]
        return blocks

    base = next(w[:d] for w in where if len(w) > d)
    return walk(method_items(qid, v["method"]), (), d, base)


def question_graph(g, qid, values, answer_label, frame=None):
    """Draw a question with these values into g: start → × which first step? → first steps (merged across methods)
    → × which next step? where methods share a first step → the rest of each method → the answer.
    Returns (start, end, methods that don't apply)."""
    q, methods = Q[qid], methods_of(qid)
    routes, applicable = routes_for(qid, values)
    mental = {key_of({"op": m["op"], "args": m["args"]}) for m in q.get("mental_first_steps", [])}
    start = g.node("start", render(q["prompt"], values), frame)
    end = g.node("end", answer_label, frame)
    first_choice = g.node("choice", "× Which first step?", frame)
    g.edge(start, first_choice)
    continuation = {}

    def attach(src, route, consumed, label=None, kind="seq"):
        blocks = rest_blocks(qid, route, consumed)
        key = (route[0]["method"], repr(blocks))
        if key not in continuation:
            entry, exit_ = draw_blocks(g, blocks, frame)
            if entry:
                g.edge(exit_, end)
            continuation[key] = entry or end
        g.edge(src, continuation[key], label, kind)

    groups = {}
    for r in routes:
        v, env, trace, vis = r
        sig = signatures([t[0] for t in trace], 1)[0]
        entries = [(vis[0], 1, None)]
        if len(vis) > 1 and key_of(sig) in mental:
            entries.append((vis[1], 2, expression(*trace[vis[0]])))
        for idx, consumed, after in entries:
            key = (label_key(*trace[idx]), after)
            depth = methods[v["method"]]["display_level"] + 1
            gr = groups.setdefault(key, {"routes": [], "methods": set(), "entry": trace[idx], "env": env,
                                         "consumed": consumed, "after": after, "cls": classify_sig(qid, sig),
                                         "inside": context_of(trace[idx][0], depth)})
            gr["routes"].append(r)
            gr["methods"].add(v["method"])

    for (key, after), gr in sorted(groups.items(), key=lambda kv: (kv[1]["after"] is not None, kv[1]["cls"]["operation"],
                                                                  kv[1]["cls"]["scope"], str(kv[0]))):
        names = [methods[m]["name"] for m in sorted(gr["methods"])]
        tags = [f"{gr['cls']['operation']} · {gr['cls']['scope']}"] + (["in: " + " › ".join(gr["inside"])] if gr["inside"] else [])
        fn = g.node("first", step_lines(gr["entry"], gr["env"], tags), frame)
        g.edge(first_choice, fn, " or ".join(names) + (f" (after {after} in their head)" if after else ""), "option")
        if len(gr["methods"]) == 1:
            for r in gr["routes"]:
                attach(fn, r, gr["consumed"])
            continue
        nxt = g.node("choice", "× Which next step?", frame)
        g.edge(fn, nxt)
        seconds = {}
        for r in gr["routes"]:
            v, env, trace, vis = r
            if len(vis) > gr["consumed"]:
                e = trace[vis[gr["consumed"]]]
                s = seconds.setdefault(label_key(*e), {"routes": [], "methods": set(), "entry": e, "env": env})
            else:
                s = seconds.setdefault(None, {"routes": [], "methods": set()})
            s["routes"].append(r)
            s["methods"].add(v["method"])
        for k2, s in seconds.items():
            names2 = [methods[m]["name"] for m in sorted(s["methods"])]
            if k2 is None:
                for m in sorted(s["methods"]):
                    g.edge(nxt, end, methods[m]["name"], "option")
                continue
            depth = methods[s["routes"][0][0]["method"]]["display_level"] + 1
            inside = context_of(s["entry"][0], depth)
            sn = g.node("step", step_lines(s["entry"], s["env"], ["in: " + " › ".join(inside)] if inside else []), frame)
            g.edge(nxt, sn, " or ".join(names2), "option")
            if len(s["methods"]) == 1:
                for r in s["routes"]:
                    attach(sn, r, gr["consumed"] + 1)
            else:
                mc = g.node("choice", "× Which method?", frame)
                g.edge(sn, mc)
                for m in sorted(s["methods"]):
                    r = next(r for r in s["routes"] if r[0]["method"] == m)
                    attach(mc, r, gr["consumed"] + 1, methods[m]["name"], "option")
    return start, end, sorted(set(methods) - applicable)


def example_graph(qid, ex):
    g = Mermaid()
    ans = ex["answer"]
    shown = "/".join(map(str, ans.values())) if isinstance(ans, dict) else ans
    _, _, na = question_graph(g, qid, ex["values"], f"Answer: {shown}")
    return g.emit(), na


# ================================================================ legends

def legend_question():
    g = Mermaid("L")
    f = g.frame("Legend")
    a = g.node("start", "Start: the question", f)
    b = g.node("choice", "× Choice: pick one way", f)
    c = g.node("first", ["First step: the sentence", "the worked expression", "[operation · scope]"], f)
    d = g.node("all", "all", f)
    e = g.node("call", ["Call: another question", "inputs → its result"], f)
    h = g.node("step", ["Step: the sentence", "the worked expression", "[in: question it sits inside]"], f)
    j = g.node("all", "all", f)
    k = g.node("end", "End: the answer", f)
    g.edge(a, b, "then")
    g.edge(b, c, "option: the method it leads to", "option")
    g.edge(c, d)
    g.edge(d, e, "all branches, any order")
    g.edge(d, h)
    g.edge(e, j)
    g.edge(h, j)
    g.edge(j, k, "then")
    return g.emit()


def legend_word():
    g = Mermaid("L")
    f = g.frame("Legend")
    s = g.node("start", "Start: the story", f)
    d = g.node("all", "all", f)
    c = g.node("choice", "× Decision", f)
    st = g.node("step", ["Decision without traps", "the answer"], f)
    j = g.node("all", "all", f)
    t = g.node("call", ["Call: the question with the wrong numbers", "→ its result"], f)
    w = g.node("wrong", ["wrong answer ✗", "gives itself away: first step"], f)
    q = g.node("start", "Question with the extracted numbers", f)
    ch = g.node("choice", "× Which first step?", f)
    fs = g.node("first", ["First step", "worked expression", "[operation · scope]"], f)
    e = g.node("end", "Answer, then in the story's terms", f)
    g.edge(s, d)
    g.edge(d, c, "decide all, any order")
    g.edge(d, st)
    g.edge(c, j, "✓ the correct reading", "option")
    g.edge(st, j)
    g.edge(c, t, "✗ concept: a wrong reading", "trap")
    g.edge(t, w)
    g.edge(j, q, ["data: the values passed in", "a: 4 spoons of sugar"], "data")
    g.edge(q, ch)
    g.edge(ch, fs, "option: the method", "option")
    g.edge(fs, e, "then …")
    return g.emit()


def legend_index():
    g = Mermaid("L")
    f = g.frame("Legend")
    s = g.node("skill", "Skill", f)
    c = g.node("core", "Core question", f)
    a = g.node("applied", "Applied question", f)
    g.edge(c, s, "a method uses it as a step")
    g.edge(a, c, "is a (in context)", "dotted")
    return g.emit()


LEGENDS = {"question": legend_question, "word": legend_word, "index": legend_index}


# ================================================================ word problems

def option_effects(plan, o):
    if "question" in o:
        plan["question"] = o["question"]
    plan["binds"].update(o.get("binds", {}))
    plan["steps"] = plan["steps"] + o.get("steps", [])
    for key in ("then", "answer_map", "answer"):
        if key in o:
            plan[key] = o[key]


def wp_plan(wp, trap=None):
    """The correct reading: every decision's correct option. A trap swaps in one wrong option on top of it."""
    plan = {"question": None, "binds": {}, "steps": [], "then": [], "answer_map": None, "answer": None}
    for dec in wp["extract"]:
        option_effects(plan, next(o for o in dec["options"] if o.get("correct")))
    if trap:
        option_effects(plan, trap)
    return plan


def solve(qid, values, main_route_only=False):
    """The answer from the first route that applies (defaults first), plus the first steps a solver could write:
    from every route, or only each method's main route."""
    answer, firsts, seen = None, {}, set()
    for v in variants_of(qid):
        if main_route_only and v["method"] in seen:
            continue
        try:
            env, trace = run(v["steps"], values)
        except (NotApplicable, KeyError):
            continue
        seen.add(v["method"])
        if answer is None:
            answer = outputs_of(qid, env)
        vis = [t for t in trace if visible(t[0])]
        if vis:
            firsts.setdefault(label_key(*vis[0]), expression(*vis[0]))
    return answer, firsts


def wp_run(wp, plan, main_route_only=False):
    env = {q["id"]: num(q["value"]) for q in wp["quantities"]}
    before = []
    for st in plan["steps"]:
        exec_step(dict(st, loc=()), env, before)
    out = {"env": env, "before": before, "inputs": None, "result": None, "mapped": None, "firsts": {}, "after": []}
    if plan["answer"]:
        out["final"] = env[plan["answer"]]
        return out
    inputs = {k: val(e, env) for k, e in plan["binds"].items()}
    result, firsts = solve(plan["question"], inputs, main_route_only)
    mapped = (plan["answer_map"] or {}).get(result, result) if isinstance(result, str) else result
    env["result"] = mapped
    after = []
    for st in plan["then"]:
        exec_step(dict(st, loc=()), env, after)
    out.update(inputs=inputs, result=result, mapped=mapped, firsts=firsts, after=after,
               final=env[plan["then"][-1]["out"]] if plan["then"] else mapped)
    return out


def same_answer(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    return num(a) == num(b)


def show(v):
    return v if isinstance(v, str) else fmt(v)


def check_word_problem(wp):
    ok = True
    for dec in wp["extract"]:
        if sum(1 for o in dec["options"] if o.get("correct")) != 1:
            print(f"  ERROR {wp['id']}: decision '{dec['say']}' needs exactly one correct option")
            ok = False
        if dec["concept"] not in EXTRACTION["concepts"]:
            print(f"  ERROR {wp['id']}: unknown concept {dec['concept']}")
            ok = False
    plan = wp_plan(wp)
    if not plan["question"] or set(plan["binds"]) != set(Q[plan["question"]]["inputs"]):
        print(f"  ERROR {wp['id']}: binds {sorted(plan['binds'])} don't match {plan['question']} inputs")
        return False, None
    correct = wp_run(wp, plan)
    ok &= same_answer(correct["final"], wp["answer"])
    traps = []
    for di, dec in enumerate(wp["extract"]):
        for o in dec["options"]:
            if o.get("correct"):
                continue
            tplan = wp_plan(wp, o)
            res = wp_run(wp, tplan, main_route_only=True)
            tells = [lab for key, lab in res["firsts"].items() if key not in correct["firsts"]]
            if any(not isinstance(v, str) for v in tplan["binds"].values()):
                tells = []  # a count written as count/1 isn't a real reading of the methods; diagnose by answer
            traps.append({"decision": di, "concept": dec["concept"], "option": o, "plan": tplan, "run": res,
                          "same_as_correct": same_answer(res["final"], correct["final"]), "tells": tells})
    return ok, {"plan": plan, "run": correct, "traps": traps}


def used_quantities(wp, plan):
    names = set(v for v in plan["binds"].values() if isinstance(v, str))
    for st in plan["steps"] + plan["then"]:
        names |= {a for a in st["args"] if isinstance(a, str)}
    if plan["answer"]:
        names.add(plan["answer"])
    return names


def bind_lines(wp, plan, run_):
    qs = {q["id"]: q for q in wp["quantities"]}
    computed = {st["out"]: st for st in plan["steps"]}
    lines = []
    for k in Q[plan["question"]]["inputs"]:
        src = plan["binds"][k]
        if isinstance(src, str) and src in qs:
            lines.append(f"{k}: {qs[src]['text']}")
        elif isinstance(src, str) and src in computed:
            lines.append(f"{k}: {fmt(run_['env'][src])} ({say(computed[src]['say'], run_['env']).lower()})")
        else:
            lines.append(f"{k}: {fmt(num(src))}")
    return lines


def word_problem_graph(wp, info):
    """Story → extraction (a frame of decisions, done in any order; traps branch off) → data edge with the extracted
    numbers → the question drawn exactly as on its own page → follow-up steps → the answer in the story's terms."""
    g = Mermaid()
    plan, run_ = info["plan"], info["run"]
    story = g.node("start", ["Story", wp["title"]])
    xf = g.frame("Extract: decide all of these, in any order")
    split, join = g.node("all", "all", xf), g.node("all", "all", xf)
    g.edge(story, split)
    traps_by_option = {id(t["option"]): t for t in info["traps"]}

    def chain(entries, env, frame, extra=()):
        return draw_blocks(g, [("step", step_lines(e, env)) for e in entries] + list(extra), frame)

    for dec in wp["extract"]:
        correct = next(o for o in dec["options"] if o.get("correct"))
        own = [e for e in run_["before"] if e[0]["out"] in {s["out"] for s in correct.get("steps", [])}]
        traps = [o for o in dec["options"] if not o.get("correct")]
        if not traps:
            s = g.node("step", [dec["say"], correct["say"]], xf)
            g.edge(split, s)
            e, x = chain(own, run_["env"], xf)
            if e:
                g.edge(s, e)
            g.edge(x or s, join)
            continue
        c = g.node("choice", f"× {dec['say']}", xf)
        g.edge(split, c)
        e, x = chain(own, run_["env"], xf)
        g.edge(c, e or join, f"✓ {correct['say']}", "option")
        if e:
            g.edge(x, join)
        for o in traps:
            t = traps_by_option[id(o)]
            res, tplan = t["run"], t["plan"]
            extra = []
            if res["inputs"] is not None:
                q = Q[tplan["question"]]
                extra.append(("call", [q["title"], f"{render(q['prompt'], res['inputs']).rstrip('.?')} → {show(res['mapped'])}"]))
            trap_steps = [en for en in res["before"] if en[0]["out"] in {s["out"] for s in o.get("steps", [])}]
            after = [("step", step_lines(en, res["env"])) for en in res["after"]]
            e2, x2 = chain(trap_steps, res["env"], None, extra + after)
            label = [f"{show(res['final'])} ✗"]
            if t["same_as_correct"]:
                label.append("same answer as the correct reading!")
            if t["tells"]:
                label.append("gives itself away: " + ", ".join(t["tells"][:2]))
            w = g.node("wrong", label)
            if x2:
                g.edge(x2, w)
            g.edge(c, e2 or w, f"✗ {EXTRACTION['concepts'][dec['concept']]['name']}: {o['say']}", "trap")

    qid = plan["question"]
    qf = g.frame(f"{Q[qid]['title']} (as on its own page)")
    qstart, qend, _ = question_graph(g, qid, {k: fmt(v) for k, v in run_["inputs"].items()},
                                     f"Answer: {show(run_['result'])}", qf)
    g.edge(join, qstart, bind_lines(wp, plan, run_), "data")
    last = qend
    if run_["after"]:
        e, x = draw_blocks(g, [("step", step_lines(en, run_["env"])) for en in run_["after"]], None)
        g.edge(last, e)
        last = x
    final = g.node("end", ["Answer", wp["answer_text"]])
    g.edge(last, final, "in the story's terms" if plan["answer_map"] else None)
    return g.emit()


# ================================================================ svg: render once, add the legend

SVG = ROOT / "svg"
CACHE = ROOT / ".cache"
SITE = ROOT.parent / "site"   # generated Quarto sources (git-ignored)
DOCS = ROOT.parent / "docs"   # rendered website (GitHub Pages)
MERMAID_CONFIG = {"htmlLabels": False, "flowchart": {"htmlLabels": False}}
GRAPHS = {}  # name → {title, source, legend}; pages hold {{GRAPH:name}} until embed() fills them in


def graph_ref(name, title, source, legend):
    GRAPHS[name] = {"title": title, "source": source, "legend": legend}
    return "{{GRAPH:" + name + "}}"


def render_raw(sources):
    """Render mermaid sources to svg text with mmdc in one run, cached by content hash."""
    CACHE.mkdir(exist_ok=True)
    digest = {n: hashlib.sha1((json.dumps(MERMAID_CONFIG) + s).encode()).hexdigest()[:16] for n, s in sources.items()}
    todo = [n for n in sources if not (CACHE / f"{digest[n]}.svg").exists()]
    if todo:
        print(f"  rendering {len(todo)} diagram(s) with mmdc …")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "cfg.json").write_text(json.dumps(MERMAID_CONFIG))
            (tmp / "in.md").write_text("\n\n".join(f"```mermaid\n{sources[n]}\n```" for n in todo))
            res = subprocess.run(["mmdc", "-q", "-i", "in.md", "-o", "out.md", "-c", "cfg.json", "-b", "white"],
                                 cwd=tmp, capture_output=True, text=True)
            if res.returncode != 0:
                print(res.stderr[-3000:])
                raise SystemExit("mmdc failed")
            for i, n in enumerate(todo, 1):
                shutil.move(tmp / f"out-{i}.svg", CACHE / f"{digest[n]}.svg")
    keep = {f"{d}.svg" for d in digest.values()}
    for f in CACHE.glob("*.svg"):
        if f.name not in keep:
            f.unlink()
    return {n: (CACHE / f"{digest[n]}.svg").read_text() for n in sources}


def svg_parts(text):
    m = re.search(r"<svg\b([^>]*)>", text)
    attrs, inner = m[1], text[m.end(): text.rindex("</svg>")]
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', attrs)[1].split()]
    attrs = re.sub(r'\s(width|height|style|viewBox)="[^"]*"', "", attrs)
    return attrs, inner, vb


def with_legend(graph_svg, legend_svg):
    """Stack the diagram and its legend into one svg, legend at the bottom."""
    ga, gi, gvb = svg_parts(graph_svg)
    la, li, lvb = svg_parts(legend_svg.replace("my-svg", "legend-svg"))
    gap = 28
    W, H = max(gvb[2], lvb[2]), gvb[3] + gap + lvb[3]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {W:.1f} {H:.1f}" width="{W:.0f}" height="{H:.0f}" style="background-color: white;">'
            f'<rect width="100%" height="100%" fill="white"/>'
            f'<svg{ga} x="0" y="0" width="{gvb[2]:.1f}" height="{gvb[3]:.1f}" viewBox="{" ".join(map(str, gvb))}">{gi}</svg>'
            f'<line x1="0" x2="{W:.1f}" y1="{gvb[3] + gap / 2:.1f}" y2="{gvb[3] + gap / 2:.1f}" stroke="#d0d4dc"/>'
            f'<svg{la} x="0" y="{gvb[3] + gap:.1f}" width="{lvb[2]:.1f}" height="{lvb[3]:.1f}" viewBox="{" ".join(map(str, lvb))}">{li}</svg>'
            f'</svg>')


def render_svgs():
    """Write svg/<name>.svg (diagram + legend) and svg/<name>.mmd for every registered graph.
    Returns name → width in px, or None when mmdc is unavailable."""
    if not shutil.which("mmdc"):
        print("  WARNING mmdc not found; graph images not updated")
        return None
    SVG.mkdir(exist_ok=True)
    sources = {n: g["source"] for n, g in GRAPHS.items()}
    sources.update({f"legend-{k}": f() for k, f in LEGENDS.items()})
    raw = render_raw(sources)
    widths = {}
    for n, g in GRAPHS.items():
        composed = with_legend(raw[n], raw[f"legend-{g['legend']}"])
        (SVG / f"{n}.svg").write_text(composed)
        (SVG / f"{n}.mmd").write_text(g["source"] + "\n")
        widths[n] = round(float(re.search(r'width="([\d.]+)"', composed)[1]))
    for f in SVG.iterdir():
        if f.suffix in (".svg", ".mmd") and f.stem not in GRAPHS:
            f.unlink()
    stale = SVG / "hashes.json"
    if stale.exists():
        stale.unlink()
    return widths


def embed(text, prefix, mode, widths=None):
    """Replace graph placeholders: an image for GitHub markdown, a zoomable figure for the website,
    or a mermaid block when no images exist."""
    def one(m):
        n = m[1]
        g = GRAPHS[n]
        if mode == "mermaid":
            return f"```mermaid\n{g['source']}\n```"
        if mode == "github":
            return (f"[![{g['title']}]({prefix}{n}.svg)]({prefix}{n}.svg)\n\n"
                    f"<sub>Click the graph to open it full size · [mermaid source]({prefix}{n}.mmd)</sub>")
        w = (widths or {}).get(n)
        size = f' style="width:{w}px"' if w else ""
        return (f'<figure class="graph fit"><div class="graph-scroll">'
                f'<img src="{prefix}{n}.svg" alt="{g["title"]}"{size} loading="lazy"></div>'
                f'<figcaption><button type="button" class="graph-zoom">Actual size</button> · '
                f'<a href="{prefix}{n}.svg" target="_blank">Open in new tab</a> · '
                f'<a href="{prefix}{n}.mmd">Mermaid source</a></figcaption></figure>')
    return re.sub(r"\{\{GRAPH:([\w.-]+)\}\}", one, text)


# ================================================================ pages

def calls_in(items):
    out = set()
    for s in items:
        if s["op"] == "use":
            out.add(s["question"])
        for br in s.get("branches", []):
            out |= calls_in(br)
    return out


def uses(qid):
    out = set()
    for m in methods_of(qid).values():
        out |= calls_in(m["steps"])
    red = Q[qid].get("reduces_to")
    return out - ({red["question"]} if red else set())


def question_md(qid, link=lambda u: f"{u}.md", h="#"):
    """One question's page. `link` builds cross-references; `h` is the top heading level."""
    q, methods = Q[qid], methods_of(qid)
    red = q.get("reduces_to")
    out = [f"{h} {q['title']}", "", f"`{qid}` · {q['kind']} · prompt: *{q['prompt']}*", ""]
    if red:
        out += [f"This is [{red['question']}]({link(red['question'])}) in context, with `{json.dumps(red['with'])}`. "
                + (red.get("note") or ""), ""]
    if uses(qid):
        out += ["Its methods call: " + ", ".join(f"[{u}]({link(u)})" for u in sorted(uses(qid))), ""]
    out += ["| Method | Idea | Best when | Calls |", "|---|---|---|---|"]
    for mid, m in methods.items():
        core = f" (= {red['question']} · {m['core_method']})" if m.get("core_method") else ""
        calls = sorted(calls_in(method_items(qid, mid)))
        out.append(f"| **{m['name']}** `{mid}`{core} | {render(m.get('idea', ''), {})} | {m.get('best_when', '')} | "
                   + (", ".join(f"[{u}]({link(u)})" for u in calls) or "—") + " |")
    out += ["", "Each graph starts at the question and branches at **× Which first step?** into every first step a "
            "student might write. Methods that share a first step meet there and split at **× Which next step?**. "
            "Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.", ""]
    for i, ex in enumerate(q["examples"]):
        graph, na = example_graph(qid, ex)
        title = render(q["prompt"], ex["values"])
        out += [f"{h}# {title}", "", graph_ref(f"{qid}-{i + 1}", title, graph, "question"), ""]
        if na:
            out += ["Not applicable here: " + ", ".join(f"{methods[m]['name']} (`{m}`)" for m in na), ""]
    return "\n".join(out)


REPORT_INTRO = """# Solving arithmetic problems: methods classified by first step

Most arithmetic questions can be solved in several ways. This report catalogs the methods for a family of
ratio, fraction, and percent questions, and the word problems built on them. Each method is classified by **the first
step a student takes**, with the second step used only when methods share a first step. The goal is an app that guides a
student step by step: from each step the student writes, a classifier works out which route through the graph they
are on, and the app responds with help for *that* route.

## How the data is organized

Everything is written in one step language (see `v2/vocabulary.json`). A **step** is one thing a student does, and every
step has a sentence. Steps run in sequence. **`all`** marks steps that can be done in any order. **`choose`** marks a
decision with one correct option and its traps. **`use`** calls another question as a single step.

- **Skills** are small questions that other methods call: simplify a fraction, write it as a decimal, find a common
  multiple, cross products. Each has its own methods (a common multiple can be recalled, found by listing multiples,
  by multiplying, or from the GCF).
- **Core questions** (compare fractions, missing value, add fractions) have methods built from steps and skill calls.
- **Applied questions** are core questions in context: a proportion check *is* comparing fractions for equality, a
  better buy *is* comparing price ÷ quantity, and a percent of a number *is* a missing value with denominator 100.
- **Word problems** start with **extraction**: a set of decisions (which numbers go together, which way round,
  "more" or "in all", which numbers aren't needed), done in any order. Each decision has a correct option and traps,
  and the decisions together pick the question and its numbers.

`v2/build.py` expands every skill call into every combination of skill methods and every `all` block into every order,
runs each variant on the examples to check the answer, and groups variants by their first step (then their second) to
make the classifier's trees. The hand-written first version is in `v1/` for comparison.

## Reading the graphs

Every diagram uses the same grammar, and every diagram carries a legend at the bottom.

- **Rectangles are steps**: the sentence, then the worked expression, then tags. A first step is tagged with its
  operation · scope; a step inside a called question is tagged *in: that question*.
- **× hexagons are choices**: the student picks one way forward. This is where the classifier works. Arrows leaving a
  choice are always labeled: with the method they lead to, or with the extraction answer (✓). Red dashed arrows are traps (✗).
- **"all" diamonds** split into branches that are all done, in any order, and join again.
- **Boxes with side bars are calls** to another question, shown with what goes in and what comes out; each has its own page.
- **Thick green arrows carry data** into a question: the extracted numbers, with what they count.
- A **method is a route**, not a box. Steps that methods share are drawn once, and the method's name sits on the arrow
  where its route becomes unique.

## What expanding the skills revealed

Shared first steps that only appear once skills and `all` blocks are expanded:

- In *compare fractions*, `3 × 7` starts both **cross-multiply** and **rewrite one fraction over the other's
  denominator** (through missing value's cross-multiply). The next step decides: `5 × 4` vs `21 ÷ 4`.
- In *proportion check*, `6 ÷ 8` starts both **decimal** and **rewrite over the other's denominator**,
  and `GCF(6, 8)` starts both **simplify** and the same rewrite.
- `3 × 5 = 15` can come from **listing multiples** or from **multiplying**; the graphs show it as one step.

Known limit: the generated trees store a student-chosen multiplier as a wildcard, so a typed classifier sees
`4 × 25` as matching three methods. The per-example graphs tell those apart by value.

## How the questions reuse each other
"""

INDEX_CAPTION = ("Green = skill, yellow = core, blue = applied. Solid arrows: a method uses that question as a step. "
                 "Dotted arrows: the applied question *is* the core question in context. "
                 "(compare-fractions also calls itself: *distance from 1* ends by comparing the two gaps.)")


def index_graph():
    g = Mermaid("i")
    ids = {qid: g.node(Q[qid]["kind"], Q[qid]["title"]) for qid in Q}
    for qid, q in Q.items():
        for u in sorted(uses(qid) - {qid}):
            g.edge(ids[qid], ids[u])
        if q.get("reduces_to"):
            g.edge(ids[qid], ids[q["reduces_to"]["question"]], "is a", "dotted")
    return graph_ref("index", "How the questions reuse each other", g.emit(), "index")


def question_table(link):
    order = [k for kind in ("core", "applied", "skill") for k, q in Q.items() if q["kind"] == kind]
    rows = ["| Question | Kind | Methods | Uses |", "|---|---|---|---|"]
    for qid in order:
        q = Q[qid]
        u = sorted(uses(qid) | ({q["reduces_to"]["question"]} if q.get("reduces_to") else set()))
        rows.append(f"| [{q['title']}]({link(qid)}) | {q['kind']} | {len(methods_of(qid))} | "
                    + (", ".join(f"[{x}]({link(x)})" for x in u) or "—") + " |")
    return rows


def index_md():
    return "\n".join(["# Question graphs (v2)", "", "How the questions reuse each other. " + INDEX_CAPTION, "",
                      index_graph(), ""] + question_table(lambda u: f"{u}.md")
                     + ["", "Word problems: [word-problems.md](word-problems.md)", ""])


WORD_INTRO = (
    "A word problem needs **extraction** before any method applies. Extraction is a set of decisions, done in any "
    "order: which question the story is, which numbers go together and which way round, whether a number is extra or "
    "a total, which numbers aren't needed. Each decision has one correct option and its **traps**: the mistakes "
    "students actually make. A trap is the correct reading with that one decision swapped, so the build computes the "
    "wrong answer it leads to, and the first steps that give it away (steps no correct reading starts with). That lets "
    "an app diagnose an extraction mistake from a student's answer, and often from their first step.")

WORD_GRAPH_NOTE = (
    "The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for "
    "each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the "
    "question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the "
    "story's terms. The legend is at the bottom.")


def word_problems_intro(link, item_link, h="#"):
    c = EXTRACTION["concepts"]
    out = [f"{h} Word problems", "", WORD_INTRO, "", f"{h}# Extraction concepts", "",
           "| Concept | What the student decides | Cues | Typical mistake |", "|---|---|---|---|"]
    for k, v in c.items():
        out.append(f"| **{v['name']}** `{k}` | {v['does']} | {'; '.join(v.get('cues', [])) or '—'} | {v.get('mistake', '—')} |")
    out += ["", "| Word problem | Is a | Decisions |", "|---|---|---|"]
    for wid, wp in WP.items():
        qid = wp_plan(wp)["question"]
        out.append(f"| [{wp['title']}]({item_link(wid)}) | [{Q[qid]['title']}]({link(qid)}) | "
                   + ", ".join(c[x]["name"] for x in wp["concepts"]) + " |")
    out.append("")
    return out


def word_problem_section(wid, info, link, h="#"):
    c = EXTRACTION["concepts"]
    wp = WP[wid]
    plan = info["plan"]
    qid = plan["question"]
    used = used_quantities(wp, plan)
    out = [f"{h} {wp['title']}", "", f"> {wp['text']}", "",
           f"**Asked:** {wp['asks']['text']} ({wp['asks']['unit']}). "
           f"**Is a:** [{Q[qid]['title']}]({link(qid)}). **Answer:** {wp['answer_text']}.", "",
           "| Phrase | Value | Counts | Needed? |", "|---|---|---|---|"]
    for q in wp["quantities"]:
        out.append(f"| “{q['text']}” | {q['value']} {q['unit']} | {q['counts']} | {'yes' if q['id'] in used else '**no**'} |")
    out += ["", "| Decision | Concept | Correct | Traps → wrong answer |", "|---|---|---|---|"]
    for di, dec in enumerate(wp["extract"]):
        correct = next(o for o in dec["options"] if o.get("correct"))
        traps = [t for t in info["traps"] if t["decision"] == di]
        tr = "; ".join(f"{t['option']['say']} → {show(t['run']['final'])}" for t in traps) or "—"
        out.append(f"| {dec['say']} | {c[dec['concept']]['name']} | {correct['say']} | {tr} |")
    out += ["", WORD_GRAPH_NOTE, "", graph_ref(f"wp-{wid}", wp["title"], word_problem_graph(wp, info), "word"), "",
            "| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |", "|---|---|---|---|---|"]
    for t in info["traps"]:
        out.append(f"| {c[t['concept']]['name']} | {t['option']['trap']} | {show(t['run']['final'])} | "
                   + ("**no**: same answer, so ask how they got it" if t["same_as_correct"] else "yes") + " | "
                   + (", ".join(f"`{x}`" for x in t["tells"][:4]) or "—") + " |")
    return "\n".join(out)


def word_problems_md(infos, link=lambda u: f"{u}.md", h="#"):
    out = word_problems_intro(link, lambda w: f"#{w}", h)
    for wid in WP:
        out += [f'<a name="{wid}"></a>', "", word_problem_section(wid, infos[wid], link, h + "#"), ""]
    return "\n".join(out)


def report_md(infos):
    anchor = lambda u: f"#{u}"
    order = [k for kind in ("core", "applied", "skill") for k, q in Q.items() if q["kind"] == kind]
    body = [REPORT_INTRO, INDEX_CAPTION, "", index_graph(), ""] + question_table(anchor)
    body += ["", "## Contents", ""] + [f"- [{Q[k]['title']}](#{k}) ({Q[k]['kind']})" for k in order]
    body += [f"- [Word problems](#word-problems): extraction concepts and {len(WP)} stories", ""]
    for qid in order:
        body += [f'<a name="{qid}"></a>', "", question_md(qid, anchor, "##"), ""]
    body += [word_problems_md(infos, anchor, "##"), ""]
    body += ["## Rebuilding", "", "```sh", "cd v2 && python3 build.py --demo", "```", "",
             "This checks every method variant against every example and every word problem against its answer; "
             "regenerates `v2/trees/`, `v2/graphs/`, the graph images in `v2/svg/` (with `mmdc`), and this report; "
             "builds the website in `docs/` (with Quarto); and runs the classifier on sample student steps.", ""]
    return "\n".join(body)


# ================================================================ website

SITE_CSS = """
.graph { margin: 1rem 0 2rem; }
.graph-scroll { overflow: auto; max-height: 85vh; border: 1px solid #dee2e6; border-radius: 6px; background: #fff; }
.graph-scroll img { display: block; max-width: none; cursor: zoom-in; }
.graph.fit .graph-scroll img { width: 100% !important; height: auto; }
.graph:not(.fit) .graph-scroll img { cursor: zoom-out; }
.graph figcaption { font-size: .85rem; color: #6c757d; margin-top: .35rem; }
.graph figcaption button { border: 1px solid #ced4da; background: #f8f9fa; border-radius: 4px; padding: 0 .5rem; font-size: .85rem; }
blockquote { font-size: 1.05rem; }
"""

SITE_JS = """<script>
document.addEventListener('click', e => {
  const fig = e.target.closest('.graph');
  if (!fig) return;
  if (e.target.matches('.graph-zoom') || e.target.matches('.graph-scroll img')) {
    const fit = fig.classList.toggle('fit');
    fig.querySelector('.graph-zoom').textContent = fit ? 'Actual size' : 'Fit to width';
  }
});
</script>
"""


def page(title, body):
    return f"---\ntitle: {json.dumps(title)}\n---\n\n{body}\n"


def strip_heading(md):
    return md.split("\n", 1)[1].lstrip("\n")


def build_site(infos, widths):
    """Write Quarto sources to site/ and render the website into docs/."""
    if not shutil.which("quarto"):
        print("  WARNING quarto not found; website not built")
        return
    if SITE.exists():
        shutil.rmtree(SITE)
    for d in ("questions", "word-problems", "svg"):
        (SITE / d).mkdir(parents=True)
    for f in SVG.iterdir():
        if f.suffix in (".svg", ".mmd"):
            shutil.copy(f, SITE / "svg" / f.name)
    kinds = {k: [q for q in Q if Q[q]["kind"] == k] for k in ("core", "applied", "skill")}
    names = {"core": "Core questions", "applied": "Applied questions", "skill": "Skills"}
    sidebar = ["      - text: Overview", "        href: index.md"]
    for k, ids in kinds.items():
        sidebar += [f"      - section: {json.dumps(names[k])}", "        contents:"]
        sidebar += [f"          - questions/{q}.md" for q in ids]
    sidebar += ['      - section: "Word problems"', "        contents:", "          - word-problems/index.md"]
    sidebar += [f"          - word-problems/{w}.md" for w in WP]
    (SITE / "_quarto.yml").write_text("\n".join([
        "project:", "  type: website", "  output-dir: ../docs", "  resources:", "    - svg/*",
        "website:", '  title: "Problem solving by first step"', "  repo-url: https://github.com/rahuldave/ProblemSolving",
        "  page-navigation: true", "  sidebar:", "    style: docked", "    search: true", "    contents:", *sidebar,
        "format:", "  html:", "    theme: cosmo", "    css: styles.css", "    toc: true", "    page-layout: full",
        "    include-after-body: graph.html", ""]))
    (SITE / "styles.css").write_text(SITE_CSS)
    (SITE / "graph.html").write_text(SITE_JS)

    intro = REPORT_INTRO.split("\n", 1)[1]
    for path in ("v2/vocabulary.json", "v2/build.py"):
        intro = intro.replace(f"`{path}`", f"[`{path}`](https://github.com/rahuldave/ProblemSolving/blob/main/{path})")
    home = (intro + INDEX_CAPTION + "\n\n" + index_graph() + "\n\n" + "\n".join(question_table(lambda u: f"questions/{u}.md"))
            + f"\n\n[Word problems](word-problems/index.md): extraction concepts and {len(WP)} stories, "
            "drilled down to the arithmetic.\n")
    (SITE / "index.md").write_text(page("Solving arithmetic problems: methods classified by first step",
                                        embed(home, "svg/", "site", widths)))
    for qid in Q:
        md = strip_heading(question_md(qid, lambda u: f"{u}.md", "#"))
        (SITE / "questions" / f"{qid}.md").write_text(page(Q[qid]["title"], embed(md, "../svg/", "site", widths)))
    wintro = "\n".join(word_problems_intro(lambda u: f"../questions/{u}.md", lambda w: f"{w}.md", "#"))
    (SITE / "word-problems" / "index.md").write_text(page("Word problems", embed(strip_heading(wintro), "../svg/", "site", widths)))
    for wid in WP:
        md = strip_heading(word_problem_section(wid, infos[wid], lambda u: f"../questions/{u}.md", "#"))
        (SITE / "word-problems" / f"{wid}.md").write_text(page(WP[wid]["title"], embed(md, "../svg/", "site", widths)))
    print("  rendering website with quarto …")
    res = subprocess.run(["quarto", "render"], cwd=SITE, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout[-2000:], res.stderr[-2000:])
        raise SystemExit("quarto render failed")
    (DOCS / ".nojekyll").write_text("")


# ================================================================ validation

def check_question(qid):
    ok = True
    for mid, m in methods_of(qid).items():
        def walk(items, where):
            nonlocal ok
            for s in items:
                if s["op"] == "use":
                    child = Q.get(s["question"])
                    if not child:
                        print(f"  ERROR {where} uses unknown question {s['question']}")
                        ok = False
                    elif set(s["with"]) != set(child["inputs"]) or not set(s["out"]) <= set(child["outputs"]):
                        print(f"  ERROR {where} → {s['question']}: inputs or outputs don't match")
                        ok = False
                for br in s.get("branches", []):
                    walk(br, where)
                for sub in s.get("steps", []) if s["op"] == "repeat" else []:
                    walk([sub], where)
                if not s.get("hidden") and s["op"] not in ("map", "all") and not s.get("say"):
                    print(f"  ERROR {where}: a {s['op']} step has no sentence (`say`)")
                    ok = False
        if m["display_level"] == 0:
            walk(m["steps"], f"{qid}/{mid}")
    return ok


def validate(qid):
    q, methods = Q[qid], methods_of(qid)
    ok = check_question(qid)
    variants = variants_of(qid)
    print(f"\n== {qid} ({q['kind']}): {len(methods)} methods, {len(variants)} variants")
    for ex in q["examples"]:
        print(f"  {ex['id']!r} → {ex['answer']}")
        for mid, m in methods.items():
            vs = [v for v in variants if v["method"] == mid]
            good = bad = 0
            got = None
            for v in vs:
                try:
                    env, _ = run(v["steps"], ex["values"])
                except NotApplicable:
                    continue
                got = outputs_of(qid, env)
                if answer_ok(got, ex["answer"], m):
                    good += 1
                else:
                    bad += 1
                    print(f"    BAD {mid}: got {got}")
            ok &= bad == 0
            shown = {k: fmt(x) for k, x in got.items()} if isinstance(got, dict) else fmt(got) if got is not None else got
            status = "ok " if good and not bad else ("BAD" if bad else " - ")
            print(f"    {status} {mid:22s} {f'{shown}  ({good}/{len(vs)} variants apply)' if good else 'not applicable'}")
    return ok


# ================================================================ classifier demo

TOKEN = re.compile(r"^\s*(gcf|lcm)\s*\(?\s*([\d.]+)\s*,?\s*([\d.]+)\s*\)?\s*$|"
                   r"^\s*([\d.]+)\s*([+\-*x×/÷])\s*([\d.]+)\s*$", re.I)
SYM_OP = {"+": "add", "-": "subtract", "*": "multiply", "x": "multiply", "×": "multiply", "/": "divide", "÷": "divide"}


def parse(text):
    m = TOKEN.match(text)
    if m.group(1):
        return m.group(1).lower(), [num(m.group(2)), num(m.group(3))]
    return SYM_OP[m.group(5).lower()], [num(m.group(4)), num(m.group(6))]


def split_top(s):
    depth, cur, parts = 0, "", []
    for ch in s:
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    return parts + [cur.strip()]


def ev(expr, values):
    """Evaluate a tree expression; wildcards come back as ('int',) or ('cf', x, y)."""
    if expr == "int":
        return ("int",)
    m = re.fullmatch(r"(\w+)\((.*)\)", expr)
    if m:
        args = [ev(a, values) for a in split_top(m[2])]
        if m[1] == "common_factor":
            return ("cf", *args)
        if any(isinstance(a, tuple) for a in args):
            return ("int",)
        return apply_op(m[1], *args)
    if re.fullmatch(r"[\d.]+", expr):
        return num(expr)
    return values[expr]


def fits(pattern, n):
    if not isinstance(pattern, tuple):
        return pattern == n
    if pattern[0] == "int":
        return n.denominator == 1
    _, x, y = pattern
    return n > 1 and (x / n).denominator == 1 and (y / n).denominator == 1


def find(entries, op, nums, values):
    hits = []
    for e in entries:
        if e["match"]["op"] != op:
            continue
        try:
            pats = [ev(a, values) for a in e["match"]["args"]]
        except (KeyError, NotApplicable):
            continue
        orders = itertools.permutations(nums) if op in COMMUTATIVE else [nums]
        if any(all(fits(p, n) for p, n in zip(pats, o)) for o in orders):
            hits.append((sum("int" in a or "common_factor" in a for a in e["match"]["args"]), e))
    best = min((w for w, _ in hits), default=None)
    return [e for w, e in hits if w == best]


def classify(qid, values, steps):
    tree = json.loads((ROOT / "trees" / f"{qid}.json").read_text())
    vals = {k: num(v) for k, v in values.items()}
    entries, trail = tree["first_steps"], []
    for text in steps:
        op, nums = parse(text)
        hits = find(entries, op, nums, vals)
        methods = sorted({m for e in hits for m in e["methods"]})
        trail.append(f"{text} ⇒ {methods or 'unrecognized'}")
        nexts = [n for e in hits for n in e.get("next", [])]
        if len(methods) <= 1 or not nexts:
            break
        entries = nexts
    return " → ".join(trail)


DEMOS = [
    ("proportion-check", ["6 / 8"]), ("proportion-check", ["72 ÷ 96"]), ("proportion-check", ["8 ÷ 6"]),
    ("proportion-check", ["72 ÷ 6"]), ("proportion-check", ["gcf(6, 8)"]), ("proportion-check", ["96 x 6"]),
    ("compare-fractions", ["3 x 7", "5 x 4"]), ("compare-fractions", ["5 x 4", "3 x 7"]), ("compare-fractions", ["3 x 7", "21 / 4"]),
    ("compare-fractions", ["3 / 4", "5 / 7"]), ("compare-fractions", ["3 / 4", "0.75 x 7"]),
    ("compare-fractions", ["lcm(4, 7)"]), ("compare-fractions", ["4 x 7"]),
    ("missing-value", ["40 / 5"]), ("better-buy", ["3 / 12"]), ("better-buy", ["20 / 12"]),
    ("percent-of", ["15 / 100", "0.15 x 80"]), ("percent-of", ["0.15 x 80"]), ("percent-of", ["80 / 100"]),
    ("percent-of", ["gcf(15, 100)"]), ("percent-of", ["80 / 10"]), ("percent-of", ["15 x 80"]),
    ("add-fractions", ["lcm(6, 4)"]), ("add-fractions", ["6 x 4"]), ("add-fractions", ["5 x 4"]),
]


# ================================================================ main

def main():
    ok = True
    md_out = {}
    (ROOT / "trees").mkdir(exist_ok=True)
    (ROOT / "graphs").mkdir(exist_ok=True)
    for qid in Q:
        ok &= validate(qid)
        (ROOT / "trees" / f"{qid}.json").write_text(json.dumps(build_tree(qid), indent=2, ensure_ascii=False) + "\n")
        md_out[ROOT / "graphs" / f"{qid}.md"] = ("../svg/", question_md(qid))
    md_out[ROOT / "graphs" / "README.md"] = ("../svg/", index_md())

    print(f"\n== word problems: {len(WP)}")
    infos = {}
    for wid, wp in WP.items():
        wok, info = check_word_problem(wp)
        ok &= wok
        if not info:
            continue
        infos[wid] = info
        print(f"  {'ok ' if wok else 'BAD'} {wid:22s} {show(info['run']['final']):18s} traps: "
              + ", ".join(show(t["run"]["final"]) + ("(=!)" if t["same_as_correct"] else "") for t in info["traps"]))

    def option_json(o, traps):
        if o.get("correct"):
            return {"say": o["say"], "correct": True}
        t = next(t for t in traps if t["option"] is o)
        return {"say": o["say"], "trap": o["trap"], "answer": show(t["run"]["final"]),
                "caught_by_answer": not t["same_as_correct"], "first_steps_that_give_it_away": t["tells"]}

    (ROOT / "trees" / "word-problems.json").write_text(json.dumps({
        wid: {"question": i["plan"]["question"],
              "inputs": {k: fmt(v) for k, v in i["run"]["inputs"].items()},
              "answer": show(i["run"]["final"]),
              "decisions": [{"concept": d["concept"], "say": d["say"],
                             "options": [option_json(o, i["traps"]) for o in d["options"]]} for d in WP[wid]["extract"]]}
        for wid, i in infos.items()}, indent=2, ensure_ascii=False) + "\n")
    md_out[ROOT / "graphs" / "word-problems.md"] = ("../svg/", word_problems_md(infos))
    md_out[ROOT.parent / "REPORT.md"] = ("v2/svg/", report_md(infos))

    print("\n== graphs and website")
    widths = render_svgs()
    for path, (prefix, text) in md_out.items():
        path.write_text(embed(text, prefix, "github" if widths is not None else "mermaid"))
    if widths is not None and "--no-site" not in sys.argv:
        build_site(infos, widths)
    if "--demo" in sys.argv:
        print("\n== Classifier demo (first example of each question)")
        for qid, steps in DEMOS:
            ex = Q[qid]["examples"][0]
            print(f"  [{ex['id']}] {classify(qid, ex['values'], steps)}")
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
