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

## Releasing

Publishing uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
via [`.github/workflows/release.yml`](.github/workflows/release.yml). There is no API
token in this repository — PyPI mints a short-lived credential for this specific
workflow, in this repository, in a named environment. Nothing to leak, nothing to
rotate.

### One-time setup

These steps happen in the PyPI and GitHub web UIs; a workflow cannot perform them.

1. **PyPI** → *Your projects* → *Publishing* → *Add a pending publisher*:

   | Field | Value |
   |---|---|
   | Owner | `SafeerAhmad211` |
   | Repository | `glassbox-hiring` |
   | Workflow | `release.yml` |
   | Environment | `pypi` |

   Repeat on [test.pypi.org](https://test.pypi.org) with environment `testpypi`.

2. **GitHub** → *Settings* → *Environments* → create `pypi` and `testpypi`. Add a
   required reviewer on `pypi` so a real upload cannot happen unattended.

### Cutting a release

1. Bump `__version__` in `src/glassbox/__init__.py`. That is the **only** place a
   version is written — `pyproject.toml` reads it via `[tool.hatch.version]`, so the
   two can no longer disagree.
2. Add a `CHANGELOG.md` entry.
3. Rehearse: *Actions* → *release* → *Run workflow* → target `testpypi`. This builds,
   verifies, and uploads to TestPyPI without touching the real index.
4. Publish a GitHub Release tagged `v<version>` (e.g. `v0.2.0`). That triggers the
   PyPI upload.

### What the workflow checks before uploading

PyPI never allows a version to be reused, so every check runs *before* the upload
step rather than after it:

- the release tag matches the package version — tagging `v0.2.0` without bumping
  `__version__` would otherwise publish `0.1.2` under a `0.2.0` release, permanently;
- the version is not already on PyPI;
- `twine check --strict` passes on both distributions;
- the **wheel** installs and works on Linux, macOS, and Windows across Python 3.10
  and 3.13 — with no checkout, so a data file missing from the wheel is caught. A
  test suite run against a git checkout cannot see that class of bug at all;
- the installed package still pulls **zero** third-party dependencies;
- the console entry point runs and returns its documented exit codes.

`tests/test_packaging.py` asserts the workflow's security properties — that only the
publishing jobs hold `id-token: write`, that they are environment-bound, that they
never check out source, and that no credentials are configured — so those cannot
regress unnoticed.

## Reporting issues

Especially valuable:

- **Parser behaviour measured against a real system.** Much of what is documented about
  how specific ATS platforms fail is second-hand. Reproducible measurements would let us
  promote those claims from `vendor`/`inference` to `public`.
- **Regulatory changes**, with a primary source.
- **Statistical errors.** Please include the reference value and its source.
