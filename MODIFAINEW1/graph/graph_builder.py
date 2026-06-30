"""
ModifAI LangGraph Graph Builder.

This module is the **single source of truth** for the pipeline topology.
It owns:

* Node registration — every callable agent mapped to a string key.
* Edge registration — unconditional transitions between nodes.
* Conditional edge registration — routing functions from ``graph/routers.py``.
* Graph compilation — returns a ``CompiledGraph`` ready for ``.invoke()``.

Only this file should import both agents and routers.
Agents never import each other; they communicate solely through the state.

Usage::

    from graph.graph_builder import build_graph

    graph = build_graph()
    final_state = graph.invoke(initial_state_dict)

Extending the pipeline
----------------------
To add a new agent:
1. Add a new field to ``ModifAIState`` in ``graph/state.py``.
2. Create ``agents/my_new_agent.py`` following the existing pattern.
3. Call ``builder.add_node("my_new_agent", my_new_agent)`` below.
4. Wire it with ``add_edge`` or ``add_conditional_edges``.
"""

from langgraph.graph import END, StateGraph

from agents.chunking import chunking_agent
from agents.deployment import deployment_agent
from agents.evaluation import evaluation_agent
from agents.finetune import finetune_agent
from agents.generation import generation_agent
from agents.ocr import ocr_agent
from agents.quality import quality_agent
from agents.validation import validation_agent
from graph.routers import (
    route_after_evaluation,
    route_after_quality,
    route_after_router,
    route_after_validation,
)
from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Built-in nodes (not delegated to the agents/ package)
# ---------------------------------------------------------------------------


def _initialize_state_node(state: ModifAIState) -> dict:
    """Lightweight pipeline initialisation node.

    Logs the incoming request context before any agent has run.
    Does not modify any domain fields — only updates orchestration fields.

    Args:
        state: The incoming pipeline state from the entry point.

    Returns:
        A dict with base orchestration fields (current_agent, history).
    """
    enter_node("Initialize State", state, logger)
    update = build_base_update("Initialize State")

    logger.info("  Pipeline run starting.")
    logger.info(f"  session_id  : {state.get('session_id', 'N/A')}")
    logger.info(
        f"  user_prompt : {str(state.get('user_prompt', ''))[:80]}..."
    )
    logger.info(f"  files       : {state.get('uploaded_files', [])}")

    leave_node("Initialize State", update, logger)
    return update


def _router_node(state: ModifAIState) -> dict:
    """Explicit branching node between validation and document processing.

    This node exists to make the graph topology self-documenting.
    The actual routing decision is made by ``route_after_router`` in
    ``graph/routers.py`` via the conditional edge attached to this node.

    Args:
        state: The current pipeline state.

    Returns:
        A dict with base orchestration fields.
    """
    enter_node("Router", state, logger)
    update = build_base_update("Router")

    logger.info(
        f"  ocr_required = {state.get('ocr_required', False)}"
        " --> selecting document processing path."
    )

    leave_node("Router", update, logger)
    return update


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------


def build_graph():
    """Builds and compiles the ModifAI ``StateGraph``.

    Registers all nodes, linear edges, and conditional edges, then
    compiles the graph into an executable ``CompiledGraph``.

    Returns:
        A LangGraph ``CompiledGraph`` instance.

    Raises:
        Any exception raised by ``StateGraph.compile()`` if the topology
        is invalid (e.g. unreachable nodes, missing entry point).

    Example::

        graph = build_graph()
        result = graph.invoke(initial_state)
        print(result["deployment_url"])
    """
    builder: StateGraph = StateGraph(ModifAIState)

    # ------------------------------------------------------------------
    # 1. Register nodes
    # ------------------------------------------------------------------
    builder.add_node("initialize_state", _initialize_state_node)
    builder.add_node("validation_agent", validation_agent)
    builder.add_node("router", _router_node)
    builder.add_node("ocr_agent", ocr_agent)
    builder.add_node("chunking_agent", chunking_agent)
    builder.add_node("generation_agent", generation_agent)
    builder.add_node("quality_agent", quality_agent)
    builder.add_node("finetune_agent", finetune_agent)
    builder.add_node("evaluation_agent", evaluation_agent)
    builder.add_node("deployment_agent", deployment_agent)

    # ------------------------------------------------------------------
    # 2. Set entry point
    # ------------------------------------------------------------------
    builder.set_entry_point("initialize_state")

    # ------------------------------------------------------------------
    # 3. Register linear (unconditional) edges
    # ------------------------------------------------------------------
    # initialize_state → validation_agent (always)
    builder.add_edge("initialize_state", "validation_agent")

    # OCR path merges back into chunking (both paths share the same tail)
    builder.add_edge("ocr_agent", "chunking_agent")

    # Document processing → dataset generation tail
    builder.add_edge("chunking_agent", "generation_agent")
    builder.add_edge("generation_agent", "quality_agent")

    # Training tail
    builder.add_edge("finetune_agent", "evaluation_agent")

    # Terminal node → END
    builder.add_edge("deployment_agent", END)

    # ------------------------------------------------------------------
    # 4. Register conditional edges
    # ------------------------------------------------------------------

    # [Decision 1] After Validation Agent
    #   validation_status True  → router
    #   validation_status False → END
    builder.add_conditional_edges(
        "validation_agent",
        route_after_validation,
        {
            "proceed": "router",
            "end": END,
        },
    )

    # [Decision 2] After Router
    #   ocr_required True  → ocr_agent
    #   ocr_required False → chunking_agent
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "ocr": "ocr_agent",
            "chunking": "chunking_agent",
        },
    )

    # [Decision 3] After Dataset Quality Agent
    #   score >= threshold → finetune_agent
    #   score <  threshold → generation_agent  (retry loop)
    builder.add_conditional_edges(
        "quality_agent",
        route_after_quality,
        {
            "finetune": "finetune_agent",
            "regenerate": "generation_agent",
        },
    )

    # [Decision 4] After Evaluation Agent
    #   metrics pass → deployment_agent
    #   metrics fail → finetune_agent  (retry loop)
    builder.add_conditional_edges(
        "evaluation_agent",
        route_after_evaluation,
        {
            "deploy": "deployment_agent",
            "retrain": "finetune_agent",
        },
    )

    # ------------------------------------------------------------------
    # 5. Compile
    # ------------------------------------------------------------------
    compiled = builder.compile()
    logger.info("ModifAI graph compiled successfully.")
    return compiled
