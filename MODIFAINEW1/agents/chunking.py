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
_STUB_CHUNKS_PER_SOURCE: int = 3
_CHUNK_SIZE_HINT: int = 512
_OVERLAP_HINT: int = 50
_DEFAULT_CHUNK = "[CHUNK STUB] No source documents found — using default chunk."


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
        sources: List[str] = _resolve_sources(state)
        logger.info(
            f"Chunking {len(sources)} source(s) "
            f"(chunk_size≈{_CHUNK_SIZE_HINT}, overlap≈{_OVERLAP_HINT})..."
        )

        chunks: List[str] = _split_into_chunks(
            sources,
            chunks_per_source=_STUB_CHUNKS_PER_SOURCE,
        )

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


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_sources(state: ModifAIState) -> List[str]:
    """Determines which source list to chunk.

    Prefers ``extracted_documents`` (set by the OCR Agent) when available.
    Falls back to ``uploaded_files`` when OCR was not required.

    Args:
        state: The current shared pipeline state (read-only).

    Returns:
        A non-empty list of source strings to split into chunks.
    """
    extracted: List[str] = state.get("extracted_documents", []) or []
    if extracted:
        return extracted

    fallback: List[str] = state.get("uploaded_files", []) or []
    if fallback:
        logger.warning(
            "extracted_documents is empty — falling back to uploaded_files."
        )
    return fallback


def _split_into_chunks(
    sources: List[str],
    chunks_per_source: int = _STUB_CHUNKS_PER_SOURCE,
) -> List[str]:
    """Splits a list of source documents into fixed-size text chunks.

    Stub implementation produces ``chunks_per_source`` synthetic chunks per
    source document.  The real implementation will call LangChain's
    ``RecursiveCharacterTextSplitter`` with configurable ``chunk_size`` and
    ``chunk_overlap`` to produce overlapping character-level chunks.

    Args:
        sources: List of source text strings to split.
        chunks_per_source: Number of stub chunks to emit per source document.

    Returns:
        A flat list of chunk strings.  Returns a single default placeholder
        chunk when ``sources`` is empty.
    """
    if not sources:
        return [_DEFAULT_CHUNK]

    # TODO: Replace stub with RecursiveCharacterTextSplitter
    chunks: List[str] = []
    for src_idx, source in enumerate(sources):
        preview = source[:80].replace("\n", " ")
        for chunk_num in range(1, chunks_per_source + 1):
            chunks.append(
                f"[CHUNK STUB] src={src_idx + 1} chunk={chunk_num} | "
                f"{preview}..."
            )
    return chunks
