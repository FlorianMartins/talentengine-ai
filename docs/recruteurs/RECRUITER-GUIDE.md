# TalentEngine-AI — Recruiter Guide

> **Find the people who can do the work, not just the people who can write a CV.**
>
> Free trial, no account, two minutes: **https://hivey.be/talentengine/essai** (English interface available via the language switch)
> Paste one of your job ads (text or LinkedIn link), add a CV and a GitHub or portfolio link:
> you see the score, the evidence, the gaps and the generated interview questions.

*Version française : [GUIDE-RECRUTEURS.md](GUIDE-RECRUTEURS.md)*

---

## Contents

1. [The problem you already know](#1-the-problem-you-already-know)
2. [What TalentEngine-AI changes](#2-what-talentengine-ai-changes)
3. [What you gain, concretely](#3-what-you-gain-concretely)
4. [Try it in 10 minutes](#4-try-it-in-10-minutes)
5. [Step-by-step usage](#5-step-by-step-usage)
6. [Reading a report without being an expert](#6-reading-a-report-without-being-an-expert)
7. [Running the interview with the generated guide](#7-running-the-interview-with-the-generated-guide)
8. [Worked examples with numbers](#8-worked-examples-with-numbers)
9. [Compliance, ethics and personal data](#9-compliance-ethics-and-personal-data)
10. [What the tool does not do (yet)](#10-what-the-tool-does-not-do-yet)
11. [Your objections, our answers](#11-your-objections-our-answers)
12. [Proposal: a 30-day pilot](#12-proposal-a-30-day-pilot)

---

## 1. The problem you already know

You publish a job ad. Hundreds of applications arrive. Your ATS sorts them on **keywords**
and **degrees**, because that is what it can read. The result:

- **Excellent profiles disappear before you ever read them.** The self-taught engineer who built and
  maintained a complete infrastructure, the career changer who has already delivered three projects,
  the craftsperson whose work speaks for itself: they do not have the right degree title, or the
  right word in the right field.
- **"Optimised" CVs rise to the top.** A CV that repeats the words of the ad gets through the filters,
  whether or not there is any achievement behind it.
- **You are judging trades you do not practise.** Assessing a GitHub repository, a conversion funnel
  or a dovetail joint takes expertise that the recruitment team does not always have, and that
  managers do not have the time to apply to every application.
- **The degree is used as a shortcut.** It is convenient, but it measures a past path, not what the
  person can do today, and it reproduces inequalities in access to education.

## 2. What TalentEngine-AI changes

TalentEngine-AI reads **what candidates have actually produced**: code repositories, quantified
campaign reports, case studies, descriptions and photos of finished work, and the CV itself. It draws
**evidence** from them, and compares that evidence with the criteria of **your** job ad.

| | Classic ATS | TalentEngine-AI |
|---|---|---|
| What is assessed | The words in the CV, the title of the degree | Evidence drawn from the candidate's work |
| "Google Ads proficiency" in a skills list | Counts as a criterion met | Earns **no points**: it is a claim, and it becomes an interview question |
| "Google Ads budget of €450k, ROAS from 2.1 to 4.3" | One keyword among others | **Quantified evidence**, quoted line by line in the report |
| Degrees and certifications | Often a knock-out filter | Counted, but **capped** (10% by default, never more than 25%) |
| Decision | Automatic rejection | **No automatic rejection**: the tool ranks, a person decides |
| Explanation | None | Each skill cites the file, line or image that proves it |
| Personal data | Read by everyone | Name, age, gender, nationality, address and **school name** masked before analysis |

### How it works, in four steps

1. **The legal shield.** Every document is first anonymised: identity, contact details, age, family
   situation, nationality, name of the school (a prestige indicator that skews judgement), and
   gendered wording ("développeuse" becomes "développeur·euse"). Faces and logos in images are
   blurred by a **local** model. The identity is encrypted; you only see it after you have made a
   shortlisting decision.
2. **The budget funnel.** Everyone is analysed for free, on your server. For a GitHub repository, the
   tool reads the **structure** (presence of tests, continuous integration, security checks…) without
   reading all the code. A commercial AI model steps in, if you enable it, only for the few files
   richest in evidence, with a spending cap per job ad.
3. **The trade translator.** Evidence is translated into skills (31 skills: software, data, design,
   marketing, sales, craft, cooking, sewing, management, cloud…) and scored on three axes that
   everyone understands: **autonomy** (did they carry the work through end to end?), **complexity**
   (is it hard?), **reliability** (are there checks, tests, measured results?).
4. **The HR dashboard.** A compatibility score against **your** criteria, the list of evidence in
   plain language, the gaps to explore, and three interview questions with the expected answers.

## 3. What you gain, concretely

### For the recruiter
- **A wider talent pool**: atypical profiles are no longer eliminated by a keyword filter.
- **Faster reading of rich files**: the evidence is extracted and ranked for you, with the exact
  excerpt ("see file `.github/workflows/ci.yml`", "see report T3, lines 3-5").
- **Better-prepared interviews without being an expert**: three precise questions about the
  candidate's work, with the points a person who really did it will mention, and the warning signs.
- **Less reliance on managers for the first screening**: they step in on files that already come with
  an argument.

### For the hiring manager
- **They define for themselves what matters**: essential, important or bonus skills, expected level,
  and what they value most (autonomy, complexity or reliability).
- **They see facts**, not adjectives: "the pipeline blocks any merge if the tests fail" rather than
  "rigorous and passionate".

### For the HR director, the DPO and management
- **Less legal risk**: no automated decision (GDPR Art. 22), explanation of every score (AI Act
  Art. 13 and 86), tamper-proof audit log (AI Act Art. 12), reasoned human decision (AI Act Art. 14),
  erasure on request (GDPR Art. 17).
- **Diversity commitments you can keep**: anonymisation is measured (the same masking quality
  whatever the origin of the name) and a test checks that the same work gets the same score whatever
  the name, gender, age, nationality or school.
- **Controlled AI costs**: 100% local operation by default; commercial AI is a capped option,
  reserved for the best files.
- **No vendor lock-in**: free software (MIT licence), self-hosted, your data stays with you.

### For candidates (and your employer brand)
- They are assessed on their work, not on their ability to guess the right keywords.
- They can obtain the explanation of their score.
- The public trial shows them what they need to prove for a given job ad: a rare gesture of
  transparency.

## 4. Try it in 10 minutes

### Step 1 — The public trial (2 minutes, no account)

1. Open **https://hivey.be/talentengine/essai**.
2. **The role**: paste the text of one of your job ads, or its link (LinkedIn, Welcome to the Jungle,
   Indeed, careers page). The tool detects the skills requested, their importance ("essential",
   "a plus") and the level expected ("5 years of experience", "senior"). You can correct everything.
   You can also start from a **template role**.
3. **The profile**: upload a CV (your own, a willing colleague's, or a fictitious one), add a GitHub
   or portfolio link.
4. **The result**: score, evidence, gaps, interview questions.

Nothing is kept: the analysis runs in memory and everything is erased at the end of the request.

> Tip: test the same job ad with two very different profiles, for example a highly qualified CV with
> no achievements, and the CV of a self-taught person with a real project. It is the best
> demonstration of what the tool changes.

### Step 2 — The recruiter edition (self-hosted)

The full version (several job ads, an application database, comparison, decisions, audit log) installs
with a single command on a server in your organisation:

```bash
git clone https://github.com/FlorianMartins/talentengine-ai.git && cd talentengine-ai
cp .env.example .env        # then fill in the keys (talentengine keygen)
docker compose up -d --build
```

Your IT team will find all the details in the [user guide](../USER_GUIDE.md).
For a guided demonstration of the recruiter edition, open a request at
https://github.com/FlorianMartins/talentengine-ai/issues.

## 5. Step-by-step usage

### 5.1 Describing the role (the configuration studio)

This is the most important step: **the tool looks for what you ask it to look for**.

1. **Start from a template role** (DevSecOps, full-stack developer, UI/UX designer, growth marketer,
   key account sales executive, joiner and fitter, chef de partie, pattern-maker and tailor),
   or from your own job ad.
2. **Choose the criteria** from the catalogue. For each one:
   - **importance**: *essential* (counts triple), *important* (double), *bonus* (single);
   - **weight**: a fine adjustment on top of importance;
   - **expected level** from 0 to 4 (Emerging, Initiated, Operational, Confirmed, Expert): the level at
     which the criterion is fully met;
   - **a note** in your own words ("essential from the first month"), carried into the reports.
3. **Set the three axes**: an on-call role values *reliability*, a creative role *complexity*, a role
   with a lot of independence *autonomy*.
4. **Degrees and certifications**: ignore them or keep them in the background (10% by default, 25%
   at most), and list the ones that really matter to you ("CAP" (French vocational certificate),
   "HACCP", "AWS Certified").
5. **AI budget**: leave it on "local only" to start with. Enable AI deepening only if you want a finer
   analysis of the best files, with a cap in euros.
6. **Privacy**: leave the options switched on unless your DPO advises otherwise.

Each change creates a **new version** of the role, recorded in the audit log: you will always be able
to say which configuration produced which score.

### 5.2 Receiving applications

Share the application form or upload the documents on the candidate's behalf (with their agreement):
CV (PDF, Word, text), documents (reports, case studies), GitHub links, described achievements, photos
of work. The **name is mandatory**: it is what allows it to be masked everywhere, whatever the layout
of the documents.

### 5.3 Running the evaluation

One click on **Run the evaluation**. You get an **anonymous** list (`CAND-1A2B3C`) ranked by
compatibility. This ranking **does not rule anyone out**: the screen filters only change what you
are looking at.

### 5.4 Comparing and deciding

Select two or three applications to compare them criterion by criterion. Record your decision
(shortlisted, interview, on hold, not selected) with a short justification. After a shortlisting or
an interview, you can **reveal the identity** in order to contact the person; this access is logged.

## 6. Reading a report without being an expert

| Element | What it tells you | How to use it |
|---|---|---|
| **Compatibility score** | How far the evidence provided covers *your* criteria | To order your reading, never to eliminate |
| **Proven skills / degrees** | The share of the score coming from evidence and the share coming from degrees | Check that the score does not rest on paper |
| **Evidence level** (strong, moderate, limited) | The quantity and quality of the material provided, **not the worth of the person** | A "limited" level calls for a question, not a rejection |
| **Criteria grid** | For each criterion: expected level, observed level, status | Spot at a glance what has been demonstrated |
| **Evidence panel** | "Proven by the documents: can manage a budget (see Document 2)" + the exact excerpt | Quote the evidence in the interview |
| **To explore in interview** | Criteria with no or partial evidence; skills only *declared* | Prepare your questions; "no evidence" does not mean "no skill" |
| **Described in the CV only** | A skill claimed in the CV with no attached achievement: capped at "Operational" | Ask for an example or an achievement |
| **Alerts** | Hidden instructions detected in a document, images set aside for lack of a face detector | To be reviewed by a person: the tool never penalises automatically |
| **Glass box (audit)** | The full, verifiable history of every step | Answer a candidate who asks "why this score?" |

## 7. Running the interview with the generated guide

Each report offers **three questions** about the candidate's real work, chosen to check that they are
**truly the author**. Example, for a repository containing a continuous integration pipeline:

> **Question.** "The project repo-1 contains an automated pipeline (.github/workflows/ci.yml). What
> happens, step by step, when you push a change? What do you do when it fails?"
>
> **What a person who did it will mention:** steps in order (installation, checks, tests, build); what
> blocks a release; how they read a failure and reproduce it; secrets management (passwords kept out
> of the code).
>
> **Warning signs:** a generic answer that could apply to any project; the person cannot find the item
> in their own work.

Tick off the points during the interview. For a file with no attached achievement, the questions are
about the **declared** skills: "You say you are proficient in X: describe a concrete achievement, what
you did yourself and the result." A thin file is a reason to ask questions, never to reject.

## 8. Worked examples with numbers

These figures come from the demonstration set (fictitious profiles) and from the measurements
published in [MEASUREMENTS.md](../MEASUREMENTS.md). They show how the tool behaves; they are not a
promise of results in your organisation.

| Role | Profile | Score |
|---|---|---|
| DevSecOps engineer | Self-taught, **no degree**, tested, automated and secured repository | **78%** |
| | Career changer (industrial maintenance → DevOps), CAP (French vocational certificate) | 61% |
| | Engineering degree + 2 certifications + a solid repository | 59% |
| | Master's + engineering degree + 3 certifications, **no achievements** | **5%** |
| Joiner | Independent craftsperson, three described achievements | 70% |
| | CAP + brevet professionnel (French advanced vocational certificate), one achievement | 22% |

And on robustness:

- **A CV "stuffed" with invented figures** scored 64% in the first version, more than a real
  repository. It is now brought down to **34%**, still below real work.
- **Name masking is identical** for the 7 name origins tested.
- **The same work** submitted under five different identities (name, gender, age, nationality,
  prestigious school or not) gets **exactly the same score**.

## 9. Compliance, ethics and personal data

Recruitment is classed as **high risk** by the European AI Act. TalentEngine-AI was designed to help
you meet your obligations:

| Requirement | What the tool does |
|---|---|
| No automated decision (GDPR Art. 22) | No automatic rejection exists in the code; the decision is human, named and reasoned |
| Transparency and explanation (AI Act Art. 13 and 86) | Each skill cites the exact evidence; the candidate can obtain the explanation of their score |
| Logging (AI Act Art. 12) | Append-only audit log, chained and sealed: any modification is detected |
| Human oversight (AI Act Art. 14) | Indicative ranking, visible alerts, traced decisions |
| Minimisation and protection by design (GDPR Art. 5 and 25) | Anonymisation on intake, encrypted identity, local analysis by default |
| Right to erasure (GDPR Art. 17) | One-click erasure; the log stays intact but is no longer linked to the person |

**What remains your responsibility**: the impact assessment (DPIA), informing candidates and staff
representatives, the choice of any AI provider, and training recruiters in the proper use of the
score. Details: [COMPLIANCE.md](../COMPLIANCE.md).

## 10. What the tool does not do (yet)

We would rather tell you:

- **It replaces neither the interview nor your judgement.** It prepares both.
- **The anonymisation measurements come from synthetic corpora**, not yet from a large set of real
  CVs.
- **It does not read everything**: profiles with no written or visual trace of their work get a
  "limited" evidence level. That is an invitation to ask for examples, not a verdict.
- **The recruiter edition is an MVP**: SQLite database, one access key per instance, no multi-user
  login yet and no native integration with your ATS (both planned in the
  [roadmap](../ROADMAP.md)).
- **The skill-detection rules** need to be reviewed with practitioners of each trade before large-scale
  use.

## 11. Your objections, our answers

**"I don't have time to install a new tool."**
The public trial needs no installation and no account: two minutes with one of your job ads. The
recruiter edition installs with a single command on a server.

**"Degrees matter for our roles."**
They matter here too: list the ones that are important to you, and they weigh up to 25% of the score.
What the tool prevents is a degree **with no achievements at all** getting ahead of a person who has
proved themselves.

**"What if the candidate lies or copies a project?"**
Claims without evidence earn nothing. Repetitive, inflated CVs are penalised. And the interview guide
is designed precisely to check that the person is the author of what they present.

**"Our candidates don't have a GitHub."**
GitHub is only one source among others: campaign reports, case studies, site descriptions, photos of
finished work, technical sheets. The catalogue also covers marketing, sales, craft, cooking, sewing
and management.

**"Will the AI discriminate?"**
The tool removes sensitive information **before** any analysis, measures its own masking by name
origin, and checks with a test that the same work gets the same score whatever the identity.
Commercial AI, if you enable it, sees neither the weighting criteria nor the degrees, and its
influence is bounded to a band around the evidence-based estimate.

**"What happens to candidates' data?"**
In the public trial: nothing is kept. In the recruiter edition: it stays on your server, the identity
is encrypted, and erasure is immediate on request.

**"How much does it cost?"**
The software is free and open. Local analysis costs nothing. Deepening with a commercial AI is
optional, capped per job ad ($5 by default), and applies only to the best files.

**"Does it replace my ATS?"**
No: it sits alongside it. You keep publishing and managing the process in your ATS; TalentEngine-AI
assesses the evidence and helps you choose whom to meet.

## 12. Proposal: a 30-day pilot

To form your own view, we suggest a simple pilot, on **one real job ad**:

| Week | Action | What you measure |
|---|---|---|
| 1 | Configure the role with the manager in the studio (30 min); test with 3 CVs you know | Does the ranking match your intuition on profiles you know? |
| 2 | Evaluate in parallel with your usual process | How many profiles shortlisted by TalentEngine-AI would your usual filter have ruled out? |
| 3 | Run 3 to 5 interviews with the generated guide | Did the questions help verify expertise? How much preparation time was saved? |
| 4 | Review with the manager and the DPO | Quality of the profiles met, diversity of backgrounds, reading comfort, compliance questions |

At the end, you will have **your** figures, on **your** job ads. That is the only measure that counts.

---

**Try it now:** https://hivey.be/talentengine/essai ·
**Source code:** https://github.com/FlorianMartins/talentengine-ai ·
**Questions and demonstration:** https://github.com/FlorianMartins/talentengine-ai/issues
