"""
Shared LangGraph state for the ModifAI pipeline.

``ModifAIState`` is the *single source of truth* for all agents.
Every node reads from it and returns only the fields it updates —
LangGraph merges partial returns back into the full state automatically.

Design notes
------------
* The state is a ``TypedDict`` because LangGraph's ``StateGraph`` requires
  a TypedDict (or a class that behaves like one).  Pydantic validation of
  the *initial* state happens in ``schemas/state_schema.py`` before the
  graph is invoked.
* ``execution_history`` and ``errors`` use ``Annotated[List[str], operator.add]``
  so that LangGraph *appends* new items rather than replacing the list when
  a node returns ``{"execution_history": ["MyAgent"]}``.
* All other fields use the default *replace* reducer (last write wins).
* Adding a new feature = adding a new field here + registering a new node.
  The graph topology itself does not need to change.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import TypedDict


class ModifAIState(TypedDict, total=False):
    """Shared state object for the entire ModifAI multi-agent pipeline.

    Attributes:
        session_id: Unique identifier for this pipeline run (UUID4).
        user_prompt: The raw instruction submitted by the user.
        uploaded_files: File paths or URIs provided by the user.

        dataset_type: Category of dataset to generate
            (e.g., ``"QA"``, ``"instruction"``).  Set by Validation Agent.
        task_type: ML task category
            (e.g., ``"text-classification"``, ``"summarization"``).
            Set by Validation Agent.

        validation_status: ``True`` if the request passed validation,
            ``False`` if it failed, ``None`` before the Validation Agent runs.
        ocr_required: ``True`` when uploaded files require OCR pre-processing.

        extracted_documents: Raw text extracted from documents (OCR output).
        chunks: Text segments produced by the Chunking Agent.

        generated_dataset: Training examples produced by the Generation Agent.
        dataset_quality_score: Quality score from the Quality Agent (0–1).

        training_job_id: Identifier of the fine-tuning job.
        training_status: Status string of the job (``"COMPLETED"``, etc.).
        model_uri: URI of the trained model artefact.

        evaluation_metrics: Dict of metric names to float values
            (accuracy, f1_score, bleu, rouge_l …).
        deployment_url: Public endpoint of the deployed model.

        current_agent: Display name of the agent currently executing.
        execution_history: Ordered list of agent names that have executed.
            Uses ``operator.add`` reducer — each node *appends* its name.
        errors: Error messages from failed agents.
            Uses ``operator.add`` reducer — each node *appends* its errors.
        metadata: Arbitrary extensibility bag for future fields.
    """

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------
    session_id: str
    user_prompt: str
    uploaded_files: List[str]

    # ------------------------------------------------------------------
    # Classification (set by Validation Agent)
    # ------------------------------------------------------------------
    dataset_type: Optional[str]
    task_type: Optional[str]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    validation_status: Optional[bool]
    ocr_required: bool

    # ------------------------------------------------------------------
    # Document processing
    # ------------------------------------------------------------------
    extracted_documents: List[str]
    chunks: List[str]

    # ------------------------------------------------------------------
    # Dataset generation
    # ------------------------------------------------------------------
    generated_dataset: List[Dict[str, Any]]
    dataset_quality_score: float

    # ------------------------------------------------------------------
    # Fine-tuning
    # ------------------------------------------------------------------
    training_job_id: Optional[str]
    training_status: Optional[str]
    model_uri: Optional[str]

    # ------------------------------------------------------------------
    # Evaluation & deployment
    # ------------------------------------------------------------------
    evaluation_metrics: Dict[str, Any]
    deployment_url: Optional[str]

    # ------------------------------------------------------------------
    # Orchestration (managed by LangGraph + node_helpers)
    # ------------------------------------------------------------------
    current_agent: str
    # operator.add reducer → returned list is *appended*, not replaced
    execution_history: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
    metadata: Dict[str, Any]
