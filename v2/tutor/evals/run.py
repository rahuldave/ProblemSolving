"""Score the Talk-it-through interpreter against the eval cases.

    cd v2 && uv run python -m tutor.evals.run                    # every case (calls the API)
    uv run python -m tutor.evals.run --category find_method       # one category (repeatable)
    uv run python -m tutor.evals.run --limit 10                   # the first 10 cases
    uv run python -m tutor.evals.run --dry                        # resolve every case and check it, no API calls

Each case (cases.json) names a problem, a state reached the way the automatic student reaches it (states.reach), a
student utterance and the typed inputs a careful human would read from it. A case passes when Claude's inputs,
normalized, equal the expected ones exactly, in order. Operand order is ignored only for commutative operations
(add, multiply, gcf, lcm), `a > b` equals `b < a`, and numbers compare by exact value (0.667 is not 2/3).
`find_method` cases also report whether feeding Claude's inputs leaves the session on the same methods as feeding the
expected ones (method identification). Results, with every failure, go to results/<timestamp>.json.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

from .. import ai
from ..session import WordProblemSession

HERE = Path(__file__).parent
COMMUTATIVE = {"add", "multiply", "gcf", "lcm"}


def normalize_key(inp, decision=None) -> tuple:
    """A typed input as a comparable tuple."""
    v = lambda n: n.value
    k = inp.kind
    if k == "arithmetic" or k == "function":
        op = inp.op if k == "arithmetic" else inp.name
        ops = (v(inp.left), v(inp.right))
        if op in COMMUTATIVE:
            ops = tuple(sorted(ops))
        return (op, ops, v(inp.result) if inp.result is not None else None)
    if k == "compare":
        a, rel, b = v(inp.left), inp.relation, v(inp.right)
        if rel == ">":
            a, rel, b = b, "<", a
        if rel == "=":
            a, b = sorted((a, b))
        return ("compare", a, rel, b)
    if k == "ratio_compare":
        pairs = sorted(((v(inp.left[0]), v(inp.left[1])), (v(inp.right[0]), v(inp.right[1]))))
        return ("ratio_compare", inp.relation, tuple(pairs))
    if k == "plot":
        return ("plot", tuple(sorted((v(x), v(y)) for x, y in inp.points)))
    if k == "choice":
        return ("choice", decision or 1, inp.index)
    return ("value", v(inp.value))


def show_key(key) -> str:
    def f(x):
        if isinstance(x, Fraction):
            return str(x.numerator) if x.denominator == 1 else (f"{float(x):g}" if (10 ** 6 * x).denominator == 1 else str(x))
        if isinstance(x, tuple):
            return "(" + ", ".join(f(y) for y in x) + ")"
        return str(x)
    return " ".join(f(x) for x in key)


def methods_after(problem, at, inputs, decisions):
    """The live methods once these inputs are fed to a fresh copy of the state."""
    from .states import reach
    s = reach(problem, at)
    ai.feed(s, inputs, decisions)
    q = s.question if isinstance(s, WordProblemSession) else s
    return sorted(q.live_methods()) if q is not None else []


def load(categories=None, limit=None):
    cases = json.loads((HERE / "cases.json").read_text())
    if categories:
        cases = [c for c in cases if c["category"] in categories]
    return cases[:limit] if limit else cases


def resolve(case):
    """The reached session and the expected normalized inputs for a case."""
    from .states import expected, reach
    s = reach(case["problem"], case["at"])
    return s, expected(s, case["expect"])


def dry(cases) -> int:
    """Check every case resolves; for find_method cases, that the expected inputs identify the named method."""
    from ..parse import parse
    bad = 0
    for c in cases:
        try:
            s, exp = resolve(c)
            if c.get("method"):
                steps = [parse(e) for e in c["expect"]]
                m = methods_after(c["problem"], c["at"], steps, [None] * len(steps))
                assert c["method"] in m, (c["method"], m)
        except Exception as e:  # noqa: BLE001 - report every broken case
            bad += 1
            print(f"BROKEN {c['id']}: {e!r}")
    print(f"{len(cases) - bad}/{len(cases)} cases resolve")
    return bad


def run_case(case, client=None):
    s, exp = resolve(case)
    ctx = ai.context(s)
    reading = ai.interpret(s, case["say"], client)
    phase_extract = isinstance(s, WordProblemSession) and s.phase == "extract"
    got = [normalize_key(i, d if phase_extract else None) for i, d in zip(reading.inputs, reading.decisions)]
    invalid = len(reading.raw) - len(reading.inputs)
    ok = got == exp and not reading.error and invalid == 0
    out = {"id": case["id"], "category": case["category"], "problem": case["problem"], "say": case["say"],
           "ok": ok, "expected": [show_key(k) for k in exp], "got": [show_key(k) for k in got], "raw": reading.raw,
           "note": reading.note, "error": reading.error, "usage": reading.usage, "seconds": round(reading.seconds, 2),
           "context": ctx}
    if case.get("method"):
        from ..parse import parse
        steps = [parse(e) for e in case["expect"]]
        want = methods_after(case["problem"], case["at"], steps, [None] * len(steps))
        have = methods_after(case["problem"], case["at"], reading.inputs, reading.decisions) if reading.inputs else None
        out["method_ok"] = have == want
        out["methods"] = {"expected": want, "got": have}
    return out


def table(results) -> str:
    by = defaultdict(list)
    for r in results:
        by[r["category"]].append(r)
    rows = [("category", "pass", "n", "%")]
    for cat, rs in by.items():
        p = sum(r["ok"] for r in rs)
        rows.append((cat, str(p), str(len(rs)), f"{100 * p / len(rs):.0f}"))
    p = sum(r["ok"] for r in results)
    rows.append(("TOTAL", str(p), str(len(results)), f"{100 * p / max(1, len(results)):.0f}"))
    meth = [r for r in results if "method_ok" in r]
    if meth:
        mp = sum(r["method_ok"] for r in meth)
        rows.append(("method identified", str(mp), str(len(meth)), f"{100 * mp / len(meth):.0f}"))
    w = [max(len(r[i]) for r in rows) for i in range(4)]
    return "\n".join("  ".join(c.ljust(w[i]) if i == 0 else c.rjust(w[i]) for i, c in enumerate(r)) for r in rows)


def totals(results) -> dict:
    t = defaultdict(float)
    for r in results:
        for k, v in (r["usage"] or {}).items():
            t[k] += v
    secs = sorted(r["seconds"] for r in results if r["seconds"])
    t["calls"] = len(results)
    t["median_seconds"] = secs[len(secs) // 2] if secs else 0
    t["p90_seconds"] = secs[int(len(secs) * 0.9)] if secs else 0
    return dict(t)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category", action="append", help="only this category (repeatable)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry", action="store_true", help="resolve and check the cases without calling the API")
    ap.add_argument("--label", default="", help="a short tag stored with the results")
    a = ap.parse_args(argv)
    cases = load(a.category, a.limit)
    if a.dry:
        return 1 if dry(cases) else 0
    if not ai.configured():
        print("No ANTHROPIC_API_KEY (or .env); nothing to run. Use --dry to check the cases.")
        return 2
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as pool:
        results = list(pool.map(run_case, cases))
    print(table(results))
    t = totals(results)
    print(f"\n{t['calls']} calls in {time.time() - t0:.0f}s · median {t['median_seconds']:.1f}s, p90 {t['p90_seconds']:.1f}s per call")
    print(f"tokens: input {t.get('input_tokens', 0):.0f}, output {t.get('output_tokens', 0):.0f}, "
          f"cache write {t.get('cache_creation_input_tokens', 0):.0f}, cache read {t.get('cache_read_input_tokens', 0):.0f}"
          f" · cost ${t.get('cost_usd', 0):.3f} (${t.get('cost_usd', 0) / max(1, t['calls']):.4f}/call)")
    fails = [r for r in results if not r["ok"] or r.get("method_ok") is False]
    for r in fails:
        print(f"  FAIL {r['id']} [{r['category']}] “{r['say']}”\n       want {r['expected']}\n       got  {r['got']}"
              + (f"  note: {r['note']}" if r["note"] else "") + (f"  error: {r['error']}" if r["error"] else "")
              + (f"  methods {r['methods']}" if r.get("method_ok") is False else ""))
    out = HERE / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    summary = {"label": a.label, "model": ai.MODEL, "categories": a.category, "limit": a.limit, "table": table(results),
               "totals": t, "failures": fails,
               "passed": [r["id"] for r in results if r["ok"] and r.get("method_ok") is not False]}
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    print(f"\nwrote {out.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
