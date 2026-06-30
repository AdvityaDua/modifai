"""
Chunking Agent — ModifAI Pipeline.

Responsibilities
----------------
* Reads ``extracted_documents`` (OCR path) or falls back to treating
  ``uploaded_files`` paths as source labels (non-OCR path).
* Splits text into fixed-size chunks with overlap.
* Populates ``state.chunks``.

Routing consequence
-------------------
Always flows into Dataset Generation Agent (linear edge).

Note
----
Real implementation will use LangChain's ``RecursiveCharacterTextSplitter``
with configurable ``chunk_size`` and ``chunk_overlap`` parameters.
"""

from typing import List

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)

# Stub parameters — replace with RecursiveCharacterTextSplitter in production
_STUB_CHUNKS_PER_SOURCE = 3
_CHUNK_SIZE_HINT = 512
_OVERLAP_HINT = 50


def chunking_agent(state: ModifAIState) -> dict:
    """Splits source documents into text chunks for dataset generation.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("Chunking Agent", state, logger)
    update = build_base_update("Chunking Agent")

    try:
        # Prefer OCR output; fall back to file names as labels
        sources: List[str] = state.get("extracted_documents", []) or state.get(
            "uploaded_files", []
        )

        logger.info(
            f"Chunking {len(sources)} source(s) "
            f"(chunk_size≈{_CHUNK_SIZE_HINT}, overlap≈{_OVERLAP_HINT})..."
        )

        # Stub: produce _STUB_CHUNKS_PER_SOURCE synthetic chunks per source
        chunks: List[str] = []
        for src_idx, source in enumerate(sources):
            preview = source[:80].replace("\n", " ")
            for chunk_num in range(1, _STUB_CHUNKS_PER_SOURCE + 1):
                chunks.append(
                    f"[CHUNK STUB] src={src_idx + 1} chunk={chunk_num} | "
                    f"{preview}..."
                )

        if not chunks:
            chunks = [
                "[CHUNK STUB] No source documents found — using default chunk."
            ]

        update["chunks"] = chunks
        logger.info(f"  Produced {len(chunks)} chunk(s).")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in Chunking Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"ChunkingAgent: {exc}"]
        update["chunks"] = []

    leave_node("Chunking Agent", update, logger)
    return update
