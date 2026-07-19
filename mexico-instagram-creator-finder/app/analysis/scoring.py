"""100 分透明评分系统。

分项权重：
- 墨西哥地区可信度: 25
- 垂类匹配度: 25
- 近期 Reels 表现: 20
- 内容活跃度: 10
- 粉丝区间匹配度: 10
- 公开商务联系方式: 5
- 个人创作者可信度: 5
总分: 100

推荐级别：
- A: >=80 重点人工检查
- B: >=60 值得人工检查
- C: >=40 信息不足
- D: <40 不符合当前条件
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.models import (
    AccountTypeClassification,
    ContactInfo,
    MediaMetrics,
    MexicoSignal,
    NicheClassification,
    ProfileData,
    ScoreResult,
)

logger = get_logger("analysis.scoring")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_score(
    profile: ProfileData,
    mexico: MexicoSignal,
    niche: NicheClassification,
    metrics: MediaMetrics,
    contact: ContactInfo,
    account_type: AccountTypeClassification,
    *,
    min_followers: int = 20000,
    max_followers: int = 300000,
    minimum_median_reel_views: int = 2000,
    maximum_days_since_last_post: int = 90,
) -> ScoreResult:
    """
    计算透明评分。

    评分仅为与搜索条件的匹配程度，不描述个人价值或外貌。
    """
    breakdown: dict[str, float] = {}
    reasons: list[str] = []

    # 1. 墨西哥地区可信度 (25 分)
    mx_score = _clamp(mexico.mexico_confidence_score) * 25
    breakdown["mexico_region"] = round(mx_score, 2)
    if mexico.mexico_confidence_score >= 0.6:
        reasons.append(f"墨西哥信号置信度 {mexico.mexico_confidence_score}")
    elif mexico.mexico_confidence_score > 0:
        reasons.append(f"墨西哥信号较弱 ({mexico.mexico_confidence_score})")

    # 2. 垂类匹配度 (25 分)
    target_niches = ["perfume", "beauty", "skincare", "makeup", "fashion", "lifestyle", "UGC"]
    if niche.primary_niche in target_niches:
        niche_score = niche.niche_scores.get(niche.primary_niche, 0.5) * 25
    else:
        niche_score = 0.0
        if niche.primary_niche == "general":
            reasons.append("垂类为 general，无目标垂类匹配")
        else:
            reasons.append(f"垂类 {niche.primary_niche} 不在目标列表")
    breakdown["niche_match"] = round(niche_score, 2)

    # 3. 近期 Reels 表现 (20 分)
    reels_score = 0.0
    if metrics.reels_view_data_available == "available" and metrics.median_visible_reel_views is not None:
        # 中位数 >= minimum_median_reel_views 得满分
        if metrics.median_visible_reel_views >= minimum_median_reel_views:
            reels_score = 20.0
        else:
            # 线性缩放
            reels_score = _clamp(metrics.median_visible_reel_views / minimum_median_reel_views) * 20
        reasons.append(f"Reels 中位播放量 {metrics.median_visible_reel_views}")
    elif metrics.reels_view_data_available == "not_visible":
        reels_score = 5.0  # 有 Reels 但数据不可见，给少量分
        reasons.append("Reels 播放量不可见")
    else:
        reels_score = 0.0
        reasons.append("无 Reels")
    breakdown["reels_performance"] = round(reels_score, 2)

    # 4. 内容活跃度 (10 分)
    activity_score = 0.0
    if metrics.days_since_last_post is not None:
        if metrics.days_since_last_post <= 30:
            activity_score = 10.0
        elif metrics.days_since_last_post <= maximum_days_since_last_post:
            # 30-90 天线性衰减
            activity_score = 10.0 * (1 - (metrics.days_since_last_post - 30) / (maximum_days_since_last_post - 30))
        else:
            activity_score = 0.0
            reasons.append(f"停更 {metrics.days_since_last_post} 天")
    breakdown["content_activity"] = round(activity_score, 2)

    # 5. 粉丝区间匹配度 (10 分)
    followers = profile.follower_count or 0
    follower_score = 0.0
    if min_followers <= followers <= max_followers:
        follower_score = 10.0
    elif followers < min_followers:
        # 粉丝不足，按比例给分
        follower_score = _clamp(followers / min_followers) * 5.0
        reasons.append(f"粉丝数 {followers} 低于下限 {min_followers}")
    else:
        # 粉丝超出上限
        follower_score = 5.0
        reasons.append(f"粉丝数 {followers} 超过上限 {max_followers}")
    breakdown["follower_range"] = round(follower_score, 2)

    # 6. 公开商务联系方式 (5 分)
    contact_score = 5.0 if contact.has_public_contact else 0.0
    breakdown["public_contact"] = round(contact_score, 2)

    # 7. 个人创作者可信度 (5 分)
    creator_score = 0.0
    if account_type.account_type in ("personal_creator", "ugc_creator"):
        creator_score = 5.0 * account_type.account_type_confidence
    elif account_type.account_type == "brand":
        creator_score = 0.0
        reasons.append("账号类型为 brand")
    elif account_type.account_type in ("media", "news"):
        creator_score = 0.0
        reasons.append("账号类型为 media/news")
    else:
        creator_score = 1.0
    breakdown["creator_trust"] = round(creator_score, 2)

    total = sum(breakdown.values())
    total = round(min(total, 100.0), 2)

    # 推荐级别
    if total >= 80:
        level = "A"
    elif total >= 60:
        level = "B"
    elif total >= 40:
        level = "C"
    else:
        level = "D"

    if not reasons:
        reasons.append(f"总分 {total}，推荐级别 {level}")

    return ScoreResult(
        total_score=total,
        score_breakdown=breakdown,
        recommendation_level=level,
        recommendation_reasons=reasons,
    )
