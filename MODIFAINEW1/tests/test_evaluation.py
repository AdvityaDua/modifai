"""
Unit tests for agents/evaluation.py.

Test coverage
-------------
- Happy path: all expected metric keys present, eval_pass=True.
- Metric value ranges: accuracy, f1_score, bleu, rouge_l all in [0, 1].
- Private helper: _run_evaluation returns expected structure.
- Contract: returns only owned fields; no foreign fields.
- Error path: eval_pass=False, accuracy=0.0 on exception.
"""

from __future__ import annotations

import pytest

from agents.evaluation import _run_evaluation, evaluation_agent
from config.settings import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for evaluation_agent tests."""
    defaults = {
        "session_id": "test-session-eval",
        "model_uri": "s3://modifai-models/stub/modifai-job-abc12345/model.tar.gz",
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


class TestRunEvaluation:
    def test_returns_dict(self):
        assert isinstance(_run_evaluation("s3://bucket/model", "text-classification"), dict)

    def test_required_metric_keys(self):
        metrics = _run_evaluation("s3://bucket/model", "text-classification")
        for key in ("accuracy", "f1_score", "bleu", "rouge_l", "eval_pass"):
            assert key in metrics, f"Missing key: '{key}'"

    def test_eval_pass_is_bool(self):
        metrics = _run_evaluation("s3://bucket/model", "text-classification")
        assert isinstance(metrics["eval_pass"], bool)

    def test_default_eval_passes(self):
        metrics = _run_evaluation("s3://bucket/model", "text-classification")
        assert metrics["eval_pass"] is True
        assert metrics["accuracy"] >= settings.EVAL_PASS_THRESHOLD


# ---------------------------------------------------------------------------
# Tests: evaluation_agent — happy path
# ---------------------------------------------------------------------------


class TestEvaluationAgentHappyPath:
    def test_evaluation_metrics_set(self):
        result = evaluation_agent(_state())
        assert "evaluation_metrics" in result

    def test_all_required_metric_keys_present(self):
        result = evaluation_agent(_state())
        metrics = result["evaluation_metrics"]
        for key in ("accuracy", "f1_score", "bleu", "rouge_l"):
            assert key in metrics, f"Missing metric: '{key}'"

    def test_eval_pass_is_true_on_happy_path(self):
        result = evaluation_agent(_state())
        assert result["evaluation_metrics"]["eval_pass"] is True

    def test_accuracy_above_threshold(self):
        result = evaluation_agent(_state())
        accuracy = result["evaluation_metrics"]["accuracy"]
        assert accuracy >= settings.EVAL_PASS_THRESHOLD

    @pytest.mark.parametrize("metric", ["accuracy", "f1_score", "bleu", "rouge_l"])
    def test_metric_in_valid_range(self, metric):
        result = evaluation_agent(_state())
        value = result["evaluation_metrics"][metric]
        assert 0.0 <= value <= 1.0, f"Metric '{metric}' out of [0,1] range: {value}"

    def test_no_errors_on_happy_path(self):
        result = evaluation_agent(_state())
        assert "errors" not in result


# ---------------------------------------------------------------------------
# Tests: evaluation_agent — contract
# ---------------------------------------------------------------------------


class TestEvaluationAgentContract:
    def test_returns_dict(self):
        assert isinstance(evaluation_agent(_state()), dict)

    def test_current_agent_set(self):
        result = evaluation_agent(_state())
        assert result["current_agent"] == "Evaluation Agent"

    def test_execution_history_contains_agent(self):
        result = evaluation_agent(_state())
        assert "Evaluation Agent" in result["execution_history"]

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
            "deployment_url",
        }
        result = evaluation_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"


# ---------------------------------------------------------------------------
# Tests: evaluation_agent — error path
# ---------------------------------------------------------------------------


class TestEvaluationAgentErrorPath:
    def test_error_sets_eval_pass_false(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("Batch transform failed")

        monkeypatch.setattr("agents.evaluation._run_evaluation", _raise)
        result = evaluation_agent(_state())
        assert result["evaluation_metrics"]["eval_pass"] is False

    def test_error_sets_accuracy_zero(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("Batch transform failed")

        monkeypatch.setattr("agents.evaluation._run_evaluation", _raise)
        result = evaluation_agent(_state())
        assert result["evaluation_metrics"]["accuracy"] == pytest.approx(0.0)

    def test_error_appends_error_message(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("Batch transform failed")

        monkeypatch.setattr("agents.evaluation._run_evaluation", _raise)
        result = evaluation_agent(_state())
        assert any("EvaluationAgent" in e for e in result["errors"])

    def test_returns_dict_on_error(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("Batch transform failed")

        monkeypatch.setattr("agents.evaluation._run_evaluation", _raise)
        assert isinstance(evaluation_agent(_state()), dict)
