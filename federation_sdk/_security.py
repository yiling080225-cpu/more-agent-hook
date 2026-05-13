"""安全相关工具：脱敏、路径校验。"""
from __future__ import annotations

import re
from pathlib import Path

_SENSITIVE_KEYS = {"key", "token", "secret", "password", "auth", "credential"}


def mask_sensitive(data: dict) -> dict:
    """递归脱敏敏感字段，值为 '***'。"""
    result = {}
    for k, v in data.items():
        k_lower = k.lower()
        if any(s in k_lower for s in _SENSITIVE_KEYS):
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = mask_sensitive(v)
        elif isinstance(v, list):
            result[k] = [mask_sensitive(item) if isinstance(item, dict) else item for item in v]
        else:
            result[k] = v
    return result


def safe_path(user_path: str, base_dir: str | Path) -> Path:
    """解析路径并确保在 base_dir 范围内，防止路径穿越。"""
    base = Path(base_dir).resolve()
    resolved = (base / user_path).resolve()
    if not str(resolved).startswith(str(base)):
        raise ValueError(f"路径穿越检测: {user_path}")
    return resolved


def validate_base_url(url: str) -> str:
    """校验 base_url 安全。"""
    if not url.startswith(("http://", "https://")):
        raise ValueError("base_url 必须以 http:// 或 https:// 开头")
    if "@" in url.replace("://", ""):
        raise ValueError("base_url 禁止包含认证信息")
    return url.rstrip("/")
