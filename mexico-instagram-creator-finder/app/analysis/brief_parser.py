"""将自然语言达人 Brief 转换为本地、可解释的规则。"""

from __future__ import annotations

import re

from app.models import SearchIntent

_NICHE_TERMS = {
    "perfume": ("香水", "香氛", "固体香水", "perfume", "fragancia", "perfumería"),
    "beauty": ("美妆", "beauty", "belleza"),
    "skincare": ("护肤", "skincare", "cuidado de la piel"),
    "makeup": ("彩妆", "化妆", "makeup", "maquillaje"),
    "fashion": ("穿搭", "时尚", "fashion", "moda", "outfit"),
    "lifestyle": ("生活方式", "生活", "lifestyle", "estilo de vida"),
    "UGC": ("ugc", "内容创作者", "creador de contenido"),
}


def _number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _scaled_number(raw: str, suffix: str | None) -> int:
    value = _number(raw)
    scale = {"k": 1_000, "m": 1_000_000, "万": 10_000}.get((suffix or "").lower(), 1)
    return int(value * scale)


def parse_search_brief(brief: str) -> SearchIntent:
    """解析中文、西班牙语和英文中的常见筛选意图。"""
    text = brief.strip()
    lowered = text.lower()
    niches = [name for name, terms in _NICHE_TERMS.items() if any(term.lower() in lowered for term in terms)]
    regions = ["mexico"] if any(t in lowered for t in ("墨西哥", "méxico", "mexico", "mexicana", "mexicano")) else []

    min_followers = max_followers = None
    range_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(k|m|万)?\s*(?:[-—~到至]|a)\s*(\d+(?:[.,]\d+)?)\s*(k|m|万)?",
        lowered,
    )
    if range_match:
        min_followers = _scaled_number(range_match.group(1), range_match.group(2))
        max_followers = _scaled_number(range_match.group(3), range_match.group(4))
    else:
        min_match = re.search(
            r"(?:粉丝(?:数(?:量)?)?.{0,6}?(?:大于|超过|不少于|至少)|(?:more than|at least|más de).{0,6}?)"
            r"(\d+(?:[.,]\d+)?)\s*(k|m|万)?",
            lowered,
        )
        max_match = re.search(
            r"(?:粉丝(?:数(?:量)?)?.{0,6}?(?:小于|少于|不超过|最多)|(?:less than|at most|menos de).{0,6}?)"
            r"(\d+(?:[.,]\d+)?)\s*(k|m|万)?",
            lowered,
        )
        if min_match:
            min_followers = _scaled_number(min_match.group(1), min_match.group(2))
        if max_match:
            max_followers = _scaled_number(max_match.group(1), max_match.group(2))

    view_match = re.search(r"(?:播放|views?|vistas?).{0,8}?(\d+(?:[.,]\d+)?)\s*(k|m|万)?", lowered)
    days_match = re.search(r"(?:最近|近|within|últimos?)\s*(\d+)\s*(?:天|days?|días?)", lowered)
    require_contact = any(t in lowered for t in ("联系方式", "联系邮箱", "公开邮箱", "contact", "correo", "email"))
    public_only = not any(t in lowered for t in ("允许私密", "private allowed", "privada permitida"))

    account_types: list[str] = []
    if any(t in lowered for t in ("个人博主", "个人创作者", "personal creator", "creador personal")):
        account_types.append("personal_creator")
    if "ugc" in lowered:
        account_types.append("ugc_creator")

    consumed = {term.lower() for terms in _NICHE_TERMS.values() for term in terms if term.lower() in lowered}
    consumed.update({"墨西哥", "méxico", "mexico", "联系方式", "公开邮箱", "contact", "email"})
    latin_words = re.findall(r"[a-záéíóúñ]{3,}", lowered)
    known_chinese = [
        term
        for term in ("开箱", "测评", "推荐", "好物", "礼物", "日常", "固体香水", "香氛")
        if term in lowered and term not in consumed
    ]
    stop_words = {"寻找", "最近", "粉丝", "创作者", "个人创作者", "博主", "活跃", "需要"}
    keywords = sorted({word for word in [*latin_words, *known_chinese] if word not in consumed | stop_words})[:30]

    return SearchIntent(
        raw_brief=text,
        target_niches=niches,
        target_regions=regions,
        target_account_types=account_types,
        content_keywords=keywords,
        min_followers=min_followers,
        max_followers=max_followers,
        maximum_days_since_last_post=int(days_match.group(1)) if days_match else None,
        minimum_median_reel_views=(_scaled_number(view_match.group(1), view_match.group(2)) if view_match else None),
        require_public_account=public_only,
        require_mexico_signal=bool(regions),
        require_public_contact=require_contact,
    )
