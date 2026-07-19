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

    # ===== 进度持久化字段（GUI 实时显示用）=====
    # 即使页面刷新/WebSocket 重连/GUI 重启，也能从 SQLite 恢复最新进度
    stage = Column(String, nullable=True)  # 当前阶段（login/discovery/deduplication/...）
    progress_message = Column(Text, nullable=True)  # 最近一条进度消息
    current_hashtag = Column(String, nullable=True)
    current_username = Column(String, nullable=True)
    hashtags_total = Column(Integer, default=0)
    hashtags_completed = Column(Integer, default=0)
    candidates_found = Column(Integer, default=0)  # 原始发现数
    candidates_kept = Column(Integer, default=0)  # 去重+排除后保留数
    profiles_total = Column(Integer, default=0)  # 待分析账号数
    profiles_analyzed = Column(Integer, default=0)  # 已分析（含匹配+跳过+失败）
    profiles_matched = Column(Integer, default=0)  # 符合条件的账号数
    profiles_skipped = Column(Integer, default=0)  # 被筛选跳过的账号数
    profiles_failed = Column(Integer, default=0)  # 失败账号数
    overall_progress = Column(Integer, default=0)  # 总体百分比 0-100
    progress_updated_at = Column(DateTime, nullable=True)  # 进度最后更新时间


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
        self._migrate_task_progress_columns()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        logger.info("database initialized at %s", self.database_file)

    def _migrate_task_progress_columns(self) -> None:
        """自动为旧版 tasks 表添加进度持久化列（ALTER TABLE ADD COLUMN）。

        幂等：已存在的列会跳过。SQLite 不支持 IF NOT EXISTS，所以用 PRAGMA 检查。
        """
        # 期望的列名列表（与 TaskRow 中的进度字段一致）
        progress_columns: list[tuple[str, str]] = [
            ("stage", "VARCHAR"),
            ("progress_message", "TEXT"),
            ("current_hashtag", "VARCHAR"),
            ("current_username", "VARCHAR"),
            ("hashtags_total", "INTEGER DEFAULT 0"),
            ("hashtags_completed", "INTEGER DEFAULT 0"),
            ("candidates_found", "INTEGER DEFAULT 0"),
            ("candidates_kept", "INTEGER DEFAULT 0"),
            ("profiles_total", "INTEGER DEFAULT 0"),
            ("profiles_analyzed", "INTEGER DEFAULT 0"),
            ("profiles_matched", "INTEGER DEFAULT 0"),
            ("profiles_skipped", "INTEGER DEFAULT 0"),
            ("profiles_failed", "INTEGER DEFAULT 0"),
            ("overall_progress", "INTEGER DEFAULT 0"),
            ("progress_updated_at", "DATETIME"),
        ]
        try:
            with self.engine.connect() as conn:
                from sqlalchemy import text

                rows = conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
                existing_cols = {r[1] for r in rows}  # r[1] 是列名
                for col_name, col_type in progress_columns:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}"))
                        logger.info("migrated tasks table: added column %s", col_name)
                conn.commit()
        except Exception as e:  # noqa: BLE001 - 迁移失败不应阻塞启动
            logger.warning("task progress migration skipped: %s", e)

    def get_session(self):
        return self.Session()

    def close(self) -> None:
        self.engine.dispose()
