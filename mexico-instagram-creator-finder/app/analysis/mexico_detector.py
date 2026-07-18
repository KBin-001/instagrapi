"""墨西哥地区信号识别。

综合多个公开信号，不得仅凭 mx/西语/国旗表情/单 Hashtag 判定。
"""

from __future__ import annotations

import re
from typing import Any

from app.config import load_mexico_locations
from app.logging_config import get_logger
from app.models import MexicoSignal, ProfileData

logger = get_logger("analysis.mexico_detector")

# 墨西哥国旗表情
_MEXICO_FLAG_EMOJI = "🇲🇽"


def _to_lower_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).lower()


def detect_mexico_signal(
    profile: ProfileData,
    source_hashtags: list[str] | None = None,
    recent_captions: list[str] | None = None,
    location_text: str | None = None,
    config_dir: Any = None,
) -> MexicoSignal:
    """
    多信号识别墨西哥地区可信度。

    信号：
    - Biography 中的国家名称（Mexico/México/MX）
    - Biography 中的州/城市名（来自 config/mexico_locations.yaml）
    - 公开 business address
    - 来源 Hashtag 含 mexican/mexico/cdmx/guadalajara/monterrey 等
    - 近期 Caption 含墨西哥地名
    - 公开地点标签
    - .mx 网站
    - 用户公开展示的 +52 电话国家代码（仅辅助）

    不得仅凭 mx 两字母、西班牙语、墨西哥国旗表情、单个 Hashtag 直接判定。
    """
    locations_data = load_mexico_locations(config_dir)
    states = locations_data.get("states", [])
    country_aliases = [s.lower() for s in locations_data.get("country_aliases", [])] + ["mexico", "méxico"]
    mexican_hashtags = set(h.lower() for h in locations_data.get("mexican_hashtags", []))

    # "mx" 作为短国家代码易误判（如 "I love mx"），单独不构成强信号
    strong_country_aliases = [a for a in country_aliases if a and a != "mx"]
    weak_country_aliases = {"mx"} if "mx" in country_aliases else set()

    bio = _to_lower_str(profile.biography)
    full_name = _to_lower_str(profile.full_name)
    external_url = _to_lower_str(profile.external_url)
    category = _to_lower_str(profile.category_name)
    business_category = _to_lower_str(profile.business_category_name)

    signals: list[str] = []
    weak_signals: list[str] = []
    detected_country: str | None = None
    detected_state: str | None = None
    detected_city: str | None = None

    # 信号 1：Biography 含国家名（"mx" 作为弱信号单独处理）
    for alias in strong_country_aliases:
        if alias and alias in bio:
            signals.append(f"biography 含国家名 '{alias}'")
            detected_country = "Mexico"
            break
    # 弱信号：仅 "mx" 字母
    for alias in weak_country_aliases:
        if alias and re.search(rf"\b{re.escape(alias)}\b", bio):
            weak_signals.append(f"biography 含国家代码 '{alias}'（弱信号）")

    # 信号 2：Biography/外部链接含州或城市名
    text_pool = f"{bio} {full_name} {category} {business_category}"
    for state_entry in states:
        state_name = state_entry.get("name", "")
        state_aliases = [a.lower() for a in state_entry.get("aliases", [])] + [state_name.lower()]
        cities = [c.lower() for c in state_entry.get("cities", [])]

        for alias in state_aliases:
            if not alias:
                continue
            # 短别名（≤3 字符）要求单词边界匹配，避免 "only" 中的 "nl" 误判
            if len(alias) <= 3:
                if re.search(rf"\b{re.escape(alias)}\b", text_pool):
                    signals.append(f"文本含州名 '{state_name}' (alias: {alias})")
                    detected_state = state_name
                    detected_country = "Mexico"
                    break
            elif alias in text_pool:
                signals.append(f"文本含州名 '{state_name}' (alias: {alias})")
                detected_state = state_name
                detected_country = "Mexico"
                break

        for city in cities:
            if city and city in text_pool:
                signals.append(f"文本含城市 '{city}' (州: {state_name})")
                detected_city = city
                detected_country = "Mexico"
                break

    # 信号 3：来源 Hashtag 含墨西哥标识（需要至少 2 个独立墨西哥 Hashtag）
    if source_hashtags:
        ht_lower = [h.lower().lstrip("#") for h in source_hashtags]
        matched_mx_ht = [h for h in ht_lower if h in mexican_hashtags or "mexico" in h or "mexican" in h]
        if len(matched_mx_ht) >= 2:
            signals.append(f"来源 Hashtag 含 {len(matched_mx_ht)} 个墨西哥标识: {matched_mx_ht[:3]}")
            if detected_country is None:
                detected_country = "Mexico"

    # 信号 4：近期 Caption 含墨西哥地名
    if recent_captions:
        captions_text = " ".join(recent_captions).lower()
        for state_entry in states:
            state_name = state_entry.get("name", "")
            cities = [c.lower() for c in state_entry.get("cities", [])]
            for city in cities:
                if city and city in captions_text:
                    signals.append(f"近期 Caption 含城市 '{city}'")
                    detected_city = city
                    detected_country = "Mexico"
                    break

    # 信号 5：公开地点标签
    if location_text:
        loc_lower = location_text.lower()
        for state_entry in states:
            state_name = state_entry.get("name", "")
            state_aliases = [a.lower() for a in state_entry.get("aliases", [])] + [state_name.lower()]
            for alias in state_aliases:
                if not alias:
                    continue
                # 短别名同样要求单词边界
                if len(alias) <= 3:
                    if re.search(rf"\b{re.escape(alias)}\b", loc_lower):
                        signals.append(f"公开地点含州名 '{state_name}'")
                        detected_state = state_name
                        detected_country = "Mexico"
                        break
                elif alias in loc_lower:
                    signals.append(f"公开地点含州名 '{state_name}'")
                    detected_state = state_name
                    detected_country = "Mexico"
                    break

    # 信号 6：.mx 网站
    if external_url:
        if ".mx" in external_url or "://*.mx" in external_url or re.search(r"\.mx(?:/|$|\?)", external_url):
            signals.append(f"外部网站含 .mx 域名: {external_url}")
            if detected_country is None:
                detected_country = "Mexico"

    # 信号 7：+52 电话国家代码（仅辅助，单独不足以判定）
    phone_pattern = re.compile(r"\+52\d{6,}")
    if phone_pattern.search(bio) or phone_pattern.search(_to_lower_str(profile.public_email)):
        weak_signals.append("biography 含 +52 墨西哥电话国家代码（辅助信号）")
        # 不单独将 detected_country 设为 Mexico

    # 弱信号：墨西哥国旗表情（单独不判定）
    if _MEXICO_FLAG_EMOJI in (profile.biography or "") or _MEXICO_FLAG_EMOJI in (profile.full_name or ""):
        weak_signals.append("biography 含墨西哥国旗表情（弱信号）")

    # 计算置信度：strong_signals 为已收集的强信号；weak_signals 为辅助/弱信号
    strong_signals = list(signals)

    # 弱信号单独不足以判定
    if not strong_signals:
        if detected_country is None:
            return MexicoSignal(
                mexico_confidence_score=0.0,
                mexico_signals=weak_signals,
                detected_country=None,
                detected_state=None,
                detected_city=None,
            )

    # 置信度计算
    score = min(1.0, 0.3 * len(strong_signals) + 0.1 * len(weak_signals))
    if len(strong_signals) == 0:
        score = 0.0
    elif len(strong_signals) == 1:
        score = min(score, 0.5)

    all_signals = strong_signals + weak_signals
    return MexicoSignal(
        mexico_confidence_score=round(score, 2),
        mexico_signals=all_signals,
        detected_country=detected_country,
        detected_state=detected_state,
        detected_city=detected_city,
    )
