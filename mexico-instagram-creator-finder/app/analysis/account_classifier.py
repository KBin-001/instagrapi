"""账号类型识别。

区分个人创作者与品牌/媒体/机构等。不直接删除疑似账号，仅标记。
"""

from __future__ import annotations

from typing import Any

from app.config import load_excluded_terms
from app.logging_config import get_logger
from app.models import AccountTypeClassification, ProfileData

logger = get_logger("analysis.account_classifier")


def _to_lower_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).lower()


def classify_account_type(
    profile: ProfileData,
    source_hashtags: list[str] | None = None,
    config_dir: Any = None,
) -> AccountTypeClassification:
    """
    区分：
    - personal_creator：个人创作者
    - ugc_creator：UGC 创作者
    - brand：品牌
    - shop：商店
    - media：媒体
    - news：新闻账号
    - agency：经纪公司
    - marketing：营销机构
    - fan_reposter：粉丝搬运账号
    - topic_aggregator：主题聚合账号
    """
    terms = load_excluded_terms(config_dir)
    brand_terms = [t.lower() for t in terms.get("brand_terms", [])]
    media_terms = [t.lower() for t in terms.get("media_terms", [])]
    agency_terms = [t.lower() for t in terms.get("agency_terms", [])]
    shop_terms = [t.lower() for t in terms.get("shop_terms", [])]
    fan_terms = [t.lower() for t in terms.get("fan_terms", [])]
    aggregator_terms = [t.lower() for t in terms.get("aggregator_terms", [])]

    username = _to_lower_str(profile.username)
    bio = _to_lower_str(profile.biography)
    full_name = _to_lower_str(profile.full_name)
    category = _to_lower_str(profile.category_name)
    business_category = _to_lower_str(profile.business_category_name)
    text_pool = f"{username} {bio} {full_name} {category} {business_category}"

    reasons: list[str] = []
    account_type = "personal_creator"
    confidence = 0.5

    # 品牌判定
    brand_hits = [t for t in brand_terms if t and t in text_pool]
    if profile.is_business and len(brand_hits) >= 1:
        account_type = "brand"
        confidence = 0.8
        reasons.append(f"is_business=true 且文本含品牌词: {brand_hits[:3]}")
    elif profile.is_business and "oficial" in username:
        account_type = "brand"
        confidence = 0.9
        reasons.append("username 含 oficial 且为商业账号")
    elif profile.is_business:
        account_type = "brand"
        confidence = 0.6
        reasons.append("is_business=true")

    # 商店判定
    shop_hits = [t for t in shop_terms if t and t in text_pool]
    if shop_hits and account_type == "personal_creator":
        account_type = "shop"
        confidence = 0.7
        reasons.append(f"文本含商店词: {shop_hits[:3]}")

    # 媒体判定
    media_hits = [t for t in media_terms if t and t in text_pool]
    if media_hits and account_type in ("personal_creator", "shop"):
        account_type = "media"
        confidence = 0.75
        reasons.append(f"文本含媒体词: {media_hits[:3]}")
        if "news" in text_pool or "noticias" in text_pool:
            account_type = "news"
            confidence = 0.8
            reasons.append("含 news/noticias 标识，升级为 news")

    # 经纪公司/营销机构
    agency_hits = [t for t in agency_terms if t and t in text_pool]
    if agency_hits and account_type == "personal_creator":
        if "management" in text_pool or "talent" in text_pool:
            account_type = "agency"
            confidence = 0.75
            reasons.append(f"文本含经纪词: {agency_hits[:3]}")
        else:
            account_type = "marketing"
            confidence = 0.7
            reasons.append(f"文本含营销词: {agency_hits[:3]}")

    # 粉丝搬运
    fan_hits = [t for t in fan_terms if t and t in text_pool]
    if fan_hits and account_type == "personal_creator":
        account_type = "fan_reposter"
        confidence = 0.7
        reasons.append(f"文本含粉丝搬运词: {fan_hits[:3]}")

    # 主题聚合
    aggregator_hits = [t for t in aggregator_terms if t and t in text_pool]
    if aggregator_hits and account_type == "personal_creator":
        account_type = "topic_aggregator"
        confidence = 0.65
        reasons.append(f"文本含聚合词: {aggregator_hits[:3]}")

    # UGC 创作者
    if account_type == "personal_creator":
        ugc_keywords = [
            "ugc",
            "user generated content",
            "creador de contenido",
            "creadora de contenido",
            "content creator",
        ]
        if any(k in bio for k in ugc_keywords) or any(k in full_name for k in ugc_keywords):
            account_type = "ugc_creator"
            confidence = 0.7
            reasons.append("biography/full_name 含 UGC 创作者标识")

    if not reasons:
        reasons.append("未命中品牌/媒体/机构/粉丝/聚合信号，默认个人创作者")

    return AccountTypeClassification(
        account_type=account_type,
        account_type_confidence=round(confidence, 2),
        account_type_reasons=reasons,
    )
