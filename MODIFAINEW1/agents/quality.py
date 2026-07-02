"""
Dataset Quality Agent — ModifAI Pipeline.

Responsibilities
----------------
* Evaluates the quality of ``state.generated_dataset``.
* Assigns a quality score between 0.0 and 1.0.
* Populates ``state.dataset_quality_score``.

Routing consequence
-------------------
* Score >= ``settings.QUALITY_THRESHOLD`` → Fine-Tune Agent.
* Score <  ``settings.QUALITY_THRESHOLD`` → Dataset Generation Agent (loop).

Note
----
Real implementation will measure semantic diversity, answer completeness,
question-answer overlap, and coverage of the source documents.
"""

from typing import Any, Dict, List

from config.settings import settings
from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)


def quality_agent(state: ModifAIState) -> dict:
    """Evaluates the quality of the generated training dataset.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("Dataset Quality Agent", state, logger)
    update = build_base_update("Dataset Quality Agent")

    try:
        dataset: List[Dict[str, Any]] = state.get("generated_dataset", [])
        logger.info(
            f"Evaluating quality of {len(dataset)} training example(s)..."
        )

        metadata: dict = _increment_loop_count(state.get("metadata") or {})
        update["metadata"] = metadata

        stub_score: float = state.get("_stub_quality_override", 0.92)
        score: float = _score_dataset(dataset, stub_score)
        update["dataset_quality_score"] = score

        _log_score_result(score)

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Dataset Quality Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"QualityAgent: {exc}"]
        update["dataset_quality_score"] = 0.0

    leave_node("Dataset Quality Agent", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _increment_loop_count(metadata: dict) -> dict:
    """Increments the quality retry loop counter stored in metadata.

    Creates a shallow copy of ``metadata`` so the original is not mutated.
    The counter helps developers spot accidental regeneration loops during
    debugging.

    Args:
        metadata: The current metadata dict from the pipeline state.

    Returns:
        A new dict with ``_quality_loop_count`` incremented by 1.
    """
    updated = dict(metadata)
    updated["_quality_loop_count"] = updated.get("_quality_loop_count", 0) + 1
    return updated


def _score_dataset(
    dataset: List[Dict[str, Any]],
    stub_override: float = 0.92,
) -> float:
    """Computes a quality score for the generated training dataset.

    Stub implementation returns ``stub_override`` directly, ignoring the
    dataset content.  The real implementation will compute:
    - Semantic diversity across QA pairs.
    - ROUGE-L overlap between questions and answers.
    - Source document coverage.
    - LLM-as-judge binary quality labels.

    Args:
        dataset: List of training example dicts to evaluate.
        stub_override: Score to return from the stub.  Override to a low
            value in tests that exercise the quality retry loop.

    Returns:
        A float in [0.0, 1.0] representing overall dataset quality.
    """
    # TODO: Replace stub with real diversity/overlap/coverage metrics
    return float(stub_override)


def _log_score_result(score: float) -> None:
    """Logs whether the quality score meets the configured threshold.

    Args:
        score: The computed dataset quality score.
    """
    if score >= settings.QUALITY_THRESHOLD:
        logger.info(
            f"  Quality score {score:.3f} >= threshold "
            f"{settings.QUALITY_THRESHOLD} --> PASS, proceeding to fine-tuning."
        )
    else:
        logger.warning(
            f"  Quality score {score:.3f} < threshold "
            f"{settings.QUALITY_THRESHOLD} --> FAIL, routing back to generation."
        )
