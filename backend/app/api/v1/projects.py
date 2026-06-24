import uuid
from typing import Any, List

import boto3
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_r2_client
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectList, ProjectResponse, ProjectUpdate
from app.schemas.project_file import FileResponse, UploadURLRequest, UploadURLResponse
from app.services import project_service, storage_service

router = APIRouter()


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new project."""
    try:
        return await project_service.create_project(db, current_user.id, project_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=ProjectList)
async def list_projects(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List projects for the current user."""
    projects, total = await project_service.get_projects(db, current_user.id, skip, limit)
    return ProjectList(items=projects, total=total, page=skip // limit + 1, size=limit)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get project details by ID."""
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a project."""
    try:
        project = await project_service.update_project(db, project_id, current_user.id, project_in)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: boto3.client = Depends(get_r2_client)
):
    """Delete a project and all associated files."""
    # Delete files from R2 first
    try:
        storage_service.delete_project_prefix(s3_client, current_user.id, project_id)
    except Exception as e:
        # Log error, but proceed to delete db record (or maybe don't depending on strictness)
        print(f"Error deleting files from R2: {e}")
        
    success = await project_service.delete_project(db, project_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/upload-url", response_model=UploadURLResponse)
async def get_upload_url(
    project_id: uuid.UUID,
    request: UploadURLRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: boto3.client = Depends(get_r2_client)
):
    """Generate a presigned URL to upload a file directly to R2."""
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return storage_service.generate_upload_url(
        s3_client,
        current_user.id,
        project_id,
        request.folder,
        request.filename,
        request.content_type
    )


@router.get("/{project_id}/files")
async def list_files(
    project_id: uuid.UUID,
    folder: str = "Data",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: boto3.client = Depends(get_r2_client)
):
    """List files in a project's folder."""
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return storage_service.list_objects(s3_client, current_user.id, project_id, folder)


@router.get("/{project_id}/download-url")
async def get_download_url(
    project_id: uuid.UUID,
    r2_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: boto3.client = Depends(get_r2_client)
):
    """Generate a presigned URL to download a file from R2."""
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if str(current_user.id) not in r2_key or str(project_id) not in r2_key:
        raise HTTPException(status_code=403, detail="Invalid key for this project")
        
    url = storage_service.generate_download_url(s3_client, r2_key)
    return {"download_url": url}


@router.post("/{project_id}/run")
async def run_pipeline(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Trigger the celery pipeline for a project."""
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    from app.worker.tasks import task_run_pipeline
    task = task_run_pipeline.delay(str(project_id), project.execution_type)
    
    project.status = "processing"
    await db.commit()
    
    return {"message": "Pipeline started", "task_id": str(task.id)}
