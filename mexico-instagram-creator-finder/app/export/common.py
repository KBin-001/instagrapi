"""导出公共工具：排序、字段映射。

仅处理公开数据；不导出密码、Cookie 或 Session。
"""

from __future__ import annotations

import json
from typing import Any

from app.models import CreatorRecord

# 导出字段顺序（统一用于 CSV / XLSX；JSON 同样按此顺序输出 key）
EXPORT_FIELDS: list[str] = [
    "username",
    "full_name",
    "profile_url",
    "follower_count",
    "following_count",
    "media_count",
    "is_private",
    "is_verified",
    "is_business",
    "category_name",
    "business_category_name",
    "biography",
    "external_url",
    "profile_pic_url",
    "public_email",
    "public_whatsapp_url",
    "linktree_url",
    "beacons_url",
    "has_public_contact",
    "contact_source",
    "detected_country",
    "detected_state",
    "detected_city",
    "mexico_confidence_score",
    "mexico_signals",
    "primary_niche",
    "niche_scores",
    "account_type",
    "account_type_confidence",
    "recent_media_checked",
    "recent_reels_checked",
    "last_post_date",
    "days_since_last_post",
    "average_likes",
    "median_likes",
    "average_comments",
    "median_comments",
    "average_visible_reel_views",
    "median_visible_reel_views",
    "maximum_visible_reel_views",
    "posting_frequency",
    "reels_view_data_available",
    "total_score",
    "score_breakdown",
    "recommendation_level",
    "recommendation_reasons",
    "source_hashtags",
]


def sort_records(records: list[CreatorRecord]) -> list[CreatorRecord]:
    """
    默认排序：total_score 降序 → median_visible_reel_views 降序 → followers 降序。

    缺失字段按 0 处理，确保排序稳定不抛错。
    """

    def sort_key(r: CreatorRecord) -> tuple:
        score = r.score.total_score if r.score else 0.0
        median_views = (
            r.metrics.median_visible_reel_views
            if r.metrics and r.metrics.median_visible_reel_views is not None
            else 0.0
        )
        followers = r.profile.follower_count or 0
        return (-score, -median_views, -followers)

    return sorted(records, key=sort_key)


def record_to_dict(record: CreatorRecord) -> dict[str, Any]:
    """将 CreatorRecord 转为扁平字典（用于 JSON 导出）。"""
    p = record.profile
    m = record.metrics
    c = record.contact
    n = record.niche
    mx = record.mexico
    a = record.account_type
    s = record.score

    return {
        "username": record.username,
        "full_name": p.full_name,
        "profile_url": p.profile_url,
        "follower_count": p.follower_count,
        "following_count": p.following_count,
        "media_count": p.media_count,
        "is_private": p.is_private,
        "is_verified": p.is_verified,
        "is_business": p.is_business,
        "category_name": p.category_name,
        "business_category_name": p.business_category_name,
        "biography": p.biography,
        "external_url": p.external_url,
        "profile_pic_url": p.profile_pic_url,
        "public_email": c.public_email if c else (p.public_email or None),
        "public_whatsapp_url": c.public_whatsapp_url if c else None,
        "linktree_url": c.linktree_url if c else None,
        "beacons_url": c.beacons_url if c else None,
        "has_public_contact": c.has_public_contact if c else False,
        "contact_source": c.contact_source if c else "none",
        "detected_country": mx.detected_country if mx else None,
        "detected_state": mx.detected_state if mx else None,
        "detected_city": mx.detected_city if mx else None,
        "mexico_confidence_score": mx.mexico_confidence_score if mx else 0.0,
        "mexico_signals": mx.mexico_signals if mx else [],
        "primary_niche": n.primary_niche if n else "general",
        "niche_scores": n.niche_scores if n else {},
        "account_type": a.account_type if a else "personal_creator",
        "account_type_confidence": a.account_type_confidence if a else 0.0,
        "recent_media_checked": m.recent_media_checked if m else 0,
        "recent_reels_checked": m.recent_reels_checked if m else 0,
        "last_post_date": m.last_post_date.isoformat() if m and m.last_post_date else None,
        "days_since_last_post": m.days_since_last_post if m else None,
        "average_likes": m.average_likes if m else None,
        "median_likes": m.median_likes if m else None,
        "average_comments": m.average_comments if m else None,
        "median_comments": m.median_comments if m else None,
        "average_visible_reel_views": m.average_visible_reel_views if m else None,
        "median_visible_reel_views": m.median_visible_reel_views if m else None,
        "maximum_visible_reel_views": m.maximum_visible_reel_views if m else None,
        "posting_frequency": m.posting_frequency if m else None,
        "reels_view_data_available": m.reels_view_data_available if m else "no_reels",
        "total_score": s.total_score if s else 0.0,
        "score_breakdown": s.score_breakdown if s else {},
        "recommendation_level": s.recommendation_level if s else "D",
        "recommendation_reasons": s.recommendation_reasons if s else [],
        # CreatorRecord 不直接保存 source_hashtags（来自 CandidateAccount），
        # 此处保留字段位以兼容导出列。
        "source_hashtags": [],
    }


def records_to_dicts(records: list[CreatorRecord]) -> list[dict[str, Any]]:
    """批量转 dict（JSON 导出用）。"""
    return [record_to_dict(r) for r in records]


def _to_str(value: Any) -> str:
    """将复杂类型转为字符串（CSV/XLSX 用）。"""
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def record_to_row(record: CreatorRecord) -> dict[str, str]:
    """将 CreatorRecord 转为字符串行（CSV/XLSX 用）。"""
    d = record_to_dict(record)
    return {k: _to_str(v) for k, v in d.items()}


def records_to_rows(records: list[CreatorRecord]) -> tuple[list[dict[str, str]], list[str]]:
    """
    批量转为字符串行，返回 (rows, fieldnames)。
    fieldnames 为 EXPORT_FIELDS 列表。
    """
    rows = [record_to_row(r) for r in records]
    return rows, EXPORT_FIELDS
