"""任务进度持久化测试。

覆盖：
- Database 自动迁移：旧版 tasks 表（无进度列）→ 升级后包含所有进度列
- update_task_progress：写入/更新进度字段
- get_latest_task：按 updated_at 倒序返回最新任务
- compute_overall_progress：各阶段百分比估算
- SearchService.emit 持久化路径：dry-run 任务结束后 tasks 表有进度数据
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.storage.database import Database, TaskRow
from app.storage.repositories import (
    compute_overall_progress,
    get_latest_task,
    get_recent_tasks,
    update_task_progress,
    upsert_task,
)

# ---------- 自动迁移 ----------


def test_migration_adds_progress_columns_to_old_db(tmp_path: Path) -> None:
    """旧版数据库（无进度列）打开后自动添加进度列。"""
    db_file = tmp_path / "old.db"
    # 手动创建一个旧版 tasks 表（无进度列）
    import sqlite3

    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE tasks (
                task_id VARCHAR PRIMARY KEY,
                status VARCHAR,
                started_at DATETIME,
                updated_at DATETIME,
                completed_at DATETIME,
                stop_reason TEXT,
                config_snapshot TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO tasks (task_id, status) VALUES (?, ?)",
            ("old-task", "completed"),
        )
        conn.commit()

    # 用 Database 打开 → 触发迁移
    db = Database(db_file)
    with db.get_session() as session:
        row = session.get(TaskRow, "old-task")
        assert row is not None
        # 新增的进度列应有默认值
        assert row.stage is None
        assert row.hashtags_total == 0
        assert row.profiles_analyzed == 0
        assert row.overall_progress == 0
    db.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    """多次打开同一数据库不会重复迁移或报错。"""
    db_file = tmp_path / "test.db"
    db1 = Database(db_file)
    db1.close()
    # 第二次打开：列已存在，迁移应跳过
    db2 = Database(db_file)
    with db2.get_session() as session:
        # 写入测试
        upsert_task(session, "t1", status="running")
        update_task_progress(session, "t1", stage="login", overall_progress=5)
    db2.close()
    # 第三次打开
    db3 = Database(db_file)
    with db3.get_session() as session:
        row = session.get(TaskRow, "t1")
        assert row is not None
        assert row.stage == "login"
        assert row.overall_progress == 5
    db3.close()


# ---------- update_task_progress ----------


def test_update_task_progress_writes_all_fields(tmp_path: Path) -> None:
    """update_task_progress 写入所有进度字段。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_task(session, "task-1", status="running")
        update_task_progress(
            session,
            "task-1",
            stage="profile_analysis",
            message="正在分析 @alice",
            current_hashtag="perfumemexico",
            current_username="alice",
            hashtags_total=15,
            hashtags_completed=15,
            candidates_found=180,
            candidates_kept=120,
            profiles_total=100,
            profiles_analyzed=43,
            profiles_matched=17,
            profiles_skipped=21,
            profiles_failed=2,
            overall_progress=65,
        )

        row = session.get(TaskRow, "task-1")
        assert row is not None
        assert row.stage == "profile_analysis"
        assert row.progress_message == "正在分析 @alice"
        assert row.current_hashtag == "perfumemexico"
        assert row.current_username == "alice"
        assert row.hashtags_total == 15
        assert row.hashtags_completed == 15
        assert row.candidates_found == 180
        assert row.candidates_kept == 120
        assert row.profiles_total == 100
        assert row.profiles_analyzed == 43
        assert row.profiles_matched == 17
        assert row.profiles_skipped == 21
        assert row.profiles_failed == 2
        assert row.overall_progress == 65
        assert row.progress_updated_at is not None
    db.close()


def test_update_task_progress_partial_update(tmp_path: Path) -> None:
    """部分更新：只传某些字段，其他字段保持不变。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_task(session, "task-2", status="running")
        # 第一次写
        update_task_progress(
            session,
            "task-2",
            stage="discovery",
            candidates_found=50,
            overall_progress=10,
        )
        # 第二次部分更新
        update_task_progress(
            session,
            "task-2",
            stage="discovery",
            candidates_found=80,  # 只更新这个
            hashtags_completed=3,
            hashtags_total=10,
        )

        row = session.get(TaskRow, "task-2")
        assert row is not None
        assert row.candidates_found == 80  # 新值
        assert row.hashtags_completed == 3
        assert row.hashtags_total == 10
        # overall_progress 不会被清零（None 不覆盖）
        assert row.overall_progress == 10
    db.close()


def test_update_task_progress_unknown_task_no_error(tmp_path: Path) -> None:
    """未知 task_id 不应抛错（仅记日志）。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        # 不存在的 task_id
        update_task_progress(session, "nonexistent", stage="login", overall_progress=5)
        # 应无异常
    db.close()


def test_overall_progress_clamped_to_0_100(tmp_path: Path) -> None:
    """overall_progress 被夹在 [0, 100]。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_task(session, "task-3", status="running")
        update_task_progress(session, "task-3", overall_progress=150)
        row = session.get(TaskRow, "task-3")
        assert row is not None
        assert row.overall_progress == 100

        update_task_progress(session, "task-3", overall_progress=-20)
        row = session.get(TaskRow, "task-3")
        assert row.overall_progress == 0
    db.close()


# ---------- get_latest_task / get_recent_tasks ----------


def test_get_latest_task_returns_most_recent(tmp_path: Path) -> None:
    """get_latest_task 按 updated_at 倒序返回最新任务。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_task(session, "old-task", status="completed")
        # 让 old-task 的 updated_at 早一点
        from sqlalchemy import update

        session.execute(
            update(TaskRow).where(TaskRow.task_id == "old-task").values(updated_at=datetime(2025, 1, 1, tzinfo=UTC))
        )
        session.commit()

        upsert_task(session, "new-task", status="running")
        update_task_progress(session, "new-task", stage="login")

        latest = get_latest_task(session)
        assert latest is not None
        assert latest.task_id == "new-task"
    db.close()


def test_get_latest_task_empty_db_returns_none(tmp_path: Path) -> None:
    """空数据库返回 None。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        assert get_latest_task(session) is None
    db.close()


def test_get_recent_tasks_returns_sorted(tmp_path: Path) -> None:
    """get_recent_tasks 按 started_at 倒序返回。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        upsert_task(session, "t1", status="completed", started_at=datetime(2025, 1, 1, tzinfo=UTC))
        upsert_task(session, "t2", status="completed", started_at=datetime(2025, 6, 1, tzinfo=UTC))
        upsert_task(session, "t3", status="completed", started_at=datetime(2025, 3, 1, tzinfo=UTC))

        tasks = get_recent_tasks(session, limit=10)
        assert len(tasks) == 3
        # 最新的在前
        assert tasks[0].task_id == "t2"
        assert tasks[1].task_id == "t3"
        assert tasks[2].task_id == "t1"
    db.close()


# ---------- compute_overall_progress ----------


def test_compute_overall_progress_stages() -> None:
    """compute_overall_progress 各阶段返回正确百分比。"""
    # login 阶段：基线 0%
    assert compute_overall_progress("login") == 0
    # discovery 阶段：5% → 25%
    assert compute_overall_progress("discovery", hashtags_completed=0, hashtags_total=10) == 5
    assert compute_overall_progress("discovery", hashtags_completed=5, hashtags_total=10) == 15
    assert compute_overall_progress("discovery", hashtags_completed=10, hashtags_total=10) == 25
    # deduplication：固定 25%
    assert compute_overall_progress("deduplication") == 25
    # exclusion：固定 30%
    assert compute_overall_progress("exclusion") == 30
    # profile_analysis：35% → 95%
    assert compute_overall_progress("profile_analysis", profiles_analyzed=0, profiles_total=100) == 35
    assert compute_overall_progress("profile_analysis", profiles_analyzed=50, profiles_total=100) == 65
    assert compute_overall_progress("profile_analysis", profiles_analyzed=100, profiles_total=100) == 95
    # export：固定 95%
    assert compute_overall_progress("export") == 95
    # completed：100%
    assert compute_overall_progress("completed") == 100


def test_compute_overall_progress_unknown_stage() -> None:
    """未知阶段返回 0%。"""
    assert compute_overall_progress("unknown") == 0


# ---------- SearchService 集成：进度持久化端到端 ----------


def test_search_service_persists_progress_to_db(tmp_path: Path, monkeypatch) -> None:
    """SearchService dry-run 任务结束后，tasks 表应有完整的进度数据。"""
    from app.config import build_settings
    from app.services.domain import SearchConfig
    from app.services.search_service import SearchService

    # 准备 settings：使用临时数据库
    cli_overrides = {
        "checkpoint": {"database_file": str(tmp_path / "test.db")},
        "discovery": {"max_profiles_to_analyze": 5, "media_per_hashtag": 5},
        "output": {"directory": str(tmp_path / "output"), "formats": ["json"]},
    }
    settings = build_settings(cli_overrides=cli_overrides)
    # 让 settings.config_dir 仍指向真实 config 目录（dry-run 需要 fake_client 加载示例数据）
    settings.config_dir = Path("config")

    config = SearchConfig(
        settings=settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    service = SearchService()
    result = service.run(config)

    assert result.status.value == "completed"

    # 从数据库验证进度已持久化
    db = Database(settings.checkpoint.database_file)
    try:
        with db.get_session() as session:
            latest = get_latest_task(session)
            assert latest is not None
            assert latest.task_id == result.task_id
            assert latest.status == "completed"
            assert latest.stage == "completed"
            assert latest.overall_progress == 100
            # 应有候选发现数据（dry-run fake_client 会返回示例账号）
            assert latest.hashtags_total >= 1
            assert latest.progress_updated_at is not None
    finally:
        db.close()


def test_progress_persists_across_db_reopen(tmp_path: Path) -> None:
    """进度写入后，关闭并重新打开数据库，进度数据应仍然存在。"""
    db_file = tmp_path / "test.db"
    db1 = Database(db_file)
    with db1.get_session() as session:
        upsert_task(session, "persistent-task", status="running")
        update_task_progress(
            session,
            "persistent-task",
            stage="profile_analysis",
            current_username="alice",
            profiles_analyzed=10,
            profiles_total=50,
            overall_progress=47,
        )
    db1.close()

    # 模拟 GUI 重启：重新打开数据库
    db2 = Database(db_file)
    with db2.get_session() as session:
        latest = get_latest_task(session)
        assert latest is not None
        assert latest.task_id == "persistent-task"
        assert latest.stage == "profile_analysis"
        assert latest.current_username == "alice"
        assert latest.profiles_analyzed == 10
        assert latest.profiles_total == 50
        assert latest.overall_progress == 47
    db2.close()
