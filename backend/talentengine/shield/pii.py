"""Text pseudonymisation (Module 1).

Three passes, in this order:

1. **Detection** of personal data with deterministic, auditable rules (no model involved): e-mails,
   phone numbers, profile URLs, dates of birth, ages, postal addresses, labelled demographic fields
   (nationality, gender, family status, religion, birthplace), civility titles, the candidate's own
   name (declared at submission) and a header heuristic for the name at the top of a CV.
2. **Bias proxies**: school and university names are masked too. The *diploma* stays (it is still
   weighed, in second position) but the prestige of the institution never reaches the scoring.
3. **Gendered wording**: common gender-inflected job titles and adjectives are rewritten in an
   inclusive form (French) or a neutral pronoun (English), so grammar does not leak gender.

An optional NER backend (spaCy, Presidio, ...) can be plugged in through ``NerBackend`` to catch the
names that rules miss. Rules are the floor, not the ceiling.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from .vault import PseudonymVault

_W = r"[A-Za-zÀ-ÖØ-öø-ÿ'’\-]"  # a "word" character including accents, apostrophes and hyphens
_CAP = r"[A-ZÀ-ÖØ-Þ]"
_SP = r"[ \t]"  # horizontal space only: a multi-word match must never swallow the next line


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str


class NerBackend(Protocol):
    def persons(self, text: str) -> Iterable[tuple[int, int]]: ...


# --------------------------------------------------------------------------------------------------
# Detection rules
# --------------------------------------------------------------------------------------------------

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")),
    (
        "PROFILE_URL",
        re.compile(
            r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|gitlab\.com|twitter\.com|x\.com|"
            r"instagram\.com|behance\.net|dribbble\.com|facebook\.com|medium\.com|youtube\.com)"
            r"/[\w\-./%@]+",
            re.IGNORECASE,
        ),
    ),
    (
        "PHONE",
        re.compile(
            r"(?<![\w+])(?:\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?(?:[\s.\-]?\d{2,4}){2,4}"
            r"|0\d(?:[\s.\-]?\d{2}){4})(?!\w)"
        ),
    ),
    (
        "BIRTHDATE",
        re.compile(
            r"\b(?:né\(e\)|née|né|born|date de naissance|date of birth|DOB)\b[^\n]{0,25}?"
            r"(?:\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}(?:er)?[ \t]+" + _W + r"+[ \t]+\d{4})",
            re.IGNORECASE,
        ),
    ),
    ("AGE", re.compile(r"\b\d{2}\s?(?:ans|years old|y/o|yo)\b|\b(?:âge|age)\s*:?\s*\d{2}\b", re.IGNORECASE)),
    (
        "ADDRESS",
        re.compile(
            r"\b\d{1,4}(?:[ \t]?(?:bis|ter))?,?[ \t]+(?:rue|avenue|av\.|boulevard|bd|chemin|allée|impasse|"
            r"place|route|quai|cours|square)\b[^\n,;—|]{2,60}",
            re.IGNORECASE,
        ),
    ),
    ("ADDRESS", re.compile(r"\b\d{5}" + _SP + "+" + _CAP + _W + r"+(?:(?:" + _SP + r"|-)" + _CAP + _W + r"+){0,3}")),
    (
        "ADDRESS",
        re.compile(
            r"\b\d{1,5}[ \t]+(?:" + _CAP + r"[a-z]+[ \t]){1,3}(?:Street|St\.|Avenue|Ave\.|Road|Rd\.|Lane|"
            r"Boulevard|Blvd\.|Drive|Dr\.)"
        ),
    ),
    (
        "GENDER",
        re.compile(r"\b(?:Monsieur|Madame|Mademoiselle|Mme|Mlle|Mrs\.?|Ms\.?|Mr\.?|Miss|M\.)(?=[ \t]+" + _CAP + ")"),
    ),
    (
        "FAMILY",
        re.compile(
            r"\b(?:marié|mariée|célibataire|divorcé|divorcée|pacsé|pacsée|veuf|veuve|married|divorced|"
            r"widowed)\b|\b\d+[ \t]+(?:enfants?|children|kids)\b",
            re.IGNORECASE,
        ),
    ),
]

# Labelled fields: the label stays readable, the value up to the end of line is masked.
_LABELLED: list[tuple[str, re.Pattern[str]]] = [
    # A label may start a line or follow a separator ("Née le ... — Nationalité : française").
    (kind, re.compile(r"(?im)(?:^|[—|;•·]|\s-\s)[ \t•\-*]*(?:" + labels + r")[ \t]*[:：][ \t]*(?P<v>[^\n—|;]+)"))
    for kind, labels in [
        ("PERSON", r"nom|prénom|nom complet|name|full name|first name|last name"),
        ("NATIONALITY", r"nationalité|nationality|citizenship|citoyenneté"),
        ("GENDER", r"sexe|genre|gender|sex"),
        ("FAMILY", r"situation familiale|état civil|marital status|family status"),
        ("RELIGION", r"religion|confession"),
        ("BIRTHPLACE", r"lieu de naissance|place of birth|birthplace"),
        ("AGE", r"âge|age|date de naissance|date of birth|birth date"),
        ("ADDRESS", r"adresse|address|domicile"),
        ("PHOTO", r"photo"),
    ]
]

_SCHOOL = re.compile(
    r"\b(?:Université|Universite|University|Univ\.|École|Ecole|School|Institut|Institute|College|Collège|"
    r"Lycée|IUT|Polytech|Polytechnique|Sciences Po|HEC|ESSEC|ESCP|EDHEC|INSA|Centrale|Epitech|Epita|"
    r"Ensimag|CNAM|Conservatoire|Academy|Académie)\b"
    r"(?:[ \t]+(?:(?:of|de|du|des|la|le|en|et|and|the|für)[ \t]+|d'|d’|l'|l’)?" + _CAP + _W + r"*){0,6}",
)

# A CV usually starts with the person's name. These words mean the first line is a title instead.
_HEADER_STOPWORDS = {
    "cv", "curriculum", "vitae", "resume", "résumé", "portfolio", "profil", "profile", "développeur",
    "developer", "designer", "ingénieur", "engineer", "chef", "manager", "consultant", "responsable",
    "menuisier", "cuisinier", "graphiste", "marketing", "commercial", "data", "senior", "junior",
    "freelance", "expérience", "experience", "compétences", "skills", "contact", "lead", "head",
}


def _header_name_span(text: str) -> Span | None:
    for match in re.finditer(r"[^\n]+", text):
        line = match.group(0).strip(" \t#*•-")
        if not line:
            continue
        words = line.split()
        if not 2 <= len(words) <= 4:
            return None
        if any(w.lower().strip(",.") in _HEADER_STOPWORDS for w in words):
            return None
        if all(re.fullmatch(_CAP + _W + r"*\.?", w) for w in words):
            start = match.start() + match.group(0).index(line)
            return Span(start, start + len(line), "PERSON")
        return None
    return None


# --------------------------------------------------------------------------------------------------
# Gendered wording
# --------------------------------------------------------------------------------------------------

# (masculine, feminine, inclusive). Both forms are rewritten so that neither leaks.
_FR_GENDERED: list[tuple[str, str, str]] = [
    ("développeur", "développeuse", "développeur·euse"),
    ("ingénieur", "ingénieure", "ingénieur·e"),
    ("consultant", "consultante", "consultant·e"),
    ("directeur", "directrice", "directeur·rice"),
    ("menuisier", "menuisière", "menuisier·ère"),
    ("charpentier", "charpentière", "charpentier·ère"),
    ("cuisinier", "cuisinière", "cuisinier·ère"),
    ("couturier", "couturière", "couturier·ère"),
    ("technicien", "technicienne", "technicien·ne"),
    ("vendeur", "vendeuse", "vendeur·euse"),
    ("animateur", "animatrice", "animateur·rice"),
    ("rédacteur", "rédactrice", "rédacteur·rice"),
    ("concepteur", "conceptrice", "concepteur·rice"),
    ("assistant", "assistante", "assistant·e"),
    ("apprenti", "apprentie", "apprenti·e"),
    ("chargé", "chargée", "chargé·e"),
    ("diplômé", "diplômée", "diplômé·e"),
    ("certifié", "certifiée", "certifié·e"),
    ("passionné", "passionnée", "passionné·e"),
    ("motivé", "motivée", "motivé·e"),
    ("autodidacte", "autodidacte", "autodidacte"),
    ("chef", "cheffe", "chef·fe"),
]
_EN_PRONOUNS = {"he": "they", "she": "they", "him": "them", "his": "their", "her": "their", "hers": "theirs",
                "himself": "themself", "herself": "themself"}


def _build_gender_table() -> dict[str, str]:
    table: dict[str, str] = {}
    for masc, fem, neutral in _FR_GENDERED:
        if masc != neutral:
            table[masc] = neutral
            table[masc + "s"] = neutral + "s"
        if fem != neutral:
            table[fem] = neutral
            table[fem + "s"] = neutral + "s"
    table.update(_EN_PRONOUNS)
    return table


_GENDER_TABLE = _build_gender_table()
_GENDER_RE = re.compile(r"(?<![\w·])(" + "|".join(sorted(map(re.escape, _GENDER_TABLE), key=len, reverse=True))
                        + r")(?![\w·])", re.IGNORECASE)


def neutralise_gender(text: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        word = match.group(0)
        neutral = _GENDER_TABLE[word.lower()]
        if neutral.lower() == word.lower():
            return word
        count += 1
        if word.isupper() and len(word) > 1:
            return neutral.upper()
        return neutral[0].upper() + neutral[1:] if word[0].isupper() else neutral

    return _GENDER_RE.sub(repl, text), count


# --------------------------------------------------------------------------------------------------
# Pseudonymiser
# --------------------------------------------------------------------------------------------------


@dataclass
class PseudonymizedText:
    text: str
    counts: Counter[str] = field(default_factory=Counter)
    gendered_terms: int = 0


class TextPseudonymizer:
    def __init__(
        self,
        vault: PseudonymVault,
        *,
        mask_school_names: bool = True,
        neutralise_gendered_terms: bool = True,
        ner: NerBackend | None = None,
    ) -> None:
        self.vault = vault
        self.mask_school_names = mask_school_names
        self.neutralise_gendered_terms = neutralise_gendered_terms
        self.ner = ner

    def detect(self, text: str, known_identity: Iterable[str] = (), *, header_name: bool = True) -> list[Span]:
        spans: list[Span] = []
        for kind, pattern in _RULES:
            spans.extend(Span(m.start(), m.end(), kind) for m in pattern.finditer(text))
        for kind, pattern in _LABELLED:
            for m in pattern.finditer(text):
                value = m.group("v").strip()
                if value:
                    start = m.start("v") + m.group("v").index(value)
                    spans.append(Span(start, start + len(value), kind))
        for value in _identity_terms(known_identity):
            pattern = re.compile(r"(?<![\w@])" + re.escape(value) + r"(?![\w@])", re.IGNORECASE)
            spans.extend(Span(m.start(), m.end(), "PERSON") for m in pattern.finditer(text))
        if header_name and (span := _header_name_span(text)):
            spans.append(span)
        if self.mask_school_names:
            spans.extend(Span(m.start(), m.end(), "SCHOOL") for m in _SCHOOL.finditer(text))
        if self.ner is not None:
            spans.extend(Span(s, e, "PERSON") for s, e in self.ner.persons(text))
        return _resolve_overlaps(spans)

    def run(
        self,
        text: str,
        candidate_ref: str,
        known_identity: Iterable[str] = (),
        *,
        header_name: bool = True,
    ) -> PseudonymizedText:
        spans = self.detect(text, known_identity, header_name=header_name)
        counts: Counter[str] = Counter()
        parts: list[str] = []
        cursor = 0
        for span in spans:
            parts.append(text[cursor:span.start])
            parts.append(self.vault.token(span.kind, text[span.start:span.end], candidate_ref))
            counts[span.kind] += 1
            cursor = span.end
        parts.append(text[cursor:])
        result = "".join(parts)
        gendered = 0
        if self.neutralise_gendered_terms:
            result, gendered = neutralise_gender(result)
        return PseudonymizedText(result, counts, gendered)


def _identity_terms(values: Iterable[str]) -> list[str]:
    terms: set[str] = set()
    for value in values:
        value = value.strip()
        if not value:
            continue
        terms.add(value)
        if "@" in value:
            terms.add(value.split("@", 1)[0])  # the local part of an e-mail is often the name
            continue
        terms.update(part for part in re.split(r"[\s\-]+", value) if len(part) >= 3)
    return sorted(terms, key=len, reverse=True)


def _resolve_overlaps(spans: list[Span]) -> list[Span]:
    """Keep the earliest span; on ties keep the longest. Overlapping later spans are dropped."""
    ordered = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    kept: list[Span] = []
    for span in ordered:
        if kept and span.start < kept[-1].end:
            if span.end > kept[-1].end:  # extend so that no fragment of PII survives
                kept[-1] = Span(kept[-1].start, span.end, kept[-1].kind)
            continue
        kept.append(span)
    return kept
