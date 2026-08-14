# Contributing

Contributions are welcome. This project makes factual claims about real companies and
about legal obligations, so the evidence standard is stricter than for typical software.

## The evidence standard

Every factual claim in `data/vendors.json` and `research/TEARDOWN.md` carries a
provenance tag:

| Tag | Means | Examples |
|---|---|---|
| `public` | Regulation, granted patent, peer-reviewed work, court filing, or substantiated reporting | 29 CFR 1607, US 2019/0057356 A1, FAccT 2021 |
| `vendor` | The vendor's own claim. **Not verified.** | A product page describing what a test measures |
| `inference` | Our reasoning from the above, labelled as ours | "This behaviour is consistent with content-stream ordering" |
| `unknown` | We could not establish it | — |

Rules:

1. **Never promote a `vendor` claim to `public`** because it sounds plausible or is
   widely repeated. A number appearing in twenty blog posts that all cite the same
   press release is one `vendor` claim.
2. **Marketing arithmetic is not measurement.** "12,000 data points" counts telemetry
   events, not latent constructs. Record such claims under
   `marketing_claims_flagged` with the reason.
3. **Absence of a bias finding is not evidence of absence.** Do not add
   "no known bias issues" to a vendor record.
4. **Date anything time-sensitive.** Regulatory status changes; the Colorado entry in
   this dataset records a statute repealed before it took effect.

## What we will not accept

- **Reverse-engineered proprietary code or assets.** Everything here comes from public
  record. A PR containing decompiled vendor code, scraped internal API responses, or
  copied proprietary art will be closed.
- **Anything designed to defeat a live assessment.** Task implementations exist for
  research, validation, and self-hosted assessment. A PR whose purpose is to help
  someone cheat a real employer's assessment will be closed.
- **Scrapers that bypass access controls.** `glassbox.atlas.scraper` honours
  `robots.txt` with no override, rate-limits, and identifies itself. Keep it that way.
- **Code copied from a repository without a compatible license.** We excluded an
  otherwise useful working-memory task battery specifically because it had no license
  file.

## Code standards

- **Zero dependencies in `glassbox.audit`.** The predecessor library in this space died
  of dependency rot. Numerical work there uses the standard library only.
- **Exact arithmetic where the law draws a line.** Impact ratios use
  `fractions.Fraction`, not floats. `0.8 * 0.8 * 100 == 64.00000000000001`, and both a
  false "adverse impact" finding at exactly four-fifths and an inflated remedy figure
  were real bugs caught by tests.
- **Type annotations on every signature.** `mypy` runs in CI.
- **Docstrings state why, not only what** — particularly for any statistical choice a
  reader might otherwise suspect was made to produce a preferred answer.
- **`ruff` for lint and import order.**

## Testing

```bash
pip install -e ".[dev,parse]"
pytest --cov=src/glassbox --cov-report=term-missing
```

Requirements:

- **80% coverage minimum**, currently 85%.
- **Test against external references where they exist.** The Fisher exact tests check
  against published values from R and scipy; the four-fifths tests use the EEOC's own
  worked example. Tests that only assert the code agrees with itself catch far less.
- **Prefer property tests for numerical claims.** `TestShortfallProperty` asserts that
  applying a reported shortfall actually clears the threshold, across a parameter grid.
  It caught a floating-point bug that a hand-worked example missed.
- **Control tests for detectors.** `test_harness_would_catch_a_biased_rubric` proves the
  invariance test can fail. A detector never shown failing is not evidence of anything.

## Adding a task paradigm

`glassbox.psych.tasks` implements published paradigms. A new one needs:

1. The **primary citation** — the paper defining the paradigm, in the docstring.
2. The **scoring rule from that paper**, not a vendor's variant. Where the literature
   disagrees, say so and explain the choice (see `stop_signal_rt`, which uses the
   integration method and documents why).
3. **Honest `None` returns** where a measure is undefined. "Cannot be computed" and
   "no effect" are different findings and must not both render as `0.0`.
4. Tests using **values derived from the paradigm's definition**.

## Adding a jurisdiction

Add to the `regulations` array in `data/vendors.json` with `id`, `name`,
`jurisdiction`, `status` (including effective dates), and `key_obligations`. If a
widely-cited source is now wrong, add a `warning` field — that field exists because
much published guidance still describes the repealed Colorado act.

## Reporting issues

Especially valuable:

- **Parser behaviour measured against a real system.** Much of what is documented about
  how specific ATS platforms fail is second-hand. Reproducible measurements would let us
  promote those claims from `vendor`/`inference` to `public`.
- **Regulatory changes**, with a primary source.
- **Statistical errors.** Please include the reference value and its source.
