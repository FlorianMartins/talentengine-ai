"""Optional named-entity recognition for person names (``pip install talentengine-ai[ner]``).

Rules catch structured identifiers (e-mail, phone, labelled fields) and the name the candidate
declared; they miss *other* people's names (a manager, a client, a reference) and unusual layouts.
A statistical NER model closes that gap.

Over-masking is a real cost here: a "person" that is actually a tool or a technique would erase
evidence and hurt the candidate. So only PER entities of two capitalised words or more are used, and a
stop-list keeps technology and trade vocabulary visible. ``eval/pii_recall.py``
measures both recall and over-masking; see ``docs/MEASUREMENTS.md``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from typing import Any

# Words that statistical models regularly tag as persons in CVs but are evidence, not identity.
_KEEP = {
    "kubernetes", "terraform", "ansible", "docker", "jenkins", "grafana", "prometheus", "figma", "looker",
    "tableau", "hubspot", "salesforce", "github", "gitlab", "python", "django", "flask", "react", "angular",
    "vue", "svelte", "pandas", "spark", "kafka", "airflow", "excel", "photoshop", "illustrator", "indesign",
    "zero-trust", "haccp", "scrum", "agile", "kanban", "devops", "devsecops", "linux", "windows", "azure",
    "aws", "gcp", "opa", "rego", "trivy", "gitleaks", "codeql", "dependabot", "helm", "argo", "argocd",
    "redis", "postgres", "postgresql", "mysql", "mongodb", "node", "deno", "rust", "golang", "java",
    "kotlin", "swift", "flutter", "ruby", "rails", "laravel", "symfony", "wordpress", "shopify", "notion",
    "jira", "confluence", "slack", "meta", "google", "mailchimp", "semrush", "ahrefs", "canva", "sketch",
}
# Degree acronyms and titles: "CAP Menuisier" was tagged as a person and erased a diploma (demo data).
_CREDENTIALS = {"cap", "bep", "bts", "dut", "but", "mba", "bac", "master", "licence", "bachelor", "doctorat", "phd",
                "brevet", "titre", "diplôme", "certificat", "msc", "bsc", "rncp", "deug", "dess", "dea"}
_PARTICLES = {"de", "du", "des", "da", "dos", "di", "del", "van", "von", "der", "la", "le", "el", "al", "bin", "ben"}


def _name_like(token: str) -> bool:
    if token.lower() in _PARTICLES:
        return True
    letters = re.sub(r"['’\-]", "", token)
    return letters.isalpha() and token[0].isupper()


@lru_cache(maxsize=2)
def _load(model: str) -> Any:
    import spacy

    return spacy.load(model, disable=["lemmatizer", "tagger", "parser", "attribute_ruler", "morphologizer"])


class SpacyNer:
    """NerBackend running the French and English small models and merging their PER spans."""

    def __init__(self, models: Iterable[str] = ("fr_core_news_sm", "en_core_web_sm")) -> None:
        self.models = tuple(models)
        for name in self.models:
            _load(name)  # fail fast at start-up rather than on the first candidate

    def persons(self, text: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        for name in self.models:
            for ent in _load(name)(text).ents:
                if ent.label_ not in ("PER", "PERSON"):
                    continue
                tokens = ent.text.split()
                if any(t.lower().strip(".,") in _NOT_NAMES for t in tokens):
                    continue
                if "\n" in ent.text or not all(_name_like(t) for t in tokens):
                    continue  # names are capitalised words on one line; anything else is noise
                if len(tokens) < 2:
                    continue  # a lone capitalised word is too often a verb or a tool ("Négocié", "Jenkins")
                spans.append((ent.start_char, ent.end_char))
        return spans


def _not_names() -> set[str]:
    from .pii import _HEADER_STOPWORDS  # job titles and trades, already curated for the header heuristic

    return _KEEP | _CREDENTIALS | _HEADER_STOPWORDS


_NOT_NAMES = _not_names()


def build_ner(kind: str) -> SpacyNer | None:
    return SpacyNer() if kind == "spacy" else None
