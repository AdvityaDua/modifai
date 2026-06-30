"""
Evaluation Agent — ModifAI Pipeline.

Responsibilities
----------------
* Evaluates the fine-tuned model against a held-out test set.
* Populates ``state.evaluation_metrics``.

Routing consequence
-------------------
* Metrics acceptable (accuracy ≥ threshold AND ``eval_pass`` is True)
  → Deployment Agent.
* Metrics unacceptable → Fine-Tune Agent (retry loop).

Note
----
Real implementation will run batch inference on a held-out test set
and compute accuracy, F1, BLEU, ROUGE-L, etc.
"""

from typing import Any, Dict

from config.settings import settings
from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)


def evaluation_agent(state: ModifAIState) -> dict:
    """Evaluates the quality of the fine-tuned model.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("Evaluation Agent", state, logger)
    update = build_base_update("Evaluation Agent")

    try:
        model_uri: str = state.get("model_uri", "N/A") or "N/A"
        logger.info(f"Evaluating model artefact: {model_uri}")

        # Stub metrics — all above threshold to allow the happy path
        # Real impl: SageMaker batch transform + metric computation
        metrics: Dict[str, Any] = {
            "accuracy": 0.92,
            "f1_score": 0.91,
            "bleu": 0.88,
            "rouge_l": 0.89,
            # Convenience flag read by route_after_evaluation()
            "eval_pass": True,
        }

        update["evaluation_metrics"] = metrics

        accuracy = metrics["accuracy"]
        if accuracy >= settings.EVAL_PASS_THRESHOLD and metrics["eval_pass"]:
            logger.info(
                f"  Evaluation PASSED "
                f"(accuracy={accuracy:.2f} >= {settings.EVAL_PASS_THRESHOLD})."
            )
        else:
            logger.warning(
                f"  Evaluation FAILED "
                f"(accuracy={accuracy:.2f} < {settings.EVAL_PASS_THRESHOLD}) "
                "--> routing back to fine-tuning."
            )

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Evaluation Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"EvaluationAgent: {exc}"]
        update["evaluation_metrics"] = {"eval_pass": False, "accuracy": 0.0}

    leave_node("Evaluation Agent", update, logger)
    return update
