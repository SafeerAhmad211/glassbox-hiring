"""Fetch the primary sources cited in TEARDOWN.md into research/raw/ (git-ignored).

These are not redistributed with the repository. Papers remain copyrighted by their
publishers; we link and extract locally instead of vendoring their text.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

RAW = Path(__file__).parent / "raw"

SOURCES = {
    "pymetrics-facct-2021.pdf": (
        "https://www.ccs.neu.edu/home/amislove/publications/Pymetrics-FAccT.pdf"
    ),
}

USER_AGENT = "glassbox-hiring/0.1 (research; +https://github.com/SafeerAhmad211/glassbox-hiring)"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)

    for name, url in SOURCES.items():
        target = RAW / name
        if target.exists():
            print(f"  {name}: already present")
            continue
        print(f"  {name}: fetching...")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                target.write_bytes(response.read())
            print(f"  {name}: {target.stat().st_size:,} bytes")
        except Exception as exc:
            print(f"  {name}: FAILED ({exc}) — download manually from {url}")

    print(f"\nSources in {RAW}. Extract text with: pip install pypdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
