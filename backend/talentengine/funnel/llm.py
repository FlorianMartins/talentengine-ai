"""Escalation-tier model providers.

All providers implement the same small contract: take a system prompt, a user message and a JSON
schema, return parsed JSON plus token usage. The pipeline never depends on a specific vendor.

* ``none``              local-only mode, the default. Level-1 heuristics produce the whole report.
* ``ollama``            a local model (zero marginal cost, data stays on premises).
* ``anthropic``         Claude through the official SDK, with structured outputs and server-side
                        refusal fallback enabled.
* ``openai_compatible`` any vendor exposing the Chat Completions shape (Mistral, vLLM, OpenRouter...).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from ..config import Settings
from .budget import Price


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    data: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str, schema: dict[str, Any], max_tokens: int) -> LLMResult: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str, price: Price) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - optional extra
            raise LLMError("install the 'anthropic' extra: pip install talentengine-ai[anthropic]") from exc
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key or None)
        self.model = model
        self.price = price

    def complete_json(self, system: str, user: str, schema: dict[str, Any], max_tokens: int) -> LLMResult:
        anthropic = self._anthropic
        try:
            resp = self._client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
                # On a safety-classifier decline, the API re-runs the request on a recommended model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as exc:
            raise LLMError("rate limited by the Anthropic API") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("cannot reach the Anthropic API") from exc
        if resp.stop_reason == "refusal":
            raise LLMError("the model declined this request")
        if resp.stop_reason == "max_tokens":
            raise LLMError("output budget exhausted before the answer was complete")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("model returned invalid JSON") from exc
        usage = resp.usage
        return LLMResult(data, usage.input_tokens, usage.output_tokens,
                         self.price.cost(usage.input_tokens, usage.output_tokens), resp.model)


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete_json(self, system: str, user: str, schema: dict[str, Any], max_tokens: int) -> LLMResult:
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", timeout=self.timeout, json={
                "model": self.model, "stream": False, "format": schema,
                "options": {"temperature": 0, "num_predict": max_tokens},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            })
            resp.raise_for_status()
            body = resp.json()
            data = json.loads(body["message"]["content"])
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            raise LLMError(f"ollama: {exc}") from exc
        return LLMResult(data, int(body.get("prompt_eval_count", 0)), int(body.get("eval_count", 0)), 0.0, self.model)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, price: Price, timeout: float = 180.0) -> None:
        if not base_url:
            raise LLMError("TE_LLM_BASE_URL is required for the openai_compatible provider")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.price = price
        self.timeout = timeout

    def complete_json(self, system: str, user: str, schema: dict[str, Any], max_tokens: int) -> LLMResult:
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions", timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model, "max_tokens": max_tokens, "temperature": 0,
                    "response_format": {"type": "json_schema",
                                        "json_schema": {"name": "skill_graph", "schema": schema, "strict": True}},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
            )
            resp.raise_for_status()
            body = resp.json()
            data = json.loads(body["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMError(f"openai_compatible: {exc}") from exc
        usage = body.get("usage", {})
        tin, tout = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        return LLMResult(data, tin, tout, self.price.cost(tin, tout), self.model)


def build_provider(settings: Settings) -> LLMProvider | None:
    price = Price(settings.llm_price_input_per_mtok, settings.llm_price_output_per_mtok)
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings.llm_model, settings.llm_api_key, price)
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.llm_base_url or settings.ollama_url, settings.llm_model)
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(settings.llm_base_url, settings.llm_api_key, settings.llm_model, price)
    return None
