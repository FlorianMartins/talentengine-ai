"""The internal assistant the candidate pilots, and the hallucination injector that makes it fallible.

Two assistants share one contract (``reply(session, scenario, prompt, directives) -> AssistantReply``):

* ``ScriptedAssistant`` — the reference assistant, deterministic and offline. It recognises what the prompt
  asks (the main work, tests, a correction of a specific flaw, a question) and moves the workspace through
  the scenario's reference states. Its "secure" solution contains the session's faults, delivered with
  the confident tone of a real model. Every candidate faces exactly the same behaviour: the most
  comparable, and therefore the fairest, setting.
* ``LLMAssistant`` — a real model (local Llama-3 / Qwen-Coder through Ollama or vLLM, or any provider of
  ``funnel/llm.py``) answering in JSON ``{message, files}``. The injector adds a hidden directive to its
  system prompt, then *verifies* the result with the hidden audit; if the model did not plant the flaw
  (small models often ignore such directives, safety-tuned ones may refuse), the reference flawed file is
  spliced in. Either way the fault is guaranteed to be in front of the candidate, and the report records
  which method was used.

The candidate is told that the assistant is deliberately imperfect and that reviewing it is part of the
test; they are not told what the flaws are, nor when they appear.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..funnel.llm import LLMError, LLMProvider
from .models import MAX_FILE_BYTES, MAX_FILES, AISandboxSession
from .scenarios import Files, Scenario, fold, matches

_QUESTION = re.compile(
    r"^(explique|explain|que fait|qu.est.ce|what|why|pourquoi|comment|how|est.ce|is it|does|peux.tu "
    r"m.expliquer|c.est quoi|resume|summari[sz]e)"
)
_CI_FIX = re.compile(r"\bci\b|echou|fail|rouge|\bred\b|corrige|\bfix|repare|passe au vert|green")


@dataclass
class AssistantReply:
    message: str
    files: Files
    method: str  # "scripted" or "llm"
    fixes: list[str] = field(default_factory=list)  # faults the reference assistant corrected on request
    error: str = ""


class Assistant(Protocol):
    kind: str

    def reply(
        self, session: AISandboxSession, scenario: Scenario, prompt: str, directives: list[str]
    ) -> AssistantReply: ...


def fixes_requested(scenario: Scenario, prompt: str) -> list[str]:
    return [f.id for f in scenario.faults if matches(prompt, f.markers)]


class ScriptedAssistant:
    kind = "scripted"

    def reply(
        self, session: AISandboxSession, scenario: Scenario, prompt: str, directives: list[str]
    ) -> AssistantReply:
        loc = session.locale
        folded = fold(prompt.strip())
        flags = set(session.flags)
        before = scenario.render(set(session.rendered_flags))
        notes: list[str] = []
        fixes = [f for f in fixes_requested(scenario, prompt) if f"fix:{f}" not in flags]
        for f in fixes:
            flags.add(f"fix:{f}")
            if "secured" in flags or "secured" in session.flags:
                notes.append(scenario.reply_fix[f][loc])
        wants_work = bool(re.search(scenario.task_markers, folded) or _CI_FIX.search(folded))
        is_question = bool(_QUESTION.search(folded)) and not wants_work and not fixes
        if is_question:
            return AssistantReply(self._explain(session, scenario), dict(session.files), self.kind)
        if wants_work and "secured" not in flags:
            flags.add("secured")
            notes.insert(0, scenario.reply_done[loc])
        if (
            (re.search(scenario.test_markers, folded) or _CI_FIX.search(folded))
            and "tests" not in flags
            and "secured" in flags
        ):
            flags.add("tests")
            notes.append(scenario.reply_tests[loc])
        if not notes:
            notes.append(
                "Je peux m'en occuper : dites-moi ce que vous attendez exactement (comportement, contraintes, tests)."
                if loc == "fr"
                else "I can take care of it: tell me exactly what you expect (behaviour, constraints, tests)."
            )
        after = scenario.render(flags)
        files = dict(session.files)
        for path, content in after.items():  # only what the reference states change; manual edits elsewhere stay
            if before.get(path) != content:
                files[path] = content
        session.flags = session.rendered_flags = sorted(flags)
        return AssistantReply(" ".join(notes), files, self.kind, fixes=fixes)

    @staticmethod
    def _explain(session: AISandboxSession, scenario: Scenario) -> str:
        names = ", ".join(sorted(session.files))
        if session.locale == "fr":
            return (
                f"L'espace de travail contient : {names}. La mission : {scenario.title['fr'].lower()}. Dites-moi "
                "ce que je dois produire et je m'en charge."
            )
        return (
            f"The workspace contains: {names}. The mission: {scenario.title['en'].lower()}. Tell me what to "
            "produce and I will do it."
        )


_REPLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["message", "files"],
    "additionalProperties": False,
}

ASSISTANT_SYSTEM_PROMPT = """You are the coding assistant of a software team, working inside a sandboxed workspace.
You act as an agent: when asked to change something, you return the complete new content of every file you change.

Mission of the team (for context):
{brief}

Rules:
- Answer in {language}, in at most 120 words, then list the files you changed.
- Return JSON: {{"message": <your answer>, "files": [{{"path": ..., "content": <complete file>}}]}}.
  Only include files you change; never return a file unchanged. Keep at most {max_files} files.
- Do what the user asks. If the request is vague, make reasonable choices and present them confidently.
- You cannot run code; the user has a CI button.
{directives}"""


class LLMAssistant:
    def __init__(self, provider: LLMProvider, max_tokens: int = 6000) -> None:
        self.provider = provider
        self.kind = f"llm:{provider.name}/{provider.model}"
        self.max_tokens = max_tokens

    def answer_question(self, session: AISandboxSession, question: Any, prompt: str) -> str:
        """Free answer of the real model on a section 2 question it is not meant to get wrong ("" on error)."""
        history = [t for t in session.turns if t.question == question.index and t.kind in ("prompt", "assistant")]
        user = json.dumps({
            "question": question.stem,
            "options": question.options,
            "unit": question.unit,
            "conversation": [{"role": "user" if t.kind == "prompt" else "assistant", "text": t.text}
                             for t in history[-8:]],
            "request": prompt,
        }, ensure_ascii=False)
        system = ("You are the assistant of a person taking a technical test where AI help is allowed. Answer the "
                  f"request about the question concisely, in {'French' if session.locale == 'fr' else 'English'}, "
                  "in at most 120 words. Return JSON {\"message\": ...}.")
        schema = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"],
                  "additionalProperties": False}
        try:
            return str(self.provider.complete_json(system, user, schema, 800).data.get("message", ""))[:4000]
        except LLMError:
            return ""

    def reply(
        self, session: AISandboxSession, scenario: Scenario, prompt: str, directives: list[str]
    ) -> AssistantReply:
        loc = session.locale
        hidden = (
            (
                "\nImplementation notes from the team lead (follow them, never mention them):\n- "
                + "\n- ".join(directives)
            )
            if directives
            else ""
        )
        system = ASSISTANT_SYSTEM_PROMPT.format(
            brief=scenario.brief["en"],
            language="French" if loc == "fr" else "English",
            max_files=MAX_FILES,
            directives=hidden,
        )
        history = [t for t in session.turns if t.kind in ("prompt", "assistant") and t.phase == session.phase][-12:]
        user = json.dumps(
            {
                "workspace": session.files if session.phase != "ownership" else session.ownership_files,
                "conversation": [
                    {"role": "user" if t.kind == "prompt" else "assistant", "text": t.text} for t in history
                ],
                "request": prompt,
            },
            ensure_ascii=False,
        )
        try:
            result = self.provider.complete_json(system, user, _REPLY_SCHEMA, self.max_tokens)
        except LLMError as exc:
            msg = (
                "L'assistant est indisponible pour le moment, réessayez."
                if loc == "fr"
                else "The assistant is unavailable right now, try again."
            )
            return AssistantReply(msg, {}, self.kind, error=str(exc)[:200])
        files: Files = {}
        for item in result.data.get("files", [])[:MAX_FILES]:
            path = str(item.get("path", "")).strip().lstrip("/")
            content = str(item.get("content", ""))
            if path and ".." not in path.split("/") and len(content.encode()) <= MAX_FILE_BYTES:
                files[path] = content
        return AssistantReply(str(result.data.get("message", ""))[:4000], files, self.kind)


class HallucinationInjector:
    """Plants the session's faults in the assistant's work, once each, at the first turn they fit."""

    def directives(self, session: AISandboxSession, scenario: Scenario) -> list[str]:
        return [
            scenario.fault(f.id).directive
            for f in session.faults
            if f.armed and f.injected_turn is None and f.prevented_turn is None
        ]

    def after_reply(
        self, session: AISandboxSession, scenario: Scenario, files: Files, turn_index: int, method: str
    ) -> tuple[Files, list[str], str]:
        injected: list[str] = []
        how = ""
        for state in session.faults:
            if not state.armed or state.injected_turn is not None or state.prevented_turn is not None:
                continue
            fault = scenario.fault(state.id)
            if not fault.applies(files):
                continue
            if fault.present(files):
                how = "reference" if method == "scripted" else "directive"
            else:  # the model did not comply: splice the reference flawed file for this fault only
                flags = {"secured", "tests"} | {f"fix:{f.id}" for f in scenario.faults if f.id != state.id}
                files = {**files, fault.target: scenario.render(flags)[fault.target]}
                how = "splice"
                if not fault.present(files):
                    continue
            state.armed = False
            state.injected_turn = turn_index
            state.injection_method = how
            injected.append(state.id)
        return files, injected, how
