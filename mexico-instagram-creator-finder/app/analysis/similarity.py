"""可解释的本地达人相似度，不依赖外部模型或服务。"""

from __future__ import annotations

import math
import re
from collections import Counter

from app.models import (
    AccountTypeClassification,
    ContactInfo,
    MediaMetrics,
    MexicoSignal,
    NicheClassification,
    ProfileData,
    SearchIntent,
)


def _tokens(value: str) -> list[str]:
    lowered = value.lower()
    words = re.findall(r"[a-záéíóúñü0-9_]{2,}", lowered)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    words.extend(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return words


def _tfidf_cosine(left: str, right: str, corpus: list[str]) -> float:
    a, b = Counter(_tokens(left)), Counter(_tokens(right))
    if not a or not b:
        return 0.0
    tokenized_corpus = [set(_tokens(item)) for item in corpus if item]
    total_documents = max(1, len(tokenized_corpus))

    def weight(token: str, frequency: int) -> float:
        document_frequency = sum(1 for document in tokenized_corpus if token in document)
        return frequency * (math.log((total_documents + 1) / (document_frequency + 1)) + 1)

    common = set(a) & set(b)
    numerator = sum(weight(token, a[token]) * weight(token, b[token]) for token in common)
    denominator = math.sqrt(sum(weight(token, value) ** 2 for token, value in a.items())) * math.sqrt(
        sum(weight(token, value) ** 2 for token, value in b.items())
    )
    return numerator / denominator if denominator else 0.0


def profile_document(profile: ProfileData, captions: list[str] | None = None) -> str:
    return " ".join(
        part
        for part in [
            profile.username,
            profile.full_name or "",
            profile.biography or "",
            profile.category_name or "",
            *(captions or []),
        ]
        if part
    )


def _spanish_signal(value: str) -> float:
    tokens = set(_tokens(value))
    markers = {
        "méxico",
        "mexico",
        "perfumes",
        "fragancias",
        "reseñas",
        "belleza",
        "colaboraciones",
        "creadora",
        "creador",
        "envíos",
    }
    return min(1.0, len(tokens & markers) / 3)


def _follower_signal(profile: ProfileData, intent: SearchIntent) -> float:
    followers = profile.follower_count
    if followers is None:
        return 0.0
    low, high = intent.min_followers, intent.max_followers
    if low is not None and followers < low:
        return max(0.0, followers / low)
    if high is not None and followers > high:
        return max(0.0, high / followers)
    return 1.0


def _engagement_signal(profile: ProfileData, metrics: MediaMetrics) -> float:
    followers = profile.follower_count or 0
    if metrics.median_visible_reel_views is not None and followers:
        return min(1.0, metrics.median_visible_reel_views / followers / 0.20)
    if metrics.median_likes is not None and followers:
        return min(1.0, metrics.median_likes / followers / 0.03)
    return 0.0


def compute_local_similarity(
    profile: ProfileData,
    *,
    brief: str,
    seed_documents: dict[str, str],
    niche: NicheClassification,
    mexico: MexicoSignal,
    account_type: AccountTypeClassification,
    metrics: MediaMetrics,
    intent: SearchIntent | None = None,
    contact: ContactInfo | None = None,
    captions: list[str] | None = None,
    source_count: int = 1,
) -> tuple[float, dict[str, object], str | None]:
    """返回 0-100 相似分、透明明细和最相似种子。"""
    document = profile_document(profile, captions)
    corpus = [document, brief, *seed_documents.values()]
    brief_text = _tfidf_cosine(document, brief, corpus)
    reference_seed = None
    seed_text = 0.0
    for username, seed_document in seed_documents.items():
        value = _tfidf_cosine(document, seed_document, corpus)
        if value > seed_text:
            seed_text, reference_seed = value, username

    intent = intent or SearchIntent(raw_brief=brief)
    target_niche_scores = [niche.niche_scores.get(name, 0.0) for name in intent.target_niches]
    niche_signal = min(
        1.0,
        max(target_niche_scores, default=max(niche.niche_scores.values(), default=0.0)),
    )
    mexico_signal = min(1.0, mexico.mexico_confidence_score)
    language_signal = _spanish_signal(document) if "mexico" in intent.target_regions else 0.0
    region_language_signal = min(1.0, mexico_signal * 0.75 + language_signal * 0.25)
    target_types = set(intent.target_account_types)
    if target_types:
        creator_signal = 1.0 if account_type.account_type in target_types else 0.0
    else:
        creator_signal = 1.0 if account_type.account_type in {"personal_creator", "ugc_creator"} else 0.0
    activity_signal = 0.0
    if metrics.days_since_last_post is not None:
        activity_signal = max(0.0, 1.0 - metrics.days_since_last_post / 180)
    provenance_signal = min(1.0, max(0, source_count - 1) / 3)
    follower_signal = _follower_signal(profile, intent)
    engagement_signal = _engagement_signal(profile, metrics)
    contact_signal = 1.0 if contact and contact.has_public_contact else 0.0
    breakdown = {
        "brief_text": round(brief_text * 10, 2),
        "seed_text": round(seed_text * 15, 2),
        "niche": round(niche_signal * 20, 2),
        "region_language": round(region_language_signal * 15, 2),
        "follower_fit": round(follower_signal * 10, 2),
        "engagement": round(engagement_signal * 10, 2),
        "creator_type": round(creator_signal * 5, 2),
        "activity": round(activity_signal * 5, 2),
        "multi_source": round(provenance_signal * 5, 2),
        "public_contact": round(contact_signal * 5, 2),
    }
    reasons: list[str] = []
    if niche_signal >= 0.6:
        reasons.append(f"垂类匹配：{niche.primary_niche}")
    if region_language_signal >= 0.5:
        reasons.append("墨西哥地区或西班牙语信号较强")
    if follower_signal >= 1:
        reasons.append("粉丝数符合 Brief 区间")
    if contact_signal:
        reasons.append("存在公开联系方式")
    if creator_signal:
        reasons.append(f"账号类型匹配：{account_type.account_type}")
    if engagement_signal >= 0.5:
        reasons.append("近期公开互动表现较好")
    breakdown["reasons"] = reasons
    numeric_total = sum(value for value in breakdown.values() if isinstance(value, (int, float)))
    return round(numeric_total, 2), breakdown, reference_seed
