"""Build v2: expand skills and reductions, check every method on every example,
derive first-step trees (trees/*.json) and mermaid graphs (graphs/*.md).

Usage: python3 build.py           # validate + generate
       python3 build.py --demo    # also run the student-step classifier demo
"""

import itertools
import json
import math
import re
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).parent
VOCAB = json.loads((ROOT / "vocabulary.json").read_text())
Q = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "questions").glob("*.json"))}
OPERATION = VOCAB["classification"]["levels"][0]["from_op"]
COMMUTATIVE = {"add", "multiply", "gcf", "lcm", "plot"}
SYMBOL = {"add": "+", "subtract": "−", "multiply": "×", "divide": "÷"}
BOOKKEEPING = {"map", "init", "choose"}


class NotApplicable(Exception):
    pass


# ---------------------------------------------------------------- methods

_methods_cache = {}


def methods_of(qid):
    """Method id → method, with an applied question's reductions turned into methods."""
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
            steps = [{"op": "use", "question": red["question"], "method": cid,
                      "with": red["with"], "out": {"answer": target}}]
            if red.get("answer_map"):
                steps.append({"op": "map", "args": ["core_answer"], "out": "answer",
                              "table": red["answer_map"], "hidden": True})
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


# ---------------------------------------------------------------- expansion

def local(name, rename, prefix):
    if isinstance(name, list):
        return [local(n, rename, prefix) for n in name]
    if not isinstance(name, str):
        return name
    return rename.get(name, prefix + name)


def rename_step(step, rename, prefix, path):
    L = lambda n: local(n, rename, prefix)
    new = dict(step, path=path)
    if "args" in step:
        new["args"] = L(step["args"])
    if "out" in step:
        new["out"] = L(step["out"])
    if "search" in step:
        s = dict(step["search"])
        s["var"] = L(s["var"])
        for key in ("until", "until_divisible_by"):
            if key in s:
                s[key] = L(s[key])
        if "until_power_of_ten" in s:
            s["until_power_of_ten"] = L(s["until_power_of_ten"])
        new["search"] = s
    if step["op"] == "repeat":
        new["init"] = {L(k): L(v) for k, v in step["init"].items()}
        new["choose"] = dict(step["choose"], var=L(step["choose"]["var"]), of=L(step["choose"]["of"]))
        new["steps"] = [rename_step(s, rename, prefix, path) for s in step["steps"]]
    if "text" in step:
        new["text"] = re.sub(r"\{([^{}]+)\}", lambda m: "{" + str(L(m[1])) + "}", step["text"])
    return new


def expand(qid, forced, rename, prefix, path, stack, defaults_only):
    """Yield (method_id, steps, calls) for every combination of skill-method choices."""
    methods = methods_of(qid)
    default = default_method(qid)
    if forced:
        ids = [forced if forced in methods else
               next(k for k, m in methods.items() if m.get("core_method") == forced)]
    elif defaults_only:
        ids = [default]
    else:
        ids = sorted(methods, key=lambda m: m != default)
    for mid in ids:
        for steps, calls in expand_steps(qid, mid, methods[mid]["steps"], rename,
                                         f"{prefix}{mid}.", path, stack + [qid], defaults_only):
            yield mid, steps, calls


def expand_steps(qid, mid, steps, rename, prefix, path, stack, defaults_only):
    partials = [([], [])]
    for i, step in enumerate(steps):
        here = path + [(qid, mid, i)]
        if step["op"] != "use":
            new = rename_step(step, rename, prefix, here)
            partials = [(s + [new], c) for s, c in partials]
            continue
        child = step["question"]
        cwith = {k: local(v, rename, prefix) for k, v in step["with"].items()}
        couts = {k: local(v, rename, prefix) for k, v in step["out"].items()}
        call = {"path": here, "question": child, "with": cwith, "out": couts}
        subs = list(expand(child, step.get("method"), {**cwith, **couts}, f"{prefix}{i}:",
                           here, stack, defaults_only or child in stack))
        partials = [(s + ss, c + [call] + sc) for s, c in partials for _, ss, sc in subs]
    return partials


def variants_of(qid):
    q = Q[qid]
    rename = {k: k for k in list(q["inputs"]) + q["outputs"]}
    return [{"method": mid, "steps": steps, "calls": calls}
            for mid, steps, calls in expand(qid, None, rename, "", [], [], False)]


# ---------------------------------------------------------------- evaluation

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
    return Fraction({"gcf": math.gcd(a, b), "lcm": math.lcm(a, b),
                     "floor_div": a // b, "mod": a % b}[op])


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
    op = st["op"]
    if op == "plot":
        trace.append((st, [val(a, env) for a in st["args"]], None))
        return
    if op == "repeat":
        for k, v in st["init"].items():
            env[k] = val(v, env)
        trace.append(({"op": "init", "init": st["init"], "path": st["path"]}, None, None))
        ch = st["choose"]
        if smallest_common_prime(*(val(a, env) for a in ch["of"])) is None:
            raise NotApplicable("already in lowest terms; nothing to divide out")
        while (f := smallest_common_prime(*(val(a, env) for a in ch["of"]))) is not None:
            env[ch["var"]] = Fraction(f)
            trace.append(({"op": "choose", **ch, "path": st["path"]}, None, f))
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
        meaning = st["meaning"]
        env[st["out"]] = meaning.get(rel) or meaning["≠"]
        trace.append((st, [x, y], rel))
        return
    if "search" in st:
        s, var = st["search"], st["search"]["var"]
        base = val(next(a for a in st["args"] if a != var), env)
        k = None
        if "until" in s:
            k = val(s["until"][1], env) / base
        elif "until_power_of_ten" in s:
            k = next((Fraction(10 ** n) / base for n in range(1, 16)
                      if (Fraction(10 ** n) / base).denominator == 1), None)
        elif "until_divisible_by" in s:
            b, dv = whole(base, val(s["until_divisible_by"][1], env))
            k = Fraction(dv // math.gcd(b, dv))
        if k is None or k.denominator != 1 or k < 1:
            raise NotApplicable(f"no whole-number {var.split('.')[-1]} works")
        env[var] = k
        if k == 1:
            env.setdefault("__trivial__", set()).add(var)
            st = dict(st, hidden=True)
    if set(st.get("args", [])) & env.get("__trivial__", set()):
        st = dict(st, hidden=True)
    x, y = (val(a, env) for a in st["args"])
    result = apply_op(op, x, y)
    if st.get("requires_nonnegative") and result < 0:
        raise NotApplicable(f"{result} is negative")
    if st.get("requires_integer") and result.denominator != 1:
        raise NotApplicable(f"{result} is not whole")
    env[st["out"]] = result
    trace.append((st, [x, y], result))


def outputs_of(qid, env):
    outs = Q[qid]["outputs"]
    return env[outs[0]] if outs == ["answer"] else {o: env[o] for o in outs}


def answer_ok(got, expected, method):
    if isinstance(expected, dict):
        return all(answer_ok(got[k], v, method) for k, v in expected.items())
    if isinstance(got, str):
        if got == expected:
            return True
        return method.get("decides") == "equality_only" and got == "not equal" and expected in ("first", "second")
    exp = num(expected)
    if method.get("answer_relation") == "multiple":
        return (got / exp).denominator == 1
    return got == exp


# ---------------------------------------------------------------- signatures

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
        if op == "choose":
            sym[st["var"]] = f"common_factor({', '.join(S(a) for a in st['of'])})"
            continue
        if op == "repeat":  # static walk: one round of the loop
            out += signatures([{"op": "init", "init": st["init"]},
                               {"op": "choose", **st["choose"]}] + st["steps"], limit - len(out))
            continue
        if "search" in st:
            sym[st["search"]["var"]] = "int"
        args = [S(a) for a in st.get("args", [])]
        if op in COMMUTATIVE:
            args = sorted(args)
        if "out" in st:
            sym[st["out"]] = f"{op}({', '.join(args)})"
        if not st.get("hidden") and op not in BOOKKEEPING:
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


def via(step, method):
    inner = step["path"][method["display_level"] + 1:]
    return f"{inner[-1][0]}/{inner[-1][1]}" if inner else ""


# ---------------------------------------------------------------- trees

def build_tree(qid, variants):
    methods = methods_of(qid)
    mental = {key_of({"op": m["op"], "args": sorted(m["args"]) if m["op"] in COMMUTATIVE else m["args"]})
              for m in Q[qid].get("mental_first_steps", [])}
    entries = {}

    def add(sig, nxt, v, is_mental):
        key = ("mental:" if is_mental else "") + key_of(sig)
        e = entries.setdefault(key, {"sig": sig, "mental": is_mental, "methods": {}, "next": {}})
        m = methods[v["method"]]
        e["methods"].setdefault(v["method"], set()).add(via(sig["step"], m))
        if nxt:
            n = e["next"].setdefault(key_of(nxt), {"sig": nxt, "methods": {}})
            n["methods"].setdefault(v["method"], set()).add(via(nxt["step"], m))

    for v in variants:
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
        out["via"] = {m: sorted(x for x in e["methods"][m] if x) for m in names if any(e["methods"][m])}
        if not out["via"]:
            del out["via"]
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


# ---------------------------------------------------------------- labels

def fmt(v):
    if isinstance(v, str):
        return v
    if isinstance(v, tuple):
        return ":".join(fmt(x) for x in v)
    if v.denominator == 1:
        return str(v.numerator)
    d = v.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    if d == 1:
        return format(Decimal(v.numerator) / Decimal(v.denominator), "f")
    return f"{v.numerator}/{v.denominator}"


def terminates(v):
    d = v.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    return d == 1


def approx(v):
    return fmt(v) if not isinstance(v, Fraction) or terminates(v) else f"≈ {float(v):.3f}"


def label(st, args, result):
    op = st["op"]
    if op == "plot":
        return "plot " + ", ".join(f"({fmt(x)}, {fmt(y)})" for x, y in args)
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


def render(template, values):
    return re.sub(r"\{(\w+)\}", lambda m: fmt(num(values[m[1]])) if m[1] in values else m[0], template)


def visible(trace):
    return [t for t in trace if not t[0].get("hidden") and t[0]["op"] not in BOOKKEEPING]


def chain(qid, variant, env, trace):
    """Labels for the method's own steps; calls to other questions collapse into one node each."""
    level = methods_of(qid)[variant["method"]]["display_level"]
    calls = {tuple(c["path"]): c for c in variant["calls"]}
    nodes, seen = [], set()
    for st, args, result in trace:
        p = tuple(st["path"])
        if len(p) > level + 1:
            key = p[:level + 1]
            if key in seen:
                continue
            seen.add(key)
            c = calls[key]
            child = Q[c["question"]]
            ins = {k: fmt(val(v, env)) for k, v in c["with"].items()}
            show = approx if child.get("output_format") == "decimal" else fmt
            outs = "/".join(show(env[v]) for v in c["out"].values())
            prompt = re.sub(r"\{(\w+)\}", lambda m: ins.get(m[1], m[0]), child["prompt"]).rstrip(".?")
            nodes.append(("skill", f"{prompt} → {outs}", c["question"]))
        elif not st.get("hidden") and st["op"] not in BOOKKEEPING:
            nodes.append(("step", label(st, args, result), None))
    return nodes


# ---------------------------------------------------------------- mermaid

def esc(s):
    return s.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def example_graph(qid, ex, variants):
    body, na, _, _ = example_graph_parts(qid, ex, variants)
    return "\n".join(["flowchart LR"] + body), na


def example_graph_parts(qid, ex, variants, prefix="n"):
    """Mermaid lines (no header) for one example, plus the root and answer node ids so callers can attach to them."""
    q, methods = Q[qid], methods_of(qid)
    mental = {key_of({"op": m["op"], "args": m["args"]}) for m in q.get("mental_first_steps", [])}
    runs = {}
    for v in variants:
        try:
            env, trace = run(v["steps"], ex["values"])
        except (NotApplicable, KeyError) as e:
            runs.setdefault(v["method"], [])
            continue
        runs.setdefault(v["method"], []).append((v, env, trace))

    ids = itertools.count()
    nid = lambda: f"{prefix}{next(ids)}"
    lines = []
    styles = {"cls": [], "first": [], "second": [], "method": [], "skill": [], "step": [], "ans": []}

    def node(kind, text, shape="[]"):
        n = nid()
        o, c = {"[]": ("[", "]"), "()": ("(", ")"), "([": ("([", "])"), "{{": ("{{", "}}")}.get(shape, ("[", "]"))
        lines.append(f'  {n}{o}"{esc(text)}"{c}')
        styles[kind].append(n)
        return n

    root = node("ans", render(q["prompt"], ex["values"]), "([")
    answer = node("ans", f"Answer: {ex['answer'] if not isinstance(ex['answer'], dict) else '/'.join(map(str, ex['answer'].values()))}", "([")

    # method chains
    mnode = {}
    for mid, rs in runs.items():
        if not rs:
            continue
        v, env, trace = rs[0]
        mnode[mid] = node("method", methods[mid]["name"])
        prev = mnode[mid]
        for kind, text, _ in chain(qid, v, env, trace):
            n = node(kind, text)
            lines.append(f"  {prev} --> {n}")
            prev = n
        lines.append(f"  {prev} --> {answer}")

    # first steps: (class, first label) → second label → method
    firsts = {}
    for mid, rs in runs.items():
        for v, env, trace in rs:
            vis = visible(trace)
            sigs = signatures([t[0] for t in trace])
            m = methods[mid]
            entries = [(vis[0], vis[1] if len(vis) > 1 else None, classify_sig(qid, sigs[0]), False)]
            if len(vis) > 1 and key_of(sigs[0]) in mental:
                entries.append((vis[1], None, None, True))
            for first, second, cls, is_mental in entries:
                cname = f"{first[0]['op']} done mentally" if is_mental else f"{cls['operation']} · {cls['scope']}"
                if is_mental:
                    cname = f"after {label(*vis[0])} in their head"
                f = firsts.setdefault(label_key(*first), {"label": label(*first), "classes": set(), "methods": {}, "seconds": {}})
                f["classes"].add(cname)
                f["methods"].setdefault(mid, set()).add(via(first[0], m))
                if second:
                    s = f["seconds"].setdefault(label_key(*second), {"label": label(*second), "methods": {}})
                    s["methods"].setdefault(mid, set()).add(via(second[0], m))

    cls_nodes = {}
    for f in sorted(firsts.values(), key=lambda f: (sorted(f["classes"]), f["label"])):
        fn = node("first", f["label"])
        for cname in sorted(f["classes"]):
            if cname not in cls_nodes:
                cls_nodes[cname] = node("cls", cname, "{{")
                lines.append(f"  {root} --> {cls_nodes[cname]}")
            lines.append(f"  {cls_nodes[cname]} --> {fn}")
        if len(f["methods"]) == 1 or not f["seconds"]:
            for mid, vias in sorted(f["methods"].items()):
                edge(lines, fn, mnode[mid], vias)
            continue
        for s in f["seconds"].values():
            sn = node("second", "then " + s["label"])
            lines.append(f"  {fn} --> {sn}")
            for mid, vias in sorted(s["methods"].items()):
                edge(lines, sn, mnode[mid], vias)
        for mid in set(f["methods"]) - {m for s in f["seconds"].values() for m in s["methods"]}:
            edge(lines, fn, mnode[mid], f["methods"][mid])

    lines += [
        "  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222",
        "  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222",
        "  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222",
        "  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold",
        "  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222",
        "  classDef step fill:#ffffff,stroke:#999,color:#222",
        "  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222",
    ]
    for kind, ns in styles.items():
        if ns:
            lines.append(f"  class {','.join(ns)} {kind}")
    na = sorted(mid for mid, rs in runs.items() if not rs)
    return lines, na, root, answer


def edge(lines, a, b, vias):
    text = " / ".join(sorted(v for v in vias if v))
    lines.append(f'  {a} -->|"{esc(text)}"| {b}' if text else f"  {a} --> {b}")


def uses(qid):
    out = set()
    for m in methods_of(qid).values():
        out |= {s["question"] for s in m["steps"] if s["op"] == "use"}
    red = Q[qid].get("reduces_to")
    return out - ({red["question"]} if red else set())


def question_md(qid, variants, link=lambda u: f"{u}.md", h="#"):
    """One question's page. `link` builds cross-references; `h` is the top heading level."""
    q, methods = Q[qid], methods_of(qid)
    red = q.get("reduces_to")
    out = [f"{h} {q['title']}", "", f"`{qid}` · {q['kind']} · prompt: *{q['prompt']}*", ""]
    if red:
        out += [f"Reduces to [{red['question']}]({link(red['question'])}) with `{json.dumps(red['with'])}`. "
                + (red.get("note") or ""), ""]
    if uses(qid):
        out += ["Uses: " + ", ".join(f"[{u}]({link(u)})" for u in sorted(uses(qid))), ""]
    out += ["| Method | Idea | Steps use |", "|---|---|---|"]
    for mid, m in methods.items():
        u = sorted({s["question"] for s in m["steps"] if s["op"] == "use"} - ({red["question"]} if red else set()))
        core = f" (= {red['question']} · {m['core_method']})" if m.get("core_method") else ""
        out.append(f"| **{m['name']}** `{mid}`{core} | {render(m.get('idea', ''), {})} | {', '.join(u) or '—'} |")
    out += ["", "Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, "
            "**purple** = second step (only where methods share a first step); **yellow** = method; "
            "**green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.", ""]
    for ex in q["examples"]:
        graph, na = example_graph(qid, ex, variants)
        out += [f"{h}# {render(q['prompt'], ex['values'])}", "", "```mermaid", graph, "```", ""]
        if na:
            out += ["Not applicable here: " + ", ".join(f"{methods[m]['name']} (`{m}`)" for m in na), ""]
    return "\n".join(out)


REPORT_INTRO = """# Solving arithmetic problems: methods classified by first step

Most arithmetic questions can be solved in several ways. This report catalogs the methods for a family of
ratio, fraction, and percent questions and classifies each method by **the first step a student takes**,
using the second step only when methods share a first step. The goal is an app that recognizes a student's
method from what they write first and responds with help for *that* method.

## How the data is organized

- **Skills** are small questions that other methods call as steps: simplify a fraction, write it as a decimal,
  find a common multiple, cross products. Each has its own methods (a common multiple can be recalled, found by
  listing multiples, by multiplying, or from the GCF).
- **Core questions** (compare fractions, missing value, add fractions) have methods built from primitive steps
  and skill calls.
- **Applied questions** are core questions in context: a proportion check *is* comparing fractions for equality,
  a better buy *is* comparing price ÷ quantity, and a percent of a number *is* a missing value with denominator 100.

The first-step trees are not written by hand: `v2/build.py` expands every skill call into every combination of
skill methods, runs each variant on the examples to check the answer, and groups variants by their first step,
then by their second where needed. The hand-written version this replaced is in `v1/` for comparison.

## What expanding the skills revealed

Shared first steps that the hand-written v1 tree missed, because they only appear once skills are expanded:

- In *compare fractions*, `3 × 7` starts both **cross-multiply** and **rewrite one fraction over the other's
  denominator** (through missing value's cross-multiply). The next step decides: `5 × 4` vs `21 ÷ 4`.
- In *proportion check*, `6 ÷ 8` starts both **decimal** and **rewrite over the other's denominator**,
  and `GCF(6, 8)` starts both **simplify** and the same rewrite.
- `3 × 5 = 15` can come from **listing multiples** or from **multiplying**; the graphs show it as one node
  linked from both classes.

Known limit: the generated trees store a student-chosen multiplier as a wildcard, so a typed classifier sees
`4 × 25` as matching three methods. The per-example graphs tell those apart by value.

## Reading the graphs

Each example graph reads left to right: question → **hexagons** grouping first steps by operation · scope →
**blue** first step → **purple** second step (only where methods share a first step) → **yellow** method →
the method's steps, where a **green dashed** box is a call to another question (it has its own section) →
answer. Edge labels name the skill method that produced the step.

## How the questions reuse each other
"""


def index_md():
    lines = ["flowchart LR"]
    kinds = {"skill": [], "core": [], "applied": []}
    for qid, q in Q.items():
        lines.append(f'  {qid.replace("-", "_")}["{esc(q["title"])}"]')
        kinds[q["kind"]].append(qid.replace("-", "_"))
    for qid, q in Q.items():
        for u in sorted(uses(qid) - {qid}):
            lines.append(f"  {qid.replace('-', '_')} --> {u.replace('-', '_')}")
        if q.get("reduces_to"):
            lines.append(f"  {qid.replace('-', '_')} -.->|is a| {q['reduces_to']['question'].replace('-', '_')}")
    lines += ["  classDef skill fill:#e3f4e6,stroke:#3f9a55,color:#222",
              "  classDef core fill:#fff1cc,stroke:#c99a1a,color:#222",
              "  classDef applied fill:#e3edfd,stroke:#5b7fd1,color:#222"]
    lines += [f"  class {','.join(v)} {k}" for k, v in kinds.items() if v]
    body = ["# Question graphs (v2)", "",
            "How the questions reuse each other. Green = skill, yellow = core, blue = applied. "
            "Solid arrows: a method calls that question as a step. Dotted arrows: the applied question *is* the core question in context. "
            "(compare-fractions also calls itself: *distance from 1* ends by comparing the two gaps.)",
            "", "```mermaid", "\n".join(lines), "```", "", "| Question | Kind | Methods | Uses |", "|---|---|---|---|"]
    for qid, q in Q.items():
        u = sorted(uses(qid) | ({q["reduces_to"]["question"]} if q.get("reduces_to") else set()))
        body.append(f"| [{q['title']}]({qid}.md) | {q['kind']} | {len(methods_of(qid))} | {', '.join(u) or '—'} |")
    return "\n".join(body) + "\n"


# ---------------------------------------------------------------- validation

def check_refs():
    ok = True
    for qid, q in Q.items():
        for mid, m in methods_of(qid).items():
            for s in m["steps"]:
                if s["op"] != "use":
                    continue
                child = Q.get(s["question"])
                if not child:
                    print(f"  ERROR {qid}/{mid} uses unknown question {s['question']}")
                    ok = False
                    continue
                if set(s["with"]) != set(child["inputs"]):
                    print(f"  ERROR {qid}/{mid} → {s['question']}: inputs {sorted(s['with'])} ≠ {sorted(child['inputs'])}")
                    ok = False
                if not set(s["out"]) <= set(child["outputs"]):
                    print(f"  ERROR {qid}/{mid} → {s['question']}: unknown outputs {set(s['out']) - set(child['outputs'])}")
                    ok = False
    return ok


def validate(qid, variants):
    q, methods = Q[qid], methods_of(qid)
    ok = True
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
            detail = f"{shown}  ({good}/{len(vs)} variants apply)" if good else "not applicable"
            print(f"    {status} {mid:22s} {detail}")
    return ok


# ---------------------------------------------------------------- classifier demo

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
            return ("int",)  # a step built on a wildcard: accept any number
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


def rename_expr(expr, mapping):
    return re.sub(r"[A-Za-z_]\w*", lambda m: mapping.get(m[0], m[0]), expr)


def find(entries, op, nums, values, symmetries):
    hits = []
    for e in entries:
        if e["match"]["op"] != op:
            continue
        for mapping in [{}] + symmetries:
            try:
                pats = [ev(rename_expr(a, mapping), values) for a in e["match"]["args"]]
            except (KeyError, NotApplicable):
                continue
            orders = itertools.permutations(nums) if op in COMMUTATIVE else [nums]
            if any(all(fits(p, n) for p, n in zip(pats, o)) for o in orders):
                wild = sum("int" in a or "common_factor" in a for a in e["match"]["args"])
                hits.append((wild, e))
                break
    if not hits:
        return []
    best = min(w for w, _ in hits)
    return [e for w, e in hits if w == best]


def classify(qid, values, steps):
    tree = json.loads((ROOT / "trees" / f"{qid}.json").read_text())
    vals = {k: num(v) for k, v in values.items()}
    sym = Q[qid].get("symmetries", [])
    entries, trail = tree["first_steps"], []
    for text in steps:
        op, nums = parse(text)
        hits = find(entries, op, nums, vals, sym)
        methods = sorted({m for e in hits for m in e["methods"]})
        trail.append(f"{text} ⇒ {methods or 'unrecognized'}")
        nexts = [n for e in hits for n in e.get("next", [])]
        if len(methods) <= 1 or not nexts:
            break
        entries = nexts
    return " → ".join(trail)


DEMOS = [
    ("proportion-check", ["6 / 8"]), ("proportion-check", ["8 ÷ 6"]), ("proportion-check", ["72 ÷ 6"]),
    ("proportion-check", ["gcf(6, 8)"]), ("proportion-check", ["72 ÷ 2"]), ("proportion-check", ["96 x 6"]),
    ("compare-fractions", ["3 x 7", "5 x 4"]), ("compare-fractions", ["3 x 7", "21 / 4"]),
    ("compare-fractions", ["3 / 4", "5 / 7"]), ("compare-fractions", ["3 / 4", "0.75 x 7"]),
    ("compare-fractions", ["lcm(4, 7)"]), ("compare-fractions", ["4 x 7"]), ("compare-fractions", ["4 x 25"]),
    ("missing-value", ["40 / 5"]), ("better-buy", ["3 / 12"]), ("better-buy", ["20 / 12"]),
    ("percent-of", ["15 / 100", "0.15 x 80"]), ("percent-of", ["0.15 x 80"]), ("percent-of", ["80 / 100"]),
    ("percent-of", ["gcf(15, 100)"]), ("percent-of", ["80 / 10"]), ("percent-of", ["15 x 80"]),
    ("add-fractions", ["lcm(6, 4)"]), ("add-fractions", ["6 x 4"]), ("add-fractions", ["5 x 4"]),
]


# ---------------------------------------------------------------- main

def report_md(pages, infos):
    anchor = lambda u: f"#{u}"
    order = [k for kind in ("core", "applied", "skill") for k, q in Q.items() if q["kind"] == kind]
    index = index_md().split("```mermaid", 1)[1].split("```", 1)[0]
    body = [REPORT_INTRO, "```mermaid" + index + "```", "",
            "| Question | Kind | Methods | Uses |", "|---|---|---|---|"]
    for qid in order:
        q = Q[qid]
        u = sorted(uses(qid) | ({q["reduces_to"]["question"]} if q.get("reduces_to") else set()))
        body.append(f"| [{q['title']}](#{qid}) | {q['kind']} | {len(methods_of(qid))} | "
                    + (", ".join(f"[{x}](#{x})" for x in u) or "—") + " |")
    body += ["", "## Contents", ""] + [f"- [{Q[k]['title']}](#{k}) ({Q[k]['kind']})" for k in order]
    body += ["- [Word problems](#word-problems): extraction concepts and 12 stories", ""]
    for qid in order:
        body += [f'<a name="{qid}"></a>', "", pages[qid](anchor), ""]
    body += [word_problems_md(infos, lambda u: f"#{u}", "##"), ""]
    body += ["## Rebuilding", "", "```sh", "cd v2 && python3 build.py --demo", "```", "",
             "This checks every method variant against every example, regenerates `v2/trees/`, `v2/graphs/` "
             "and this report, and runs the classifier on sample student steps.", ""]
    return "\n".join(body)


# ---------------------------------------------------------------- word problems

EXTRACTION = json.loads((ROOT / "extraction.json").read_text())
WP = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "word-problems").glob("*.json"))}
_variants_cache = {}


def cached_variants(qid):
    if qid not in _variants_cache:
        _variants_cache[qid] = variants_of(qid)
    return _variants_cache[qid]


def wp_context(wp):
    """Values as used (after any derive step) and as written."""
    raw = {q["id"]: num(q["value"]) for q in wp["quantities"]}
    vals = {q["id"]: wp_eval(q["derive"]["expr"], raw, raw) if "derive" in q else raw[q["id"]] for q in wp["quantities"]}
    return vals, raw


def wp_eval(expr, vals, raw):
    """Evaluate a mapping expression: a quantity id, a number, or op(args) incl. num(), den(), raw()."""
    if not isinstance(expr, str):
        return num(expr)
    expr = expr.strip()
    m = re.fullmatch(r"(\w+)\((.*)\)", expr)
    if m:
        if m[1] == "raw":
            return raw[m[2].strip()]
        args = [wp_eval(a, vals, raw) for a in split_top(m[2])]
        if m[1] == "num":
            return Fraction(args[0].numerator)
        if m[1] == "den":
            return Fraction(args[0].denominator)
        return apply_op(m[1], *args)
    if re.fullmatch(r"[\d.]+", expr):
        return num(expr)
    return vals[expr]


def solve(qid, values, main_route_only=False):
    """Answer from the first applicable variant (defaults first), plus first steps a solver could take:
    from every variant, or only each method's main route (its first applicable variant)."""
    answer, firsts, seen = None, {}, set()
    for v in cached_variants(qid):
        if main_route_only and v["method"] in seen:
            continue
        try:
            env, trace = run(v["steps"], values)
        except NotApplicable:
            continue
        seen.add(v["method"])
        if answer is None:
            answer = outputs_of(qid, env)
        vis = visible(trace)
        if vis:
            firsts.setdefault(label_key(*vis[0]), {"label": label(*vis[0]), "methods": set()})["methods"].add(v["method"])
    return answer, firsts



def interpret(wp, reading, is_trap=False):
    """Final answer (and first steps) for the correct reading or a trap."""
    vals, raw = wp_context(wp)
    firsts, inputs = {}, None
    if "expr" in reading:
        result = wp_eval(reading["expr"], vals, raw)
    elif "answer" in reading and "maps_to" not in reading:
        result = reading["answer"]
    else:
        mt = reading["maps_to"]
        inputs = {k: wp_eval(e, vals, raw) for k, e in mt["with"].items()}
        result, firsts = solve(mt["question"], inputs, main_route_only=is_trap)
        if is_trap and any(not isinstance(e, str) for e in mt["with"].values()):
            firsts = {}  # a count encoded as count/1 isn't a real reading of the methods; diagnose by answer
        amap = mt.get("answer_map", wp["maps_to"].get("answer_map"))
        if isinstance(result, str) and amap:
            result = amap.get(result, result)
    if reading.get("then"):
        result = wp_eval(reading["then"]["expr"], {**vals, "result": result}, raw)
    return result, firsts, inputs


def same_answer(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    return num(a) == num(b)


def check_word_problem(wp):
    """Returns (ok, report dict)."""
    vals, raw = wp_context(wp)
    result, firsts, inputs = interpret(wp, wp)
    ok = same_answer(result, wp["answer"])
    traps = []
    for t in wp.get("traps", []):
        tr, tfirsts, tinputs = interpret(wp, t, is_trap=True)
        traps.append({**t, "computed": tr, "inputs": tinputs, "firsts": tfirsts,
                      "same_as_correct": same_answer(tr, result)})
    for c in wp["concepts"] + [t["concept"] for t in wp.get("traps", [])]:
        if c not in EXTRACTION["concepts"]:
            print(f"  ERROR {wp['id']}: unknown concept {c}")
            ok = False
    mt = wp["maps_to"]
    if set(mt["with"]) != set(Q[mt["question"]]["inputs"]):
        print(f"  ERROR {wp['id']}: maps_to inputs don't match {mt['question']}")
        ok = False
    return ok, {"result": result, "firsts": firsts, "inputs": inputs, "traps": traps}


def diagnostic_firsts(info):
    """First steps that only a trap reading produces: seeing one tells you which extraction went wrong."""
    correct = set(info["firsts"])
    out = {}
    for t in info["traps"]:
        for key, f in t["firsts"].items():
            if key not in correct:
                out.setdefault(f["label"], []).append(t["mistake"])
    return out


def word_problem_graph(wp, info):
    """Story → quantities (→ conversion steps) → the mapped question's full method graph → follow-up step → answer.
    Traps hang off the story with the first steps that give each one away."""
    lines = ["flowchart LR"]
    ids = itertools.count()
    nid = lambda: f"w{next(ids)}"
    styles = {"wstory": [], "wused": [], "wdist": [], "wop": [], "wfinal": [], "wtrap": [], "wtfirst": []}

    def node(kind, text, o="[", c="]"):
        n = nid()
        lines.append(f'  {n}{o}"{esc(text)}"{c}')
        styles[kind].append(n)
        return n

    def build(expr, nodes, values, raw, note=""):
        """Draw an expression as operation nodes; returns (node feeding the result or None, value)."""
        if not isinstance(expr, str) or re.fullmatch(r"[\d.]+", expr.strip()):
            return None, num(expr)
        expr = expr.strip()
        m = re.fullmatch(r"(\w+)\((.*)\)", expr)
        if not m:
            return nodes[expr], values[expr]
        if m[1] == "raw":
            return nodes[m[2].strip()], raw[m[2].strip()]
        parts = [build(a, nodes, values, raw) for a in split_top(m[2])]
        if m[1] in ("num", "den"):
            v = parts[0][1]
            return parts[0][0], Fraction(v.numerator if m[1] == "num" else v.denominator)
        x, y = parts[0][1], parts[1][1]
        result = apply_op(m[1], x, y)
        on = node("wop", label({"op": m[1]}, [x, y], result) + (f" ({note})" if note else ""))
        for src, _ in parts:
            if src:
                lines.append(f"  {src} --> {on}")
        return on, result

    vals, raw = wp_context(wp)
    mt = wp["maps_to"]
    qid = mt["question"]
    story = node("wstory", wp["title"], "([", "])")

    # quantities, with conversion steps drawn as operations
    effective = {}
    for q in wp["quantities"]:
        distract = q["role"] == "distractor"
        qn = node("wdist" if distract else "wused", q["text"] + (" (not needed)" if distract else ""))
        lines.append(f"  {story} --> {qn}")
        effective[q["id"]] = qn
        if "derive" in q:
            effective[q["id"]], _ = build(q["derive"]["expr"], {q["id"]: qn}, raw, raw, q["derive"].get("note", ""))

    # the mapped question, drawn with every method's operations
    core, _, _ = interpret(wp, {"maps_to": mt})
    ex = {"values": {k: fmt(v) for k, v in info["inputs"].items()}, "answer": core if isinstance(core, str) else fmt(core)}
    body, _, root, answer = example_graph_parts(qid, ex, cached_variants(qid), prefix="c")
    lines += body
    for k, e in mt["with"].items():
        src, _ = build(e, effective, vals, raw)
        if src:
            lines.append(f'  {src} -->|"{k}"| {root}')

    # follow-up step and the answer in the story's terms
    last = answer
    if wp.get("then"):
        last, _ = build(wp["then"]["expr"], {**effective, "result": answer}, {**vals, "result": core}, raw,
                        wp["then"].get("note", ""))
    final = node("wfinal", wp["answer_text"], "([", "])")
    lines.append(f"  {last} --> {final}")

    # traps and the first steps that give them away
    correct = set(info["firsts"])
    for t in info["traps"]:
        shown = t["computed"] if isinstance(t["computed"], str) else fmt(t["computed"])
        tn = node("wtrap", f"{t['mistake']} → {shown}" + (" (same answer!)" if t["same_as_correct"] else ""))
        lines.append(f'  {story} -.->|"{esc(EXTRACTION["concepts"][t["concept"]]["name"])}"| {tn}')
        tells = [f["label"] for key, f in t["firsts"].items() if key not in correct][:4]
        for lab in tells:
            fn = node("wtfirst", lab)
            lines.append(f"  {tn} -.-> {fn}")

    lines += [
        "  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222",
        "  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222",
        "  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222",
        "  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold",
        "  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222",
        "  classDef step fill:#ffffff,stroke:#999,color:#222",
        "  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222",
        "  classDef wstory fill:#fde4e1,stroke:#c4554a,color:#222",
        "  classDef wused fill:#dbe9ff,stroke:#3d6fd1,color:#222",
        "  classDef wdist fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777",
        "  classDef wop fill:#ffffff,stroke:#3d6fd1,color:#222",
        "  classDef wfinal fill:#d4f0da,stroke:#2f8a45,color:#222,font-weight:bold",
        "  classDef wtrap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33",
        "  classDef wtfirst fill:#fff5f4,stroke:#c4554a,stroke-dasharray:2 2,color:#a33",
    ]
    lines += [f"  class {','.join(v)} {k}" for k, v in styles.items() if v]
    return "\n".join(lines)


def word_problems_md(infos, link=lambda u: f"{u}.md", h="#"):
    c = EXTRACTION["concepts"]
    out = [f"{h} Word problems", "",
           "A word problem needs **extraction** before any method applies: pull out the quantities, drop the "
           "distractors, pair the right numbers in the right order, and recognize which question the story is. "
           "Each problem below maps to one of the questions above; its **traps** are common wrong extractions, "
           "written as alternative mappings so the wrong answer each one produces is computed, not guessed. "
           "That lets an app diagnose an extraction mistake from a student's answer, and often from their first step.", "",
           "Each graph drills from the story down to the arithmetic: **story** → its **quantities** (grey dashed = not needed; "
           "white boxes are arithmetic steps, such as converting 2 dozen to 24) → the mapped question with **every method's "
           "first steps and operations**, exactly as in the question graphs → the **follow-up step**, if any → the "
           "**answer in the story's terms** (green). **Red dashed** branches are traps, each with the first steps "
           "that give it away (steps no correct reading starts with).", "",
           f"{h}# Extraction concepts", "", "| Concept | What the student does | Cues | Typical mistake |", "|---|---|---|---|"]
    for k, v in c.items():
        out.append(f"| **{v['name']}** `{k}` | {v['does']} | {'; '.join(v.get('cues', [])) or '—'} | {v.get('mistake', '—')} |")
    out += ["", "| Word problem | Maps to | Concepts |", "|---|---|---|"]
    for wid, wp in WP.items():
        out.append(f"| [{wp['title']}](#{wid}) | [{wp['maps_to']['question']}]({link(wp['maps_to']['question'])}) | "
                   + ", ".join(c[x]["name"] for x in wp["concepts"]) + " |")
    out.append("")
    for wid, wp in WP.items():
        info = infos[wid]
        mt = wp["maps_to"]
        out += [f'<a name="{wid}"></a>', "", f"{h}# {wp['title']}", "", f"> {wp['text']}", "",
                "| Phrase | Value | Counts | Role |", "|---|---|---|---|"]
        for q in wp["quantities"]:
            val = q["value"]
            if "derive" in q:
                vals, raw = wp_context(wp)
                val = f"{q['value']} {q['unit']} → **{fmt(vals[q['id']])}** ({q['derive'].get('note', q['derive']['expr'])})"
            out.append(f"| “{q['text']}” | {val} | {q['counts']} | {q['role']} |")
        out += ["", f"**Asked:** {wp['unknown']['text']} ({wp['unknown']['unit'] or wp['unknown']['counts']}). "
                f"**Link:** “{wp['relationship']['cue']}”: {wp['relationship']['note']}", "",
                f"**Maps to** [{mt['question']}]({link(mt['question'])}): "
                + ", ".join(f"{k} = {fmt(v)}" for k, v in info["inputs"].items())
                + (f", then {wp['then'].get('note') or wp['then']['expr']}" if wp.get("then") else "")
                + f". **Answer:** {wp['answer_text']}.", "",
                "```mermaid", word_problem_graph(wp, info), "```", "",
                "| Trap | Mistake | Gives | Caught by the answer? |", "|---|---|---|---|"]
        for t in info["traps"]:
            shown = t["computed"] if isinstance(t["computed"], str) else fmt(t["computed"])
            out.append(f"| {c[t['concept']]['name']} | {t['mistake']} | {shown} | "
                       + ("**no**: same answer, so ask how they got it" if t["same_as_correct"] else "yes") + " |")
        diag = diagnostic_firsts(info)
        if diag:
            out += ["", "First steps that give a trap away (each method's main route under the wrong reading; "
                    "no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.", "",
                    "| Student's first step | Suggests |", "|---|---|"]
            out += [f"| `{lab}` | {' / '.join(ms)} |" for lab, ms in sorted(diag.items())]
        out.append("")
    return "\n".join(out)


def main():
    ok = check_refs()
    pages = {}
    (ROOT / "trees").mkdir(exist_ok=True)
    (ROOT / "graphs").mkdir(exist_ok=True)
    for qid in Q:
        variants = variants_of(qid)
        ok &= validate(qid, variants)
        (ROOT / "trees" / f"{qid}.json").write_text(json.dumps(build_tree(qid, variants), indent=2, ensure_ascii=False) + "\n")
        (ROOT / "graphs" / f"{qid}.md").write_text(question_md(qid, variants))
        pages[qid] = lambda link, qid=qid, variants=variants: question_md(qid, variants, link, "##")
    (ROOT / "graphs" / "README.md").write_text(index_md())
    print(f"\n== word problems: {len(WP)}")
    infos = {}
    for wid, wp in WP.items():
        wok, info = check_word_problem(wp)
        ok &= wok
        infos[wid] = info
        res = info["result"] if isinstance(info["result"], str) else fmt(info["result"])
        print(f"  {'ok ' if wok else 'BAD'} {wid:22s} {res:18s} traps: "
              + ", ".join((t["computed"] if isinstance(t["computed"], str) else fmt(t["computed"]))
                          + ("(=!)" if t["same_as_correct"] else "") for t in info["traps"]))
    (ROOT / "trees" / "word-problems.json").write_text(json.dumps({
        wid: {"maps_to": WP[wid]["maps_to"]["question"],
              "inputs": {k: fmt(v) for k, v in i["inputs"].items()},
              "answer": i["result"] if isinstance(i["result"], str) else fmt(i["result"]),
              "traps": [{"concept": t["concept"], "mistake": t["mistake"],
                         "answer": t["computed"] if isinstance(t["computed"], str) else fmt(t["computed"]),
                         "caught_by_answer": not t["same_as_correct"]} for t in i["traps"]],
              "first_steps_revealing_traps": diagnostic_firsts(i)}
        for wid, i in infos.items()}, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "graphs" / "word-problems.md").write_text(word_problems_md(infos))
    (ROOT.parent / "REPORT.md").write_text(report_md(pages, infos))
    if "--demo" in sys.argv:
        print("\n== Classifier demo (first example of each question)")
        for qid, steps in DEMOS:
            ex = Q[qid]["examples"][0]
            print(f"  [{ex['id']}] {classify(qid, ex['values'], steps)}")
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
