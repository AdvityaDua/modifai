"""
Global configuration settings for the ModifAI platform.

All tunable thresholds and environment-level constants live here.
Agents read from the singleton ``settings`` object rather than
hard-coding values, making the system easy to re-configure without
touching business logic.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable, application-level configuration.

    Attributes:
        QUALITY_THRESHOLD: Minimum dataset quality score (0–1) required
            before the pipeline proceeds to fine-tuning. Below this
            value the Dataset Quality Agent triggers a regeneration loop.
        EVAL_PASS_THRESHOLD: Minimum model accuracy (0–1) required before
            the pipeline proceeds to deployment. Below this value the
            Evaluation Agent triggers a re-training loop.
        MAX_RETRY_LOOPS: Safety cap on regeneration/re-training cycles
            (informational — enforcement is left to future guard nodes).
        LOG_LEVEL: Python ``logging`` level string (DEBUG, INFO, WARNING …).
        APP_NAME: Human-readable application name used in logs and headers.
        VERSION: Semantic version of the orchestration layer.
    """

    # Quality thresholds
    QUALITY_THRESHOLD: float = 0.85
    EVAL_PASS_THRESHOLD: float = 0.80

    # Safety limits
    MAX_RETRY_LOOPS: int = 3

    # Logging
    LOG_LEVEL: str = "INFO"

    # App metadata
    APP_NAME: str = "ModifAI"
    VERSION: str = "0.1.0"


# ---------------------------------------------------------------------------
# Singleton — import and use this throughout the project
# ---------------------------------------------------------------------------
settings = Settings()
