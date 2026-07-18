"""近期内容指标封装。

复用 app.instagram.mappers.compute_media_metrics 计算 MediaMetrics。
另提供从 medias 提取 caption/hashtag 的辅助函数，供垂类分类使用。
"""

from __future__ import annotations

import re
from typing import Any

from app.config import Settings
from app.instagram.mappers import compute_media_metrics
from app.logging_config import get_logger
from app.models import MediaMetrics

logger = get_logger("analysis.media_metrics")


def extract_recent_captions(medias: list[Any], max_length: int = 3000) -> list[str]:
    """从 medias 提取近期 caption 文本（截断到 max_length）。"""
    captions: list[str] = []
    for m in medias:
        caption = getattr(m, "caption_text", None) or ""
        if caption:
            if len(caption) > max_length:
                caption = caption[:max_length]
            captions.append(caption)
    return captions


def extract_recent_hashtags(medias: list[Any]) -> list[str]:
    """从 medias 的 caption 中提取 #hashtag。"""
    pattern = re.compile(r"#([A-Za-z0-9_]+)")
    hashtags: list[str] = []
    for m in medias:
        caption = getattr(m, "caption_text", None) or ""
        hashtags.extend(pattern.findall(caption))
    return hashtags


def analyze_media_metrics(medias: list[Any], settings: Settings) -> MediaMetrics:
    """
    分析近期内容指标。

    内部调用 compute_media_metrics，并应用配置的 recent_media_amount 上限。
    """
    amount = settings.analysis.recent_media_amount
    truncated = medias[:amount]
    return compute_media_metrics(truncated)
