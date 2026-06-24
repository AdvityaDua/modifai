from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


# Valid execution types
EXECUTION_TYPES = ["dataset_generation", "fine_tune", "dataset_and_fine_tune", "full_pipeline"]


def validate_metadata(execution_type: str, metadata: Dict[str, Any]) -> None:
    """
    Validates the metadata payload based on the selected execution type.
    Raises ValueError if validation fails.
    """
    if execution_type not in EXECUTION_TYPES:
        raise ValueError(f"Invalid execution type. Must be one of: {EXECUTION_TYPES}")

    # For POC, we do light validation. This can be expanded.
    if execution_type in ["dataset_generation", "dataset_and_fine_tune", "full_pipeline"]:
        if "gen_model" not in metadata:
            raise ValueError("Missing 'gen_model' in metadata for dataset generation")
        if "min_samples" not in metadata:
            raise ValueError("Missing 'min_samples' in metadata for dataset generation")

    if execution_type in ["fine_tune", "dataset_and_fine_tune", "full_pipeline"]:
        if "base_model" not in metadata:
            raise ValueError("Missing 'base_model' in metadata for fine tuning")

    if execution_type == "full_pipeline":
        if "deploy_instance_type" not in metadata:
            raise ValueError("Missing 'deploy_instance_type' in metadata for deployment")


async def create_project(db: AsyncSession, user_id: UUID, project_data: ProjectCreate) -> Project:
    """Creates a new project for a user."""
    metadata = project_data.metadata_ or {}
    validate_metadata(project_data.execution_type, metadata)

    project = Project(
        user_id=user_id,
        name=project_data.name,
        description=project_data.description,
        execution_type=project_data.execution_type,
        metadata_=metadata,
        status="created",
        pipeline_status={}
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_projects(db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 10) -> Tuple[List[Project], int]:
    """Retrieves a paginated list of projects for a user."""
    # Get total count
    count_stmt = select(func.count(Project.id)).where(Project.user_id == user_id)
    total_count = await db.scalar(count_stmt)

    # Get items
    stmt = select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    projects = list(result.scalars().all())

    return projects, total_count


async def get_project(db: AsyncSession, project_id: UUID, user_id: UUID) -> Optional[Project]:
    """Retrieves a single project, verifying ownership."""
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_project(db: AsyncSession, project_id: UUID, user_id: UUID, update_data: ProjectUpdate) -> Optional[Project]:
    """Updates a project. Only allows updates to certain fields."""
    project = await get_project(db, project_id, user_id)
    if not project:
        return None

    update_dict = update_data.model_dump(exclude_unset=True)

    if "execution_type" in update_dict or "metadata_" in update_dict:
        new_execution_type = update_dict.get("execution_type", project.execution_type)
        new_metadata = update_dict.get("metadata_", project.metadata_)
        validate_metadata(new_execution_type, new_metadata)

    for key, value in update_dict.items():
        setattr(project, key, value)

    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: UUID, user_id: UUID) -> bool:
    """Deletes a project."""
    project = await get_project(db, project_id, user_id)
    if not project:
        return False

    await db.delete(project)
    await db.commit()
    return True
