"""Question bank for the verification tests.

Questions live in ``bank/*.json`` (one file per skill family) and are validated at load. A question is a
*template*: numbers can be parameters drawn per candidate (so an answer key or a photo of the screen is
useless to anyone else), options are shuffled per session, and the correct answer is computed server-side
and never sent to the browser.

Types:
* ``single``   one correct option among 3-6;
* ``multi``    several correct options (all-or-nothing, partial credit on near misses);
* ``numeric``  a value computed from the parameters with a safe arithmetic expression, with a tolerance;
* ``order``    put steps in the right order (partial credit by adjacent pairs).
"""

from __future__ import annotations

import ast
import json
import operator
import random
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..translator.catalog import CATALOG

BANK_DIR = Path(__file__).parent / "bank"

Level = Literal[1, 2, 3]  # 1 junior, 2 confirmed, 3 senior


class Text(BaseModel):
    fr: str = Field(..., min_length=3)
    en: str = Field(..., min_length=3)

    def get(self, locale: str) -> str:
        return self.fr if locale == "fr" else self.en


class Param(BaseModel):
    min: float
    max: float
    step: float = 1


class QuestionTemplate(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    skill_id: str
    level: Level
    type: Literal["single", "multi", "numeric", "order"]
    stem: Text
    options: list[Text] = Field(default_factory=list)
    correct: list[int] = Field(default_factory=list)  # indices into options (single/multi), or the right order
    params: dict[str, Param] = Field(default_factory=dict)
    answer: str = ""  # arithmetic expression over params (numeric)
    tolerance: float = 0.01  # relative tolerance for numeric answers
    unit: str = ""
    seconds: int = Field(60, ge=20, le=300)
    explanation: Text | None = None

    @model_validator(mode="after")
    def _consistent(self) -> QuestionTemplate:
        if self.skill_id not in CATALOG:
            raise ValueError(f"{self.id}: unknown skill {self.skill_id}")
        if self.type in ("single", "multi", "order"):
            if not 3 <= len(self.options) <= 6:
                raise ValueError(f"{self.id}: needs 3 to 6 options")
            if any(i < 0 or i >= len(self.options) for i in self.correct):
                raise ValueError(f"{self.id}: correct index out of range")
        if self.type == "single" and len(self.correct) != 1:
            raise ValueError(f"{self.id}: single needs exactly one correct option")
        if self.type == "multi" and not 2 <= len(self.correct) < len(self.options):
            raise ValueError(f"{self.id}: multi needs at least two correct options and one wrong")
        if self.type == "order" and sorted(self.correct) != list(range(len(self.options))):
            raise ValueError(f"{self.id}: order needs a permutation of all options")
        if self.type == "numeric":
            if not self.answer:
                raise ValueError(f"{self.id}: numeric needs an answer expression")
            safe_eval(self.answer, {k: p.min for k, p in self.params.items()})
        return self


_OPS: dict[type, Callable[..., Any]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FUNCS: dict[str, Callable[..., Any]] = {"round": round, "min": min, "max": max, "abs": abs}


def safe_eval(expr: str, values: dict[str, float]) -> float:
    """Arithmetic only: numbers, parameters, + - * / **, round/min/max/abs. No attribute, no call else."""

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in values:
            return float(values[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return float(_OPS[type(node.op)](ev(node.left), ev(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return float(_OPS[type(node.op)](ev(node.operand)))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS
                and not node.keywords):
            args = [ev(a) for a in node.args]
            if node.func.id == "round" and len(args) == 2:
                return float(round(args[0], int(args[1])))  # the number of digits must be an integer
            return float(_FUNCS[node.func.id](*args))
        raise ValueError(f"unsupported expression: {ast.dump(node)[:80]}")

    return ev(ast.parse(expr, mode="eval"))


@lru_cache
def load_bank() -> tuple[QuestionTemplate, ...]:
    questions: list[QuestionTemplate] = []
    for path in sorted(BANK_DIR.glob("*.json")):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            questions.append(QuestionTemplate.model_validate(raw))
    ids = [q.id for q in questions]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate question ids: {sorted(duplicates)}")
    return tuple(questions)


def coverage() -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = {}
    for q in load_bank():
        out.setdefault(q.skill_id, {1: 0, 2: 0, 3: 0})[q.level] += 1
    return out


def draw_params(template: QuestionTemplate, rng: random.Random) -> dict[str, float]:
    values = {}
    for name, p in template.params.items():
        steps = round((p.max - p.min) / p.step)
        value = p.min + p.step * rng.randint(0, max(0, steps))
        values[name] = round(value, 6) if p.step < 1 else round(value)
    return values


def render(text: str, values: dict[str, Any]) -> str:
    out = text
    for name, value in values.items():
        shown = f"{value:,.0f}".replace(",", " ") if isinstance(value, int) and abs(value) >= 10_000 else f"{value:g}"
        out = out.replace("{" + name + "}", shown)
    return out
