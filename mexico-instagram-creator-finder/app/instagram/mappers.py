"""将 instagrapi 类型映射为项目内部 Pydantic 模型。

只提取公开字段，不保存任何私密数据。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models import CandidateAccount, MediaMetrics, ProfileData


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def map_user_to_profile(user: Any, username: str | None = None) -> ProfileData:
    """
    将 instagrapi.types.User 映射为 ProfileData。

    只提取公开字段，不保存密码、Session、私信。
    """
    uname = username or getattr(user, "username", None) or ""
    profile_url = f"https://www.instagram.com/{uname}/" if uname else None

    return ProfileData(
        username=uname,
        pk=_to_str(getattr(user, "pk", None)),
        full_name=getattr(user, "full_name", None),
        biography=getattr(user, "biography", None) or None,
        profile_url=profile_url,
        profile_pic_url=_to_str(getattr(user, "profile_pic_url", None)),
        follower_count=getattr(user, "follower_count", None),
        following_count=getattr(user, "following_count", None),
        media_count=getattr(user, "media_count", None),
        is_private=bool(getattr(user, "is_private", False)),
        is_verified=bool(getattr(user, "is_verified", False)),
        is_business=bool(getattr(user, "is_business", False)),
        category_name=getattr(user, "category_name", None),
        business_category_name=getattr(user, "business_category_name", None),
        external_url=_to_str(getattr(user, "external_url", None)),
        public_email=getattr(user, "public_email", None),
        collected_at=datetime.now(UTC),
    )


def map_media_to_candidate(media: Any, hashtag: str) -> CandidateAccount | None:
    """
    从 instagrapi.types.Media 提取作者作为 CandidateAccount。

    Returns:
        CandidateAccount，或 None（无作者时）。
    """
    user = getattr(media, "user", None)
    if user is None:
        return None
    uname = getattr(user, "username", None)
    if not uname:
        return None
    return CandidateAccount(
        username=uname,
        source_hashtags=[hashtag],
        discovered_at=datetime.now(UTC),
        normalized=False,
    )


def compute_media_metrics(medias: list[Any]) -> MediaMetrics:
    """
    根据 instagrapi.types.Media 列表计算 MediaMetrics。

    区分三态：
    - no_reels：没有 Reels
    - not_visible：发布了 Reels 但 view_count=None 或 like_and_view_counts_disabled=true
    - available：有可计算播放量
    """
    import statistics

    if not medias:
        return MediaMetrics(reels_view_data_available="no_reels")

    likes: list[int] = []
    comments: list[int] = []
    reel_views: list[int] = []
    reels_count = 0
    reels_views_disabled = False
    last_post_date: datetime | None = None

    for m in medias:
        like_count = getattr(m, "like_count", None) or 0
        comment_count = getattr(m, "comment_count", None) or 0
        likes.append(like_count)
        comments.append(comment_count)

        taken_at = getattr(m, "taken_at", None)
        if taken_at is not None:
            if last_post_date is None or taken_at > last_post_date:
                last_post_date = taken_at

        media_type = getattr(m, "media_type", None)
        product_type = getattr(m, "product_type", None)
        is_reel = media_type == 2 or product_type == "clips" or product_type == "igtv"
        if is_reel:
            reels_count += 1
            counts_disabled = bool(getattr(m, "like_and_view_counts_disabled", False))
            view_count = getattr(m, "view_count", None)
            play_count = getattr(m, "play_count", None)
            if counts_disabled or (view_count is None and play_count is None):
                reels_views_disabled = True
            else:
                v = view_count if view_count is not None else play_count
                if v is not None and v >= 0:
                    reel_views.append(int(v))

    # 三态判定
    if reels_count == 0:
        reels_state = "no_reels"
    elif reel_views and not reels_views_disabled:
        reels_state = "available"
    else:
        reels_state = "not_visible"

    days_since = None
    if last_post_date is not None:
        now = datetime.now(UTC)
        if last_post_date.tzinfo is None:
            last_post_date = last_post_date.replace(tzinfo=UTC)
        days_since = max(0, (now - last_post_date).days)

    posting_freq = None
    if len(medias) >= 2 and last_post_date is not None:
        earliest = min(
            (getattr(m, "taken_at", last_post_date) for m in medias if getattr(m, "taken_at", None)),
            default=last_post_date,
        )
        if earliest is not None:
            if earliest.tzinfo is None:
                earliest = earliest.replace(tzinfo=UTC)
            span_days = max(1, (last_post_date - earliest).days)
            posting_freq = round(len(medias) / span_days * 7.0, 2)

    return MediaMetrics(
        recent_media_checked=len(medias),
        recent_reels_checked=reels_count,
        last_post_date=last_post_date,
        days_since_last_post=days_since,
        average_likes=round(statistics.mean(likes), 2) if likes else None,
        median_likes=statistics.median(likes) if likes else None,
        average_comments=round(statistics.mean(comments), 2) if comments else None,
        median_comments=statistics.median(comments) if comments else None,
        average_visible_reel_views=round(statistics.mean(reel_views), 2) if reel_views else None,
        median_visible_reel_views=statistics.median(reel_views) if reel_views else None,
        maximum_visible_reel_views=max(reel_views) if reel_views else None,
        posting_frequency=posting_freq,
        reels_view_data_available=reels_state,
    )
