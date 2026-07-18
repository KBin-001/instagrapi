"""垂类内容分类。

多信号综合判定，不得仅依赖单个关键词。
"""

from __future__ import annotations

from typing import Any

from app.config import load_niche_keywords
from app.logging_config import get_logger
from app.models import NicheClassification, ProfileData

logger = get_logger("analysis.niche_classifier")

# 评分用的目标垂类
_TARGET_NICHES = ["perfume", "beauty", "skincare", "makeup", "fashion", "lifestyle", "UGC"]


def _to_lower_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).lower()


def classify_niche(
    profile: ProfileData,
    source_hashtags: list[str] | None = None,
    recent_captions: list[str] | None = None,
    recent_media_hashtags: list[str] | None = None,
    config_dir: Any = None,
) -> NicheClassification:
    """
    多信号垂类分类。

    信号源：
    - Biography
    - Full name
    - Category
    - 来源 Hashtag
    - 近期 Caption
    - 近期内容 Hashtag
    """
    niche_data = load_niche_keywords(config_dir)
    niches_def = niche_data.get("niches", {})

    bio = _to_lower_str(profile.biography)
    full_name = _to_lower_str(profile.full_name)
    category = _to_lower_str(profile.category_name)
    business_category = _to_lower_str(profile.business_category_name)

    source_ht_lower = [h.lower().lstrip("#") for h in (source_hashtags or [])]
    captions_text = " ".join(_to_lower_str(c) for c in (recent_captions or [])).lower()
    media_ht_lower = [h.lower().lstrip("#") for h in (recent_media_hashtags or [])]

    scores: dict[str, float] = {}
    signals: list[str] = []
    reasons: list[str] = []

    for niche_name, niche_def in niches_def.items():
        keywords = [k.lower() for k in niche_def.get("keywords", [])]
        hashtags = set(h.lower() for h in niche_def.get("hashtags", []))

        signal_count = 0
        niche_signals: list[str] = []

        # 信号 1: Biography 含关键词
        bio_matches = [k for k in keywords if k and k in bio]
        if bio_matches:
            signal_count += 1
            niche_signals.append(f"biography 含 {len(bio_matches)} 个 {niche_name} 关键词")

        # 信号 2: Full name 含关键词
        if any(k and k in full_name for k in keywords):
            signal_count += 1
            niche_signals.append(f"full_name 含 {niche_name} 关键词")

        # 信号 3: Category 含关键词
        if any(k and k in category for k in keywords) or any(k and k in business_category for k in keywords):
            signal_count += 1
            niche_signals.append(f"category 含 {niche_name} 关键词")

        # 信号 4: 来源 Hashtag 命中
        ht_matches = [h for h in source_ht_lower if h in hashtags]
        if ht_matches:
            signal_count += 1
            niche_signals.append(f"来源 Hashtag 命中 {len(ht_matches)} 个 {niche_name} 标签")

        # 信号 5: 近期 Caption 含关键词
        caption_matches = [k for k in keywords if k and k in captions_text]
        if caption_matches:
            signal_count += 1
            niche_signals.append(f"近期 Caption 含 {len(caption_matches)} 个 {niche_name} 关键词")

        # 信号 6: 近期内容 Hashtag 命中
        media_ht_matches = [h for h in media_ht_lower if h in hashtags]
        if media_ht_matches:
            signal_count += 1
            niche_signals.append(f"近期内容 Hashtag 命中 {len(media_ht_matches)} 个 {niche_name} 标签")

        # 得分：信号越多越高，归一化到 0-1
        score = min(1.0, signal_count / 3.0)
        scores[niche_name] = round(score, 2)

        if signal_count > 0:
            signals.extend(niche_signals)

    # 选 primary_niche：得分最高且至少有 2 个独立信号源
    primary = "general"
    max_score = 0.0
    for niche_name in _TARGET_NICHES:
        s = scores.get(niche_name, 0.0)
        if s > max_score:
            max_score = s
            primary = niche_name

    # 单信号源不足以确认 primary
    if max_score > 0 and max_score < 0.4:
        primary = "general"
        reasons.append("单一信号源不足以确认垂类，标记为 general")

    # 品牌类目
    if profile.is_business and profile.business_category_name:
        if any(t in business_category for t in ["perfume", "fragance", "cosmetic", "beauty", "skincare"]):
            scores["brand"] = 0.5
            if primary == "general":
                primary = "brand"
                reasons.append(f"商业账号类目 {profile.business_category_name}")

    if primary == "general" and max_score == 0:
        reasons.append("无垂类信号命中")

    return NicheClassification(
        primary_niche=primary,
        niche_scores=scores,
        niche_signals=signals,
        classification_reasons=reasons,
    )
