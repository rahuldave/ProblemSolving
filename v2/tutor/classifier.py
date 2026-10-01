"""Classify a student's step against the candidate next steps.

The input is concrete: a typed StudentStep and a list of Candidates with their values. The output says which
candidates the step is (or that it's on track toward a build-up step, or that it matches nothing), and whether the
student's arithmetic is right. Anything with this interface can replace RuleClassifier, e.g. a trained model.
"""

from fractions import Fraction
from typing import Protocol

from .models import Candidate, Classification, StudentStep

OPS = {"arithmetic": None, "function": None, "compare": "compare", "plot": "plot"}
COMMUTATIVE = {"add", "multiply", "gcf", "lcm"}


def is_wildcard(c: Candidate) -> bool:
    return any(isinstance(x, tuple) and x and x[0] in ("int", "cf") for x in c.operands)


class Classifier(Protocol):
    def classify(self, step: StudentStep, candidates: list[Candidate]) -> Classification: ...


def step_op(step) -> str:
    if step.kind == "arithmetic":
        return step.op
    if step.kind == "function":
        return step.name
    if step.kind == "ratio_compare":
        return "compare"
    return step.kind


def fits(pattern, number) -> bool:
    """Does a student's Number fit a candidate operand (a value or a wildcard)?"""
    if isinstance(pattern, tuple) and pattern and pattern[0] == "int":
        return number.value.denominator == 1
    if isinstance(pattern, tuple) and pattern and pattern[0] == "cf":
        _, x, y = pattern
        n = number.value
        return n > 1 and (x / n).denominator == 1 and (y / n).denominator == 1
    return number.close_to(pattern)


class RuleClassifier:
    """Exact matching: same operation, same numbers (either order where order doesn't matter)."""

    def classify(self, step: StudentStep, candidates: list[Candidate]) -> Classification:
        op = step_op(step)
        matched = [c for c in candidates if c.op == op and self._operands_fit(step, c)]
        exact = [c for c in matched if not is_wildcard(c)]
        matched = exact or matched  # an exact match beats a wildcard one (as in the trees' matching rules)
        if matched:
            return Classification(matched=[c.id for c in matched], status="match", **self._check(step, matched[0]))
        on_track = [c for c in candidates if c.search and op == "multiply" and self._toward(step, c)]
        if on_track:
            return Classification(matched=[c.id for c in on_track], status="on_track", **self._own_arithmetic(step))
        return Classification(status="none", **self._own_arithmetic(step))

    # -- matching

    def _operands_fit(self, step, c) -> bool:
        if step.kind == "plot":
            want = sorted((Fraction(x), Fraction(y)) for x, y in c.operands)
            got = sorted((x.value, y.value) for x, y in step.points)
            return want == got
        if step.kind == "ratio_compare" or any(isinstance(x, tuple) and len(x) == 2 and not isinstance(x[0], str)
                                               for x in c.operands):
            if step.kind != "ratio_compare":
                return False
            pairs = [tuple(x) for x in c.operands]
            got = [(n.value, d.value) for n, d in (step.left, step.right)]
            return sorted(pairs) == sorted(got)
        a, b = step.left, step.right
        x, y = c.operands
        if fits(x, a) and fits(y, b):
            return True
        return (c.op in COMMUTATIVE or c.op == "compare") and fits(x, b) and fits(y, a)

    def _toward(self, step, c) -> bool:
        """A build-up step on the way: base × some other whole number (6 × 2 while building toward 6 × 3 = 18)."""
        base, target = c.search["base"], c.search["target"]
        for n, k in ((step.left, step.right), (step.right, step.left)):
            if n.close_to(base) and k.value.denominator == 1 and 1 <= k.value and base * k.value < target:
                return True
        return False

    # -- arithmetic

    def _check(self, step, c) -> dict:
        if step.kind == "plot":
            return {"arithmetic_ok": True}
        if step.kind == "ratio_compare":
            return {"arithmetic_ok": step.relation == c.result, "expected_result": c.result}
        if step.kind == "compare":
            left_first = step.left.close_to(c.operands[0]) if not isinstance(c.operands[0], tuple) else True
            relation = c.result if left_first else {"<": ">", ">": "<"}.get(c.result, c.result)
            return {"arithmetic_ok": step.relation == relation, "expected_result": relation}
        if step.result is None or c.result is None or isinstance(c.result, str):
            return self._own_arithmetic(step)
        return {"arithmetic_ok": step.result.close_to(c.result), "expected_result": _fmt(c.result)}

    def _own_arithmetic(self, step) -> dict:
        """Check the student's arithmetic on their own numbers."""
        if step.kind == "ratio_compare":
            (a, b), (c, d) = ((n.value, m.value) for n, m in (step.left, step.right))
            rel = "=" if a * d == b * c else "≠"
            return {"arithmetic_ok": step.relation == rel, "expected_result": rel}
        if step.kind in ("plot",) or getattr(step, "result", None) is None:
            return {}
        if step.kind == "compare":
            a, b = step.left.value, step.right.value
            rel = "=" if a == b else "<" if a < b else ">"
            return {"arithmetic_ok": step.relation == rel, "expected_result": rel}
        a, b = step.left.value, step.right.value
        try:
            exact = {"add": a + b, "subtract": a - b, "multiply": a * b, "divide": a / b if b else None,
                     "gcf": _gcd(a, b), "lcm": _lcm(a, b)}[step_op(step)]
        except (TypeError, ValueError):
            return {}
        if exact is None:
            return {}
        return {"arithmetic_ok": step.result.close_to(exact), "expected_result": _fmt(exact)}


def _gcd(a, b):
    import math
    return Fraction(math.gcd(int(a), int(b))) if a.denominator == b.denominator == 1 else None


def _lcm(a, b):
    import math
    return Fraction(math.lcm(int(a), int(b))) if a.denominator == b.denominator == 1 else None


def _fmt(v) -> str:
    if isinstance(v, Fraction):
        if v.denominator == 1:
            return str(v.numerator)
        d = v.denominator
        for p in (2, 5):
            while d % p == 0:
                d //= p
        return str(float(v)) if d == 1 else f"{v.numerator}/{v.denominator} (≈ {float(v):.3f})"
    return str(v)
