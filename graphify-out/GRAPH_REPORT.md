# Graph Report - glassbox-hiring  (2026-08-15)

## Corpus Check
- Corpus is ~36,650 words - fits in a single context window. You may not need a graph.

## Summary
- 867 nodes · 1566 edges · 66 communities (60 shown, 6 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 110 edges (avg confidence: 0.58)
- Token cost: 89,430 input · 4,200 output

## Community Hubs (Navigation)
- Transparent Rubric Scoring
- PDF and DOCX Extraction
- LL144 Report Generation
- Parseability Diagnostics
- Vendor Atlas Loading
- Command Line Interface
- Atlas Refresh Crawler
- Perturbation Auditing
- Agent Tool Surface
- Agent Tool Surface (2)
- Methodology Teardown
- LL144 Report Generation (2)
- Reading Order Reconstruction
- Adverse Impact Analysis
- Statistical Primitives
- Reliability and Norming
- Parsing Tests
- Parseability Diagnostics (2)
- Adverse Impact Analysis (2)
- Command Line Interface (2)
- Task Paradigm Scoring
- External: data
- Vendor Atlas Loading (2)
- Adverse Impact Analysis (3)
- Adverse Impact Analysis (4)
- Perturbation Auditing (2)
- Impact Tests
- Adverse Impact Analysis (5)
- Statistical Primitives (2)
- Statistical Primitives (3)
- Reading Order Reconstruction (2)
- Reliability and Norming (2)
- Task Paradigm Scoring (2)
- Parsing Tests (2)
- Perturbation Auditing (3)
- Perturbation Auditing (4)
- Perturbation Auditing (5)
- Statistical Primitives (4)
- Reading Order Reconstruction (3)
- Agent Tests
- Reliability and Norming (3)
- Task Paradigm Scoring (3)
- Task Paradigm Scoring (4)
- Task Paradigm Scoring (5)
- Task Paradigm Scoring (6)
- Perturbation Auditing (6)
- Reliability and Norming (4)
- Reliability and Norming (5)
- Reliability and Norming (6)
- Adverse Impact Analysis (6)
- Perturbation Auditing (7)
- Statistical Primitives (5)
- Impact Tests (2)
- BART Browser Task
- Impact Tests (3)
- Parsing Tests (3)
- Project Framing
- Methodology Teardown (2)
- Impact Tests (4)
- Methodology Teardown (3)
- Source Fetching Policy
- Contribution Standards
- CI and Automation
- External: src
- External: pkg

## God Nodes (most connected - your core abstractions)
1. `TextBlock` - 50 edges
2. `diagnose()` - 41 edges
3. `adverse_impact()` - 33 edges
4. `score_resume()` - 33 edges
5. `call()` - 27 edges
6. `GroupOutcome` - 27 edges
7. `Rubric` - 27 edges
8. `Requirement` - 25 edges
9. `BartTrial` - 23 edges
10. `run_perturbation_audit()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `TestDegenerateCases` --uses--> `GroupOutcome`  [INFERRED]
  tests/test_audit_impact.py → src/glassbox/audit/impact.py
- `TestExclusions` --uses--> `GroupOutcome`  [INFERRED]
  tests/test_audit_impact.py → src/glassbox/audit/impact.py
- `TestImpactRatioCurve` --uses--> `GroupOutcome`  [INFERRED]
  tests/test_audit_impact.py → src/glassbox/audit/impact.py
- `TestOutcomesFromScores` --uses--> `GroupOutcome`  [INFERRED]
  tests/test_audit_impact.py → src/glassbox/audit/impact.py
- `TestPassingCase` --uses--> `GroupOutcome`  [INFERRED]
  tests/test_audit_impact.py → src/glassbox/audit/impact.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Adverse-Impact Legal Framework** — research_teardown_four_fifths_rule, research_teardown_small_numbers_qualification, research_teardown_passing_is_not_clearance, research_teardown_threshold_dependence, research_teardown_nyc_ll144 [EXTRACTED 1.00]
- **HireVue Patent Fairness Mechanism** — research_teardown_hirevue_patent, research_teardown_class_normalised_loss, research_teardown_digital_fingerprinting, research_teardown_iterative_feature_ablation [EXTRACTED 1.00]
- **Project Integrity Commitments** — research_teardown_evidence_tagging, contributing_no_cheating_tools, research_teardown_no_incumbent_model, research_fetch_sources_no_redistribution, contributing_license_compatibility [INFERRED 0.85]

## Communities (66 total, 6 thin omitted)

### Community 0 - "Transparent Rubric Scoring"
Cohesion: 0.05
Nodes (37): Transparent, fully-attributable resume scoring., Evidence, _find_evidence(), MatchResult, _normalise(), Transparent rubric-based resume/JD matching. Design constraint: **every point…, A hard requirement with no supporting evidence., Complete, attributable match outcome. (+29 more)

### Community 1 - "PDF and DOCX Extraction"
Cohesion: 0.07
Nodes (29): build_pdf(), Generate small PDFs with text at known positions, for testing and demos. Writes…, Build a one-page PDF placing each string at an absolute position. Args: items:…, A two-column resume emitted row-by-row across both columns. This is the failure…, A clean single-column resume that parses correctly everywhere., single_column_resume(), two_column_resume(), extract_blocks() (+21 more)

### Community 2 - "LL144 Report Generation"
Cohesion: 0.09
Nodes (11): date, build_bias_audit(), Assemble a bias audit from selection counts. Args: tool_name: Name of the AEDT.…, Render a bias audit as a publishable markdown summary. Structured to cover each…, render_markdown(), fixture, Tests for LL144 bias-audit report generation., The case LL144's intersectional requirement exists to catch. (+3 more)

### Community 3 - "Parseability Diagnostics"
Cohesion: 0.10
Nodes (20): Enum, Finding, _normalise(), ParseabilityReport, Parseability diagnostics: what a screener loses from a document. Every finding…, Findings ordered most severe first., Collapse whitespace so ordering differences are not masked by spacing., How much a finding is likely to cost the candidate. (+12 more)

### Community 4 - "Vendor Atlas Loading"
Cohesion: 0.13
Nodes (13): find_vendor(), load_atlas(), Any, The vendor and regulation atlas. A structured, citable dataset of ATS and…, Load and cache the full atlas. Returns: The parsed dataset with ``vendors`` and…, Return vendor records, optionally filtered by category. Args: category:…, Return regulation records., Look up one vendor by id. Args: vendor_id: The record's ``id`` field, e.g.… (+5 more)

### Community 5 - "Command Line Interface"
Cohesion: 0.19
Nodes (21): ArgumentParser, Namespace, Return name, description, and parameter names for each tool. Enough for an…, tool_schemas(), build_parser(), _cmd_atlas(), _cmd_audit(), _cmd_lens() (+13 more)

### Community 6 - "Atlas Refresh Crawler"
Cohesion: 0.13
Nodes (19): atlas_path(), Path, Locate ``data/vendors.json``. Checks the packaged copy first, then the…, fetch(), FetchResult, main(), merge_into_atlas(), Any (+11 more)

### Community 7 - "Perturbation Auditing"
Cohesion: 0.16
Nodes (10): Scorer, Perturbation, Score each resume before and after each perturbation. Args: resumes: Resume…, A single counterfactual edit. Args: name: Identifier, e.g.…, run_perturbation_audit(), A scorer keying only on job-relevant content must show zero delta., A scorer penalising specific names must be caught, with the right sign., The headline number: best- minus worst-treated variant within a dimension. (+2 more)

### Community 8 - "Agent Tool Surface"
Cohesion: 0.15
Nodes (7): Typed tool surface for agents driving glassbox., call(), Dispatch a tool by name. ``tool_name`` is positional-only. Several tools take a…, Tests for the agent tool surface, the atlas, and the CLI. The agent-surface…, A finding is not a failure. Collapsing them teaches an agent to retry., TestAgentTools, TestWarningVersusError

### Community 9 - "Agent Tool Surface (2)"
Cohesion: 0.16
Nodes (19): audit_scorer_invariance(), audit_selection_rates(), check_resume_parseability(), _error(), generate_ll144_report(), match_resume_to_rubric(), Observation, Any (+11 more)

### Community 10 - "Methodology Teardown"
Cohesion: 0.11
Nodes (19): Exact Arithmetic Where the Law Draws a Line, Refusal of Assessment-Defeating Contributions, Property Tests for Numerical Claims, Four Surfaces Over One Core, Intersectional Disparity Hiding Behind Clean Marginals, No Redistribution of Copyrighted Papers, Class-Normalised Objective Function, Digital Fingerprinting of a Protected Attribute (+11 more)

### Community 11 - "LL144 Report Generation (2)"
Cohesion: 0.13
Nodes (13): ImpactReport, Adverse-impact findings for one demographic category. ``threshold`` is…, Smallest impact ratio across non-reference groups (the "minimum bias ratio")., Whether every ratio clears 0.8. Named narrowly on purpose. This is *not* a…, BiasAudit, _format_ratio(), NYC Local Law 144 bias-audit report generation. Local Law 144 of 2021 requires…, All populated category reports. (+5 more)

### Community 12 - "Reading Order Reconstruction"
Cohesion: 0.19
Nodes (8): group_into_lines(), A positioned run of text. Args: text: The literal text. x: Left edge, in points…, Rendered width in points. Uses the measured ``width`` when the extractor…, Group blocks sharing a baseline into lines, each ordered left to right. Args:…, TextBlock, TestContactInHeader, single_column_blocks(), TestGroupIntoLines

### Community 13 - "Adverse Impact Analysis"
Cohesion: 0.16
Nodes (12): GroupImpact, Adverse-impact analysis under the EEOC Uniform Guidelines (29 CFR 1607).…, True when the impact ratio falls strictly below four-fifths. Uses exact…, Groups falling below four-fifths, worst first., Impact ratio at one cut score., Per-group findings. ``impact_ratio`` is ``None`` for the reference group.…, ThresholdPoint, Adverse-impact and fairness auditing for employment selection procedures. (+4 more)

### Community 14 - "Statistical Primitives"
Cohesion: 0.17
Nodes (8): fisher_exact_2x2(), Two-sided Fisher's exact test on a 2x2 contingency table. The table is laid out…, Fisher's original tea-tasting experiment: p = 0.4857142857... The canonical 2x2…, ``scipy.stats.fisher_exact([[8, 2], [1, 5]])`` gives p = 0.034965034965..., Swapping which group is focal must not change a two-sided p-value., A zero margin permits only one arrangement; p=1 is the honest answer., Float accumulation must not push the summed probability past 1.0., TestFisherExact

### Community 15 - "Reliability and Norming"
Cohesion: 0.15
Nodes (11): Psychometrics: published task-paradigm scoring, reliability, and norming., _pearson(), Reliability, norming, and validity ceilings. A gamified assessment that…, Standard error of measurement. .. math:: SEM = \\sigma \\sqrt{1 - r} The number…, Pearson correlation, or ``None`` when undefined., Split-half reliability, Spearman-Brown corrected to full-test length. Args:…, split_half_reliability(), standard_error_of_measurement() (+3 more)

### Community 16 - "Parsing Tests"
Cohesion: 0.16
Nodes (8): codes(), parametrize, Tests for parseability diagnostics., The word 'experience' inside a sentence must not count as a section., With no text layer, downstream findings are noise., TestMissingInformation, TestScannedDocument, TestSectionHeadings

### Community 17 - "Parseability Diagnostics (2)"
Cohesion: 0.23
Nodes (8): diagnose(), _find_recognised_sections(), Analyse a document's parseability. Args: blocks: Body text blocks with…, Return conventional section headings appearing as their own line., TestMultiColumn, TestReportOrdering, A two-column resume whose producer emitted rows across both columns. Left…, two_column_blocks()

### Community 18 - "Adverse Impact Analysis (2)"
Cohesion: 0.19
Nodes (7): adverse_impact(), Run a four-fifths analysis over one demographic category. Args: outcomes:…, IR == 0.8 exactly is not "less than four-fifths", so it does not flag., LL144 permits excluding categories under 2% of the data., Default min_share=0 keeps small groups: dropping them silently hides disparity., TestExclusions, TestPassingCase

### Community 19 - "Command Line Interface (2)"
Cohesion: 0.23
Nodes (5): _configure_stdout(), main(), Force UTF-8 on stdout where the platform default cannot encode our output., Entry point. Returns: 0 clean, 1 finding, 2 error., TestCli

### Community 20 - "Task Paradigm Scoring"
Cohesion: 0.29
Nodes (7): bart_score(), BartTrial, One balloon in the Balloon Analogue Risk Task. Args: pumps: Number of pumps the…, Score the Balloon Analogue Risk Task (Lejuez et al., 2002). The standard…, The defining feature of the standard measure., Cannot compute intended behaviour when every balloon was truncated., TestBart

### Community 21 - "External: data"
Cohesion: 0.15
Nodes (12): evidence_policy, levels, note, generated, inference, public, unknown, vendor (+4 more)

### Community 22 - "Vendor Atlas Loading (2)"
Cohesion: 0.15
Nodes (12): evidence_policy, levels, note, generated, inference, public, unknown, vendor (+4 more)

### Community 23 - "Adverse Impact Analysis (3)"
Cohesion: 0.23
Nodes (6): GroupOutcome, Highest-selecting group, per 1607.4(D). Ties break on larger n, then name., Observed selection counts for one demographic group. Args: name: Group label,…, Selection rate, or 0.0 for an empty group., _select_reference(), TestGroupOutcome

### Community 24 - "Adverse Impact Analysis (4)"
Cohesion: 0.24
Nodes (6): impact_ratio_curve(), Sweep the cut score and report the impact ratio at each one. The single most…, The threshold-dependence result from the FAccT pymetrics audit., The strongest form of threshold dependence: the *harmed group changes*. Group…, pymetrics searched for fairness at the 70th but deployed cuts at 50th too., TestImpactRatioCurve

### Community 25 - "Perturbation Auditing (2)"
Cohesion: 0.26
Nodes (5): pronoun_swap(), Rewrite third-person pronouns to ``target`` ('he', 'she', or 'they'). Case-…, his' inside 'history' must not be rewritten., Swapping to 'they' works whether the source used he/him or she/her., TestPronounSwap

### Community 26 - "Impact Tests"
Cohesion: 0.17
Nodes (4): fixture, The canonical EEOC example: 80 of 100 white, 40 of 100 Black applicants hired.…, To reach IR 0.8 against a 0.80 reference rate: 64 selections needed. 64 - 40 =…, TestUGESPWorkedExample

### Community 27 - "Adverse Impact Analysis (5)"
Cohesion: 0.27
Nodes (5): Standardized mean differences against a reference group. Threshold-free…, score_gap_report(), The point of this metric: no cut score is involved, so none can be gamed. A…, A single-observation group yields None, not a fake zero., TestScoreGapReport

### Community 28 - "Statistical Primitives (2)"
Cohesion: 0.27
Nodes (5): Two-sided two-proportion Z-test with pooled variance. Appropriate when both…, two_proportion_z(), Hand-computed: p1=0.4, p2=0.6, pooled=0.5, n=100 each. z = (0.4-0.6) /…, Nobody selected in either group: rates are identical, not disparate., TestTwoProportionZ

### Community 29 - "Statistical Primitives (3)"
Cohesion: 0.27
Nodes (5): Wilson score confidence interval for a proportion. Preferred over the normal-…, wilson_interval(), 40/100 at 95%: Wilson gives approximately (0.3094, 0.4979)., Where the Wald interval would escape [0, 1], Wilson must not., TestWilsonInterval

### Community 30 - "Reading Order Reconstruction (2)"
Cohesion: 0.27
Nodes (5): detect_columns(), Detect vertical columns by finding sustained horizontal gaps. Projects every…, Word spacing must not be read as a column boundary., A single indented block far right is not a column., TestDetectColumns

### Community 31 - "Reliability and Norming (2)"
Cohesion: 0.25
Nodes (5): percentile_rank(), Percentile rank of ``score`` within a norm sample. Uses the standard definition…, Standardise ``score`` against a norm sample. Args: score: The score to…, z_score(), TestNorming

### Community 32 - "Task Paradigm Scoring (2)"
Cohesion: 0.25
Nodes (5): flanker_score(), Scoring for published behavioural-task paradigms. Commercial gamified…, Score an Eriksen flanker task. The measure of interest is the **conflict…, Tests for task scoring and psychometric indices. Reference values are taken…, TestFlanker

### Community 33 - "Parsing Tests (2)"
Cohesion: 0.25
Nodes (5): good_resume_blocks(), A clean, single-column, fully parseable resume., LOW findings do not make a document unclean., TestCleanDocument, TestDocumentFeatures

### Community 34 - "Perturbation Auditing (3)"
Cohesion: 0.27
Nodes (5): affiliation_swap(), Counterfactual perturbation testing for resume screeners. Adverse-impact…, Replace an institution or organisation name. Probes proxy discrimination: a…, Tests for counterfactual perturbation auditing. The key tests use *deliberately…, TestAffiliationSwap

### Community 35 - "Perturbation Auditing (4)"
Cohesion: 0.29
Nodes (5): _default_perturbations(), name_swap(), Replace the candidate name with ``replacement``. Assumes the name is the first…, Name and pronoun probes covering the standard audit-study design., TestNameSwap

### Community 36 - "Perturbation Auditing (5)"
Cohesion: 0.20
Nodes (6): PerturbationResult, Effect of one perturbation across a corpus of resumes., Mean signed score change. Positive means the perturbation *raised* scores., Largest single-resume swing -- a mean near zero can hide large offsetting moves., How many resumes changed score at all., Standard deviation of deltas, or ``None`` with fewer than two resumes.

### Community 37 - "Statistical Primitives (4)"
Cohesion: 0.29
Nodes (5): Cohen's *d* between two score distributions, using pooled SD. Used for…, standardized_mean_difference(), Focal mean 2, reference mean 4, pooled SD 1.0 -> d = -2.0. Negative because the…, None, not 0.0 -- 'cannot compute' is a different finding from 'no difference'., TestStandardizedMeanDifference

### Community 38 - "Reading Order Reconstruction (3)"
Cohesion: 0.29
Nodes (5): column_aware_reading_order(), Serialise in human reading order: each column top-to-bottom, left to right.…, Left column fully, then right column -- as a human reads it., The point of the exercise: the employer stays with its dates., TestColumnAwareReadingOrder

### Community 39 - "Agent Tests"
Cohesion: 0.20
Nodes (4): parametrize, Every tool must return the same shape, whatever happens., Recovery route, not just a complaint., TestObservationContract

### Community 40 - "Reliability and Norming (3)"
Cohesion: 0.31
Nodes (5): max_validity(), Maximum possible correlation between a test and a criterion. .. math:: r_{max}…, Reliability 0.60 caps validity at sqrt(0.60) = 0.7746., The number vendors omit: a noisy criterion caps validity hard., TestMaxValidity

### Community 41 - "Task Paradigm Scoring (3)"
Cohesion: 0.33
Nodes (4): digit_span_score(), Score a digit-span task. Args: results: ``(span_length, correct)`` pairs in…, max_span rewards one lucky trial; reliable_span requires 2/3 correct., TestDigitSpan

### Community 42 - "Task Paradigm Scoring (4)"
Cohesion: 0.31
Nodes (5): Estimate stop-signal reaction time (SSRT) by the integration method. SSRT is…, stop_signal_rt(), Go RTs 100..1000 by 100, 50% inhibition, mean SSD 200. p(respond) = 0.5 ->…, Outside [0.1, 0.9] SSRT estimates are not trustworthy; return None., TestStopSignalRt

### Community 43 - "Task Paradigm Scoring (5)"
Cohesion: 0.33
Nodes (4): Score a Tower of London planning task. Args: problems: ``(moves_made,…, tower_of_london_score(), Longer first-move latency associated with fewer excess moves., TestTowerOfLondon

### Community 44 - "Task Paradigm Scoring (6)"
Cohesion: 0.36
Nodes (3): Score a trust (investment) game round. The investor sends some portion of an…, trust_game_score(), TestTrustGame

### Community 45 - "Perturbation Auditing (6)"
Cohesion: 0.25
Nodes (5): PerturbationReport, Findings across all perturbations., True when no perturbation moved any score beyond the tolerance. Counterfactual…, Perturbations that moved scores beyond tolerance, largest effect first., Per dimension, the gap between its best- and worst-treated variant. This is the…

### Community 46 - "Reliability and Norming (4)"
Cohesion: 0.39
Nodes (3): cronbach_alpha(), Cronbach's alpha: internal consistency across items. .. math:: \\alpha =…, TestCronbachAlpha

### Community 47 - "Reliability and Norming (5)"
Cohesion: 0.36
Nodes (4): interpret_reliability(), Plain-language interpretation of a reliability coefficient. Args: reliability:…, 0.85 is 'good' for research but only marginal for individual decisions., TestInterpretReliability

### Community 48 - "Reliability and Norming (6)"
Cohesion: 0.36
Nodes (4): Predict reliability after changing test length by ``factor``. .. math:: r' =…, spearman_brown(), r=0.5 doubled -> 2(0.5)/(1+0.5) = 0.667., TestSpearmanBrown

### Community 49 - "Adverse Impact Analysis (6)"
Cohesion: 0.33
Nodes (4): outcomes_from_scores(), Convert continuous scores into selection counts at a cut score. Args:…, Tests for adverse-impact analysis. The worked example in…, TestOutcomesFromScores

### Community 50 - "Perturbation Auditing (7)"
Cohesion: 0.43
Nodes (3): employment_gap(), Append an explicit career break to the experience section. Career gaps…, TestEmploymentGap

### Community 51 - "Statistical Primitives (5)"
Cohesion: 0.29
Nodes (5): normal_cdf(), Standard normal CDF, via the stdlib error function. Exact to double precision;…, parametrize, Tests for the statistical primitives. Reference values come from published…, TestNormalCdf

### Community 52 - "Impact Tests (2)"
Cohesion: 0.29
Nodes (3): The 1607.4(D) carve-out: big ratio gap, too few people to conclude., The reverse carve-out: passes 0.8 but significant, so not clearance., TestSmallSampleHandling

### Community 53 - "BART Browser Task"
Cohesion: 0.33
Nodes (6): Burst Points Drawn Without Replacement, Local-Only Data Handling, BART Browser Implementation, Balloon Analogue Risk Task (Lejuez et al. 2002), Published Paradigm Layer, Stop-Signal Task (Logan & Cowan 1984)

### Community 54 - "Impact Tests (3)"
Cohesion: 0.40
Nodes (4): parametrize, One fewer selection than reported must still fail -- no over-prescribing., Applying the reported shortfall must actually clear the four-fifths bar. This…, TestShortfallProperty

### Community 55 - "Parsing Tests (3)"
Cohesion: 0.33
Nodes (3): Tests for reading-order reconstruction. The two-column fixture is the central…, The classic scrambled resume, reproduced exactly., TestNaiveReadingOrder

### Community 56 - "Project Framing"
Cohesion: 0.40
Nodes (5): License Compatibility Requirement, Zero-Dependency CI Guard, Absence of a Maintained EEOC Adverse-Impact Library, Zero-Dependency Audit Core, audit-ai Unmaintained Since 2020

### Community 57 - "Methodology Teardown (2)"
Cohesion: 0.50
Nodes (5): Column Interleaving Failure, PDF Header/Footer Content Loss, Learned Ranking on Historical Hiring Outcomes, Reading-Order Reconstruction, Two-Stage Hiring Funnel

### Community 59 - "Methodology Teardown (3)"
Cohesion: 0.67
Nodes (3): Scheduled Atlas Refresh, Colorado SB 24-205 Repeal, EU AI Act Annex III Deferral

## Knowledge Gaps
- **32 isolated node(s):** `$schema`, `generated`, `license`, `note`, `public` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `adverse_impact()` connect `Adverse Impact Analysis (2)` to `LL144 Report Generation`, `Impact Tests`, `Agent Tool Surface (2)`, `LL144 Report Generation (2)`, `Adverse Impact Analysis`, `Statistical Primitives`, `Impact Tests (2)`, `Impact Tests (3)`, `Adverse Impact Analysis (3)`, `Adverse Impact Analysis (4)`, `Impact Tests (4)`, `Statistical Primitives (2)`, `Statistical Primitives (3)`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `TextBlock` connect `Reading Order Reconstruction` to `PDF and DOCX Extraction`, `Parsing Tests (2)`, `Parseability Diagnostics`, `Reading Order Reconstruction (3)`, `Agent Tool Surface (2)`, `Parsing Tests`, `Parseability Diagnostics (2)`, `Parsing Tests (3)`, `Reading Order Reconstruction (2)`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `diagnose()` connect `Parseability Diagnostics (2)` to `Parsing Tests (2)`, `PDF and DOCX Extraction`, `Parseability Diagnostics`, `Reading Order Reconstruction (3)`, `Agent Tool Surface (2)`, `Reading Order Reconstruction`, `Parsing Tests`, `Reading Order Reconstruction (2)`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `TextBlock` (e.g. with `Finding` and `ParseabilityReport`) actually correct?**
  _`TextBlock` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `call()` (e.g. with `.test_check_parseability()` and `.test_check_parseability_rejects_malformed_blocks()`) actually correct?**
  _`call()` has 16 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `generated`, `license` to the rest of the system?**
  _32 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Transparent Rubric Scoring` be split into smaller, more focused modules?**
  _Cohesion score 0.052614052614052616 - nodes in this community are weakly interconnected._