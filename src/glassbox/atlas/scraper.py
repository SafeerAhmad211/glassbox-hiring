"""Atlas refresh: keep the vendor and regulation dataset current.

Follows the COLLECT -> ENRICH -> STORE shape, with the store being a git-committed JSON
file rather than a hosted database. That choice is deliberate for a dataset whose whole
value is auditability: every change to a factual claim lands in git history with a diff
and a timestamp, so a reader can see when a claim changed and what it was before.

**Collection policy.** Only sources that are public and permit automated access:

- ``robots.txt`` is fetched and honoured for every host, with no override switch.
- One request at a time, with a delay between them. No concurrency.
- A descriptive User-Agent that identifies the project and links to it.
- Public regulatory and patent sources are preferred over vendor marketing pages,
  because they are both more reliable and unambiguously public record.

We do not log in anywhere, do not bypass any access control, and do not collect
personal data. The dataset is about companies and regulations, not people.

Requires the scrape extra: ``pip install 'glassbox-hiring[scrape]'``.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

__all__ = [
    "USER_AGENT",
    "FetchResult",
    "RobotsCache",
    "fetch",
    "merge_into_atlas",
    "refresh_regulations",
]

#: Identifies the crawler and links to the project, so an operator who sees it in their
#: logs can find out what it is and contact us.
USER_AGENT = (
    "glassbox-hiring-atlas/0.1 "
    "(+https://github.com/SafeerAhmad211/glassbox-hiring; research crawler)"
)

#: Seconds between requests to the same host. Deliberately conservative -- the dataset
#: refreshes daily at most, so there is no reason to be fast.
CRAWL_DELAY = 2.0


@dataclass(frozen=True)
class FetchResult:
    """Outcome of one fetch."""

    url: str
    status: int | None
    text: str | None
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.text is not None


@dataclass
class RobotsCache:
    """Per-host ``robots.txt`` rules, fetched once and cached.

    A host whose ``robots.txt`` cannot be fetched is treated as **disallowed**. The
    opposite default (allow on error) is how well-meaning crawlers end up hammering
    sites that were trying to say no.
    """

    _parsers: dict[str, urllib.robotparser.RobotFileParser] = field(default_factory=dict)
    _failed: set[str] = field(default_factory=set)

    def allows(self, url: str) -> bool:
        """Whether ``robots.txt`` permits fetching ``url``."""
        import requests

        parsed = urllib.parse.urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"

        if host in self._failed:
            return False

        if host not in self._parsers:
            parser = urllib.robotparser.RobotFileParser()
            try:
                response = requests.get(
                    f"{host}/robots.txt",
                    headers={"User-Agent": USER_AGENT},
                    timeout=15,
                )
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                elif response.status_code in (401, 403):
                    # Explicitly protected: treat everything as disallowed.
                    self._failed.add(host)
                    return False
                else:
                    # 404 means no robots.txt, which conventionally means allow all.
                    parser.parse([])
            except Exception:
                self._failed.add(host)
                return False
            self._parsers[host] = parser

        return self._parsers[host].can_fetch(USER_AGENT, url)


def fetch(url: str, robots: RobotsCache, *, delay: float = CRAWL_DELAY) -> FetchResult:
    """Fetch one URL, honouring robots.txt and rate limits.

    Args:
        url: The URL to fetch.
        robots: Shared robots cache.
        delay: Seconds to wait before the request.

    Returns:
        A :class:`FetchResult`. Disallowed or failed fetches return a result with
        ``skipped_reason`` set rather than raising -- a refresh run should continue
        past one unavailable source.
    """
    import requests

    if not robots.allows(url):
        return FetchResult(url, None, None, skipped_reason="disallowed by robots.txt")

    time.sleep(delay)
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        return FetchResult(url, response.status_code, response.text)
    except Exception as exc:
        return FetchResult(url, None, None, skipped_reason=f"fetch failed: {exc}")


#: Public regulatory sources. Primary law and regulator pages only -- these are public
#: record, stable, and authoritative in a way vendor pages are not.
REGULATION_SOURCES: dict[str, str] = {
    "eeoc-ugesp": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XIV/part-1607",
    "nyc-ll144": "https://rules.cityofnewyork.us/rule/automated-employment-decision-tools-2/",
}


def refresh_regulations(
    sources: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Check regulation source pages for availability and change.

    Deliberately does **not** attempt to auto-rewrite legal status text. Regulatory
    status is exactly the kind of claim that must not be updated by a scraper: the
    Colorado entry in this dataset records a statute that was repealed before taking
    effect, which no amount of page-diffing would have got right. This reports *that a
    source changed* so a human checks it.

    Args:
        sources: ``{regulation_id: url}``. Defaults to :data:`REGULATION_SOURCES`.

    Returns:
        One record per source with ``id``, ``url``, ``available``, ``content_length``,
        and ``checked`` date.
    """
    robots = RobotsCache()
    results = []

    for regulation_id, url in (sources or REGULATION_SOURCES).items():
        result = fetch(url, robots)
        results.append(
            {
                "id": regulation_id,
                "url": url,
                "available": result.ok,
                "content_length": len(result.text) if result.text else 0,
                "skipped_reason": result.skipped_reason,
                "checked": date.today().isoformat(),
            }
        )

    return results


def merge_into_atlas(
    atlas_path: Path, checks: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Record source-availability checks in the atlas without altering claims.

    Adds or replaces a ``source_checks`` block and refreshes ``generated``. Factual
    fields are never touched by automation.

    Args:
        atlas_path: Path to ``vendors.json``.
        checks: Records from :func:`refresh_regulations`.

    Returns:
        The updated atlas dict (also written to disk).

    Raises:
        FileNotFoundError: If the atlas file does not exist.
    """
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    atlas["source_checks"] = list(checks)
    atlas["generated"] = date.today().isoformat()
    atlas_path.write_text(
        json.dumps(atlas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return atlas


def main() -> int:
    """Run a refresh. Entry point for the scheduled GitHub Action."""
    from . import atlas_path

    print(f"glassbox atlas refresh — {date.today().isoformat()}")
    print(f"user-agent: {USER_AGENT}\n")

    checks = refresh_regulations()
    for check in checks:
        status = "ok" if check["available"] else f"SKIPPED ({check['skipped_reason']})"
        print(f"  {check['id']:<20} {status}")

    path = atlas_path()
    merge_into_atlas(path, checks)
    print(f"\nUpdated {path}")

    unavailable = [c for c in checks if not c["available"]]
    if unavailable:
        print(f"\n{len(unavailable)} source(s) unavailable — review before relying on them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
