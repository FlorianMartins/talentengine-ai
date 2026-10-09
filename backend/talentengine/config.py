"""Runtime settings. Every value can be overridden with a ``TE_``-prefixed environment variable."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENGINE_VERSION = "0.7.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TE_", env_file=".env", extra="ignore")

    # --- Storage -----------------------------------------------------------------------------------
    data_dir: Path = Path("./data")

    # --- Security ----------------------------------------------------------------------------------
    # Fernet key for the identity vault (Module 1). Generate one with `talentengine keygen`.
    # Left empty in development: a key is generated and persisted under data_dir on first start.
    vault_key: str = ""
    # HMAC key sealing every ledger entry. Same behaviour as vault_key when empty.
    ledger_seal_key: str = ""
    # When set, every /api call must carry `X-API-Key: <value>`.
    api_key: str = ""
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- Module 1: vision redaction ------------------------------------------------------------------
    # "ollama": local VLM returns bounding boxes; "opencv": Haar face detector; "none": no detector.
    # Optional statistical name detection on top of the rules: "spacy" needs the `ner` extra and the
    # fr_core_news_sm / en_core_web_sm models (see docs/MEASUREMENTS.md for its measured effect).
    ner: Literal["none", "spacy"] = "none"
    vision_detector: Literal["ollama", "opencv", "none"] = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    vision_model: str = "qwen2.5vl:7b"

    # --- Module 2: escalation tier ------------------------------------------------------------------
    # "none" keeps everything local and free. "ollama" runs the synthesis on a local model.
    llm_provider: Literal["none", "ollama", "anthropic", "openai_compatible"] = "none"
    llm_model: str = "claude-opus-5-5"
    llm_base_url: str = ""
    llm_api_key: str = ""
    # USD per million tokens, used by the budget guard. Defaults match claude-opus-5-5 list prices.
    llm_price_input_per_mtok: float = 4.0
    llm_price_output_per_mtok: float = 20.0

    # --- Module 3: AI-pilot test -----------------------------------------------------------------------
    # The assistant candidates pilot: "scripted" (reference assistant: offline, identical for everyone) or
    # "llm" (a real model such as Qwen-Coder or Llama-3 on Ollama / vLLM; planted flaws are verified, and
    # spliced in when the model did not comply).
    pilot_assistant: Literal["scripted", "llm"] = "scripted"
    pilot_llm_provider: Literal["ollama", "anthropic", "openai_compatible"] = "ollama"
    pilot_llm_model: str = "qwen2.5-coder:7b"
    pilot_llm_base_url: str = ""
    pilot_llm_api_key: str = ""
    # LLM-as-a-judge: uses the escalation provider (TE_LLM_*) when one is configured; false disables it.
    pilot_judge: bool = True
    pilot_starts_per_hour: int = 6
    # Source files kept per repository of an application, for the AI-pilot task on the candidate's own code
    # (pseudonymised like key files, never sent to the escalation model). 0 disables.
    ownership_source_files: int = 3

    # A GitHub profile link expands to all its public repositories, up to this many.
    max_repos_per_submission: int = 30
    # Optional GitHub token: raises the API rate limit from 60 to 5000 requests/hour.
    github_token: str = ""

    enable_demo: bool = True

    # Hours between automatic erasures of applications whose retention period is over (0 disables).
    retention_sweep_hours: int = 24

    # Public URL of the app (e.g. https://hivey.be/talentengine), used to verify Safe Exam Browser hashes
    # computed by the browser on the URL it sees, before any reverse-proxy rewriting.
    public_base_url: str = ""

    # --- Public sandbox (/api/try): anyone can test an offer against their own CV, nothing is stored ---
    sandbox_enabled: bool = True
    sandbox_matches_per_hour: int = 12
    sandbox_offers_per_hour: int = 40
    sandbox_concurrency: int = 2
    # Behind a reverse proxy, read the client address from X-Forwarded-For (rightmost value, set by our proxy).
    trust_proxy: bool = False
    # Built front-end to serve at "/". Empty: <repo>/frontend/dist when running from a checkout.
    frontend_dist: str = ""

    @property
    def db_path(self) -> Path:
        return self.data_dir / "talentengine.sqlite3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
