"""Synthetic, annotated CV corpus for measuring the shield (no real person in here).

Each generated CV comes with its ground truth: every personal value it contains, by category, and the
evidence lines that must survive masking untouched. Names are drawn from deliberately diverse origins
so that recall can be compared *per origin*: a shield that protects some names better than others
would itself be a source of bias.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

NAMES: dict[str, list[tuple[str, str]]] = {
    "french": [("Camille", "Rousseau"), ("Jean-Baptiste", "Lefèvre"), ("Margaux", "de La Fontaine"),
               ("Théo", "Garnier"), ("Élodie", "Marchand"), ("Gaël", "Le Goff")],
    "maghrebi": [("Yanis", "Benali"), ("Fatima-Zahra", "El Idrissi"), ("Karim", "Haddad"),
                 ("Nour", "Bouaziz"), ("Rachid", "Ait Ouali"), ("Inès", "Belkacem")],
    "west_african": [("Aminata", "Diallo"), ("Moussa", "N'Diaye"), ("Fatou", "Sow"),
                     ("Ibrahima", "Konaté"), ("Awa", "Traoré"), ("Ousmane", "Coulibaly")],
    "east_asian": [("Lan", "Nguyễn Thị"), ("Minh", "Trần"), ("Wei", "Zhang"),
                   ("Haruto", "Sato"), ("Ji-woo", "Park"), ("Mei", "Lin")],
    "eastern_european": [("Agnieszka", "Kowalczyk"), ("Dmytro", "Shevchenko"), ("Ioana", "Popescu"),
                         ("Tomasz", "Wiśniewski"), ("Milena", "Petrović"), ("Andrei", "Ivanov")],
    "iberian_latin": [("João", "Pereira da Silva"), ("María José", "García López"), ("Lucas", "Fernández"),
                      ("Beatriz", "Gonçalves"), ("Diego", "Ramírez"), ("Inês", "Carvalho")],
    "anglo_irish": [("Siobhan", "O'Connor"), ("Liam", "McCarthy"), ("Grace", "Thompson"),
                    ("Oliver", "Bennett"), ("Aoife", "Byrne"), ("Harry", "Whitfield")],
}
OTHER_PEOPLE = [("Sophie", "Bernard"), ("Karim", "Mansouri"), ("Paul", "Durand"), ("Aïcha", "Koné"),
                ("Thomas", "Weber"), ("Laura", "Moretti")]
STREETS = ["rue des Lilas", "avenue Jean Jaurès", "boulevard Voltaire", "chemin des Vignes", "allée des Tilleuls"]
CITIES = [("35000", "Rennes"), ("69003", "Lyon"), ("13001", "Marseille"), ("31000", "Toulouse"),
          ("59800", "Lille"), ("44000", "Nantes")]
SCHOOLS = ["Université de Bordeaux", "École Centrale de Lyon", "Université Paris-Saclay", "IUT de Lannion",
           "INSA Rennes", "Epitech Paris", "Université de Montpellier", "ESSEC Business School"]
NATIONALITIES = ["française", "marocaine", "sénégalaise", "vietnamienne", "polonaise", "portugaise", "irlandaise"]
EVIDENCE = [
    "- Déployé un cluster Kubernetes de 12 nœuds avec Terraform et Helm, disponibilité 99,95 %.",
    "- Réduit de 40 % le temps de build grâce à un pipeline GitHub Actions avec cache.",
    "- Conçu une maquette Figma de 35 écrans, testée auprès de 8 utilisateurs.",
    "- Piloté un budget Google Ads de 120 k€ ; ROAS passé de 2,4 à 3,9.",
    "- Construit un tableau de bord Looker suivi chaque semaine par 15 managers.",
    "- Mis en place le plan HACCP d'une cuisine de 80 couverts, zéro non-conformité en audit.",
    "- Réalisé un escalier en chêne à tenons et mortaises en 5 semaines.",
    "- Automatisé les tests (pytest, 420 tests) avec une couverture de 87 %.",
    "- Migré 30 services vers Docker et Grafana pour la supervision.",
    "- Négocié et signé 14 contrats grands comptes pour 1,2 M€ de chiffre d'affaires.",
]


@dataclass
class Sample:
    text: str
    origin: str
    declared_identity: list[str]
    truth: dict[str, list[str]] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


def _phone(rng: random.Random) -> str:
    digits = [f"{rng.randint(0, 99):02d}" for _ in range(4)]
    return rng.choice([f"0{rng.choice('67')} {' '.join(digits)}", f"+33 {rng.choice('67')} {' '.join(digits)}",
                       f"0{rng.choice('67')}.{'.'.join(digits)}"])


def generate(n: int = 210, seed: int = 7) -> list[Sample]:
    rng = random.Random(seed)
    origins = sorted(NAMES)
    samples = []
    for i in range(n):
        origin = origins[i % len(origins)]
        first, last = rng.choice(NAMES[origin])
        full = f"{first} {last}"
        local = f"{first.split('-')[0].split()[0]}.{last.split()[0]}".lower().replace("'", "")
        email = f"{local}@example.org"
        phone = _phone(rng)
        number, street = rng.randint(1, 120), rng.choice(STREETS)
        postcode, city = rng.choice(CITIES)
        dob = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1970, 2003)}"
        age = f"{rng.randint(21, 55)} ans"
        nationality = rng.choice(NATIONALITIES)
        school = rng.choice(SCHOOLS)
        # The third party never shares a name token with the candidate, so leaks stay attributable.
        other = " ".join(rng.choice([p for p in OTHER_PEOPLE if not set(p) & set(full.split())]))
        evidence = rng.sample(EVIDENCE, 4)
        layout = i % 3
        if layout == 0:
            header = (f"{full}\n{email} — {phone}\n{number} {street}, {postcode} {city}\n"
                      f"Né(e) le {dob} — Nationalité : {nationality}")
        elif layout == 1:
            header = (f"CURRICULUM VITAE\nNom : {full}\nE-mail : {email}\nTéléphone : {phone}\n"
                      f"Adresse : {number} {street}, {postcode} {city}\nÂge : {age}\nNationalité : {nationality}")
        else:
            header = f"Profil — {full}, {age}\nContact : {email} | {phone} | {postcode} {city}"
        text = (f"{header}\n\nEXPÉRIENCE\n" + "\n".join(evidence)
                + f"\n- Travaillé sous la direction de {other}, responsable technique.\n\n"
                f"FORMATION\nMaster Informatique — {school}\n")
        truth = {"PERSON_SELF": [full], "PERSON_OTHER": [other], "EMAIL": [email], "PHONE": [phone],
                 "SCHOOL": [school], "POSTCODE_CITY": [f"{postcode} {city}"]}
        if layout != 2:
            truth["STREET"] = [f"{number} {street}"]
            truth["NATIONALITY"] = [nationality]
        if layout == 0:
            truth["BIRTHDATE"] = [dob]
        if layout != 0:
            truth["AGE"] = [age]
        # Half the candidates declare their identity in the submission form, half do not.
        declared = [full, email] if i % 2 == 0 else []
        samples.append(Sample(text, origin, declared, truth, evidence))
    return samples


def generate_heldout(n: int = 140, seed: int = 11) -> list[Sample]:
    """Layouts written *after* the rules were tuned on ``generate``: an honest generalisation check."""
    rng = random.Random(seed)
    origins = sorted(NAMES)
    samples = []
    for i in range(n):
        origin = origins[i % len(origins)]
        first, last = rng.choice(NAMES[origin])
        full = f"{first} {last}"
        user = f"{first.split('-')[0].split()[0]}.{last.split()[0]}".lower().replace("'", "")
        evidence = rng.sample(EVIDENCE, 3)
        layout = i % 4
        truth: dict[str, list[str]] = {"PERSON_SELF": [full]}
        if layout == 0:  # name only in a closing signature, obfuscated e-mail
            obf = f"{user} [at] example [dot] org"
            text = ("PROFIL\nIngénieur·e cloud avec 8 ans d'expérience.\n\nEXPÉRIENCE\n" + "\n".join(evidence)
                    + f"\n\nCordialement,\n{full}\n{obf}\n")
            truth["EMAIL"] = [obf]
        elif layout == 1:  # name inside a sentence, foreign phone with dashes
            phone = rng.choice(["+44 20 7946 0958", "+1 (415) 555-0134", "06-12-34-56-78", "+49 30 901820"])
            text = (f"Je m'appelle {full} et je cherche un poste en CDI.\nJoignable au {phone}.\n\n"
                    "RÉALISATIONS\n" + "\n".join(evidence) + "\n")
            truth["PHONE"] = [phone]
        elif layout == 2:  # social handle without URL, birth year and age phrased in prose
            handle = f"{user.replace('.', '-')}-{rng.randint(10, 99)}"
            year = rng.randint(1970, 2003)
            age = rng.randint(21, 55)
            text = (f"{full.upper()}\nLinkedIn : {handle}\nNé en {year}, âgé de {age} ans.\n\n"
                    "PARCOURS\n" + "\n".join(evidence) + "\n")
            truth["PROFILE"] = [handle]
            truth["BIRTH_YEAR"] = [f"en {year}"]
            truth["AGE"] = [f"{age} ans"]
        else:  # surname first, comma-separated, as in many administrative forms
            text = (f"{last.upper()}, {first}\nNationality: {rng.choice(NATIONALITIES)}\n\n"
                    "EXPERIENCE\n" + "\n".join(evidence) + "\n")
        samples.append(Sample(text, origin, [], truth, evidence))
    return samples
