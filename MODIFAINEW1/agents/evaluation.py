"""
Evaluation Agent — ModifAI Pipeline.

Responsibilities
----------------
* Evaluates the fine-tuned model against a held-out test set.
* Populates ``state.evaluation_metrics``.

Routing consequence
-------------------
* Metrics acceptable (accuracy >= threshold AND ``eval_pass`` is True)
  → Deployment Agent.
* Metrics unacceptable → Fine-Tune Agent (retry loop).

Note
----
Real implementation will run batch inference on a held-out test set
and compute accuracy, F1, BLEU, ROUGE-L, etc.
"""

from typing import Any, Dict, Optional

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
        model_uri: Optional[str] = state.get("model_uri") or "N/A"
        task_type: Optional[str] = state.get("task_type") or "N/A"

        logger.info(f"Evaluating model artefact: {model_uri}")

        metrics: Dict[str, Any] = _run_evaluation(model_uri, task_type)
        update["evaluation_metrics"] = metrics

        _log_evaluation_result(metrics)

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Evaluation Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"EvaluationAgent: {exc}"]
        update["evaluation_metrics"] = {"eval_pass": False, "accuracy": 0.0}

    leave_node("Evaluation Agent", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _run_evaluation(
    model_uri: str,  # noqa: ARG001  — used by real SageMaker impl
    task_type: str,  # noqa: ARG001  — used by real SageMaker impl
) -> Dict[str, Any]:
    """Runs batch evaluation of the fine-tuned model.

    Stub implementation returns a fixed set of above-threshold metrics so the
    happy path completes without external dependencies.  The real
    implementation will:
    - Run SageMaker batch transform on a held-out test dataset.
    - Download the prediction output from S3.
    - Compute accuracy, F1, BLEU, and ROUGE-L against ground-truth labels.

    Args:
        model_uri: S3 URI of the trained model artefact to evaluate.
        task_type: ML task category determining which metrics to compute.

    Returns:
        A dict mapping metric names to float values, plus the convenience
        boolean ``eval_pass`` read by ``route_after_evaluation``.
    """
    # TODO: Replace stub with SageMaker batch transform + metric computation
    return {
        "accuracy": 0.92,
        "f1_score": 0.91,
        "bleu": 0.88,
        "rouge_l": 0.89,
        # Convenience flag read by route_after_evaluation()
        "eval_pass": True,
    }


def _log_evaluation_result(metrics: Dict[str, Any]) -> None:
    """Logs the evaluation outcome relative to the configured pass threshold.

    Args:
        metrics: The full dict of evaluation metric names to values.
    """
    accuracy: float = metrics.get("accuracy", 0.0)
    eval_pass: bool = metrics.get("eval_pass", False)

    if eval_pass and accuracy >= settings.EVAL_PASS_THRESHOLD:
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
