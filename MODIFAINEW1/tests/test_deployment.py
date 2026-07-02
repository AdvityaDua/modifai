"""
Unit tests for agents/deployment.py.

Test coverage
-------------
- Happy path: deployment_url is set, is a string, contains session prefix.
- URL format: contains the API base and a valid endpoint segment.
- Private helper: _deploy_model returns a string URL.
- Private helper: _build_endpoint_id uses session prefix.
- Contract: returns only owned fields; no foreign fields.
- Error path: deployment_url=None on exception.
"""

from __future__ import annotations

import pytest

from agents.deployment import (
    _API_BASE,
    _build_endpoint_id,
    _deploy_model,
    deployment_agent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for deployment_agent tests."""
    defaults = {
        "session_id": "abcd1234-efgh-5678-ijkl-mnop90123456",
        "model_uri": "s3://modifai-models/stub/modifai-job-abc12345/model.tar.gz",
        "evaluation_metrics": {
            "accuracy": 0.92,
            "f1_score": 0.91,
            "eval_pass": True,
        },
        "execution_history": [],
        "errors": [],
        "metadata": {},
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Tests: private helpers
# ---------------------------------------------------------------------------


class TestBuildEndpointId:
    def test_contains_session_prefix(self):
        session_id = "abcd1234-efgh"
        endpoint_id = _build_endpoint_id(session_id)
        assert endpoint_id.startswith("abcd1234")

    def test_returns_string(self):
        assert isinstance(_build_endpoint_id("test-session-id"), str)

    def test_unique_per_call(self):
        id1 = _build_endpoint_id("same-session")
        id2 = _build_endpoint_id("same-session")
        assert id1 != id2


class TestDeployModel:
    def test_returns_string(self):
        url = _deploy_model("s3://bucket/model", "test-session")
        assert isinstance(url, str)

    def test_url_starts_with_api_base(self):
        url = _deploy_model("s3://bucket/model", "test-session")
        assert url.startswith(_API_BASE)

    def test_url_contains_session_prefix(self):
        url = _deploy_model("s3://bucket/model", "abcd1234-session")
        assert "abcd1234" in url


# ---------------------------------------------------------------------------
# Tests: deployment_agent — happy path
# ---------------------------------------------------------------------------


class TestDeploymentAgentHappyPath:
    def test_deployment_url_set(self):
        result = deployment_agent(_state())
        assert result["deployment_url"] is not None

    def test_deployment_url_is_string(self):
        result = deployment_agent(_state())
        assert isinstance(result["deployment_url"], str)

    def test_deployment_url_starts_with_api_base(self):
        result = deployment_agent(_state())
        assert result["deployment_url"].startswith(_API_BASE)

    def test_deployment_url_contains_session_prefix(self):
        result = deployment_agent(_state(session_id="cafe1234-rest"))
        # First 8 chars of session_id appear in the URL
        assert "cafe1234" in result["deployment_url"]

    def test_no_errors_on_happy_path(self):
        result = deployment_agent(_state())
        assert "errors" not in result


# ---------------------------------------------------------------------------
# Tests: deployment_agent — contract
# ---------------------------------------------------------------------------


class TestDeploymentAgentContract:
    def test_returns_dict(self):
        assert isinstance(deployment_agent(_state()), dict)

    def test_current_agent_set(self):
        result = deployment_agent(_state())
        assert result["current_agent"] == "Deployment Agent"

    def test_execution_history_contains_agent(self):
        result = deployment_agent(_state())
        assert "Deployment Agent" in result["execution_history"]

    def test_does_not_write_foreign_fields(self):
        forbidden = {
            "validation_status",
            "dataset_type",
            "task_type",
            "ocr_required",
            "extracted_documents",
            "chunks",
            "generated_dataset",
            "dataset_quality_score",
            "training_job_id",
            "training_status",
            "model_uri",
            "evaluation_metrics",
        }
        result = deployment_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"


# ---------------------------------------------------------------------------
# Tests: deployment_agent — error path
# ---------------------------------------------------------------------------


class TestDeploymentAgentErrorPath:
    def test_error_sets_deployment_url_none(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker endpoint creation failed")

        monkeypatch.setattr("agents.deployment._deploy_model", _raise)
        result = deployment_agent(_state())
        assert result["deployment_url"] is None

    def test_error_appends_error_message(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker endpoint creation failed")

        monkeypatch.setattr("agents.deployment._deploy_model", _raise)
        result = deployment_agent(_state())
        assert any("DeploymentAgent" in e for e in result["errors"])

    def test_returns_dict_on_error(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker endpoint creation failed")

        monkeypatch.setattr("agents.deployment._deploy_model", _raise)
        assert isinstance(deployment_agent(_state()), dict)
