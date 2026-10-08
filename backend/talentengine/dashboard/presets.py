"""Reference job profiles. Recruiters and sandbox visitors start from one and tune everything.

Each preset carries search keywords in French and English (common titles, synonyms, acronyms), so that
"IA engineer", "ingénieur IA" or "LLM" all find the AI engineer profile. Search ignores case and accents.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from ..models import AxisWeights, CredentialsPolicy, Criterion, Family, Importance, JobProfile

E, IMP, B = Importance.essential, Importance.important, Importance.bonus


@dataclass(frozen=True)
class Preset:
    id: str
    family: Family
    title: tuple[str, str]  # (fr, en)
    summary: tuple[str, str]
    keywords: str  # space-separated, FR and EN
    criteria: tuple[tuple[str, Importance, float], ...]
    axis: tuple[float, float, float] = (1, 1, 1)  # autonomy, complexity, reliability
    credentials: tuple[str, ...] = ()


SW, DATA, DES, MKT, SALES = Family.software, Family.data, Family.design, Family.marketing, Family.sales
CRAFT, FOOD, TEX, MGMT, TRANS = Family.craft, Family.culinary, Family.textile, Family.management, Family.transversal

_PRESETS: list[Preset] = [
    # ---------------------------------------------------------------- software & infrastructure
    Preset("devsecops", SW, ("Ingénieur·e DevSecOps", "DevSecOps Engineer"),
           ("Automatiser, sécuriser et fiabiliser la livraison logicielle.",
            "Automate, secure and harden software delivery."),
           "devsecops devops security pipeline ci cd sécurité",
           (("ci_cd", E, 2.5), ("security_engineering", E, 2.5), ("infrastructure_as_code", IMP, 2),
            ("containerization", IMP, 2), ("automated_testing", IMP, 2), ("technical_documentation", B, 1.5)),
           (1, 1, 1.5), ("AWS Certified", "CKA", "CKS", "Security+")),
    Preset("devops", SW, ("Ingénieur·e DevOps", "DevOps Engineer"),
           ("Automatiser l'intégration, le déploiement et l'exploitation.",
            "Automate integration, deployment and operations."),
           "devops ops déploiement deployment automatisation automation intégration continue",
           (("ci_cd", E, 2.5), ("containerization", E, 2), ("infrastructure_as_code", IMP, 2),
            ("cloud_infrastructure", IMP, 2), ("systems_integration", IMP, 2), ("automated_testing", B, 1.5)),
           (1, 1, 1.5), ("AWS Certified", "CKA")),
    Preset("sre", SW, ("Ingénieur·e SRE / fiabilité", "Site Reliability Engineer (SRE)"),
           ("Garder des services disponibles, observables et résilients.",
            "Keep services available, observable and resilient."),
           "sre site reliability fiabilité astreinte on-call observabilité monitoring production exploitation",
           (("cloud_infrastructure", E, 2.5), ("infrastructure_as_code", E, 2), ("containerization", IMP, 2),
            ("ci_cd", IMP, 2), ("quality_control", IMP, 2), ("systems_integration", B, 1.5)),
           (1, 1, 2), ("CKA", "AWS Certified")),
    Preset("cloud_architect", SW, ("Architecte cloud", "Cloud Architect"),
           ("Concevoir des plateformes cloud sûres et maîtrisées en coût.", "Design secure, cost-aware cloud platforms."),
           "cloud architecte architect azure aws gcp plateforme platform landing zone",
           (("cloud_infrastructure", E, 3), ("software_architecture", E, 2.5), ("infrastructure_as_code", IMP, 2.5),
            ("security_engineering", IMP, 2), ("technical_documentation", B, 2)),
           (1.25, 1.5, 1), ("AWS Certified", "Azure", "Google Cloud")),
    Preset("platform_engineer", SW, ("Ingénieur·e plateforme", "Platform Engineer"),
           ("Offrir aux équipes une plateforme interne fiable et outillée.",
            "Give teams a reliable, well-tooled internal platform."),
           "platform plateforme internal developer platform kubernetes outillage tooling",
           (("containerization", E, 2.5), ("infrastructure_as_code", E, 2.5), ("systems_integration", IMP, 2),
            ("ci_cd", IMP, 2), ("technical_documentation", IMP, 1.5), ("cloud_infrastructure", B, 2)),
           (1.25, 1.25, 1.25), ("CKA",)),
    Preset("backend", SW, ("Développeur·euse back-end", "Back-end Developer"),
           ("Construire des API et services fiables.", "Build reliable APIs and services."),
           "backend back-end back end api serveur server python java node go php développeur developer",
           (("backend_development", E, 2.5), ("database_design", IMP, 2), ("automated_testing", IMP, 2),
            ("software_architecture", IMP, 2), ("ci_cd", B, 1.5), ("security_engineering", B, 1.5))),
    Preset("frontend", SW, ("Développeur·euse front-end", "Front-end Developer"),
           ("Construire des interfaces web rapides et accessibles.", "Build fast, accessible web interfaces."),
           "frontend front-end front end react vue angular javascript typescript intégrateur web développeur developer",
           (("frontend_development", E, 2.5), ("ui_design", IMP, 1.5), ("automated_testing", IMP, 2),
            ("code_quality", IMP, 2), ("software_architecture", B, 1.5))),
    Preset("fullstack", SW, ("Développeur·euse full-stack", "Full-stack Developer"),
           ("Construire des produits web de bout en bout.", "Build web products end to end."),
           "fullstack full-stack full stack web développeur developer produit",
           (("frontend_development", E, 2), ("backend_development", E, 2), ("automated_testing", IMP, 2),
            ("software_architecture", IMP, 2), ("database_design", B, 1.5), ("ci_cd", B, 1.5))),
    Preset("mobile", SW, ("Développeur·euse mobile", "Mobile Developer"),
           ("Créer des applications iOS / Android soignées.", "Build polished iOS / Android apps."),
           "mobile ios android flutter react native swift kotlin application app",
           (("mobile_development", E, 2.5), ("ui_design", IMP, 1.5), ("automated_testing", IMP, 2),
            ("backend_development", B, 1.5), ("ci_cd", B, 1.5))),
    Preset("software_architect", SW, ("Architecte logiciel / tech lead", "Software Architect / Tech Lead"),
           ("Structurer des systèmes durables et faire grandir les équipes.", "Shape durable systems and grow teams."),
           "architecte architect logiciel software tech lead lead dev principal staff",
           (("software_architecture", E, 3), ("systems_integration", E, 2.5), ("technical_documentation", IMP, 2),
            ("automated_testing", IMP, 2), ("team_leadership", B, 2)), (1.5, 1.5, 1)),
    Preset("qa_engineer", SW, ("Ingénieur·e qualité / QA", "QA / Test Engineer"),
           ("Garantir la qualité par des tests automatisés pertinents.",
            "Guarantee quality through meaningful automated tests."),
           "qa test testeur tester qualité quality assurance automatisation des tests sdet",
           (("automated_testing", E, 3), ("quality_control", E, 2.5), ("ci_cd", IMP, 2), ("code_quality", IMP, 2),
            ("structured_communication", B, 1.5)), (1, 1, 2), ("ISTQB",)),
    Preset("systems_engineer", SW, ("Ingénieur·e systèmes / bas niveau", "Systems / Low-level Engineer"),
           ("Écrire du logiciel proche du matériel, performant et sûr.",
            "Write performant, safe software close to the hardware."),
           "système systems embarqué embedded bas niveau low level kernel noyau os c c++ rust firmware",
           (("software_architecture", E, 2.5), ("automated_testing", IMP, 2), ("code_quality", IMP, 2),
            ("technical_documentation", B, 1.5), ("ci_cd", B, 1.5)), (1.25, 1.5, 1.25)),
    # ---------------------------------------------------------------- AI & data
    Preset("ai_engineer", DATA, ("Ingénieur·e IA / LLM", "AI Engineer (LLM)"),
           ("Construire des produits fondés sur des modèles de langage, mesurés et sûrs.",
            "Build measured, safe products on top of language models."),
           "ia ai engineer ingénieur intelligence artificielle llm genai générative generative rag agents prompt "
           "chatbot openai anthropic claude gpt mistral",
           (("llm_engineering", E, 2.5), ("backend_development", IMP, 2), ("automated_testing", IMP, 2),
            ("security_engineering", IMP, 1.5), ("machine_learning", B, 1.5), ("cloud_infrastructure", B, 1.5)),
           (1.25, 1.25, 1.5)),
    Preset("ml_engineer", DATA, ("Ingénieur·e machine learning", "Machine Learning Engineer"),
           ("Entraîner, évaluer et mettre en production des modèles.", "Train, evaluate and ship models to production."),
           "machine learning ml ingénieur engineer apprentissage automatique deep learning modèles models pytorch "
           "tensorflow ia ai",
           (("machine_learning", E, 2.5), ("data_engineering", IMP, 2), ("automated_testing", IMP, 1.5),
            ("backend_development", B, 1.5), ("llm_engineering", B, 1.5))),
    Preset("mlops", DATA, ("Ingénieur·e MLOps", "MLOps Engineer"),
           ("Industrialiser le cycle de vie des modèles.", "Industrialise the model lifecycle."),
           "mlops ml ops industrialisation modèles model serving registry pipeline ia ai",
           (("machine_learning", E, 2), ("ci_cd", E, 2.5), ("containerization", IMP, 2), ("data_engineering", IMP, 2),
            ("systems_integration", IMP, 2), ("cloud_infrastructure", B, 1.5)), (1, 1, 1.5)),
    Preset("data_scientist", DATA, ("Data scientist", "Data Scientist"),
           ("Transformer des données en décisions mesurées.", "Turn data into measured decisions."),
           "data scientist science des données statistiques statistics modélisation prédictive analyse ia ai",
           (("machine_learning", E, 2), ("data_analysis", E, 2.5), ("experimentation", IMP, 2),
            ("structured_communication", IMP, 1.5), ("data_engineering", B, 1.5)), (1, 1.25, 1.25)),
    Preset("data_engineer", DATA, ("Data engineer", "Data Engineer"),
           ("Construire des pipelines de données fiables.", "Build reliable data pipelines."),
           "data engineer ingénieur données pipeline etl elt airflow dbt spark entrepôt warehouse",
           (("data_engineering", E, 2.5), ("database_design", IMP, 2), ("cloud_infrastructure", IMP, 1.5),
            ("automated_testing", B, 1.5), ("ci_cd", B, 1.5)), (1, 1, 1.5)),
    Preset("data_analyst", DATA, ("Data analyst / BI", "Data Analyst / BI"),
           ("Éclairer les décisions avec des analyses et tableaux de bord.",
            "Inform decisions with analyses and dashboards."),
           "data analyst analyste bi business intelligence tableau de bord dashboard sql power bi looker reporting",
           (("data_analysis", E, 2.5), ("structured_communication", IMP, 2), ("database_design", B, 1.5),
            ("experimentation", B, 1.5))),
    # ---------------------------------------------------------------- security
    Preset("security_analyst", SW, ("Analyste cybersécurité / SOC", "Security Analyst / SOC"),
           ("Détecter, analyser et répondre aux incidents de sécurité.",
            "Detect, analyse and respond to security incidents."),
           "cybersécurité cybersecurity sécurité security soc analyste analyst blue team siem incident réponse",
           (("security_engineering", E, 2.5), ("data_analysis", IMP, 1.5), ("structured_communication", IMP, 2),
            ("systems_integration", B, 1.5)), (1, 1, 1.5), ("CompTIA Security+", "CEH", "CISSP")),
    Preset("pentester", SW, ("Pentester / sécurité offensive", "Penetration Tester"),
           ("Éprouver la sécurité des systèmes et rapporter clairement.", "Test system security and report clearly."),
           "pentest pentester red team offensive sécurité offensive ethical hacking audit cybersécurité",
           (("security_engineering", E, 3), ("structured_communication", E, 2), ("backend_development", B, 1.5),
            ("cloud_infrastructure", B, 1.5)), (1.25, 1.5, 1), ("OSCP", "CEH")),
    Preset("ai_security", SW, ("Ingénieur·e sécurité IA", "AI Security Engineer"),
           ("Sécuriser les applications fondées sur des LLM.", "Secure LLM-based applications."),
           "sécurité ia ai security llm red team prompt injection guardrails owasp cybersécurité",
           (("security_engineering", E, 2.5), ("llm_engineering", E, 2), ("automated_testing", IMP, 2),
            ("technical_documentation", B, 1.5)), (1, 1.25, 1.5)),
    # ---------------------------------------------------------------- design
    Preset("ui_designer", DES, ("Designer UI/UX", "UI/UX Designer"),
           ("Concevoir des interfaces claires, testées auprès de vrais utilisateurs.",
            "Design clear interfaces tested with real users."),
           "ui ux designer design interface produit product figma maquette",
           (("ui_design", E, 2.5), ("ux_research", IMP, 2), ("visual_identity", IMP, 2), ("experimentation", B, 1.5),
            ("structured_communication", B, 1.5)), (1, 1.5, 0.75)),
    Preset("product_designer", DES, ("Product designer", "Product Designer"),
           ("Du problème utilisateur à l'interface livrée.", "From user problem to shipped interface."),
           "product designer design produit ux ui parcours utilisateur",
           (("ux_research", E, 2.5), ("ui_design", E, 2.5), ("experimentation", IMP, 1.5), ("data_analysis", B, 1.5),
            ("structured_communication", B, 1.5)), (1.25, 1.25, 1)),
    Preset("ux_researcher", DES, ("UX researcher", "UX Researcher"),
           ("Comprendre les utilisateurs et éclairer les décisions produit.",
            "Understand users and inform product decisions."),
           "ux researcher recherche utilisateur user research entretiens tests utilisabilité",
           (("ux_research", E, 3), ("structured_communication", E, 2), ("data_analysis", IMP, 1.5),
            ("experimentation", B, 1.5))),
    Preset("graphic_designer", DES, ("Graphiste / designer de marque", "Graphic / Brand Designer"),
           ("Créer des identités et supports visuels cohérents.", "Create consistent identities and visual assets."),
           "graphiste graphic designer brand marque identité visuelle logo print packaging illustration "
           "direction artistique da",
           (("visual_identity", E, 2.5), ("ui_design", B, 1.5), ("structured_communication", B, 1.5)),
           (1.25, 1.5, 0.75)),
    # ---------------------------------------------------------------- marketing
    Preset("growth_marketer", MKT, ("Growth marketer", "Growth Marketer"),
           ("Piloter l'acquisition par la donnée et l'expérimentation.",
            "Drive acquisition through data and experimentation."),
           "growth marketing acquisition croissance hacker",
           (("campaign_performance", E, 2.5), ("funnel_design", E, 2), ("experimentation", IMP, 2),
            ("data_analysis", IMP, 2), ("budget_management", IMP, 2), ("content_strategy", B, 1.5)),
           (1, 1, 1.5), ("Google Ads", "Google Analytics", "Meta Blueprint")),
    Preset("performance_marketer", MKT, ("Responsable acquisition payante (SEA/SMA)", "Paid Acquisition Manager"),
           ("Piloter les campagnes payantes au retour sur investissement.", "Run paid campaigns by return on investment."),
           "sea sma ads acquisition payante paid media performance google ads meta ads traffic manager marketing",
           (("campaign_performance", E, 3), ("budget_management", E, 2), ("data_analysis", IMP, 2),
            ("experimentation", IMP, 1.5)), (1, 1, 1.5), ("Google Ads", "Meta Blueprint")),
    Preset("seo_content", MKT, ("Responsable SEO / contenu", "SEO / Content Manager"),
           ("Attirer une audience qualifiée par le contenu.", "Attract a qualified audience through content."),
           "seo référencement naturel contenu content rédacteur writer copywriter éditorial blog marketing",
           (("content_strategy", E, 2.5), ("data_analysis", IMP, 1.5), ("structured_communication", IMP, 2),
            ("experimentation", B, 1.5))),
    Preset("social_media", MKT, ("Social media manager", "Social Media Manager"),
           ("Animer des communautés et mesurer l'engagement.", "Grow communities and measure engagement."),
           "social media réseaux sociaux community manager instagram tiktok linkedin contenu marketing",
           (("content_strategy", E, 2), ("campaign_performance", IMP, 1.5), ("visual_identity", IMP, 1.5),
            ("data_analysis", B, 1.5))),
    Preset("marketing_manager", MKT, ("Responsable marketing", "Marketing Manager"),
           ("Construire et piloter un plan marketing mesuré.", "Build and run a measured marketing plan."),
           "marketing manager responsable marketing plan stratégie cmo marque",
           (("campaign_performance", E, 2), ("budget_management", E, 2), ("funnel_design", IMP, 2),
            ("team_leadership", IMP, 1.5), ("data_analysis", IMP, 1.5)), (1.25, 1, 1.25)),
    # ---------------------------------------------------------------- sales & customers
    Preset("account_executive", SALES, ("Commercial·e grands comptes", "Account Executive"),
           ("Développer un portefeuille et conclure des ventes complexes.", "Grow a portfolio and close complex deals."),
           "commercial vente sales account executive grands comptes key account business",
           (("sales_pipeline", E, 2.5), ("structured_communication", IMP, 2), ("data_analysis", B, 1.5),
            ("project_management", B, 1.5)), (1.5, 1, 1)),
    Preset("sdr", SALES, ("Business developer / SDR", "Business Developer / SDR"),
           ("Prospecter et ouvrir de nouvelles opportunités.", "Prospect and open new opportunities."),
           "sdr bdr business developer prospection prospecting lead generation commercial vente sales",
           (("sales_pipeline", E, 2), ("structured_communication", IMP, 1.5), ("data_analysis", B, 1)),
           (1.5, 0.75, 1)),
    Preset("customer_success", SALES, ("Customer success manager", "Customer Success Manager"),
           ("Faire réussir les clients et développer le revenu récurrent.",
            "Make customers successful and grow recurring revenue."),
           "customer success csm relation client account manager fidélisation retention onboarding",
           (("sales_pipeline", IMP, 2), ("structured_communication", E, 2), ("data_analysis", IMP, 1.5),
            ("project_management", B, 1.5))),
    # ---------------------------------------------------------------- product & management
    Preset("product_manager", MGMT, ("Product manager / product owner", "Product Manager / Product Owner"),
           ("Décider quoi construire, et le prouver par la donnée.", "Decide what to build, and prove it with data."),
           "product manager pm product owner po produit chef de produit roadmap",
           (("project_management", E, 2), ("data_analysis", E, 2), ("experimentation", IMP, 2),
            ("ux_research", IMP, 1.5), ("structured_communication", IMP, 2)), (1.25, 1, 1.25)),
    Preset("project_manager", MGMT, ("Chef·fe de projet", "Project Manager"),
           ("Mener des projets à terme, dans les délais et le budget.", "Deliver projects on time and on budget."),
           "chef de projet project manager pmo gestion de projet planning coordination moa amoa",
           (("project_management", E, 2.5), ("budget_management", IMP, 2), ("structured_communication", IMP, 2),
            ("team_leadership", B, 1.5)), (1.25, 1, 1.25), ("PMP", "PRINCE2", "Scrum Master")),
    Preset("scrum_master", MGMT, ("Scrum master / coach agile", "Scrum Master / Agile Coach"),
           ("Faire progresser les équipes et leur façon de livrer.", "Help teams improve how they deliver."),
           "scrum master agile coach agilité kanban rituels",
           (("project_management", E, 2), ("team_leadership", E, 2), ("structured_communication", IMP, 2)),
           (1, 1, 1), ("Scrum Master", "PSM")),
    Preset("engineering_manager", MGMT, ("Engineering manager / CTO", "Engineering Manager / CTO"),
           ("Faire grandir une équipe technique et ses pratiques.", "Grow an engineering team and its practices."),
           "engineering manager cto directeur technique tech lead manager équipe technique head of engineering",
           (("team_leadership", E, 2.5), ("software_architecture", E, 2), ("project_management", IMP, 2),
            ("ci_cd", B, 1.5), ("budget_management", B, 1.5)), (1.5, 1.25, 1)),
    Preset("operations_manager", MGMT, ("Responsable des opérations", "Operations Manager"),
           ("Organiser l'activité, les équipes et les budgets.", "Run activity, teams and budgets."),
           "opérations operations responsable directeur des opérations office manager gestion",
           (("project_management", E, 2), ("budget_management", E, 2), ("team_leadership", IMP, 2),
            ("quality_control", B, 1.5))),
    # ---------------------------------------------------------------- crafts & trades
    Preset("cabinetmaker", CRAFT, ("Menuisier·ère agenceur·euse", "Cabinetmaker / Joiner"),
           ("Fabriquer et poser des ouvrages bois sur mesure.", "Build and install bespoke timber work."),
           "menuisier menuisière agenceur ébéniste bois joiner cabinetmaker woodworker",
           (("woodworking", E, 2.5), ("construction_works", IMP, 2), ("quality_control", IMP, 2),
            ("project_management", B, 1.5), ("budget_management", B, 1.5)), (1.25, 1.5, 1),
           ("CAP", "Brevet professionnel")),
    Preset("carpenter", CRAFT, ("Charpentier·ère", "Carpenter (structural)"),
           ("Tailler, assembler et lever des charpentes.", "Cut, assemble and raise timber frames."),
           "charpentier charpente carpenter timber frame couvreur ossature bois",
           (("woodworking", E, 2.5), ("construction_works", E, 2), ("quality_control", IMP, 2)),
           (1.25, 1.5, 1.25), ("CAP",)),
    Preset("renovation", CRAFT, ("Conducteur·rice de travaux / rénovation", "Site Manager / Renovation"),
           ("Mener des chantiers de rénovation de bout en bout.", "Run renovation jobs end to end."),
           "conducteur de travaux chantier rénovation renovation bâtiment btp construction site manager",
           (("construction_works", E, 2.5), ("project_management", E, 2), ("budget_management", IMP, 2),
            ("quality_control", IMP, 2), ("team_leadership", B, 1.5)), (1.5, 1, 1.25)),
    Preset("welder", CRAFT, ("Soudeur·euse / métallier·ère", "Welder / Metalworker"),
           ("Réaliser des ouvrages métalliques soudés et contrôlés.", "Produce welded, inspected metalwork."),
           "soudeur soudure métallier serrurier chaudronnier welder metalwork tig mig",
           (("metalwork", E, 2.5), ("quality_control", E, 2), ("construction_works", B, 1.5)), (1, 1.5, 1.5),
           ("CAP",)),
    # ---------------------------------------------------------------- culinary
    Preset("line_cook", FOOD, ("Chef·fe de partie", "Chef de partie"),
           ("Tenir un poste en cuisine avec régularité et hygiène irréprochable.",
            "Run a kitchen station with consistency and flawless hygiene."),
           "chef de partie cuisinier cuisine cook commis restauration",
           (("culinary_technique", E, 2.5), ("food_safety", E, 2), ("team_leadership", B, 1.5),
            ("quality_control", IMP, 2)), (1, 1.25, 1.5), ("HACCP", "CAP")),
    Preset("head_chef", FOOD, ("Chef·fe de cuisine", "Head Chef"),
           ("Concevoir la carte, diriger la brigade et tenir les coûts.",
            "Design the menu, lead the brigade and control costs."),
           "chef de cuisine head chef second de cuisine sous-chef brigade restaurant gastronomie",
           (("culinary_technique", E, 3), ("team_leadership", E, 2), ("food_safety", E, 2),
            ("budget_management", IMP, 2)), (1.5, 1.25, 1.5), ("HACCP",)),
    Preset("pastry_chef", FOOD, ("Pâtissier·ère", "Pastry Chef"),
           ("Réaliser des pâtisseries techniques avec précision.", "Produce technical pastry with precision."),
           "pâtissier pâtissière pastry chef boulanger boulangerie chocolatier",
           (("culinary_technique", E, 2.5), ("quality_control", IMP, 2), ("food_safety", IMP, 2)), (1, 1.5, 1.5),
           ("CAP", "HACCP")),
    # ---------------------------------------------------------------- textile
    Preset("dressmaker", TEX, ("Modéliste couturier·ère", "Pattern maker / Dressmaker"),
           ("Du patron à la pièce finie.", "From pattern to finished garment."),
           "couturier couturière modéliste couture patronage pattern maker dressmaker tailleur retouche mode",
           (("garment_construction", E, 2.5), ("quality_control", IMP, 2), ("visual_identity", B, 1.5)),
           (1, 1.5, 1)),
    # ---------------------------------------------------------------- transversal
    Preset("technical_writer", TRANS, ("Rédacteur·rice technique", "Technical Writer"),
           ("Rendre des sujets complexes clairs et utilisables.", "Make complex topics clear and usable."),
           "rédacteur technique technical writer documentation doc writer",
           (("technical_documentation", E, 2.5), ("structured_communication", E, 2.5),
            ("frontend_development", B, 1))),
]

PRESETS: dict[str, Preset] = {p.id: p for p in _PRESETS}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def preset_job(preset_id: str, locale: str = "fr") -> JobProfile:
    p = PRESETS[preset_id]
    i = 0 if locale == "fr" else 1
    return JobProfile(
        title=p.title[i], summary=p.summary[i], family=p.family, locale="fr" if locale == "fr" else "en",
        criteria=[Criterion(skill_id=s, importance=imp, min_level=lvl) for s, imp, lvl in p.criteria],
        axis_weights=AxisWeights(autonomy=p.axis[0], complexity=p.axis[1], reliability=p.axis[2]),
        credentials=CredentialsPolicy(accepted=list(p.credentials)),
    )


def _words(text: str) -> set[str]:
    return set(re.split(r"[^a-z0-9+#]+", _fold(text)))


def _hit(word: str, vocabulary: set[str]) -> bool:
    return word in vocabulary if len(word) <= 2 else any(v.startswith(word) for v in vocabulary)


def search_presets(query: str) -> list[str]:
    """Preset ids matching every word of the query (titles, keywords, skill labels), accent-insensitive."""
    from ..translator.catalog import CATALOG

    words = [w for w in re.split(r"[^a-z0-9+#]+", _fold(query)) if w]
    if not words:
        return [p.id for p in _PRESETS]
    scored = []
    for p in _PRESETS:
        labels = " ".join(CATALOG[s].label["fr"] + " " + CATALOG[s].label["en"] for s, _, _ in p.criteria)
        hay = _words(" ".join([*p.title, p.keywords, labels]))
        title = _words(" ".join(p.title))
        # Short words ("ia", "ux", "ml") must match a whole word, longer ones a word prefix:
        # a substring search found "ia" in "fiabilité" and "ux" in "travaux".
        if all(_hit(w, hay) for w in words):
            scored.append((sum(3 if _hit(w, title) else 1 for w in words), p.id))
    return [pid for _, pid in sorted(scored, key=lambda t: -t[0])]


def list_presets(locale: str = "fr", query: str = "") -> list[dict[str, Any]]:
    i = 0 if locale == "fr" else 1
    ids = search_presets(query) if query.strip() else [p.id for p in _PRESETS]
    return [{"id": pid, "family": PRESETS[pid].family, "title": PRESETS[pid].title[i],
             "summary": PRESETS[pid].summary[i], "keywords": PRESETS[pid].keywords,
             "job": preset_job(pid, locale).model_dump(mode="json")} for pid in ids]
