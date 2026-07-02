"""
Unit tests for agents/ocr.py.

Test coverage
-------------
- Happy path: files provided → extracted_documents populated.
- Fallback path: no files → single placeholder document.
- Contract: returns only owned fields; no foreign fields.
- Error path: exception in helper → empty list + error recorded.
"""

from __future__ import annotations

import pytest

from agents.ocr import _extract_text_from_file, _extract_text_from_files, ocr_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for ocr_agent tests."""
    defaults = {
        "session_id": "test-session-ocr",
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


class TestExtractTextFromFile:
    def test_returns_string(self):
        result = _extract_text_from_file("test.pdf")
        assert isinstance(result, str)

    def test_contains_file_path(self):
        result = _extract_text_from_file("my_document.pdf")
        assert "my_document.pdf" in result

    def test_non_empty(self):
        result = _extract_text_from_file("test.pdf")
        assert len(result) > 0


class TestExtractTextFromFiles:
    def test_one_result_per_file(self):
        files = ["a.pdf", "b.png", "c.jpg"]
        results = _extract_text_from_files(files)
        assert len(results) == len(files)

    def test_empty_files_returns_placeholder(self):
        results = _extract_text_from_files([])
        assert len(results) == 1
        assert "STUB" in results[0] or "placeholder" in results[0].lower()

    def test_each_result_is_string(self):
        results = _extract_text_from_files(["a.pdf"])
        assert all(isinstance(r, str) for r in results)


# ---------------------------------------------------------------------------
# Tests: ocr_agent — happy path
# ---------------------------------------------------------------------------


class TestOcrAgentHappyPath:
    def test_extracted_documents_populated(self):
        result = ocr_agent(_state(uploaded_files=["doc.pdf", "img.png"]))
        assert len(result["extracted_documents"]) == 2

    def test_extracted_documents_are_strings(self):
        result = ocr_agent(_state(uploaded_files=["doc.pdf"]))
        assert all(isinstance(d, str) for d in result["extracted_documents"])

    def test_no_errors_on_happy_path(self):
        result = ocr_agent(_state())
        assert "errors" not in result


# ---------------------------------------------------------------------------
# Tests: ocr_agent — fallback path (no files)
# ---------------------------------------------------------------------------


class TestOcrAgentFallbackPath:
    def test_placeholder_when_no_files(self):
        result = ocr_agent(_state(uploaded_files=[]))
        assert len(result["extracted_documents"]) == 1

    def test_placeholder_is_string(self):
        result = ocr_agent(_state(uploaded_files=[]))
        assert isinstance(result["extracted_documents"][0], str)


# ---------------------------------------------------------------------------
# Tests: ocr_agent — contract
# ---------------------------------------------------------------------------


class TestOcrAgentContract:
    def test_always_returns_dict(self):
        assert isinstance(ocr_agent(_state()), dict)

    def test_current_agent_set(self):
        result = ocr_agent(_state())
        assert result["current_agent"] == "OCR Agent"

    def test_execution_history_contains_agent(self):
        result = ocr_agent(_state())
        assert "OCR Agent" in result["execution_history"]

    def test_does_not_write_foreign_fields(self):
        forbidden = {
            "validation_status",
            "dataset_type",
            "task_type",
            "ocr_required",
            "chunks",
            "generated_dataset",
            "dataset_quality_score",
            "training_job_id",
            "training_status",
            "model_uri",
            "evaluation_metrics",
            "deployment_url",
        }
        result = ocr_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"


# ---------------------------------------------------------------------------
# Tests: ocr_agent — error path
# ---------------------------------------------------------------------------


class TestOcrAgentErrorPath:
    def test_error_sets_empty_extracted_documents(self, monkeypatch):
        """Simulate an exception inside the extraction helper."""

        def _raise(*_args, **_kwargs):
            raise RuntimeError("Simulated OCR failure")

        monkeypatch.setattr(
            "agents.ocr._extract_text_from_files", _raise
        )
        result = ocr_agent(_state())
        assert result["extracted_documents"] == []

    def test_error_appends_error_message(self, monkeypatch):
        def _raise(*_args, **_kwargs):
            raise RuntimeError("Simulated OCR failure")

        monkeypatch.setattr(
            "agents.ocr._extract_text_from_files", _raise
        )
        result = ocr_agent(_state())
        assert any("OCRAgent" in e for e in result["errors"])

    def test_still_returns_dict_on_error(self, monkeypatch):
        def _raise(*_args, **_kwargs):
            raise RuntimeError("Simulated OCR failure")

        monkeypatch.setattr(
            "agents.ocr._extract_text_from_files", _raise
        )
        result = ocr_agent(_state())
        assert isinstance(result, dict)
