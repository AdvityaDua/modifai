"""
Pydantic input schema for the ModifAI pipeline entry point.

``ModifAIInputSchema`` validates and sanitises the user-facing request
*before* it enters the LangGraph graph.  The ``to_initial_state()`` method
converts the validated model into a plain ``dict`` that matches
``ModifAIState``, ready for ``graph.invoke()``.

Separating Pydantic validation from the LangGraph TypedDict avoids the
mismatch between Pydantic BaseModel and LangGraph's required TypedDict API.
"""

import uuid
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


class ModifAIInputSchema(BaseModel):
    """Validates and sanitises a user's pipeline request.

    Attributes:
        session_id: Unique session identifier.  Auto-generated (UUID4)
            if not provided by the caller.
        user_prompt: The user's instruction for the pipeline.
            Must be non-empty and non-blank.
        uploaded_files: File paths or URIs uploaded by the user.
            Defaults to an empty list.
        metadata: Arbitrary key-value pairs for caller-specific context.

    Raises:
        ValidationError: If ``user_prompt`` is blank or empty.
    """

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique session identifier.  Auto-generated if omitted.",
    )
    user_prompt: str = Field(
        ...,
        min_length=1,
        description="The user's instruction driving the entire pipeline.",
    )
    uploaded_files: List[str] = Field(
        default_factory=list,
        description="File paths or URIs provided by the user.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller-specific metadata.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("user_prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        """Strips leading/trailing whitespace and rejects blank prompts.

        Args:
            value: The raw ``user_prompt`` string from the caller.

        Returns:
            The stripped prompt string.

        Raises:
            ValueError: If the stripped prompt is empty.
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                "user_prompt must not be blank or contain only whitespace."
            )
        return stripped

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_initial_state(self) -> Dict[str, Any]:
        """Converts the validated input into a ``ModifAIState``-compatible dict.

        All fields that have not yet been set by an agent are initialised
        to their zero/null values so LangGraph never encounters missing keys.

        Returns:
            A complete initial state dict suitable for ``graph.invoke()``.
        """
        return {
            # Session
            "session_id": self.session_id,
            "user_prompt": self.user_prompt,
            "uploaded_files": self.uploaded_files,
            # Classification — populated by Validation Agent
            "dataset_type": None,
            "task_type": None,
            # Validation
            "validation_status": None,
            "ocr_required": False,
            # Document processing
            "extracted_documents": [],
            "chunks": [],
            # Dataset
            "generated_dataset": [],
            "dataset_quality_score": 0.0,
            # Fine-tuning
            "training_job_id": None,
            "training_status": None,
            "model_uri": None,
            # Evaluation & deployment
            "evaluation_metrics": {},
            "deployment_url": None,
            # Orchestration
            "current_agent": "START",
            "execution_history": [],
            "errors": [],
            "metadata": self.metadata,
        }
