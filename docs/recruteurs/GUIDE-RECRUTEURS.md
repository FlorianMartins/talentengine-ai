# TalentEngine-AI — Guide pour les recruteurs

> **Trouvez les personnes qui savent faire, pas seulement celles qui savent écrire un CV.**
>
> Essai gratuit, sans compte, en deux minutes : **https://hivey.be/talentengine/essai**
> Collez une de vos offres (texte ou lien LinkedIn), ajoutez un CV et un lien GitHub ou portfolio :
> vous voyez le score, les preuves, les écarts et les questions d'entretien générées.

*English version: [RECRUITER-GUIDE.md](RECRUITER-GUIDE.md)*

---

## Sommaire

1. [Le problème que vous connaissez déjà](#1-le-problème-que-vous-connaissez-déjà)
2. [Ce que TalentEngine-AI change](#2-ce-que-talentengine-ai-change)
3. [Ce que vous y gagnez, concrètement](#3-ce-que-vous-y-gagnez-concrètement)
4. [Essayer en 10 minutes](#4-essayer-en-10-minutes)
5. [Utilisation pas à pas](#5-utilisation-pas-à-pas)
6. [Lire un rapport sans être du métier](#6-lire-un-rapport-sans-être-du-métier)
7. [Mener l'entretien avec le guide généré](#7-mener-lentretien-avec-le-guide-généré)
8. [Des exemples chiffrés](#8-des-exemples-chiffrés)
9. [Conformité, éthique et données personnelles](#9-conformité-éthique-et-données-personnelles)
10. [Ce que l'outil ne fait pas (encore)](#10-ce-que-loutil-ne-fait-pas-encore)
11. [Vos objections, nos réponses](#11-vos-objections-nos-réponses)
12. [Proposition : un pilote de 30 jours](#12-proposition--un-pilote-de-30-jours)

---

## 1. Le problème que vous connaissez déjà

Vous publiez une offre. Des centaines de candidatures arrivent. Votre ATS les trie sur des **mots-clés**
et des **diplômes**, parce que c'est ce qu'il sait lire. Résultat :

- **Des profils excellents disparaissent avant votre lecture.** L'autodidacte qui a construit et
  maintenu une infrastructure complète, la personne en reconversion qui a déjà livré trois projets,
  l'artisan dont le travail parle de lui-même : ils n'ont pas le bon intitulé de diplôme, ou pas le
  bon mot dans le bon champ.
- **Les CV « optimisés » remontent.** Un CV qui répète les mots de l'offre passe les filtres, qu'il y
  ait ou non une réalisation derrière.
- **Vous jugez des métiers que vous ne pratiquez pas.** Évaluer un dépôt GitHub, un tunnel de
  conversion ou un assemblage à queue d'aronde demande une expertise que l'équipe de recrutement n'a
  pas toujours, et que les managers n'ont pas le temps de mettre au service de chaque candidature.
- **Le diplôme sert de raccourci.** Il est pratique, mais il mesure un parcours passé, pas ce que la
  personne sait faire aujourd'hui, et il reproduit les inégalités d'accès aux études.

## 2. Ce que TalentEngine-AI change

TalentEngine-AI lit **ce que les candidats ont réellement produit** : dépôts de code, rapports de
campagne chiffrés, études de cas, descriptions et photos de réalisations, et le CV lui-même. Il en
tire des **preuves**, et compare ces preuves aux critères de **votre** offre.

| | ATS classique | TalentEngine-AI |
|---|---|---|
| Ce qui est évalué | Les mots du CV, l'intitulé du diplôme | Des preuves tirées du travail du candidat |
| « Maîtrise de Google Ads » dans une liste de compétences | Compte comme un critère rempli | Ne rapporte **aucun point** : c'est une déclaration, elle devient une question d'entretien |
| « Budget Google Ads de 450 k€, ROAS de 2,1 à 4,3 » | Un mot-clé parmi d'autres | Une **preuve chiffrée**, citée ligne à ligne dans le rapport |
| Diplômes et certifications | Souvent un filtre éliminatoire | Comptés, mais **plafonnés** (10 % par défaut, jamais plus de 25 %) |
| Décision | Rejet automatique | **Aucun rejet automatique** : l'outil classe, une personne décide |
| Explication | Aucune | Chaque compétence cite le fichier, la ligne ou l'image qui la prouve |
| Données personnelles | Lues par tous | Nom, âge, genre, nationalité, adresse et **nom d'école** masqués avant l'analyse |

### Comment ça marche, en quatre étapes

1. **Le bouclier légal.** Chaque pièce est d'abord anonymisée : identité, coordonnées, âge, situation
   familiale, nationalité, nom de l'établissement scolaire (un indicateur de prestige qui biaise), et
   tournures genrées (« développeuse » devient « développeur·euse »). Les visages et logos des images
   sont floutés par un modèle **local**. L'identité est chiffrée ; vous ne la voyez qu'après avoir pris
   une décision de présélection.
2. **L'entonnoir budgétaire.** Tout le monde est analysé gratuitement, sur votre serveur. Pour un dépôt
   GitHub, l'outil lit la **structure** (présence de tests, d'intégration continue, de contrôles de
   sécurité…) sans lire tout le code. Un modèle d'IA commercial n'intervient, si vous l'activez, que
   pour les quelques dossiers les plus riches en preuves, avec un plafond de dépense par offre.
3. **Le traducteur métier.** Les preuves sont traduites en compétences (31 compétences : logiciel,
   données, design, marketing, vente, artisanat, cuisine, couture, management, cloud…) et notées sur
   trois axes que tout le monde comprend : **autonomie** (a-t-il mené le travail de bout en bout ?),
   **complexité** (est-ce difficile ?), **fiabilité** (y a-t-il des contrôles, des tests, des résultats
   mesurés ?).
4. **Le tableau de bord RH.** Un score de compatibilité avec **vos** critères, la liste des preuves en
   langage clair, les écarts à explorer, et trois questions d'entretien avec les réponses attendues.

## 3. Ce que vous y gagnez, concrètement

### Pour la chargée ou le chargé de recrutement
- **Un vivier élargi** : les profils atypiques ne sont plus éliminés par un filtre de mots-clés.
- **Une lecture plus rapide des dossiers riches** : les preuves sont extraites et classées pour vous,
  avec l'extrait exact (« voir le fichier `.github/workflows/ci.yml` », « voir le rapport T3, lignes
  3-5 »).
- **Des entretiens mieux préparés sans être expert** : trois questions précises sur le travail du
  candidat, avec les points qu'une personne qui l'a vraiment fait mentionnera, et les signaux d'alerte.
- **Moins de dépendance aux managers pour le premier tri** : ils interviennent sur des dossiers déjà
  argumentés.

### Pour le manager qui recrute
- **Il définit lui-même ce qui compte** : compétences essentielles, importantes ou bonus, niveau
  attendu, et ce qu'il valorise le plus (autonomie, complexité ou fiabilité).
- **Il voit des faits**, pas des adjectifs : « le pipeline bloque toute fusion si les tests échouent »
  plutôt que « rigoureux et passionné ».

### Pour la DRH, la ou le DPO et la direction
- **Moins de risque juridique** : pas de décision automatisée (RGPD art. 22), explication de chaque
  score (AI Act art. 13 et 86), journal d'audit infalsifiable (AI Act art. 12), décision humaine
  motivée (AI Act art. 14), effacement sur demande (RGPD art. 17).
- **Des engagements diversité tenables** : l'anonymisation est mesurée (même qualité de masquage quelle
  que soit l'origine du nom) et un test vérifie qu'un même travail obtient le même score quels que
  soient le nom, le genre, l'âge, la nationalité ou l'école.
- **Des coûts d'IA maîtrisés** : fonctionnement 100 % local par défaut ; l'IA commerciale est une option
  plafonnée, réservée aux meilleurs dossiers.
- **Pas de dépendance à un éditeur** : logiciel libre (licence MIT), auto-hébergé, vos données restent
  chez vous.

### Pour les candidats (et votre marque employeur)
- Ils sont évalués sur leur travail, pas sur leur capacité à deviner les bons mots-clés.
- Ils peuvent obtenir l'explication de leur score.
- L'essai public leur montre ce qu'ils doivent prouver pour une offre : un geste de transparence rare.

## 4. Essayer en 10 minutes

### Étape 1 — L'essai public (2 minutes, sans compte)

1. Ouvrez **https://hivey.be/talentengine/essai**.
2. **Le poste** : collez le texte d'une de vos offres, ou son lien (LinkedIn, Welcome to the Jungle,
   Indeed, page carrière). L'outil détecte les compétences demandées, leur importance (« indispensable »,
   « un plus ») et le niveau attendu (« 5 ans d'expérience », « senior »). Vous pouvez tout corriger.
   Vous pouvez aussi partir d'un **poste type**.
3. **Le profil** : déposez un CV (le vôtre, celui d'un collègue volontaire, ou un CV fictif), ajoutez un
   lien GitHub ou portfolio.
4. **Le résultat** : score, preuves, écarts, questions d'entretien.

Rien n'est conservé : l'analyse se fait en mémoire et tout est effacé à la fin de la requête.

> Astuce : testez la même offre avec deux profils très différents, par exemple un CV très diplômé mais
> sans réalisation, et un CV d'autodidacte avec un vrai projet. C'est la meilleure démonstration de ce
> que l'outil change.

### Étape 2 — La version recruteur (auto-hébergée)

La version complète (plusieurs offres, base de candidatures, comparaison, décisions, journal d'audit)
s'installe en une commande sur un serveur de votre organisation :

```bash
git clone https://github.com/FlorianMartins/talentengine-ai.git && cd talentengine-ai
cp .env.example .env        # puis renseignez les clés (talentengine keygen)
docker compose up -d --build
```

Votre équipe informatique trouvera tous les détails dans le [guide d'utilisation](../USER_GUIDE.md).
Pour une démonstration accompagnée de la version recruteur, ouvrez une demande sur
https://github.com/FlorianMartins/talentengine-ai/issues.

## 5. Utilisation pas à pas

### 5.1 Décrire le poste (le studio de configuration)

C'est l'étape la plus importante : **l'outil cherche ce que vous lui demandez de chercher**.

1. **Partez d'un poste type** (DevSecOps, développeur·euse full-stack, designer UI/UX, growth marketer,
   commercial·e grands comptes, menuisier·ère agenceur·euse, chef·fe de partie, modéliste couturier·ère),
   ou de votre propre offre.
2. **Choisissez les critères** dans le catalogue. Pour chacun :
   - **importance** : *essentiel* (compte triple), *important* (double), *bonus* (simple) ;
   - **poids** : un réglage fin en plus de l'importance ;
   - **niveau attendu** de 0 à 4 (Émergent, Initié, Opérationnel, Confirmé, Expert) : le niveau à partir
     duquel le critère est pleinement rempli ;
   - **une note** dans vos mots (« indispensable dès le premier mois »), reprise dans les rapports.
3. **Réglez les trois axes** : un poste d'astreinte valorise la *fiabilité*, un poste de création la
   *complexité*, un poste en indépendance l'*autonomie*.
4. **Diplômes et certifications** : ignorez-les ou gardez-les en second plan (10 % par défaut, 25 %
   au maximum), et listez ceux qui comptent vraiment pour vous (« CAP », « HACCP », « AWS Certified »).
5. **Budget IA** : laissez « local uniquement » pour commencer. Activez l'approfondissement par IA
   seulement si vous voulez une analyse plus fine des meilleurs dossiers, avec un plafond en euros.
6. **Confidentialité** : laissez les options activées sauf avis contraire de votre DPO.

Chaque modification crée une **nouvelle version** du poste, enregistrée dans le journal d'audit : vous
pourrez toujours dire quelle configuration a produit quel score.

### 5.2 Recevoir les candidatures

Partagez le formulaire de candidature ou déposez les pièces pour le compte du candidat (avec son
accord) : CV (PDF, Word, texte), documents (rapports, études de cas), liens GitHub, réalisations
décrites, photos de travaux. Le **nom est obligatoire** : c'est lui qui permet de le masquer partout,
quelle que soit la mise en page des documents.

### 5.3 Lancer l'évaluation

Un clic sur **Lancer l'évaluation**. Vous obtenez une liste **anonyme** (`CAND-1A2B3C`) classée par
compatibilité. Ce classement **n'écarte personne** : les filtres de l'écran ne changent que ce que vous
regardez.

### 5.4 Comparer et décider

Sélectionnez deux ou trois candidatures pour les comparer critère par critère. Enregistrez votre
décision (présélection, entretien, en attente, non retenu·e) avec une courte justification. Après une
présélection ou un entretien, vous pouvez **révéler l'identité** pour contacter la personne ; cet accès
est journalisé.

## 6. Lire un rapport sans être du métier

| Élément | Ce qu'il vous dit | Comment l'utiliser |
|---|---|---|
| **Score de compatibilité** | À quel point les preuves fournies couvrent *vos* critères | Pour ordonner votre lecture, jamais pour éliminer |
| **Compétences prouvées / diplômes** | La part du score venant des preuves et celle venant des diplômes | Vérifier que le score ne repose pas sur le papier |
| **Niveau de preuve** (solide, modéré, limité) | La quantité et la qualité du matériel fourni, **pas la valeur de la personne** | Un niveau « limité » appelle une question, pas un rejet |
| **Grille des critères** | Pour chaque critère : niveau attendu, niveau observé, statut | Repérer en un coup d'œil ce qui est démontré |
| **Panneau des preuves** | « Prouvé par les pièces : sait gérer un budget (voir Document 2) » + l'extrait exact | Citer la preuve en entretien |
| **À explorer en entretien** | Critères sans preuve ou partiels ; compétences seulement *déclarées* | Préparer vos questions ; « pas de preuve » ne veut pas dire « pas de compétence » |
| **Uniquement décrit dans le CV** | Une compétence affirmée dans le CV sans réalisation jointe : plafonnée à « Opérationnel » | Demander un exemple ou une réalisation |
| **Alertes** | Instructions cachées détectées dans un document, images mises de côté faute de détecteur de visages | À examiner par une personne : l'outil ne pénalise jamais automatiquement |
| **Boîte de verre (audit)** | L'historique complet et vérifiable de chaque étape | Répondre à un candidat qui demande « pourquoi ce score ? » |

## 7. Mener l'entretien avec le guide généré

Chaque rapport propose **trois questions** portant sur le travail réel du candidat, choisies pour
vérifier qu'il en est **bien l'auteur**. Exemple, pour un dépôt contenant un pipeline d'intégration
continue :

> **Question.** « Le projet repo-1 contient un pipeline automatique (.github/workflows/ci.yml). Que se
> passe-t-il, étape par étape, quand vous envoyez une modification ? Que faites-vous quand il échoue ? »
>
> **Ce qu'une personne qui l'a fait mentionnera :** des étapes dans l'ordre (installation, vérifications,
> tests, construction) ; ce qui bloque une livraison ; comment elle lit un échec et le reproduit ; la
> gestion des secrets (mots de passe hors du code).
>
> **Signaux d'alerte :** une réponse générale qui pourrait s'appliquer à n'importe quel projet ; la
> personne ne retrouve pas l'élément dans son propre travail.

Cochez les points pendant l'entretien. Pour un dossier sans réalisation jointe, les questions portent
sur les compétences **déclarées** : « Vous indiquez maîtriser X : décrivez une réalisation concrète, ce
que vous avez fait vous-même et le résultat. » Un dossier mince est une raison de poser des questions,
jamais de rejeter.

## 8. Des exemples chiffrés

Ces chiffres viennent du jeu de démonstration (profils fictifs) et des mesures publiées dans
[MEASUREMENTS.md](../MEASUREMENTS.md). Ils montrent le comportement de l'outil ; ils ne sont pas une
promesse de résultats dans votre organisation.

| Poste | Profil | Score |
|---|---|---|
| Ingénieur·e DevSecOps | Autodidacte, **sans diplôme**, dépôt testé, automatisé et sécurisé | **78 %** |
| | Reconversion (maintenance industrielle → DevOps), CAP | 61 % |
| | Diplôme d'ingénieur + 2 certifications + un dépôt solide | 59 % |
| | Master + diplôme d'ingénieur + 3 certifications, **aucune réalisation** | **5 %** |
| Menuisier·ère | Artisan indépendant, trois réalisations décrites | 70 % |
| | CAP + brevet professionnel, une réalisation | 22 % |

Et sur la robustesse :

- **Un CV « bourré » de phrases chiffrées inventées** obtenait 64 % dans la première version, plus
  qu'un vrai dépôt. Il est aujourd'hui ramené à **34 %**, toujours en dessous d'un vrai travail.
- **Le masquage du nom est identique** pour les 7 origines de noms testées.
- **Un même travail** soumis sous cinq identités différentes (nom, genre, âge, nationalité, école
  prestigieuse ou non) obtient **exactement le même score**.

## 9. Conformité, éthique et données personnelles

Le recrutement est classé **à haut risque** par l'AI Act européen. TalentEngine-AI a été conçu pour
vous aider à respecter vos obligations :

| Exigence | Ce que fait l'outil |
|---|---|
| Pas de décision automatisée (RGPD art. 22) | Aucun rejet automatique n'existe dans le code ; la décision est humaine, nominative et motivée |
| Transparence et explication (AI Act art. 13 et 86) | Chaque compétence cite la preuve exacte ; le candidat peut obtenir l'explication de son score |
| Journalisation (AI Act art. 12) | Journal d'audit en ajout seul, chaîné et scellé : toute modification est détectée |
| Contrôle humain (AI Act art. 14) | Classement indicatif, alertes visibles, décisions tracées |
| Minimisation et protection dès la conception (RGPD art. 5 et 25) | Anonymisation à l'entrée, identité chiffrée, analyse locale par défaut |
| Droit à l'effacement (RGPD art. 17) | Effacement en un clic ; le journal reste intègre mais n'est plus relié à la personne |

**Ce qui reste de votre responsabilité** : l'analyse d'impact (AIPD), l'information des candidats et des
représentants du personnel, le choix d'un éventuel fournisseur d'IA, et la formation des recruteurs au
bon usage du score. Détails : [COMPLIANCE.md](../COMPLIANCE.md).

## 10. Ce que l'outil ne fait pas (encore)

Nous préférons vous le dire :

- **Il ne remplace ni l'entretien ni votre jugement.** Il prépare les deux.
- **Les mesures d'anonymisation viennent de corpus synthétiques**, pas encore d'un grand jeu de vrais CV.
- **Il ne lit pas tout** : les profils sans aucune trace écrite ou visuelle de leur travail obtiennent
  un niveau de preuve « limité ». C'est une invitation à demander des exemples, pas un verdict.
- **La version recruteur est un MVP** : base SQLite, une clé d'accès par instance, pas encore de
  connexion multi-utilisateurs ni d'intégration native à votre ATS (prévues dans la
  [feuille de route](../ROADMAP.md)).
- **Les règles de détection des compétences** doivent être relues avec des praticiens de chaque métier
  avant un usage à grande échelle.

## 11. Vos objections, nos réponses

**« Je n'ai pas le temps d'installer un nouvel outil. »**
L'essai public ne demande ni installation ni compte : deux minutes avec une de vos offres. La version
recruteur s'installe en une commande sur un serveur.

**« Les diplômes comptent pour nos postes. »**
Ils comptent ici aussi : listez ceux qui vous importent, ils pèsent jusqu'à 25 % du score. Ce que
l'outil empêche, c'est qu'un diplôme **sans aucune réalisation** passe devant une personne qui a fait
ses preuves.

**« Et si le candidat ment ou copie un projet ? »**
Les déclarations sans preuve ne rapportent rien. Les CV répétitifs et gonflés sont pénalisés. Et le
guide d'entretien est précisément conçu pour vérifier que la personne est l'auteur de ce qu'elle
présente.

**« Nos candidats n'ont pas de GitHub. »**
GitHub n'est qu'une source parmi d'autres : rapports de campagne, études de cas, descriptions de
chantiers, photos de réalisations, fiches techniques. Le catalogue couvre aussi le marketing, la vente,
l'artisanat, la cuisine, la couture et le management.

**« L'IA va-t-elle discriminer ? »**
L'outil retire les informations sensibles **avant** toute analyse, mesure son propre masquage par
origine de nom, et vérifie par un test qu'un même travail reçoit le même score quelle que soit
l'identité. L'IA commerciale, si vous l'activez, ne voit ni les critères de pondération ni les diplômes,
et son influence est bornée à un niveau autour de l'estimation fondée sur les preuves.

**« Que deviennent les données des candidats ? »**
Dans l'essai public : rien n'est conservé. Dans la version recruteur : elles restent sur votre serveur,
l'identité est chiffrée, et l'effacement est immédiat sur demande.

**« Combien ça coûte ? »**
Le logiciel est libre et gratuit. L'analyse locale ne coûte rien. L'approfondissement par une IA
commerciale est optionnel, plafonné par offre (5 $ par défaut), et ne concerne que les meilleurs
dossiers.

**« Ça remplace mon ATS ? »**
Non : il s'intercale. Vous continuez à publier et à gérer le processus dans votre ATS ; TalentEngine-AI
évalue les preuves et vous aide à choisir qui rencontrer.

## 12. Proposition : un pilote de 30 jours

Pour vous faire votre propre idée, nous vous proposons un pilote simple, sur **une offre réelle** :

| Semaine | Action | Ce que vous mesurez |
|---|---|---|
| 1 | Configurer le poste avec le manager dans le studio (30 min) ; tester avec 3 CV connus | Le classement correspond-il à votre intuition sur des profils que vous connaissez ? |
| 2 | Évaluer en parallèle de votre processus habituel | Combien de profils présélectionnés par TalentEngine-AI votre filtre habituel aurait-il écartés ? |
| 3 | Mener 3 à 5 entretiens avec le guide généré | Les questions ont-elles aidé à vérifier l'expertise ? Combien de temps de préparation gagné ? |
| 4 | Bilan avec le manager et la ou le DPO | Qualité des profils rencontrés, diversité des parcours, confort de lecture, questions de conformité |

À la fin, vous aurez **vos** chiffres, sur **vos** offres. C'est la seule mesure qui compte.

---

**Essayer maintenant :** https://hivey.be/talentengine/essai ·
**Code source :** https://github.com/FlorianMartins/talentengine-ai ·
**Questions et démonstration :** https://github.com/FlorianMartins/talentengine-ai/issues
