"""用户名标准化、去重与 Instagram URL 解析。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Instagram URL 模式
_INSTAGRAM_URL_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?(?:[?#].*)?$",
    re.IGNORECASE,
)

# 合法 username 字符
_USERNAME_VALID_PATTERN = re.compile(r"^[A-Za-z0-9._]+$")

# Instagram 保留字（路径段），不作为有效 username
_RESERVED_WORDS = frozenset({"accounts", "explore", "tags", "locations", "p", "reel", "reels", "stories"})


def normalize_username(raw: str) -> str | None:
    """
    标准化用户名：
    - 去除 @
    - 去除 URL（提取 Instagram URL 中的 username）
    - 转小写
    - 去除末尾 /
    - 去除首尾空白
    - 忽略空行
    - 忽略 # 开头的注释

    Returns:
        标准化后的 username（小写），或 None（无效输入）。
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # 注释行
    if text.startswith("#"):
        return None
    # 去除 @
    text = text.lstrip("@")
    # 尝试匹配 Instagram URL
    url_match = _INSTAGRAM_URL_PATTERN.match(text)
    if url_match:
        text = url_match.group(1)
    else:
        # 一般 URL：取 path 最后一段
        if text.startswith("http://") or text.startswith("https://"):
            try:
                parsed = urlparse(text)
                path = parsed.path.strip("/")
                if "/" in path:
                    text = path.split("/")[-1]
                else:
                    text = path
            except Exception:
                return None
    # 去除末尾 /
    text = text.rstrip("/")
    # 转小写
    text = text.lower().strip()
    if not text:
        return None
    # 合法性校验
    if not _USERNAME_VALID_PATTERN.match(text):
        return None
    # 排除保留字
    if text in _RESERVED_WORDS:
        return None
    return text


def _is_reserved_word(raw: str) -> bool:
    """判断原始输入是否为 Instagram 保留字（URL 或 @ 形式都支持）。"""
    if raw is None:
        return False
    text = str(raw).strip()
    if not text:
        return False
    # 去除 @ 前缀
    text = text.lstrip("@")
    # 尝试从 Instagram URL 提取
    url_match = _INSTAGRAM_URL_PATTERN.match(text)
    if url_match:
        text = url_match.group(1)
    text = text.rstrip("/").lower().strip()
    return text in _RESERVED_WORDS


def parse_username_list(raw_items: list[str]) -> tuple[list[str], list[str]]:
    """
    批量标准化用户名列表。

    Returns:
        (valid_usernames, invalid_raw) — 已去重的小写 username 列表 + 无法解析的原始值。

    注意：保留字（accounts/explore 等）和空行/注释不计入 invalid。
    """
    seen: set[str] = set()
    valid: list[str] = []
    invalid: list[str] = []
    for raw in raw_items:
        # 保留字静默过滤（不计入 invalid）
        if _is_reserved_word(raw):
            continue
        norm = normalize_username(raw)
        if norm is None:
            if raw and not str(raw).strip().startswith("#") and str(raw).strip():
                invalid.append(str(raw).strip())
            continue
        if norm not in seen:
            seen.add(norm)
            valid.append(norm)
    return valid, invalid


def deduplicate_candidates(candidates: list) -> list:
    """
    对 CandidateAccount 列表去重（按 username），合并 source_hashtags。

    Args:
        candidates: CandidateAccount 对象列表

    Returns:
        去重后的列表（保留首次发现的 discovered_at）
    """
    from app.models import CandidateAccount

    merged: dict[str, CandidateAccount] = {}
    for c in candidates:
        uname = normalize_username(c.username) if not c.normalized else c.username.lower()
        if uname is None:
            continue
        if uname in merged:
            existing = merged[uname]
            # 合并 source_hashtags
            for h in c.source_hashtags:
                if h not in existing.source_hashtags:
                    existing.source_hashtags.append(h)
        else:
            new_c = CandidateAccount(
                username=uname,
                source_hashtags=list(c.source_hashtags),
                discovered_at=c.discovered_at,
                normalized=True,
            )
            merged[uname] = new_c
    return list(merged.values())
