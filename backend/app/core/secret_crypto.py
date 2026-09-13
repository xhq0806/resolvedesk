"""服务端密钥加密工具。by AI.Coding"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretCipher:
    """基于应用密钥派生 Fernet key 的对称加密器。by AI.Coding"""

    def __init__(self, secret_key: str) -> None:
        """从稳定服务端密钥派生 Fernet 所需的 32 字节 key。by AI.Coding"""
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> bytes:
        """加密非空敏感文本并返回可落库密文。by AI.Coding"""
        if not plaintext:
            raise ValueError("敏感文本不能为空。")
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        """解密落库密文，失败时只返回稳定错误。by AI.Coding"""
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("密钥密文无法解密。") from exc


def secret_cipher_from_settings() -> SecretCipher:
    """使用当前 Settings 创建服务端密钥加密器。by AI.Coding"""
    return SecretCipher(settings.SECRET_KEY)
