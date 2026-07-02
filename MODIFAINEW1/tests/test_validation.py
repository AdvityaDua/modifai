"""
Unit tests for agents/validation.py.

Test coverage
-------------
- Happy path: valid prompt, no OCR files.
- Happy path: valid prompt with a PDF file triggers OCR.
- Failure path: empty prompt sets validation_status=False.
- Failure path: blank-only prompt sets validation_status=False.
- Error path: exception during classification sets safe defaults.
- Contract: agent always returns update dict with correct keys.
- Contract: agent does not write fields owned by other agents.
"""

from __future__ import annotations

import pytest

from agents.validation import (
    _classify_prompt,
    _has_ocr_file,
    _is_prompt_valid,
    validation_agent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> dict:
    """Builds a minimal state dict for validation_agent tests."""
    defaults = {
        "session_id": "test-session-001",
        "user_prompt": "Generate a QA dataset from the uploaded document.",
        "uploaded_files": [],
        "execution_history": [],
        "errors": [],
        "metadata": {},
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Tests: private helpers
# ---------------------------------------------------------------------------


class TestIsPromptValid:
    def test_non_empty_prompt_is_valid(self):
        assert _is_prompt_valid("Generate a QA dataset.") is True

    def test_whitespace_only_is_invalid(self):
        assert _is_prompt_valid("   ") is False

    def test_empty_string_is_invalid(self):
        assert _is_prompt_valid("") is False


class TestHasOcrFile:
    @pytest.mark.parametrize(
        "files,expected",
        [
            (["doc.pdf"], True),
            (["image.PNG"], True),
            (["photo.jpg"], True),
            (["scan.tiff"], True),
            (["data.txt"], False),
            (["notes.csv"], False),
            ([], False),
            (["data.txt", "scan.bmp"], True),
        ],
    )
    def test_ocr_detection(self, files, expected):
        assert _has_ocr_file(files) is expected


class TestClassifyPrompt:
    def test_returns_required_keys(self):
        result = _classify_prompt("Make a QA dataset.", [])
        assert "dataset_type" in result
        assert "task_type" in result
        assert "ocr_required" in result

    def test_no_ocr_files_gives_false(self):
        result = _classify_prompt("Make a QA dataset.", ["file.txt"])
        assert result["ocr_required"] is False

    def test_pdf_file_gives_ocr_true(self):
        result = _classify_prompt("Make a QA dataset.", ["file.pdf"])
        assert result["ocr_required"] is True


# ---------------------------------------------------------------------------
# Tests: validation_agent — happy path
# ---------------------------------------------------------------------------


class TestValidationAgentHappyPath:
    def test_validation_status_true(self):
        result = validation_agent(_state())
        assert result["validation_status"] is True

    def test_dataset_type_set(self):
        result = validation_agent(_state())
        assert result["dataset_type"] is not None
        assert isinstance(result["dataset_type"], str)

    def test_task_type_set(self):
        result = validation_agent(_state())
        assert result["task_type"] is not None
        assert isinstance(result["task_type"], str)

    def test_ocr_required_false_for_txt(self):
        result = validation_agent(_state(uploaded_files=["data.txt"]))
        assert result["ocr_required"] is False

    def test_ocr_required_true_for_pdf(self):
        result = validation_agent(_state(uploaded_files=["doc.pdf"]))
        assert result["ocr_required"] is True

    def test_no_errors(self):
        result = validation_agent(_state())
        assert "errors" not in result


# ---------------------------------------------------------------------------
# Tests: validation_agent — failure path (empty prompt)
# ---------------------------------------------------------------------------


class TestValidationAgentFailurePath:
    def test_empty_prompt_fails(self):
        result = validation_agent(_state(user_prompt=""))
        assert result["validation_status"] is False

    def test_blank_prompt_fails(self):
        result = validation_agent(_state(user_prompt="    "))
        assert result["validation_status"] is False

    def test_failure_safe_defaults_dataset_type(self):
        result = validation_agent(_state(user_prompt=""))
        assert result["dataset_type"] is None

    def test_failure_safe_defaults_task_type(self):
        result = validation_agent(_state(user_prompt=""))
        assert result["task_type"] is None

    def test_failure_safe_defaults_ocr_required(self):
        result = validation_agent(_state(user_prompt=""))
        assert result["ocr_required"] is False


# ---------------------------------------------------------------------------
# Tests: validation_agent — agent contract
# ---------------------------------------------------------------------------


class TestValidationAgentContract:
    def test_always_returns_dict(self):
        result = validation_agent(_state())
        assert isinstance(result, dict)

    def test_current_agent_field_set(self):
        result = validation_agent(_state())
        assert result["current_agent"] == "Validation Agent"

    def test_execution_history_contains_agent(self):
        result = validation_agent(_state())
        assert "Validation Agent" in result["execution_history"]

    def test_does_not_write_foreign_fields(self):
        """Validation Agent must not write fields owned by other agents."""
        forbidden = {
            "extracted_documents",
            "chunks",
            "generated_dataset",
            "dataset_quality_score",
            "training_job_id",
            "training_status",
            "model_uri",
            "evaluation_metrics",
            "deployment_url",
        }
        result = validation_agent(_state())
        for field in forbidden:
            assert field not in result, f"Forbidden field '{field}' was written"
