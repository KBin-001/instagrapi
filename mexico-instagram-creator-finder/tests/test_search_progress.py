"""SearchProgress 与 SearchResult 数据模型测试。"""

from __future__ import annotations

from app.services.domain import (
    STAGE_DISCOVERY,
    STAGE_LOGIN,
    STAGE_PROFILE_ANALYSIS,
    SearchProgress,
    SearchResult,
    TaskStatus,
)


def test_search_progress_defaults() -> None:
    p = SearchProgress()
    assert p.stage == ""
    assert p.current_hashtag is None
    assert p.hashtags_completed == 0
    assert p.hashtags_total == 0
    assert p.candidates_found == 0
    assert p.profiles_total == 0
    assert p.profiles_analyzed == 0
    assert p.profiles_matched == 0
    assert p.profiles_skipped == 0
    assert p.profiles_failed == 0
    assert p.current_username is None
    assert p.message == ""
    assert p.timestamp is not None


def test_search_progress_with_values() -> None:
    p = SearchProgress(
        stage=STAGE_DISCOVERY,
        current_hashtag="perfumemexico",
        hashtags_completed=3,
        hashtags_total=15,
        candidates_found=42,
        message="完成 #perfumemexico，发现 28 个账号",
    )
    assert p.stage == STAGE_DISCOVERY
    assert p.current_hashtag == "perfumemexico"
    assert p.hashtags_completed == 3
    assert p.hashtags_total == 15
    assert p.candidates_found == 42


def test_search_progress_stage_constants() -> None:
    """阶段常量应为非空字符串。"""
    assert STAGE_LOGIN
    assert STAGE_DISCOVERY
    assert STAGE_PROFILE_ANALYSIS
    assert STAGE_LOGIN != STAGE_DISCOVERY
    assert STAGE_DISCOVERY != STAGE_PROFILE_ANALYSIS


def test_task_status_enum_values() -> None:
    """TaskStatus 枚举值应与现有数据库字符串兼容。"""
    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.RUNNING == "running"
    assert TaskStatus.STOPPING == "stopping"
    assert TaskStatus.STOPPED == "stopped"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"
    assert TaskStatus.RATE_LIMITED == "rate_limited"
    assert TaskStatus.VERIFICATION_REQUIRED == "verification_required"


def test_task_status_is_string() -> None:
    """TaskStatus 继承 StrEnum，应可直接当字符串使用。"""
    status = TaskStatus.RUNNING
    assert isinstance(status, str)
    assert status == "running"
    # 与字符串比较
    assert TaskStatus.COMPLETED in ("completed", "stopped")


def test_search_result_defaults() -> None:
    r = SearchResult(task_id="task_123", status=TaskStatus.COMPLETED)
    assert r.task_id == "task_123"
    assert r.status == TaskStatus.COMPLETED
    assert r.records_count == 0
    assert r.exported_files == {}
    assert r.stop_reason is None


def test_search_result_with_exported_files() -> None:
    r = SearchResult(
        task_id="task_456",
        status=TaskStatus.COMPLETED,
        records_count=10,
        exported_files={"csv": "/path/a.csv", "json": "/path/a.json"},
    )
    assert r.records_count == 10
    assert r.exported_files["csv"] == "/path/a.csv"
    assert r.exported_files["json"] == "/path/a.json"


def test_search_result_stopped_with_reason() -> None:
    r = SearchResult(
        task_id="task_789",
        status=TaskStatus.STOPPED,
        stop_reason="用户取消",
    )
    assert r.status == TaskStatus.STOPPED
    assert r.stop_reason == "用户取消"
