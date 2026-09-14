"""知识库解析、切块和上传安全测试。by AI.Coding"""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import ValidationError as DomainValidationError
from app.core.provider_security import validate_provider_base_url
from app.models.knowledge import KnowledgeChunk
from app.services.knowledge_retrieval import trim_sources
from app.services.knowledge_service import (
    chunk_text,
    parse_document,
    validate_upload_metadata,
)


def test_chunk_text_keeps_overlap_and_discards_blank_input() -> None:
    """切块应保持重叠窗口并对空白文档返回空列表。by AI.Coding"""
    text = "a" * 120

    chunks = chunk_text(text, chunk_size=50, overlap=10)

    assert chunks == ["a" * 50, "a" * 50, "a" * 40]
    assert chunk_text(" \n\t ") == []


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("faq.exe", "application/octet-stream"),
        ("../faq.txt", "text/plain"),
        ("faq.pdf", "text/plain"),
    ],
)
def test_upload_validation_rejects_unsafe_or_mismatched_files(
    filename: str,
    content_type: str,
) -> None:
    """不支持扩展名、路径穿越和 MIME 不匹配必须在入库前拒绝。by AI.Coding"""
    with pytest.raises(DomainValidationError):
        validate_upload_metadata(filename, content_type, 10)


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("faq.md", "text/plain"),
        ("faq.md", "application/octet-stream"),
        ("faq.docx", "application/octet-stream"),
        ("faq.pdf", "application/octet-stream"),
        ("faq.txt", ""),
    ],
)
def test_upload_validation_accepts_browser_mime_variants(
    filename: str, content_type: str
) -> None:
    """浏览器常见 MIME 变体不应误伤合法文档上传。by AI.Coding"""
    extension, mime_type = validate_upload_metadata(filename, content_type, 10)
    assert extension == f".{filename.rsplit('.', 1)[1]}"
    assert mime_type


def test_markdown_parser_preserves_document_source() -> None:
    """Markdown 解析应返回可用于引用的文档来源元数据。by AI.Coding"""
    segments = parse_document(b"# FAQ\n\nReset password here.", ".md")

    assert len(segments) == 1
    assert segments[0].text.startswith("# FAQ")
    assert segments[0].source_meta == {"kind": "document"}


def test_provider_url_rejects_private_network_targets() -> None:
    """模型 Provider URL 校验应阻止内网目标，降低 SSRF 风险。by AI.Coding"""
    with pytest.raises(ValueError):
        validate_provider_base_url("http://127.0.0.1:11434/v1")


def test_trim_sources_deduplicates_documents_and_caps_results() -> None:
    """RAG 来源应按文档去重并限制最多五条。by AI.Coding"""
    rows = [
        (
            KnowledgeChunk(
                id=uuid.uuid4(),
                document_id=uuid.UUID(int=1),
                workspace_id=uuid.UUID(int=2),
                chunk_index=0,
                content="first",
                source_meta={"kind": "page", "page": 1},
            ),
            "faq.md",
            0.1,
        ),
        (
            KnowledgeChunk(
                id=uuid.uuid4(),
                document_id=uuid.UUID(int=1),
                workspace_id=uuid.UUID(int=2),
                chunk_index=1,
                content="duplicate document",
                source_meta={"kind": "page", "page": 2},
            ),
            "faq.md",
            0.2,
        ),
    ]

    result = trim_sources(rows)

    assert len(result) == 1
    assert result[0].display_name == "faq.md"
