"""Bring your own key: per-recruiter model keys for the technical test's judge and assistant."""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from talentengine.api.app import create_app
from talentengine.auth import UserStore
from talentengine.byok import ByokStore, LLMSettingsInput
from talentengine.config import Settings
from talentengine.dashboard.presets import preset_job
from talentengine.funnel.budget import Price
from talentengine.funnel.llm import LLMError, LLMResult, OpenAICompatibleProvider
from talentengine.pipeline import Engine, Submission, TextDocument
from talentengine.shield.vision import NoDetector


def _byok(settings: Settings) -> tuple[Engine, ByokStore]:
    engine = Engine(settings, detector=NoDetector(), provider=False)
    return engine, ByokStore(engine.store, engine.vault_key)


def test_keys_are_encrypted_hidden_kept_and_removed(settings: Settings) -> None:
    engine, byok = _byok(settings)
    byok.set("Alex", LLMSettingsInput(provider="openrouter", model="some/model:free", api_key="sk-or-secret-1234"))
    raw = engine.store.query("SELECT body FROM documents WHERE collection = 'llm_keys'")[0]["body"]
    assert "sk-or-secret" not in raw  # encrypted at rest
    public = byok.public("Alex")
    assert public["key_hint"] == "…1234" and "api_key" not in public
    assert public["base_url"] == "https://openrouter.ai/api/v1"
    byok.set("Alex", LLMSettingsInput(provider="openrouter", model="other/model:free", use_for_judge=False))
    settings_, key = byok.get("Alex")
    assert key == "sk-or-secret-1234" and settings_.model == "other/model:free"  # key kept when omitted
    assert byok.provider("Alex", "judge") is None and byok.provider("Alex") is not None
    with pytest.raises(ValueError):
        byok.set("Bob", LLMSettingsInput(provider="openrouter", model="m/m"))  # no key at all
    assert byok.delete("Alex") and byok.get("Alex") is None


@pytest.mark.parametrize("url", ["http://api.example.com/v1", "https://127.0.0.1/v1", "https://localhost/v1",
                                 "https://10.0.0.5/v1"])
def test_a_custom_endpoint_cannot_reach_internal_services(settings: Settings, url: str) -> None:
    _, byok = _byok(settings)
    with pytest.raises(ValueError):
        byok.set("Alex", LLMSettingsInput(provider="custom", model="m", base_url=url, api_key="k"))


class _Resp:
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


def test_free_models_without_structured_output_still_answer_json(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    replies = [_Resp(400, {}), _Resp(200, {"choices": [{"message": {"content": '```json\n{"ok": true}\n```'}}],
                                             "usage": {"prompt_tokens": 5, "completion_tokens": 2}})]

    def post(url: str, **kw: Any) -> _Resp:
        calls.append(kw["json"])
        return replies.pop(0)

    monkeypatch.setattr(httpx, "post", post)
    provider = OpenAICompatibleProvider("https://openrouter.ai/api/v1", "k", "m:free", Price(0, 0))
    result = provider.complete_json("s", "u", {"type": "object"}, 10)
    assert result.data == {"ok": True}
    assert calls[0]["response_format"]["type"] == "json_schema" and calls[1]["response_format"]["type"] == "json_object"
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Resp(429, {}))
    with pytest.raises(LLMError, match="quota"):
        provider.complete_json("s", "u", {"type": "object"}, 10)


def test_only_free_openrouter_models_are_listed(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Get:
        def raise_for_status(self) -> None: ...

        def json(self) -> dict[str, Any]:
            return {"data": [{"id": "a/paid"}, {"id": "b/small:free", "context_length": 8000},
                             {"id": "c/large:free", "context_length": 128000}]}

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _Get())
    _, byok = _byok(settings)
    assert [m["id"] for m in byok.free_models()] == ["c/large:free", "b/small:free"]


class FakeJudge:
    name = "openrouter"
    model = "judge/model:free"

    def complete_json(self, system: str, user: str, schema: dict[str, Any], max_tokens: int) -> LLMResult:
        dim = {"applicable": True, "score": 100, "rationale": "framed", "evidence_turns": []}
        return LLMResult({"intent_precision": dim, "critical_thinking": dim, "ownership": dim,
                          "fault_callouts": [], "manipulation_turns": []}, 10, 10, 0.0, self.model)


def test_a_recruiters_own_key_judges_their_tests_in_the_background(settings: Settings,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    users = UserStore(settings.data_dir / "users.json")
    rec = {"X-API-Key": users.add("Alex recruiter", "recruiter")}
    dpo = {"X-API-Key": users.add("Dana dpo", "dpo")}
    engine = Engine(settings, detector=NoDetector(), provider=False)
    app = create_app(settings, engine)
    client = TestClient(app)
    body = {"provider": "openrouter", "model": "judge/model:free", "api_key": "sk-or-v1-abcd"}
    assert client.put("/api/me/llm", json=body, headers=dpo).status_code == 403
    saved = client.put("/api/me/llm", json=body, headers=rec).json()["settings"]
    assert saved["key_hint"] == "…abcd" and "sk-or" not in str(client.get("/api/me/llm", headers=rec).json())
    pilot = app.state.pilot
    monkeypatch.setattr(pilot.byok, "provider", lambda owner, purpose="any": FakeJudge()
                        if owner == "Alex recruiter" and purpose != "assistant" else None)
    job = engine.create_job(preset_job("ai_engineer", "fr"))
    cand = engine.ingest(job.id, Submission(consent=True, identity_name="Camille Rousseau", documents=[
        TextDocument(name="cv.txt", content="Ingénieure LLM.", kind="cv")]))
    created = client.post(f"/api/candidates/{cand.ref}/pilot", headers=rec, json={
        "knowledge_questions": 0, "ai_questions": 0, "ownership": False}).json()
    assert created["judge"] == "openrouter/judge/model:free"
    token = created["token"]
    client.post(f"/api/pilot/{token}/begin")
    client.post(f"/api/pilot/{token}/chat", json={"message": "fais un truc sûr"})
    assert client.post(f"/api/pilot/{token}/close").json() == {"closed": True, "mode": "candidate"}
    for _ in range(50):  # the candidate did not wait; the judge finishes in the background
        report = client.get(f"/api/candidates/{cand.ref}/pilot", headers=rec).json()[0]["report"]
        if not report["judge"].startswith("pending"):
            break
        time.sleep(0.05)
    assert report["judge"] == "openrouter/judge/model:free"
    assert any(e.kind == "pilot_judged" for e in engine.ledger.entries(candidate_ref=cand.ref, limit=50))
    assert client.delete("/api/me/llm", headers=rec).json() == {"removed": True}
    kinds = [e.kind for e in engine.ledger.entries(limit=200)]
    assert "llm_key_set" in kinds and "llm_key_removed" in kinds
