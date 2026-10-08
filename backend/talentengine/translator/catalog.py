"""Universal skill catalogue.

Skills are defined by what can be *observed in someone's work*, never by a diploma. Each entry holds:

* a plain-language label and an HR statement ("can run a budget") in French and English,
* an interview template used to verify authorship of the evidence, written for a recruiter with no
  domain knowledge: the question, what a genuine author is expected to mention, and warning signs.

Placeholders available in templates: {artifact} (pseudonymous label), {locator}, {excerpt}.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Family, Locale


@dataclass(frozen=True)
class InterviewTemplate:
    question: str
    purpose: str
    expected: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SkillDef:
    id: str
    family: Family
    label: dict[str, str]
    statement: dict[str, str]
    interview: dict[str, InterviewTemplate] = field(default_factory=dict)

    def l(self, locale: Locale) -> str:  # noqa: E743 - short accessor used everywhere
        return self.label.get(locale) or self.label["en"]


def _t(q: str, p: str, e: tuple[str, ...], w: tuple[str, ...]) -> InterviewTemplate:
    return InterviewTemplate(q, p, e, w)


_GENERIC_WARNINGS_FR = ("Réponse générale qui pourrait s'appliquer à n'importe quel projet",
                        "Ne retrouve pas l'élément précis dans son propre travail")
_GENERIC_WARNINGS_EN = ("Generic answer that would fit any project",
                        "Cannot locate the specific element in their own work")

SKILLS: list[SkillDef] = [
    # ---------------------------------------------------------------- software
    SkillDef(
        "automated_testing", Family.software,
        {"fr": "Tests automatisés", "en": "Automated testing"},
        {"fr": "sait écrire des tests automatisés qui protègent un logiciel des régressions",
         "en": "can write automated tests that protect software against regressions"},
        {
            "fr": _t("Dans {artifact}, on trouve {locator}. Comment avez-vous décidé de ce qui méritait d'être "
                     "testé, et pouvez-vous raconter un bug précis que ces tests ont empêché ?",
                     "Vérifier que la personne a réellement conçu la stratégie de test.",
                     ("Fait la différence entre test unitaire (une fonction) et test d'intégration (plusieurs "
                      "parties ensemble)", "Cite un bug concret attrapé par un test",
                      "Sait comment lancer les tests (commande ou pipeline automatique)",
                      "Évoque la simulation (« mock ») des services externes"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} contains {locator}. How did you decide what was worth testing, and can you tell "
                     "me about one specific bug those tests caught?",
                     "Check that the candidate actually designed the test strategy.",
                     ("Distinguishes unit tests (one function) from integration tests (parts together)",
                      "Gives a concrete bug caught by a test", "Knows how the tests are run (command or CI)",
                      "Mentions mocking external services"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "ci_cd", Family.software,
        {"fr": "Intégration et déploiement continus", "en": "Continuous integration & delivery"},
        {"fr": "sait automatiser la vérification et la livraison d'un logiciel",
         "en": "can automate how software is checked and shipped"},
        {
            "fr": _t("Le projet {artifact} contient un pipeline automatique ({locator}). Que se passe-t-il, étape "
                     "par étape, quand vous envoyez une modification ? Que faites-vous quand il échoue ?",
                     "Vérifier la compréhension de bout en bout de l'automatisation.",
                     ("Décrit des étapes dans l'ordre (installation, vérifications, tests, construction)",
                      "Explique ce qui bloque une livraison", "Sait lire un échec et le reproduire en local",
                      "Mentionne la gestion des secrets (mots de passe hors du code)"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} ships an automated pipeline ({locator}). Walk me through what happens when you "
                     "push a change. What do you do when it fails?",
                     "Check end-to-end understanding of the automation.",
                     ("Describes ordered stages (install, checks, tests, build)",
                      "Explains what blocks a release", "Can read a failure and reproduce it locally",
                      "Mentions secrets handling (credentials kept out of code)"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "containerization", Family.software,
        {"fr": "Conteneurisation", "en": "Containerisation"},
        {"fr": "sait empaqueter une application pour qu'elle tourne de façon identique partout",
         "en": "can package an application so it runs the same everywhere"},
        {
            "fr": _t("Dans {artifact}, il y a {locator}. Pourquoi cette image est-elle construite ainsi, et "
                     "comment avez-vous réduit sa taille ou ses risques de sécurité ?",
                     "Vérifier la maîtrise réelle des conteneurs.",
                     ("Parle d'image de base et de son choix", "Évoque la construction en plusieurs étapes",
                      "Ne fait pas tourner l'application en administrateur (root)",
                      "Sait relier plusieurs services (compose)"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} has {locator}. Why is the image built this way, and how did you reduce its size "
                     "or its security risks?",
                     "Check real container skills.",
                     ("Talks about the base image choice", "Mentions multi-stage builds",
                      "Avoids running as root", "Can wire several services together (compose)"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "infrastructure_as_code", Family.software,
        {"fr": "Infrastructure as Code", "en": "Infrastructure as code"},
        {"fr": "sait décrire et reconstruire une infrastructure entière à partir de fichiers versionnés",
         "en": "can describe and rebuild a whole infrastructure from versioned files"},
        {
            "fr": _t("Les fichiers {locator} de {artifact} décrivent une infrastructure. Si tout était détruit "
                     "demain, comment la reconstruiriez-vous, et qu'est-ce qui ne serait pas recréé ?",
                     "Vérifier la compréhension de l'état, des dépendances et des limites.",
                     ("Explique la notion d'état (ce que l'outil sait déjà créé)",
                      "Sait prévisualiser un changement avant de l'appliquer (plan)",
                      "Identifie les données qui ne se recréent pas (bases, sauvegardes)",
                      "Sépare les environnements (test / production)"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("The {locator} files in {artifact} describe infrastructure. If everything were destroyed "
                     "tomorrow, how would you rebuild it, and what would not come back?",
                     "Check understanding of state, dependencies and limits.",
                     ("Explains state (what the tool knows it created)", "Previews changes before applying (plan)",
                      "Identifies data that does not get recreated (databases, backups)",
                      "Separates environments (staging / production)"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "llm_engineering", Family.data,
        {"fr": "Ingénierie LLM et IA générative", "en": "LLM & generative AI engineering"},
        {"fr": "sait construire des applications fondées sur des modèles de langage (RAG, agents, évaluations)",
         "en": "can build applications on top of language models (RAG, agents, evaluations)"},
        {
            "fr": _t("Dans {artifact} ({locator}), comment avez-vous mesuré que les réponses du modèle étaient "
                     "bonnes, et qu'avez-vous changé quand elles ne l'étaient pas ?",
                     "Distinguer une démo d'appel d'API d'une vraie démarche d'ingénierie IA.",
                     ("Décrit un jeu d'évaluation ou des critères de qualité", "Parle de récupération de contexte "
                      "(RAG, découpage, embeddings) ou d'outils d'agent", "Évoque coûts, latence ou garde-fous "
                      "(injection de prompt, données sensibles)", "Cite une amélioration mesurée"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("In {artifact} ({locator}), how did you measure that the model's answers were good, and what "
                     "did you change when they were not?",
                     "Tell an API-call demo from real AI engineering.",
                     ("Describes an evaluation set or quality criteria", "Talks about retrieval (RAG, chunking, "
                      "embeddings) or agent tools", "Mentions cost, latency or guardrails (prompt injection, "
                      "sensitive data)", "Gives a measured improvement"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "mobile_development", Family.software,
        {"fr": "Développement mobile", "en": "Mobile development"},
        {"fr": "sait développer et publier des applications mobiles (iOS, Android, multiplateforme)",
         "en": "can build and ship mobile apps (iOS, Android, cross-platform)"},
        {
            "fr": _t("Pour l'application de {artifact} ({locator}), comment gérez-vous le hors-ligne, les "
                     "différentes tailles d'écran et la publication sur les stores ?",
                     "Vérifier l'expérience réelle du mobile.",
                     ("Parle de cycle de vie de l'application ou de gestion d'état", "Évoque les tests sur "
                      "appareils ou simulateurs", "Décrit la publication (signature, revue des stores)"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("For the app in {artifact} ({locator}), how do you handle offline use, screen sizes and store "
                     "releases?",
                     "Check real mobile experience.",
                     ("Talks about app lifecycle or state management", "Mentions testing on devices or "
                      "simulators", "Describes releasing (signing, store review)"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "systems_integration", Family.software,
        {"fr": "Intégration et orchestration de systèmes", "en": "Systems integration & orchestration"},
        {"fr": "sait faire fonctionner ensemble plusieurs outils, services ou projets (dépendances, pipelines, "
               "déploiement coordonné)",
         "en": "can make several tools, services or projects work together (dependencies, pipelines, "
               "coordinated deployment)"},
        {
            "fr": _t("{artifact} s'appuie sur un autre de vos projets ou orchestre plusieurs outils ({locator}). "
                     "Pourquoi les avoir séparés, et que se passe-t-il quand l'un des deux change ?",
                     "Vérifier une vraie pensée système, au-delà d'un projet isolé.",
                     ("Explique le rôle de chaque projet ou outil et leur frontière", "Parle de versions, de "
                      "compatibilité ou de contrat d'interface", "Décrit l'ordre d'exécution ou de déploiement",
                      "Sait ce qui casse quand une brique change"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} builds on another of your projects or orchestrates several tools ({locator}). Why "
                     "keep them separate, and what happens when one of them changes?",
                     "Check real systems thinking, beyond a single project.",
                     ("Explains each project's or tool's role and boundary", "Talks about versions, "
                      "compatibility or interface contracts", "Describes the execution or deployment order",
                      "Knows what breaks when one piece changes"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "cloud_infrastructure", Family.software,
        {"fr": "Infrastructure cloud", "en": "Cloud infrastructure"},
        {"fr": "sait concevoir et exploiter des services sur un cloud public (Azure, AWS, GCP...)",
         "en": "can design and run services on a public cloud (Azure, AWS, GCP...)"},
        {
            "fr": _t("Dans {artifact} ({locator}), quels services cloud avez-vous choisis, et comment maîtrisez-"
                     "vous les coûts et les accès ?",
                     "Vérifier une pratique réelle du cloud, au-delà des noms de services.",
                     ("Justifie le choix d'un service (géré ou non)", "Parle de gestion des identités et des accès",
                      "Évoque le suivi des coûts ou un dépassement évité", "Sait comment l'environnement est recréé"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("In {artifact} ({locator}), which cloud services did you choose, and how do you keep costs and "
                     "access under control?",
                     "Check real cloud practice, beyond service names.",
                     ("Justifies a service choice (managed or not)", "Talks about identity and access management",
                      "Mentions cost tracking or an overrun avoided", "Knows how the environment is recreated"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "security_engineering", Family.software,
        {"fr": "Sécurité applicative et cloud", "en": "Application & cloud security"},
        {"fr": "sait intégrer la sécurité dans la conception et l'automatisation (moindre privilège, Zero-Trust)",
         "en": "can build security into design and automation (least privilege, zero trust)"},
        {
            "fr": _t("Dans {artifact}, {locator} montre des contrôles de sécurité. Quelle menace précise vouliez-"
                     "vous bloquer, et comment savez-vous que le contrôle fonctionne ?",
                     "Distinguer une configuration copiée d'une démarche de sécurité réfléchie.",
                     ("Nomme une menace concrète (fuite de secret, dépendance vulnérable, accès trop large)",
                      "Explique le principe du moindre privilège", "Décrit comment le contrôle a été testé",
                      "Sait ce qui se passe quand une alerte se déclenche"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("In {artifact}, {locator} shows security controls. Which specific threat were you blocking, "
                     "and how do you know the control works?",
                     "Tell a copied configuration from a deliberate security approach.",
                     ("Names a concrete threat (leaked secret, vulnerable dependency, over-broad access)",
                      "Explains least privilege", "Describes how the control was tested",
                      "Knows what happens when an alert fires"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "software_architecture", Family.software,
        {"fr": "Architecture logicielle", "en": "Software architecture"},
        {"fr": "sait découper un logiciel en modules clairs qui évoluent sans tout casser",
         "en": "can split software into clear modules that evolve without breaking everything"},
        {
            "fr": _t("{artifact} est organisé ainsi : {locator}. Si on vous demandait d'ajouter une fonction "
                     "importante, quels dossiers toucheriez-vous et lesquels resteraient intacts ?",
                     "Vérifier que la personne a pensé l'organisation du code.",
                     ("Explique le rôle de chaque grand dossier", "Parle de dépendances entre modules",
                      "Justifie au moins un compromis (simplicité vs flexibilité)",
                      "Évoque des décisions documentées"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} is organised as {locator}. If you had to add a major feature, which folders "
                     "would you touch and which would stay untouched?",
                     "Check that the candidate designed the code organisation.",
                     ("Explains the role of each main folder", "Talks about dependencies between modules",
                      "Justifies at least one trade-off (simplicity vs flexibility)",
                      "Mentions documented decisions"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "code_quality", Family.software,
        {"fr": "Qualité et maintenabilité du code", "en": "Code quality & maintainability"},
        {"fr": "sait outiller un projet pour garder un code lisible et sans erreurs évitables",
         "en": "can tool a project to keep code readable and free of avoidable errors"},
        {
            "fr": _t("{artifact} utilise des outils de contrôle ({locator}). Quelle règle vous a déjà fait "
                     "corriger du code, et laquelle avez-vous désactivée, pourquoi ?",
                     "Vérifier un usage réel, pas une configuration par défaut.",
                     ("Cite une règle précise", "Explique un choix de désactivation argumenté",
                      "Sait lancer les vérifications automatiquement"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} uses quality tooling ({locator}). Which rule once made you change your code, "
                     "and which one did you disable, and why?",
                     "Check real use, not a default configuration.",
                     ("Names a specific rule", "Gives a reasoned choice to disable one",
                      "Runs the checks automatically"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "technical_documentation", Family.software,
        {"fr": "Documentation technique", "en": "Technical documentation"},
        {"fr": "sait documenter un travail pour qu'une autre personne puisse le reprendre",
         "en": "can document work so someone else can take it over"},
        {
            "fr": _t("La documentation de {artifact} ({locator}) : à qui s'adresse-t-elle, et qu'avez-vous "
                     "volontairement laissé de côté ?",
                     "Vérifier la conscience du lecteur cible.",
                     ("Identifie un public précis", "Explique ce qu'un nouveau venu doit lire en premier",
                      "Mentionne des décisions d'architecture consignées"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("The documentation of {artifact} ({locator}): who is it for, and what did you deliberately "
                     "leave out?",
                     "Check awareness of the target reader.",
                     ("Identifies a specific audience", "Explains what a newcomer should read first",
                      "Mentions recorded architecture decisions"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "frontend_development", Family.software,
        {"fr": "Développement d'interfaces web", "en": "Front-end development"},
        {"fr": "sait construire des interfaces web structurées en composants réutilisables",
         "en": "can build web interfaces structured as reusable components"},
        {
            "fr": _t("Dans {artifact} ({locator}), quel composant avez-vous réutilisé le plus, et comment "
                     "gérez-vous l'état partagé entre écrans ?",
                     "Vérifier la conception des composants.",
                     ("Cite un composant précis et ses variantes", "Explique où vit l'état partagé",
                      "Évoque l'accessibilité ou le responsive"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("In {artifact} ({locator}), which component did you reuse the most, and how is state "
                     "shared between screens?",
                     "Check component design.",
                     ("Names a specific component and its variants", "Explains where shared state lives",
                      "Mentions accessibility or responsive design"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "backend_development", Family.software,
        {"fr": "Développement back-end et API", "en": "Back-end & API development"},
        {"fr": "sait construire des services et des API qui exposent des données de façon fiable",
         "en": "can build services and APIs that expose data reliably"},
        {
            "fr": _t("{artifact} expose un service ({locator}). Que se passe-t-il si deux personnes modifient la "
                     "même donnée en même temps, ou si une requête est invalide ?",
                     "Vérifier la gestion des cas limites.",
                     ("Parle de validation des entrées", "Évoque transactions ou verrous",
                      "Décrit les codes d'erreur renvoyés"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} exposes a service ({locator}). What happens if two people edit the same record "
                     "at once, or if a request is invalid?",
                     "Check edge-case handling.",
                     ("Talks about input validation", "Mentions transactions or locking",
                      "Describes the error responses"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "database_design", Family.data,
        {"fr": "Conception de bases de données", "en": "Database design"},
        {"fr": "sait modéliser des données et faire évoluer une base sans perte",
         "en": "can model data and evolve a database without losing anything"},
        {
            "fr": _t("{artifact} contient des migrations ({locator}). Racontez une évolution de schéma délicate "
                     "et comment vous avez protégé les données existantes.",
                     "Vérifier l'expérience réelle des évolutions de schéma.",
                     ("Décrit une migration en plusieurs temps", "Parle de sauvegarde avant changement",
                      "Évoque index ou contraintes"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} contains migrations ({locator}). Tell me about a tricky schema change and how "
                     "you protected existing data.",
                     "Check real experience of schema evolution.",
                     ("Describes a multi-step migration", "Mentions a backup before the change",
                      "Talks about indexes or constraints"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    # ---------------------------------------------------------------- data
    SkillDef(
        "data_engineering", Family.data,
        {"fr": "Ingénierie des données", "en": "Data engineering"},
        {"fr": "sait construire des chaînes de traitement de données automatisées et fiables",
         "en": "can build automated, reliable data pipelines"},
        {
            "fr": _t("Le pipeline de {artifact} ({locator}) : que se passe-t-il si la source envoie des données "
                     "en retard ou en double ?",
                     "Vérifier la robustesse pensée par la personne.",
                     ("Parle d'idempotence (relancer sans doublon)", "Évoque des contrôles de qualité",
                      "Explique l'ordonnancement des tâches"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("The pipeline in {artifact} ({locator}): what happens if the source sends late or duplicate "
                     "data?",
                     "Check robustness designed by the candidate.",
                     ("Talks about idempotency (re-run without duplicates)", "Mentions data quality checks",
                      "Explains task scheduling"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "data_analysis", Family.data,
        {"fr": "Analyse de données", "en": "Data analysis"},
        {"fr": "sait tirer des conclusions chiffrées et vérifiables à partir de données",
         "en": "can draw quantified, verifiable conclusions from data"},
        {
            "fr": _t("Dans {artifact}, {locator} : « {excerpt} ». D'où viennent ces chiffres et qu'est-ce qui "
                     "aurait pu les fausser ?",
                     "Vérifier la compréhension de la méthode derrière les chiffres.",
                     ("Cite la source et la période des données", "Évoque un biais ou une limite",
                      "Distingue corrélation et causalité"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("In {artifact}, {locator}: \"{excerpt}\". Where do these numbers come from and what could "
                     "have distorted them?",
                     "Check understanding of the method behind the numbers.",
                     ("Names the data source and period", "Mentions a bias or limitation",
                      "Distinguishes correlation from causation"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "machine_learning", Family.data,
        {"fr": "Apprentissage automatique", "en": "Machine learning"},
        {"fr": "sait entraîner et évaluer honnêtement un modèle prédictif",
         "en": "can train and honestly evaluate a predictive model"},
        {
            "fr": _t("{artifact} contient un travail de modélisation ({locator}). Comment avez-vous vérifié que "
                     "le modèle ne « trichait » pas sur les données de test ?",
                     "Vérifier la rigueur d'évaluation.",
                     ("Explique la séparation entraînement / test", "Cite une métrique adaptée au problème",
                      "Évoque une fuite de données évitée"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} contains modelling work ({locator}). How did you make sure the model was not "
                     "\"cheating\" on the test data?",
                     "Check evaluation rigour.",
                     ("Explains the train / test split", "Names a metric suited to the problem",
                      "Mentions a data leak they avoided"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    # ---------------------------------------------------------------- design
    SkillDef(
        "ui_design", Family.design,
        {"fr": "Design d'interface (UI)", "en": "Interface design (UI)"},
        {"fr": "sait concevoir des écrans clairs, cohérents et utilisables",
         "en": "can design clear, consistent and usable screens"},
        {
            "fr": _t("Sur {artifact} ({locator}) : quelle contrainte (marque, accessibilité, technique) a le plus "
                     "influencé ce design, et quelle version précédente avez-vous abandonnée ?",
                     "Vérifier que la personne connaît l'historique de conception.",
                     ("Cite une contrainte concrète", "Décrit une itération abandonnée et pourquoi",
                      "Parle de système de composants ou de grille", "Évoque contraste ou lisibilité"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("On {artifact} ({locator}): which constraint (brand, accessibility, technical) shaped this "
                     "design most, and which earlier version did you drop?",
                     "Check that the candidate knows the design history.",
                     ("Names a concrete constraint", "Describes a dropped iteration and why",
                      "Talks about a component system or grid", "Mentions contrast or legibility"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "visual_identity", Family.design,
        {"fr": "Identité visuelle et graphisme", "en": "Visual identity & graphic design"},
        {"fr": "sait créer une identité visuelle cohérente et déclinable",
         "en": "can create a consistent visual identity that scales across media"},
        {
            "fr": _t("Pour {artifact} ({locator}), comment l'identité se décline-t-elle sur un support que vous "
                     "n'avez pas montré, par exemple en noir et blanc ou en très petit ?",
                     "Vérifier la pensée système derrière le visuel.",
                     ("Évoque des règles d'usage (marges, tailles minimales)", "Parle de palette et typographie",
                      "Décrit un brief client et sa réponse"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("For {artifact} ({locator}), how does the identity work on a medium you did not show, such "
                     "as black and white or very small sizes?",
                     "Check the system thinking behind the visuals.",
                     ("Mentions usage rules (clear space, minimum sizes)", "Talks about palette and typography",
                      "Describes a client brief and the answer to it"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "ux_research", Family.design,
        {"fr": "Recherche utilisateur (UX)", "en": "User research (UX)"},
        {"fr": "sait observer de vrais utilisateurs et en tirer des décisions de conception",
         "en": "can observe real users and turn findings into design decisions"},
        {
            "fr": _t("{artifact} ({locator}) présente une démarche utilisateur. Quel résultat de test vous a le "
                     "plus surpris, et qu'avez-vous changé ensuite ?",
                     "Vérifier que la recherche a réellement eu lieu.",
                     ("Décrit le recrutement des participants", "Cite une observation concrète",
                      "Relie l'observation à une décision"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} ({locator}) shows user research. Which test result surprised you most, and what "
                     "did you change afterwards?",
                     "Check that the research really happened.",
                     ("Describes how participants were recruited", "Gives a concrete observation",
                      "Links the observation to a decision"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    # ---------------------------------------------------------------- marketing
    SkillDef(
        "campaign_performance", Family.marketing,
        {"fr": "Pilotage de campagnes à la performance", "en": "Performance campaign management"},
        {"fr": "sait piloter des campagnes publicitaires par les résultats chiffrés (ROAS, CPA, conversions)",
         "en": "can run ad campaigns by measured results (ROAS, CPA, conversions)"},
        {
            "fr": _t("{artifact} indique « {excerpt} » ({locator}). Comment ce résultat a-t-il été mesuré, et "
                     "quelle décision avez-vous prise en le voyant ?",
                     "Vérifier que la personne a piloté, pas seulement constaté.",
                     ("Explique le calcul de l'indicateur (ex. ROAS = revenu / dépense publicitaire)",
                      "Cite l'outil de mesure et la fenêtre d'attribution", "Décrit une décision d'arbitrage de budget",
                      "Mentionne ce qui n'a pas marché"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} says \"{excerpt}\" ({locator}). How was this measured, and what decision did you "
                     "make when you saw it?",
                     "Check that the candidate steered the campaign, not just reported on it.",
                     ("Explains how the metric is computed (e.g. ROAS = revenue / ad spend)",
                      "Names the tracking tool and attribution window", "Describes a budget reallocation decision",
                      "Mentions what did not work"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "funnel_design", Family.marketing,
        {"fr": "Conception de tunnels de conversion", "en": "Conversion funnel design"},
        {"fr": "sait construire un parcours qui transforme des visiteurs en clients",
         "en": "can build a journey that turns visitors into customers"},
        {
            "fr": _t("Le tunnel décrit dans {artifact} ({locator}) : à quelle étape perdiez-vous le plus de monde, "
                     "et qu'avez-vous changé pour corriger cela ?",
                     "Vérifier la maîtrise des étapes et des fuites du tunnel.",
                     ("Nomme les étapes du parcours", "Cite un taux de passage entre deux étapes",
                      "Décrit une modification et son effet mesuré"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("The funnel in {artifact} ({locator}): at which step did you lose the most people, and what "
                     "did you change to fix it?",
                     "Check mastery of funnel stages and drop-off.",
                     ("Names the journey stages", "Gives a pass-through rate between two steps",
                      "Describes a change and its measured effect"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "experimentation", Family.marketing,
        {"fr": "Expérimentation (tests A/B)", "en": "Experimentation (A/B testing)"},
        {"fr": "sait tester des hypothèses de façon rigoureuse avant de généraliser",
         "en": "can test hypotheses rigorously before rolling them out"},
        {
            "fr": _t("{artifact} mentionne un test ({locator}). Combien de temps a-t-il duré et comment avez-vous "
                     "su que le résultat n'était pas dû au hasard ?",
                     "Vérifier la rigueur statistique de base.",
                     ("Parle de taille d'échantillon ou de durée minimale", "Évoque la significativité",
                      "Une seule variable changée à la fois"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} mentions a test ({locator}). How long did it run and how did you know the result "
                     "was not luck?",
                     "Check basic statistical rigour.",
                     ("Mentions sample size or minimum duration", "Talks about significance",
                      "One variable changed at a time"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "content_strategy", Family.marketing,
        {"fr": "Stratégie de contenu et SEO", "en": "Content strategy & SEO"},
        {"fr": "sait planifier des contenus qui attirent une audience mesurable",
         "en": "can plan content that attracts a measurable audience"},
        {
            "fr": _t("Le plan de contenu de {artifact} ({locator}) : comment avez-vous choisi les sujets, et "
                     "lequel a le mieux fonctionné, selon quel indicateur ?",
                     "Vérifier une démarche guidée par les données.",
                     ("Cite une source pour choisir les sujets (recherche de mots-clés, questions clients)",
                      "Donne un indicateur précis", "Évoque la mise à jour de contenus existants"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("The content plan in {artifact} ({locator}): how did you choose topics, and which performed "
                     "best by which metric?",
                     "Check a data-led approach.",
                     ("Names a source for topics (keyword research, customer questions)",
                      "Gives a precise metric", "Mentions refreshing existing content"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    # ---------------------------------------------------------------- sales
    SkillDef(
        "sales_pipeline", Family.sales,
        {"fr": "Gestion du cycle de vente", "en": "Sales pipeline management"},
        {"fr": "sait conduire des opportunités commerciales jusqu'à la signature, chiffres à l'appui",
         "en": "can take sales opportunities to signature, backed by numbers"},
        {
            "fr": _t("{artifact} mentionne « {excerpt} » ({locator}). Racontez une vente précise de ce "
                     "portefeuille : le premier contact, l'objection principale et comment elle a été levée.",
                     "Vérifier l'expérience vécue derrière les chiffres.",
                     ("Décrit les étapes du cycle", "Cite une objection réelle et sa réponse",
                      "Connaît son taux de transformation"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} mentions \"{excerpt}\" ({locator}). Tell me about one specific deal: first "
                     "contact, main objection and how it was overcome.",
                     "Check the lived experience behind the numbers.",
                     ("Describes the cycle stages", "Gives a real objection and the answer",
                      "Knows their own conversion rate"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    # ---------------------------------------------------------------- craft & trades
    SkillDef(
        "woodworking", Family.craft,
        {"fr": "Menuiserie et charpente", "en": "Woodworking & carpentry"},
        {"fr": "sait réaliser des ouvrages en bois avec des assemblages techniques",
         "en": "can build timber work with technical joinery"},
        {
            "fr": _t("Sur {artifact} ({locator}), quel assemblage avez-vous utilisé à cet endroit, pourquoi "
                     "celui-ci, et dans quel ordre avez-vous procédé ?",
                     "Vérifier que la personne a réalisé l'ouvrage elle-même.",
                     ("Nomme l'assemblage (tenon-mortaise, queue d'aronde, mi-bois...)",
                      "Explique le choix (efforts, esthétique, démontage)", "Décrit l'ordre de fabrication",
                      "Parle du choix et du sens du bois"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("On {artifact} ({locator}), which joint did you use here, why this one, and in which order "
                     "did you work?",
                     "Check that the candidate made the piece themselves.",
                     ("Names the joint (mortise and tenon, dovetail, half-lap...)",
                      "Explains the choice (load, look, disassembly)", "Describes the build sequence",
                      "Talks about wood choice and grain direction"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "construction_works", Family.craft,
        {"fr": "Conduite de chantier et rénovation", "en": "Construction & renovation works"},
        {"fr": "sait mener un chantier de rénovation de la préparation à la livraison",
         "en": "can carry a renovation job from preparation to handover"},
        {
            "fr": _t("Pour le chantier montré dans {artifact} ({locator}), quel imprévu avez-vous rencontré et "
                     "comment avez-vous adapté le planning ou le budget ?",
                     "Vérifier l'expérience réelle de chantier.",
                     ("Décrit un imprévu concret", "Parle de coordination avec d'autres corps de métier",
                      "Évoque normes ou sécurité sur le chantier"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("For the job shown in {artifact} ({locator}), which unexpected issue came up and how did you "
                     "adapt the schedule or budget?",
                     "Check real on-site experience.",
                     ("Describes a concrete surprise", "Mentions coordinating other trades",
                      "Talks about standards or site safety"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "metalwork", Family.craft,
        {"fr": "Métallerie et soudure", "en": "Metalwork & welding"},
        {"fr": "sait réaliser des pièces métalliques soudées et contrôlées",
         "en": "can produce welded, inspected metal parts"},
        {
            "fr": _t("Sur {artifact} ({locator}), quel procédé de soudure avez-vous employé et comment avez-vous "
                     "limité les déformations ?",
                     "Vérifier la maîtrise technique.",
                     ("Nomme le procédé (MIG, TIG, arc...)", "Parle de pointage ou de séquence de soudure",
                      "Décrit un contrôle de la soudure"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("On {artifact} ({locator}), which welding process did you use and how did you limit "
                     "distortion?",
                     "Check technical mastery.",
                     ("Names the process (MIG, TIG, stick...)", "Mentions tacking or weld sequence",
                      "Describes how the weld was inspected"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "culinary_technique", Family.culinary,
        {"fr": "Techniques culinaires", "en": "Culinary technique"},
        {"fr": "sait exécuter des préparations culinaires techniques et régulières",
         "en": "can execute technical, consistent culinary preparations"},
        {
            "fr": _t("Pour le plat de {artifact} ({locator}), décrivez la préparation de l'élément le plus "
                     "technique et comment vous garantissez le même résultat à chaque service.",
                     "Vérifier que la personne a réalisé le plat.",
                     ("Décrit des étapes, temps et températures précis", "Parle de mise en place",
                      "Évoque la régularité en service (fiche technique)"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("For the dish in {artifact} ({locator}), describe how you prepare its most technical element "
                     "and how you get the same result every service.",
                     "Check that the candidate made the dish.",
                     ("Describes precise steps, times and temperatures", "Talks about mise en place",
                      "Mentions consistency during service (recipe card)"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "food_safety", Family.culinary,
        {"fr": "Hygiène et sécurité alimentaire", "en": "Food safety & hygiene"},
        {"fr": "sait appliquer et tracer les règles d'hygiène alimentaire",
         "en": "can apply and record food hygiene rules"},
        {
            "fr": _t("{artifact} évoque l'hygiène ({locator}). Quels contrôles notez-vous au quotidien et que "
                     "faites-vous si une température n'est pas bonne ?",
                     "Vérifier la pratique réelle.",
                     ("Cite des contrôles (températures, traçabilité, DLC)", "Décrit une action corrective",
                      "Parle de la marche en avant"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} mentions hygiene ({locator}). Which checks do you log daily and what do you do "
                     "when a temperature is out of range?",
                     "Check real practice.",
                     ("Names checks (temperatures, traceability, use-by dates)", "Describes a corrective action",
                      "Talks about forward flow"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "garment_construction", Family.textile,
        {"fr": "Patronage et confection", "en": "Pattern making & garment construction"},
        {"fr": "sait concevoir un patron et assembler un vêtement aux finitions soignées",
         "en": "can draft a pattern and assemble a garment with clean finishes"},
        {
            "fr": _t("Sur la pièce de {artifact} ({locator}), comment avez-vous construit le patron et quelle "
                     "finition intérieure avez-vous choisie ?",
                     "Vérifier la maîtrise de la confection.",
                     ("Parle de mesures, gradation ou toile d'essai", "Nomme une finition (couture anglaise, "
                      "surjet, biais...)", "Explique le choix du tissu et du droit fil"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("On the piece in {artifact} ({locator}), how did you draft the pattern and which inside "
                     "finish did you choose?",
                     "Check garment-making mastery.",
                     ("Talks about measurements, grading or a toile", "Names a finish (French seam, overlock, "
                      "bias binding...)", "Explains fabric choice and grain line"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    # ---------------------------------------------------------------- management & transversal
    SkillDef(
        "project_management", Family.management,
        {"fr": "Gestion de projet", "en": "Project management"},
        {"fr": "sait planifier un projet en étapes et le mener à terme",
         "en": "can plan a project in stages and deliver it"},
        {
            "fr": _t("Dans {artifact} ({locator}), quel jalon a glissé, pourquoi, et comment avez-vous recalé la "
                     "suite du projet ?",
                     "Vérifier l'expérience vécue de pilotage.",
                     ("Décrit un retard concret et sa cause", "Explique l'arbitrage (périmètre, délai, coût)",
                      "Parle de communication aux parties prenantes"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("In {artifact} ({locator}), which milestone slipped, why, and how did you re-plan the rest?",
                     "Check lived project-steering experience.",
                     ("Describes a concrete delay and its cause", "Explains the trade-off (scope, time, cost)",
                      "Talks about informing stakeholders"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "budget_management", Family.management,
        {"fr": "Gestion de budget", "en": "Budget management"},
        {"fr": "sait construire et tenir un budget", "en": "can build and keep to a budget"},
        {
            "fr": _t("{artifact} mentionne « {excerpt} » ({locator}). Comment ce budget était-il réparti, et "
                     "qu'avez-vous fait quand un poste a dépassé ?",
                     "Vérifier la responsabilité réelle du budget.",
                     ("Donne la répartition des grands postes", "Décrit un dépassement et l'arbitrage",
                      "Parle de suivi régulier (tableau, outil)"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} mentions \"{excerpt}\" ({locator}). How was the budget split, and what did you do "
                     "when one line overran?",
                     "Check real budget ownership.",
                     ("Gives the split of the main lines", "Describes an overrun and the trade-off",
                      "Mentions regular tracking (sheet, tool)"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "team_leadership", Family.management,
        {"fr": "Encadrement d'équipe", "en": "Team leadership"},
        {"fr": "sait coordonner et faire progresser une équipe", "en": "can coordinate and grow a team"},
        {
            "fr": _t("{artifact} indique « {excerpt} » ({locator}). Racontez un désaccord dans cette équipe et "
                     "comment il a été réglé.",
                     "Vérifier l'expérience réelle de l'encadrement.",
                     ("Décrit une situation précise", "Explique la façon d'écouter chaque partie",
                      "Parle de la progression d'un membre de l'équipe"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} says \"{excerpt}\" ({locator}). Tell me about a disagreement in that team and how "
                     "it was resolved.",
                     "Check real leadership experience.",
                     ("Describes a specific situation", "Explains how each side was heard",
                      "Talks about how a team member grew"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "quality_control", Family.transversal,
        {"fr": "Contrôle qualité", "en": "Quality control"},
        {"fr": "sait mettre en place des contrôles qui garantissent un résultat fiable",
         "en": "can put checks in place that guarantee a reliable result"},
        {
            "fr": _t("{artifact} montre des contrôles ({locator}). Quel défaut ce contrôle a-t-il déjà détecté, "
                     "et qu'avez-vous changé dans votre façon de travailler ensuite ?",
                     "Vérifier un contrôle vécu, pas théorique.",
                     ("Cite un défaut réel détecté", "Décrit l'action corrective", "Parle de prévention"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("{artifact} shows checks ({locator}). Which defect has this check caught, and what did you "
                     "change in how you work afterwards?",
                     "Check lived, not theoretical, quality control.",
                     ("Names a real defect caught", "Describes the corrective action", "Talks about prevention"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
    SkillDef(
        "structured_communication", Family.transversal,
        {"fr": "Communication écrite structurée", "en": "Structured written communication"},
        {"fr": "sait produire des documents structurés, clairs et chiffrés",
         "en": "can produce structured, clear documents backed by figures"},
        {
            "fr": _t("Le document {artifact} ({locator}) : à qui était-il destiné et quelle décision devait-il "
                     "permettre de prendre ?",
                     "Vérifier la conscience du destinataire et de l'objectif.",
                     ("Nomme le destinataire", "Explique la décision attendue", "Justifie la structure choisie"),
                     _GENERIC_WARNINGS_FR),
            "en": _t("The document {artifact} ({locator}): who was it for, and which decision was it meant to "
                     "support?",
                     "Check awareness of the audience and goal.",
                     ("Names the audience", "Explains the expected decision", "Justifies the structure"),
                     _GENERIC_WARNINGS_EN),
        },
    ),
]

CATALOG: dict[str, SkillDef] = {s.id: s for s in SKILLS}


def skill(skill_id: str) -> SkillDef:
    try:
        return CATALOG[skill_id]
    except KeyError as exc:
        raise KeyError(f"unknown skill id: {skill_id}") from exc
