from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    execution_type: str
    metadata_: Optional[Dict[str, Any]] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    execution_type: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: UUID
    user_id: UUID
    num_files: int
    status: str
    pipeline_status: Dict[str, Any]
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectList(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    size: int
