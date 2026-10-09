"""Bring your own key: each recruiter can connect their own model provider.

The deployment needs no paid model: scoring, questions and the reference assistant are rule-based. A recruiter
who wants the optional parts — the LLM judge of the technical test, or a real model as the test's assistant —
enters *their* key, and pays for *their* use. Keys are:

* stored encrypted with the vault key (Fernet), one per account, never returned by the API (only the last
  four characters, as a hint);
* used only for the tests that recruiter sends (the session remembers who created it);
* sent only to the provider the recruiter chose: preset providers have fixed addresses; a custom
  OpenAI-compatible endpoint must be HTTPS on a public address (the same SSRF guard as the sandbox).

What goes to the provider: the pseudonymised transcript of a test (no name, e-mails and IBANs masked). Free
models may use prompts for training: the interface says so, and the choice is the deployer's (GDPR Art. 28).
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field

from .funnel.budget import Price
from .funnel.llm import AnthropicProvider, LLMError, LLMProvider, OpenAICompatibleProvider
from .models import utcnow
from .store import Store

ProviderId = Literal["openrouter", "anthropic", "openai", "mistral", "custom"]

PRESETS: dict[str, dict[str, str]] = {
    "openrouter": {"label": "OpenRouter (free models available)", "base_url": "https://openrouter.ai/api/v1",
                   "models_url": "https://openrouter.ai/api/v1/models", "help": "https://openrouter.ai/keys"},
    "anthropic": {"label": "Anthropic (Claude)", "base_url": "", "help": "https://console.anthropic.com/settings/keys"},
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "help": "https://platform.openai.com/api-keys"},
    "mistral": {"label": "Mistral AI", "base_url": "https://api.mistral.ai/v1",
                "help": "https://console.mistral.ai/api-keys"},
    "custom": {"label": "Other OpenAI-compatible endpoint (HTTPS)", "base_url": "", "help": ""},
}
COLLECTION = "llm_keys"
_MODELS_TTL = 3600.0


class LLMSettings(BaseModel):
    provider: ProviderId
    model: str = Field(..., min_length=2, max_length=200)
    base_url: str = Field("", max_length=300)
    use_for_judge: bool = True
    use_for_assistant: bool = False
    key_hint: str = ""
    updated_at: str = ""


class LLMSettingsInput(BaseModel):
    provider: ProviderId
    model: str = Field(..., min_length=2, max_length=200)
    base_url: str = Field("", max_length=300)
    api_key: str | None = Field(None, max_length=500, description="Omit to keep the stored key")
    use_for_judge: bool = True
    use_for_assistant: bool = False


def _owner_id(owner: str) -> str:
    return hashlib.sha256(owner.encode()).hexdigest()[:32]


def check_endpoint(url: str) -> str:
    """A custom endpoint must be HTTPS on a public address, so a key setting cannot reach internal services."""
    from .sandbox.fetch import FetchError, _check_url

    url = url.strip().rstrip("/")
    if urlsplit(url).scheme != "https":
        raise ValueError("the endpoint must use https")
    try:
        _check_url(url)
    except FetchError as exc:
        raise ValueError(str(exc)) from exc
    return url


class ByokStore:
    def __init__(self, store: Store, vault_key: str) -> None:
        self.store = store
        self.fernet = Fernet(vault_key.encode())
        self._models: tuple[float, list[dict[str, Any]]] = (0.0, [])
        self._lock = threading.Lock()

    def get(self, owner: str) -> tuple[LLMSettings, str] | None:
        row = self.store.get_json(COLLECTION, _owner_id(owner))
        if not row:
            return None
        try:
            key = self.fernet.decrypt(row["key"].encode()).decode()
        except (InvalidToken, KeyError):
            return None
        return LLMSettings.model_validate(row["settings"]), key

    def public(self, owner: str) -> dict[str, Any] | None:
        found = self.get(owner)
        return found[0].model_dump() if found else None

    def set(self, owner: str, data: LLMSettingsInput) -> LLMSettings:
        previous = self.get(owner)
        key = (data.api_key or "").strip() or (previous[1] if previous else "")
        if not key:
            raise ValueError("enter the API key of your provider")
        base_url = PRESETS[data.provider]["base_url"]
        if data.provider == "custom":
            base_url = check_endpoint(data.base_url)
        settings = LLMSettings(provider=data.provider, model=data.model.strip(), base_url=base_url,
                               use_for_judge=data.use_for_judge, use_for_assistant=data.use_for_assistant,
                               key_hint="…" + key[-4:], updated_at=utcnow().isoformat())
        self.store.put_json(COLLECTION, _owner_id(owner), {
            "settings": settings.model_dump(), "key": self.fernet.encrypt(key.encode()).decode()})
        return settings

    def delete(self, owner: str) -> bool:
        existed = self.get(owner) is not None
        self.store.delete(COLLECTION, _owner_id(owner))
        return existed

    def provider(self, owner: str, purpose: Literal["judge", "assistant", "any"] = "any") -> LLMProvider | None:
        if not owner:
            return None
        found = self.get(owner)
        if found is None:
            return None
        settings, key = found
        if (purpose == "judge" and not settings.use_for_judge) or (
                purpose == "assistant" and not settings.use_for_assistant):
            return None
        return make_provider(settings, key)

    def free_models(self) -> list[dict[str, Any]]:
        """OpenRouter's free models (public list, cached one hour): ids end with ":free"."""
        with self._lock:
            at, cached = self._models
            if cached and time.monotonic() - at < _MODELS_TTL:
                return cached
        try:
            resp = httpx.get(PRESETS["openrouter"]["models_url"], timeout=15)
            resp.raise_for_status()
            rows = resp.json().get("data", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError("the list of free models is unavailable right now") from exc
        free = sorted(({"id": m["id"], "name": m.get("name", m["id"]), "context_length": m.get("context_length")}
                       for m in rows if str(m.get("id", "")).endswith(":free")),
                      key=lambda m: -(m["context_length"] or 0))
        with self._lock:
            self._models = (time.monotonic(), free)
        return free


def make_provider(settings: LLMSettings, key: str) -> LLMProvider:
    if settings.provider == "anthropic":
        return AnthropicProvider(settings.model, key, Price(0.0, 0.0))
    base_url = settings.base_url or PRESETS[settings.provider]["base_url"]
    provider = OpenAICompatibleProvider(base_url, key, settings.model, Price(0.0, 0.0), timeout=120.0)
    provider.name = settings.provider
    return provider


def test_provider(provider: LLMProvider) -> dict[str, Any]:
    """A tiny call that proves the key, the model and JSON output all work."""
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
              "additionalProperties": False}
    result = provider.complete_json('Reply with the JSON object {"ok": true}.', "ping", schema, 50)
    return {"ok": bool(result.data.get("ok")), "model": result.model,
            "tokens": result.input_tokens + result.output_tokens}
