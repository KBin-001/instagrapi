"""浏览器扩展通信数据模型。

所有字段均对应 Instagram 网页公开可见信息。
- 不包含 Cookie / Session / 私信 / 私密账号内容
- 不包含推测邮箱 / 推测电话号码
- 仅记录用户主动公开的联系方式（bio 中的邮箱、wa.me、linktree 等）
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _ExtBase(BaseModel):
    """扩展模块所有模型的公共基类。"""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


class ExtensionHandshake(_ExtBase):
    """扩展首次连接时发送的握手信息。"""

    extension_version: str
    chrome_version: str | None = None
    user_agent: str | None = None


class ExtensionProfileData(_ExtBase):
    """扩展采集的博主公开主页信息。

    follower_text / following_text / post_count_text 为网页上显示的文本
    （如 "52.4K"、"1,234"），后端负责解析为整数。
    """

    username: str
    full_name: str | None = None
    biography: str | None = None
    follower_text: str | None = None
    following_text: str | None = None
    post_count_text: str | None = None
    external_links: list[str] = Field(default_factory=list)
    is_verified: bool | None = None
    is_business: bool | None = None
    category_name: str | None = None
    public_email: str | None = None
    is_private: bool | None = None
    profile_pic_url: str | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)


class ExtensionCandidateItem(_ExtBase):
    """候选账号项（来自官方推荐或关注列表）。"""

    username: str
    full_name: str | None = None
    profile_url: str | None = None
    is_verified: bool | None = None


class ExtensionProfilePayload(_ExtBase):
    """扩展推送的博主完整 payload（对应场景一）。"""

    source: str = "instagram_web_extension"
    collected_at: datetime
    page_url: str
    profile: ExtensionProfileData
    visible_recommendations: list[ExtensionCandidateItem] = Field(default_factory=list)
    recent_media_urls: list[str] = Field(default_factory=list, max_length=12)
    collection_version: str = "0.4.0"


class ExtensionCandidatesPayload(_ExtBase):
    """扩展推送的候选账号列表（对应场景二/三）。"""

    source: str = "instagram_web_extension"
    collected_at: datetime
    source_page_url: str
    candidates: list[ExtensionCandidateItem]


class ExtensionStatusResponse(_ExtBase):
    """扩展状态查询响应。"""

    connected: bool
    extension_version: str | None = None
    last_handshake_at: datetime | None = None
    today_collected: int = 0
    today_new_candidates: int = 0
    today_duplicates: int = 0
    today_excluded: int = 0
    local_api_url: str | None = None


class IngestResult(_ExtBase):
    """博主入库结果。"""

    username: str
    is_new: bool = False
    is_duplicate: bool = False
    is_excluded: bool = False
    error: str | None = None


class CandidatesIngestResult(_ExtBase):
    """候选账号入库结果。"""

    total: int = 0
    new: int = 0
    duplicates: int = 0
    excluded: int = 0


class ExtensionTaskCreate(_ExtBase):
    brief: str = ""
    seeds: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    bulk_links: list[str] = Field(default_factory=list, max_length=100)
    public_list_urls: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    min_followers: int | None = None
    max_followers: int | None = None
    minimum_median_reel_views: int | None = None
    maximum_days_since_last_post: int | None = None
    require_mexico_signal: bool | None = None
    require_public_contact: bool | None = None
    require_public_account: bool | None = None
    exclude_brands: bool | None = None
    exclude_media_accounts: bool | None = None
    target_niches: list[str] = Field(default_factory=list)
    max_profiles_to_analyze: int = Field(default=100, ge=1, le=500)


class TaskCandidatesPayload(_ExtBase):
    queue_item_id: int | None = None
    source_page_url: str
    source_type: str
    candidates: list[ExtensionCandidateItem]
    media_urls: list[str] = Field(default_factory=list)


class TaskProfilePayload(ExtensionProfilePayload):
    queue_item_id: int | None = None


class ExtensionMediaPayload(_ExtBase):
    queue_item_id: int | None = None
    username: str
    media_url: str
    shortcode: str
    media_type: str = "post"
    taken_at: datetime | None = None
    caption: str | None = None
    like_count: int | None = None
    comment_count: int | None = None
    visible_play_count: int | None = None
    is_reel: bool = False
    collected_at: datetime
    mentioned_usernames: list[str] = Field(default_factory=list, max_length=20)
    field_sources: dict[str, str | None] = Field(default_factory=dict)


class QueueFailurePayload(_ExtBase):
    queue_item_id: int
    error: str
    safe_stop: bool = False
    retryable: bool = True
    error_code: str = "collection_error"
    diagnostics: dict[str, str | int | bool | None] = Field(default_factory=dict)


class TaskRerankPayload(_ExtBase):
    brief: str = Field(min_length=2, max_length=2000)


class CreatorReviewAction(_ExtBase):
    list_name: str = "默认达人库"
    note: str | None = None
