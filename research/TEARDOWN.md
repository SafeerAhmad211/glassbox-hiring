# How Algorithmic Hiring Systems Actually Work

A methodology teardown of ATS resume screening and gamified assessment, reconstructed
from public evidence: granted patents, peer-reviewed audits, vendor technical
documentation, and regulatory filings.

**Evidence discipline.** Every claim below is tagged:

- `[PATENT]` — from a granted patent or published application (public record, and the
  most technically detailed source available)
- `[AUDIT]` — from a peer-reviewed academic audit with source-code access
- `[VENDOR]` — vendor's own technical/marketing documentation (treat as claims, not facts)
- `[REG]` — statute, regulation, or regulator guidance
- `[INFERENCE]` — our reasoning from the above, labelled as such

No claim here comes from reverse-engineering a proprietary application, scraping a
logged-in vendor surface, or any private source. Where we could not verify something,
it says so.

Last verified: 2026-08-14.

---

## 1. The two-stage funnel

Nearly every large-employer pipeline is two distinct systems that vendors market as one:

```
                  STAGE 1: SCREENING                    STAGE 2: ASSESSMENT
         ┌────────────────────────────────┐    ┌────────────────────────────────┐
resume → │ parse → structure → match/rank │ →  │ behavioural tasks → features → │ → tier
         │  (deterministic + IR/ML)       │    │ ML model → percentile → tier   │
         └────────────────────────────────┘    └────────────────────────────────┘
              Workday, Taleo, iCIMS,               pymetrics/Harver, Arctic Shores,
              Greenhouse, Lever, SAP               HireVue, Cognify, SHL, Sapia
```

The two stages fail in completely different ways, which matters for anyone auditing them:

- **Stage 1 failures are mostly mechanical.** A candidate is rejected because a PDF's
  two-column layout serialised into interleaved garbage, not because a model judged them.
  This is a *parsing* bug wearing the costume of a hiring decision.
- **Stage 2 failures are statistical.** A candidate is rejected because a model trained on
  50–100 incumbent employees decided their reaction-time distribution didn't match. This is
  where adverse impact and validity questions actually live.

Conflating them is the single most common error in public commentary about "AI hiring."

---

## 2. Stage 1: resume screening

### 2.1 What the parser actually does

Resume parsing is a document-layout problem, not an NLP problem. The pipeline is:

```
PDF/DOCX → text + geometry extraction → reading-order reconstruction
        → section segmentation → field extraction → entity normalisation
```

Reading-order reconstruction is where it breaks. A PDF stores positioned glyph runs, not
paragraphs. Naive extraction emits runs in content-stream order, which for a two-column
layout interleaves the columns:

```
What you designed:                What a naive parser emits:
┌──────────────┬──────────────┐
│ EXPERIENCE   │ SKILLS       │   EXPERIENCE
│ Acme Corp    │ Python       │   SKILLS
│ 2020–2024    │ Postgres     │   Acme Corp
│ Built X      │ Docker       │   Python
└──────────────┴──────────────┘   2020–2024
                                  Postgres
                                  ...
```

`[VENDOR]`/`[INFERENCE]` Documented behavioural differences between major systems, which
are consistent with different reading-order strategies:

| System | Reported failure mode | Implied strategy |
|---|---|---|
| Taleo | Scrambles table cells into unpredictable order; Unicode/symbol failures | Content-stream order, minimal geometry use |
| Workday | Merges same-row cell contents into one string | Row-major geometric grouping without column detection |
| Greenhouse | Handles simple tables; fails on nested/complex | Some column detection, no recursion |

`[VENDOR]` Content in PDF **headers and footers** is frequently not extracted at all —
which silently deletes contact information for candidates who put their name and email
there. Reported figures put >40% of resumes as containing at least one element that
causes a parse error; treat that specific number as a vendor-adjacent claim, not a
measured fact, since we found no primary study behind it.

**Design consequence for us:** parseability is measurable and deterministic. You can tell a
candidate *exactly* what a geometry-naive parser loses from their document, with no model
and no guessing. That is the honest core of a candidate-facing tool — and it is the part
that actually changes outcomes.

### 2.2 What the matcher does

`[INFERENCE]` Public documentation is thin here, but the observable behaviour across
systems is consistent with a small number of well-known techniques:

1. **Boolean/keyword requirement filters** — recruiter-authored, hard pass/fail. Still the
   dominant mechanism at most employers, and entirely non-ML.
2. **Lexical relevance ranking** — BM25/TF-IDF over the JD as query, resume as document.
3. **Embedding similarity** — bi-encoder cosine between JD and resume vectors, increasingly
   with an LLM reranker on top since 2024–25.
4. **Learned ranking on historical outcomes** — the genuinely dangerous one, because the
   training label is "who we hired before," which encodes prior human bias directly.

The failure mode of (4) is well understood in the literature and needs no reverse
engineering to predict: a model trained to reproduce historical hiring decisions
reproduces historical hiring patterns, including the illegal ones.

---

## 3. Stage 2: gamified assessment

This is where the real methodology is, and where public evidence is unusually good —
because one vendor submitted to a cooperative academic audit and another patented its
approach in detail.

### 3.1 The published-paradigm layer

`[VENDOR]`/`[INFERENCE]` The pymetrics battery is 12 tasks. Each maps onto a
long-published experimental paradigm from the cognitive/behavioural-economics literature:

| Game name | Established paradigm | Canonical citation | Construct |
|---|---|---|---|
| Balloons | Balloon Analogue Risk Task (BART) | Lejuez et al., 2002 | Risk taking under uncertainty |
| Cards | Iowa Gambling Task | Bechara et al., 1994 | Decision under ambiguous reward |
| Money Exchange 1 | Trust/investment game | Berg, Dickhaut & McCabe, 1995 | Trust, reciprocity |
| Money Exchange 2 | Trust game, trustee role | Berg et al., 1995 | Fairness, altruism |
| Digits | Digit span | Wechsler / Jacobs 1887 lineage | Working memory capacity |
| Stop | Stop-signal task | Logan & Cowan, 1984 | Inhibitory control (SSRT) |
| Arrows | Eriksen flanker / ANT | Eriksen & Eriksen, 1974; Fan et al., 2002 | Selective attention, conflict |
| Towers | Tower of London | Shallice, 1982 | Planning, look-ahead depth |
| Easy or Hard | EEfRT | Treadway et al., 2009 | Effort–reward allocation |
| Keypresses | Motor speed / tapping | Long lineage | Processing & motor speed |
| Lengths | Perceptual discrimination | Psychophysics lineage | Attention to detail |
| Faces | Emotion recognition | Ekman lineage; RMET (Baron-Cohen 2001) | Emotion perception |

**This is the most important finding in this document.** The scientific substrate of
commercial gamified assessment is public, decades old, and thoroughly validated in the
open literature. The proprietary layer is only:

1. the specific art, UI, and copy,
2. the normative database (millions of players), and
3. the client-specific supervised model on top.

An open implementation therefore does not need to clone anything proprietary. It needs to
implement the *published paradigms* correctly and cite them — which is strictly better
science, because the paradigm's psychometric properties are documented in peer review
rather than asserted in a marketing page.

**Note on "34 traits" / "12,000 data points" / "90+ traits" claims.** `[VENDOR]` These
numbers appear in vendor and test-prep marketing. They are not independently verified, and
a raw count of recorded telemetry events is not a count of measured constructs. Treat them
as marketing arithmetic. A task yielding 12,000 keystroke timestamps still measures however
many latent factors it measures — typically a handful.

### 3.2 The scoring model: pymetrics, as audited

`[AUDIT]` Wilson, Ghosh, Jiang, Mislove, Wei, Wu, Liu et al., *Building and Auditing Fair
Algorithms: A Case Study in Candidate Screening*, ACM FAccT 2021. This is a cooperative
audit **with source-code access** — the highest-quality public evidence that exists on any
commercial hiring algorithm. Full text: `research/raw/pymetrics-facct-2021.txt`.

**Three-dataset construction:**

| Dataset | Contents | Typical size | Role |
|---|---|---|---|
| **in group** | Gameplay of high-performing incumbents at the client, identified by job analysis | **50–100 players** | Positive class |
| **out group** | Sampled from vendor database to approximate the applicant pool | — | Negative class |
| **bias group** | Players who volunteered EEOC demographic labels, engineered to be **balanced across protected groups** | **>10,000** | Held out; adverse-impact testing only |

The critical architectural decision: **demographics never enter training.** The bias group
is used exclusively to *evaluate* candidate models. Protected attributes are not features —
which is both a legal requirement and a real constraint on what mitigation is possible.

**Preprocessing, in order:**

1. Correct for platform differences (web vs. mobile elicit different behaviour).
2. Drop players with **more than two** missing games.
3. Clip feature outliers to psychometrically-derived acceptable bounds.
4. Impute remaining missing values with the **feature median**.
5. Z-score each feature (centre 0, unit variance).

**Model:** Support Vector Machine, **64 features** in the audited code. Trained on in-group
vs. out-group only. SVM is a defensible choice here precisely because the feature space is
small and known and the positive class is tiny (n=50–100) — this is a low-data regime where
a deep net would simply memorise 60 people.

**Fairness search — the actual mechanism:**

> "pymetrics conducts a search for the most predictive, least biased permutation of
> features. Fairness is measured by applying the predictive models to the bias group data,
> and comparing performance of the demographic subgroups."

So: enumerate feature subsets → train a model per subset → score the bias group → compute
impact ratio per demographic group → keep subsets that pass, rank by predictive
performance. It is **feature-subset selection under a fairness constraint**, not
post-hoc score adjustment. `[AUDIT]` The auditors note this could be construed as a form of
direct fairness intervention, and that the choice to operationalise fairness *as* the
four-fifths rule is itself a consequential design decision, not a neutral one.

**Tiering and thresholds:**

| Tier | Score percentile |
|---|---|
| Highly Recommended | ≥ 70th |
| Recommended | 50th – 70th |
| Not Recommended | < 50th |

The fairness search evaluates IR at the **70th** percentile; final models are tested at
**both 50th and 70th**. This matters enormously and is under-appreciated: **the impact ratio
is a function of the threshold.** A model can pass at one cut score and fail at another.
Any audit that reports a single IR without naming its threshold is not reportable.

`[AUDIT]` The auditors' verdict: the code did faithfully implement the stated four-fifths
guarantee via minimum bias ratio, with adequate safeguards against error and manipulation.
The limitation they flag is not implementation fidelity but the framing — passing the
four-fifths rule is a floor, not evidence of a good or valid selection procedure.

### 3.3 The scoring model: HireVue, as patented

`[PATENT]` US 2019/0057356 A1, *Detecting disability and ensuring fairness in automated
scoring of video interviews* (HireVue). Patents are public record and often disclose more
math than any marketing page.

**Features:** facial/visual action units (e.g. mouth-corner raise magnitude, blink rate),
audio (voice inflection, stuttering, accent), lexical (word choice, grammatical structure),
and temporal (response latency, pause and silence structure).

**Architecture:** CNNs over audio/video; also describes autoencoder and GAN variants
(a deconvolutional generator conditioned on a disability label, against a discriminator).

**Class-normalised loss.** Instead of plain sum-of-squared errors, the patent specifies
per-class normalisation so no demographic group dominates the objective by sheer count:

$$\mathrm{SSE}_{\text{corrected}} = \sum_{i=1}^{A}\frac{e_i^2}{A} + \sum_{i=1}^{B}\frac{e_i^2}{B} + \sum_{i=1}^{C}\frac{e_i^2}{C}$$

This is group-balanced empirical risk minimisation, and it is a genuinely reusable idea —
independent of anything else in the patent.

**"Digital fingerprinting" of a protected attribute.** The distinctive contribution:

1. Split candidates into group A (has attribute) and group B (does not).
2. Extract features correlating with the attribute.
3. Build a **fingerprint** — the median pairwise-difference vector between clustered
   groups, or a PDF-matching function interpolated piecewise over the data.
4. **Project the fingerprint onto non-affected candidates' data** and measure the effect on
   their job-performance score. This synthesises the counterfactual: *what does this model
   do to someone who merely presents these features?*
5. **Iteratively ablate** the offending features until adverse impact is mitigated.
6. Fold a four-fifths penalty term directly into the objective: if any class's rate falls
   below 80% of the top class's rate, add a penalty.

`[INFERENCE]` Steps 3–4 are the technically interesting part and are directly portable to
resume screening, where the analogous move is far cheaper: rather than fingerprinting
audio-visual features, perturb a *name*, a *school*, a *pronoun*, or a *gap* on an
otherwise identical resume and measure the score delta. Same counterfactual logic, no
demographic labels required, no protected attribute ever collected. **This is the design
basis for our perturbation harness** (`glassbox.audit.perturb`).

**Context that belongs next to the patent:** `[VENDOR]` HireVue discontinued facial
analysis in 2021 after sustained criticism. The patent describes a system partly abandoned
in practice. We cite it for its *methods*, which remain sound and reusable, not as a
description of a currently shipping product.

---

## 4. The regulatory layer

`[REG]` This is what makes an audit toolkit compliance-relevant rather than academic. Dates
verified 2026-08-14 — several widely-circulated compliance guides still encode superseded
deadlines.

| Regime | Status as of 2026-08-14 | Core obligation |
|---|---|---|
| **EEOC UGESP** (29 CFR 1607) | In force since 1978 | Four-fifths rule as the screening standard for adverse impact; validity required for procedures that do have impact |
| **NYC Local Law 144** | In force | Annual **independent** bias audit of AEDTs; public posting of impact ratios; candidate notice. Penalties to $1,500/day. Categories <2% of data may be excluded |
| **Illinois HB 3773** | **Effective 2026-01-01** | Amends Human Rights Act; bars discriminatory AI in employment decisions; **notice required**. No impact assessment mandated |
| **Colorado** | ⚠️ **SB 24-205 repealed before taking effect** by SB 26-189 (signed 2026-05-14), replacement effective **2027-01-01** | Replacement requires disclosure + human review. The risk-management programmes, annual impact assessments, and duty of care are **gone** |
| **EU AI Act** | Annex III high-risk deadline **deferred to 2027-12-02** by Digital Omnibus (in force 2026-07-27), from 2026-08-02 | Employment AI is high-risk: risk management, data governance, logging, human oversight, conformity assessment |
| **California FEHA regs** | Finalised 2025–26 | Automated-decision-system discrimination rules under state employment law |

### 4.1 The four-fifths rule, precisely

`[REG]` 29 CFR 1607.4(D). For each group, selection rate $r_g = s_g / n_g$. Impact ratio
against the highest-selecting group:

$$\mathrm{IR}_g = \frac{r_g}{\max_h r_h}, \qquad \text{flag if } \mathrm{IR}_g < 0.8$$

Three qualifications that most implementations get wrong, stated in the regulation itself:

1. **Small numbers cut both ways.** Large rate differences may *not* be adverse impact when
   based on small numbers and not statistically significant. So an IR must be reported
   alongside a significance test and the group sizes — never alone.
2. **Passing 0.8 is not safety.** Smaller differences *can* constitute adverse impact when
   significant in both statistical and practical terms.
3. **Validity is a separate obligation.** §1607.14 sets technical standards for validity
   studies, with criterion-related validity requiring significance at $p \le 0.05$.

`[INFERENCE]` The regulation does not name a specific statistical test. Practice uses
Fisher's exact test for small cells and the two-proportion Z-test at larger n; we implement
both and report both, because picking one silently is how you get an audit that says
whatever the author wanted.

---

## 5. What this implies for an open implementation

Reading the patents and the audit together, the defensible design is not a clone of any
vendor. It is:

| Subsystem | Grounded in | Why open beats proprietary here |
|---|---|---|
| Adverse-impact testing | UGESP + FAccT audit method | **The void.** `audit-ai` (pymetrics' own, MIT) has been unmaintained since 2020-07-29. No maintained Python library implements UGESP/LL144 reporting |
| Perturbation testing | HireVue fingerprinting patent, inverted | Needs no demographic data at all — anyone can run it on any screener |
| Task battery | Published paradigms + citations | Peer-reviewed psychometrics beats asserted psychometrics |
| Scoring | pymetrics' documented pipeline | Same math, but every weight inspectable |
| Parseability | Deterministic geometry analysis | No model needed; fully explainable to a candidate |

Two things we deliberately do **not** build:

1. **A behavioural model trained on incumbent "high performers."** The pymetrics pipeline is
   reproducible, but the *label* is the problem: "resembles our current top 60 employees"
   is a homogeneity engine. We ship the scoring machinery and the audit gate; we do not
   ship a pretrained "good employee" model, because there is no such artefact that is
   valid across contexts.
2. **Anything that defeats a live assessment.** The task implementations are for research,
   validation, and self-hosted assessment. Reaction-time distributions are trivially
   fakeable, which is itself an argument these instruments carry less signal than claimed —
   an argument better made in a validity report than in a cheating tool.

---

## 6. Primary sources

**Patents**
- US 2019/0057356 A1 — HireVue, disability detection & fairness in automated video scoring —
  https://patents.google.com/patent/US20190057356A1/en

**Peer-reviewed**
- Wilson et al. (2021), *Building and Auditing Fair Algorithms: A Case Study in Candidate
  Screening*, ACM FAccT — https://doi.org/10.1145/3442188.3445928 ·
  [PDF](https://www.ccs.neu.edu/home/amislove/publications/Pymetrics-FAccT.pdf)
- Sánchez-Monedero, Dencik & Edwards (2019), *What does it mean to solve the problem of
  discrimination in hiring?* — https://arxiv.org/pdf/1910.06144

**Task paradigms**
- Lejuez et al. (2002), BART, *J. Exp. Psychol. Appl.* 8(2)
- Bechara et al. (1994), Iowa Gambling Task, *Cognition* 50
- Berg, Dickhaut & McCabe (1995), trust game, *Games & Econ. Behavior* 10
- Logan & Cowan (1984), stop-signal, *Psychol. Review* 91
- Eriksen & Eriksen (1974), flanker, *Perception & Psychophysics* 16
- Shallice (1982), Tower of London, *Phil. Trans. R. Soc. B* 298
- Treadway et al. (2009), EEfRT, *PLoS ONE* 4(8)
- Fan et al. (2002), Attention Network Test, *J. Cog. Neuroscience* 14

**Regulation**
- 29 CFR Part 1607 UGESP — https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XIV/part-1607
- 29 CFR 1607.4 (impact) — https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XIV/part-1607/subject-group-ECFRdb347e844acdea6/section-1607.4
- NYC AEDT rules — https://rules.cityofnewyork.us/rule/automated-employment-decision-tools-2/

**Prior-art code**
- `pymetrics/audit-ai` — MIT, 322★, last push 2020-07-29 (unmaintained)
- `fairlearn/fairlearn` — MIT, active
- `jspsych/jsPsych` — MIT, active
- `eribean/girth` — MIT, IRT, last push 2022-09-09
