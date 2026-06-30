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
        model_uri: str = state.get("model_uri", "N/A") or "N/A"
        session_id: str = state.get("session_id", "unknown")
        endpoint_id = uuid.uuid4().hex[:8]

        deployment_url = f"{_API_BASE}/{session_id[:8]}-{endpoint_id}"

        logger.info(f"Deploying model artefact: {model_uri}")
        logger.info(f"  endpoint URL: {deployment_url}")

        update["deployment_url"] = deployment_url

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Deployment Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"DeploymentAgent: {exc}"]
        update["deployment_url"] = None

    leave_node("Deployment Agent", update, logger)
    return update
