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


def _terminates(v) -> bool:
    d = v.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    return d == 1


def is_fraction_text(text) -> bool:
    """Is a number written as a fraction? 3/4 and 1.5/2 are; 0.75/1 and 100/1 aren't (n/1 is n)."""
    if "/" not in text:
        return False
    try:
        return Fraction(text.split("/", 1)[1].strip()) != 1
    except (ValueError, ZeroDivisionError):
        return True


def two_steps(step) -> bool:
    """3 × 40/5 = 24, typed, reads left to right as two steps (3 × 40, then ÷ 5): a fraction written after ×
    that is a whole number (40/5 = 8, not n/1) isn't one number. Any other fraction is (15 × 4/5, 80 × 15/100,
    1 − 3/4), and so is every fraction from the boxes or Claude, where it is plainly one number."""
    return (step.kind == "arithmetic" and getattr(step, "typed", False) and step.op == "multiply"
            and "/" in step.right.text and step.right.value.denominator == 1
            and step.right.text.split("/", 1)[1].strip() not in ("1", "1.0"))


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
    """Exact matching: same operation, same numbers (either order where order doesn't matter). `strict`: a result
    that is a decimal that ends must be exact (to-decimal: 5 ÷ 8 = 0.6 is a slip)."""

    def __init__(self, strict=False, as_decimals=()):
        self.strict = strict
        self.as_decimals = set(as_decimals)  # methods whose point is writing the fractions as decimals
        self.exact_values = frozenset()  # the question's numbers and every route's: a typed decimal among them isn't
        # a rounding she carries (the session fills it in)

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
            if step.kind != "ratio_compare" or not all(isinstance(x, tuple) and len(x) == 2 for x in c.operands):
                return False  # a ratio comparison only fits a comparison of two ratios (not 21 > 20)
            pairs = [tuple(x) for x in c.operands]
            got = [(n.value, d.value) for n, d in (step.left, step.right)]
            return sorted(pairs) == sorted(got)
        if two_steps(step):
            return False
        if c.methods and set(c.methods) <= self.as_decimals and any(  # 3/4 written as a fraction isn't the 0.75
                is_fraction_text(n.text) and n.value.denominator != 1 and _terminates(n.value)  # of Convert to
                for n in (step.left, step.right)):                     # decimals, as an operand in either place
            return False                                                # (a result as a fraction fits, as on main)
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
        if self.strict and is_fraction_text(step.result.text):  # to-decimal: 5 ÷ 8 = 5/8 isn't a decimal
            return {"arithmetic_ok": False, "expected_result": _fmt(c.result)}
        ok = step.result.value == c.result if self.strict and _terminates(c.result) else step.result.close_to(c.result)
        return {"arithmetic_ok": ok, "expected_result": _fmt(c.result)}

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
        if self.strict and is_fraction_text(step.result.text):  # to-decimal: 5 ÷ 8 = 5/8 isn't a decimal
            return {"arithmetic_ok": False, "expected_result": _fmt(exact)}
        if step.result.close_to(exact) or _carried(step, exact, self.exact_values):
            return {"arithmetic_ok": True, "expected_result": _fmt(exact)}
        return {"arithmetic_ok": False, "expected_result": _fmt(exact)}


def _carried(step, exact, exact_values=frozenset()) -> bool:
    """3 × 1.67 = 5: an operand she rounded (1.67 for 5/3) carries its rounding into the result. The result is right
    when it is what the exact values her rounded operands stand for give (3 × 5/3 = 5): the exact values are the
    question's and the routes' numbers her rounding fits. Not any value in a rounding's range: 0.3 × 900 = 250 is
    neither 270 nor 300."""
    if step.kind != "arithmetic" or step.result is None:
        return False
    choices = []
    for n in (step.left, step.right):
        if n.places and n.value not in exact_values:  # 4.5 is the question's 4.5, not a rounding
            stands = [x for x in exact_values if isinstance(x, Fraction) and n.close_to(x)]
            if not stands:
                return False
            choices.append(stands)
        else:
            choices.append([n.value])
    for x in choices[0]:
        for y in choices[1]:
            v = {"add": x + y, "subtract": x - y, "multiply": x * y, "divide": x / y if y else None}[step.op]
            if v is not None and (step.result.value == v or step.result.close_to(v)):
                return True
    return False


def _gcd(a, b):
    import math
    return Fraction(math.gcd(int(a), int(b))) if a.denominator == b.denominator == 1 else None


def _lcm(a, b):
    import math
    return Fraction(math.lcm(int(a), int(b))) if a.denominator == b.denominator == 1 else None


def _fmt(v) -> str:
    try:
        return _fmt_exact(v)
    except ValueError:  # a number too long to print exactly (Python's int-to-str digit limit)
        return f"{float(v):.6g}"


def _fmt_exact(v) -> str:
    if isinstance(v, Fraction):
        if v.denominator == 1:
            return str(v.numerator)
        d = v.denominator
        for p in (2, 5):
            while d % p == 0:
                d //= p
        return str(float(v)) if d == 1 else f"{v.numerator}/{v.denominator} (≈ {float(v):.3f})"
    return str(v)
