# Import all models here for Alembic auto-discovery
from app.db.base import Base  # noqa
from app.models.project import Project  # noqa
from app.models.project_file import ProjectFile  # noqa
from app.models.user import User  # noqa
