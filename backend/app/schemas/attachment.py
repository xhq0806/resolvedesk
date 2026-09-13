"""附件上传与下载 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentPublic(BaseModel):
    """附件公开元数据，不返回存储键。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    ticket_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    display_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    uploaded_by_id: uuid.UUID
    created_at: datetime
