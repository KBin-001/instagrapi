"""地点发现入口（MVP 阶段预留）。

完整实现见后续阶段：从公开地点页面提取候选账号。
"""

from __future__ import annotations

from typing import Any

from app.instagram.client import InstagramClient
from app.logging_config import get_logger
from app.models import CandidateAccount

logger = get_logger("discovery.location")


def discover_from_locations(
    client: InstagramClient,
    settings: Any,
    location_ids: list[str] | None = None,
) -> list[CandidateAccount]:
    """
    从地点发现候选账号（MVP 阶段返回空列表）。
    """
    logger.info("location discovery is not implemented in MVP; returning empty list")
    return []
