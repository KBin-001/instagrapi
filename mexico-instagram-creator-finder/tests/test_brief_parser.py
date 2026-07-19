from app.analysis.brief_parser import parse_search_brief


def test_parse_chinese_brief_with_wan_range_and_contact() -> None:
    intent = parse_search_brief("寻找墨西哥香水和美妆个人创作者，2万—30万粉丝，最近90天活跃，需要公开邮箱")

    assert intent.min_followers == 20_000
    assert intent.max_followers == 300_000
    assert intent.require_mexico_signal is True
    assert intent.require_public_contact is True
    assert intent.maximum_days_since_last_post == 90
    assert {"perfume", "beauty"}.issubset(intent.target_niches)
    assert "personal_creator" in intent.target_account_types


def test_parse_spanish_brief_with_k_range_and_views() -> None:
    intent = parse_search_brief(
        "Creadores de belleza en México, 20k a 150k seguidores, vistas 5k, con email de contacto"
    )

    assert intent.min_followers == 20_000
    assert intent.max_followers == 150_000
    assert intent.minimum_median_reel_views == 5_000
    assert intent.require_mexico_signal is True
    assert intent.require_public_contact is True
    assert "beauty" in intent.target_niches


def test_unknown_brief_terms_are_kept_as_keyword_signals() -> None:
    intent = parse_search_brief("墨西哥香水测评 开箱 regalo artesanal")

    assert intent.content_keywords
    assert any(keyword in intent.content_keywords for keyword in ("开箱", "regalo", "artesanal"))


def test_parse_greater_than_follower_requirement() -> None:
    intent = parse_search_brief("墨西哥香水达人，粉丝数量大于1万，必须有联系方式")

    assert intent.min_followers == 10_000
    assert intent.max_followers is None
    assert intent.require_mexico_signal is True
    assert intent.require_public_contact is True
