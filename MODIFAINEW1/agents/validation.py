"""
Validation Agent — ModifAI Pipeline.

Responsibilities
----------------
* Checks that the user prompt is non-empty and coherent.
* Infers ``dataset_type`` and ``task_type`` from the prompt.
* Detects whether uploaded files require OCR (PDF/image extensions).
* Sets ``validation_status`` to ``True`` (pass) or ``False`` (fail).

Routing consequence
-------------------
If ``validation_status is False`` the graph routes to ``END``.
Otherwise it proceeds to the Router node.

Note
----
Real implementation would call an LLM to classify the prompt and
inspect file types / MIME types for accurate OCR detection.
"""

from typing import List, Optional

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)

# Extensions that require OCR pre-processing
_OCR_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"})


def validation_agent(state: ModifAIState) -> dict:
    """Validates the incoming pipeline request and classifies the task.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("Validation Agent", state, logger)
    update = build_base_update("Validation Agent")

    try:
        user_prompt: str = state.get("user_prompt", "")
        uploaded_files: List[str] = state.get("uploaded_files", [])

        logger.info("Running validation checks...")

        if not _is_prompt_valid(user_prompt):
            logger.warning("Validation FAILED — user_prompt is empty or blank.")
            update["validation_status"] = False
            update["dataset_type"] = None
            update["task_type"] = None
            update["ocr_required"] = False
        else:
            classification = _classify_prompt(user_prompt, uploaded_files)

            logger.info("Validation PASSED.")
            update["validation_status"] = True
            update["dataset_type"] = classification["dataset_type"]
            update["task_type"] = classification["task_type"]
            update["ocr_required"] = classification["ocr_required"]

        logger.info(f"  validation_status : {update.get('validation_status')}")
        logger.info(f"  dataset_type      : {update.get('dataset_type', 'N/A')}")
        logger.info(f"  task_type         : {update.get('task_type', 'N/A')}")
        logger.info(f"  ocr_required      : {update.get('ocr_required', False)}")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Validation Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"ValidationAgent: {exc}"]
        update["validation_status"] = False
        update["dataset_type"] = None
        update["task_type"] = None
        update["ocr_required"] = False

    leave_node("Validation Agent", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_prompt_valid(prompt: str) -> bool:
    """Checks that the user prompt contains meaningful text.

    Args:
        prompt: The raw user-supplied instruction string.

    Returns:
        ``True`` if the prompt is non-empty after stripping whitespace.
    """
    return bool(prompt.strip())


def _has_ocr_file(uploaded_files: List[str]) -> bool:
    """Determines whether any uploaded file requires OCR processing.

    Checks each file path against the known OCR-required extensions.

    Args:
        uploaded_files: List of file paths or URIs supplied by the user.

    Returns:
        ``True`` if at least one file has an OCR-required extension.
    """
    return any(
        any(f.lower().endswith(ext) for ext in _OCR_EXTENSIONS)
        for f in uploaded_files
    )


def _classify_prompt(
    user_prompt: str,  # noqa: ARG001  — used by real LLM impl
    uploaded_files: List[str],
) -> dict:
    """Classifies the pipeline request into dataset type, task type, and OCR flag.

    Stub implementation returns fixed defaults.  The real implementation will
    call an LLM (e.g. Amazon Bedrock Claude) with a classification prompt to
    infer ``dataset_type`` and ``task_type`` from ``user_prompt``, and will
    inspect file MIME types for accurate OCR detection.

    Args:
        user_prompt: The validated, non-empty user instruction.
        uploaded_files: List of file paths or URIs supplied by the user.

    Returns:
        A dict with keys ``dataset_type`` (str), ``task_type`` (str),
        and ``ocr_required`` (bool).
    """
    # TODO: Replace stub with LLM-based classification
    return {
        "dataset_type": "QA",
        "task_type": "text-classification",
        "ocr_required": _has_ocr_file(uploaded_files),
    }


def _build_failure_update(update: dict) -> dict:
    """Populates a validation-failure update with safe field defaults.

    Args:
        update: The base update dict (already contains orchestration fields).

    Returns:
        The same update dict with all Validation Agent fields set to safe values.
    """
    update["validation_status"] = False
    update["dataset_type"] = None
    update["task_type"] = None
    update["ocr_required"] = False
    return update
