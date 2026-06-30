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

        # Stub: simulate text extraction per file
        # Real impl: boto3 Textract async job per document
        extracted: List[str] = [
            (
                f"[OCR STUB] Extracted text from '{file_path}'. "
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
                "Pellentesque habitant morbi tristique senectus."
            )
            for file_path in uploaded_files
        ]

        if not extracted:
            logger.warning("No files provided — inserting placeholder document.")
            extracted = [
                "[OCR STUB] No files uploaded — using placeholder document text."
            ]

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
