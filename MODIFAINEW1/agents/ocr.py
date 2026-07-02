"""
OCR Agent — ModifAI Pipeline.

Responsibilities
----------------
* Receives the list of uploaded file paths from the state.
* Extracts raw text from each document.
* Populates ``state.extracted_documents``.

Routing consequence
-------------------
OCR Agent always flows into Chunking Agent (linear edge in graph).

Note
----
Real implementation will call AWS Textract (``boto3.client("textract")``).
The stub simulates extraction by producing a placeholder string per file.
"""

from typing import List

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)

# Placeholder text used when no files are provided
_PLACEHOLDER_DOCUMENT = (
    "[OCR STUB] No files uploaded — using placeholder document text."
)


def ocr_agent(state: ModifAIState) -> dict:
    """Extracts text from uploaded documents using OCR.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("OCR Agent", state, logger)
    update = build_base_update("OCR Agent")

    try:
        uploaded_files: List[str] = state.get("uploaded_files", [])
        logger.info(f"Processing {len(uploaded_files)} file(s) via OCR...")

        extracted: List[str] = _extract_text_from_files(uploaded_files)

        update["extracted_documents"] = extracted
        logger.info(f"  Extracted {len(extracted)} document(s).")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in OCR Agent: {exc}", exc_info=True
        )
        update["errors"] = [f"OCRAgent: {exc}"]
        update["extracted_documents"] = []

    leave_node("OCR Agent", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_text_from_file(file_path: str) -> str:
    """Extracts raw text from a single document.

    Stub implementation returns a formatted placeholder string.
    The real implementation will submit the file to AWS Textract via an
    async job and poll for completion before returning the extracted text.

    Args:
        file_path: Path or URI of the document to process.

    Returns:
        Extracted text content as a plain string.
    """
    # TODO: Replace stub with boto3 Textract async job
    return (
        f"[OCR STUB] Extracted text from '{file_path}'. "
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Pellentesque habitant morbi tristique senectus."
    )


def _extract_text_from_files(uploaded_files: List[str]) -> List[str]:
    """Extracts raw text from all uploaded documents.

    Iterates over each file path and delegates to ``_extract_text_from_file``.
    If no files are provided, returns a list containing a single placeholder
    document so that downstream agents always receive at least one item.

    Args:
        uploaded_files: List of file paths or URIs to process.

    Returns:
        A list of extracted text strings, one entry per input file.
        Falls back to a single placeholder entry when the input list is empty.
    """
    if not uploaded_files:
        logger.warning("No files provided — inserting placeholder document.")
        return [_PLACEHOLDER_DOCUMENT]

    return [_extract_text_from_file(path) for path in uploaded_files]
