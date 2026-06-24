from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    execution_type = Column(String(50), nullable=False)
    status = Column(String(50), default="created")
    num_files = Column(Integer, default=0)
    
    # Execution-specific config
    metadata_ = Column("metadata", JSONB, default=dict)
    
    # Step-level progress tracking
    pipeline_status = Column(JSONB, default=dict)
    
    error_message = Column(Text, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="projects")
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
