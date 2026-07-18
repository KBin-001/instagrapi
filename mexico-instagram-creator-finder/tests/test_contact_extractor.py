"""公开联系方式提取测试。

覆盖 app/analysis/contact_extractor.py：extract_contacts
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.contact_extractor import extract_contacts
from app.models import ProfileData


def _make_profile(
    *,
    biography: str | None = None,
    external_url: str | None = None,
    public_email: str | None = None,
) -> ProfileData:
    return ProfileData(
        username="testuser",
        biography=biography,
        external_url=external_url,
        public_email=public_email,
        collected_at=datetime.now(UTC),
    )


# ---------- 邮箱提取 ----------


def test_email_from_biography() -> None:
    """Biography 含 contacto@brand.com → public_email。"""
    profile = _make_profile(biography="Para colaboraciones: contacto@brand.com")
    result = extract_contacts(profile)
    assert result.public_email == "contacto@brand.com"
    assert "biography_email" in result.contact_source
    assert result.has_public_contact is True


def test_mailto_link_from_biography() -> None:
    """Biography 含 mailto:hello@brand.com → public_email。"""
    profile = _make_profile(biography="Email: mailto:hello@brand.com")
    result = extract_contacts(profile)
    assert result.public_email == "hello@brand.com"
    assert "biography_mailto" in result.contact_source


def test_instagram_public_email_field() -> None:
    """Instagram public_email 字段 → public_email。"""
    profile = _make_profile(biography="", public_email="business@brand.com")
    result = extract_contacts(profile)
    assert result.public_email == "business@brand.com"
    assert "instagram_public_email" in result.contact_source


def test_instagram_public_email_priority() -> None:
    """Instagram public_email 字段优先于 biography。"""
    profile = _make_profile(
        biography="contact: bio@brand.com",
        public_email="ig@brand.com",
    )
    result = extract_contacts(profile)
    assert result.public_email == "ig@brand.com"


# ---------- WhatsApp 提取 ----------


def test_whatsapp_wa_me_link() -> None:
    """Biography 含 https://wa.me/521234567890 → public_whatsapp_url。"""
    profile = _make_profile(biography="WhatsApp: https://wa.me/521234567890")
    result = extract_contacts(profile)
    assert result.public_whatsapp_url == "https://wa.me/521234567890"
    assert "biography_wa_me" in result.contact_source


def test_whatsapp_api_link() -> None:
    """Biography 含 https://api.whatsapp.com/send?phone=521234567890 → public_whatsapp_url。"""
    profile = _make_profile(biography="Contacto: https://api.whatsapp.com/send?phone=521234567890")
    result = extract_contacts(profile)
    assert result.public_whatsapp_url == "https://wa.me/521234567890"
    assert "biography_whatsapp_business" in result.contact_source


def test_whatsapp_link_in_external_url() -> None:
    """external_url 含 wa.me 链接。"""
    profile = _make_profile(
        biography="",
        external_url="https://wa.me/521234567890",
    )
    result = extract_contacts(profile)
    assert result.public_whatsapp_url == "https://wa.me/521234567890"


# ---------- Linktree / Beacons ----------


def test_linktree_link() -> None:
    """Biography 含 https://linktr.ee/mylink → linktree_url。"""
    profile = _make_profile(biography="Más enlaces: https://linktr.ee/mylink")
    result = extract_contacts(profile)
    assert result.linktree_url == "https://linktr.ee/mylink"
    assert "biography_linktree" in result.contact_source


def test_beacons_link() -> None:
    """Biography 含 https://beacons.ai/mylink → beacons_url。"""
    profile = _make_profile(biography="https://beacons.ai/mylink")
    result = extract_contacts(profile)
    assert result.beacons_url == "https://beacons.ai/mylink"
    assert "biography_beacons" in result.contact_source


# ---------- external_url ----------


def test_external_url_field() -> None:
    """external_url 字段 → external_url。"""
    profile = _make_profile(external_url="https://mitienda.com")
    result = extract_contacts(profile)
    assert result.external_url == "https://mitienda.com"
    assert "external_url" in result.contact_source
    assert result.has_public_contact is True


# ---------- 负面场景 ----------


def test_plain_number_not_recognized_as_whatsapp() -> None:
    """不识别普通数字为 WhatsApp。"""
    profile = _make_profile(biography="Mi número es 5551234567")
    result = extract_contacts(profile)
    assert result.public_whatsapp_url is None


def test_no_email_guessing() -> None:
    """不推测邮箱（不拼接域名）。"""
    # 仅含用户名和域名，但无 @ 不应识别为邮箱
    profile = _make_profile(biography="contacto en brand.com")
    result = extract_contacts(profile)
    assert result.public_email is None


def test_no_contact_returns_empty() -> None:
    """无任何联系方式。"""
    profile = _make_profile(biography="Solo un creador de contenido")
    result = extract_contacts(profile)
    assert result.public_email is None
    assert result.public_whatsapp_url is None
    assert result.linktree_url is None
    assert result.beacons_url is None
    assert result.external_url is None
    assert result.has_public_contact is False
    assert result.contact_source == "none"


# ---------- 多联系方式 ----------


def test_multiple_contacts() -> None:
    """同时提取多种联系方式。"""
    profile = _make_profile(
        biography="Email: hola@brand.com | WhatsApp: https://wa.me/521234567890 | https://linktr.ee/brand",
        external_url="https://mitienda.mx",
    )
    result = extract_contacts(profile)
    assert result.public_email == "hola@brand.com"
    assert result.public_whatsapp_url == "https://wa.me/521234567890"
    assert result.linktree_url == "https://linktr.ee/brand"
    assert result.external_url == "https://mitienda.mx"
    assert result.has_public_contact is True
    # contact_source 应含多个来源
    assert "," in result.contact_source


# ---------- 输出字段 ----------


def test_output_fields_present() -> None:
    """输出字段：public_email/public_whatsapp_url/external_url/contact_source/has_public_contact。"""
    profile = _make_profile(biography="test@brand.com")
    result = extract_contacts(profile)
    assert hasattr(result, "public_email")
    assert hasattr(result, "public_whatsapp_url")
    assert hasattr(result, "external_url")
    assert hasattr(result, "linktree_url")
    assert hasattr(result, "beacons_url")
    assert hasattr(result, "contact_source")
    assert hasattr(result, "has_public_contact")


def test_contact_source_recorded() -> None:
    """每个联系方式记录来源。"""
    profile = _make_profile(biography="mailto:hello@brand.com")
    result = extract_contacts(profile)
    assert result.contact_source != "none"
    assert "biography_mailto" in result.contact_source
