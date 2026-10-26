"""Typed student input and tutor output.

Everything a student enters is turned into one of these models before the tutor looks at it, so the classifier sees
concrete, validated data. Today the models come from a small text parser (parse.py); later an ML model can produce the
same models from free-form input, or replace the classifier that consumes them.
"""

import re
from fractions import Fraction
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator


NUMBER = re.compile(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:/(?:\d+(?:\.\d*)?|\.\d+))?", re.ASCII)  # 0-9 only
MAX_NUMBER_TEXT = 30


def number_value(text: str) -> Fraction:
    """The value of a number in the parser's notation. A fraction's top and bottom may be decimals (3/0.5 = 6).
    Raises ValueError for anything else, and for a zero bottom."""
    if len(text) > MAX_NUMBER_TEXT or not NUMBER.fullmatch(text):
        raise ValueError("not a number like 12, 0.75 or 2/3")
    top, _, bottom = text.partition("/")
    value = Fraction(top)
    if bottom:
        if Fraction(bottom) == 0:
            raise ValueError("a fraction can't have 0 on the bottom")
        value /= Fraction(bottom)
    return value


class Number(BaseModel):
    """A number as the student wrote it: 12, 0.75, 2/3. Keeping the text lets us accept 0.667 for 2/3.

    Only the parser's notation is allowed: digits, an optional decimal point, an optional `/` denominator (itself
    possibly a decimal: 3/0.5 is 6), an optional leading minus. No exponents, at most 30 characters, and never a zero
    denominator. The validator computes the value with number_value(), the same function `.value` uses, so the two
    can't disagree."""

    text: str
    _value: Fraction | None = PrivateAttr(default=None)

    @field_validator("text")
    @classmethod
    def parses(cls, v: str) -> str:
        v = v.strip().replace("$", "").replace(",", "")
        number_value(v)
        return v

    @property
    def value(self) -> Fraction:
        if self._value is None:
            self._value = number_value(self.text)
        return self._value

    @property
    def places(self) -> Optional[int]:
        """Decimal places typed, if the student wrote a decimal (used as a rounding tolerance)."""
        return len(self.text.split(".")[1]) if "." in self.text and "/" not in self.text else None

    def close_to(self, exact: Fraction) -> bool:
        if self.value == exact:
            return True
        if self.places:  # a rounded decimal stands for a decimal that doesn't end (0.667 for 2/3), never for one
            d = exact.denominator  # that ends: 0.15, 0.225 and 0.625 are written exactly, so no cruder rounding of
            for p in (2, 5):       # them passes where a closer one fails
                while d % p == 0:
                    d //= p
            if d == 1:
                return False
            return abs(self.value - exact) < Fraction(1, 2 * 10 ** self.places)
        return False

    def __str__(self) -> str:
        return self.text


# ---------------------------------------------------------------- what a student can write

class ArithmeticStep(BaseModel):
    kind: Literal["arithmetic"] = "arithmetic"
    op: Literal["add", "subtract", "multiply", "divide"]
    left: Number
    right: Number
    result: Optional[Number] = None
    typed: bool = Field(default=False, exclude=True)  # read from typed text, where 3 × 40/5 has no brackets


class FunctionStep(BaseModel):
    kind: Literal["function"] = "function"
    name: Literal["gcf", "lcm"]
    left: Number
    right: Number
    result: Optional[Number] = None


class CompareStep(BaseModel):
    kind: Literal["compare"] = "compare"
    left: Number
    relation: Literal["<", ">", "="]
    right: Number


class RatioCompareStep(BaseModel):
    """Two ratios (or fractions in lowest terms) compared for sameness: 3:4 ≠ 5:7."""
    kind: Literal["ratio_compare"] = "ratio_compare"
    left: tuple[Number, Number]
    relation: Literal["=", "≠"]
    right: tuple[Number, Number]


class PlotStep(BaseModel):
    kind: Literal["plot"] = "plot"
    points: list[tuple[Number, Number]] = Field(min_length=1)


StudentStep = Annotated[Union[ArithmeticStep, FunctionStep, CompareStep, RatioCompareStep, PlotStep],
                        Field(discriminator="kind")]


class ChoiceAnswer(BaseModel):
    """Picking one of the listed options (an extraction decision, or a final answer like 'first')."""

    kind: Literal["choice"] = "choice"
    index: int = Field(ge=1)
    decision: Optional[int] = Field(default=None, ge=0)  # which extraction decision (its index); None: the current one


class ValueAnswer(BaseModel):
    """A bare final answer: a number."""

    kind: Literal["value"] = "value"
    value: Number


StudentInput = Annotated[Union[ArithmeticStep, FunctionStep, CompareStep, RatioCompareStep, PlotStep, ChoiceAnswer,
                               ValueAnswer],
                         Field(discriminator="kind")]


# ---------------------------------------------------------------- what the classifier works with

class Candidate(BaseModel):
    """One possible next step, with concrete values. `operands` may hold wildcards from the trees:
    ('int',) for any whole number the student chose, ('cf', x, y) for a common factor of x and y."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    op: str                       # add | subtract | multiply | divide | gcf | lcm | compare | plot
    operands: list[Any]           # Fractions, wildcard tuples, or (x, y) points for plot
    result: Optional[Any] = None  # Fraction, or the relation for compare
    expression: str = ""          # 4 × 18 = 72
    say: str = ""                 # Multiply across the diagonal
    methods: list[str] = []
    mental: bool = False          # matches the step after one done in the head (15% → 0.15)
    search: Optional[dict] = None  # {'base', 'target'}: a build-up step (ratio table, listing multiples)
    source: Literal["tree", "route", "trap"] = "route"
    note: str = ""


class Classification(BaseModel):
    """Which candidates a student's step matches. `arithmetic_ok` is about the student's result, not the choice."""

    matched: list[str] = []
    status: Literal["match", "on_track", "none"]
    arithmetic_ok: Optional[bool] = None
    expected_result: Optional[str] = None


# ---------------------------------------------------------------- what the tutor says back

class Feedback(BaseModel):
    kind: Literal["correct", "slip", "on_track", "trap", "unknown", "info", "method", "hint", "done", "error"]
    message: str
