"""知识库文档与摄取任务 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.knowledge import IngestionJobStatus, KnowledgeDocumentStatus


class KnowledgeDocumentPublic(BaseModel):
    """不暴露存储路径的知识文档公开信息。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    display_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: KnowledgeDocumentStatus
    version: int
    error_code: str | None
    created_by_id: uuid.UUID
    created_at: datetime
    deleted_at: datetime | None


class DocumentIngestionJobPublic(BaseModel):
    """文档摄取任务状态。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    status: IngestionJobStatus
    attempts: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeSourceKind(StrEnum):
    """知识片段来源定位类型。by AI.Coding"""

    PAGE = "page"
    PARAGRAPH = "paragraph"
    DOCUMENT = "document"


class KnowledgeSearchRequest(BaseModel):
    """RAG 检索请求。by AI.Coding"""

    query: str
    limit: int = 8


class RetrievedChunkPublic(BaseModel):
    """可用于 AI 引用展示的来源片段。by AI.Coding"""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    display_name: str
    locator: dict[str, object]
    preview: str
    distance: float
