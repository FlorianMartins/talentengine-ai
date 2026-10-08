# TalentEngine-AI — backend

FastAPI service implementing the four modules (shield, funnel, translator, dashboard). See the
[project README](../README.md) and [architecture manifesto](../docs/ARCHITECTURE.md).

```bash
pip install -e ".[dev,anthropic]"
talentengine seed && talentengine serve   # API docs at http://127.0.0.1:8000/api/docs
pytest -q && ruff check . && mypy talentengine
```
