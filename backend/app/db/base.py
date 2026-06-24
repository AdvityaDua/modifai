import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

# Define the base declarative class
Base = declarative_base()


class TimestampMixin:
    """
    Mixin to add created_at and updated_at columns to models.
    """
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UUIDMixin:
    """
    Mixin to add a UUID primary key column.
    """
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
