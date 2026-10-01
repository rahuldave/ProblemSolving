"""Validate methods.json and demo first-step classification.

Usage: python3 check_methods.py
"""

import itertools
import json
import math
import re
from fractions import Fraction
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "methods.json").read_text())
OPS = DATA["vocabulary"]["operations"]


class NotApplicable(Exception):
    pass


def num(v):
    return Fraction(str(v))


def apply_op(op, x, y):
    if op == "add":
        return x + y
    if op == "subtract":
        return x - y
    if op == "multiply":
        return x * y
    if op == "divide":
        return x / y
    if op in ("gcf", "lcm", "floor_div", "mod"):
        if x.denominator != 1 or y.denominator != 1:
            raise NotApplicable(f"{op} needs whole numbers")
        x, y = int(x), int(y)
        return Fraction({"gcf": math.gcd(x, y), "lcm": math.lcm(x, y),
                         "floor_div": x // y, "mod": x % y}[op])
    raise ValueError(op)


def resolve(arg, env):
    if isinstance(arg, (int, float)):
        return Fraction(arg)
    if isinstance(arg, list):
        return tuple(resolve(a, env) for a in arg)
    return env[arg]


def relation(x, y):
    if isinstance(x, tuple):
        return "=" if x == y else "≠"
    return "=" if x == y else ("<" if x < y else ">")


def run_method(method, values):
    env = {k: num(v) for k, v in values.items()}
    for step in method["steps"]:
        op = step["op"]
        if op == "plot":
            continue
        if "search" in step:
            var, (out, target) = step["search"]["var"], step["search"]["until"]
            other = next(a for a in step["args"] if a != var)
            k = resolve(target, env) / resolve(other, env)
            if k.denominator != 1 or k < 1:
                raise NotApplicable(f"no whole-number {var} makes {other}×{var} = {target}")
            env[var] = k
        if op == "compare":
            x, y = (resolve(a, env) for a in step["args"])
            rel = relation(x, y)
            meaning = step["meaning"]
            env[step["out"]] = meaning.get(rel) or meaning["≠"]
            continue
        x, y = (resolve(a, env) for a in step["args"])
        result = apply_op(op, x, y)
        if step.get("requires_integer") and result.denominator != 1:
            raise NotApplicable(f"{step['out']} = {result} is not whole")
        env[step["out"]] = result
    return env["answer"], env


def answers_match(got, expected):
    if isinstance(got, str):
        return got == expected
    return got == num(expected)


def iter_nodes(nodes, depth=1):
    for node in nodes:
        yield node, depth
        yield from iter_nodes(node.get("next", []), depth + 1)


def validate():
    problems_ok = True
    for pt in DATA["problem_types"]:
        print(f"\n== {pt['id']}: {pt['title']}")
        methods = pt["methods"]

        # Every node names real methods; every method is reachable from a first step.
        reachable = set()
        for node, _ in iter_nodes(pt["first_steps"]):
            for m in node["methods"]:
                if m not in methods:
                    print(f"  ERROR node references unknown method {m}")
                    problems_ok = False
                reachable.add(m)
        for m in methods:
            if m not in reachable:
                print(f"  ERROR method {m} is not reachable from any first step")
                problems_ok = False

        # Every method reaches the stated answer on every example.
        for ex in pt["examples"]:
            print(f"  example {ex['id']!r} → expected {ex['answer']}")
            for mid, method in methods.items():
                try:
                    got, _ = run_method(method, ex["values"])
                except NotApplicable as e:
                    print(f"    -   {mid:22s} not applicable ({e})")
                    continue
                ok = answers_match(got, ex["answer"])
                problems_ok &= ok
                print(f"    {'ok ' if ok else 'BAD'} {mid:22s} {got}")
    return problems_ok


# ---------------- classifier demo ----------------

TOKEN = re.compile(r"^\s*(gcf|lcm)\s*\(?\s*([\d.]+)\s*,?\s*([\d.]+)\s*\)?\s*$|"
                   r"^\s*([\d.]+)\s*([+\-*x×/÷])\s*([\d.]+)\s*$", re.I)
SYM_OP = {"+": "add", "-": "subtract", "*": "multiply", "x": "multiply",
          "×": "multiply", "/": "divide", "÷": "divide"}


def parse(text):
    if text.strip().lower().startswith("plot"):
        return "plot", []
    m = TOKEN.match(text)
    if not m:
        raise ValueError(f"can't parse {text!r}")
    if m.group(1):
        return m.group(1).lower(), [num(m.group(2)), num(m.group(3))]
    return SYM_OP[m.group(5).lower()], [num(m.group(4)), num(m.group(6))]


def arg_matches(pattern, value, env, mapping):
    if isinstance(pattern, dict):
        if value.denominator != 1:
            return False
        if pattern["any"] == "integer":
            return True
        if pattern["any"] == "common_factor":
            a, b = (resolve(mapping.get(x, x), env) for x in pattern["of"])
            return value > 1 and (a / value).denominator == 1 and (b / value).denominator == 1
    name = mapping.get(pattern, pattern) if isinstance(pattern, str) else pattern
    try:
        return resolve(name, env) == value
    except KeyError:
        return False


def node_matches(node, op, args, env, mappings):
    match = node["match"]
    if match["op"] != op:
        return False
    if op == "plot":
        return True
    orders = itertools.permutations(args) if OPS[op]["commutative"] else [args]
    for order in orders:
        for mapping in mappings:
            if all(arg_matches(p, v, env, mapping) for p, v in zip(match["args"], order)):
                return True
    return False


def wildcards(node):
    return sum(isinstance(a, dict) for a in node["match"].get("args", []))


def classify(pt, values, steps):
    env = {k: num(v) for k, v in values.items()}
    for name, d in pt.get("derived", {}).items():
        env[name] = apply_op(d["op"], resolve(d["args"][0], env), resolve(d["args"][1], env))
    mappings = [{}] + pt.get("symmetries", [])

    nodes, path = pt["first_steps"], []
    for text in steps:
        op, args = parse(text)
        hits = [n for n in nodes if node_matches(n, op, args, env, mappings)]
        if not hits:
            path.append((text, None))
            break
        best = min(wildcards(n) for n in hits)
        hits = [n for n in hits if wildcards(n) == best]
        methods = sorted({m for n in hits for m in n["methods"]})
        path.append((text, methods))
        node = hits[0]
        if "out" in node["match"]:
            env[node["match"]["out"]] = apply_op(op, *args)
        if len(methods) == 1 or "next" not in node:
            break
        nodes = node["next"]
    return path


DEMOS = [
    ("proportion-check", 0, ["6 / 8"]),
    ("proportion-check", 0, ["72 ÷ 6"]),
    ("proportion-check", 0, ["96 x 6"]),
    ("proportion-check", 0, ["6 ÷ 2"]),
    ("proportion-check", 0, ["8 ÷ 6"]),
    ("proportion-check", 0, ["6 x 3"]),
    ("compare-fractions", 0, ["3 x 7", "4 x 7"]),
    ("compare-fractions", 0, ["3 x 7", "5 x 4"]),
    ("compare-fractions", 0, ["lcm(3, 5)"]),
    ("missing-value", 1, ["15 / 6"]),
    ("better-buy", 0, ["4.50 / 20"]),
    ("percent-of", 0, ["15 / 100", "0.15 x 80"]),
    ("percent-of", 0, ["15 / 100", "gcf(15, 100)"]),
    ("percent-of", 0, ["0.15 * 80"]),
    ("percent-of", 0, ["80 / 10"]),
    ("add-fractions", 0, ["6 x 4"]),
    ("add-fractions", 0, ["lcm 6 4"]),
    ("add-fractions", 0, ["6 x 2"]),
]


def demo():
    print("\n== Classifier demo")
    by_id = {pt["id"]: pt for pt in DATA["problem_types"]}
    for pid, ex_i, steps in DEMOS:
        pt = by_id[pid]
        ex = pt["examples"][ex_i]
        trail = " → ".join(f"{t} ⇒ {m or 'unrecognized'}" for t, m in classify(pt, ex["values"], steps))
        print(f"  [{ex['id']}] {trail}")


if __name__ == "__main__":
    ok = validate()
    demo()
    print("\nALL METHODS CHECK OUT" if ok else "\nSOME CHECKS FAILED")
    raise SystemExit(0 if ok else 1)
