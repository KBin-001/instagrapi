"""Hashtag 发现：从 Hashtag 帖子和 Reels 提取候选账号。"""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.discovery.deduplication import normalize_username
from app.exceptions import SecurityStopError
from app.instagram.client import InstagramClient
from app.instagram.mappers import map_media_to_candidate
from app.logging_config import get_logger
from app.models import CandidateAccount

logger = get_logger("discovery.hashtag")


def discover_from_hashtags(
    client: InstagramClient,
    settings: Settings,
    hashtags: list[str],
    on_hashtag_done: Any | None = None,
) -> list[CandidateAccount]:
    """
    从 Hashtag 列表发现候选账号。

    受以下限制：
    - discovery.max_hashtags：本次最多处理多少个 Hashtag
    - discovery.media_per_hashtag：每个 Hashtag 最多获取多少条媒体
    - discovery.max_candidates：累计候选账号数上限

    Args:
        client: 已登录的 InstagramClient
        settings: 项目配置
        hashtags: Hashtag 名称列表（不带 #）
        on_hashtag_done: 可选回调，每完成一个 Hashtag 调用一次（hashtag_name, candidates_count）

    Returns:
        候选账号列表（已按 username 去重，未应用排除名单）。
    """
    max_hashtags = settings.discovery.max_hashtags
    media_per_hashtag = settings.discovery.media_per_hashtag
    max_candidates = settings.discovery.max_candidates

    selected = hashtags[:max_hashtags]
    logger.info("discovering from %d hashtags (max %d)", len(selected), max_hashtags)

    all_candidates: list[CandidateAccount] = []
    seen_usernames: set[str] = set()

    for i, tag in enumerate(selected, start=1):
        tag_lower = tag.lower().lstrip("#")
        logger.info("[%d/%d] fetching media for #%s", i, len(selected), tag_lower)

        try:
            medias = client.hashtag_medias(tag_lower, amount=media_per_hashtag)
        except SecurityStopError:
            logger.error("security stop while fetching #%s; aborting discovery", tag_lower)
            raise
        except Exception as e:
            logger.warning("failed to fetch #%s: %s", tag_lower, e)
            if on_hashtag_done:
                on_hashtag_done(tag_lower, 0)
            continue

        added = 0
        for media in medias:
            candidate = map_media_to_candidate(media, tag_lower)
            if candidate is None:
                continue
            uname = normalize_username(candidate.username)
            if uname is None or uname in seen_usernames:
                continue
            seen_usernames.add(uname)
            candidate.username = uname
            candidate.normalized = True
            all_candidates.append(candidate)
            added += 1
            if len(all_candidates) >= max_candidates:
                logger.info("max_candidates (%d) reached; stopping", max_candidates)
                if on_hashtag_done:
                    on_hashtag_done(tag_lower, added)
                return all_candidates

        logger.info("[%d/%d] #%s: +%d candidates (total=%d)", i, len(selected), tag_lower, added, len(all_candidates))
        if on_hashtag_done:
            on_hashtag_done(tag_lower, added)

    return all_candidates
