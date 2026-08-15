"""Conformance tests for the agent action space.

An agent depends on the *contract*, not on any individual tool: uniform observation
shape whatever happens, no raised exceptions, and every failure carrying a cause plus
a safe next step. Those properties are easy to break silently when adding a tool, so
they are tested across the whole surface rather than tool by tool.

Structured after the action-space and error-recovery rules in
`agent-harness-construction`.
"""

from __future__ import annotations

import json

import pytest

from glassbox.agent.tools import TOOLS, Observation, call, tool_schemas

VALID_STATUSES = {"success", "warning", "error"}

#: A minimal valid invocation per tool, for the success-path conformance checks.
VALID_CALLS: dict[str, dict] = {
    "audit_selection_rates": {"outcomes": {"A": [50, 100], "B": [45, 100]}},
    "sweep_thresholds": {
        "scores_by_group": {
            "A": [float(i) for i in range(30)],
            "B": [float(i) / 2 for i in range(30)],
        }
    },
    "audit_scorer_invariance": {
        "resumes": ["Jane Doe\nEngineer"],
        "scorer": len,
    },
    "check_resume_parseability": {
        "blocks": [
            {"text": "Jane Doe", "x": 50, "y": 700},
            {"text": "jane@example.com", "x": 50, "y": 680},
            {"text": "EXPERIENCE", "x": 50, "y": 660},
            {"text": "Acme Corp 2020 - 2024", "x": 50, "y": 640},
            {"text": "EDUCATION", "x": 50, "y": 620},
        ]
    },
    "match_resume_to_rubric": {
        "resume_text": "Built services in Python.",
        "required_skills": ["Python"],
    },
    "generate_ll144_report": {
        "tool_name": "T",
        "tool_version": "1",
        "auditor": "A",
        "data_source": "S",
        "data_explanation": "E",
        "sex_outcomes": {"Male": [50, 100], "Female": [48, 100]},
    },
}

#: Malformed invocations per tool, to exercise the error contract.
INVALID_CALLS: dict[str, list[dict]] = {
    "audit_selection_rates": [
        {"outcomes": {"A": "nonsense"}},
        {"outcomes": {"A": [1]}},
        {"outcomes": {}},
        {"outcomes": {"A": [50, 100]}},
        {"outcomes": {"A": [50, 100], "B": [45, 100]}, "min_share": 5.0},
        {"outcomes": {"A": [200, 100], "B": [45, 100]}},
    ],
    "sweep_thresholds": [
        {"scores_by_group": {}},
        {"scores_by_group": {"A": [], "B": []}},
        {"scores_by_group": {"A": ["not-a-number"], "B": [1.0]}},
    ],
    "audit_scorer_invariance": [
        {"resumes": [], "scorer": len},
        {"resumes": ["x"], "scorer": len, "tolerance": -1.0},
    ],
    "check_resume_parseability": [
        {"blocks": [{"no_text_key": 1}]},
        {"blocks": [{"text": "a", "x": "not-a-number", "y": 1}]},
        {"blocks": "not-a-list"},
    ],
    "match_resume_to_rubric": [
        {"resume_text": "x"},
        {"resume_text": "x", "required_skills": []},
    ],
    "generate_ll144_report": [
        {
            "tool_name": "T", "tool_version": "1", "auditor": "A",
            "data_source": "S", "data_explanation": "E",
        },
        {
            "tool_name": "T", "tool_version": "1", "auditor": "A",
            "data_source": "S", "data_explanation": "E",
            "sex_outcomes": {"Male": "bad"},
        },
    ],
}


class TestActionSpaceCompleteness:
    def test_every_tool_has_a_valid_call_fixture(self):
        """Guards the test suite itself: a new tool must be covered here."""
        assert set(VALID_CALLS) == set(TOOLS)

    def test_every_tool_has_invalid_call_fixtures(self):
        assert set(INVALID_CALLS) == set(TOOLS)

    def test_schemas_cover_every_tool(self):
        assert set(tool_schemas()) == set(TOOLS)

    def test_tool_names_are_snake_case_and_stable(self):
        """Tool names are public API; drift breaks every agent prompt referencing them."""
        for name in TOOLS:
            assert name.islower()
            assert " " not in name
            assert name.replace("_", "").isalnum()


class TestObservationShape:
    """Every call returns the same four fields, whatever happens."""

    @pytest.mark.parametrize("tool_name", sorted(VALID_CALLS))
    def test_valid_call_returns_observation(self, tool_name):
        observation = call(tool_name, **VALID_CALLS[tool_name])
        assert isinstance(observation, Observation)
        assert observation.status in VALID_STATUSES
        assert isinstance(observation.data, dict)
        assert isinstance(observation.next_actions, list)
        assert isinstance(observation.artifacts, list)

    @pytest.mark.parametrize("tool_name", sorted(VALID_CALLS))
    def test_summary_is_a_single_informative_line(self, tool_name):
        observation = call(tool_name, **VALID_CALLS[tool_name])
        assert observation.summary
        assert "\n" not in observation.summary
        assert len(observation.summary) > 15

    @pytest.mark.parametrize("tool_name", sorted(VALID_CALLS))
    def test_observation_is_json_serialisable(self, tool_name):
        """Observations cross a process boundary to reach an agent."""
        observation = call(tool_name, **VALID_CALLS[tool_name])
        parsed = json.loads(observation.to_json())
        assert set(parsed) == {"status", "summary", "data", "next_actions", "artifacts"}

    @pytest.mark.parametrize("tool_name", sorted(VALID_CALLS))
    def test_successful_call_offers_next_actions(self, tool_name):
        """Even a clean result should tell an agent where it can go next."""
        observation = call(tool_name, **VALID_CALLS[tool_name])
        assert observation.next_actions


class TestErrorContract:
    """No tool raises; every failure carries a cause and a safe retry."""

    @pytest.mark.parametrize(
        "tool_name,kwargs",
        [(name, kw) for name, cases in INVALID_CALLS.items() for kw in cases],
    )
    def test_malformed_input_never_raises(self, tool_name, kwargs):
        observation = call(tool_name, **kwargs)
        assert isinstance(observation, Observation)
        assert observation.status in VALID_STATUSES

    @pytest.mark.parametrize(
        "tool_name,kwargs",
        [(name, kw) for name, cases in INVALID_CALLS.items() for kw in cases],
    )
    def test_error_observations_carry_cause_and_retry(self, tool_name, kwargs):
        observation = call(tool_name, **kwargs)
        if observation.status != "error":
            return  # some malformed inputs are legitimately handled as findings
        assert observation.data.get("hint"), "error must state a root cause"
        assert observation.next_actions, "error must state a safe next step"
        assert len(observation.next_actions[0]) > 10

    def test_unknown_tool_lists_valid_names(self):
        observation = call("no_such_tool")
        assert observation.status == "error"
        assert all(name in observation.data["hint"] for name in TOOLS)

    def test_wrong_keyword_is_recoverable(self):
        observation = call("audit_selection_rates", not_a_real_param=1)
        assert observation.status == "error"
        assert "tool_schemas" in observation.next_actions[0]

    def test_dispatcher_survives_a_raising_scorer(self):
        """A caller-supplied callable that raises must not escape the harness.

        The scorer is arbitrary user code -- an HTTP call, a model, anything. If its
        failure propagates as an exception, an agent gets a traceback instead of a
        recoverable observation.
        """
        def broken_scorer(text: str) -> float:
            raise RuntimeError("model endpoint down")

        observation = call(
            "audit_scorer_invariance", resumes=["x"], scorer=broken_scorer
        )
        assert isinstance(observation, Observation)
        assert observation.status == "error"
        assert observation.next_actions


class TestFindingsAreNotFailures:
    """`warning` means the tool worked and the answer is bad news."""

    def test_adverse_impact_is_a_warning(self):
        observation = call(
            "audit_selection_rates", outcomes={"A": [80, 100], "B": [40, 100]}
        )
        assert observation.status == "warning"
        assert observation.data["groups"], "a finding must still carry its data"

    def test_missing_required_skill_is_a_warning(self):
        observation = call(
            "match_resume_to_rubric",
            resume_text="Python only",
            required_skills=["Python", "Kubernetes"],
        )
        assert observation.status == "warning"
        assert observation.data["score"] > 0, "a finding still reports a result"

    def test_parseability_problem_is_a_warning(self):
        observation = call(
            "check_resume_parseability",
            blocks=[
                {"text": "Jane Doe", "x": 50, "y": 700, "emit_index": 0},
                {"text": "SKILLS", "x": 350, "y": 700, "emit_index": 1},
                {"text": "jane@example.com", "x": 50, "y": 680, "emit_index": 2},
                {"text": "Python", "x": 350, "y": 680, "emit_index": 3},
            ],
        )
        assert observation.status == "warning"
        assert observation.data["findings"]

    @pytest.mark.parametrize("tool_name", sorted(VALID_CALLS))
    def test_warnings_carry_data_not_just_a_message(self, tool_name):
        """A finding an agent cannot inspect is not actionable."""
        observation = call(tool_name, **VALID_CALLS[tool_name])
        if observation.status == "warning":
            assert observation.data


class TestDeterminism:
    """Same input, same observation -- agents retry, and flapping results break them."""

    @pytest.mark.parametrize("tool_name", sorted(VALID_CALLS))
    def test_repeated_calls_agree(self, tool_name):
        first = call(tool_name, **VALID_CALLS[tool_name])
        second = call(tool_name, **VALID_CALLS[tool_name])
        assert first.status == second.status
        assert first.summary == second.summary
        assert first.next_actions == second.next_actions
