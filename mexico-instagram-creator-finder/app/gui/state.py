"""GUI 共享状态管理。

负责：
- 加载 Settings（与 CLI 共用同一份配置文件）
- 在后台线程运行 SearchService
- 通过 latest_progress 字段向 UI 暴露实时进度
- 管理 CancellationToken（启动/停止按钮共用）
- 缓存最近一次 SearchResult

线程模型：
- UI 在主线程（NiceGUI 基于 asyncio + socketio）
- SearchService.run() 在后台线程（避免阻塞事件循环）
- progress_callback 在后台线程中被调用 → 写入 latest_progress（加锁）
- UI 通过 ui.timer 定时拉取 latest_progress 更新显示
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from app.config import Settings, build_settings
from app.logging_config import get_logger, setup_logging
from app.services import SearchService
from app.services.domain import (
    CancellationToken,
    SearchConfig,
    SearchProgress,
    SearchResult,
    TaskStatus,
)

logger = get_logger("gui.state")
setup_logging(log_file="logs/app.log")


@dataclass
class GuiState:
    """GUI 全局状态单例。

    所有页面共享同一个实例（通过 app.gui import gui_state）。
    """

    settings: Settings = field(default_factory=build_settings)
    # 后台任务
    _thread: threading.Thread | None = None
    _token: CancellationToken | None = None
    # 进度共享（线程安全）
    _lock: threading.Lock = field(default_factory=threading.Lock)
    latest_progress: SearchProgress | None = None
    latest_result: SearchResult | None = None
    # 历史 progress 用于「任务进度」页面显示日志
    progress_log: list[SearchProgress] = field(default_factory=list)
    # 错误消息（启动失败等）
    last_error: str | None = None
    # 运行起始时间（用于显示已用时长）
    started_at: float | None = None
    active_extension_task_id: str | None = None

    @property
    def is_running(self) -> bool:
        """是否有搜索任务正在运行。"""
        return self._thread is not None and self._thread.is_alive()

    def reload_settings(self) -> None:
        """重新加载配置（设置页面修改后调用）。"""
        self.settings = build_settings()

    def start_search(
        self,
        hashtags: list[str],
        dry_run: bool = False,
        resume: bool = False,
        reset_task: bool = False,
    ) -> tuple[bool, str]:
        """启动搜索任务。

        Returns:
            (success, message)
        """
        if self.is_running:
            return False, "已有任务正在运行"

        # 重置状态
        with self._lock:
            self.latest_progress = None
            self.latest_result = None
            self.progress_log.clear()
            self.last_error = None
            self.started_at = time.time()

        # 校验凭据（非 dry-run 模式不再支持 instagrapi 登录）
        if not dry_run:
            return False, (
                "非 dry-run 模式不再支持 instagrapi 移动端 API 登录。"
                "请使用浏览器扩展采集数据，或开启 DRY-RUN 模式测试流程。"
            )

        # 创建令牌
        self._token = CancellationToken()

        # 创建配置（克隆 settings 避免被后台线程修改）
        config = SearchConfig(
            settings=self.settings,
            hashtags=hashtags,
            dry_run=dry_run,
            resume=resume,
            reset_task=reset_task,
        )

        # 启动后台线程
        self._thread = threading.Thread(
            target=self._run_in_background,
            args=(config, self._token),
            daemon=True,
            name="search-service",
        )
        self._thread.start()
        logger.info("search started: hashtags=%s dry_run=%s", hashtags, dry_run)
        return True, f"任务已启动（hashtags={len(hashtags)}, dry_run={dry_run}）"

    def stop_search(self) -> tuple[bool, str]:
        """请求停止当前任务（协作式取消）。"""
        if not self.is_running and self.active_extension_task_id:
            from app.extension.task_service import ExtensionTaskService

            task_id = self.active_extension_task_id
            ExtensionTaskService(settings=self.settings).control(task_id, "stop")
            self.active_extension_task_id = None
            logger.info("extension task stopped: %s", task_id)
            return True, "扩展发现任务已停止，已完成的数据仍然保留"
        if not self.is_running or self._token is None:
            return False, "当前无运行中的任务"
        self._token.cancel()
        logger.info("cancellation requested")
        return True, "已请求停止，正在保存断点..."

    def _run_in_background(self, config: SearchConfig, token: CancellationToken) -> None:
        """后台线程入口：运行 SearchService.run()。"""
        try:

            def on_progress(p: SearchProgress) -> None:
                with self._lock:
                    self.latest_progress = p
                    # 限制日志长度
                    if len(self.progress_log) >= 200:
                        self.progress_log = self.progress_log[-150:]
                    self.progress_log.append(p)

            result = SearchService().run(config, progress_callback=on_progress, cancellation_token=token)
            with self._lock:
                self.latest_result = result
        except Exception as e:  # noqa: BLE001
            logger.exception("search failed")
            with self._lock:
                self.last_error = str(e)
                self.latest_result = SearchResult(
                    task_id="",
                    status=TaskStatus.FAILED,
                    stop_reason=str(e),
                )

    def elapsed_seconds(self) -> float | None:
        """已运行秒数（未运行时返回 None）。"""
        if self.started_at is None:
            return None
        if self.is_running:
            return time.time() - self.started_at
        return None

    def wait_for_completion(self, timeout: float = 30.0) -> bool:
        """等待任务完成（用于测试）。"""
        if self._thread is None:
            return True
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()


# 全局单例
gui_state = GuiState()
