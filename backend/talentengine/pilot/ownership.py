"""Git ownership verification: "change your own code, under a new constraint, in five minutes".

The task generator picks a real, non-trivial function from the candidate's own repositories and asks
for a new business constraint (a Prometheus-instrumented cache, retries with back-off, an audit log
without personal data, a feature flag, a latency histogram) chosen to fit what the function does.

The candidate sees the function's file. What they do *not* see is the rest of the repository — and that
is the signal: someone who wrote or truly maintains the code reaches for the names that live around it
(the module that calls it, the settings object, the client class two files away). Someone piloting
blind asks the assistant to explain the function, or gives orders that name nothing.

Factual signals (all reproducible):

* ``hidden_identifiers_used`` — identifiers from *other* files of the repository used in the prompts;
* ``visible_identifiers_used`` — precise use of names inside the function;
* ``location_precision`` — the prompt says *where* the change goes (around which call, before which
  return, as a decorator...);
* ``explain_requests`` — asking the assistant what one's own function does;
* ``first_prompt_seconds`` and ``constraint_implemented`` (static check on the result).

The result is reported as *authenticity of the evidence*: a signal for the interview, never a verdict.
Some people maintain code they did not write, and nervous people freeze; the interviewer decides.
"""

from __future__ import annotations

import ast
import random
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .models import Evidence, OwnershipFacts, OwnershipTask
from .scenarios import Files, fold

SOURCE_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".mjs": "javascript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rs": "rust",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".dart": "dart",
}
_SKIP_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|vendor|node_modules|dist|build|migrations|\.github|docs?|examples?"
    r"|fixtures|generated)(/|$)|(_test|\.test|\.spec|_spec)\.\w+$|(^|/)test_[^/]+$|\.min\.js$"
)
_GENERIC = {
    "self",
    "this",
    "none",
    "true",
    "false",
    "null",
    "return",
    "async",
    "await",
    "function",
    "const",
    "string",
    "list",
    "dict",
    "print",
    "len",
    "range",
    "data",
    "value",
    "result",
    "error",
    "item",
    "items",
    "args",
    "kwargs",
    "main",
    "test",
    "tests",
    "utils",
    "config",
    "index",
    "client",
    "server",
    "app",
    "src",
    "lib",
    "init",
    "type",
    "json",
    "path",
    "name",
    "file",
    "line",
    "text",
    "time",
    "info",
    "debug",
    "warning",
    "logger",
    "log",
    "response",
    "request",
    "params",
    "options",
    "context",
    "default",
    "object",
    "number",
    "boolean",
}
_KEYWORDS = r"\b(if|elif|else if|for|while|case|catch|except|and|or|&&|\|\||\?)\b"


@dataclass
class FunctionInfo:
    repository: str
    path: str
    name: str
    language: str
    start: int
    end: int
    complexity: int
    source: str
    inner_names: set[str] = field(default_factory=set)

    @property
    def lines(self) -> int:
        return self.end - self.start + 1


def candidate_source_paths(paths: list[str], limit: int = 8) -> list[str]:
    """Source files most likely to hold real logic: code extensions, no tests or vendored code, shallow first."""
    code = [
        p
        for p in paths
        if PurePosixPath(p).suffix in SOURCE_EXT
        and not _SKIP_PATH.search(p.lower())
        and not PurePosixPath(p).name.startswith(("__init__", "setup.", "conftest", "vite.config", "next.config"))
    ]
    return sorted(code, key=lambda p: (p.count("/") > 3, -len(PurePosixPath(p).stem), p))[:limit]


def _python_functions(repo: str, path: str, src: str) -> list[FunctionInfo]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.end_lineno:
            continue
        branches = sum(
            isinstance(
                n,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.Try,
                    ast.With,
                    ast.BoolOp,
                    ast.ExceptHandler,
                    ast.comprehension,
                    ast.IfExp,
                    ast.Match,
                ),
            )
            for n in ast.walk(node)
        )
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
        }
        out.append(
            FunctionInfo(
                repo,
                path,
                node.name,
                "python",
                node.lineno,
                node.end_lineno,
                1 + branches,
                ast.get_source_segment(src, node) or "",
                names,
            )
        )
    return out


_BRACE_DEF = re.compile(
    r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:pub(?:\(crate\))?\s+)?(?:public|private|protected|internal|static|override"
    r"|async|suspend|final|\s)*"
    r"(?:function\s*\*?\s*(?P<a>\w+)|func\s+(?:\([^)]*\)\s*)?(?P<b>\w+)|fn\s+(?P<c>\w+)|fun\s+(?P<d>\w+)"
    r"|(?:const|let|var)\s+(?P<e>\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"
    r"|(?:[\w<>\[\],?]+\s+)+(?P<f>\w+)\s*\([^;{}]*\)\s*(?:throws [\w, ]+)?)"
    r"[^;{]*\{",
    re.M,
)


def _brace_functions(repo: str, path: str, src: str, language: str) -> list[FunctionInfo]:
    out = []
    for m in _BRACE_DEF.finditer(src):
        name = next((g for g in m.groups() if g), "")
        if not name or name in ("if", "for", "while", "switch", "catch", "return", "new") or name.isupper():
            continue
        if not m.group("e") and re.search(r"\b(const|let|var)\b|=", m.group(0).split(name)[0]):
            continue  # an assignment such as `const X = (() => {...})()`, not a function definition
        depth, i = 0, m.end() - 1
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[m.start() : i + 1]
        start = src.count("\n", 0, m.start()) + 1
        names = set(re.findall(r"\b[A-Za-z_]\w{3,}\b", body))
        out.append(
            FunctionInfo(
                repo,
                path,
                name,
                language,
                start,
                start + body.count("\n"),
                1 + len(re.findall(_KEYWORDS, body)),
                body,
                names,
            )
        )
    return out


def extract_functions(repo: str, files: Files) -> list[FunctionInfo]:
    out: list[FunctionInfo] = []
    for path, src in files.items():
        lang = SOURCE_EXT.get(PurePosixPath(path).suffix)
        if not lang or _SKIP_PATH.search(path.lower()):
            continue
        out += _python_functions(repo, path, src) if lang == "python" else _brace_functions(repo, path, src, lang)
    return out


def _is_specific(identifier: str) -> bool:
    """Names a candidate would not say by chance: snake_case, kebab-case, camelCase or PascalCase."""
    if identifier.lower() in _GENERIC or len(identifier) < 5:
        return False
    return (
        "_" in identifier.strip("_")
        or "-" in identifier.strip("-")
        or bool(re.search(r"[a-z][A-Z]", identifier))
        or bool(re.match(r"[A-Z][a-z]+[A-Z]", identifier))
    )


def repository_identifiers(files: Files, paths: list[str]) -> set[str]:
    names: set[str] = set()
    for src in files.values():
        names |= set(re.findall(r"(?:def|class|func|fn|function|interface|struct|type)\s+([A-Za-z_]\w+)", src))
        names |= set(re.findall(r"^([A-Z][A-Z0-9_]{4,})\s*=", src, re.M))  # module constants
    for p in paths:
        pp = PurePosixPath(p)
        # other modules of the codebase, by name
        if pp.suffix in SOURCE_EXT and not _SKIP_PATH.search(p.lower()) and _is_specific(pp.stem):
            names.add(pp.stem)
    return {n for n in names if _is_specific(n)}


# Constraint catalogue: id, applies-to pattern on the function, instruction, implementation markers.
CONSTRAINTS = [
    (
        "prometheus_cache",
        r"requests\.|httpx|fetch\(|axios|http\.|\.get\(|\.query\(|\.execute\(|select |open\(|read",
        {
            "fr": "Ajoutez à `{fn}` un cache (TTL configurable) et exposez un compteur Prometheus des succès "
            "et des échecs de cache.",
            "en": "Add a cache (configurable TTL) to `{fn}` and expose a Prometheus counter of cache hits and misses.",
        },
        r"cache|lru|ttl",
        r"prometheus|Counter\(|counter|metric",
    ),
    (
        "retry_backoff",
        r"requests\.|httpx|fetch\(|axios|http\.|connect|send|post\(|call",
        {
            "fr": "Faites réessayer `{fn}` sur les erreurs transitoires (3 tentatives, attente exponentielle) "
            "et comptez les nouvelles tentatives dans une métrique Prometheus.",
            "en": "Make `{fn}` retry transient errors (3 attempts, exponential back-off) and count retries in a "
            "Prometheus metric.",
        },
        r"retry|retries|backoff|attempt|tenacity",
        r"prometheus|Counter\(|counter|metric",
    ),
    (
        "audit_log",
        r"user|email|account|customer|client|person|candidate|token|auth|login",
        {
            "fr": "Chaque appel de `{fn}` doit laisser une ligne de journal d'audit, sans aucune donnée personnelle "
            "(identifiants masqués ou pseudonymisés).",
            "en": "Every call of `{fn}` must leave an audit log line without any personal data (identifiers masked or "
            "pseudonymised).",
        },
        r"audit",
        r"mask|redact|pseudonym|hash|hmac|anonym",
    ),
    (
        "latency_histogram",
        r".",
        {
            "fr": "Mesurez `{fn}` avec un histogramme Prometheus de latence, étiqueté par résultat (ok / erreur).",
            "en": "Instrument `{fn}` with a Prometheus latency histogram labelled by outcome (ok / error).",
        },
        r"histogram|Histogram|latency|duration|timer|observe",
        r"ok|error|outcome|status|label",
    ),
]


def choose_task(
    repos: list[tuple[str, list[str], Files]], rng: random.Random, locale: str, seconds: int = 300
) -> tuple[OwnershipTask, Files] | None:
    """repos: (pseudonymous label, tree paths, fetched source files). None when no suitable function exists."""
    candidates: list[tuple[FunctionInfo, str, list[str], Files]] = []
    for label, paths, files in repos:
        for fn in extract_functions(label, files):
            if 8 <= fn.lines <= 150 and fn.complexity >= 3 and not fn.name.startswith(("test", "_test")):
                candidates.append((fn, label, paths, files))
    if not candidates:
        return None
    candidates.sort(key=lambda c: -(min(c[0].complexity, 25) * 2 + min(c[0].lines, 80) / 10))
    fn, label, paths, files = rng.choice(candidates[:5])  # among the five richest: not predictable, still meaningful
    fitting = [c for c in CONSTRAINTS if re.search(c[1], fn.source, re.I)] or [CONSTRAINTS[-1]]
    cid, _, text, _, _ = rng.choice(fitting)
    loc = "en" if locale == "en" else "fr"
    shown = files[fn.path]
    visible = {n for n in fn.inner_names if _is_specific(n) and n != fn.name}
    shown_names = set(re.findall(r"\b[A-Za-z_]\w+\b", shown))
    hidden = {
        n
        for n in repository_identifiers(files, paths)
        if n not in shown_names and n != PurePosixPath(fn.path).name and n != PurePosixPath(fn.path).stem
    }
    instruction = text[loc].format(fn=fn.name) + (
        f" ({fn.path}, {'lignes' if loc == 'fr' else 'lines'} {fn.start}-{fn.end})"
    )
    task = OwnershipTask(
        repository=label,
        path=fn.path,
        function=fn.name,
        language=fn.language,
        start_line=fn.start,
        end_line=fn.end,
        complexity=fn.complexity,
        constraint_id=cid,
        instruction=instruction,
        seconds=seconds,
        hidden_identifiers=sorted(hidden)[:400],
        visible_identifiers=sorted(visible),
        original_source=shown,
    )
    return task, {fn.path: shown}


_LOCATION = re.compile(
    r"avant|apres|before|after|autour|around|wrap|envelopp|entre|between|boucle|loop|ligne \d|line \d"
    r"|decor|au debut|at the (start|top|beginning)|a la fin|at the end|retour|return|appel|call to|"
    r"bloc|block|branche|branch|except|catch"
)
_EXPLAIN = re.compile(
    r"explique|explain|que fait|what does|comment (marche|fonctionne)|how does|c.est quoi|what is this"
    r"|resume|summari[sz]e|a quoi sert|what.s the purpose"
)


def _mentions(text: str, identifiers: list[str]) -> list[str]:
    low = text.lower()
    return [i for i in identifiers if re.search(r"(?<![\w.])" + re.escape(i.lower()) + r"(?![\w])", low)]


def analyse(
    task: OwnershipTask | None, prompts: list[tuple[int, float, str]], files_after: Files, original: Files
) -> tuple[OwnershipFacts | None, float | None, list[Evidence], dict[str, float]]:
    """prompts: (turn index, seconds since the task started, text). Returns facts, score, evidence, breakdown."""
    if task is None:
        return None, None, [], {}
    if task.started_at is None:
        return (
            OwnershipFacts(
                function=task.function,
                path=task.path,
                repository=task.repository,
                constraint=task.constraint_id,
                seconds_used=None,
                first_prompt_seconds=None,
                hidden_identifiers_used=[],
                visible_identifiers_used=[],
                location_precision=False,
                explain_requests=0,
                constraint_implemented=False,
                band="not_taken",
            ),
            None,
            [],
            {},
        )
    hidden_used: list[str] = []
    visible_used: list[str] = []
    evidence: list[Evidence] = []
    located = False
    explain = 0
    for turn, _, text in prompts:
        h = [i for i in _mentions(text, task.hidden_identifiers) if i not in hidden_used]
        v = [i for i in _mentions(text, [*task.visible_identifiers, task.function]) if i not in visible_used]
        hidden_used += h
        visible_used += v
        if h:
            evidence.append(
                Evidence(
                    turn=turn, quote=text[:200], note="uses names from elsewhere in the repository: " + ", ".join(h[:5])
                )
            )
        if v and _LOCATION.search(fold(text)) and not located:
            located = True
            evidence.append(Evidence(turn=turn, quote=text[:200], note="says where the change goes in the function"))
        if _EXPLAIN.search(fold(text)):
            explain += 1
            evidence.append(Evidence(turn=turn, quote=text[:200], note="asks the assistant to explain the function"))
    constraint = next(c for c in CONSTRAINTS if c[0] == task.constraint_id)
    new_code = files_after.get(task.path, "")
    old_code = original.get(task.path, "")
    added = "\n".join(ln for ln in new_code.splitlines() if ln not in set(old_code.splitlines()))
    implemented = bool(re.search(constraint[3], added, re.I) and re.search(constraint[4], added, re.I))
    first = prompts[0][1] if prompts else None
    breakdown = {
        "repository_knowledge": float(min(40, 20 * len(hidden_used))),
        "precision_in_function": float(min(20, 7 * len(visible_used))),
        "location": 15.0 if located else 0.0,
        "quick_start": 10.0
        if first is not None and first <= 90
        else 5.0
        if first is not None and first <= 180
        else 0.0,
        "constraint_implemented": 15.0 if implemented else 0.0,
        "explain_requests": -float(min(20, 10 * explain)),
    }
    score = max(0.0, min(100.0, sum(breakdown.values())))
    band = "knows_the_code" if score >= 65 else "partial" if score >= 35 else "navigates_blind"
    if not prompts:
        evidence.append(Evidence(note="no instruction was given during the five minutes"))
    used = None
    if task.started_at and task.deadline:
        used = float(min(task.seconds, max((p[1] for p in prompts), default=0.0)))
    facts = OwnershipFacts(
        function=task.function,
        path=task.path,
        repository=task.repository,
        constraint=task.constraint_id,
        seconds_used=used,
        first_prompt_seconds=first,
        hidden_identifiers_used=hidden_used,
        visible_identifiers_used=visible_used,
        location_precision=located,
        explain_requests=explain,
        constraint_implemented=implemented,
        band=band,
    )
    return facts, round(score, 1), evidence, breakdown
