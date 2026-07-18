"""墨西哥地区信号识别测试。

覆盖 app/analysis/mexico_detector.py：detect_mexico_signal
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.mexico_detector import detect_mexico_signal
from app.models import ProfileData


def _make_profile(
    *,
    biography: str | None = None,
    full_name: str | None = None,
    external_url: str | None = None,
    category_name: str | None = None,
    business_category_name: str | None = None,
    public_email: str | None = None,
) -> ProfileData:
    return ProfileData(
        username="testuser",
        biography=biography,
        full_name=full_name,
        external_url=external_url,
        category_name=category_name,
        business_category_name=business_category_name,
        public_email=public_email,
        collected_at=datetime.now(UTC),
    )


# ---------- 单信号场景 ----------


def test_bio_contains_mexico_keyword() -> None:
    """Biography 含 Mexico → confidence > 0。"""
    profile = _make_profile(biography="Vivo en Mexico, amante del perfume")
    result = detect_mexico_signal(profile)
    assert result.mexico_confidence_score > 0
    assert result.detected_country == "Mexico"
    assert any("国家名" in s for s in result.mexico_signals)


def test_bio_contains_mexico_with_accent() -> None:
    """Biography 含 México（带重音）→ confidence > 0。"""
    profile = _make_profile(biography="Orgullosamente México 🇲🇽")
    result = detect_mexico_signal(profile)
    assert result.mexico_confidence_score > 0
    assert result.detected_country == "Mexico"


def test_bio_contains_cdmx_detects_state() -> None:
    """Biography 含 CDMX → 检测州为 Ciudad de México。"""
    profile = _make_profile(biography="Viviendo en CDMX")
    result = detect_mexico_signal(profile)
    assert result.detected_state == "Ciudad de México"
    assert result.detected_country == "Mexico"
    assert result.mexico_confidence_score > 0


def test_bio_contains_guadalajara_detects_city() -> None:
    """Biography 含 Guadalajara → 检测城市。"""
    profile = _make_profile(biography="Desde Guadalajara")
    result = detect_mexico_signal(profile)
    assert result.detected_city == "guadalajara"
    assert result.detected_country == "Mexico"


def test_bio_contains_monterrey() -> None:
    """Biography 含 Monterrey → 检测城市。"""
    profile = _make_profile(biography="Monterrey, NL")
    result = detect_mexico_signal(profile)
    assert result.detected_country == "Mexico"
    assert result.mexico_confidence_score > 0


def test_dot_mx_website_increases_confidence() -> None:
    """.mx 网站 → confidence 增加。"""
    profile_no_mx = _make_profile(biography="creator")
    profile_with_mx = _make_profile(biography="creator", external_url="https://mi-tienda.mx")
    result_no = detect_mexico_signal(profile_no_mx)
    result_mx = detect_mexico_signal(profile_with_mx)
    assert result_mx.mexico_confidence_score >= result_no.mexico_confidence_score
    assert any(".mx" in s for s in result_mx.mexico_signals)


# ---------- 弱信号不应判定为墨西哥 ----------


def test_only_mx_letters_not_enough() -> None:
    """仅 'mx' 两字母不应判定为墨西哥。"""
    profile = _make_profile(biography="I love mx so much")
    result = detect_mexico_signal(profile)
    # 单个 mx 字母不应触发强信号
    assert result.mexico_confidence_score == 0.0
    assert result.detected_country is None


def test_only_flag_emoji_not_enough() -> None:
    """仅墨西哥国旗表情不应判定为墨西哥（confidence 为 0）。"""
    profile = _make_profile(biography="🇲🇽 only emoji")
    result = detect_mexico_signal(profile)
    assert result.mexico_confidence_score == 0.0
    assert result.detected_country is None


def test_only_spanish_not_enough() -> None:
    """仅西班牙语不应判定为墨西哥。"""
    profile = _make_profile(biography="Hola, me gusta el perfume y la moda")
    result = detect_mexico_signal(profile)
    assert result.mexico_confidence_score == 0.0
    assert result.detected_country is None


def test_single_mexican_hashtag_not_enough() -> None:
    """单个墨西哥 Hashtag 不应单独判定（按实现至少 2 个）。"""
    profile = _make_profile(biography="creator")
    result = detect_mexico_signal(profile, source_hashtags=["mexico"])
    # 单个 hashtag 不足以触发强信号
    assert result.mexico_confidence_score == 0.0


# ---------- 多信号场景 ----------


def test_two_mexican_hashtags_increases_confidence() -> None:
    """2 个以上墨西哥标识 Hashtag → confidence 增加。"""
    profile = _make_profile(biography="creator")
    result = detect_mexico_signal(
        profile,
        source_hashtags=["mexico", "cdmx"],
    )
    assert result.mexico_confidence_score > 0
    assert result.detected_country == "Mexico"
    assert any("Hashtag" in s for s in result.mexico_signals)


def test_caption_contains_mexican_city() -> None:
    """Caption 含墨西哥地名 → 检测。"""
    profile = _make_profile(biography="creator")
    result = detect_mexico_signal(
        profile,
        recent_captions=["Hoy estuve en Cancún disfrutando la playa"],
    )
    assert result.detected_country == "Mexico"
    assert result.detected_city == "cancún"
    assert result.mexico_confidence_score > 0


def test_multiple_signals_higher_confidence() -> None:
    """多信号组合 → confidence 较高。"""
    profile = _make_profile(
        biography="Vivo en Mexico, CDMX",
        external_url="https://tienda.mx",
    )
    result = detect_mexico_signal(
        profile,
        source_hashtags=["mexico", "cdmx"],
        recent_captions=["Desde Polanco"],
    )
    assert result.mexico_confidence_score >= 0.6
    assert result.detected_country == "Mexico"
    assert len(result.mexico_signals) >= 3


def test_confidence_increases_with_more_signals() -> None:
    """信号越多 confidence 越高。"""
    profile_single = _make_profile(biography="Mexico")
    profile_multi = _make_profile(
        biography="Mexico CDMX",
        external_url="https://x.mx",
    )
    result_single = detect_mexico_signal(profile_single)
    result_multi = detect_mexico_signal(profile_multi, source_hashtags=["mexico", "cdmx"])
    assert result_multi.mexico_confidence_score > result_single.mexico_confidence_score


def test_single_strong_signal_capped_at_half() -> None:
    """单个强信号 confidence 上限为 0.5。"""
    profile = _make_profile(biography="Mexico")
    result = detect_mexico_signal(profile)
    assert result.mexico_confidence_score <= 0.5


# ---------- 输出字段 ----------


def test_output_fields_present() -> None:
    """输出字段：mexico_confidence_score/mexico_signals/detected_country/detected_state/detected_city。"""
    profile = _make_profile(biography="Vivo en CDMX, Mexico")
    result = detect_mexico_signal(profile)
    assert hasattr(result, "mexico_confidence_score")
    assert hasattr(result, "mexico_signals")
    assert hasattr(result, "detected_country")
    assert hasattr(result, "detected_state")
    assert hasattr(result, "detected_city")
    assert isinstance(result.mexico_signals, list)


def test_no_signals_returns_zero() -> None:
    """无任何墨西哥信号 → confidence 为 0。"""
    profile = _make_profile(biography="Just a regular creator")
    result = detect_mexico_signal(profile)
    assert result.mexico_confidence_score == 0.0
    assert result.detected_country is None
    assert result.detected_state is None
    assert result.detected_city is None


def test_location_text_signal() -> None:
    """公开地点标签含州名 → 检测。"""
    profile = _make_profile(biography="creator")
    result = detect_mexico_signal(profile, location_text="Jalisco, Mexico")
    assert result.detected_country == "Mexico"
    assert result.mexico_confidence_score > 0


def test_phone_country_code_auxiliary_signal() -> None:
    """+52 电话国家代码作为辅助信号。"""
    profile = _make_profile(biography="Contacto: +525512345678")
    result = detect_mexico_signal(profile)
    # 辅助信号单独不足以判定
    assert result.mexico_confidence_score == 0.0
    # 但应记录辅助信号
    assert any("辅助信号" in s for s in result.mexico_signals)
