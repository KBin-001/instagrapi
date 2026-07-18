"""公开联系方式提取。

允许：公开邮箱、mailto:、wa.me、WhatsApp Business、Linktree、Beacons、公开网站、Instagram public_email。
禁止：推测邮箱、拼接域名邮箱、将普通数字识别为 WhatsApp、访问登录后才能看到的联系方式。
"""

from __future__ import annotations

import re
from typing import Any

from app.logging_config import get_logger
from app.models import ContactInfo, ProfileData

logger = get_logger("analysis.contact_extractor")

# 邮箱正则（保守）
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# wa.me 链接
_WA_ME_PATTERN = re.compile(r"https?://wa\.me/(\d{6,15})", re.IGNORECASE)

# WhatsApp Business 链接（api.whatsapp.com）
_WHATSAPP_BUSINESS_PATTERN = re.compile(
    r"https?://(?:api\.whatsapp\.com/send\?phone=|wa\.me/)(\d{6,15})",
    re.IGNORECASE,
)

# mailto:
_MAILTO_PATTERN = re.compile(r"mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", re.IGNORECASE)

# Linktree
_LINKTREE_PATTERN = re.compile(r"https?://linktr\.ee/([A-Za-z0-9_\-]+)", re.IGNORECASE)

# Beacons
_BEACONS_PATTERN = re.compile(r"https?://beacons\.ai/([A-Za-z0-9_\-]+)", re.IGNORECASE)


def _safe_lower(value: Any) -> str:
    if value is None:
        return ""
    return str(value).lower()


def extract_contacts(profile: ProfileData) -> ContactInfo:
    """
    提取公开联系方式。

    不推测邮箱、不拼接域名、不识别普通数字为 WhatsApp。
    每个联系方式记录来源。
    """
    bio = profile.biography or ""
    external_url = profile.external_url or ""
    public_email_from_ig = profile.public_email or None

    public_email: str | None = None
    public_whatsapp_url: str | None = None
    linktree_url: str | None = None
    beacons_url: str | None = None
    contact_source: str = "none"
    sources: list[str] = []

    # 1. Instagram 公开 public_email（最高优先级）
    if public_email_from_ig and _EMAIL_PATTERN.fullmatch(public_email_from_ig):
        public_email = public_email_from_ig
        sources.append("instagram_public_email")

    # 2. Biography 中的 mailto:
    mailto_match = _MAILTO_PATTERN.search(bio)
    if mailto_match and not public_email:
        public_email = mailto_match.group(1)
        sources.append("biography_mailto")

    # 3. Biography 中的邮箱（保守正则，避免误识别）
    if not public_email:
        email_match = _EMAIL_PATTERN.search(bio)
        if email_match:
            candidate = email_match.group(0)
            # 排除明显不是邮箱的（如 example@test）
            if "." in candidate.split("@")[-1]:
                public_email = candidate
                sources.append("biography_email")

    # 4. WhatsApp wa.me 链接
    wa_match = _WA_ME_PATTERN.search(bio) or _WA_ME_PATTERN.search(external_url)
    if wa_match:
        phone = wa_match.group(1)
        public_whatsapp_url = f"https://wa.me/{phone}"
        sources.append("biography_wa_me")

    # 5. WhatsApp Business 链接
    wb_match = _WHATSAPP_BUSINESS_PATTERN.search(bio) or _WHATSAPP_BUSINESS_PATTERN.search(external_url)
    if wb_match and not public_whatsapp_url:
        phone = wb_match.group(1)
        public_whatsapp_url = f"https://wa.me/{phone}"
        sources.append("biography_whatsapp_business")

    # 6. Linktree
    linktree_match = _LINKTREE_PATTERN.search(bio) or _LINKTREE_PATTERN.search(external_url)
    if linktree_match:
        linktree_url = f"https://linktr.ee/{linktree_match.group(1)}"
        sources.append("biography_linktree")

    # 7. Beacons
    beacons_match = _BEACONS_PATTERN.search(bio) or _BEACONS_PATTERN.search(external_url)
    if beacons_match:
        beacons_url = f"https://beacons.ai/{beacons_match.group(1)}"
        sources.append("biography_beacons")

    # 8. external_url 作为公开网站
    final_external_url = external_url or None
    if final_external_url:
        sources.append("external_url")

    if sources:
        contact_source = ",".join(sources)

    has_public_contact = bool(public_email or public_whatsapp_url or linktree_url or beacons_url or final_external_url)

    return ContactInfo(
        public_email=public_email,
        public_whatsapp_url=public_whatsapp_url,
        external_url=final_external_url,
        linktree_url=linktree_url,
        beacons_url=beacons_url,
        contact_source=contact_source,
        has_public_contact=has_public_contact,
    )
