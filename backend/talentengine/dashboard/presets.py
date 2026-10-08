"""Ready-made job profiles. Recruiters start from one and tune everything in the configuration studio."""

from __future__ import annotations

from typing import Any

from ..models import AxisWeights, CredentialsPolicy, Criterion, Family, Importance, JobProfile

E, IMP, B = Importance.essential, Importance.important, Importance.bonus


def _c(skill_id: str, importance: Importance, min_level: float = 2.0, weight: float = 1.0) -> Criterion:
    return Criterion(skill_id=skill_id, importance=importance, min_level=min_level, weight=weight)


PRESETS: dict[str, dict[str, Any]] = {
    "devsecops": {
        "family": Family.software,
        "title": {"fr": "Ingénieur·e DevSecOps", "en": "DevSecOps Engineer"},
        "summary": {"fr": "Automatiser, sécuriser et fiabiliser la livraison logicielle.",
                    "en": "Automate, secure and harden software delivery."},
        "criteria": [_c("ci_cd", E, 2.5), _c("security_engineering", E, 2.5), _c("infrastructure_as_code", IMP),
                     _c("containerization", IMP), _c("automated_testing", IMP), _c("technical_documentation", B, 1.5)],
        "axis": AxisWeights(autonomy=1, complexity=1, reliability=1.5),
        "credentials": ["AWS Certified", "CKA", "CKS", "Security+"],
    },
    "fullstack": {
        "family": Family.software,
        "title": {"fr": "Développeur·euse full-stack", "en": "Full-stack Developer"},
        "summary": {"fr": "Construire des produits web de bout en bout.",
                    "en": "Build web products end to end."},
        "criteria": [_c("frontend_development", E), _c("backend_development", E), _c("automated_testing", IMP),
                     _c("software_architecture", IMP), _c("database_design", B, 1.5), _c("ci_cd", B, 1.5)],
        "axis": AxisWeights(),
        "credentials": [],
    },
    "ui_designer": {
        "family": Family.design,
        "title": {"fr": "Designer UI/UX", "en": "UI/UX Designer"},
        "summary": {"fr": "Concevoir des interfaces claires, testées auprès de vrais utilisateurs.",
                    "en": "Design clear interfaces tested with real users."},
        "criteria": [_c("ui_design", E, 2.5), _c("ux_research", IMP), _c("visual_identity", IMP),
                     _c("experimentation", B, 1.5), _c("structured_communication", B, 1.5)],
        "axis": AxisWeights(autonomy=1, complexity=1.5, reliability=0.75),
        "credentials": [],
    },
    "growth_marketer": {
        "family": Family.marketing,
        "title": {"fr": "Growth marketer", "en": "Growth Marketer"},
        "summary": {"fr": "Piloter l'acquisition par la donnée et l'expérimentation.",
                    "en": "Drive acquisition through data and experimentation."},
        "criteria": [_c("campaign_performance", E, 2.5), _c("funnel_design", E), _c("experimentation", IMP),
                     _c("data_analysis", IMP), _c("budget_management", IMP), _c("content_strategy", B, 1.5)],
        "axis": AxisWeights(autonomy=1, complexity=1, reliability=1.5),
        "credentials": ["Google Ads", "Google Analytics", "Meta Blueprint"],
    },
    "account_executive": {
        "family": Family.sales,
        "title": {"fr": "Commercial·e grands comptes", "en": "Account Executive"},
        "summary": {"fr": "Développer un portefeuille et conclure des ventes complexes.",
                    "en": "Grow a portfolio and close complex deals."},
        "criteria": [_c("sales_pipeline", E, 2.5), _c("structured_communication", IMP), _c("data_analysis", B, 1.5),
                     _c("project_management", B, 1.5)],
        "axis": AxisWeights(autonomy=1.5, complexity=1, reliability=1),
        "credentials": [],
    },
    "cabinetmaker": {
        "family": Family.craft,
        "title": {"fr": "Menuisier·ère agenceur·euse", "en": "Cabinetmaker / Joiner"},
        "summary": {"fr": "Fabriquer et poser des ouvrages bois sur mesure.",
                    "en": "Build and install bespoke timber work."},
        "criteria": [_c("woodworking", E, 2.5), _c("construction_works", IMP), _c("quality_control", IMP),
                     _c("project_management", B, 1.5), _c("budget_management", B, 1.5)],
        "axis": AxisWeights(autonomy=1.25, complexity=1.5, reliability=1),
        "credentials": ["CAP", "Brevet professionnel"],
    },
    "line_cook": {
        "family": Family.culinary,
        "title": {"fr": "Chef·fe de partie", "en": "Chef de partie"},
        "summary": {"fr": "Tenir un poste en cuisine avec régularité et hygiène irréprochable.",
                    "en": "Run a kitchen station with consistency and flawless hygiene."},
        "criteria": [_c("culinary_technique", E, 2.5), _c("food_safety", E, 2.0), _c("team_leadership", B, 1.5),
                     _c("quality_control", IMP)],
        "axis": AxisWeights(autonomy=1, complexity=1.25, reliability=1.5),
        "credentials": ["HACCP", "CAP"],
    },
    "dressmaker": {
        "family": Family.textile,
        "title": {"fr": "Modéliste couturier·ère", "en": "Pattern maker / Dressmaker"},
        "summary": {"fr": "Du patron à la pièce finie.", "en": "From pattern to finished garment."},
        "criteria": [_c("garment_construction", E, 2.5), _c("quality_control", IMP), _c("visual_identity", B, 1.5)],
        "axis": AxisWeights(autonomy=1, complexity=1.5, reliability=1),
        "credentials": [],
    },
}


def preset_job(preset_id: str, locale: str = "fr") -> JobProfile:
    p = PRESETS[preset_id]
    return JobProfile(
        title=p["title"][locale], summary=p["summary"][locale], family=p["family"], locale=locale,
        criteria=[c.model_copy() for c in p["criteria"]], axis_weights=p["axis"].model_copy(),
        credentials=CredentialsPolicy(accepted=list(p["credentials"])),
    )


def list_presets(locale: str = "fr") -> list[dict[str, Any]]:
    return [{"id": pid, "family": p["family"], "title": p["title"][locale], "summary": p["summary"][locale],
             "job": preset_job(pid, locale).model_dump(mode="json")} for pid, p in PRESETS.items()]
