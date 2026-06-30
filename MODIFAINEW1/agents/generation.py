"""
Dataset Generation Agent — ModifAI Pipeline.

Responsibilities
----------------
* Reads ``state.chunks`` produced by the Chunking Agent.
* Generates question-answer (or instruction-response) training pairs.
* Populates ``state.generated_dataset``.

Routing consequence
-------------------
Always flows into Dataset Quality Agent (linear edge).
May be re-invoked by the quality retry loop if the score is too low.

Note
----
Real implementation will call an LLM (e.g. Amazon Bedrock Claude) via
a LangChain prompt template for each chunk.
"""

from typing import Any, Dict, List

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)


def generation_agent(state: ModifAIState) -> dict:
    """Generates a synthetic training dataset from text chunks.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("Dataset Generation Agent", state, logger)
    update = build_base_update("Dataset Generation Agent")

    try:
        chunks: List[str] = state.get("chunks", [])
        dataset_type: str = state.get("dataset_type", "QA") or "QA"

        logger.info(
            f"Generating '{dataset_type}' dataset from {len(chunks)} chunk(s)..."
        )

        # Stub: one QA pair per chunk
        # Real impl: LangChain | Bedrock chain per chunk, deduplicated
        dataset: List[Dict[str, Any]] = [
            {
                "id": idx,
                "chunk_source": chunk[:100],
                "question": (
                    f"[STUB] What is the primary topic described in chunk {idx + 1}?"
                ),
                "answer": (
                    f"[STUB] Chunk {idx + 1} covers the following synthesised "
                    "information from the source document."
                ),
                "dataset_type": dataset_type,
            }
            for idx, chunk in enumerate(chunks)
        ]

        if not dataset:
            dataset = [
                {
                    "id": 0,
                    "question": "[STUB] Default fallback question.",
                    "answer": "[STUB] Default fallback answer.",
                    "dataset_type": dataset_type,
                }
            ]

        update["generated_dataset"] = dataset
        logger.info(f"  Generated {len(dataset)} training example(s).")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Dataset Generation Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"GenerationAgent: {exc}"]
        update["generated_dataset"] = []

    leave_node("Dataset Generation Agent", update, logger)
    return update
