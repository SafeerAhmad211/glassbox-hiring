# glassbox-hiring

**Open, auditable implementations of the algorithms behind ATS resume screening and gamified hiring assessment.**

[![tests](https://github.com/SafeerAhmad211/glassbox-hiring/actions/workflows/ci.yml/badge.svg)](https://github.com/SafeerAhmad211/glassbox-hiring/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Algorithmic hiring is opaque in a specific, fixable way: the *methods* are largely public
— in granted patents, in one unusually good peer-reviewed audit, and in fifty years of
psychometric literature — while the *implementations* are proprietary. This project reads
the public record and builds what it describes, in the open.

Start with **[research/TEARDOWN.md](research/TEARDOWN.md)**, the methodology teardown the
code is grounded in. Every claim there is tagged by evidence type, and nothing came from
reverse-engineering a proprietary application.

```bash
pip install glassbox-hiring
```

The audit core has **zero dependencies**. That is deliberate: its predecessor
([`pymetrics/audit-ai`](https://github.com/pymetrics/audit-ai), MIT) has been
unmaintained since July 2020, and it died of dependency rot rather than incorrect
statistics. An audit run today should reproduce in ten years.

---

## The gap this fills

`gh search repos "adverse impact EEOC python"` returns nothing maintained. For a legal
standard in force since 1978, governing every employment selection procedure in the
United States, there is no living Python implementation. Meanwhile NYC Local Law 144
requires annual published bias audits, Illinois HB 3773 took effect in January 2026, and
the EU AI Act classifies employment AI as high-risk.

## Four surfaces, one core

| Surface | Module | What it does |
|---|---|---|
| **Audit** | `glassbox.audit` | Four-fifths analysis, significance testing, threshold sweeps, counterfactual perturbation, LL144 report generation |
| **Engine** | `glassbox.score`, `glassbox.psych`, `games/` | Transparent rubric scoring; published task paradigms with citations; reliability and norming |
| **Lens** | `glassbox.parse` | What a screener actually extracts from a resume, and what it silently loses |
| **Atlas** | `glassbox.atlas` | Structured vendor/regulation dataset with per-field provenance |

---

## Quick start

### Is this screener producing adverse impact?

```bash
glassbox audit selections.csv --category race/ethnicity
```

```
[FINDING] Adverse impact indicated: Black or African American at impact ratio 0.500 (below 0.80).

  → Black or African American would need 24 additional selections to reach 0.80.
  → Call sweep_thresholds to see whether a different cut score avoids this.
  → Under 29 CFR 1607.14, a procedure with adverse impact requires validity evidence.
```

Exit codes are CI-friendly: `0` clean, `1` finding, `2` error. A bias audit can fail a
pipeline.

### The threshold problem

The single most under-reported fact in adverse-impact testing: **the impact ratio depends
on the cut score.**

```bash
glassbox sweep scores.csv
```

```
  pct    threshold   min IR  sel rate         worst
----------------------------------------------------------
   10       0.3640    0.892     0.902  PASS
   20       0.4255    0.788     0.802  FAIL   Group B
   50       0.5626    0.468     0.502  FAIL   Group B
   90       0.7602    0.109     0.102  FAIL   Group B
```

The same model and the same data. A vendor reporting "we pass the four-fifths rule" while
quietly testing at a 10% cut is telling the literal truth. The FAccT audit of pymetrics
found exactly this structure: fairness optimised at the 70th percentile, tiers deployed at
both the 50th and the 70th.

**An impact ratio without its threshold is not reportable.**

### Auditing a screener with no demographic data

Most people who want to audit a screener cannot get demographic labels. HireVue's patent
(US 2019/0057356 A1) describes building a "digital fingerprint" of a protected attribute
and projecting it onto unaffected candidates to measure the effect. Inverted for text,
that needs no protected data at all:

```python
from glassbox.audit.perturb import run_perturbation_audit

report = run_perturbation_audit(resumes, my_screener.score)

print(report.is_invariant)          # False
print(report.dimension_spread())    # {'name': 0.23, 'pronoun': 0.04}
```

Swapping only the candidate's name moved the mean score by 0.23. Nothing else changed.

### What the ATS actually sees

```bash
glassbox lens resume.pdf --show-text
```

```
  [CRITICAL] Contact details (email address) are in the page header/footer
             fix: Move your name, email, and phone into the main body of the first page.

  [HIGH    ] Multi-column layout detected (2 columns)
             fix: Use a single-column layout.
```

Every finding is deterministic geometry — no model, no invented "ATS score". You can
verify each one yourself.

### A publishable LL144 audit

```bash
glassbox ll144 --tool-name ScreenBot --auditor "Audit Co." \
  --data-source "2025 applicant data" \
  --sex sex.csv --race race.csv --intersectional intersectional.csv \
  --selection-threshold "score >= 70th percentile" --out audit.md
```

The intersectional breakdown is the LL144 requirement most often missed, and it is where
disparity hides:

| Category | Selection rate | Impact ratio | Below 4/5? |
|---|---:|---:|:---:|
| Sex — Female | 0.500 | 1.000 | no |
| Race — Black or African American | 0.500 | 1.000 | no |
| **Female / Black or African American** | **0.200** | **0.250** | **YES** |

Both marginals are perfect. The intersection is at a quarter.

---

## For agents

A typed tool surface with uniform observations — `status`, `summary`, `data`,
`next_actions`, `artifacts`:

```python
from glassbox.agent import call

obs = call("audit_selection_rates", outcomes={"White": [80, 100], "Black": [40, 100]})
obs.status        # "warning" — a finding is not a failed call
obs.next_actions  # concrete follow-ups
```

`glassbox tools` lists the surface. `warning` is distinct from `error` on purpose:
collapsing them teaches an agent to retry when it should be reporting.

---

## The assessment engine

The 12 tasks in a commercial gamified battery map onto paradigms published decades ago:

| Task | Paradigm | Citation |
|---|---|---|
| Balloons | Balloon Analogue Risk Task | Lejuez et al. 2002 |
| Cards | Iowa Gambling Task | Bechara et al. 1994 |
| Money Exchange | Trust/investment game | Berg, Dickhaut & McCabe 1995 |
| Stop | Stop-signal task | Logan & Cowan 1984 |
| Arrows | Eriksen flanker | Eriksen & Eriksen 1974 |
| Towers | Tower of London | Shallice 1982 |

`glassbox.psych.tasks` implements the **canonical scoring rules from the source papers**.
`games/bart.html` is a complete, dependency-free browser implementation — including the
detail most implementations get wrong (burst points drawn *without replacement*, giving
the uniform hazard the paradigm specifies).

The module also implements the number vendor materials tend to omit:

```python
from glassbox.psych import max_validity

max_validity(0.60)         # 0.775 — ceiling on any validity claim at this reliability
max_validity(0.80, 0.52)   # 0.645 — with a realistically noisy performance criterion
```

### What this project deliberately does not build

1. **A pretrained "good employee" model.** The pymetrics pipeline is reproducible, but
   its label — "resembles our current top 60 employees" — is a homogeneity engine. We
   ship the machinery and the audit gate, not the artefact.
2. **Anything that defeats a live assessment.** Reaction-time distributions are trivially
   fakeable, which is an argument these instruments carry less signal than claimed. That
   argument belongs in a validity report, not a cheating tool.

---

## Documentation

- **[research/TEARDOWN.md](research/TEARDOWN.md)** — how these systems work, with citations
- **[data/vendors.json](data/vendors.json)** — vendor and regulation atlas
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — evidence standards for contributions

## Regulatory status (verified 2026-08-14)

| Regime | Status |
|---|---|
| EEOC UGESP (29 CFR 1607) | In force since 1978 |
| NYC Local Law 144 | In force; annual independent bias audit, public posting |
| Illinois HB 3773 | Effective 2026-01-01; notice required |
| Colorado | ⚠️ SB 24-205 **repealed before taking effect**; SB 26-189 effective 2027-01-01 |
| EU AI Act (Annex III) | Deferred to **2027-12-02** by the Digital Omnibus |

Many published compliance guides still encode the superseded Colorado obligations and the
original EU deadline. `glassbox atlas --regulations` prints current status.

## Limitations

- The audit module computes **outcomes**, not validity. Validity under 29 CFR 1607.14 is a
  separate obligation requiring a job analysis.
- Running this code **does not make an audit independent** within the meaning of LL144.
- Perturbation testing and adverse-impact testing measure different things. A screener can
  pass one and fail the other. Run both.
- **Not legal advice.**

## Contributing

Contributions welcome, especially additional task paradigms, parser behaviour measured
against real systems, and jurisdiction coverage. The evidence standard in
[CONTRIBUTING.md](CONTRIBUTING.md) is strict: claims about vendors need a citation and a
provenance tag, and "a blog post said so" is tagged as such.

## License

MIT. Built on the shoulders of [`pymetrics/audit-ai`](https://github.com/pymetrics/audit-ai)
(MIT), whose authors open-sourced their adverse-impact framework and submitted to a
cooperative academic audit. That was a genuinely good act, and this project exists partly
because nobody picked the work back up.
