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
