from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ProjectFile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "project_files"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    r2_key = Column(Text, nullable=False, unique=True)
    folder = Column(String(50), nullable=False)
    file_size = Column(BigInteger, nullable=True)
    content_type = Column(String(255), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="files")
