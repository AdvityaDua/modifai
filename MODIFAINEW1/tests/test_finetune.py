"""
Unit tests for agents/finetune.py.

Test coverage
-------------
- Happy path: job submitted → training_job_id, training_status, model_uri set.
- Job ID format: starts with "modifai-job-".
- Model URI format: starts with expected S3 prefix.
- Contract: returns only owned fields; no foreign fields.
- Error path: all three owned fields set to safe defaults on exception.
"""

from __future__ import annotations

import pytest

from agents.finetune import (
    _MODEL_S3_PREFIX,
    _build_model_uri,
    _submit_training_job,
    finetune_agent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for finetune_agent tests."""
    defaults = {
        "session_id": "test-session-finetune",
        "generated_dataset": [
            {"id": 0, "question": "Q", "answer": "A", "dataset_type": "QA"}
        ],
        "task_type": "text-classification",
        "execution_history": [],
        "errors": [],
        "metadata": {},
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Tests: private helpers
# ---------------------------------------------------------------------------


class TestBuildModelUri:
    def test_contains_job_id(self):
        uri = _build_model_uri("my-job-abc123")
        assert "my-job-abc123" in uri

    def test_starts_with_s3_prefix(self):
        uri = _build_model_uri("job-001")
        assert uri.startswith(_MODEL_S3_PREFIX)

    def test_ends_with_tar_gz(self):
        uri = _build_model_uri("job-001")
        assert uri.endswith(".tar.gz")


class TestSubmitTrainingJob:
    def test_returns_required_keys(self):
        result = _submit_training_job([], "text-classification")
        for key in ("training_job_id", "training_status", "model_uri"):
            assert key in result

    def test_status_is_completed(self):
        result = _submit_training_job([], "text-classification")
        assert result["training_status"] == "COMPLETED"

    def test_job_id_format(self):
        result = _submit_training_job([], "text-classification")
        assert result["training_job_id"].startswith("modifai-job-")

    def test_model_uri_is_string(self):
        result = _submit_training_job([], "text-classification")
        assert isinstance(result["model_uri"], str)

    def test_unique_job_ids_per_call(self):
        r1 = _submit_training_job([], "text-classification")
        r2 = _submit_training_job([], "text-classification")
        assert r1["training_job_id"] != r2["training_job_id"]


# ---------------------------------------------------------------------------
# Tests: finetune_agent — happy path
# ---------------------------------------------------------------------------


class TestFinetuneAgentHappyPath:
    def test_training_job_id_set(self):
        result = finetune_agent(_state())
        assert result["training_job_id"] is not None

    def test_training_job_id_format(self):
        result = finetune_agent(_state())
        assert result["training_job_id"].startswith("modifai-job-")

    def test_training_status_completed(self):
        result = finetune_agent(_state())
        assert result["training_status"] == "COMPLETED"

    def test_model_uri_set(self):
        result = finetune_agent(_state())
        assert result["model_uri"] is not None

    def test_model_uri_is_string(self):
        result = finetune_agent(_state())
        assert isinstance(result["model_uri"], str)

    def test_no_errors_on_happy_path(self):
        result = finetune_agent(_state())
        assert "errors" not in result


# ---------------------------------------------------------------------------
# Tests: finetune_agent — contract
# ---------------------------------------------------------------------------


class TestFinetuneAgentContract:
    def test_returns_dict(self):
        assert isinstance(finetune_agent(_state()), dict)

    def test_current_agent_set(self):
        result = finetune_agent(_state())
        assert result["current_agent"] == "Fine-Tune Agent"

    def test_execution_history_contains_agent(self):
        result = finetune_agent(_state())
        assert "Fine-Tune Agent" in result["execution_history"]

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
            "evaluation_metrics",
            "deployment_url",
        }
        result = finetune_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"


# ---------------------------------------------------------------------------
# Tests: finetune_agent — error path
# ---------------------------------------------------------------------------


class TestFinetuneAgentErrorPath:
    def test_error_sets_failed_status(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker API timeout")

        monkeypatch.setattr("agents.finetune._submit_training_job", _raise)
        result = finetune_agent(_state())
        assert result["training_status"] == "FAILED"

    def test_error_sets_job_id_none(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker API timeout")

        monkeypatch.setattr("agents.finetune._submit_training_job", _raise)
        result = finetune_agent(_state())
        assert result["training_job_id"] is None

    def test_error_sets_model_uri_none(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker API timeout")

        monkeypatch.setattr("agents.finetune._submit_training_job", _raise)
        result = finetune_agent(_state())
        assert result["model_uri"] is None

    def test_error_appends_error_message(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker API timeout")

        monkeypatch.setattr("agents.finetune._submit_training_job", _raise)
        result = finetune_agent(_state())
        assert any("FineTuneAgent" in e for e in result["errors"])

    def test_returns_dict_on_error(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("SageMaker API timeout")

        monkeypatch.setattr("agents.finetune._submit_training_job", _raise)
        assert isinstance(finetune_agent(_state()), dict)
