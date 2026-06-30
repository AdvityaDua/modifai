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

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)

# Extensions that require OCR pre-processing
_OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


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
        uploaded_files: list = state.get("uploaded_files", [])

        logger.info("Running validation checks...")

        # --- Check 1: prompt must be non-empty ---
        is_valid = bool(user_prompt.strip())

        if not is_valid:
            logger.warning("Validation FAILED — user_prompt is empty or blank.")
            update["validation_status"] = False
        else:
            # --- Stub classification logic ---
            # Real implementation: LLM call to classify prompt intent
            has_ocr_file = any(
                any(f.lower().endswith(ext) for ext in _OCR_EXTENSIONS)
                for f in uploaded_files
            )

            logger.info("Validation PASSED.")
            update.update(
                {
                    "validation_status": True,
                    "dataset_type": "QA",
                    "task_type": "text-classification",
                    "ocr_required": has_ocr_file,
                }
            )

        # Log resolved fields
        logger.info(f"  validation_status : {update.get('validation_status')}")
        logger.info(f"  dataset_type      : {update.get('dataset_type', 'N/A')}")
        logger.info(f"  task_type         : {update.get('task_type', 'N/A')}")
        logger.info(f"  ocr_required      : {update.get('ocr_required', False)}")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Validation Agent: {exc}", exc_info=True
        )
        update["validation_status"] = False
        update["errors"] = [f"ValidationAgent: {exc}"]

    leave_node("Validation Agent", update, logger)
    return update
