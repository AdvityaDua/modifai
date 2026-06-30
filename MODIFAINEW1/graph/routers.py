"""
Conditional routing functions for the ModifAI LangGraph pipeline.

Design principles
-----------------
* Every function is **pure** — it only reads from the state and returns a
  string that maps to a node name via the ``add_conditional_edges`` mapping
  dict in ``graph_builder.py``.
* No business logic lives here.  Routing decisions are based solely on
  state field values set by the upstream agents.
* Return type literals are used so that mis-typed route strings are caught
  by static analysis tools.

The four routing points in the graph
-------------------------------------
1. ``route_after_validation``  — proceed or terminate early.
2. ``route_after_router``      — OCR path vs. direct chunking path.
3. ``route_after_quality``     — fine-tune or regenerate dataset.
4. ``route_after_evaluation``  — deploy or re-train.
"""

from typing import Literal

from config.settings import settings
from graph.state import ModifAIState
from utils.logger import get_logger

logger = get_logger(__name__)


def route_after_validation(
    state: ModifAIState,
) -> Literal["proceed", "end"]:
    """Routes based on whether the Validation Agent passed.

    Args:
        state: The current pipeline state.

    Returns:
        ``"proceed"`` if ``validation_status`` is ``True``,
        ``"end"`` otherwise.
    """
    validation_status: bool = state.get("validation_status", False)
    if validation_status:
        logger.info("[ROUTER] Validation passed --> Router node.")
        return "proceed"
    logger.warning("[ROUTER] Validation failed --> END.")
    return "end"


def route_after_router(
    state: ModifAIState,
) -> Literal["ocr", "chunking"]:
    """Routes based on whether OCR is required.

    Args:
        state: The current pipeline state.

    Returns:
        ``"ocr"`` if ``ocr_required`` is ``True``, ``"chunking"`` otherwise.
    """
    ocr_required: bool = state.get("ocr_required", False)
    if ocr_required:
        logger.info("[ROUTER] OCR required --> OCR Agent.")
        return "ocr"
    logger.info("[ROUTER] No OCR needed --> Chunking Agent.")
    return "chunking"


def route_after_quality(
    state: ModifAIState,
) -> Literal["finetune", "regenerate"]:
    """Routes based on whether the dataset quality score meets the threshold.

    Args:
        state: The current pipeline state.

    Returns:
        ``"finetune"`` if the score is acceptable,
        ``"regenerate"`` to loop back to Dataset Generation.
    """
    score: float = state.get("dataset_quality_score", 0.0)
    if score >= settings.QUALITY_THRESHOLD:
        logger.info(
            f"[ROUTER] Quality {score:.3f} >= {settings.QUALITY_THRESHOLD}"
            " --> Fine-Tune Agent."
        )
        return "finetune"
    logger.warning(
        f"[ROUTER] Quality {score:.3f} < {settings.QUALITY_THRESHOLD}"
        " --> Dataset Generation Agent (retry)."
    )
    return "regenerate"


def route_after_evaluation(
    state: ModifAIState,
) -> Literal["deploy", "retrain"]:
    """Routes based on whether model evaluation metrics are acceptable.

    Checks both the convenience ``eval_pass`` flag and the raw ``accuracy``
    value against ``settings.EVAL_PASS_THRESHOLD``.

    Args:
        state: The current pipeline state.

    Returns:
        ``"deploy"`` if metrics are acceptable,
        ``"retrain"`` to loop back to Fine-Tune Agent.
    """
    metrics: dict = state.get("evaluation_metrics", {})
    accuracy: float = metrics.get("accuracy", 0.0)
    eval_pass: bool = metrics.get("eval_pass", False)

    if eval_pass and accuracy >= settings.EVAL_PASS_THRESHOLD:
        logger.info(
            f"[ROUTER] Evaluation passed (accuracy={accuracy:.2f})"
            " --> Deployment Agent."
        )
        return "deploy"
    logger.warning(
        f"[ROUTER] Evaluation failed (accuracy={accuracy:.2f})"
        " --> Fine-Tune Agent (retry)."
    )
    return "retrain"
