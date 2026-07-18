"""垂类内容分类测试。

覆盖 app/analysis/niche_classifier.py：classify_niche
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.niche_classifier import classify_niche
from app.models import ProfileData


def _make_profile(
    *,
    biography: str | None = None,
    full_name: str | None = None,
    category_name: str | None = None,
    business_category_name: str | None = None,
    is_business: bool | None = False,
) -> ProfileData:
    return ProfileData(
        username="testuser",
        biography=biography,
        full_name=full_name,
        category_name=category_name,
        business_category_name=business_category_name,
        is_business=is_business,
        collected_at=datetime.now(UTC),
    )


# ---------- 单垂类测试 ----------


def test_perfume_niche_from_biography() -> None:
    """Biography 含 perfume → perfume 得分高。"""
    profile = _make_profile(
        biography="Amante del perfume y las fragancias artesanales",
        full_name="Perfume Lover",
    )
    result = classify_niche(profile)
    assert "perfume" in result.niche_scores
    assert result.niche_scores["perfume"] > 0
    assert any("perfume" in s for s in result.niche_signals)


def test_beauty_niche_from_biography() -> None:
    """Biography 含 beauty → beauty 得分高。"""
    profile = _make_profile(
        biography="Belleza y beauty blogger, cosmetic lover",
        full_name="Beauty Creator",
    )
    result = classify_niche(profile)
    assert result.niche_scores.get("beauty", 0) > 0


def test_skincare_niche_with_hashtag() -> None:
    """Biography 含 skincare + 来源 Hashtag #skincaremexico → skincare 得分更高。"""
    profile = _make_profile(biography="skincare routine, cuidado de la piel")
    result = classify_niche(profile, source_hashtags=["skincaremexico"])
    assert result.niche_scores.get("skincare", 0) >= 0.4
    # 多信号源应确认 primary_niche
    assert result.primary_niche == "skincare"


def test_makeup_niche_from_biography() -> None:
    """Biography 含 maquillaje → makeup 得分。"""
    profile = _make_profile(
        biography="Maquillaje profesional, makeup artist",
        full_name="Makeup Artist",
    )
    result = classify_niche(profile)
    assert result.niche_scores.get("makeup", 0) > 0


def test_fashion_niche_from_biography() -> None:
    """Biography 含 moda/fashion → fashion 得分。"""
    profile = _make_profile(
        biography="Moda y fashion, outfit diario",
        full_name="Fashion Blogger",
    )
    result = classify_niche(profile)
    assert result.niche_scores.get("fashion", 0) > 0


def test_lifestyle_niche_from_biography() -> None:
    """Biography 含 lifestyle → lifestyle 得分。"""
    profile = _make_profile(
        biography="Lifestyle blogger, estilo de vida, self care",
        full_name="Lifestyle Creator",
    )
    result = classify_niche(profile)
    assert result.niche_scores.get("lifestyle", 0) > 0


def test_ugc_niche_from_biography() -> None:
    """Biography 含 UGC → UGC 得分。"""
    profile = _make_profile(
        biography="UGC creator, creador de contenido",
        full_name="Content Creator",
    )
    result = classify_niche(profile)
    assert result.niche_scores.get("UGC", 0) > 0


# ---------- 多信号组合 ----------


def test_multi_signal_confirms_primary_niche() -> None:
    """多信号组合（Biography + Caption + Hashtag）→ primary_niche 确认。"""
    profile = _make_profile(
        biography="perfume lover y fragancias",
        full_name="Perfume Blogger",
    )
    result = classify_niche(
        profile,
        source_hashtags=["perfumemexico"],
        recent_captions=["Este perfume es increíble, nueva fragancia"],
        recent_media_hashtags=["perfumessolidos"],
    )
    assert result.primary_niche == "perfume"
    assert result.niche_scores["perfume"] >= 0.4


def test_single_signal_falls_back_to_general() -> None:
    """单一信号源 → primary_niche 为 general。"""
    # 仅 biography 含关键词，无其他信号
    profile = _make_profile(biography="perfume")
    result = classify_niche(profile)
    # 单信号得分 < 0.4 应回退 general
    assert result.primary_niche == "general"
    assert any("单一信号源" in r for r in result.classification_reasons)


# ---------- 品牌类目 ----------


def test_brand_category_classification() -> None:
    """品牌类目（is_business + business_category=Cosmetics）→ 可能 brand。"""
    profile = _make_profile(
        biography="",
        is_business=True,
        business_category_name="Cosmetics",
    )
    result = classify_niche(profile)
    # 商业账号 + 美妆类目应标记 brand
    assert "brand" in result.niche_scores
    assert result.niche_scores["brand"] > 0


def test_brand_category_perfume() -> None:
    """商业账号 + Perfume 类目 → brand。"""
    profile = _make_profile(
        biography="",
        is_business=True,
        business_category_name="Perfume Store",
    )
    result = classify_niche(profile)
    assert result.primary_niche == "brand"


# ---------- 无信号 ----------


def test_no_signals_returns_general() -> None:
    """无垂类信号命中 → general。"""
    profile = _make_profile(biography="Just a person living life")
    result = classify_niche(profile)
    assert result.primary_niche == "general"
    assert any("无垂类信号" in r for r in result.classification_reasons)


# ---------- 输出字段 ----------


def test_output_fields_present() -> None:
    """输出字段：primary_niche/niche_scores/niche_signals/classification_reasons。"""
    profile = _make_profile(biography="perfume lover")
    result = classify_niche(profile)
    assert hasattr(result, "primary_niche")
    assert hasattr(result, "niche_scores")
    assert hasattr(result, "niche_signals")
    assert hasattr(result, "classification_reasons")
    assert isinstance(result.niche_scores, dict)
    assert isinstance(result.niche_signals, list)
    assert isinstance(result.classification_reasons, list)


def test_caption_hashtag_signal() -> None:
    """近期 Caption 与 Hashtag 信号。"""
    profile = _make_profile(biography="")
    result = classify_niche(
        profile,
        recent_captions=["mi rutina de skincare diario"],
        recent_media_hashtags=["skincaremexico", "cuidadodelapielmx"],
    )
    assert result.niche_scores.get("skincare", 0) > 0


def test_category_signal() -> None:
    """Category 含关键词 → 信号。"""
    profile = _make_profile(
        biography="",
        category_name="Beauty Blogger",
    )
    result = classify_niche(profile)
    assert result.niche_scores.get("beauty", 0) > 0


def test_all_seven_target_niches_in_scores() -> None:
    """至少测试 perfume/beauty/skincare/makeup/fashion/lifestyle/UGC 七个垂类。"""
    # 一次性验证所有 7 个垂类都能被识别
    profile = _make_profile(
        biography="perfume beauty skincare makeup fashion lifestyle UGC",
        full_name="creator",
    )
    result = classify_niche(profile)
    for niche in ["perfume", "beauty", "skincare", "makeup", "fashion", "lifestyle", "UGC"]:
        assert niche in result.niche_scores
        assert result.niche_scores[niche] > 0
