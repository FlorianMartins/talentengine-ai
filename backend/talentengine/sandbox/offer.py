"""Turn a job offer (pasted text or a fetched page) into an editable job profile.

Deterministic and explainable, like the rest of Level 1: every criterion comes with the offer lines that
produced it, so the user can see *why* a skill was detected and remove or re-weight it before matching.

* Skills: the same work vocabulary as the document analyser, plus a few offer-specific terms.
* Importance: "indispensable / required / must" → essential; "un plus / nice to have / idéalement" →
  bonus; otherwise important. A skill mentioned in several places is promoted.
* Required level: years of experience and seniority words ("5 ans", "senior", "junior", "confirmé").
* Credentials: diplomas and certifications named in the offer become the accepted list, still capped.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from pydantic import BaseModel

from ..funnel.documents import _CERT, _DEGREE, _VOCAB_RE
from ..models import CredentialsPolicy, Criterion, Family, Importance, JobProfile
from ..translator.catalog import CATALOG

_EXTRA: dict[str, str] = {
    "automated_testing": r"tests?|TDD|qualité logicielle|software quality",
    "ci_cd": r"intégration continue|déploiement continu|DevOps|pipelines?",
    "backend_development": r"back-?end|API|REST|GraphQL|microservices?|Node\.?js|Django|FastAPI|Spring|Laravel|Symfony",
    "frontend_development": r"front-?end|React|Vue(?:\.js)?|Angular|Svelte|TypeScript|JavaScript|HTML|CSS",
    "database_design": r"SQL|PostgreSQL|MySQL|MongoDB|bases? de données|databases?|modélisation de données",
    "security_engineering": r"sécurité|security|cybersécurité|cybersecurity|DevSecOps|SOC|SIEM",
    "software_architecture": r"architecture|conception logicielle|design patterns?|clean code",
    "technical_documentation": r"documentation",
    "data_analysis": r"analyse de données|data analysis|BI\b|business intelligence|KPI",
    "project_management": r"gestion de projets?|project management|chef de projet|agile|scrum",
    "team_leadership": r"management d'équipe|manager une équipe|encadrement|leadership|lead",
    "structured_communication": r"rédaction|communication écrite|reporting|présentations?|synthèse",
    "sales_pipeline": r"commercial|vente|business developer|prospection|négociation",
}
_EXTRA_RE = {k: re.compile(r"(?<!\w)(?:" + v + r")(?!\w)", re.IGNORECASE) for k, v in _EXTRA.items() if v}

_ESSENTIAL = re.compile(r"indispensable|obligatoire|impérati\w+|exigée?s?|requise?s?|required|must|mandatory|"
                        r"essential|maîtrise (?:parfaite|impérative)|vous maîtrisez|strong (?:experience|knowledge)",
                        re.IGNORECASE)
_BONUS = re.compile(r"un plus|serait un (?:plus|atout)|apprécié|souhaité|idéalement|bonus|nice to have|"
                    r"is a plus|preferred|would be great|optionnel|atout", re.IGNORECASE)
# Sections that describe the company or the perks, not the job: "Carte Swile" is not a culinary skill.
_IGNORED_SECTION = re.compile(r"avantages|benefits|perks|qui sommes[- ]nous|à propos|about (?:us|the company)|"
                              r"pourquoi nous rejoindre|why (?:join|us)|notre entreprise|l'entreprise|our company|"
                              r"rémunération|salaire|salary|compensation|processus de recrutement|hiring process",
                              re.IGNORECASE)
_HIRING = re.compile(r"\b(?:nous )?recrut\w*|\bwe(?:'re| are) hiring\b|\bhiring\b|\brecherchons\b", re.IGNORECASE)
# Section titles written without a colon ("Missions", "Profil recherché") must still close the previous section,
# or a "Bonus :" section would swallow the whole rest of the offer.
_SECTION_TITLE = re.compile(
    r"^(?:vos |les |nos |the |your |key )?(?:missions?|responsabilités|responsibilities|le poste|the role|"
    r"description du poste|job description|profil(?: recherché)?|profile|requirements|qualifications|"
    r"compétences(?: attendues| requises| techniques)?|skills|prérequis|stack(?: technique)?|tech stack|"
    r"environnement technique|bonus|nice to have|un plus|atouts|avantages|benefits|perks|qui sommes-nous|"
    r"à propos|about(?: us)?|l'entreprise|notre entreprise|pourquoi nous rejoindre|why join us|"
    r"rémunération|salaire|salary|processus de recrutement|hiring process|ce que nous offrons|what we offer)"
    r"\s*[:?!.]?$", re.IGNORECASE)
_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|ans|années|years?)", re.IGNORECASE)
_SENIOR = re.compile(r"\b(?:senior|confirmée?|expérimentée?|expert|lead|principal|staff)\b", re.IGNORECASE)
_JUNIOR = re.compile(r"\b(?:junior|débutante?|alternance|stage|stagiaire|graduate|entry[- ]level|apprenti)",
                     re.IGNORECASE)


class OfferCriterionTrace(BaseModel):
    skill_id: str
    label: str
    importance: Importance
    mentions: int
    lines: list[str]


class ParsedOffer(BaseModel):
    job: JobProfile
    traces: list[OfferCriterionTrace]
    warnings: list[str]


class OfferError(ValueError):
    pass


def _level_from_text(text: str) -> float:
    years = [int(y) for y in _YEARS.findall(text) if 0 < int(y) < 30]
    if years:
        y = max(years)
        return 1.5 if y <= 1 else 2.0 if y <= 3 else 2.5 if y <= 6 else 3.0
    if _SENIOR.search(text):
        return 2.75
    if _JUNIOR.search(text):
        return 1.5
    return 2.0


def parse_offer(text: str, *, title: str = "", locale: str = "fr", max_criteria: int = 10) -> ParsedOffer:
    text = text.strip()
    if len(text) < 60:
        raise OfferError("the offer is too short to analyse: paste the full description")
    mentions: Counter[str] = Counter()
    lines_by_skill: dict[str, list[str]] = defaultdict(list)
    importance_votes: dict[str, list[Importance]] = defaultdict(list)
    section_bonus = section_essential = section_ignored = False
    for raw in text.splitlines():
        line = raw.strip(" \t•-*·")
        if not line:
            continue
        lowered = line.lower()
        is_heading = (len(line) < 60 and line.endswith(":")) or (len(line) < 50 and line.isupper()) \
            or (len(line) < 40 and line.endswith("?")) or bool(_SECTION_TITLE.match(line))
        if is_heading:
            section_ignored = bool(_IGNORED_SECTION.search(lowered))
            section_bonus = bool(_BONUS.search(lowered)) or "souhait" in lowered or "nice" in lowered
            section_essential = bool(_ESSENTIAL.search(lowered)) or "profil recherché" in lowered \
                or "requirements" in lowered or "prérequis" in lowered or "compétences attendues" in lowered
            continue
        if section_ignored:
            continue
        # Every offer talks about recruiting ("nous recrutons"): that is the employer, not a skill to evidence.
        probe = _HIRING.sub(" ", line)
        found = {s for s, p in _VOCAB_RE.items() if p.search(probe)}
        found |= {s for s, p in _EXTRA_RE.items() if p.search(probe)}
        found &= set(CATALOG)
        if not found:
            continue
        vote = (Importance.essential if _ESSENTIAL.search(line) or (section_essential and not _BONUS.search(line))
                else Importance.bonus if _BONUS.search(line) or section_bonus else Importance.important)
        for skill in found:
            mentions[skill] += 1
            importance_votes[skill].append(vote)
            if len(lines_by_skill[skill]) < 3:
                lines_by_skill[skill].append(line[:200])
    if not mentions:
        raise OfferError("no skill from the catalogue was found in this offer: try pasting the full text, "
                         "or pick a reference role")

    chosen = [s for s, _ in mentions.most_common(max_criteria)]
    level = _level_from_text(text)
    criteria, traces = [], []
    for skill in chosen:
        votes = importance_votes[skill]
        if Importance.essential in votes:
            importance = Importance.essential
        elif mentions[skill] >= 3 or votes.count(Importance.important) > votes.count(Importance.bonus):
            importance = Importance.important
        else:
            importance = Importance.bonus
        min_level = level if importance != Importance.bonus else max(1.0, level - 0.5)
        criteria.append(Criterion(skill_id=skill, importance=importance, min_level=round(min_level, 2),
                                  weight=1.0 + 0.25 * min(4, mentions[skill] - 1)))
        traces.append(OfferCriterionTrace(skill_id=skill, label=CATALOG[skill].l(locale),  # type: ignore[arg-type]
                                          importance=importance, mentions=mentions[skill], lines=lines_by_skill[skill]))

    accepted: list[str] = []
    for line in text.splitlines():
        for m in list(_DEGREE.finditer(line)) + list(_CERT.finditer(line)):
            value = m.group(0).strip()
            if value.lower().startswith("certifi"):
                continue
            if value not in accepted:
                accepted.append(value)
    families = Counter(CATALOG[s].family for s in chosen)
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    job_title = (title or first_line)[:160] or ("Offre analysée" if locale == "fr" else "Analysed offer")
    if len(job_title) < 2:
        job_title = "Offre analysée"
    warnings = []
    if len(chosen) < 3:
        warnings.append("few skills were detected: check the list and add criteria if needed"
                        if locale == "en" else
                        "peu de compétences détectées : vérifiez la liste et ajoutez des critères si besoin")
    job = JobProfile(
        title=job_title, summary=text[:600], family=families.most_common(1)[0][0] if families else Family.transversal,
        locale=locale,
        criteria=criteria, credentials=CredentialsPolicy(accepted=accepted[:8]),
    )
    return ParsedOffer(job=job, traces=traces, warnings=warnings)
