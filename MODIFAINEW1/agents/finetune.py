"""
Fine-Tune Agent — ModifAI Pipeline.

Responsibilities
----------------
* Submits the generated dataset to a fine-tuning job.
* Populates ``state.training_job_id``, ``state.training_status``,
  and ``state.model_uri``.

Routing consequence
-------------------
Always flows into Evaluation Agent (linear edge).
May be re-invoked by the evaluation retry loop.

Note
----
Real implementation will call the Amazon SageMaker ``create_training_job``
API (or Amazon Bedrock model customisation API) and poll for completion.
"""

import uuid

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)

_MODEL_S3_PREFIX = "s3://modifai-models/stub"


def finetune_agent(state: ModifAIState) -> dict:
    """Submits a fine-tuning job for the validated dataset.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("Fine-Tune Agent", state, logger)
    update = build_base_update("Fine-Tune Agent")

    try:
        dataset = state.get("generated_dataset", [])
        task_type: str = state.get("task_type", "text-classification") or "N/A"

        job_id = f"modifai-job-{uuid.uuid4().hex[:8]}"
        model_uri = f"{_MODEL_S3_PREFIX}/{job_id}/model.tar.gz"

        logger.info(
            f"Submitting fine-tuning job for {len(dataset)} example(s)..."
        )
        logger.info(f"  task_type   : {task_type}")
        logger.info(f"  job_id      : {job_id}")
        logger.info(f"  model_uri   : {model_uri}")

        # Stub: job completes immediately
        update.update(
            {
                "training_job_id": job_id,
                "training_status": "COMPLETED",
                "model_uri": model_uri,
            }
        )

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Fine-Tune Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"FineTuneAgent: {exc}"]
        update["training_status"] = "FAILED"

    leave_node("Fine-Tune Agent", update, logger)
    return update
