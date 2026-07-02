"""
Unit tests for agents/chunking.py.

Test coverage
-------------
- Happy path: extracted_documents present → chunks produced.
- Fallback path: no extracted_documents, falls back to uploaded_files.
- Empty fallback: no sources at all → single default chunk.
- Private helper: _split_into_chunks produces expected count.
- Private helper: _resolve_sources prefers extracted_documents.
- Contract: returns only owned fields; no foreign fields.
- Error path: exception in helper → empty list + error recorded.
"""

from __future__ import annotations

import pytest

from agents.chunking import (
    _STUB_CHUNKS_PER_SOURCE,
    _resolve_sources,
    _split_into_chunks,
    chunking_agent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for chunking_agent tests."""
    defaults = {
        "session_id": "test-session-chunking",
        "extracted_documents": [
            "Extracted text from document 1.",
            "Extracted text from document 2.",
        ],
        "uploaded_files": ["doc1.pdf", "doc2.pdf"],
        "execution_history": [],
        "errors": [],
        "metadata": {},
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Tests: private helpers
# ---------------------------------------------------------------------------


class TestSplitIntoChunks:
    def test_produces_chunks_per_source(self):
        sources = ["source a", "source b"]
        chunks = _split_into_chunks(sources, chunks_per_source=3)
        assert len(chunks) == 6

    def test_empty_sources_returns_default(self):
        chunks = _split_into_chunks([])
        assert len(chunks) == 1
        assert "STUB" in chunks[0] or "default" in chunks[0].lower()

    def test_each_chunk_is_string(self):
        chunks = _split_into_chunks(["some text"])
        assert all(isinstance(c, str) for c in chunks)

    def test_default_chunks_per_source_constant(self):
        """Ensure the module constant is what the function uses by default."""
        sources = ["one source"]
        chunks = _split_into_chunks(sources)
        assert len(chunks) == _STUB_CHUNKS_PER_SOURCE


class TestResolveSources:
    def test_prefers_extracted_documents(self):
        state = _state(
            extracted_documents=["doc text"],
            uploaded_files=["file.txt"],
        )
        sources = _resolve_sources(state)
        assert sources == ["doc text"]

    def test_falls_back_to_uploaded_files(self):
        state = _state(extracted_documents=[])
        sources = _resolve_sources(state)
        assert sources == state["uploaded_files"]

    def test_empty_state_returns_empty_list(self):
        state = _state(extracted_documents=[], uploaded_files=[])
        sources = _resolve_sources(state)
        assert sources == []


# ---------------------------------------------------------------------------
# Tests: chunking_agent — happy path
# ---------------------------------------------------------------------------


class TestChunkingAgentHappyPath:
    def test_chunks_populated(self):
        result = chunking_agent(_state())
        assert len(result["chunks"]) > 0

    def test_chunks_are_strings(self):
        result = chunking_agent(_state())
        assert all(isinstance(c, str) for c in result["chunks"])

    def test_chunk_count_matches_sources(self):
        state = _state(extracted_documents=["source 1"])
        result = chunking_agent(state)
        assert len(result["chunks"]) == _STUB_CHUNKS_PER_SOURCE

    def test_no_errors_on_happy_path(self):
        result = chunking_agent(_state())
        assert "errors" not in result


# ---------------------------------------------------------------------------
# Tests: chunking_agent — fallback path
# ---------------------------------------------------------------------------


class TestChunkingAgentFallbackPath:
    def test_fallback_uses_uploaded_files(self):
        state = _state(extracted_documents=[], uploaded_files=["file.txt"])
        result = chunking_agent(state)
        assert len(result["chunks"]) > 0

    def test_no_sources_gives_default_chunk(self):
        state = _state(extracted_documents=[], uploaded_files=[])
        result = chunking_agent(state)
        assert len(result["chunks"]) == 1


# ---------------------------------------------------------------------------
# Tests: chunking_agent — contract
# ---------------------------------------------------------------------------


class TestChunkingAgentContract:
    def test_returns_dict(self):
        assert isinstance(chunking_agent(_state()), dict)

    def test_current_agent_set(self):
        result = chunking_agent(_state())
        assert result["current_agent"] == "Chunking Agent"

    def test_execution_history_contains_agent(self):
        result = chunking_agent(_state())
        assert "Chunking Agent" in result["execution_history"]

    def test_does_not_write_foreign_fields(self):
        forbidden = {
            "validation_status",
            "dataset_type",
            "task_type",
            "ocr_required",
            "extracted_documents",
            "generated_dataset",
            "dataset_quality_score",
            "training_job_id",
            "training_status",
            "model_uri",
            "evaluation_metrics",
            "deployment_url",
        }
        result = chunking_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"


# ---------------------------------------------------------------------------
# Tests: chunking_agent — error path
# ---------------------------------------------------------------------------


class TestChunkingAgentErrorPath:
    def test_error_gives_empty_chunks(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise ValueError("Simulated split failure")

        monkeypatch.setattr("agents.chunking._split_into_chunks", _raise)
        result = chunking_agent(_state())
        assert result["chunks"] == []

    def test_error_appends_error_message(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise ValueError("Simulated split failure")

        monkeypatch.setattr("agents.chunking._split_into_chunks", _raise)
        result = chunking_agent(_state())
        assert any("ChunkingAgent" in e for e in result["errors"])

    def test_returns_dict_on_error(self, monkeypatch):
        def _raise(*_a, **_kw):
            raise ValueError("Simulated split failure")

        monkeypatch.setattr("agents.chunking._split_into_chunks", _raise)
        assert isinstance(chunking_agent(_state()), dict)
