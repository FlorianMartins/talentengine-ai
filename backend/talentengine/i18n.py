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
]


def localise(text: str, locale: str) -> str:
    if locale != "fr" or not text:
        return text
    for pattern, replacement in _FR:
        text = pattern.sub(replacement, text)
    return text
