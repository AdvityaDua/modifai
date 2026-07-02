"""
Centralised logger factory for the ModifAI platform.

Every module should obtain its logger via ``get_logger(__name__)``
rather than calling ``logging.getLogger`` directly.  This guarantees
consistent formatting across the entire application and avoids
duplicate handler registration.

Example::

    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Hello from my module.")
"""

import logging
import sys

from config.settings import settings

# ---------------------------------------------------------------------------
# Format constants
# ---------------------------------------------------------------------------
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Creates or retrieves a configured ``logging.Logger`` instance.

    Handlers are added only once (idempotent).  All loggers propagate
    is set to ``False`` to prevent double-printing when a root logger
    is also configured.

    Args:
        name: Logger name — pass ``__name__`` from the calling module.

    Returns:
        A ``logging.Logger`` configured with a ``StreamHandler`` writing
        to ``stdout`` at the level specified in ``settings.LOG_LEVEL``.
    """
    logger = logging.getLogger(name)

    # Guard: avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    return logger
