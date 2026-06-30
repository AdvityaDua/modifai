"""
Dataset Quality Agent — ModifAI Pipeline.

Responsibilities
----------------
* Evaluates the quality of ``state.generated_dataset``.
* Assigns a quality score between 0.0 and 1.0.
* Populates ``state.dataset_quality_score``.

Routing consequence
-------------------
* Score ≥ ``settings.QUALITY_THRESHOLD`` → Fine-Tune Agent.
* Score <  ``settings.QUALITY_THRESHOLD`` → Dataset Generation Agent (loop).

Note
----
Real implementation will measure semantic diversity, answer completeness,
question-answer overlap, and coverage of the source documents.
"""

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
        dataset = state.get("generated_dataset", [])
        logger.info(
            f"Evaluating quality of {len(dataset)} training example(s)..."
        )

        # Stub scoring: fixed passing score for demo/testing.
        # Increment a loop counter so developers can spot accidental loops.
        # Real impl: diversity metrics, ROUGE overlap, LLM-as-judge.
        metadata: dict = dict(state.get("metadata") or {})
        quality_loop_count: int = metadata.get("_quality_loop_count", 0) + 1
        metadata["_quality_loop_count"] = quality_loop_count
        update["metadata"] = metadata

        # Default stub score is always above threshold so the demo completes.
        # Override to a low value in tests that exercise the retry loop.
        stub_score: float = state.get("_stub_quality_override", 0.92)
        update["dataset_quality_score"] = stub_score

        if stub_score >= settings.QUALITY_THRESHOLD:
            logger.info(
                f"  Quality score {stub_score:.3f} >= threshold "
                f"{settings.QUALITY_THRESHOLD} --> PASS, proceeding to fine-tuning."
            )
        else:
            logger.warning(
                f"  Quality score {stub_score:.3f} < threshold "
                f"{settings.QUALITY_THRESHOLD} --> FAIL, routing back to generation."
            )

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Dataset Quality Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"QualityAgent: {exc}"]
        update["dataset_quality_score"] = 0.0

    leave_node("Dataset Quality Agent", update, logger)
    return update
