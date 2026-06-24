from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadURLRequest(BaseModel):
    filename: str
    folder: str
    content_type: Optional[str] = None


class UploadURLResponse(BaseModel):
    upload_url: str
    r2_key: str
    expires_in: int


class FileResponse(BaseModel):
    id: UUID
    filename: str
    folder: str
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
