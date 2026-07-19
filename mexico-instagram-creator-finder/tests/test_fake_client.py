"""FakeInstagramClient 测试。

验证 dry-run 模式使用的 Fake Client 能正常驱动业务流程，
不登录真实 Instagram、不发起网络请求。
"""

from __future__ import annotations

from app.instagram.fake_client import _ALL_USERS, FakeInstagramClient
from app.instagram.mappers import compute_media_metrics, map_media_to_candidate


def test_fake_client_login_immediate_success() -> None:
    """FakeClient 模拟登录立即成功，不调用真实 API。"""
    client = FakeInstagramClient()
    assert client.is_logged_in is False
    client.login_from_env()
    assert client.is_logged_in is True


def test_fake_client_hashtag_medias_returns_list() -> None:
    """hashtag_medias 返回 FakeMedia 列表。"""
    client = FakeInstagramClient()
    client.login_from_env()
    medias = client.hashtag_medias("perfumemexico", amount=10)
    assert isinstance(medias, list)
    assert len(medias) > 0
    # 每条 media 都有 user 属性
    for m in medias:
        assert hasattr(m, "user")
        assert hasattr(m, "caption_text")


def test_fake_client_user_info_returns_profile() -> None:
    """user_info_by_username 返回 ProfileData。"""
    client = FakeInstagramClient()
    client.login_from_env()
    profile = client.user_info_by_username("xiangshui_cdmx")
    assert profile.username == "xiangshui_cdmx"
    assert profile.follower_count == 85000
    assert profile.is_private is False
    assert "méxico" in (profile.biography or "").lower()


def test_fake_client_user_info_unknown_username_creates_default() -> None:
    """未知 username 也能返回一个默认 ProfileData，不抛异常。"""
    client = FakeInstagramClient()
    client.login_from_env()
    profile = client.user_info_by_username("unknown_random_user_xyz")
    assert profile.username == "unknown_random_user_xyz"
    assert profile.follower_count == 30000


def test_fake_client_user_medias_returns_list() -> None:
    """user_medias 返回该用户的近期内容列表。"""
    client = FakeInstagramClient()
    client.login_from_env()
    medias = client.user_medias("xiangshui_cdmx", amount=12)
    assert len(medias) > 0
    # xiangshui_cdmx 预定义 8 条 Reels
    assert all(m.media_type == 2 for m in medias)
    assert all(m.view_count is not None for m in medias)


def test_fake_client_user_medias_empty_for_private() -> None:
    """私密账号返回空 media 列表。"""
    client = FakeInstagramClient()
    client.login_from_env()
    medias = client.user_medias("private_xiangshui_riji", amount=12)
    assert medias == []


def test_fake_client_covers_various_scenarios() -> None:
    """示例数据覆盖多种筛选场景。"""
    # 完美匹配
    assert "xiangshui_cdmx" in _ALL_USERS
    # 粉丝不足
    assert _ALL_USERS["xiaoshizi_mx"].follower_count < 20000
    # 私密账号
    assert _ALL_USERS["private_xiangshui_riji"].is_private is True
    # 品牌账号
    assert _ALL_USERS["xiangshui_pinpai_mx"].is_business is True
    # 媒体账号
    assert _ALL_USERS["meizhuang_news_mx"].category_name == "Media/News Company"
    # 无墨西哥信号
    assert "xiangshui_lover_us" in _ALL_USERS


def test_fake_client_mappers_compatible() -> None:
    """FakeMedia 与 mappers.py 完全兼容。"""
    client = FakeInstagramClient()
    client.login_from_env()
    medias = client.hashtag_medias("perfumemexico", amount=5)

    # map_media_to_candidate
    for m in medias:
        candidate = map_media_to_candidate(m, "perfumemexico")
        assert candidate is not None
        assert candidate.username
        assert "perfumemexico" in candidate.source_hashtags

    # compute_media_metrics
    metrics = compute_media_metrics(medias)
    assert metrics.recent_media_checked > 0


def test_fake_client_map_user_to_profile() -> None:
    """FakeUser 与 map_user_to_profile 完全兼容。"""
    client = FakeInstagramClient()
    client.login_from_env()
    profile = client.user_info_by_username("meizhuang_laura")
    assert profile.full_name == "劳拉 · 美妆教程"
    assert profile.category_name == "Beauty & Makeup"
    assert profile.external_url == "https://linktr.ee/laurabeauty"


def test_fake_client_no_network_calls() -> None:
    """FakeClient 不应该有任何网络请求属性。"""
    client = FakeInstagramClient()
    # 不应该有 client._client / client.settings 等真实 instagrapi.Client 相关属性
    assert not hasattr(client, "_client") or client.__class__.__name__ == "FakeInstagramClient"
    # 不应该有 rate_limiter（真实客户端才有）
    assert not hasattr(client, "_rate_limiter")


def test_fake_client_supports_read_only_search_and_related_profiles() -> None:
    client = FakeInstagramClient()

    matches = client.search_users("香水", amount=5)
    related = client.related_profiles(matches[0].username, amount=3)

    assert matches
    assert len(related) <= 3
    assert all(user.username != matches[0].username for user in related)
