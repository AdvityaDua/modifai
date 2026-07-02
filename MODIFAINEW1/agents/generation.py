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

_DEFAULT_DATASET: List[Dict[str, Any]] = [
    {
        "id": 0,
        "question": "[STUB] Default fallback question.",
        "answer": "[STUB] Default fallback answer.",
        "dataset_type": "QA",
    }
]


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

        dataset: List[Dict[str, Any]] = _generate_dataset(chunks, dataset_type)

        update["generated_dataset"] = dataset
        logger.info(f"  Generated {len(dataset)} training example(s).")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Dataset Generation Agent: {exc}",
            exc_info=True,
        )
        update["errors"] = [f"GenerationAgent: {exc}"]
        update["generated_dataset"] = []

    leave_node("Dataset Generation Agent", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _generate_qa_pair(
    idx: int,
    chunk: str,
    dataset_type: str,
) -> Dict[str, Any]:
    """Generates a single question-answer training pair from one chunk.

    Stub implementation returns a formatted placeholder.  The real
    implementation will invoke an LLM (e.g. Bedrock Claude) via a LangChain
    prompt template to produce a semantically meaningful QA pair derived from
    the chunk's actual content.

    Args:
        idx: Zero-based index of the chunk within the full chunk list.
        chunk: The source text chunk to base the training pair on.
        dataset_type: The dataset format requested by the user (e.g. ``"QA"``).

    Returns:
        A dict representing one training example with keys:
        ``id``, ``chunk_source``, ``question``, ``answer``, ``dataset_type``.
    """
    # TODO: Replace stub with LangChain | Bedrock chain invocation
    return {
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


def _generate_dataset(
    chunks: List[str],
    dataset_type: str,
) -> List[Dict[str, Any]]:
    """Generates a full training dataset from all text chunks.

    Calls ``_generate_qa_pair`` for each chunk and falls back to
    ``_DEFAULT_DATASET`` when no chunks are supplied.

    Args:
        chunks: List of text chunks produced by the Chunking Agent.
        dataset_type: The dataset format label (e.g. ``"QA"``).

    Returns:
        A list of training example dicts.  Never empty — returns the default
        fallback dataset when ``chunks`` is empty.
    """
    if not chunks:
        logger.warning(
            "chunks list is empty — returning default fallback dataset."
        )
        return list(_DEFAULT_DATASET)  # return a copy

    return [_generate_qa_pair(idx, chunk, dataset_type) for idx, chunk in enumerate(chunks)]
