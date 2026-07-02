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
from typing import Any, Dict, List, Optional

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
        dataset: List[Dict[str, Any]] = state.get("generated_dataset", [])
        task_type: str = state.get("task_type", "text-classification") or "N/A"

        logger.info(
            f"Submitting fine-tuning job for {len(dataset)} example(s)..."
        )
        logger.info(f"  task_type : {task_type}")

        job_result = _submit_training_job(dataset, task_type)

        update["training_job_id"] = job_result["training_job_id"]
        update["training_status"] = job_result["training_status"]
        update["model_uri"] = job_result["model_uri"]

        logger.info(f"  job_id    : {job_result['training_job_id']}")
        logger.info(f"  model_uri : {job_result['model_uri']}")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Fine-Tune Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"FineTuneAgent: {exc}"]
        update["training_job_id"] = None
        update["training_status"] = "FAILED"
        update["model_uri"] = None

    leave_node("Fine-Tune Agent", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_model_uri(job_id: str) -> str:
    """Constructs the S3 URI for the fine-tuned model artefact.

    Args:
        job_id: The unique identifier of the training job.

    Returns:
        A fully qualified S3 URI string pointing to the model artefact.
    """
    return f"{_MODEL_S3_PREFIX}/{job_id}/model.tar.gz"


def _submit_training_job(
    dataset: List[Dict[str, Any]],
    task_type: str,  # noqa: ARG001  — used by real SageMaker impl
) -> Dict[str, Optional[str]]:
    """Submits a fine-tuning job and waits for completion.

    Stub implementation generates a random job ID and returns a COMPLETED
    status immediately.  The real implementation will:
    - Upload ``dataset`` to S3 in the SageMaker training data format.
    - Call ``sagemaker_client.create_training_job(...)`` or the Bedrock
      model customisation API.
    - Poll ``describe_training_job`` until the status is terminal.

    Args:
        dataset: List of training example dicts to fine-tune on.
        task_type: ML task category (e.g. ``"text-classification"``).

    Returns:
        A dict with keys:
        - ``training_job_id``: Unique job identifier string.
        - ``training_status``: Final status string (e.g. ``"COMPLETED"``).
        - ``model_uri``: S3 URI of the trained model artefact.
    """
    # TODO: Replace stub with boto3 SageMaker / Bedrock API calls
    job_id = f"modifai-job-{uuid.uuid4().hex[:8]}"
    return {
        "training_job_id": job_id,
        "training_status": "COMPLETED",
        "model_uri": _build_model_uri(job_id),
    }
