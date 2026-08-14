# Fetching the primary sources

The teardown in [TEARDOWN.md](TEARDOWN.md) cites sources this repository does **not**
redistribute. Academic papers are copyrighted by their publishers, so we link to them
and extract locally rather than vendoring their text.

Run this to pull them into `research/raw/` (git-ignored):

```bash
python research/fetch_sources.py
```

## Sources

| Source | Access | Why it matters |
|---|---|---|
| Wilson et al. (2021), *Building and Auditing Fair Algorithms* — [ACM DL](https://doi.org/10.1145/3442188.3445928) · [author PDF](https://www.ccs.neu.edu/home/amislove/publications/Pymetrics-FAccT.pdf) | Open author copy | The only public audit of a commercial hiring algorithm with source-code access. Section 3 documents the full training and fairness pipeline |
| US 2019/0057356 A1 — [Google Patents](https://patents.google.com/patent/US20190057356A1/en) | Public record | Class-normalised loss and the "digital fingerprint" method our perturbation harness inverts |
| 29 CFR Part 1607 (UGESP) — [eCFR](https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XIV/part-1607) | Public record | The four-fifths rule and its three qualifications |
| NYC AEDT rules — [NYC Rules](https://rules.cityofnewyork.us/rule/automated-employment-decision-tools-2/) | Public record | What a published bias audit must contain |

Patents and regulations are public record and may be quoted freely. Papers are quoted
only briefly and with attribution, as in TEARDOWN.md.
