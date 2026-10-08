"""Localisation of machine-generated fragments (evidence locators, escalation reasons).

Analysers and the budget funnel produce short English fragments; reports are written in the job's
language, so French reports translate them here instead of mixing languages.
"""

from __future__ import annotations

import re

_FR: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^line (\d+)$"), r"ligne \1"),
    (re.compile(r"^lines (\d+)-(\d+)$"), r"lignes \1-\2"),
    (re.compile(r"^(\d+) file\(s\) in (.+)$"), r"\1 fichier(s) dans \2"),
    (re.compile(r"^(\d+) source files across (\d+) folders$"), r"\1 fichiers source répartis dans \2 dossiers"),
    (re.compile(r"\(root\)"), "(racine)"),
    (re.compile(r"^no escalation provider configured \(local-only mode\)$"),
     "aucun fournisseur d'approfondissement configuré (mode 100 % local)"),
    (re.compile(r"^escalation disabled for this job$"), "approfondissement par IA désactivé pour ce poste"),
    (re.compile(r"^outside the top (\S+)% by factual density$"), r"hors du top \1 % par densité factuelle"),
    (re.compile(r"^factual density (\S+) below threshold (\S+)$"), r"densité factuelle \1 sous le seuil \2"),
    (re.compile(r"^rank (\d+)/(\d+) by factual density \((\S+)\)$"), r"rang \1/\2 par densité factuelle (\3)"),
    (re.compile(r"^escalation refused by budget guard: "), "approfondissement refusé par le garde-fou budgétaire : "),
    (re.compile(r"job budget exhausted \(needs (\S+), (\S+) left\)"),
     r"budget du poste épuisé (besoin de \1, reste \2)"),
    (re.compile(r"context of (\d+) tokens exceeds the per-request budget"),
     r"contexte de \1 tokens au-delà du budget par requête"),
    (re.compile(r"^escalation failed, Level-1 assessment kept: "),
     "échec de l'approfondissement, évaluation de niveau 1 conservée : "),
    (re.compile(r"^(.+), line (\d+) → (\S+)$"), r"\1, ligne \2 → \3"),
    (re.compile(r"^used by (.+)$"), r"utilisé par \1"),
    (re.compile(r"^(\d+) workflow\(s\): (\d+) tools, (\d+) job dependencies$"),
     r"\1 workflow(s) : \2 outils, \3 dépendances entre jobs"),
    # Public sandbox messages
    (re.compile(r"^could not read this link: "), "impossible de lire ce lien : "),
    (re.compile(r"the page answered HTTP (\d+)"), r"la page a répondu HTTP \1"),
    (re.compile(r"only http\(s\) links are accepted"), "seuls les liens http(s) sont acceptés"),
    (re.compile(r"links with credentials are not accepted"), "les liens contenant des identifiants sont refusés"),
    (re.compile(r"only standard web ports are accepted"), "seuls les ports web standards sont acceptés"),
    (re.compile(r"unknown host (\S+)"), r"site inconnu : \1"),
    (re.compile(r"this address is not publicly reachable"), "cette adresse n'est pas accessible publiquement"),
    (re.compile(r"unsupported content type (.+)"), r"type de contenu non pris en charge (\1)"),
    (re.compile(r"page too large"), "page trop volumineuse"),
    (re.compile(r"too many redirects"), "trop de redirections"),
    (re.compile(r"LinkedIn did not return this offer publicly: paste its text instead"),
     "LinkedIn ne publie pas cette offre en accès libre : collez plutôt son texte"),
    (re.compile(r"the offer is too short to analyse: paste the full description"),
     "l'offre est trop courte pour être analysée : collez la description complète"),
    (re.compile(r"no skill from the catalogue was found in this offer: try pasting the full text, or pick a "
                r"reference role"),
     "aucune compétence du catalogue n'a été trouvée dans cette offre : collez le texte complet ou choisissez "
     "un poste type"),
    (re.compile(r"limit reached for this hour, try again in about (\d+) min"),
     r"limite atteinte pour cette heure, réessayez dans environ \1 min"),
    (re.compile(r"the sandbox is busy, please retry in a minute"),
     "l'outil est très sollicité, réessayez dans une minute"),
    (re.compile(r"^consent is required$"), "le consentement est nécessaire"),
    (re.compile(r"choose a reference role or analyse an offer first"),
     "choisissez un poste type ou analysez d'abord une offre"),
    (re.compile(r"GitHub rate limit reached: paste repository links instead of a profile"),
     "limite GitHub atteinte : collez des liens de dépôts plutôt qu'un profil"),
    (re.compile(r"GitHub profile not found \((\d+)\)"), r"profil GitHub introuvable (\1)"),
    (re.compile(r"not a GitHub link: (.+)"), r"ce n'est pas un lien GitHub : \1"),
    (re.compile(r"(\S+): repository not found or private"), r"\1 : dépôt introuvable ou privé"),
    (re.compile(r"(\S+): repository too slow to read"), r"\1 : dépôt trop long à lire"),
    (re.compile(r"file larger than (\d+) MB"), r"fichier de plus de \1 Mo"),
    (re.compile(r"unreadable PDF"), "PDF illisible"),
    (re.compile(r"unreadable Word document"), "document Word illisible"),
    (re.compile(r"unsupported format, please send PDF, DOCX, Markdown or plain text"),
     "format non pris en charge : envoyez un PDF, un DOCX, du Markdown ou du texte"),
    (re.compile(r"a submission needs at least one document, repository, portfolio item or image"),
     "ajoutez au moins un document, un dépôt GitHub ou un lien de portfolio"),
    (re.compile(r"^invalid job profile: "), "profil de poste invalide : "),
]


def localise(text: str, locale: str) -> str:
    if locale != "fr" or not text:
        return text
    for pattern, replacement in _FR:
        text = pattern.sub(replacement, text)
    return text
