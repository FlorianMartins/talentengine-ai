"""Building blocks of the AI-pilot scenarios: checks, faults, scenarios, and static-analysis helpers."""

from __future__ import annotations

import ast
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from ...models import Locale

Files = dict[str, str]


def fold(text: str) -> str:
    """Lowercase, strip accents: markers are written once for French and English."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _parse(files: Files, path: str) -> ast.Module | None:
    try:
        return ast.parse(files.get(path, ""))
    except SyntaxError:
        return None


def _functions(tree: ast.AST | None) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    if tree is None:
        return {}
    return {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _calls_in(node: ast.AST) -> set[str]:
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            names.add(f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else "")
    return names


_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log", "print"}
_SENSITIVE_KEYS = {
    "iban",
    "email",
    "name",
    "content",
    "messages",
    "prompt",
    "text",
    "account",
    "card",
    "pan",
    "phone",
    "address",
}
_STRINGIFY = {"str", "repr", "dumps", "format", "join"}


def _logs_raw(files: Files, path: str, raw_names: set[str]) -> bool:
    """True when a logging call receives one of ``raw_names`` (directly, subscripted, or stringified).

    Models sometimes return code that does not parse; the flaw is then looked for line by line, so that a
    leak in broken code is still seen (a candidate who fixes the syntax would otherwise ship it unnoticed).
    """
    tree = _parse(files, path)
    if tree is None:
        return any(_line_logs_raw(line, raw_names) for line in files.get(path, "").splitlines())
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        f = call.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name not in _LOG_METHODS:
            continue
        for arg in [*call.args, *(k.value for k in call.keywords)]:
            if _exposes(arg, raw_names):
                return True
    return False


_LOG_LINE = re.compile(r"\b(?:log|logger|logging)\.(?:debug|info|warning|warn|error|exception|critical)\s*\("
                       r"|\bprint\s*\(")


def _line_logs_raw(line: str, raw_names: set[str]) -> bool:
    m = _LOG_LINE.search(line)
    if not m:
        return False
    args = line[m.end():]
    args = re.sub(r"(\w+)\[\s*([\"'])(\w+)\2\s*\]",
                  lambda k: k.group(1) if k.group(3).lower() in _SENSITIVE_KEYS else "SAFE", args)
    args = re.sub(r"\blen\(\s*\w+\s*\)", "N", args)
    args = re.sub(r"([\"']).*?(?<!\\)\1", "S", args)  # string literals (format strings, labels)
    return any(re.search(rf"\b{re.escape(n)}\b", args) for n in raw_names)


def _def_names(files: Files, path: str) -> set[str]:
    """Function names, from the AST or — when the code does not parse — from ``def`` lines."""
    tree = _parse(files, path)
    if tree is not None:
        return set(_functions(tree))
    return set(re.findall(r"^\s*(?:async\s+)?def\s+(\w+)", files.get(path, ""), re.M))


def _exposes(node: ast.AST, raw_names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in raw_names
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):  # row["date"] is fine, row["iban"] is not
            return key.value.lower() in _SENSITIVE_KEYS and _exposes(node.value, raw_names)
        return _exposes(node.value, raw_names)
    if isinstance(node, ast.Attribute):
        return _exposes(node.value, raw_names)
    if isinstance(node, ast.JoinedStr):
        return any(_exposes(v.value, raw_names) for v in node.values if isinstance(v, ast.FormattedValue))
    if isinstance(node, ast.BinOp):  # "..." % x, "..." + x
        return _exposes(node.left, raw_names) or _exposes(node.right, raw_names)
    if isinstance(node, ast.Call):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name in _STRINGIFY:
            return any(_exposes(a, raw_names) for a in node.args) or (
                isinstance(f, ast.Attribute) and _exposes(f.value, raw_names)
            )
    return False


def _without_docstring(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Module:
    body = (
        fn.body[1:]
        if fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], "value", None), ast.Constant)
        else fn.body
    )
    return ast.Module(body=list(body), type_ignores=[])


def _has_tests(files: Files, path: str, must_mention: str, minimum: int = 3) -> tuple[bool, str]:
    text = files.get(path, "")
    n = len(re.findall(r"^\s*def test_", text, re.M))
    ok = n >= minimum and must_mention in text and _parse(files, path) is not None
    return ok, f"{n} test(s)"


@dataclass
class Check:
    id: str
    label: dict[str, str]
    run: Callable[[Files], tuple[bool, str]]


@dataclass
class Fault:
    id: str
    title: dict[str, str]
    category: str
    cwe: str
    target: str  # file the flaw lives in
    present: Callable[[Files], bool]  # hidden audit: True while the flaw is in the code
    applies: Callable[[Files], bool]  # the code has reached the point where this flaw can be planted
    markers: list[str]  # every regex must match (on folded text) for a prompt to "call it out"
    directive: str  # hidden instruction that makes a real model plant it
    explanation: dict[str, str]  # shown in the report, after the test
    # Second-order trap: only appears in the assistant's fix of this other fault (e.g. a hard-coded HMAC key
    # in the fix of an unkeyed hash). Empty for first-order faults.
    after: str = ""


@dataclass
class Scenario:
    id: str
    title: dict[str, str]
    brief: dict[str, str]
    skills: list[str]
    par: int  # iterations a good pilot needs to reach a green CI with no surviving flaw
    render: Callable[[set[str]], Files]  # reference assistant: workspace for a set of flags
    checks: list[Check]
    faults: list[Fault]
    task_markers: str  # a prompt matching this asks for the main work
    test_markers: str = r"\btests?\b|pytest|unit|unitaire|couverture|coverage"
    reply_done: dict[str, str] = field(default_factory=dict)
    reply_tests: dict[str, str] = field(default_factory=dict)
    reply_fix: dict[str, dict[str, str]] = field(default_factory=dict)
    # Real execution (pytest in the isolated runner): the visible CI runs the workspace's tests, and at close
    # ``hidden_tests`` (fault id → pytest file) exercise each planted flaw by behaviour.
    runnable: bool = False
    hidden_tests: dict[str, str] = field(default_factory=dict)

    def t(self, attr: str, locale: Locale) -> str:
        return str(getattr(self, attr)[locale])

    def starter(self) -> Files:
        return self.render(set())

    def run_checks(self, files: Files, locale: Locale) -> list[tuple[str, str, bool, str]]:
        out = []
        for c in self.checks:
            try:
                ok, detail = c.run(files)
            except Exception as exc:
                ok, detail = False, f"check error: {type(exc).__name__}"
            out.append((c.id, c.label[locale], ok, detail))
        return out

    def fault(self, fault_id: str) -> Fault:
        return next(f for f in self.faults if f.id == fault_id)


def _syntax(files: Files) -> tuple[bool, str]:
    bad = [p for p, src in files.items() if p.endswith(".py") and _parse(files, p) is None]
    return not bad, ("syntax errors: " + ", ".join(bad)) if bad else "all Python files parse"


def matches(text: str, markers: list[str]) -> bool:
    folded = fold(text)
    return all(re.search(m, folded) for m in markers)
