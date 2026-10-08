"""Level 1, non-IT: structure extraction from documents, CVs, image captions and portfolio notes.

The rule that matters: **a claim is not a proof**. "Proficient in Google Ads" in a skills list is a
declaration and scores nothing; "Cut CPA by 32% on a 40 k€ Google Ads budget" in a project
description is evidence: it is anchored (a number, an outcome) and attributable (an action verb).
Declared skills are kept apart and become interview topics instead of points.

Diplomas and certifications are extracted separately (``extract_credentials``): they are weighed, in
second position, by Module 4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Artifact, ArtifactKind, CredentialItem, EvidenceRef, Signal

_NUM = r"\d[\d\s.,]*"
_QUANT = re.compile(
    r"(?:\d[\d\s.,]*\s?(?:%|€|\$|£|k€|K€|M€|k\$|M\$|x\b|×|pts?\b|points?\b|k\b|K\b|M\b|heures|hours|h\b|"
    r"jours|days|semaines|weeks|mois|months|m²|m2|m³|kg|cm|mm|couverts|clients|users|utilisateurs|leads|"
    r"visiteurs|visitors|personnes|people|ventes|sales|deals))|(?:[+\-−]\s?\d[\d.,]*\s?%)",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"\b(?:réalisé|réalisée|conçu|conçue|construit|construite|créé|créée|développé|développée|piloté|pilotée|"
    r"lancé|lancée|mis en place|déployé|déployée|optimisé|optimisée|réduit|augmenté|doublé|triplé|généré|"
    r"livré|livrée|fabriqué|fabriquée|rénové|rénovée|monté|montée|cousu|cousue|dirigé|dirigée|encadré|"
    r"géré|gérée|négocié|signé|built|designed|created|developed|led|launched|shipped|delivered|deployed|"
    r"reduced|increased|grew|doubled|generated|managed|negotiated|closed|crafted|made|renovated|sewed)\b",
    re.IGNORECASE,
)
_OWNERSHIP = re.compile(
    r"\b(?:de A à Z|seul|seule|en autonomie|from scratch|end[- ]to[- ]end|single-handedly|on my own|"
    r"freelance|indépendant|fondé|fondée|founded|own business|à mon compte|de bout en bout|porteur du projet)\b",
    re.IGNORECASE,
)
_CONTROL = re.compile(
    r"\b(?:contrôle|contrôlé|vérifi\w+|test\w*|recette|audit\w*|checklist|mesur\w+|suivi|KPI|tableau de bord|"
    r"dashboard|tolérance|tolerance|inspection|norme|DTU|HACCP|ISO\s?\d+|quality|qualité|monitor\w*)\b",
    re.IGNORECASE,
)

_HEADING_CLAIMS = re.compile(
    r"^(?:compétences|competences|skills|outils|tools|logiciels|software|langues|languages|centres d'intérêt|"
    r"intérêts|interests|hobbies|savoir-être|soft skills|qualités|atouts|stack|technologies)\b",
    re.IGNORECASE,
)
_HEADING_EDU = re.compile(
    r"^(?:formation|formations|education|diplômes|diplomes|études|etudes|certifications?|parcours scolaire|"
    r"cursus|academic)\b",
    re.IGNORECASE,
)
_HEADING_BODY = re.compile(
    r"^(?:expériences?|experiences?|expérience professionnelle|work experience|parcours|projets?|projects?|"
    r"réalisations|achievements|profil|profile|summary|résumé|à propos|about|contact|portfolio|synthèse|"
    r"références|references|activités|activities|bénévolat|volunteering)\b",
    re.IGNORECASE,
)
_CLAIM_LINE = re.compile(
    r"^(?:maîtrise|maitrise|connaissances?|bonne connaissance|notions|proficient|familiar|knowledge of|"
    r"expert en|expert in|compétent|skilled in)\b",
    re.IGNORECASE,
)

# Vocabulary of *work*, not of credentials. A match only becomes a signal with an anchor (see above).
_VOCAB: dict[str, str] = {
    "campaign_performance": r"ROAS|CPA|CPC|CPM|CTR|CAC|LTV|coût par|cost per|taux de clic|click[- ]through|"
                            r"impressions|ad spend|dépenses? publicitaires?|Google Ads|Meta Ads|Facebook Ads|"
                            r"LinkedIn Ads|TikTok Ads|campagnes?|campaigns?|retargeting|enchères|bidding",
    "funnel_design": r"tunnel|funnel|landing pages?|pages? d'atterrissage|TOFU|MOFU|BOFU|lead magnet|nurturing|"
                     r"taux de conversion|conversion rate|onboarding|checkout|panier|séquence e-?mail|"
                     r"email sequence|parcours d'achat",
    "experimentation": r"A/B|AB test|test A/B|split test|variantes?|variants?|significati\w+|p-value|hypothès\w+|"
                       r"hypothes\w+|uplift|expérimentation|experiment\w*",
    "content_strategy": r"SEO|mots[- ]clés|keywords|trafic organique|organic traffic|calendrier éditorial|"
                        r"editorial calendar|backlinks|articles? de blog|blog posts?|newsletter|ligne éditoriale",
    "sales_pipeline": r"pipeline commercial|sales pipeline|CRM|Salesforce|HubSpot|closing|deals?|quota|"
                      r"chiffre d'affaires|revenue|ARR|MRR|prospects?|prospection|rendez-vous|meetings booked|"
                      r"taux de transformation|win rate|portefeuille clients?|account",
    "budget_management": r"budget|enveloppe|coût total|total cost|devis|P&L|marge|margin|rentabilité|"
                         r"profitability|dépenses|expenses|forecast|prévisionnel",
    "team_leadership": r"équipe de \d+|team of \d+|encadr\w+|managed \d+|supervis\w+|recrut\w+|mentor\w*|"
                       r"tutorat|tuteur|formé \d+|trained \d+|chef d'équipe|team lead",
    "project_management": r"planning|jalons?|milestones?|sprints?|roadmap|feuille de route|phases?|Gantt|"
                          r"livrables?|deliverables?|deadline|échéance|kick-?off|recette|rétroplanning|"
                          r"coordination|coordonné|coordinated|parties prenantes|stakeholders",
    "data_analysis": r"dashboard|tableau de bord|Looker|Tableau|Power BI|Excel|SQL|cohortes?|cohorts?|"
                     r"segmentation|analyse|analysis|régression|regression|corrélation|correlation|statisti\w+|"
                     r"attribution|reporting",
    "quality_control": r"contrôle qualité|quality control|QC\b|inspection|tolérances?|non-conformit\w+|"
                       r"audit|checklist|ISO\s?\d+|DTU|autocontrôle|réception",
    "food_safety": r"HACCP|traçabilité|traceability|DLC|températures?|marche en avant|plan de maîtrise sanitaire|"
                   r"PMS\b|allergènes|allergens",
    "culinary_technique": r"cuisson|basse température|sous[- ]vide|fonds? de|sauces?|émulsion|dressage|"
                          r"pâtisserie|pastry|fermentation|braisé|confit|mise en place|fiche technique|brigade|"
                          r"plating|couverts|menu|carte|gastronomi\w+|chef de partie|second de cuisine",
    "woodworking": r"tenons?|mortaises?|queue d'aronde|aronde|mi-bois|chêne|hêtre|frêne|noyer|douglas|"
                   r"lamellé|charpente|ébénisterie|menuiserie|assemblages?|dovetail|mortise|joinery|rabot|"
                   r"toupie|CNC|escalier|parquet|placage|marqueterie|timber|woodwork\w*",
    "construction_works": r"chantiers?|rénovation|renovation|gros œuvre|second œuvre|plâtrerie|placo|"
                          r"maçonnerie|isolation|carrelage|plomberie|électricité|métré|réception des travaux|"
                          r"corps de métier|construction site|refurbish\w*|extension",
    "metalwork": r"soudure|souder|soudé|TIG|MIG|MAG|inox|acier|aluminium|métallerie|chaudronnerie|welding|"
                 r"weld\w*|serrurerie|ferronnerie|pliage|découpe plasma",
    "garment_construction": r"patrons?|patronage|toile d'essai|gradation|surjet|couture anglaise|biais|"
                            r"droit fil|ourlets?|doublure|pattern making|seams?|hems?|lining|draping|moulage|"
                            r"confection|garments?|collection",
    "ui_design": r"Figma|Sketch|Adobe XD|maquettes?|wireframes?|prototypes?|design system|interfaces?|UI\b|"
                 r"écrans?|screens?|responsive|accessibilit\w+|WCAG|contraste|contrast|composants|components",
    "visual_identity": r"logos?|charte graphique|identité visuelle|visual identity|typographi\w+|palette|"
                       r"branding|brand book|Illustrator|InDesign|Photoshop|affiches?|posters?|packaging|"
                       r"print|édition|illustration",
    "ux_research": r"entretiens? utilisateurs?|user interviews?|tests? utilisateurs?|usability|utilisabilité|"
                   r"personas?|parcours utilisateurs?|user journeys?|card sorting|SUS\b|tests? de guérilla",
    "machine_learning": r"modèle prédictif|predictive model|machine learning|apprentissage automatique|"
                        r"accuracy|F1|AUC|précision|recall|entraîn\w+|training set|fine-?tun\w+|classifi\w+",
    "data_engineering": r"pipeline de données|data pipeline|ETL|ELT|Airflow|dbt|Spark|Kafka|entrepôt de données|"
                        r"data warehouse|ingestion",
    "ci_cd": r"CI/CD|intégration continue|continuous integration|déploiement continu|continuous delivery|"
             r"continuous deployment|pipelines? (?:CI|de déploiement|de livraison)|GitHub Actions|GitLab CI|Jenkins|"
             r"mise en production|release",
    "containerization": r"Docker|conteneurs?|containers?|Kubernetes|K8s|Helm|OpenShift|Podman",
    "infrastructure_as_code": r"Terraform|Ansible|Pulumi|CloudFormation|Infrastructure as Code|IaC|"
                              r"provisionnement|provisioning",
    "automated_testing": r"tests? (?:unitaires|automatisés|d'intégration|de bout en bout)|unit tests?|"
                         r"automated tests?|end-to-end tests?|couverture de tests?|test coverage|couverture \d+|"
                         r"pytest|Jest|Cypress|Playwright|TDD",
    "software_architecture": r"architecture|microservices?|monolithe modulaire|event-driven|hexagonal|"
                             r"scalabilité|scalability",
    "security_engineering": r"Zero[- ]Trust|moindre privilège|least privilege|chiffrement|encryption|IAM|SSO|"
                            r"pentest|vulnérabilit\w+|vulnerabilit\w+|RGPD|GDPR|ISO 27001|SOC ?2",
}
_VOCAB_RE = {
    skill: re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)", re.IGNORECASE) for skill, pattern in _VOCAB.items()
}

_DEGREE = re.compile(
    r"\b(?:Master|Mastère|MBA|Licence|Bachelor(?:'s)?|BTS|DUT|BUT|CAP|BEP|Bac(?:calauréat)?(?:\s*\+\s*\d)?|"
    r"Doctorat|PhD|Ph\.D|Diplôme d'ingénieur|Engineering degree|MSc|BSc|M\.Sc|B\.Sc|Titre professionnel|"
    r"RNCP|Brevet professionnel|Master's|Associate degree|DEUG|DESS|DEA|HND)\b"
)
_CERT = re.compile(
    r"\b(?:certifi\w+|certificate|AWS Certified[\w\s\-]*|Azure [\w\-]+ (?:Associate|Expert)|CKA|CKAD|CKS|CISSP|"
    r"CEH|OSCP|Security\+|CompTIA \w+|PMP|PRINCE2|Scrum Master|PSM\s?I*|ITIL|CCNA|CCNP|Google Ads|"
    r"Google Analytics|HubSpot|Meta Blueprint|TOEIC|TOEFL|HACCP|CACES|habilitation électrique|SST)\b",
    re.IGNORECASE,
)


@dataclass
class _Line:
    no: int
    text: str
    section: str  # "claims", "education" or "body"


def _sections(text: str) -> list[_Line]:
    out: list[_Line] = []
    section = "body"
    for no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        heading = line.lstrip("#*•- ").rstrip(":： ").strip()
        known = bool(_HEADING_CLAIMS.match(heading) or _HEADING_EDU.match(heading) or _HEADING_BODY.match(heading))
        # A short all-caps line is a heading only if it names a section: "CISSP" or "HACCP" are content.
        is_heading = raw.lstrip().startswith("#") or (
            len(heading) <= 40 and (line.endswith(":") or (line.isupper() and (known or len(heading.split()) >= 3)))
        )
        if is_heading:
            if _HEADING_CLAIMS.match(heading):
                section = "claims"
            elif _HEADING_EDU.match(heading):
                section = "education"
            else:
                section = "body"
            continue
        out.append(_Line(no, line, section))
    return out


def analyze_text(artifact: Artifact) -> list[Signal]:
    visual = artifact.kind == ArtifactKind.image
    # A portfolio entry describes one piece of finished work: weaker than a photo, stronger than a CV line.
    portfolio = artifact.kind == ArtifactKind.portfolio_note
    lines = _sections(artifact.text)
    raw: list[tuple[str, _Line, float, list[str], bool]] = []  # (skill, line, strength, facets, claim)
    for line in lines:
        if line.section == "education":
            continue  # credentials are handled by extract_credentials
        quant = bool(_QUANT.search(line.text))
        action = bool(_ACTION.search(line.text))
        claim = line.section == "claims" or bool(_CLAIM_LINE.match(line.text))
        for skill, pattern in _VOCAB_RE.items():
            hits = pattern.findall(line.text)
            if not hits:
                continue
            facets: list[str] = []
            if visual:
                # A photo or render of finished work is tangible evidence in itself.
                strength = 0.45 + 0.12 * min(4, len(set(h.lower() for h in hits)))
                claim = False
            elif claim:
                strength = 0.0
            elif portfolio:
                strength = 0.35 + 0.08 * min(4, len(set(h.lower() for h in hits))) + (0.15 if quant else 0) \
                    + (0.1 if action else 0)
            else:
                if not (quant or action):
                    continue  # vocabulary with no anchor is neither proof nor an explicit claim
                strength = 0.25 + (0.35 if quant else 0) + (0.2 if action else 0)
            if quant:
                facets.append("quantified")
            if _OWNERSHIP.search(line.text):
                facets.append("ownership")
            if _CONTROL.search(line.text):
                facets.append("control")
            if len(set(h.lower() for h in hits)) >= 2 or re.search(r"\d{2,}\s?(?:k€|K€|M€|k\$|M\$|000)", line.text):
                facets.append("complex")
            raw.append((skill, line, min(1.0, strength), facets, claim))

    # Merge adjacent lines that support the same skill into one evidence range.
    signals: list[Signal] = []
    merged: dict[str, list[tuple[_Line, float, list[str], bool]]] = {}
    for skill, line, strength, facets, claim in raw:
        merged.setdefault(skill, []).append((line, strength, facets, claim))
    for skill, items in merged.items():
        groups: list[list[tuple[_Line, float, list[str], bool]]] = []
        for item in items:
            if groups and item[0].no - groups[-1][-1][0].no <= 2 and item[3] == groups[-1][-1][3]:
                groups[-1].append(item)
            else:
                groups.append([item])
        for group in groups:
            first, last = group[0][0], group[-1][0]
            claim = group[0][3]
            strength = 0.0 if claim else min(1.0, max(i[1] for i in group) + 0.08 * (len(group) - 1))
            facets = sorted({f for i in group for f in i[2]})
            excerpt = " / ".join(i[0].text for i in group)[:400]
            locator = "image" if visual else (f"line {first.no}" if first.no == last.no
                                              else f"lines {first.no}-{last.no}")
            signals.append(Signal(
                id=f"S-{artifact.id}-{len(signals) + 1:03d}", artifact_id=artifact.id,
                kind=("visual_work" if visual else ("declared" if claim else "documented_outcome")),
                skills=[skill], strength=round(strength, 3), claim_only=claim, facets=facets,
                evidence=EvidenceRef(artifact_id=artifact.id, artifact_label=artifact.label, locator=locator,
                                     excerpt=excerpt, line_start=None if visual else first.no,
                                     line_end=None if visual else last.no),
            ))
    return signals


_CERT_WORD = re.compile(r"certifi|certificate|diplôme|diploma|habilitation|titre professionnel|obtenu|obtained",
                        re.IGNORECASE)


def extract_credentials(artifact: Artifact) -> list[CredentialItem]:
    """Diplomas and certifications. Naming a tool ("ran Google Ads campaigns") is not a credential."""
    items: list[CredentialItem] = []
    seen: set[str] = set()
    for entry in _sections(artifact.text):
        no, line = entry.no, entry.text.strip(" \t•-*")
        if not line or len(line) > 220 or entry.section == "claims":
            continue
        in_education = entry.section == "education"
        cert = _CERT.search(line) if (in_education or _CERT_WORD.search(line)) else None
        degree = _DEGREE.search(line) if (in_education or _DEGREE.match(line)) else None
        if not (cert or degree):
            continue
        label = " ".join(line.split())[:160]
        if label.lower() in seen:
            continue
        seen.add(label.lower())
        items.append(CredentialItem(
            kind="certification" if cert and not degree else "degree", label=label,
            evidence=EvidenceRef(artifact_id=artifact.id, artifact_label=artifact.label, locator=f"line {no}",
                                 excerpt=label, line_start=no, line_end=no),
        ))
    return items[:12]
