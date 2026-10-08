from __future__ import annotations

from pathlib import Path

import pytest

from talentengine.config import Settings
from talentengine.dashboard.presets import preset_job
from talentengine.pipeline import Engine
from talentengine.shield.vision import NoDetector


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", vision_detector="none", llm_provider="none", enable_demo=True)


@pytest.fixture
def engine(settings: Settings) -> Engine:
    return Engine(settings, detector=NoDetector(), provider=False)


@pytest.fixture
def devsecops_job(engine: Engine):
    return engine.create_job(preset_job("devsecops", "fr"))
