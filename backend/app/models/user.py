from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    avatar_url = Column(Text, nullable=True)
    google_id = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    projects = relationship(
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
