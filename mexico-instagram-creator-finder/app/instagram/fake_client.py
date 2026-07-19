"""Fake Instagram Client — 用于无网络、无登录的本地测试。

本模块提供与 :class:`app.instagram.client.InstagramClient` 相同的接口，
但返回预定义的示例数据，覆盖多种筛选场景：

- 完美匹配的墨西哥香水创作者（A级）
- 墨西哥美妆/护肤/穿搭创作者（B/C级）
- 粉丝不足被跳过
- 私密账号被跳过
- 品牌账号被排除
- 媒体账号被排除
- 停更账号被跳过
- 无墨西哥信号被跳过

合规说明：
- 所有数据均为虚构，不对应真实 Instagram 账号
- 仅用于本地测试与流程演示
- 不发起任何网络请求
- 不实现任何 AGENTS.md §5 禁止的功能
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.models import ProfileData


def _now() -> datetime:
    return datetime.now(UTC)


def _days_ago(days: int) -> datetime:
    return _now() - timedelta(days=days)


# ============================================================
# Fake 数据类型（鸭子类型，仅需暴露 mappers.py 用到的属性）
# ============================================================


class FakeUser:
    """模拟 instagrapi.types.User。"""

    def __init__(
        self,
        *,
        pk: str,
        username: str,
        full_name: str,
        biography: str = "",
        follower_count: int = 0,
        following_count: int = 0,
        media_count: int = 0,
        is_private: bool = False,
        is_verified: bool = False,
        is_business: bool = False,
        category_name: str | None = None,
        business_category_name: str | None = None,
        external_url: str | None = None,
        public_email: str | None = None,
        profile_pic_url: str = "https://example.com/avatar.jpg",
    ) -> None:
        self.pk = pk
        self.username = username
        self.full_name = full_name
        self.biography = biography
        self.follower_count = follower_count
        self.following_count = following_count
        self.media_count = media_count
        self.is_private = is_private
        self.is_verified = is_verified
        self.is_business = is_business
        self.category_name = category_name
        self.business_category_name = business_category_name
        self.external_url = external_url
        self.public_email = public_email
        self.profile_pic_url = profile_pic_url


class FakeMedia:
    """模拟 instagrapi.types.Media。"""

    def __init__(
        self,
        *,
        pk: str,
        user: FakeUser,
        like_count: int = 0,
        comment_count: int = 0,
        taken_at: datetime | None = None,
        media_type: int = 1,  # 1=图片, 2=视频/Reel
        product_type: str | None = None,  # "clips"=Reel, "igtv"=IGTV
        view_count: int | None = None,
        play_count: int | None = None,
        like_and_view_counts_disabled: bool = False,
        caption_text: str = "",
    ) -> None:
        self.pk = pk
        self.user = user
        self.like_count = like_count
        self.comment_count = comment_count
        self.taken_at = taken_at
        self.media_type = media_type
        self.product_type = product_type
        self.view_count = view_count
        self.play_count = play_count
        self.like_and_view_counts_disabled = like_and_view_counts_disabled
        self.caption_text = caption_text


# ============================================================
# 预定义示例账号（覆盖各种筛选场景）
# ============================================================


# 账号 1：完美匹配的墨西哥香水创作者 → A 级
_user_perfumista = FakeUser(
    pk="1001",
    username="xiangshui_cdmx",
    full_name="苏菲雅 · 香水测评",
    biography=(
        "香水测评师 🇲🇽\n"
        "驻地：墨西哥城 CDMX, México\n"
        "合作邮箱：contacto@xiangshuimx.com\n"
        "WhatsApp: https://wa.me/525512345678"
    ),
    follower_count=85000,
    following_count=432,
    media_count=342,
    is_private=False,
    is_verified=False,
    is_business=False,
    external_url="https://xiangshuimx.com.mx",
    public_email="contacto@xiangshuimx.com",
)

# 账号 2：墨西哥美妆博主 → B 级
_user_beauty_laura = FakeUser(
    pk="1002",
    username="meizhuang_laura",
    full_name="劳拉 · 美妆教程",
    biography=("专业化妆师 💄\n瓜达拉哈拉 Guadalajara, Jalisco 🇲🇽\n美妆与护肤博主\ncontacto@laurabeauty.mx"),
    follower_count=124000,
    following_count=689,
    media_count=567,
    is_private=False,
    is_verified=False,
    is_business=False,
    category_name="Beauty & Makeup",
    external_url="https://linktr.ee/laurabeauty",
    public_email="contacto@laurabeauty.mx",
)

# 账号 3：护肤创作者 → B 级
_user_skincare_merida = FakeUser(
    pk="1003",
    username="hufu_merida",
    full_name="卡米拉 · 护肤分享",
    biography=("护肤步骤与心得 🌿\n梅里达 Mérida, Yucatán 🇲🇽\n产品测评与日常护肤\nwa.me/529991234567"),
    follower_count=42000,
    following_count=312,
    media_count=189,
    is_private=False,
    is_business=False,
    external_url="https://beacons.ai/hufumerida",
)

# 账号 4：穿搭创作者 → C 级（信息不足）
_user_moda_cdmx = FakeUser(
    pk="1004",
    username="chuanda_cdmx",
    full_name="丹妮拉 · 穿搭日记",
    biography="穿搭博主 | CDMX | México 穿搭分享",
    follower_count=67000,
    following_count=521,
    media_count=234,
    is_private=False,
    is_business=False,
    external_url=None,
)

# 账号 5：粉丝不足 → 被跳过
_user_small_followers = FakeUser(
    pk="1005",
    username="xiaoshizi_mx",
    full_name="玛丽亚 · 香水爱好者",
    biography="香水爱好者 in Monterrey 🇲🇽",
    follower_count=8500,  # 低于 min_followers=20000
    following_count=201,
    media_count=67,
    is_private=False,
    is_business=False,
)

# 账号 6：私密账号 → 被跳过
_user_private_account = FakeUser(
    pk="1006",
    username="private_xiangshui_riji",
    full_name="安娜 · 香水日记",
    biography="私密账号",
    follower_count=35000,
    following_count=445,
    media_count=89,
    is_private=True,
    is_business=False,
)

# 账号 7：品牌账号 → 被排除
_user_brand_oficial = FakeUser(
    pk="1007",
    username="xiangshui_pinpai_mx",
    full_name="香水品牌墨西哥官方",
    biography=("香水官方店铺\n全墨西哥发货 🇲🇽\n购买：tienda@xiangshuipinpai.mx"),
    follower_count=180000,
    following_count=12,
    media_count=456,
    is_private=False,
    is_business=True,
    category_name="Shopping & Retail",
    external_url="https://xiangshuipinpai.mx",
    public_email="tienda@xiangshuipinpai.mx",
)

# 账号 8：媒体账号 → 被排除
_user_media_news = FakeUser(
    pk="1008",
    username="meizhuang_news_mx",
    full_name="美妆新闻墨西哥",
    biography="美妆与潮流媒体 🇲🇽",
    follower_count=220000,
    following_count=34,
    media_count=1234,
    is_private=False,
    is_business=True,
    category_name="Media/News Company",
    external_url="https://meizhuangnews.mx",
)

# 账号 9：停更账号 → 被跳过
_user_inactive = FakeUser(
    pk="1009",
    username="jiu_xiangshui_blog",
    full_name="香水博客 MX",
    biography="香水博客（停更）",
    follower_count=55000,
    following_count=123,
    media_count=78,
    is_private=False,
    is_business=False,
)

# 账号 10：无墨西哥信号 → 被跳过
_user_non_mexico = FakeUser(
    pk="1010",
    username="xiangshui_lover_us",
    full_name="艾玛 · 香水测评",
    biography="Perfume reviewer from California ✨",
    follower_count=95000,
    following_count=234,
    media_count=312,
    is_private=False,
    is_business=False,
    external_url="https://emmaperfume.com",
)


# 所有示例账号（按用户名索引）
_ALL_USERS: dict[str, FakeUser] = {
    u.username: u
    for u in [
        _user_perfumista,
        _user_beauty_laura,
        _user_skincare_merida,
        _user_moda_cdmx,
        _user_small_followers,
        _user_private_account,
        _user_brand_oficial,
        _user_media_news,
        _user_inactive,
        _user_non_mexico,
    ]
}


# ============================================================
# 为每个账号生成近期内容
# ============================================================


def _make_medias_for(user: FakeUser) -> list[FakeMedia]:
    """为指定账号生成 8-12 条近期内容。"""
    username = user.username

    if username == "xiangshui_cdmx":
        # 完美：8 条 Reels，播放量都很高
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=3200 + i * 100,
                comment_count=85 + i * 5,
                taken_at=_days_ago(i * 3),
                media_type=2,
                product_type="clips",
                view_count=12000 + i * 800,
                caption_text=f"香水测评 #{i} #perfumemexico #fragancias #cdmx",
            )
            for i in range(1, 9)
        ]

    if username == "meizhuang_laura":
        # 美妆：10 条混合内容，部分 Reels 有播放量
        medias: list[FakeMedia] = []
        for i in range(1, 11):
            is_reel = i % 2 == 0
            medias.append(
                FakeMedia(
                    pk=f"{user.pk}_m{i}",
                    user=user,
                    like_count=5400 + i * 200,
                    comment_count=120 + i * 8,
                    taken_at=_days_ago(i * 2),
                    media_type=2 if is_reel else 1,
                    product_type="clips" if is_reel else None,
                    view_count=8500 + i * 600 if is_reel else None,
                    caption_text=f"美妆教程 #{i} #makeupmx #belleza #guadalajara",
                )
            )
        return medias

    if username == "hufu_merida":
        # 护肤：6 条 Reels，播放量中等
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=1800 + i * 80,
                comment_count=45 + i * 3,
                taken_at=_days_ago(i * 4),
                media_type=2,
                product_type="clips",
                view_count=3200 + i * 250,
                caption_text=f"护肤步骤 #{i} #skincare #merida #yucatan",
            )
            for i in range(1, 7)
        ]

    if username == "chuanda_cdmx":
        # 穿搭：5 条内容，无 Reels（信息不足）
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=2400 + i * 100,
                comment_count=55 + i * 2,
                taken_at=_days_ago(i * 5),
                media_type=1,
                caption_text=f"今日穿搭 #{i} #moda #cdmx",
            )
            for i in range(1, 6)
        ]

    if username == "xiaoshizi_mx":
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=200 + i * 10,
                comment_count=5 + i,
                taken_at=_days_ago(i * 3),
                media_type=2,
                product_type="clips",
                view_count=500 + i * 50,
                caption_text=f"我最爱的香水 #{i} #perfume",
            )
            for i in range(1, 6)
        ]

    if username == "private_xiangshui_riji":
        return []

    if username == "xiangshui_pinpai_mx":
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=1500 + i * 50,
                comment_count=20 + i,
                taken_at=_days_ago(i * 2),
                media_type=1,
                caption_text=f"在售商品 #{i} #tienda #mexico",
            )
            for i in range(1, 8)
        ]

    if username == "meizhuang_news_mx":
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=3200 + i * 100,
                comment_count=85 + i * 3,
                taken_at=_days_ago(i * 2),
                media_type=2,
                product_type="clips",
                view_count=15000 + i * 500,
                caption_text=f"美妆新闻 #{i} #belleza #news",
            )
            for i in range(1, 9)
        ]

    if username == "jiu_xiangshui_blog":
        # 停更：最后一条发布于 120 天前
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=1200 + i * 50,
                comment_count=30 + i,
                taken_at=_days_ago(120 + i * 10),  # 全部超过 90 天
                media_type=1,
                caption_text=f"旧版香水测评 #{i}",
            )
            for i in range(1, 5)
        ]

    if username == "xiangshui_lover_us":
        return [
            FakeMedia(
                pk=f"{user.pk}_m{i}",
                user=user,
                like_count=4200 + i * 150,
                comment_count=95 + i * 4,
                taken_at=_days_ago(i * 3),
                media_type=2,
                product_type="clips",
                view_count=11000 + i * 700,
                caption_text=f"香水测评 #{i} #perfume #california",
            )
            for i in range(1, 9)
        ]

    return []


# ============================================================
# Hashtag → 媒体列表映射（让不同 Hashtag 返回不同子集）
# ============================================================


def _medias_for_hashtag(tag: str) -> list[FakeMedia]:
    """根据 Hashtag 返回包含多个作者媒体的列表。"""
    tag_lower = tag.lower().lstrip("#")

    # 所有候选账号的近期 media（取每个账号前 2 条作为 hashtag 媒体）
    candidate_medias: list[FakeMedia] = []
    for user in _ALL_USERS.values():
        user_medias = _make_medias_for(user)
        candidate_medias.extend(user_medias[:2])

    # 按 Hashtag 关键词过滤（简单匹配 caption）
    keyword_map = {
        "perfumemexico": ["perfume", "fragancias", "perfumista"],
        "fraganciasmexico": ["fragancias", "perfume"],
        "bellezamx": ["belleza", "maquillaje", "makeup"],
        "skincaremx": ["skincare", "rutina"],
        "modamx": ["moda", "outfit", "fashion"],
    }
    keywords = keyword_map.get(tag_lower, [])
    if not keywords:
        # 未识别的 Hashtag：返回所有候选媒体（让流程仍能跑通）
        return candidate_medias[:8]

    filtered = [m for m in candidate_medias if any(k in m.caption_text.lower() for k in keywords)]
    # 至少返回一些媒体，避免空列表导致流程无候选
    return filtered if filtered else candidate_medias[:4]


# ============================================================
# FakeInstagramClient
# ============================================================


class FakeInstagramClient:
    """Instagram Client 的本地测试替身。

    实现与 :class:`app.instagram.client.InstagramClient` 相同的公开接口，
    但所有数据来自本模块的预定义示例，不发起任何网络请求。
    """

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings
        self._logged_in = False
        # 用于模拟"被查询过的 username"集合，让 user_medias 能按用户返回
        self._users_db: dict[str, FakeUser] = dict(_ALL_USERS)
        self._medias_cache: dict[str, list[FakeMedia]] = {uname: _make_medias_for(u) for uname, u in _ALL_USERS.items()}

    def login_from_env(self) -> None:
        """模拟登录，立即成功。"""
        self._logged_in = True
        # 不调用任何真实 API，不保存 session

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    def hashtag_medias(self, name: str, amount: int = 20) -> list[FakeMedia]:
        """返回预定义的 Hashtag 媒体列表。"""
        medias = _medias_for_hashtag(name)
        return medias[:amount]

    def user_info_by_username(self, username: str) -> ProfileData:
        """返回预定义的用户资料。"""
        user = self._users_db.get(username)
        if user is None:
            # 未在示例数据库中的用户：返回一个默认的虚构用户
            user = FakeUser(
                pk="9999",
                username=username,
                full_name=username.replace("_", " ").title(),
                biography="示例账号",
                follower_count=30000,
                following_count=200,
                media_count=100,
                is_private=False,
                is_business=False,
            )
            self._users_db[username] = user
            self._medias_cache[username] = _make_medias_for(user)
        # 通过 mappers 转换为 ProfileData，保持与真实流程一致
        from app.instagram.mappers import map_user_to_profile

        return map_user_to_profile(user, username=username)

    def user_medias(self, username: str, amount: int = 12) -> list[FakeMedia]:
        """返回预定义的用户近期内容。"""
        # 确保用户存在
        if username not in self._users_db:
            self.user_info_by_username(username)
        medias = self._medias_cache.get(username, [])
        return medias[:amount]

    def search_users(self, query: str, amount: int = 20) -> list[FakeUser]:
        lowered = query.lower()
        matches = [
            user
            for user in self._users_db.values()
            if lowered in user.username.lower()
            or lowered in user.full_name.lower()
            or lowered in user.biography.lower()
        ]
        return matches[:amount]

    def related_profiles(self, username: str, amount: int = 20) -> list[FakeUser]:
        return [user for key, user in self._users_db.items() if key != username][:amount]


__all__ = [
    "FakeInstagramClient",
    "FakeUser",
    "FakeMedia",
]
