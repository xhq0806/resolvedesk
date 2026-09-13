"""附件文件类型、magic number 和路径安全测试。by AI.Coding"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError as DomainValidationError
from app.services.attachment_service import validate_attachment_bytes


def test_attachment_validation_accepts_matching_pdf_signature() -> None:
    """PDF 附件应通过扩展名、MIME 与文件头校验。by AI.Coding"""
    extension, mime_type = validate_attachment_bytes(
        "error-report.pdf",
        "application/pdf",
        b"%PDF-1.7\ncontent",
    )

    assert extension == ".pdf"
    assert mime_type == "application/pdf"


@pytest.mark.parametrize(
    ("filename", "content_type", "content"),
    [
        ("../secret.txt", "text/plain", b"secret"),
        ("photo.png", "image/png", b"not-a-png"),
        ("report.pdf", "text/plain", b"%PDF-1.7"),
        ("script.exe", "application/octet-stream", b"MZ"),
    ],
)
def test_attachment_validation_rejects_unsafe_inputs(
    filename: str,
    content_type: str,
    content: bytes,
) -> None:
    """路径穿越、magic 不匹配、MIME 错误和不支持扩展名必须拒绝。by AI.Coding"""
    with pytest.raises(DomainValidationError):
        validate_attachment_bytes(filename, content_type, content)
