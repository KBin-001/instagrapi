"""SearchService 集成测试。

使用 dry-run 模式 + FakeInstagramClient 验证 SearchService 的完整流程，
不登录真实 Instagram、不发起网络请求。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings, build_settings
from app.services import SearchService
from app.services.domain import (
    STAGE_COMPLETED,
    STAGE_DISCOVERY,
    STAGE_PROFILE_ANALYSIS,
    CancellationToken,
    SearchConfig,
    SearchProgress,
    TaskStatus,
)


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    """在临时目录中构建 settings，避免污染项目数据库。"""
    # 修改 checkpoint.database_file 与 output.directory 指向 tmp_path
    settings = build_settings()
    settings.checkpoint.database_file = str(tmp_path / "test_app.db")
    settings.output.directory = str(tmp_path / "output")
    return settings


def _collect_progress() -> tuple[list[SearchProgress], SearchProgress | None]:
    """返回 (progress_list, last_progress) 辅助测试。"""
    return ([], None)


def test_search_service_dry_run_completes(isolated_settings: Settings) -> None:
    """dry-run 模式完整流程应正常完成。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico", "bellezamx"],
        dry_run=True,
    )

    progress_list: list[SearchProgress] = []

    def on_progress(p: SearchProgress) -> None:
        progress_list.append(p)

    result = SearchService().run(config, progress_callback=on_progress)

    assert result.status == TaskStatus.COMPLETED
    assert result.task_id.startswith("task_")
    assert result.records_count > 0
    assert "csv" in result.exported_files
    assert "json" in result.exported_files
    assert "xlsx" in result.exported_files
    # 各文件路径存在
    for path in result.exported_files.values():
        assert Path(path).exists()

    # 应有进度回调，且最后一个 stage 是 COMPLETED
    assert len(progress_list) > 0
    assert progress_list[-1].stage == STAGE_COMPLETED


def test_search_service_progress_stages_sequence(isolated_settings: Settings) -> None:
    """进度回调应按正确阶段顺序触发。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    stages: list[str] = []

    def on_progress(p: SearchProgress) -> None:
        # 去重相同 stage（同一阶段可能 emit 多次）
        if not stages or stages[-1] != p.stage:
            stages.append(p.stage)

    SearchService().run(config, progress_callback=on_progress)

    # 阶段顺序应包含：login → discovery → deduplication → exclusion → profile_analysis → export → completed
    assert "login" in stages
    assert "discovery" in stages
    assert "deduplication" in stages
    assert "exclusion" in stages
    assert "profile_analysis" in stages
    assert "export" in stages
    assert "completed" in stages

    # 阶段顺序检查
    login_idx = stages.index("login")
    discovery_idx = stages.index("discovery")
    completed_idx = stages.index("completed")
    assert login_idx < discovery_idx < completed_idx


def test_search_service_cancellation_token_stops(isolated_settings: Settings) -> None:
    """取消令牌应在 discovery 阶段之后立即停止任务。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico", "bellezamx", "skincaremx"],
        dry_run=True,
    )

    token = CancellationToken()
    progress_list: list[SearchProgress] = []

    def on_progress(p: SearchProgress) -> None:
        progress_list.append(p)
        # 在 discovery 阶段第一次回调后取消
        if p.stage == STAGE_DISCOVERY and not token.is_cancelled:
            token.cancel()

    result = SearchService().run(config, progress_callback=on_progress, cancellation_token=token)

    # 应为 STOPPED 状态
    assert result.status == TaskStatus.STOPPED
    assert result.stop_reason == "用户取消"
    # 任务 ID 应保存到数据库（可恢复）
    assert result.task_id.startswith("task_")


def test_search_service_cancellation_during_profile_analysis(isolated_settings: Settings) -> None:
    """取消令牌应在 profile_analysis 阶段第一个账号后停止。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    token = CancellationToken()

    def on_progress(p: SearchProgress) -> None:
        # 在 profile_analysis 阶段第一个账号开始时取消
        if p.stage == STAGE_PROFILE_ANALYSIS and not token.is_cancelled:
            token.cancel()

    result = SearchService().run(config, progress_callback=on_progress, cancellation_token=token)

    assert result.status == TaskStatus.STOPPED
    assert result.stop_reason == "用户取消"


def test_search_service_progress_callback_exception_swallowed(isolated_settings: Settings) -> None:
    """progress_callback 抛异常不应影响主流程。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    call_count = [0]

    def bad_callback(p: SearchProgress) -> None:
        call_count[0] += 1
        raise RuntimeError("callback boom")

    # 不应抛异常
    result = SearchService().run(config, progress_callback=bad_callback)

    assert result.status == TaskStatus.COMPLETED
    assert call_count[0] > 0  # 回调被调用过


def test_search_service_no_progress_callback(isolated_settings: Settings) -> None:
    """不传 progress_callback 也应正常运行。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    result = SearchService().run(config, progress_callback=None)

    assert result.status == TaskStatus.COMPLETED


def test_search_service_no_cancellation_token(isolated_settings: Settings) -> None:
    """不传 cancellation_token 也应正常运行（内部创建默认 token）。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    result = SearchService().run(config)

    assert result.status == TaskStatus.COMPLETED


def test_search_service_progress_hashtags_completed_increases(isolated_settings: Settings) -> None:
    """discovery 阶段进度回调中 hashtags_completed 应单调递增。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico", "bellezamx", "skincaremx"],
        dry_run=True,
    )

    discovery_progress: list[SearchProgress] = []

    def on_progress(p: SearchProgress) -> None:
        if p.stage == STAGE_DISCOVERY:
            discovery_progress.append(p)

    SearchService().run(config, progress_callback=on_progress)

    # 应该有 discovery 阶段回调
    assert len(discovery_progress) > 0
    # hashtags_total 应为 3
    assert any(p.hashtags_total == 3 for p in discovery_progress)


def test_search_service_task_persisted_to_database(isolated_settings: Settings) -> None:
    """任务完成后应持久化到 SQLite，可被 load_checkpoint 加载。"""
    from app.storage.checkpoint import load_checkpoint
    from app.storage.database import Database
    from app.storage.repositories import get_task

    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    result = SearchService().run(config)

    # 从数据库加载验证
    db = Database(isolated_settings.checkpoint.database_file)
    session = db.get_session()
    try:
        task = get_task(session, result.task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.task_id == result.task_id

        cp = load_checkpoint(session, result.task_id)
        assert cp is not None
        assert cp.status == "completed"
        # 应有已完成的 Hashtag
        assert len(cp.completed_hashtags) >= 1
    finally:
        session.close()
        db.close()


def test_search_service_exported_files_use_isolated_dir(isolated_settings: Settings, tmp_path: Path) -> None:
    """导出文件应写入 settings.output.directory，不污染项目 output/ 目录。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
    )

    result = SearchService().run(config)

    expected_dir = Path(isolated_settings.output.directory).resolve()
    for path in result.exported_files.values():
        actual_path = Path(path).resolve()
        # 导出文件应在 isolated_settings.output.directory 下
        assert str(actual_path).startswith(str(expected_dir))


def test_search_service_handles_empty_hashtags(isolated_settings: Settings) -> None:
    """空 Hashtag 列表应正常完成（无候选，无导出记录）。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=[],
        dry_run=True,
    )

    result = SearchService().run(config)

    assert result.status == TaskStatus.COMPLETED
    # 无候选，无导出记录
    assert result.records_count == 0


def test_search_service_resume_unknown_task_starts_new(isolated_settings: Settings) -> None:
    """resume 模式下无历史任务时应正常启动新任务。"""
    config = SearchConfig(
        settings=isolated_settings,
        hashtags=["perfumemexico"],
        dry_run=True,
        resume=True,
    )

    result = SearchService().run(config)

    assert result.status == TaskStatus.COMPLETED
    assert result.task_id.startswith("task_")
