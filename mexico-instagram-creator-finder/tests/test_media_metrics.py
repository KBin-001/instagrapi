"""近期内容指标测试。

覆盖：
- app/instagram/mappers.py：compute_media_metrics
- app/analysis/media_metrics.py：analyze_media_metrics、extract_recent_captions、extract_recent_hashtags
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.analysis.media_metrics import (
    analyze_media_metrics,
    extract_recent_captions,
    extract_recent_hashtags,
)
from app.config import Settings
from app.instagram.mappers import compute_media_metrics


class FakeMedia:
    """模拟 instagrapi.types.Media 的 Fake 对象。

    仅暴露 compute_media_metrics 所需的属性，不导入 instagrapi 真实类型。
    """

    def __init__(
        self,
        *,
        like_count: int | None = 0,
        comment_count: int | None = 0,
        taken_at: datetime | None = None,
        media_type: int | None = 1,
        product_type: str | None = None,
        view_count: int | None = None,
        play_count: int | None = None,
        like_and_view_counts_disabled: bool = False,
        caption_text: str = "",
        pk: str | None = None,
    ) -> None:
        self.like_count = like_count
        self.comment_count = comment_count
        self.taken_at = taken_at
        self.media_type = media_type
        self.product_type = product_type
        self.view_count = view_count
        self.play_count = play_count
        self.like_and_view_counts_disabled = like_and_view_counts_disabled
        self.caption_text = caption_text
        self.pk = pk


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- 无 Reels 场景 ----------


def test_no_reels_state() -> None:
    """所有 media_type=1（图片）→ reels_view_data_available=no_reels。"""
    now = _now()
    medias = [
        FakeMedia(like_count=100, comment_count=10, taken_at=now, media_type=1),
        FakeMedia(like_count=200, comment_count=20, taken_at=now, media_type=1),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.reels_view_data_available == "no_reels"
    assert metrics.recent_reels_checked == 0
    # 播放量字段应为 None（不是 0）
    assert metrics.average_visible_reel_views is None
    assert metrics.median_visible_reel_views is None
    assert metrics.maximum_visible_reel_views is None


def test_empty_medias_returns_no_reels() -> None:
    """空 medias → no_reels。"""
    metrics = compute_media_metrics([])
    assert metrics.reels_view_data_available == "no_reels"
    assert metrics.recent_media_checked == 0
    assert metrics.average_likes is None


# ---------- 有 Reels 但播放量不可见 ----------


def test_reels_not_visible_state() -> None:
    """media_type=2 + like_and_view_counts_disabled=true → not_visible。"""
    now = _now()
    medias = [
        FakeMedia(
            like_count=100,
            comment_count=10,
            taken_at=now,
            media_type=2,
            like_and_view_counts_disabled=True,
        ),
        FakeMedia(
            like_count=200,
            comment_count=20,
            taken_at=now,
            media_type=2,
            view_count=None,
        ),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.reels_view_data_available == "not_visible"
    assert metrics.recent_reels_checked == 2
    # 播放量字段为 None
    assert metrics.average_visible_reel_views is None
    assert metrics.median_visible_reel_views is None
    assert metrics.maximum_visible_reel_views is None


def test_reels_not_visible_view_count_none() -> None:
    """media_type=2 + view_count=None → not_visible。"""
    now = _now()
    medias = [
        FakeMedia(
            like_count=100,
            comment_count=10,
            taken_at=now,
            media_type=2,
            view_count=None,
            play_count=None,
        ),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.reels_view_data_available == "not_visible"
    assert metrics.average_visible_reel_views is None


# ---------- 有可计算播放量 ----------


def test_reels_available_state() -> None:
    """media_type=2 + view_count=1000/2000/3000 → available。"""
    now = _now()
    medias = [
        FakeMedia(like_count=100, comment_count=10, taken_at=now, media_type=2, view_count=1000),
        FakeMedia(like_count=200, comment_count=20, taken_at=now, media_type=2, view_count=2000),
        FakeMedia(like_count=300, comment_count=30, taken_at=now, media_type=2, view_count=3000),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.reels_view_data_available == "available"
    assert metrics.recent_reels_checked == 3
    assert metrics.average_visible_reel_views == 2000.0
    assert metrics.median_visible_reel_views == 2000.0
    assert metrics.maximum_visible_reel_views == 3000


def test_reels_available_with_play_count() -> None:
    """使用 play_count 作为播放量。"""
    now = _now()
    medias = [
        FakeMedia(
            like_count=100,
            comment_count=10,
            taken_at=now,
            media_type=2,
            view_count=None,
            play_count=5000,
        ),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.reels_view_data_available == "available"
    assert metrics.maximum_visible_reel_views == 5000


# ---------- None 与 0 的区分 ----------


def test_none_vs_zero_distinction_no_reels() -> None:
    """不得用 0 混淆无 Reels 状态。"""
    now = _now()
    medias = [FakeMedia(like_count=100, taken_at=now, media_type=1)]
    metrics = compute_media_metrics(medias)
    assert metrics.reels_view_data_available == "no_reels"
    # 应为 None 而非 0
    assert metrics.median_visible_reel_views is None
    assert metrics.maximum_visible_reel_views is None


def test_none_vs_zero_distinction_not_visible() -> None:
    """不得用 0 混淆播放量不可见状态。"""
    now = _now()
    medias = [
        FakeMedia(
            like_count=100,
            taken_at=now,
            media_type=2,
            like_and_view_counts_disabled=True,
        )
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.reels_view_data_available == "not_visible"
    assert metrics.median_visible_reel_views is None
    assert metrics.maximum_visible_reel_views is None


# ---------- 点赞与评论 ----------


def test_average_and_median_likes() -> None:
    """median_likes / average_likes 正确。"""
    now = _now()
    medias = [
        FakeMedia(like_count=100, comment_count=10, taken_at=now, media_type=1),
        FakeMedia(like_count=200, comment_count=20, taken_at=now, media_type=1),
        FakeMedia(like_count=300, comment_count=30, taken_at=now, media_type=1),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.average_likes == 200.0
    assert metrics.median_likes == 200.0
    assert metrics.average_comments == 20.0
    assert metrics.median_comments == 20.0


def test_likes_with_zero() -> None:
    """like_count 为 0 也能正确计算。"""
    now = _now()
    medias = [
        FakeMedia(like_count=0, comment_count=0, taken_at=now, media_type=1),
        FakeMedia(like_count=100, comment_count=5, taken_at=now, media_type=1),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.average_likes == 50.0
    assert metrics.median_likes == 50.0


# ---------- 时间相关 ----------


def test_last_post_date_is_max_taken_at() -> None:
    """last_post_date 取最大 taken_at。"""
    t1 = _now() - timedelta(days=10)
    t2 = _now() - timedelta(days=2)
    t3 = _now() - timedelta(days=5)
    medias = [
        FakeMedia(like_count=10, taken_at=t1, media_type=1),
        FakeMedia(like_count=20, taken_at=t2, media_type=1),
        FakeMedia(like_count=30, taken_at=t3, media_type=1),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.last_post_date == t2


def test_days_since_last_post() -> None:
    """days_since_last_post 计算（构造过去的 taken_at）。"""
    past = _now() - timedelta(days=15)
    medias = [FakeMedia(like_count=10, taken_at=past, media_type=1)]
    metrics = compute_media_metrics(medias)
    assert metrics.days_since_last_post is not None
    assert metrics.days_since_last_post >= 15


def test_naive_datetime_handled() -> None:
    """naive datetime（无 tzinfo）也能处理。"""
    # 用 UTC 时间构造 naive datetime，避免 local time 与 UTC 比较产生时差
    naive_past = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
    medias = [FakeMedia(like_count=10, taken_at=naive_past, media_type=1)]
    metrics = compute_media_metrics(medias)
    assert metrics.days_since_last_post is not None
    assert metrics.days_since_last_post >= 10


def test_posting_frequency() -> None:
    """posting_frequency 计算。"""
    now = _now()
    medias = [
        FakeMedia(like_count=10, taken_at=now - timedelta(days=7), media_type=1),
        FakeMedia(like_count=20, taken_at=now - timedelta(days=3), media_type=1),
        FakeMedia(like_count=30, taken_at=now, media_type=1),
    ]
    metrics = compute_media_metrics(medias)
    assert metrics.posting_frequency is not None
    assert metrics.posting_frequency > 0


# ---------- extract_recent_captions / extract_recent_hashtags ----------


def test_extract_recent_captions() -> None:
    """extract_recent_captions 提取并截断。"""
    medias = [
        FakeMedia(caption_text="hello world"),
        FakeMedia(caption_text=""),
        FakeMedia(caption_text="another caption"),
    ]
    captions = extract_recent_captions(medias)
    assert captions == ["hello world", "another caption"]


def test_extract_recent_captions_max_length() -> None:
    """caption 截断到 max_length。"""
    long_text = "x" * 100
    medias = [FakeMedia(caption_text=long_text)]
    captions = extract_recent_captions(medias, max_length=10)
    assert len(captions[0]) == 10


def test_extract_recent_hashtags() -> None:
    """extract_recent_hashtags 提取 #hashtag。"""
    medias = [
        FakeMedia(caption_text="hola #perfume #beauty"),
        FakeMedia(caption_text="test #skincare"),
    ]
    hashtags = extract_recent_hashtags(medias)
    assert "perfume" in hashtags
    assert "beauty" in hashtags
    assert "skincare" in hashtags


# ---------- analyze_media_metrics ----------


def test_analyze_media_metrics_applies_amount_limit() -> None:
    """analyze_media_metrics 应用 recent_media_amount 上限。"""
    settings = Settings()
    settings.analysis.recent_media_amount = 2
    now = _now()
    medias = [
        FakeMedia(like_count=10, taken_at=now, media_type=1),
        FakeMedia(like_count=20, taken_at=now, media_type=1),
        FakeMedia(like_count=30, taken_at=now, media_type=1),
        FakeMedia(like_count=40, taken_at=now, media_type=1),
    ]
    metrics = analyze_media_metrics(medias, settings)
    assert metrics.recent_media_checked == 2


def test_analyze_media_metrics_returns_media_metrics() -> None:
    """analyze_media_metrics 返回 MediaMetrics 对象。"""
    settings = Settings()
    settings.analysis.recent_media_amount = 12
    now = _now()
    medias = [
        FakeMedia(like_count=10, taken_at=now, media_type=2, view_count=1000),
    ]
    metrics = analyze_media_metrics(medias, settings)
    assert metrics.recent_media_checked == 1
    assert metrics.reels_view_data_available == "available"
