"""
Deployment Agent — ModifAI Pipeline.

Responsibilities
----------------
* Deploys the evaluated model to a serving endpoint.
* Populates ``state.deployment_url``.

Routing consequence
-------------------
Always flows into ``END`` (linear edge — terminal node).

Note
----
Real implementation will create a SageMaker real-time endpoint
(or update an existing one), configure API Gateway, and optionally
trigger a CDK/CloudFormation stack update.
"""

import uuid
from typing import Optional

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)

_API_BASE = "https://api.modifai.ai/v1/endpoints"


def deployment_agent(state: ModifAIState) -> dict:
    """Deploys the fine-tuned model to a production serving endpoint.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("Deployment Agent", state, logger)
    update = build_base_update("Deployment Agent")

    try:
        model_uri: Optional[str] = state.get("model_uri") or "N/A"
        session_id: str = state.get("session_id", "unknown") or "unknown"

        logger.info(f"Deploying model artefact: {model_uri}")

        deployment_url: str = _deploy_model(model_uri, session_id)

        update["deployment_url"] = deployment_url
        logger.info(f"  endpoint URL: {deployment_url}")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Deployment Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"DeploymentAgent: {exc}"]
        update["deployment_url"] = None

    leave_node("Deployment Agent", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_endpoint_id(session_id: str) -> str:
    """Constructs a unique endpoint identifier from the session ID.

    Combines a prefix derived from ``session_id`` with a random UUID4 suffix
    to produce a collision-resistant endpoint name.

    Args:
        session_id: The pipeline session UUID for the current run.

    Returns:
        A string of the form ``"<session_prefix>-<random_suffix>"``.
    """
    return f"{session_id[:8]}-{uuid.uuid4().hex[:8]}"


def _deploy_model(
    model_uri: str,  # noqa: ARG001  — used by real SageMaker impl
    session_id: str,
) -> str:
    """Deploys the model artefact and returns the serving endpoint URL.

    Stub implementation generates a deterministic URL without touching any
    cloud infrastructure.  The real implementation will:
    - Create (or update) a SageMaker real-time inference endpoint.
    - Wait for the endpoint status to become ``InService``.
    - Register the endpoint behind an API Gateway route.
    - Optionally trigger a CDK / CloudFormation stack update.

    Args:
        model_uri: S3 URI of the trained model artefact to deploy.
        session_id: The pipeline session UUID used to namespace the endpoint.

    Returns:
        The public HTTPS URL of the deployed serving endpoint.
    """
    # TODO: Replace stub with SageMaker endpoint creation + API Gateway wiring
    endpoint_id = _build_endpoint_id(session_id)
    return f"{_API_BASE}/{endpoint_id}"
