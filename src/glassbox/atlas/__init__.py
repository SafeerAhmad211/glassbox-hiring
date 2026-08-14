"""The vendor and regulation atlas.

A structured, citable dataset of ATS and assessment vendors, what they measure, what
methodology is publicly established about them, and the regulations that apply.

Every claim carries a provenance level. ``vendor`` means the vendor said it and nobody
checked; ``public`` means regulation, patent, peer review, or reporting. The
distinction is the point of the dataset -- most published vendor comparisons flatten
marketing copy and verified fact into the same table.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = ["atlas_path", "find_vendor", "load_atlas", "regulations", "vendors"]


def atlas_path() -> Path:
    """Locate ``data/vendors.json``.

    Checks the packaged copy first, then the repository layout, so the atlas works both
    from an installed wheel and from a source checkout.

    Raises:
        FileNotFoundError: If the dataset cannot be located.
    """
    packaged = Path(__file__).parent / "vendors.json"
    if packaged.exists():
        return packaged

    # Source checkout: src/glassbox/atlas/__init__.py -> repo root -> data/
    repo_copy = Path(__file__).resolve().parents[3] / "data" / "vendors.json"
    if repo_copy.exists():
        return repo_copy

    raise FileNotFoundError(
        "Could not locate vendors.json. Expected it beside this module or at "
        "<repo>/data/vendors.json."
    )


@lru_cache(maxsize=1)
def load_atlas() -> dict[str, Any]:
    """Load and cache the full atlas.

    Returns:
        The parsed dataset with ``vendors`` and ``regulations`` keys.

    Raises:
        FileNotFoundError: If the dataset is missing.
        json.JSONDecodeError: If it is malformed.
    """
    return json.loads(atlas_path().read_text(encoding="utf-8"))


def vendors(category: str | None = None) -> list[dict[str, Any]]:
    """Return vendor records, optionally filtered by category.

    Args:
        category: ``"ats"`` or ``"assessment"``. ``None`` returns all.
    """
    records = load_atlas()["vendors"]
    return [v for v in records if v["category"] == category] if category else records


def regulations() -> list[dict[str, Any]]:
    """Return regulation records."""
    return load_atlas()["regulations"]


def find_vendor(vendor_id: str) -> dict[str, Any] | None:
    """Look up one vendor by id.

    Args:
        vendor_id: The record's ``id`` field, e.g. ``"pymetrics"``.

    Returns:
        The record, or ``None`` if not found.
    """
    return next((v for v in load_atlas()["vendors"] if v["id"] == vendor_id), None)
