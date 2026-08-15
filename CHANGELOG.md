# Changelog

## 0.1.1 — 2026-08-15

Bug-fix release. Every item below was found by adversarial testing of 0.1.0 and now
has a regression test. Test count went from 346 to 526.

### Fixed — correctness

- **Fisher's exact test hung on large tables** (`glassbox.audit.stats`). The test is
  selected whenever any cell count is below 5, but that rule says nothing about the
  grand total, so a realistic dataset — 20,000 applicants with one selection in some
  group — enumerated a support spanning tens of thousands of huge-integer binomials.
  Measured: 1.4s at n=8,000, timing out past 20s at n=40,000. Now takes a log-space
  path with binary-searched tail boundaries. **12.6 seconds → 0.05ms at n=80,000,000**,
  with runtime now logarithmic in n rather than linear.

  Two further defects were found *inside* that fix before release:

  - the tail-boundary binary search was inverted on both sides, returning exactly
    half the correct p-value on tables where both tails contribute;
  - when a tail began already underflowed to zero, the stopping rule required a
    positive running total and so never fired, walking the full support.

  Verified against `scipy.stats.fisher_exact` across 609 tables: zero mismatches,
  worst relative error 3.2e-10, and zero disagreements on the p ≤ 0.05 decision.

- **A non-finite score produced a self-contradictory perturbation report**
  (`glassbox.audit.perturb`). `inf - inf` is `nan`, and every comparison with `nan` is
  false, so a run registered as *not invariant* while listing *no violations* —
  crashing any caller that read `violations[0]` after checking `is_invariant`.
  Scorer outputs are now validated as finite numbers.

### Fixed — silent wrong answers

- **NaN coordinates silently defeated column detection** (`glassbox.parse.layout`).
  A single non-finite x made every comparison false, collapsing span merging so a
  two-column resume was reported as one clean column — the exact failure the module
  exists to detect. `TextBlock` now rejects non-finite geometry.

- **`BartTrial` accepted impossible values** (`glassbox.psych.tasks`). A negative pump
  count yielded a negative "adjusted average pumps", which is not detectably wrong
  downstream — it just makes someone look like a low risk-taker. Behavioural telemetry
  arrives from browsers and is easy to corrupt, so the constructor now validates.

### Fixed — usability

- **Corrupt PDFs produced a raw traceback** (`glassbox.parse.pdf`). pdfminer's
  exception hierarchy inherits from neither `OSError` nor `ValueError`, so nothing in
  the call chain caught it. For a tool whose job is reading documents people hand it,
  a stack trace is the wrong answer. Now raises `ValueError` naming the file and the
  likely cause.

- **`min_share` accepted nonsensical values** (`glassbox.audit.impact`). A negative
  share excluded nothing; a share ≥ 1 excluded everything and then surfaced as
  "need at least 2 groups", pointing away from the actual mistake. Now validated
  to `[0, 1)`.

- **The agent harness could raise instead of returning an observation**
  (`glassbox.agent`). A caller-supplied scorer that raises — an HTTP call to a model
  endpoint is arbitrary user code — escaped as a traceback. Added a last-resort catch
  so no dispatched call can ever raise, plus specific handling with actionable
  guidance for scorer failures.

### Added

- `tests/test_external_validation.py` — validation against four independently
  published four-fifths worked examples, plus differential tests against `scipy`.
- `tests/test_robustness.py` — regression tests for every defect above.
- `tests/test_harness_conformance.py` — property tests over the whole agent action
  space: uniform observation shape, no raised exceptions, every error carrying a cause
  and a safe retry, and determinism across repeated calls.

### Notes

- p-values below roughly 1e-300 reach the float64 floor (subnormals bottom out near
  5e-324) and are reported as `0.0`. `scipy` behaves identically. No compliance
  decision turns on the difference.

## 0.1.0 — 2026-08-14

Initial release.
