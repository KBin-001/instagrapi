"""评分系统测试。

覆盖 app/analysis/scoring.py：compute_score
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.analysis.scoring import compute_score
from app.models import (
    AccountTypeClassification,
    ContactInfo,
    MediaMetrics,
    MexicoSignal,
    NicheClassification,
    ProfileData,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _make_profile(
    *,
    follower_count: int | None = 50000,
    username: str = "testuser",
) -> ProfileData:
    return ProfileData(
        username=username,
        follower_count=follower_count,
        collected_at=_now(),
    )


def _make_mexico(confidence: float = 1.0) -> MexicoSignal:
    return MexicoSignal(
        mexico_confidence_score=confidence,
        mexico_signals=["bio=Mexico"],
        detected_country="Mexico" if confidence > 0 else None,
    )


def _make_niche(primary: str = "perfume", score: float = 1.0) -> NicheClassification:
    return NicheClassification(
        primary_niche=primary,
        niche_scores={primary: score},
        niche_signals=["bio keyword"],
        classification_reasons=[],
    )


def _make_metrics(
    *,
    reels_state: str = "available",
    median_views: float | None = 5000,
    days_since: int | None = 5,
) -> MediaMetrics:
    return MediaMetrics(
        recent_media_checked=12,
        recent_reels_checked=5,
        last_post_date=_now() - timedelta(days=days_since or 0),
        days_since_last_post=days_since,
        average_likes=500.0,
        median_likes=500.0,
        average_comments=20.0,
        median_comments=20.0,
        average_visible_reel_views=median_views,
        median_visible_reel_views=median_views,
        maximum_visible_reel_views=int(median_views) if median_views else None,
        posting_frequency=3.0,
        reels_view_data_available=reels_state,
    )


def _make_contact(
    *,
    email: str | None = "contact@brand.com",
    whatsapp: str | None = "https://wa.me/521234567890",
) -> ContactInfo:
    return ContactInfo(
        public_email=email,
        public_whatsapp_url=whatsapp,
        external_url="https://brand.com",
        linktree_url="https://linktr.ee/brand",
        beacons_url=None,
        contact_source="biography",
        has_public_contact=True,
    )


def _make_account_type(atype: str = "personal_creator", confidence: float = 0.9) -> AccountTypeClassification:
    return AccountTypeClassification(
        account_type=atype,
        account_type_confidence=confidence,
        account_type_reasons=["test"],
    )


# ---------- 满分场景 ----------


def test_perfect_scenario_high_score_level_a() -> None:
    """满分场景：墨西哥 confidence=1 + perfume + Reels 中位 5000 + 活跃 + 粉丝 50000 +
    邮箱+WhatsApp + personal_creator → level=A。"""
    profile = _make_profile(follower_count=50000)
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=5000, days_since=5)
    contact = _make_contact(email="x@y.com", whatsapp="https://wa.me/521234567890")
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(
        profile,
        mexico,
        niche,
        metrics,
        contact,
        account_type,
        min_followers=20000,
        max_followers=300000,
        minimum_median_reel_views=2000,
        maximum_days_since_last_post=90,
    )
    assert result.total_score >= 80
    assert result.recommendation_level == "A"


def test_perfect_scenario_near_max_score() -> None:
    """接近满分场景。"""
    profile = _make_profile(follower_count=100000)
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=10000, days_since=3)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    # 各分项接近满分
    assert result.score_breakdown["mexico_region"] == 25.0
    assert result.score_breakdown["niche_match"] == 25.0
    assert result.score_breakdown["reels_performance"] == 20.0
    assert result.score_breakdown["content_activity"] == 10.0
    assert result.score_breakdown["follower_range"] == 10.0
    assert result.score_breakdown["public_contact"] == 5.0
    assert result.score_breakdown["creator_trust"] == 5.0


# ---------- 低分场景 ----------


def test_low_scenario_level_d() -> None:
    """低分场景：墨西哥 confidence=0 + general + 无 Reels + 停更 + 粉丝超出 + 无联系方式 + brand → level=D。"""
    profile = _make_profile(follower_count=500000)  # 超出上限
    mexico = _make_mexico(confidence=0.0)
    niche = _make_niche(primary="general", score=0.0)
    metrics = _make_metrics(reels_state="no_reels", median_views=None, days_since=120)
    contact = ContactInfo(contact_source="none", has_public_contact=False)
    account_type = _make_account_type("brand", confidence=0.9)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert result.total_score < 40
    assert result.recommendation_level == "D"


def test_low_score_breakdown_zero_mexico() -> None:
    """墨西哥 confidence=0 → mexico_region=0。"""
    profile = _make_profile()
    mexico = _make_mexico(confidence=0.0)
    niche = _make_niche(primary="general", score=0.0)
    metrics = _make_metrics(reels_state="no_reels", median_views=None, days_since=120)
    contact = ContactInfo(contact_source="none", has_public_contact=False)
    account_type = _make_account_type("brand", confidence=0.9)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert result.score_breakdown["mexico_region"] == 0.0
    assert result.score_breakdown["niche_match"] == 0.0
    assert result.score_breakdown["reels_performance"] == 0.0


# ---------- 中等场景 ----------


def test_medium_scenario_level_b_or_c() -> None:
    """中等场景：部分信号 → level=B 或 C。"""
    profile = _make_profile(follower_count=50000)
    mexico = _make_mexico(confidence=0.5)
    niche = _make_niche(primary="perfume", score=0.5)
    metrics = _make_metrics(reels_state="available", median_views=1500, days_since=20)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=0.8)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert result.recommendation_level in ("A", "B", "C")
    assert result.total_score >= 40


def test_partial_score_with_not_visible_reels() -> None:
    """Reels 播放量不可见 → 少量分（5 分）。"""
    profile = _make_profile()
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="not_visible", median_views=None, days_since=5)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert result.score_breakdown["reels_performance"] == 5.0


# ---------- 权重总和 ----------


def test_weights_sum_to_100() -> None:
    """验证分项权重总和=100。"""
    profile = _make_profile()
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=10000, days_since=5)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    expected_keys = {
        "mexico_region",  # 25
        "niche_match",  # 25
        "reels_performance",  # 20
        "content_activity",  # 10
        "follower_range",  # 10
        "public_contact",  # 5
        "creator_trust",  # 5
    }
    assert set(result.score_breakdown.keys()) == expected_keys
    # 各权重上限之和 = 100
    max_weights = {
        "mexico_region": 25,
        "niche_match": 25,
        "reels_performance": 20,
        "content_activity": 10,
        "follower_range": 10,
        "public_contact": 5,
        "creator_trust": 5,
    }
    assert sum(max_weights.values()) == 100


# ---------- 推荐级别阈值 ----------


def test_level_thresholds() -> None:
    """验证 level 阈值：>=80=A, >=60=B, >=40=C, <40=D。"""
    # 构造不同分数场景
    # 场景 1: 高分 → A
    profile = _make_profile(follower_count=100000)
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=5000, days_since=5)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)
    result_a = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert result_a.total_score >= 80
    assert result_a.recommendation_level == "A"

    # 场景 2: 极低分 → D
    profile_d = _make_profile(follower_count=500000)
    mexico_d = _make_mexico(confidence=0.0)
    niche_d = _make_niche(primary="general", score=0.0)
    metrics_d = _make_metrics(reels_state="no_reels", median_views=None, days_since=120)
    contact_d = ContactInfo(contact_source="none", has_public_contact=False)
    account_type_d = _make_account_type("brand", confidence=0.9)
    result_d = compute_score(profile_d, mexico_d, niche_d, metrics_d, contact_d, account_type_d)
    assert result_d.total_score < 40
    assert result_d.recommendation_level == "D"


def test_level_b_threshold() -> None:
    """验证 B 级阈值（>=60）。"""
    profile = _make_profile(follower_count=50000)
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=2000, days_since=10)
    contact = ContactInfo(contact_source="none", has_public_contact=False)
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    # 满足多个条件，应至少为 B
    assert result.total_score >= 60
    assert result.recommendation_level in ("A", "B")


# ---------- 不描述个人价值 ----------


def test_no_appearance_evaluation_in_output() -> None:
    """评分仅为匹配程度，不描述个人价值、外貌或可信人格。"""
    profile = _make_profile()
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=5000, days_since=5)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    # 输出字段不含外貌评价
    forbidden_terms = ["外貌", "长相", "颜值", "美丽", "身材", "appearance", "beauty_look"]
    all_text = " ".join(result.recommendation_reasons) + " " + str(result.score_breakdown)
    for term in forbidden_terms:
        assert term not in all_text.lower(), f"评分输出不应包含外貌评价: {term}"


def test_output_fields_present() -> None:
    """输出字段：total_score/score_breakdown/recommendation_level/recommendation_reasons。"""
    profile = _make_profile()
    mexico = _make_mexico(confidence=0.5)
    niche = _make_niche(primary="perfume", score=0.5)
    metrics = _make_metrics(reels_state="available", median_views=2000, days_since=10)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=0.8)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert hasattr(result, "total_score")
    assert hasattr(result, "score_breakdown")
    assert hasattr(result, "recommendation_level")
    assert hasattr(result, "recommendation_reasons")
    assert isinstance(result.score_breakdown, dict)
    assert isinstance(result.recommendation_reasons, list)


# ---------- 边界场景 ----------


def test_followers_below_min_gets_partial_score() -> None:
    """粉丝低于下限 → 部分分。"""
    profile = _make_profile(follower_count=10000)  # 低于 20000 下限
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=5000, days_since=5)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert result.score_breakdown["follower_range"] < 10.0
    assert result.score_breakdown["follower_range"] > 0


def test_followers_above_max_gets_half_score() -> None:
    """粉丝超过上限 → 部分分。"""
    profile = _make_profile(follower_count=500000)  # 超过 300000 上限
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=5000, days_since=5)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    # 超出上限给 5 分
    assert result.score_breakdown["follower_range"] == 5.0


def test_total_score_capped_at_100() -> None:
    """总分不超过 100。"""
    profile = _make_profile(follower_count=100000)
    mexico = _make_mexico(confidence=1.0)
    niche = _make_niche(primary="perfume", score=1.0)
    metrics = _make_metrics(reels_state="available", median_views=100000, days_since=1)
    contact = _make_contact()
    account_type = _make_account_type("personal_creator", confidence=1.0)

    result = compute_score(profile, mexico, niche, metrics, contact, account_type)
    assert result.total_score <= 100.0
