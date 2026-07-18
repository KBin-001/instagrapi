"""SQLite 存储与仓储层测试。

覆盖：
- app/storage/database.py：Database
- app/storage/repositories.py：upsert_profile / upsert_score / upsert_media_stats /
  upsert_contact / upsert_niche / upsert_mexico_signal / upsert_account_type /
  load_all_records
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.models import (
    AccountTypeClassification,
    ContactInfo,
    MediaMetrics,
    MexicoSignal,
    NicheClassification,
    ProfileData,
    ScoreResult,
)
from app.storage.database import (
    AccountTypeRow,
    CandidateRow,
    ContactRow,
    Database,
    HashtagRow,
    MediaStatsRow,
    MexicoSignalRow,
    NicheRow,
    ProfileRow,
    ScoreRow,
    TaskRow,
)
from app.storage.repositories import (
    get_profile,
    load_all_records,
    upsert_account_type,
    upsert_contact,
    upsert_media_stats,
    upsert_mexico_signal,
    upsert_niche,
    upsert_profile,
    upsert_score,
)

TASK_ID = "test-task-001"


def _now() -> datetime:
    return datetime.now(UTC)


def _make_profile(username: str = "alice") -> ProfileData:
    return ProfileData(
        username=username,
        pk="12345",
        full_name="Alice Creator",
        biography="Perfume lover from Mexico",
        profile_url="https://www.instagram.com/alice/",
        profile_pic_url="https://example.com/pic.jpg",
        follower_count=50000,
        following_count=200,
        media_count=150,
        is_private=False,
        is_verified=False,
        is_business=False,
        category_name="Beauty Blogger",
        business_category_name=None,
        external_url="https://alice.mx",
        public_email="contact@alice.mx",
        collected_at=_now(),
    )


def _make_metrics() -> MediaMetrics:
    return MediaMetrics(
        recent_media_checked=12,
        recent_reels_checked=5,
        last_post_date=_now(),
        days_since_last_post=3,
        average_likes=500.0,
        median_likes=450.0,
        average_comments=20.0,
        median_comments=18.0,
        average_visible_reel_views=5000.0,
        median_visible_reel_views=4500.0,
        maximum_visible_reel_views=8000,
        posting_frequency=3.5,
        reels_view_data_available="available",
    )


def _make_score() -> ScoreResult:
    return ScoreResult(
        total_score=85.5,
        score_breakdown={"mexico_region": 25.0, "niche_match": 20.0},
        recommendation_level="A",
        recommendation_reasons=["high mexico confidence"],
    )


def _make_contact() -> ContactInfo:
    return ContactInfo(
        public_email="contact@alice.mx",
        public_whatsapp_url="https://wa.me/521234567890",
        external_url="https://alice.mx",
        linktree_url="https://linktr.ee/alice",
        beacons_url=None,
        contact_source="biography_email,biography_wa_me",
        has_public_contact=True,
    )


def _make_niche() -> NicheClassification:
    return NicheClassification(
        primary_niche="perfume",
        niche_scores={"perfume": 0.8, "beauty": 0.3},
        niche_signals=["bio keyword: perfume"],
        classification_reasons=["multi-signal"],
    )


def _make_mexico() -> MexicoSignal:
    return MexicoSignal(
        mexico_confidence_score=0.9,
        mexico_signals=["bio=Mexico", "external_url=.mx"],
        detected_country="Mexico",
        detected_state="Ciudad de México",
        detected_city="polanco",
    )


def _make_account_type() -> AccountTypeClassification:
    return AccountTypeClassification(
        account_type="personal_creator",
        account_type_confidence=0.9,
        account_type_reasons=["default personal creator"],
    )


# ---------- Database 初始化 ----------


def test_database_initialization(tmp_path: Path) -> None:
    """Database 初始化创建文件与表。"""
    db_file = tmp_path / "test.db"
    db = Database(db_file)
    assert db_file.exists()
    # 表应已创建
    with db.get_session() as session:
        # 简单查询不应抛错
        session.execute(TaskRow.__table__.select())
    db.close()


def test_database_creates_parent_dir(tmp_path: Path) -> None:
    """Database 自动创建父目录。"""
    db_file = tmp_path / "subdir" / "nested" / "test.db"
    db = Database(db_file)
    assert db_file.exists()
    db.close()


# ---------- upsert_profile ----------


def test_upsert_profile_and_get(tmp_path: Path) -> None:
    """upsert_profile 后 get_profile 返回正确字段。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        profile = _make_profile("alice")
        upsert_profile(session, profile, TASK_ID)
        row = get_profile(session, TASK_ID, "alice")
        assert row is not None
        assert row.username == "alice"
        assert row.full_name == "Alice Creator"
        assert row.follower_count == 50000
        assert row.biography == "Perfume lover from Mexico"
        assert row.external_url == "https://alice.mx"
        assert row.public_email == "contact@alice.mx"
    db.close()


def test_upsert_profile_updates_existing(tmp_path: Path) -> None:
    """upsert_profile 更新已存在记录。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        profile1 = _make_profile("alice")
        profile1.follower_count = 50000
        upsert_profile(session, profile1, TASK_ID)

        profile2 = _make_profile("alice")
        profile2.follower_count = 60000
        upsert_profile(session, profile2, TASK_ID)

        row = get_profile(session, TASK_ID, "alice")
        assert row is not None
        assert row.follower_count == 60000
    db.close()


# ---------- upsert_score ----------


def test_upsert_score(tmp_path: Path) -> None:
    """upsert_score 写入评分。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_profile(session, _make_profile("alice"), TASK_ID)
        score = _make_score()
        upsert_score(session, score, TASK_ID, "alice")

        from sqlalchemy import select

        stmt = select(ScoreRow).where(ScoreRow.task_id == TASK_ID, ScoreRow.username == "alice")
        row = session.execute(stmt).scalar_one_or_none()
        assert row is not None
        assert row.total_score == 85.5
        assert row.recommendation_level == "A"
    db.close()


# ---------- upsert_media_stats ----------


def test_upsert_media_stats(tmp_path: Path) -> None:
    """upsert_media_stats 写入媒体统计。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_profile(session, _make_profile("alice"), TASK_ID)
        metrics = _make_metrics()
        upsert_media_stats(session, metrics, TASK_ID, "alice")

        from sqlalchemy import select

        stmt = select(MediaStatsRow).where(MediaStatsRow.task_id == TASK_ID, MediaStatsRow.username == "alice")
        row = session.execute(stmt).scalar_one_or_none()
        assert row is not None
        assert row.recent_media_checked == 12
        assert row.recent_reels_checked == 5
        assert row.median_visible_reel_views == 4500.0
        assert row.reels_view_data_available == "available"
    db.close()


# ---------- upsert_contact ----------


def test_upsert_contact(tmp_path: Path) -> None:
    """upsert_contact 写入联系方式。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_profile(session, _make_profile("alice"), TASK_ID)
        contact = _make_contact()
        upsert_contact(session, contact, TASK_ID, "alice")

        from sqlalchemy import select

        stmt = select(ContactRow).where(ContactRow.task_id == TASK_ID, ContactRow.username == "alice")
        row = session.execute(stmt).scalar_one_or_none()
        assert row is not None
        assert row.public_email == "contact@alice.mx"
        assert row.public_whatsapp_url == "https://wa.me/521234567890"
        assert row.has_public_contact == 1
    db.close()


# ---------- upsert_niche / upsert_mexico_signal / upsert_account_type ----------


def test_upsert_niche(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_profile(session, _make_profile("alice"), TASK_ID)
        upsert_niche(session, _make_niche(), TASK_ID, "alice")

        from sqlalchemy import select

        stmt = select(NicheRow).where(NicheRow.task_id == TASK_ID, NicheRow.username == "alice")
        row = session.execute(stmt).scalar_one_or_none()
        assert row is not None
        assert row.primary_niche == "perfume"
    db.close()


def test_upsert_mexico_signal(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_profile(session, _make_profile("alice"), TASK_ID)
        upsert_mexico_signal(session, _make_mexico(), TASK_ID, "alice")

        from sqlalchemy import select

        stmt = select(MexicoSignalRow).where(MexicoSignalRow.task_id == TASK_ID, MexicoSignalRow.username == "alice")
        row = session.execute(stmt).scalar_one_or_none()
        assert row is not None
        assert row.mexico_confidence_score == 0.9
        assert row.detected_country == "Mexico"
    db.close()


def test_upsert_account_type(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_profile(session, _make_profile("alice"), TASK_ID)
        upsert_account_type(session, _make_account_type(), TASK_ID, "alice")

        from sqlalchemy import select

        stmt = select(AccountTypeRow).where(AccountTypeRow.task_id == TASK_ID, AccountTypeRow.username == "alice")
        row = session.execute(stmt).scalar_one_or_none()
        assert row is not None
        assert row.account_type == "personal_creator"
        assert row.account_type_confidence == 0.9
    db.close()


# ---------- load_all_records ----------


def test_load_all_records(tmp_path: Path) -> None:
    """load_all_records 返回 CreatorRecord 列表。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        # 写入两个账号的完整数据
        for name in ("alice", "bob"):
            profile = _make_profile(name)
            upsert_profile(session, profile, TASK_ID)
            upsert_media_stats(session, _make_metrics(), TASK_ID, name)
            upsert_score(session, _make_score(), TASK_ID, name)
            upsert_contact(session, _make_contact(), TASK_ID, name)
            upsert_niche(session, _make_niche(), TASK_ID, name)
            upsert_mexico_signal(session, _make_mexico(), TASK_ID, name)
            upsert_account_type(session, _make_account_type(), TASK_ID, name)

        records = load_all_records(session, TASK_ID)
        assert len(records) == 2
        usernames = {r.username for r in records}
        assert usernames == {"alice", "bob"}

        # 验证 CreatorRecord 字段完整
        record = next(r for r in records if r.username == "alice")
        assert record.profile.full_name == "Alice Creator"
        assert record.metrics is not None
        assert record.metrics.median_visible_reel_views == 4500.0
        assert record.score is not None
        assert record.score.total_score == 85.5
        assert record.contact is not None
        assert record.contact.public_email == "contact@alice.mx"
        assert record.niche is not None
        assert record.niche.primary_niche == "perfume"
        assert record.mexico is not None
        assert record.mexico.detected_country == "Mexico"
        assert record.account_type is not None
        assert record.account_type.account_type == "personal_creator"
    db.close()


def test_load_all_records_empty(tmp_path: Path) -> None:
    """无数据时返回空列表。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        records = load_all_records(session, TASK_ID)
        assert records == []
    db.close()


# ---------- 不保存密码/Session ----------


def test_no_password_columns_in_schema() -> None:
    """验证 schema 无密码相关字段。"""
    # 检查所有表的列名
    for table_class in [
        TaskRow,
        HashtagRow,
        CandidateRow,
        ProfileRow,
        MediaStatsRow,
        ScoreRow,
        ContactRow,
        NicheRow,
        MexicoSignalRow,
        AccountTypeRow,
    ]:
        columns = {c.name for c in table_class.__table__.columns}
        # 不应含密码相关字段
        forbidden = {"password", "ig_password", "passwd", "pwd", "cookie", "session", "sessionid"}
        intersection = columns & forbidden
        assert not intersection, f"{table_class.__tablename__} 含禁止字段: {intersection}"


def test_no_session_data_in_profile_row() -> None:
    """ProfileRow 不应保存 Session/Cookie。"""
    columns = {c.name for c in ProfileRow.__table__.columns}
    forbidden_session = {"session", "sessionid", "cookie", "authorization", "token"}
    assert not (columns & forbidden_session)


# ---------- 多 task 隔离 ----------


def test_multiple_tasks_isolated(tmp_path: Path) -> None:
    """不同 task_id 数据隔离。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_profile(session, _make_profile("alice"), TASK_ID)
        upsert_profile(session, _make_profile("alice"), "other-task")

        row1 = get_profile(session, TASK_ID, "alice")
        row2 = get_profile(session, "other-task", "alice")
        assert row1 is not None
        assert row2 is not None
        assert row1.task_id == TASK_ID
        assert row2.task_id == "other-task"
    db.close()


def test_database_close_disposes_engine(tmp_path: Path) -> None:
    """close() 释放引擎。"""
    db = Database(tmp_path / "test.db")
    db.close()
    # 关闭后不应崩溃
    # 重新创建验证文件仍可用
    db2 = Database(tmp_path / "test.db")
    db2.close()
