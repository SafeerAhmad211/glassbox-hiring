"""Tests for the agent tool surface, the atlas, and the CLI.

The agent-surface tests focus on the harness contract: uniform output shape, the
warning-vs-error distinction, and error paths that carry a recovery route. Those are
the properties an agent depends on, and they are easy to break silently.
"""

from __future__ import annotations

import json

import pytest

from glassbox.agent import TOOLS, call, tool_schemas
from glassbox.atlas import find_vendor, load_atlas, regulations, vendors
from glassbox.cli import main


class TestObservationContract:
    """Every tool must return the same shape, whatever happens."""

    def test_all_tools_reachable(self):
        assert set(tool_schemas()) == set(TOOLS)

    def test_unknown_tool_returns_error_not_exception(self):
        observation = call("no_such_tool")
        assert observation.status == "error"
        assert "no_such_tool" in observation.summary

    def test_unknown_tool_lists_valid_names(self):
        """Recovery route, not just a complaint."""
        observation = call("no_such_tool")
        assert "audit_selection_rates" in observation.data["hint"]

    def test_bad_arguments_return_error_with_retry(self):
        observation = call("audit_selection_rates", wrong_kwarg=1)
        assert observation.status == "error"
        assert observation.next_actions

    @pytest.mark.parametrize("tool_name", sorted(TOOLS))
    def test_every_tool_has_a_description(self, tool_name):
        assert len(tool_schemas()[tool_name]["description"]) > 10

    def test_observation_serialises_to_json(self):
        observation = call(
            "audit_selection_rates", outcomes={"A": [50, 100], "B": [45, 100]}
        )
        parsed = json.loads(observation.to_json())
        assert set(parsed) == {"status", "summary", "data", "next_actions", "artifacts"}


class TestWarningVersusError:
    """A finding is not a failure. Collapsing them teaches an agent to retry."""

    def test_adverse_impact_is_warning_not_error(self):
        observation = call(
            "audit_selection_rates", outcomes={"A": [80, 100], "B": [40, 100]}
        )
        assert observation.status == "warning"
        assert observation.data["groups"]

    def test_clean_result_is_success(self):
        observation = call(
            "audit_selection_rates", outcomes={"A": [50, 100], "B": [45, 100]}
        )
        assert observation.status == "success"

    def test_malformed_input_is_error(self):
        observation = call("audit_selection_rates", outcomes={"A": "nonsense"})
        assert observation.status == "error"

    def test_warning_carries_actionable_next_steps(self):
        observation = call(
            "audit_selection_rates", outcomes={"A": [80, 100], "B": [40, 100]}
        )
        assert any("additional selections" in a for a in observation.next_actions)


class TestAgentTools:
    def test_sweep_thresholds(self):
        observation = call(
            "sweep_thresholds",
            scores_by_group={
                "A": [float(i) for i in range(50)],
                "B": [float(i) / 2 for i in range(50)],
            },
        )
        assert observation.status in {"success", "warning"}
        assert len(observation.data["curve"]) == 9

    def test_match_resume_to_rubric(self):
        observation = call(
            "match_resume_to_rubric",
            resume_text="Built services in Python.",
            required_skills=["Python"],
        )
        assert observation.status == "success"
        assert observation.data["score"] == pytest.approx(1.0)

    def test_match_reports_missing_required_as_warning(self):
        observation = call(
            "match_resume_to_rubric",
            resume_text="Built services in Python.",
            required_skills=["Python", "Kubernetes"],
        )
        assert observation.status == "warning"
        assert observation.data["missing_required"] == ["Kubernetes"]

    def test_check_parseability(self):
        observation = call(
            "check_resume_parseability",
            blocks=[
                {"text": "Jane Doe", "x": 50, "y": 700},
                {"text": "jane@example.com", "x": 50, "y": 680},
                {"text": "EXPERIENCE", "x": 50, "y": 660},
                {"text": "Acme Corp 2020 - 2024", "x": 50, "y": 640},
                {"text": "EDUCATION", "x": 50, "y": 620},
            ],
        )
        assert observation.status == "success"

    def test_check_parseability_rejects_malformed_blocks(self):
        observation = call("check_resume_parseability", blocks=[{"no_text": 1}])
        assert observation.status == "error"
        assert "text" in observation.data["hint"]

    def test_scorer_invariance_detects_bias(self):
        observation = call(
            "audit_scorer_invariance",
            resumes=["Jane Doe\nEngineer"],
            scorer=lambda t: 0.1 if t.startswith("Todd") else 0.9,
        )
        assert observation.status == "warning"
        assert observation.data["violations"]

    def test_generate_ll144_report(self):
        observation = call(
            "generate_ll144_report",
            tool_name="T",
            tool_version="1",
            auditor="A",
            data_source="S",
            data_explanation="E",
            sex_outcomes={"Male": [50, 100], "Female": [48, 100]},
        )
        assert observation.status == "success"
        assert "Bias Audit" in observation.data["markdown"]

    def test_ll144_writes_file(self, tmp_path):
        out = tmp_path / "audit.md"
        observation = call(
            "generate_ll144_report",
            tool_name="T",
            tool_version="1",
            auditor="A",
            data_source="S",
            data_explanation="E",
            sex_outcomes={"Male": [50, 100], "Female": [48, 100]},
            output_path=str(out),
        )
        assert out.exists()
        assert str(out) in observation.artifacts
        # UTF-8 explicitly: the report contains characters cp1252 cannot encode.
        assert "Bias Audit" in out.read_text(encoding="utf-8")


class TestAtlas:
    def test_loads(self):
        atlas = load_atlas()
        assert atlas["vendors"]
        assert atlas["regulations"]

    def test_filter_by_category(self):
        assert all(v["category"] == "ats" for v in vendors("ats"))
        assert all(v["category"] == "assessment" for v in vendors("assessment"))

    def test_find_vendor(self):
        assert find_vendor("pymetrics")["name"].startswith("pymetrics")

    def test_unknown_vendor_returns_none(self):
        assert find_vendor("not-a-vendor") is None

    def test_every_vendor_has_required_fields(self):
        for vendor in vendors():
            for field in ("id", "name", "category", "tier", "measures", "method"):
                assert field in vendor, f"{vendor.get('id')} missing {field}"

    def test_every_method_claim_declares_evidence_level(self):
        """The whole point of the dataset: no unsourced claims."""
        valid = {"public", "vendor", "inference", "unknown"}
        for vendor in vendors():
            assert vendor["method"]["evidence"] in valid, vendor["id"]

    def test_vendor_ids_are_unique(self):
        ids = [v["id"] for v in vendors()]
        assert len(ids) == len(set(ids))

    def test_colorado_records_the_repeal(self):
        """Regression guard: many published guides still cite the repealed SB 24-205."""
        colorado = next(r for r in regulations() if r["id"] == "colorado-ai")
        assert "REPEALED" in colorado["status"]
        assert "SB 26-189" in colorado["status"]

    def test_eu_ai_act_records_the_deferral(self):
        eu = next(r for r in regulations() if r["id"] == "eu-ai-act")
        assert "2027-12-02" in eu["status"]

    def test_pymetrics_records_the_audited_methodology(self):
        pymetrics = find_vendor("pymetrics")
        assert pymetrics["method"]["evidence"] == "public"
        assert "FAccT" in pymetrics["method"]["source"]
        assert len(pymetrics["task_paradigms"]) >= 10

    def test_task_paradigms_carry_citations(self):
        for paradigm in find_vendor("pymetrics")["task_paradigms"]:
            assert paradigm["citation"]


class TestCli:
    def test_audit_exits_1_on_finding(self, tmp_path, capsys):
        counts = tmp_path / "counts.csv"
        counts.write_text(
            "group,selected,total\nA,80,100\nB,40,100\n", encoding="utf-8"
        )
        assert main(["audit", str(counts)]) == 1
        assert "FINDING" in capsys.readouterr().out

    def test_audit_exits_0_when_clean(self, tmp_path):
        counts = tmp_path / "counts.csv"
        counts.write_text(
            "group,selected,total\nA,50,100\nB,48,100\n", encoding="utf-8"
        )
        assert main(["audit", str(counts)]) == 0

    def test_missing_file_exits_2(self, tmp_path):
        assert main(["audit", str(tmp_path / "nope.csv")]) == 2

    def test_bad_csv_columns_exits_2(self, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("wrong,headers\n1,2\n", encoding="utf-8")
        assert main(["audit", str(bad)]) == 2

    def test_json_output_is_parseable(self, tmp_path, capsys):
        counts = tmp_path / "counts.csv"
        counts.write_text(
            "group,selected,total\nA,50,100\nB,48,100\n", encoding="utf-8"
        )
        main(["--json", "audit", str(counts)])
        assert json.loads(capsys.readouterr().out)["status"] == "success"

    def test_atlas_lists_vendors(self, capsys):
        assert main(["atlas"]) == 0
        assert "pymetrics" in capsys.readouterr().out

    def test_atlas_regulations(self, capsys):
        assert main(["atlas", "--regulations"]) == 0
        assert "Local Law 144" in capsys.readouterr().out

    def test_tools_lists_surface(self, capsys):
        assert main(["tools"]) == 0
        assert "audit_selection_rates" in capsys.readouterr().out

    def test_sweep(self, tmp_path, capsys):
        scores = tmp_path / "scores.csv"
        rows = ["group,score"]
        rows += [f"A,{i / 50}" for i in range(50)]
        rows += [f"B,{i / 100}" for i in range(50)]
        scores.write_text("\n".join(rows) + "\n", encoding="utf-8")
        assert main(["sweep", str(scores)]) in {0, 1}
        assert "min IR" in capsys.readouterr().out
