"""
Shared helpers for LangGraph node functions.

Every agent node in the ModifAI pipeline follows the same lifecycle:

1. **Enter** — log entry, print relevant context fields.
2. **Do work** — agent-specific logic (stub or real).
3. **Return** — a partial dict that LangGraph merges into the shared state.
4. **Leave** — log the updated fields and signal exit.

The helpers in this module eliminate that boilerplate so each agent
file stays focused on its own responsibility.

Usage in an agent::

    from utils.node_helpers import build_base_update, enter_node, leave_node

    def my_agent(state: ModifAIState) -> dict:
        enter_node("My Agent", state, logger)
        update = build_base_update("My Agent")
        try:
            update["my_field"] = "value"
        except Exception as exc:
            update["errors"] = [f"MyAgent: {exc}"]
        leave_node("My Agent", update, logger)
        return update
"""

import logging
from typing import Any, Dict

from graph.state import ModifAIState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SEPARATOR = "=" * 60


def enter_node(
    name: str,
    state: ModifAIState,
    logger: logging.Logger,
) -> None:
    """Logs the entry of a LangGraph agent node.

    Prints a visual separator, the agent name, and key context fields
    from the current state to help trace execution in the logs.

    Args:
        name: Human-readable agent name (e.g. ``"Validation Agent"``).
        state: The current shared pipeline state (read-only here).
        logger: Module-level logger for the calling agent.
    """
    logger.info(_SEPARATOR)
    logger.info(f"Entering {name}...")
    logger.info(f"  session_id    : {state.get('session_id', 'N/A')}")
    logger.info(f"  current_agent : {state.get('current_agent', 'START')}")
    logger.info(f"  history so far: {state.get('execution_history', [])}")


def leave_node(
    name: str,
    update: Dict[str, Any],
    logger: logging.Logger,
) -> None:
    """Logs the exit of a LangGraph agent node.

    Prints the fields that this agent is returning (excluding the list
    reducer fields to keep output readable).

    Args:
        name: Human-readable agent name.
        update: The partial state dict the agent is returning.
        logger: Module-level logger for the calling agent.
    """
    # Omit reducer fields from the per-node log to avoid noise
    _HIDDEN = {"execution_history", "errors"}
    loggable = {k: v for k, v in update.items() if k not in _HIDDEN}

    logger.info("Current State (fields updated by this node):")
    for key, value in loggable.items():
        logger.info(f"  {key}: {value}")
    logger.info(f"Leaving {name}.")
    logger.info(_SEPARATOR)


def build_base_update(agent_name: str) -> Dict[str, Any]:
    """Returns the base fields that *every* node must include in its response.

    ``current_agent`` is a simple replace — whoever ran last wins.
    ``execution_history`` uses the ``operator.add`` reducer defined on the
    TypedDict, which means LangGraph will *append* the returned list to the
    existing history rather than overwriting it.

    Args:
        agent_name: Display name appended to ``execution_history``.

    Returns:
        A dict pre-populated with ``current_agent`` and a single-item
        ``execution_history`` list ready for LangGraph's reducer.
    """
    return {
        "current_agent": agent_name,
        "execution_history": [agent_name],  # reducer: append, not replace
    }
