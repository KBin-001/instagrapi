"""账号类型识别测试。

覆盖 app/analysis/account_classifier.py：classify_account_type
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.account_classifier import classify_account_type
from app.models import ProfileData


def _make_profile(
    *,
    username: str = "testuser",
    biography: str | None = None,
    full_name: str | None = None,
    category_name: str | None = None,
    business_category_name: str | None = None,
    is_business: bool | None = False,
) -> ProfileData:
    return ProfileData(
        username=username,
        biography=biography,
        full_name=full_name,
        category_name=category_name,
        business_category_name=business_category_name,
        is_business=is_business,
        collected_at=datetime.now(UTC),
    )


# ---------- 品牌判定 ----------


def test_brand_business_with_oficial() -> None:
    """is_business=true + username 含 oficial → brand。"""
    profile = _make_profile(
        username="brandoficial",
        biography="marca oficial",
        is_business=True,
    )
    result = classify_account_type(profile)
    assert result.account_type == "brand"
    assert result.account_type_confidence >= 0.8


def test_brand_business_with_shop_in_bio() -> None:
    """is_business=true + biography 含 shop → brand（或 shop）。"""
    profile = _make_profile(
        username="tiendabeauty",
        biography="compra en nuestra shop",
        is_business=True,
    )
    result = classify_account_type(profile)
    # shop_terms 命中 + is_business 应识别为 brand 或 shop
    assert result.account_type in ("brand", "shop")
    assert result.account_type_confidence > 0


def test_business_without_brand_terms_still_brand() -> None:
    """is_business=true 但无品牌词 → 仍为 brand（confidence 0.6）。"""
    profile = _make_profile(
        username="somebiz",
        biography="negocio",
        is_business=True,
    )
    result = classify_account_type(profile)
    assert result.account_type == "brand"
    assert result.account_type_confidence == 0.6


# ---------- 媒体/新闻判定 ----------


def test_media_news_with_noticias() -> None:
    """biography 含 noticias → media/news。"""
    profile = _make_profile(
        username="medio",
        biography="últimas noticias del mundo",
    )
    result = classify_account_type(profile)
    assert result.account_type in ("media", "news")
    assert result.account_type_confidence > 0


def test_media_news_with_news_keyword() -> None:
    """biography 含 news → media/news。"""
    profile = _make_profile(
        username="press",
        biography="daily news update",
    )
    result = classify_account_type(profile)
    assert result.account_type in ("media", "news")


# ---------- 经纪公司/营销机构 ----------


def test_agency_with_management() -> None:
    """biography 含 management → agency。"""
    profile = _make_profile(
        username="talentmgmt",
        biography="talent management agency",
    )
    result = classify_account_type(profile)
    assert result.account_type == "agency"
    assert result.account_type_confidence > 0


def test_marketing_agency() -> None:
    """biography 含 agency 但无 management → marketing。"""
    profile = _make_profile(
        username="marketingpro",
        biography="agencia de marketing digital",
    )
    result = classify_account_type(profile)
    assert result.account_type in ("agency", "marketing")


# ---------- UGC 创作者 ----------


def test_ugc_creator() -> None:
    """biography 含 ugc → ugc_creator。"""
    profile = _make_profile(
        username="ugccreator",
        biography="UGC creator, content creator",
    )
    result = classify_account_type(profile)
    assert result.account_type == "ugc_creator"


def test_ugc_creator_from_full_name() -> None:
    """full_name 含 UGC → ugc_creator。"""
    profile = _make_profile(
        username="creator",
        biography="",
        full_name="UGC Content Creator",
    )
    result = classify_account_type(profile)
    assert result.account_type == "ugc_creator"


# ---------- 粉丝搬运 ----------


def test_fan_reposter() -> None:
    """biography 含 fanpage → fan_reposter。"""
    profile = _make_profile(
        username="fanpage01",
        biography="fanpage dedicada a mi ídolo",
    )
    result = classify_account_type(profile)
    assert result.account_type == "fan_reposter"


# ---------- 主题聚合 ----------


def test_topic_aggregator() -> None:
    """biography 含 aggregator/daily → topic_aggregator。"""
    profile = _make_profile(
        username="dailyperfume",
        biography="curated daily perfume hub",
    )
    result = classify_account_type(profile)
    assert result.account_type == "topic_aggregator"


# ---------- 默认个人创作者 ----------


def test_default_personal_creator() -> None:
    """默认 → personal_creator。"""
    profile = _make_profile(
        username="alice",
        biography="amante del perfume",
    )
    result = classify_account_type(profile)
    assert result.account_type == "personal_creator"
    assert result.account_type_confidence > 0


# ---------- 输出字段 ----------


def test_output_fields_present() -> None:
    """输出字段：account_type/account_type_confidence/account_type_reasons。"""
    profile = _make_profile(biography="creator")
    result = classify_account_type(profile)
    assert hasattr(result, "account_type")
    assert hasattr(result, "account_type_confidence")
    assert hasattr(result, "account_type_reasons")
    assert isinstance(result.account_type, str)
    assert isinstance(result.account_type_confidence, float)
    assert isinstance(result.account_type_reasons, list)
    assert len(result.account_type_reasons) > 0


def test_reasons_explain_classification() -> None:
    """分类原因可解释。"""
    profile = _make_profile(
        username="brandoficial",
        biography="marca",
        is_business=True,
    )
    result = classify_account_type(profile)
    # brand 类型应有原因说明
    assert any("oficial" in r.lower() or "brand" in r.lower() or "商业" in r for r in result.account_type_reasons)


def test_source_hashtags_param_accepted() -> None:
    """source_hashtags 参数被接受（即使不影响判定）。"""
    profile = _make_profile(biography="creator")
    result = classify_account_type(profile, source_hashtags=["perfume"])
    assert result.account_type == "personal_creator"
