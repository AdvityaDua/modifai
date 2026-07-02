"""
Unit tests for agents/generation.py.

Test coverage
-------------
- Happy path: chunks provided → one training example per chunk.
- Fallback path: empty chunks → default fallback dataset returned.
- Private helper: _generate_qa_pair produces expected keys.
- Private helper: _generate_dataset returns list with correct count.
- Contract: returns only owned fields; no foreign fields.
- Error path: exception in helper → empty list + error recorded.
"""

from __future__ import annotations

import pytest

from agents.generation import (
    _generate_dataset,
    _generate_qa_pair,
    generation_agent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for generation_agent tests."""
    defaults = {
        "session_id": "test-session-gen",
        "chunks": [
            "[CHUNK STUB] src=1 chunk=1 | Some extracted content...",
            "[CHUNK STUB] src=1 chunk=2 | Some extracted content...",
            "[CHUNK STUB] src=1 chunk=3 | Some extracted content...",
        ],
        "dataset_type": "QA",
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


class TestGenerateQaPair:
    def test_returns_dict(self):
        result = _generate_qa_pair(0, "Some chunk text.", "QA")
        assert isinstance(result, dict)

    def test_required_keys_present(self):
        result = _generate_qa_pair(0, "Some chunk text.", "QA")
        for key in ("id", "chunk_source", "question", "answer", "dataset_type"):
            assert key in result, f"Missing key: '{key}'"

    def test_id_matches_index(self):
        result = _generate_qa_pair(3, "text", "QA")
        assert result["id"] == 3

    def test_dataset_type_propagated(self):
        result = _generate_qa_pair(0, "text", "instruction")
        assert result["dataset_type"] == "instruction"

    def test_chunk_source_truncated_to_100(self):
        long_chunk = "x" * 200
        result = _generate_qa_pair(0, long_chunk, "QA")
        assert len(result["chunk_source"]) <= 100


class TestGenerateDataset:
    def test_one_example_per_chunk(self):
        chunks = ["chunk a", "chunk b", "chunk c"]
        dataset = _generate_dataset(chunks, "QA")
        assert len(dataset) == 3

    def test_empty_chunks_returns_default(self):
        dataset = _generate_dataset([], "QA")
        assert len(dataset) >= 1

    def test_each_example_is_dict(self):
        dataset = _generate_dataset(["chunk 1"], "QA")
        assert all(isinstance(ex, dict) for ex in dataset)


# ---------------------------------------------------------------------------
# Tests: generation_agent — happy path
# ---------------------------------------------------------------------------


class TestGenerationAgentHappyPath:
    def test_generated_dataset_populated(self):
        result = generation_agent(_state())
        assert len(result["generated_dataset"]) > 0

    def test_one_example_per_chunk(self):
        chunks = ["c1", "c2", "c3", "c4"]
        result = generation_agent(_state(chunks=chunks))
        assert len(result["generated_dataset"]) == 4

    def test_each_example_has_required_keys(self):
        result = generation_agent(_state())
        for ex in result["generated_dataset"]:
            for key in ("id", "question", "answer", "dataset_type"):
                assert key in ex, f"Missing key '{key}' in example"

    def test_no_errors_on_happy_path(self):
        result = generation_agent(_state())
        assert "errors" not in result


# ---------------------------------------------------------------------------
# Tests: generation_agent — fallback path (empty chunks)
# ---------------------------------------------------------------------------


class TestGenerationAgentFallbackPath:
    def test_empty_chunks_gives_fallback(self):
        result = generation_agent(_state(chunks=[]))
        assert len(result["generated_dataset"]) >= 1

    def test_fallback_dataset_is_list_of_dicts(self):
        result = generation_agent(_state(chunks=[]))
        assert isinstance(result["generated_dataset"], list)
        assert all(isinstance(ex, dict) for ex in result["generated_dataset"])


# ---------------------------------------------------------------------------
# Tests: generation_agent — contract
# ---------------------------------------------------------------------------


class TestGenerationAgentContract:
    def test_returns_dict(self):
        assert isinstance(generation_agent(_state()), dict)

    def test_current_agent_set(self):
        result = generation_agent(_state())
        assert result["current_agent"] == "Dataset Generation Agent"

    def test_execution_history_contains_agent(self):
        result = generation_agent(_state())
        assert "Dataset Generation Agent" in result["execution_history"]

    def test_does_not_write_foreign_fields(self):
        forbidden = {
            "validation_status",
            "dataset_type",
            "task_type",
            "ocr_required",
            "extracted_documents",
            "chunks",
            "dataset_quality_score",
            "training_job_id",
            "training_status",
            "model_uri",
            "evaluation_metrics",
            "deployment_url",
        }
        result = generation_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"


# ---------------------------------------------------------------------------
# Tests: generation_agent — error path
# ---------------------------------------------------------------------------


class TestGenerationAgentErrorPath:
    def test_error_gives_empty_dataset(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("LLM call failed")

        monkeypatch.setattr("agents.generation._generate_dataset", _raise)
        result = generation_agent(_state())
        assert result["generated_dataset"] == []

    def test_error_appends_error_message(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("LLM call failed")

        monkeypatch.setattr("agents.generation._generate_dataset", _raise)
        result = generation_agent(_state())
        assert any("GenerationAgent" in e for e in result["errors"])

    def test_returns_dict_on_error(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise RuntimeError("LLM call failed")

        monkeypatch.setattr("agents.generation._generate_dataset", _raise)
        assert isinstance(generation_agent(_state()), dict)
