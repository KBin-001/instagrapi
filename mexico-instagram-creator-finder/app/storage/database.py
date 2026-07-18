"""SQLite 数据库初始化与表结构定义。

使用 SQLAlchemy 2.0 风格。
表：tasks / hashtags / candidates / profiles / media_stats / scores / contacts / niches /
    mexico_signals / account_types / checkpoints

遵守 AGENTS.md：
- 默认使用 SQLite
- 不保存密码、完整 Session、私信、私密账号内容、未公开电话号码、推测邮箱、下载视频、大量原始图片
- 所有公开联系方式必须记录来源
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.logging_config import get_logger

logger = get_logger("storage.database")


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True)
    status = Column(String, default="pending")  # pending/running/paused/completed/stopped/failed
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    stop_reason = Column(Text, nullable=True)
    config_snapshot = Column(Text, nullable=True)  # JSON 快照（脱敏）


class HashtagRow(Base):
    __tablename__ = "hashtags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    hashtag = Column(String, index=True)
    completed = Column(Integer, default=0)  # 0/1
    candidates_found = Column(Integer, default=0)
    completed_at = Column(DateTime, nullable=True)


class CandidateRow(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    source_hashtags = Column(Text, nullable=True)  # JSON list
    discovered_at = Column(DateTime)
    normalized = Column(Integer, default=0)
    excluded = Column(Integer, default=0)
    exclusion_source = Column(Text, nullable=True)
    exclusion_reason = Column(Text, nullable=True)


class ProfileRow(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    pk = Column(String, nullable=True)
    full_name = Column(Text, nullable=True)
    biography = Column(Text, nullable=True)
    profile_url = Column(Text, nullable=True)
    profile_pic_url = Column(Text, nullable=True)
    follower_count = Column(Integer, nullable=True)
    following_count = Column(Integer, nullable=True)
    media_count = Column(Integer, nullable=True)
    is_private = Column(Integer, nullable=True)
    is_verified = Column(Integer, nullable=True)
    is_business = Column(Integer, nullable=True)
    category_name = Column(Text, nullable=True)
    business_category_name = Column(Text, nullable=True)
    external_url = Column(Text, nullable=True)
    public_email = Column(Text, nullable=True)
    collected_at = Column(DateTime)


class MediaStatsRow(Base):
    __tablename__ = "media_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    recent_media_checked = Column(Integer, default=0)
    recent_reels_checked = Column(Integer, default=0)
    last_post_date = Column(DateTime, nullable=True)
    days_since_last_post = Column(Integer, nullable=True)
    average_likes = Column(Float, nullable=True)
    median_likes = Column(Float, nullable=True)
    average_comments = Column(Float, nullable=True)
    median_comments = Column(Float, nullable=True)
    average_visible_reel_views = Column(Float, nullable=True)
    median_visible_reel_views = Column(Float, nullable=True)
    maximum_visible_reel_views = Column(Integer, nullable=True)
    posting_frequency = Column(Float, nullable=True)
    reels_view_data_available = Column(String, default="no_reels")


class ScoreRow(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    total_score = Column(Float, default=0.0)
    score_breakdown = Column(Text, nullable=True)  # JSON
    recommendation_level = Column(String, default="D")
    recommendation_reasons = Column(Text, nullable=True)  # JSON list


class ContactRow(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    public_email = Column(Text, nullable=True)
    public_whatsapp_url = Column(Text, nullable=True)
    external_url = Column(Text, nullable=True)
    linktree_url = Column(Text, nullable=True)
    beacons_url = Column(Text, nullable=True)
    contact_source = Column(Text, nullable=True)
    has_public_contact = Column(Integer, default=0)


class NicheRow(Base):
    __tablename__ = "niches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    primary_niche = Column(String, default="general")
    niche_scores = Column(Text, nullable=True)  # JSON
    niche_signals = Column(Text, nullable=True)  # JSON list
    classification_reasons = Column(Text, nullable=True)  # JSON list


class MexicoSignalRow(Base):
    __tablename__ = "mexico_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    mexico_confidence_score = Column(Float, default=0.0)
    mexico_signals = Column(Text, nullable=True)  # JSON list
    detected_country = Column(Text, nullable=True)
    detected_state = Column(Text, nullable=True)
    detected_city = Column(Text, nullable=True)


class AccountTypeRow(Base):
    __tablename__ = "account_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)
    username = Column(String, index=True)
    account_type = Column(String, default="personal_creator")
    account_type_confidence = Column(Float, default=0.0)
    account_type_reasons = Column(Text, nullable=True)  # JSON list


class CheckpointRow(Base):
    __tablename__ = "checkpoints"

    task_id = Column(String, primary_key=True)
    status = Column(String, default="pending")
    completed_hashtags = Column(Text, nullable=True)  # JSON list
    discovered_usernames = Column(Text, nullable=True)  # JSON list
    analyzed_usernames = Column(Text, nullable=True)  # JSON list
    failed_usernames = Column(Text, nullable=True)  # JSON list
    failed_reasons = Column(Text, nullable=True)  # JSON dict
    stop_reason = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class Database:
    """SQLite 数据库管理器。

    所有表均不包含密码、完整 Session、私信或私密账号内容。
    """

    def __init__(self, database_file: str | Path = "data/app.db"):
        self.database_file = Path(database_file)
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.database_file.as_posix()}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        logger.info("database initialized at %s", self.database_file)

    def get_session(self):
        return self.Session()

    def close(self) -> None:
        self.engine.dispose()
