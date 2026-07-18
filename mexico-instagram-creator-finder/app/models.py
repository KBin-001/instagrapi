"""Mexico Instagram Creator Finder 核心数据模型。

所有模型基于 Pydantic v2 BaseModel，可序列化为 JSON 与 dict。
模型字段全部使用 Optional/默认值，确保部分填充也可用。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _BaseModel(BaseModel):
    """项目所有模型的公共基类。"""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        from_attributes=True,
    )


class CandidateAccount(_BaseModel):
    """从公开入口发现的候选账号。"""

    username: str
    source_hashtags: list[str] = []
    discovered_at: datetime
    normalized: bool = False


class ProfileData(_BaseModel):
    """Instagram 公开主页资料。

    仅保存头像 URL，不下载或长期保存高清头像。
    """

    username: str
    pk: str | None = None
    full_name: str | None = None
    biography: str | None = None
    profile_url: str | None = None
    profile_pic_url: str | None = None
    follower_count: int | None = None
    following_count: int | None = None
    media_count: int | None = None
    is_private: bool | None = None
    is_verified: bool | None = None
    is_business: bool | None = None
    category_name: str | None = None
    business_category_name: str | None = None
    external_url: str | None = None
    public_email: str | None = None
    collected_at: datetime


class MediaMetrics(_BaseModel):
    """账号近期公开内容统计。

    reels_view_data_available 三态：
    - "no_reels"：未发布 Reels
    - "not_visible"：发布了 Reels 但播放量不可见
    - "available"：有可计算的播放量
    不得用 0 混淆以上三种情况。
    """

    recent_media_checked: int = 0
    recent_reels_checked: int = 0
    last_post_date: datetime | None = None
    days_since_last_post: int | None = None
    average_likes: float | None = None
    median_likes: float | None = None
    average_comments: float | None = None
    median_comments: float | None = None
    average_visible_reel_views: float | None = None
    median_visible_reel_views: float | None = None
    maximum_visible_reel_views: int | None = None
    posting_frequency: float | None = None
    reels_view_data_available: str = "no_reels"


class ContactInfo(_BaseModel):
    """公开联系方式。

    仅记录用户主动公开的联系方式，来源必须可追溯。
    不推测邮箱、不抓取隐藏页面、不访问登录后才能看到的内容。
    """

    public_email: str | None = None
    public_whatsapp_url: str | None = None
    external_url: str | None = None
    linktree_url: str | None = None
    beacons_url: str | None = None
    contact_source: str = "biography"
    has_public_contact: bool = False


class NicheClassification(_BaseModel):
    """垂类分类结果。

    分类依据包括 Biography、Full name、Category、来源 Hashtag、近期 Caption、近期内容 Hashtag。
    不得仅依赖单个关键词。
    """

    primary_niche: str = "general"
    niche_scores: dict[str, float] = {}
    niche_signals: list[str] = []
    classification_reasons: list[str] = []


class MexicoSignal(_BaseModel):
    """墨西哥地区识别信号。

    基于多个公开信号，每个信号必须可解释。
    不得仅凭单一信号（如 mx 两字母、西班牙语、国旗表情、单个 Hashtag）直接判定。
    """

    mexico_confidence_score: float = 0.0
    mexico_signals: list[str] = []
    detected_country: str | None = None
    detected_state: str | None = None
    detected_city: str | None = None


class AccountTypeClassification(_BaseModel):
    """账号类型识别结果。

    不直接删除疑似账号，仅记录分类与原因。
    """

    account_type: str = "personal_creator"
    account_type_confidence: float = 0.0
    account_type_reasons: list[str] = []


class ScoreResult(_BaseModel):
    """透明、可配置、可测试的评分结果。

    评分仅反映与当前搜索条件的匹配程度，
    不代表对个人价值、外貌或可信人格的判断。
    """

    total_score: float = 0.0
    score_breakdown: dict[str, float] = {}
    recommendation_level: str = "D"
    recommendation_reasons: list[str] = []


class TaskCheckpoint(_BaseModel):
    """任务断点信息，用于断点续传。"""

    task_id: str
    status: str = "pending"
    completed_hashtags: list[str] = []
    discovered_usernames: list[str] = []
    analyzed_usernames: list[str] = []
    failed_usernames: list[str] = []
    failed_reasons: dict[str, str] = {}
    stop_reason: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class CreatorRecord(_BaseModel):
    """创作者聚合记录，用于导出最终结果。"""

    username: str
    profile: ProfileData
    metrics: MediaMetrics | None = None
    contact: ContactInfo | None = None
    niche: NicheClassification | None = None
    mexico: MexicoSignal | None = None
    account_type: AccountTypeClassification | None = None
    score: ScoreResult | None = None
    excluded: bool = False
    exclusion_source: str | None = None
    exclusion_reason: str | None = None
