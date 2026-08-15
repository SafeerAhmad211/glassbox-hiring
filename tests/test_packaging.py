"""Tests for packaging invariants the release workflow depends on.

A packaging mistake is unusually expensive here: PyPI never allows a version to be
reused, so a bad wheel cannot be replaced, only superseded. These check the properties
the release workflow assumes, at development time rather than at upload time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

import glassbox

# tomllib is stdlib only from Python 3.11, and this project supports 3.10. Reading
# pyproject.toml is a development-time concern, so tomli is a dev dependency; the
# shipped package still installs with zero dependencies.
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    try:
        import tomli as tomllib
    except ImportError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"

pytestmark = pytest.mark.skipif(
    not PYPROJECT.exists(),
    reason="running from an installed package, not a source checkout",
)


@pytest.fixture(scope="module")
def pyproject() -> dict:
    if tomllib is None:  # pragma: no cover
        pytest.skip("needs tomllib (3.11+) or tomli; install the dev extra")
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


class TestVersionIsSingleSourced:
    """The version must live in exactly one place.

    It used to be declared in both pyproject.toml and __init__.py, so every release
    depended on remembering to bump both. A mismatch produces a wheel whose metadata
    disagrees with the module it installs -- and it is unfixable once uploaded.
    """

    def test_pyproject_declares_version_dynamic(self, pyproject):
        assert "version" in pyproject["project"].get("dynamic", []), (
            "pyproject.toml must not hardcode a version; it is read from "
            "src/glassbox/__init__.py via [tool.hatch.version]"
        )

    def test_pyproject_does_not_hardcode_a_version(self, pyproject):
        assert "version" not in pyproject["project"]

    def test_hatch_points_at_the_package(self, pyproject):
        path = pyproject["tool"]["hatch"]["version"]["path"]
        assert path == "src/glassbox/__init__.py"

    def test_version_is_pep440_compatible(self):
        """The release workflow derives the git tag from this string."""
        assert re.fullmatch(r"\d+\.\d+\.\d+([abrc]\d+|\.dev\d+|\.post\d+)?", glassbox.__version__), (
            f"{glassbox.__version__!r} is not a version the workflow can tag"
        )

    def test_workflow_regex_extracts_the_same_version(self):
        """Guards the exact expression used in release.yml.

        The workflow reads the version with a regex rather than by importing, so a
        change to how ``__version__`` is written could silently break the tag check.
        """
        text = (REPO / "src" / "glassbox" / "__init__.py").read_text(encoding="utf-8")
        match = re.search(r'__version__ = "([^"]+)"', text)
        assert match, "release.yml's version regex no longer matches __init__.py"
        assert match.group(1) == glassbox.__version__


class TestDistributionContents:
    """Configuration that determines what actually ships."""

    def test_wheel_packages_the_source_tree(self, pyproject):
        packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
        assert packages == ["src/glassbox"]

    def test_atlas_data_file_is_inside_the_package(self):
        """vendors.json must live under src/ or it will not be in the wheel.

        The repo also keeps a copy at data/vendors.json for humans; the packaged copy
        is the one the installed library reads. A test run from a source checkout
        finds the repo copy either way, so only this check catches the omission.
        """
        assert (REPO / "src" / "glassbox" / "atlas" / "vendors.json").exists()

    def test_packaged_and_repo_atlas_agree(self):
        """The two copies must not drift."""
        import json

        packaged = json.loads(
            (REPO / "src" / "glassbox" / "atlas" / "vendors.json").read_text(encoding="utf-8")
        )
        repo_copy = json.loads((REPO / "data" / "vendors.json").read_text(encoding="utf-8"))
        assert [v["id"] for v in packaged["vendors"]] == [
            v["id"] for v in repo_copy["vendors"]
        ]

    def test_sdist_excludes_generated_artifacts(self, pyproject):
        """graphify-out/graph.html is 824 KB of regenerable output."""
        exclude = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"]
        assert "/graphify-out" in exclude

    def test_sdist_includes_tests_and_research(self, pyproject):
        """Downstream packagers need the tests; the research is the project's basis."""
        include = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
        for required in ("/src", "/tests", "/research"):
            assert required in include


class TestRuntimeDependencies:
    def test_base_install_has_no_dependencies(self, pyproject):
        """The zero-dependency guarantee, asserted against the manifest."""
        assert pyproject["project"]["dependencies"] == []

    def test_scipy_is_only_a_dev_dependency(self, pyproject):
        """scipy is a differential-test reference, never a runtime requirement."""
        optional = pyproject["project"]["optional-dependencies"]
        assert any("scipy" in dep for dep in optional["dev"])
        for extra in ("parse", "scrape"):
            assert not any("scipy" in dep for dep in optional[extra])


@pytest.fixture(scope="module")
def workflow() -> dict:
    """Parsed release.yml. Module-scoped: a class-scoped fixture defined as an
    instance method is deprecated and removed in pytest 10."""
    yaml = pytest.importorskip("yaml", reason="pyyaml not installed")
    path = REPO / ".github" / "workflows" / "release.yml"
    if not path.exists():
        pytest.skip("release workflow not present")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestReleaseWorkflow:
    """Structural checks on release.yml, so a security property cannot regress."""

    def test_workflow_parses(self, workflow):
        assert "jobs" in workflow

    def test_only_publish_jobs_hold_id_token(self, workflow):
        """`id-token: write` must never reach the build or test jobs."""
        for name, job in workflow["jobs"].items():
            has_token = "id-token" in str(job.get("permissions", ""))
            assert has_token == name.startswith("publish-"), (
                f"job {name!r} has unexpected id-token permission"
            )

    def test_publish_jobs_are_environment_bound(self, workflow):
        """Without an environment binding, a dispatched run can mint a valid token."""
        for name, job in workflow["jobs"].items():
            if name.startswith("publish-"):
                assert job.get("environment"), f"{name} must be environment-bound"

    def test_publish_jobs_do_not_check_out_source(self, workflow):
        """Publishing jobs upload a prebuilt artifact and nothing else."""
        for name, job in workflow["jobs"].items():
            if name.startswith("publish-"):
                uses = [str(step.get("uses", "")) for step in job["steps"]]
                assert not any("checkout" in u for u in uses), (
                    f"{name} must not check out the repository"
                )

    def test_publish_jobs_depend_on_verification(self, workflow):
        for name, job in workflow["jobs"].items():
            if name.startswith("publish-"):
                assert "verify" in str(job.get("needs", ""))

    def test_no_credentials_are_configured(self, workflow):
        """Trusted publishing is selected by omitting username/password."""
        for name, job in workflow["jobs"].items():
            if not name.startswith("publish-"):
                continue
            for step in job["steps"]:
                if "pypi-publish" in str(step.get("uses", "")):
                    with_block = step.get("with") or {}
                    assert "password" not in with_block
                    assert "username" not in with_block

    def test_action_is_version_pinned(self, workflow):
        """`@master` would let an upstream change run with publishing rights."""
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                uses = str(step.get("uses", ""))
                if "pypi-publish" in uses:
                    assert "@master" not in uses
                    assert "@" in uses
