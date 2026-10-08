"""Pre-filled DPIA draft (GDPR Art. 35) for one job profile.

Everything the software knows is filled in from the live configuration: data categories, retention,
masking measures, credential cap, escalation provider, logging. Everything only the organisation can
decide (controller, legal basis, transfers, residual risk acceptance) is left as an explicit "TO
COMPLETE" item. The draft follows the structure of the French CNIL PIA method and adds the AI Act
deployer duties (high-risk system, Annex III 4(a)).
"""

from __future__ import annotations

from typing import Any

from .config import ENGINE_VERSION, Settings
from .models import IMPORTANCE_MULTIPLIER, JobProfile, utcnow
from .translator.catalog import CATALOG

TODO = {"fr": "**À COMPLÉTER**", "en": "**TO COMPLETE**"}


def _yes(value: bool, locale: str) -> str:
    return ("oui" if value else "non") if locale == "fr" else ("yes" if value else "no")


def dpia_markdown(job: JobProfile, settings: Settings, runtime: dict[str, Any], locale: str = "fr") -> str:
    fr = locale == "fr"
    t = TODO[locale]
    p = job.privacy
    provider = runtime.get("llm_provider", "none")
    cloud = provider not in ("none", "ollama") and job.funnel.allow_cloud_llm
    criteria = "\n".join(
        f"| {CATALOG[c.skill_id].l(job.locale)} | {c.importance.value} (×{IMPORTANCE_MULTIPLIER[c.importance]:g}) "
        f"| {c.weight:g} | {c.min_level:g} |" for c in job.criteria)
    measures_fr = f"""
| Mesure | État |
|---|---|
| Pseudonymisation du texte avant analyse (identité, contacts, âge, nationalité, situation familiale…) | active |
| Détection statistique des noms de tiers (NER) | {_yes(settings.ner == "spacy", locale)} |
| Masquage des noms d'établissements scolaires (indicateur de prestige) | {_yes(p.mask_school_names, locale)} |
| Neutralisation des tournures genrées | {_yes(p.neutralize_gendered_terms, locale)} |
| Floutage des visages et logos par un modèle local | détecteur : `{runtime.get("vision_detector", "none")}` |
| Images sans détecteur mises en quarantaine (fail-closed) | {_yes(p.quarantine_images_without_detector, locale)} |
| Identité chiffrée (Fernet), révélée seulement après une décision humaine, accès journalisé | active |
| Poids maximal des diplômes dans le score | {job.credentials.weight:.0%} (plafond logiciel 25 %) |
| Aucun rejet automatique ; décision humaine nominative et motivée | active |
| Explication de chaque score par les extraits utilisés ; lien d'explication pour le candidat | active |
| Journal d'audit en ajout seul, chaîné et scellé (HMAC) | active |
| Effacement sur demande avec destruction de clé (crypto-shredding) ; export des données | active |
| Purge automatique à l'échéance de la durée de conservation | {"toutes les " + str(settings.retention_sweep_hours) + " h" if settings.retention_sweep_hours else "désactivée"} |
| Comptes nominatifs et rôles (recruteur, DPO, admin) | voir § 7 |
| Analyse par un modèle d'IA hors de l'infrastructure | {"oui : " + provider + " / " + runtime.get("llm_model", "") if cloud else "non (analyse 100 % locale)"} |
"""
    measures_en = f"""
| Measure | Status |
|---|---|
| Text pseudonymisation before analysis (identity, contact details, age, nationality, family status…) | active |
| Statistical detection of third-party names (NER) | {_yes(settings.ner == "spacy", locale)} |
| Masking of school names (prestige proxy) | {_yes(p.mask_school_names, locale)} |
| Neutralisation of gendered wording | {_yes(p.neutralize_gendered_terms, locale)} |
| Face and logo blurring by a local model | detector: `{runtime.get("vision_detector", "none")}` |
| Images quarantined when no detector runs (fail-closed) | {_yes(p.quarantine_images_without_detector, locale)} |
| Encrypted identity (Fernet), revealed only after a human decision, access logged | active |
| Maximum weight of credentials in the score | {job.credentials.weight:.0%} (software cap 25%) |
| No automated rejection; named, reasoned human decision | active |
| Each score explained by the excerpts used; explanation link for the candidate | active |
| Append-only, hash-chained, HMAC-sealed audit ledger | active |
| Erasure on request with crypto-shredding; data export | active |
| Automatic purge when the retention period ends | {"every " + str(settings.retention_sweep_hours) + " h" if settings.retention_sweep_hours else "disabled"} |
| Named accounts and roles (recruiter, DPO, admin) | see § 7 |
| Analysis by an AI model outside the infrastructure | {"yes: " + provider + " / " + runtime.get("llm_model", "") if cloud else "no (100% local analysis)"} |
"""
    if fr:
        return f"""# Analyse d'impact relative à la protection des données (AIPD) — brouillon

> Brouillon généré le {utcnow():%d/%m/%Y} par TalentEngine-AI {ENGINE_VERSION} à partir de la configuration
> du poste **{job.title}** (version {job.version}). Les mesures techniques sont renseignées automatiquement ;
> les éléments marqués {t} relèvent du responsable de traitement et de son ou sa DPO. Ce document n'est pas
> un avis juridique.

## 1. Description du traitement

| Élément | Valeur |
|---|---|
| Responsable de traitement | {t} |
| Délégué·e à la protection des données | {t} |
| Finalité | Aide à l'évaluation des candidatures au poste « {job.title} » à partir de preuves de compétences ; classement indicatif, décision humaine |
| Personnes concernées | Candidates et candidats au poste ; tiers éventuellement cités dans les pièces (masqués) |
| Données traitées | CV, documents professionnels, arborescence de dépôts de code publics (noms de fichiers et au plus 6 fichiers clés), descriptions et photos de réalisations, liens de portfolio |
| Données d'identification | Nom et e-mail déclarés, chiffrés, utilisés pour le masquage et révélés après décision |
| Catégories particulières (art. 9) | Non recherchées ; masquées si présentes (nationalité, situation familiale, religion…) |
| Durée de conservation | Celle consentie par la personne (180 jours par défaut, 730 au maximum), puis effacement automatique |
| Destinataires | Comptes nominatifs habilités ; {t} (liste des équipes) |
| Sous-traitants | Hébergeur {t} ; fournisseur d'IA : {provider if cloud else "aucun"} |
| Transferts hors UE | {t if cloud else "Aucun du fait du logiciel (analyse locale)"} |

### Configuration du poste évaluée

| Compétence | Importance | Poids | Niveau attendu (0-4) |
|---|---|---|---|
{criteria}

Axes : autonomie {job.axis_weights.autonomy:g}, complexité {job.axis_weights.complexity:g}, fiabilité {job.axis_weights.reliability:g}.
Diplômes : mode « {job.credentials.mode} », poids {job.credentials.weight:.0%}, acceptés : {", ".join(job.credentials.accepted) or "—"}.

## 2. Base légale et proportionnalité

- **Base légale** : {t}. Le logiciel recueille un consentement explicite, mais en recrutement le déséquilibre
  entre les parties rend souvent préférable l'exécution de mesures précontractuelles (art. 6.1.b) ou l'intérêt
  légitime (art. 6.1.f) : à arbitrer avec la ou le DPO.
- **Minimisation** : seuls les éléments utiles à l'évaluation des compétences sont analysés ; les dépôts de code
  ne sont pas lus intégralement ; les données d'identité sont retirées avant toute analyse.
- **Exactitude** : chaque compétence est rattachée à un extrait vérifiable ; les compétences seulement déclarées
  ne rapportent pas de points et deviennent des questions d'entretien.
- **Information des personnes** : {t} (mentions sur l'offre et le formulaire, lien d'explication du score).
- **Droits** : accès et portabilité (export), effacement, explication du score, contestation auprès de {t}.

## 3. Mesures techniques et organisationnelles (relevées automatiquement)
{measures_fr}
Mesures mesurées et publiées : rappel du masquage par origine de nom, test contrefactuel d'identité, invariants
du plafond des diplômes, résistance à la triche (voir `docs/MEASUREMENTS.md`).

## 4. Risques pour les personnes

| Risque | Sources | Mesures existantes | Gravité / vraisemblance résiduelles |
|---|---|---|---|
| Accès illégitime aux données | compte compromis, fuite de base | identité chiffrée, comptes nominatifs, clés hors base, en-têtes de sécurité | {t} |
| Modification non désirée | altération d'un score ou d'une décision | journal chaîné et scellé, vérification d'intégrité | {t} |
| Disparition des données | panne, suppression | {t} (sauvegardes) | {t} |
| Discrimination | biais des règles ou des modèles | masquage avant analyse, test contrefactuel, plafond des diplômes, revue humaine | {t} |
| Biais d'automatisation | confiance excessive dans le score | aucun rejet automatique, niveaux de preuve décrivant les pièces et non la personne, décision motivée | {t} |
| Opacité | score incompris ou incontestable | extraits cités, lien d'explication, journal consultable | {t} |
| Manipulation | instructions cachées, CV gonflé | détection d'injection, influence de l'IA bornée, règles anti-triche | {t} |

## 5. AI Act — système à haut risque (annexe III, point 4 a)

Obligations du déployeur (art. 26) à vérifier :

- [ ] Utilisation conforme à la notice et au présent paramétrage
- [ ] Contrôle humain confié à des personnes formées et disposant de l'autorité nécessaire (art. 14)
- [ ] Conservation des journaux au moins six mois (le journal d'audit le permet) — durée retenue : {t}
- [ ] Information des représentants du personnel et des personnes concernées avant la mise en service
- [ ] Analyse d'impact sur les droits fondamentaux (art. 27) si le déployeur y est soumis : {t}
- [ ] Surveillance du fonctionnement et signalement des incidents graves

## 6. Plan d'action et validation

| Action | Responsable | Échéance |
|---|---|---|
| Compléter les éléments marqués {t} | {t} | {t} |
| Relire les définitions de compétences avec des praticiens du métier | {t} | {t} |
| Former les recruteurs à la lecture du score | {t} | {t} |

Avis de la ou du DPO : {t}  ·  Décision du responsable de traitement : {t}

## 7. Annexe — accès

Les décisions, révélations d'identité, exports et effacements sont signés du nom du compte authentifié et
consignés dans le journal d'audit. Liste des comptes et rôles : {t} (à extraire de l'administration).
"""
    return f"""# Data Protection Impact Assessment (DPIA) — draft

> Draft generated on {utcnow():%Y-%m-%d} by TalentEngine-AI {ENGINE_VERSION} from the configuration of the job
> **{job.title}** (version {job.version}). Technical measures are filled in automatically; items marked {t}
> are for the controller and their DPO. This document is not legal advice.

## 1. Description of the processing

| Item | Value |
|---|---|
| Controller | {t} |
| Data protection officer | {t} |
| Purpose | Support the assessment of applications to "{job.title}" from evidence of skills; indicative ranking, human decision |
| Data subjects | Applicants; third parties possibly named in their files (masked) |
| Data processed | CVs, professional documents, file trees of public code repositories (file names and at most 6 key files), descriptions and photos of work, portfolio links |
| Identification data | Declared name and e-mail, encrypted, used for masking and revealed after a decision |
| Special categories (Art. 9) | Not sought; masked when present (nationality, family status, religion…) |
| Retention | As consented by the person (180 days by default, 730 at most), then automatic erasure |
| Recipients | Named authorised accounts; {t} (teams) |
| Processors | Hosting {t}; AI provider: {provider if cloud else "none"} |
| Transfers outside the EU | {t if cloud else "None caused by the software (local analysis)"} |

### Job configuration assessed

| Skill | Importance | Weight | Required level (0-4) |
|---|---|---|---|
{criteria}

Axes: autonomy {job.axis_weights.autonomy:g}, complexity {job.axis_weights.complexity:g}, reliability {job.axis_weights.reliability:g}.
Credentials: mode "{job.credentials.mode}", weight {job.credentials.weight:.0%}, accepted: {", ".join(job.credentials.accepted) or "—"}.

## 2. Legal basis and proportionality

- **Legal basis**: {t}. The software records explicit consent, but in recruitment the imbalance between the
  parties often makes pre-contractual measures (Art. 6(1)(b)) or legitimate interest (Art. 6(1)(f)) more
  appropriate: to be decided with the DPO.
- **Minimisation**: only what is useful to assess skills is analysed; code repositories are not read in full;
  identity data is removed before any analysis.
- **Accuracy**: every skill is tied to a verifiable excerpt; skills that are only declared earn no points and
  become interview questions.
- **Information of data subjects**: {t} (notices on the offer and the form, score explanation link).
- **Rights**: access and portability (export), erasure, score explanation, objection to {t}.

## 3. Technical and organisational measures (read automatically)
{measures_en}
Measured and published: masking recall per name origin, counterfactual identity test, credential-cap
invariants, gaming resistance (see `docs/MEASUREMENTS.md`).

## 4. Risks to people

| Risk | Sources | Existing measures | Residual severity / likelihood |
|---|---|---|---|
| Illegitimate access | compromised account, database leak | encrypted identity, named accounts, keys outside the database, security headers | {t} |
| Unwanted modification | altered score or decision | chained and sealed ledger, integrity verification | {t} |
| Loss of data | failure, deletion | {t} (backups) | {t} |
| Discrimination | bias in rules or models | masking before analysis, counterfactual test, credential cap, human review | {t} |
| Automation bias | over-reliance on the score | no automated rejection, evidence bands describing files not people, reasoned decision | {t} |
| Opacity | score not understood or not contestable | cited excerpts, explanation link, consultable ledger | {t} |
| Manipulation | hidden instructions, inflated CV | injection screen, bounded AI influence, anti-gaming rules | {t} |

## 5. AI Act — high-risk system (Annex III, point 4(a))

Deployer obligations (Art. 26) to check:

- [ ] Use in line with the instructions and this configuration
- [ ] Human oversight by trained people with the necessary authority (Art. 14)
- [ ] Logs kept for at least six months (the audit ledger allows it) — period chosen: {t}
- [ ] Workers' representatives and data subjects informed before going live
- [ ] Fundamental rights impact assessment (Art. 27) if the deployer is subject to it: {t}
- [ ] Monitoring of operation and reporting of serious incidents

## 6. Action plan and sign-off

| Action | Owner | Due |
|---|---|---|
| Complete the items marked {t} | {t} | {t} |
| Review skill definitions with practitioners of the trade | {t} | {t} |
| Train recruiters to read the score | {t} | {t} |

DPO opinion: {t}  ·  Controller decision: {t}

## 7. Annex — access

Decisions, identity reveals, exports and erasures are signed with the authenticated account name and
recorded in the audit ledger. Accounts and roles: {t} (export from the administration).
"""
