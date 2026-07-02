"""
ModifAI — Pipeline Entry Point.

Demonstrates how a user request enters the LangGraph pipeline and
flows through all agents.

Usage
-----
Run from the project root::

    python app.py

To exercise the OCR path, set ``uploaded_files`` to contain a ``.pdf``
file name.  The Validation Agent will detect the extension and set
``ocr_required=True``, which the Router will then use to invoke the
OCR Agent.

Scenarios demonstrated
----------------------
1. Happy path (no OCR)     — text file, full pipeline end-to-end.
2. OCR path                — PDF file, OCR Agent inserted before Chunking.
3. Validation failure      — empty prompt rejected by Pydantic before
                             the graph is even invoked.
"""

from __future__ import annotations

import sys

# Force UTF-8 on Windows terminals that default to CP1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from typing import List, Optional

from graph.graph_builder import build_graph
from schemas.state_schema import ModifAIInputSchema
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


def run_pipeline(
    user_prompt: str,
    uploaded_files: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Validates input, builds the graph, and invokes the full pipeline.

    Args:
        user_prompt: The user's natural-language instruction.
        uploaded_files: Optional list of file paths or URIs to process.
        metadata: Optional key-value metadata forwarded into the state.

    Returns:
        The final state dict after the graph has completed execution.

    Raises:
        pydantic.ValidationError: If ``user_prompt`` is blank or invalid.
    """
    uploaded_files = uploaded_files or []
    metadata = metadata or {}

    # Step 1 — Validate with Pydantic (raises ValidationError on bad input)
    logger.info("Validating pipeline input...")
    schema = ModifAIInputSchema(
        user_prompt=user_prompt,
        uploaded_files=uploaded_files,
        metadata=metadata,
    )
    initial_state = schema.to_initial_state()
    logger.info(f"Session ID: {initial_state['session_id']}")

    # Step 2 — Build graph (compiled once; reuse in production for perf)
    logger.info("Building LangGraph pipeline...")
    graph = build_graph()

    # Step 3 — Invoke
    logger.info("Invoking pipeline...\n")
    final_state: dict = graph.invoke(initial_state)
    return final_state


# ---------------------------------------------------------------------------
# Pretty-printer
# ---------------------------------------------------------------------------


def print_summary(final_state: dict, scenario: str = "") -> None:
    """Prints a formatted human-readable execution summary.

    Args:
        final_state: The final state dict returned by the graph.
        scenario: Optional scenario label for the header.
    """
    sep = "=" * 62
    print(f"\n{sep}")
    if scenario:
        print(f"  {scenario}")
        print(sep)
    print(f"  Session ID      : {final_state.get('session_id')}")
    print(f"  Validation      : {final_state.get('validation_status')}")
    print(f"  Dataset Type    : {final_state.get('dataset_type')}")
    print(f"  Task Type       : {final_state.get('task_type')}")
    print(f"  OCR Required    : {final_state.get('ocr_required')}")
    print(f"  Chunks          : {len(final_state.get('chunks', []))}")
    print(f"  Dataset Size    : {len(final_state.get('generated_dataset', []))}")

    quality = final_state.get("dataset_quality_score", 0.0)
    print(f"  Quality Score   : {quality:.3f}")
    print(f"  Training Job    : {final_state.get('training_job_id')}")
    print(f"  Training Status : {final_state.get('training_status')}")
    print(f"  Model URI       : {final_state.get('model_uri')}")

    metrics = final_state.get("evaluation_metrics", {})
    print(f"  Eval Accuracy   : {metrics.get('accuracy', 'N/A')}")
    print(f"  Eval F1         : {metrics.get('f1_score', 'N/A')}")
    print(f"  Deployment URL  : {final_state.get('deployment_url')}")

    history = final_state.get("execution_history", [])
    print(f"\n  Execution Path  ({len(history)} steps):")
    for step, name in enumerate(history, 1):
        print(f"    {step:>2}. {name}")

    errors = final_state.get("errors", [])
    if errors:
        print(f"\n  ⚠  Errors ({len(errors)}):")
        for err in errors:
            print(f"    - {err}")

    print(sep)


# ---------------------------------------------------------------------------
# Demo scenarios
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Scenario 1 — Happy path (text file, no OCR)
    # ------------------------------------------------------------------
    print("\n" + "#" * 62)
    print("# SCENARIO 1 — Standard pipeline (no OCR, .txt file)")
    print("#" * 62)
    result_1 = run_pipeline(
        user_prompt="Generate a QA dataset from our internal knowledge base.",
        uploaded_files=["knowledge_base.txt"],
    )
    print_summary(result_1, "SCENARIO 1 — Standard pipeline (no OCR)")

    # ------------------------------------------------------------------
    # Scenario 2 — OCR path (PDF uploaded)
    # ------------------------------------------------------------------
    print("\n" + "#" * 62)
    print("# SCENARIO 2 — OCR path (.pdf file uploaded)")
    print("#" * 62)
    result_2 = run_pipeline(
        user_prompt="Extract and fine-tune on the contents of this annual report.",
        uploaded_files=["annual_report_2024.pdf"],
    )
    print_summary(result_2, "SCENARIO 2 — OCR path (.pdf uploaded)")

    # ------------------------------------------------------------------
    # Scenario 3 — Validation failure (blank prompt)
    # ------------------------------------------------------------------
    print("\n" + "#" * 62)
    print("# SCENARIO 3 — Validation failure (blank prompt)")
    print("#" * 62)
    try:
        run_pipeline(user_prompt="   ")
    except Exception as exc:
        print(f"\n  ✗ Input rejected by Pydantic before graph invocation:")
        print(f"    {exc}")
        print()
