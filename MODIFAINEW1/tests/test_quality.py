"""
Unit tests for agents/quality.py.

Test coverage
-------------
- Happy path: score >= threshold → dataset_quality_score set correctly.
- Low score path: override to < threshold → score recorded faithfully.
- Loop counter: _quality_loop_count increments on each call.
- Private helper: _score_dataset returns the stub override value.
- Private helper: _increment_loop_count increments correctly.
- Contract: returns only owned fields; no foreign fields.
- Error path: exception in helper → score=0.0 + error recorded.
"""

from __future__ import annotations

import pytest

from agents.quality import (
    _increment_loop_count,
    _score_dataset,
    quality_agent,
)
from config.settings import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for quality_agent tests."""
    defaults = {
        "session_id": "test-session-quality",
        "generated_dataset": [
            {"id": 0, "question": "Q1", "answer": "A1", "dataset_type": "QA"},
            {"id": 1, "question": "Q2", "answer": "A2", "dataset_type": "QA"},
        ],
        "execution_history": [],
        "errors": [],
        "metadata": {},
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Tests: private helpers
# ---------------------------------------------------------------------------


class TestScoreDataset:
    def test_returns_stub_override(self):
        score = _score_dataset([], stub_override=0.75)
        assert score == pytest.approx(0.75)

    def test_default_stub_above_threshold(self):
        score = _score_dataset([{"id": 0}])
        assert score >= settings.QUALITY_THRESHOLD

    def test_returns_float(self):
        assert isinstance(_score_dataset([]), float)


class TestIncrementLoopCount:
    def test_starts_at_one_from_empty(self):
        result = _increment_loop_count({})
        assert result["_quality_loop_count"] == 1

    def test_increments_existing_count(self):
        result = _increment_loop_count({"_quality_loop_count": 4})
        assert result["_quality_loop_count"] == 5

    def test_does_not_mutate_input(self):
        original = {"_quality_loop_count": 2}
        _increment_loop_count(original)
        assert original["_quality_loop_count"] == 2


# ---------------------------------------------------------------------------
# Tests: quality_agent — happy path (score above threshold)
# ---------------------------------------------------------------------------


class TestQualityAgentHappyPath:
    def test_score_set(self):
        result = quality_agent(_state())
        assert "dataset_quality_score" in result

    def test_score_in_valid_range(self):
        result = quality_agent(_state())
        assert 0.0 <= result["dataset_quality_score"] <= 1.0

    def test_score_above_threshold_by_default(self):
        result = quality_agent(_state())
        assert result["dataset_quality_score"] >= settings.QUALITY_THRESHOLD

    def test_no_errors_on_happy_path(self):
        result = quality_agent(_state())
        assert "errors" not in result

    def test_loop_count_initialized(self):
        result = quality_agent(_state())
        assert result["metadata"]["_quality_loop_count"] == 1


# ---------------------------------------------------------------------------
# Tests: quality_agent — low score path (override below threshold)
# ---------------------------------------------------------------------------


class TestQualityAgentLowScorePath:
    def test_low_score_recorded(self):
        result = quality_agent(_state(**{"_stub_quality_override": 0.50}))
        assert result["dataset_quality_score"] == pytest.approx(0.50)

    def test_low_score_below_threshold(self):
        result = quality_agent(_state(**{"_stub_quality_override": 0.10}))
        assert result["dataset_quality_score"] < settings.QUALITY_THRESHOLD


# ---------------------------------------------------------------------------
# Tests: quality_agent — loop counter increments
# ---------------------------------------------------------------------------


class TestQualityAgentLoopCounter:
    def test_loop_count_starts_at_1(self):
        result = quality_agent(_state(metadata={}))
        assert result["metadata"]["_quality_loop_count"] == 1

    def test_loop_count_increments_on_second_run(self):
        first = quality_agent(_state(metadata={}))
        second = quality_agent(_state(metadata=first["metadata"]))
        assert second["metadata"]["_quality_loop_count"] == 2


# ---------------------------------------------------------------------------
# Tests: quality_agent — contract
# ---------------------------------------------------------------------------


class TestQualityAgentContract:
    def test_returns_dict(self):
        assert isinstance(quality_agent(_state()), dict)

    def test_current_agent_set(self):
        result = quality_agent(_state())
        assert result["current_agent"] == "Dataset Quality Agent"

    def test_execution_history_contains_agent(self):
        result = quality_agent(_state())
        assert "Dataset Quality Agent" in result["execution_history"]

    def test_does_not_write_foreign_fields(self):
        forbidden = {
            "validation_status",
            "dataset_type",
            "task_type",
            "ocr_required",
            "extracted_documents",
            "chunks",
            "generated_dataset",
            "training_job_id",
            "training_status",
            "model_uri",
            "evaluation_metrics",
            "deployment_url",
        }
        result = quality_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"


# ---------------------------------------------------------------------------
# Tests: quality_agent — error path
# ---------------------------------------------------------------------------


class TestQualityAgentErrorPath:
    def test_error_gives_zero_score(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("Simulated scoring failure")

        monkeypatch.setattr("agents.quality._score_dataset", _raise)
        result = quality_agent(_state())
        assert result["dataset_quality_score"] == pytest.approx(0.0)

    def test_error_appends_error_message(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("Simulated scoring failure")

        monkeypatch.setattr("agents.quality._score_dataset", _raise)
        result = quality_agent(_state())
        assert any("QualityAgent" in e for e in result["errors"])

    def test_returns_dict_on_error(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("Simulated scoring failure")

        monkeypatch.setattr("agents.quality._score_dataset", _raise)
        assert isinstance(quality_agent(_state()), dict)
