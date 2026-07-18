"""断点续传测试。

覆盖 app/storage/checkpoint.py：
- save_checkpoint / load_checkpoint
- reset_task
- is_user_analyzed / mark_usernames_analyzed
- mark_hashtag_completed
- record_failed_username
- update_status
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.models import TaskCheckpoint
from app.storage.checkpoint import (
    is_user_analyzed,
    load_checkpoint,
    mark_hashtag_completed,
    mark_usernames_analyzed,
    record_failed_username,
    reset_task,
    save_checkpoint,
    update_status,
)
from app.storage.database import Database

TASK_ID = "test-task-001"


def _now() -> datetime:
    return datetime.now(UTC)


def _make_checkpoint(
    *,
    task_id: str = TASK_ID,
    status: str = "running",
) -> TaskCheckpoint:
    return TaskCheckpoint(
        task_id=task_id,
        status=status,
        completed_hashtags=["perfumemexico"],
        discovered_usernames=["alice", "bob"],
        analyzed_usernames=["alice"],
        failed_usernames=[],
        failed_reasons={},
        stop_reason=None,
        started_at=_now(),
        updated_at=_now(),
        completed_at=None,
    )


# ---------- save / load roundtrip ----------


def test_save_and_load_checkpoint(tmp_path: Path) -> None:
    """保存后加载，字段一致。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        cp = _make_checkpoint()
        save_checkpoint(session, cp)

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.task_id == TASK_ID
        assert loaded.status == "running"
        assert loaded.completed_hashtags == ["perfumemexico"]
        assert loaded.discovered_usernames == ["alice", "bob"]
        assert loaded.analyzed_usernames == ["alice"]
        assert loaded.started_at is not None
    db.close()


def test_load_checkpoint_not_found(tmp_path: Path) -> None:
    """加载不存在的 task 返回 None。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        loaded = load_checkpoint(session, "nonexistent")
        assert loaded is None
    db.close()


def test_save_checkpoint_updates_existing(tmp_path: Path) -> None:
    """保存相同 task_id 更新已有记录。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        cp1 = _make_checkpoint(status="running")
        save_checkpoint(session, cp1)

        cp2 = _make_checkpoint(status="completed")
        cp2.completed_at = _now()
        save_checkpoint(session, cp2)

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.status == "completed"
    db.close()


# ---------- is_user_analyzed / mark_usernames_analyzed ----------


def test_mark_and_is_user_analyzed(tmp_path: Path) -> None:
    """mark_usernames_analyzed 后 is_user_analyzed 返回 True。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        # 先保存初始 checkpoint
        save_checkpoint(session, _make_checkpoint())

        mark_usernames_analyzed(session, TASK_ID, ["charlie", "dave"])

        assert is_user_analyzed(session, TASK_ID, "charlie") is True
        assert is_user_analyzed(session, TASK_ID, "dave") is True
        assert is_user_analyzed(session, TASK_ID, "unknown") is False
    db.close()


def test_is_user_analyzed_no_checkpoint(tmp_path: Path) -> None:
    """无 checkpoint 时 is_user_analyzed 返回 False。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        assert is_user_analyzed(session, TASK_ID, "alice") is False
    db.close()


def test_mark_usernames_analyzed_case_insensitive(tmp_path: Path) -> None:
    """大小写不敏感（mark "UserName" 后 is_analyzed("username") 为 True）。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        mark_usernames_analyzed(session, TASK_ID, ["UserName"])

        assert is_user_analyzed(session, TASK_ID, "username") is True
        assert is_user_analyzed(session, TASK_ID, "USERNAME") is True
        assert is_user_analyzed(session, TASK_ID, "UserName") is True
    db.close()


def test_mark_usernames_analyzed_creates_checkpoint_if_absent(tmp_path: Path) -> None:
    """无 checkpoint 时 mark_usernames_analyzed 自动创建。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        # 不预先 save_checkpoint
        mark_usernames_analyzed(session, TASK_ID, ["alice"])

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert "alice" in loaded.analyzed_usernames
    db.close()


# ---------- mark_hashtag_completed ----------


def test_mark_hashtag_completed(tmp_path: Path) -> None:
    """mark_hashtag_completed 后 completed_hashtags 包含该 Hashtag。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        mark_hashtag_completed(session, TASK_ID, "beautymexico")

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert "beautymexico" in loaded.completed_hashtags
        # 原 hashtag 仍存在
        assert "perfumemexico" in loaded.completed_hashtags
    db.close()


def test_mark_hashtag_completed_no_duplicate(tmp_path: Path) -> None:
    """重复标记同一 Hashtag 不重复添加。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        mark_hashtag_completed(session, TASK_ID, "perfumemexico")

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.completed_hashtags.count("perfumemexico") == 1
    db.close()


def test_mark_hashtag_completed_creates_checkpoint_if_absent(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        mark_hashtag_completed(session, TASK_ID, "newtag")
        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert "newtag" in loaded.completed_hashtags
    db.close()


# ---------- record_failed_username ----------


def test_record_failed_username(tmp_path: Path) -> None:
    """record_failed_username 后 failed_usernames/failed_reasons 包含。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        record_failed_username(session, TASK_ID, "failed_user", "network error")

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert "failed_user" in loaded.failed_usernames
        assert loaded.failed_reasons["failed_user"] == "network error"
    db.close()


def test_record_failed_username_no_duplicate(tmp_path: Path) -> None:
    """重复记录同一失败用户名不重复添加。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        record_failed_username(session, TASK_ID, "failed_user", "error1")
        record_failed_username(session, TASK_ID, "failed_user", "error2")

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.failed_usernames.count("failed_user") == 1
        # reasons 应被最后一条覆盖
        assert loaded.failed_reasons["failed_user"] == "error2"
    db.close()


# ---------- update_status ----------


def test_update_status_to_completed(tmp_path: Path) -> None:
    """update_status 到 completed 后 completed_at 非空。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        update_status(session, TASK_ID, "completed")

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.status == "completed"
        assert loaded.completed_at is not None
    db.close()


def test_update_status_to_stopped(tmp_path: Path) -> None:
    """update_status 到 stopped 后 completed_at 非空。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        update_status(session, TASK_ID, "stopped", stop_reason="rate_limit")

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.status == "stopped"
        assert loaded.completed_at is not None
        assert loaded.stop_reason == "rate_limit"
    db.close()


def test_update_status_to_running_no_completed_at(tmp_path: Path) -> None:
    """update_status 到 running 不设置 completed_at。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        update_status(session, TASK_ID, "running")

        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.status == "running"
        # running 不应设置 completed_at
        assert loaded.completed_at is None
    db.close()


def test_update_status_creates_checkpoint_if_absent(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        update_status(session, TASK_ID, "running")
        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.status == "running"
    db.close()


# ---------- reset_task ----------


def test_reset_task(tmp_path: Path) -> None:
    """reset_task 后 load_checkpoint 返回 None。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        assert load_checkpoint(session, TASK_ID) is not None

        reset_task(session, TASK_ID)

        assert load_checkpoint(session, TASK_ID) is None
    db.close()


def test_reset_task_idempotent(tmp_path: Path) -> None:
    """reset_task 不存在的 task 不抛错。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        # 不应抛异常
        reset_task(session, "nonexistent")
    db.close()


# ---------- 综合场景 ----------


def test_full_workflow(tmp_path: Path) -> None:
    """完整断点续传工作流。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        # 1. 创建任务
        update_status(session, TASK_ID, "running")

        # 2. 标记 hashtag 完成
        mark_hashtag_completed(session, TASK_ID, "perfumemexico")
        mark_hashtag_completed(session, TASK_ID, "beautymexico")

        # 3. 标记已分析用户名
        mark_usernames_analyzed(session, TASK_ID, ["alice", "bob"])

        # 4. 记录失败
        record_failed_username(session, TASK_ID, "charlie", "private account")

        # 5. 加载断点
        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.status == "running"
        assert "perfumemexico" in loaded.completed_hashtags
        assert "beautymexico" in loaded.completed_hashtags
        assert "alice" in loaded.analyzed_usernames
        assert "bob" in loaded.analyzed_usernames
        assert "charlie" in loaded.failed_usernames
        assert loaded.failed_reasons["charlie"] == "private account"

        # 6. 完成任务
        update_status(session, TASK_ID, "completed")
        loaded = load_checkpoint(session, TASK_ID)
        assert loaded is not None
        assert loaded.status == "completed"
        assert loaded.completed_at is not None
    db.close()


def test_resume_skips_analyzed_users(tmp_path: Path) -> None:
    """恢复任务时跳过已分析账号。"""
    db = Database(tmp_path / "test.db")
    with db.get_session() as session:
        save_checkpoint(session, _make_checkpoint())
        mark_usernames_analyzed(session, TASK_ID, ["alice", "bob", "charlie"])

        # 模拟恢复：检查是否已分析
        assert is_user_analyzed(session, TASK_ID, "alice")
        assert is_user_analyzed(session, TASK_ID, "bob")
        assert is_user_analyzed(session, TASK_ID, "charlie")
        assert not is_user_analyzed(session, TASK_ID, "dave")
    db.close()
