"""
Smoke tests for the ModifAI LangGraph pipeline.

Test coverage
-------------
- Graph builds without raising.
- Happy path (no OCR): all agents run, deployment_url is set, no errors.
- OCR path: OCR Agent appears in history, extracted_documents populated.
- Validation failure: graph terminates early, downstream fields remain None.
- Execution history completeness checks.
- State field type/value assertions.
"""

from __future__ import annotations

import pytest

from graph.graph_builder import build_graph
from schemas.state_schema import ModifAIInputSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_initial_state(**overrides: object) -> dict:
    """Creates a valid initial state dict with optional field overrides.

    Args:
        **overrides: Field key-value pairs to merge over the defaults.

    Returns:
        A complete initial state dict ready for ``graph.invoke()``.
    """
    schema = ModifAIInputSchema(
        user_prompt="Unit test prompt — generate a QA dataset.",
        uploaded_files=["test_file.txt"],
    )
    state = schema.to_initial_state()
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def compiled_graph():
    """Builds the LangGraph graph once and shares it across the module."""
    return build_graph()


@pytest.fixture(scope="module")
def happy_path_result(compiled_graph):
    """Runs the standard (no-OCR) happy path once and caches the result."""
    return compiled_graph.invoke(_make_initial_state())


@pytest.fixture(scope="module")
def ocr_path_result(compiled_graph):
    """Runs the OCR path once and caches the result."""
    return compiled_graph.invoke(
        _make_initial_state(uploaded_files=["document.pdf"])
    )


# ---------------------------------------------------------------------------
# Test: graph construction
# ---------------------------------------------------------------------------


class TestGraphBuildsSuccessfully:
    def test_build_does_not_raise(self):
        """Graph construction must succeed without exceptions."""
        graph = build_graph()
        assert graph is not None

    def test_multiple_builds_are_independent(self):
        """Each call to build_graph() must return a fresh compiled graph."""
        g1 = build_graph()
        g2 = build_graph()
        assert g1 is not g2


# ---------------------------------------------------------------------------
# Test: happy path (no OCR)
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_pipeline_completes_with_deployment_url(self, happy_path_result):
        """Full happy path must set a non-None deployment_url."""
        assert happy_path_result["deployment_url"] is not None

    def test_deployment_url_is_string(self, happy_path_result):
        """deployment_url must be a string."""
        assert isinstance(happy_path_result["deployment_url"], str)

    def test_no_errors(self, happy_path_result):
        """Happy path must not accumulate any errors."""
        assert happy_path_result["errors"] == []

    def test_validation_passed(self, happy_path_result):
        """validation_status must be True."""
        assert happy_path_result["validation_status"] is True

    def test_quality_score_within_bounds(self, happy_path_result):
        """dataset_quality_score must be in [0, 1]."""
        score = happy_path_result["dataset_quality_score"]
        assert 0.0 <= score <= 1.0

    def test_training_job_id_format(self, happy_path_result):
        """Fine-tune job ID must follow the expected prefix."""
        job_id = happy_path_result["training_job_id"]
        assert job_id is not None
        assert job_id.startswith("modifai-job-")

    def test_training_status_completed(self, happy_path_result):
        """Training status must be COMPLETED on the happy path."""
        assert happy_path_result["training_status"] == "COMPLETED"

    def test_evaluation_metrics_present(self, happy_path_result):
        """Evaluation agent must populate required metric keys."""
        metrics = happy_path_result["evaluation_metrics"]
        for key in ("accuracy", "f1_score", "bleu", "rouge_l"):
            assert key in metrics, f"Missing metric: '{key}'"

    def test_chunks_generated(self, happy_path_result):
        """Chunking agent must produce at least one chunk."""
        assert len(happy_path_result["chunks"]) > 0

    def test_dataset_generated(self, happy_path_result):
        """Generation agent must produce at least one training example."""
        assert len(happy_path_result["generated_dataset"]) > 0

    def test_execution_history_order(self, happy_path_result):
        """Key agents must appear in execution history."""
        history = happy_path_result["execution_history"]
        expected = [
            "Initialize State",
            "Validation Agent",
            "Router",
            "Chunking Agent",        # no OCR → direct to chunking
            "Dataset Generation Agent",
            "Dataset Quality Agent",
            "Fine-Tune Agent",
            "Evaluation Agent",
            "Deployment Agent",
        ]
        for agent in expected:
            assert agent in history, f"'{agent}' missing from execution_history"

    def test_ocr_agent_not_in_no_ocr_path(self, happy_path_result):
        """OCR Agent must NOT appear when uploaded_files has no PDF."""
        assert "OCR Agent" not in happy_path_result["execution_history"]


# ---------------------------------------------------------------------------
# Test: OCR path
# ---------------------------------------------------------------------------


class TestOCRPath:
    def test_ocr_agent_in_history(self, ocr_path_result):
        """OCR Agent must appear in execution_history when a PDF is supplied."""
        assert "OCR Agent" in ocr_path_result["execution_history"]

    def test_extracted_documents_populated(self, ocr_path_result):
        """OCR Agent must produce at least one extracted document."""
        assert len(ocr_path_result["extracted_documents"]) > 0

    def test_ocr_required_flag(self, ocr_path_result):
        """ocr_required must be True when a PDF is uploaded."""
        assert ocr_path_result["ocr_required"] is True

    def test_pipeline_still_completes_on_ocr_path(self, ocr_path_result):
        """OCR path must also reach deployment."""
        assert ocr_path_result["deployment_url"] is not None


# ---------------------------------------------------------------------------
# Test: validation failure path
# ---------------------------------------------------------------------------


class TestValidationFailurePath:
    def test_empty_prompt_fails_validation(self, compiled_graph):
        """Empty user_prompt must set validation_status=False."""
        initial = _make_initial_state(user_prompt="")
        result = compiled_graph.invoke(initial)
        assert result["validation_status"] is False

    def test_no_training_job_on_failure(self, compiled_graph):
        """training_job_id must remain None when validation fails."""
        initial = _make_initial_state(user_prompt="")
        result = compiled_graph.invoke(initial)
        assert result["training_job_id"] is None

    def test_no_deployment_on_failure(self, compiled_graph):
        """deployment_url must remain None when validation fails."""
        initial = _make_initial_state(user_prompt="")
        result = compiled_graph.invoke(initial)
        assert result["deployment_url"] is None

    def test_history_only_has_init_and_validation(self, compiled_graph):
        """On failure, history should only contain initialisation + validation."""
        initial = _make_initial_state(user_prompt="")
        result = compiled_graph.invoke(initial)
        history = result["execution_history"]
        assert "Initialize State" in history
        assert "Validation Agent" in history
        # No downstream agents should have run
        for agent in ("Router", "Chunking Agent", "Fine-Tune Agent"):
            assert agent not in history, f"'{agent}' should not be in history"
