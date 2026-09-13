"""Provider 配置的安全校验工具。by AI.Coding"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


def validate_provider_base_url(raw_url: str) -> str:
    """校验模型 Provider base URL，阻断明显本地和内网目标。by AI.Coding"""
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Provider base URL 必须是 http 或 https 地址。")
    hostname = parsed.hostname.lower()
    if hostname in _BLOCKED_HOSTS or hostname.endswith(".local"):
        raise ValueError("Provider base URL 不允许指向本地主机。")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return raw_url.rstrip("/")
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    ):
        raise ValueError("Provider base URL 不允许指向内网地址。")
    return raw_url.rstrip("/")
