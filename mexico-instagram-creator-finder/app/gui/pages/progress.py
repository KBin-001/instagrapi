"""任务进度页面：6 指标卡片 + 总体进度条 + 从 SQLite 恢复状态。

进度数据必须持久化到 SQLite，不依赖浏览器内存或 WebSocket 连接：
- 页面刷新：从 SQLite 重新加载最新 task 行
- WebSocket 重连：定时查询 SQLite，自动恢复
- 用户切换页面：回到本页时从 SQLite 取最新状态
- GUI 重启：启动时从 SQLite 取最近 task 显示

显示六个核心指标：
  总体进度 / 当前阶段 / 当前账号 / 当前 Hashtag / 发现候选 / 去重后
  已分析 / 符合条件 / 已跳过 / 失败
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from nicegui import ui

from app.gui.state import gui_state
from app.services.domain import (
    STAGE_COMPLETED,
    STAGE_DEDUPLICATION,
    STAGE_DISCOVERY,
    STAGE_EXCLUSION,
    STAGE_EXPORT,
    STAGE_LOGIN,
    STAGE_PROFILE_ANALYSIS,
)

# 阶段中文名
_STAGE_LABELS: dict[str, str] = {
    STAGE_LOGIN: "登录",
    STAGE_DISCOVERY: "发现候选",
    STAGE_DEDUPLICATION: "去重",
    STAGE_EXCLUSION: "应用排除",
    STAGE_PROFILE_ANALYSIS: "账号分析",
    "profile_enrichment": "主页补全",
    "media_analysis": "媒体分析",
    STAGE_EXPORT: "导出",
    STAGE_COMPLETED: "完成",
}

# 状态中文映射
_STATUS_LABELS: dict[str, str] = {
    "pending": "等待中",
    "running": "运行中",
    "paused": "已暂停",
    "stopping": "正在停止",
    "stopped": "已停止",
    "completed": "已完成",
    "failed": "失败",
    "rate_limited": "被限流",
    "verification_required": "需验证",
    "waiting_extension": "等待扩展",
    "safe_stopped": "安全停止",
}


def _fmt_elapsed(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "-"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _fmt_dt(dt: Any) -> str:
    if dt is None:
        return "-"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)


def _load_latest_task() -> Any | None:
    """从 SQLite 读取最近更新的 task 行。

    即使 GUI 刚启动 / 页面刚刷新，也能从这里恢复最新状态。
    """
    try:
        from app.storage.database import Database
        from app.storage.repositories import get_latest_task

        db = Database(gui_state.settings.checkpoint.database_file)
        try:
            session = db.get_session()
            try:
                return get_latest_task(session)
            finally:
                session.close()
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - UI 容错
        return None


def _load_recent_logs(limit: int = 50) -> list[str]:
    """从 gui_state 内存读取最近日志（仅用于辅助显示）。"""
    with gui_state._lock:  # noqa: SLF001
        items = list(gui_state.progress_log[-limit:])
    lines: list[str] = []
    for item in items:
        ts = item.timestamp.strftime("%H:%M:%S") if isinstance(item.timestamp, datetime) else ""
        stage_zh = _STAGE_LABELS.get(item.stage, item.stage or "")
        lines.append(f"[{ts}] {stage_zh} | {item.message}")
    return lines


def build_progress_page() -> None:
    """构建「搜索任务」页面 UI。"""
    ui.label("实时显示当前任务的进度指标。数据持久化到 SQLite，刷新或重启后自动恢复。").classes(
        "text-grey-7 text-sm mb-4"
    )

    # ===== 顶部状态卡 =====
    with ui.card().classes("w-full mb-3 status-card"):
        with ui.row().classes("w-full items-center"):
            status_dot = ui.html('<span class="dot"></span>').classes("status-dot")
            status_label = ui.label("● 空闲").classes("text-lg font-bold text-grey-7")
            ui.space()
            task_id_label = ui.label("任务 ID：-").classes("text-grey-7 text-sm")
            elapsed_label = ui.label("已用时：-").classes("text-grey-7 text-sm ml-4")

        with ui.row().classes("w-full mt-1"):
            stop_reason_label = ui.label("").classes("text-red-7 text-sm")

    # ===== 总体进度卡 =====
    with ui.card().classes("w-full mb-3 progress-card"):
        with ui.row().classes("w-full items-center"):
            ui.label("总体进度").classes("font-bold text-green-8")
            ui.space()
            overall_label = ui.label("0%").classes("text-2xl font-bold text-green-8")

        progress_bar = ui.linear_progress(value=0).props("color=green-8 size=12px").classes("w-full mt-1")
        overall_hint = ui.label("").classes("text-grey-7 text-xs mt-1")

    # ===== 当前阶段信息（3 列）=====
    with ui.row().classes("w-full gap-3 mb-3 flex-wrap"):
        with ui.card().classes("metric-card flex-1 min-w-200"):
            ui.label("当前阶段").classes("metric-label")
            stage_label = ui.label("-").classes("metric-value")
        with ui.card().classes("metric-card flex-1 min-w-200"):
            ui.label("当前账号").classes("metric-label")
            current_username_label = ui.label("-").classes("metric-value text-green-8")
        with ui.card().classes("metric-card flex-1 min-w-200"):
            ui.label("当前 Hashtag").classes("metric-label")
            current_hashtag_label = ui.label("-").classes("metric-value text-green-8")

    # ===== 6 指标网格（用户指定）=====
    ui.label("账号统计").classes("section-label mt-2")
    with ui.row().classes("w-full gap-3 mb-3 flex-wrap"):
        # 第一行：发现 / 去重 / 已分析
        with ui.card().classes("metric-card flex-1 min-w-180"):
            ui.label("发现候选").classes("metric-label")
            candidates_found_label = ui.label("0").classes("metric-value-large text-blue-8")
        with ui.card().classes("metric-card flex-1 min-w-180"):
            ui.label("去重后").classes("metric-label")
            candidates_kept_label = ui.label("0").classes("metric-value-large text-blue-8")
        with ui.card().classes("metric-card flex-1 min-w-180"):
            ui.label("已分析").classes("metric-label")
            analyzed_label = ui.label("0 / 0").classes("metric-value-large text-orange-8")

        # 第二行：符合 / 跳过 / 失败
        with ui.card().classes("metric-card flex-1 min-w-180"):
            ui.label("符合条件").classes("metric-label")
            matched_label = ui.label("0").classes("metric-value-large text-green-8")
        with ui.card().classes("metric-card flex-1 min-w-180"):
            ui.label("已跳过").classes("metric-label")
            skipped_label = ui.label("0").classes("metric-value-large text-grey-8")
        with ui.card().classes("metric-card flex-1 min-w-180"):
            ui.label("失败").classes("metric-label")
            failed_label = ui.label("0").classes("metric-value-large text-red-8")

    # ===== Hashtag 进度（次要）=====
    with ui.card().classes("w-full mb-3 hashtag-progress-card"):
        with ui.row().classes("w-full items-center"):
            ui.label("Hashtag 进度").classes("font-bold text-grey-8")
            ui.space()
            hashtag_progress_label = ui.label("0 / 0").classes("text-grey-7 text-sm")
        hashtag_progress_bar = ui.linear_progress(value=0).props("color=blue-6 size=8px").classes("w-full mt-1")

    # ===== 操作 =====
    with ui.row().classes("w-full justify-end items-center gap-2 mb-3"):
        refresh_btn = ui.button("刷新", icon="refresh").props("flat dense color=green-8")
        stop_btn = ui.button("安全停止任务", icon="stop_circle", color="red-5").props("unelevinated")
        stop_btn.set_enabled(False)

    # ===== 事件日志（折叠）=====
    with ui.expansion("事件日志", icon="list").classes("w-full mb-3").props("dense"):
        log_area = ui.log(max_lines=200).classes("w-full h-48").props("outlined")

    # ===== 任务详情（折叠）=====
    with ui.expansion("任务详情", icon="info").classes("w-full mb-3").props("dense"):
        detail_container = ui.column().classes("w-full")

    # ===== 提示 =====
    ui.label(
        "• 进度数据持久化到 SQLite，页面刷新 / WebSocket 重连 / GUI 重启后会自动恢复。\n"
        "• 任务运行中点击「安全停止任务」会保存断点并安全退出。\n"
        "• 已停止的任务可通过「新建搜索」页面勾选「恢复上次任务」继续。"
    ).classes("text-grey-7 text-xs whitespace-pre-wrap mt-2")

    # ===== 状态变量 =====
    state = {
        "last_log_count": 0,
        "last_progress_updated_at": None,
    }

    def _set_status(status_text: str, color: str, dot_color: str) -> None:
        status_label.text = f"● {status_text}"
        status_label.classes(replace=f"text-lg font-bold {color}")
        status_dot.classes(replace=f"status-dot {dot_color}")

    def _render_detail(task: Any) -> None:
        """渲染任务详情折叠面板。"""
        detail_container.clear()
        with detail_container:
            if task is None:
                ui.label("（无任务）").classes("text-grey-7 italic")
                return
            rows = [
                ("任务 ID", task.task_id),
                ("状态", _STATUS_LABELS.get(task.status, task.status)),
                ("开始时间", _fmt_dt(task.started_at)),
                ("最后更新", _fmt_dt(task.progress_updated_at or task.updated_at)),
                ("完成时间", _fmt_dt(task.completed_at)),
                ("停止原因", task.stop_reason or "-"),
            ]
            for label, value in rows:
                with ui.row().classes("w-full items-start"):
                    ui.label(label).classes("text-grey-6 text-sm w-24")
                    ui.label(str(value)).classes("text-grey-8 text-sm flex-1")

    def _refresh_from_db() -> None:
        """从 SQLite 读取最新任务并刷新 UI。"""
        task = _load_latest_task()
        is_running = gui_state.is_running

        # 已用时
        elapsed = gui_state.elapsed_seconds()
        if elapsed is None and task is not None and task.started_at is not None and task.status == "running":
            # GUI 重启后 gui_state.started_at 可能丢失，用 task.started_at 估算
            now = datetime.now(task.started_at.tzinfo) if task.started_at.tzinfo else datetime.now()
            elapsed = (now - task.started_at).total_seconds()
        elapsed_label.text = f"已用时：{_fmt_elapsed(elapsed)}"

        if task is None:
            _set_status("空闲", "text-grey-7", "")
            task_id_label.text = "任务 ID：-"
            stop_reason_label.text = ""
            stop_btn.disable()
            return

        # 任务 ID
        task_id_label.text = f"任务 ID：{task.task_id}"

        # 状态
        status = task.status or "pending"
        if is_running and status == "running":
            _set_status("搜索中", "text-orange-7", "running")
        elif status == "completed":
            _set_status("已完成", "text-green-7", "")
        elif status == "failed":
            _set_status("失败", "text-red-7", "error")
        elif status == "stopped":
            _set_status("已停止", "text-grey-7", "")
        elif status == "rate_limited":
            _set_status("被限流", "text-red-7", "error")
        elif status == "verification_required":
            _set_status("需验证", "text-amber-7", "error")
        else:
            _set_status(_STATUS_LABELS.get(status, status), "text-grey-7", "")

        # 停止原因
        stop_reason_label.text = f"停止原因：{task.stop_reason}" if task.stop_reason else ""

        # 总体进度
        overall = int(task.overall_progress or 0)
        overall_label.text = f"{overall}%"
        progress_bar.value = overall / 100.0
        stage_zh = _STAGE_LABELS.get(task.stage or "", task.stage or "-")
        overall_hint.text = f"阶段：{stage_zh}"

        # 当前阶段 / 账号 / Hashtag
        stage_label.text = stage_zh
        current_username_label.text = f"@{task.current_username}" if task.current_username else "-"
        current_hashtag_label.text = f"#{task.current_hashtag}" if task.current_hashtag else "-"

        # 6 指标
        candidates_found_label.text = str(task.candidates_found or 0)
        candidates_kept_label.text = str(task.candidates_kept or 0)
        analyzed = int(task.profiles_analyzed or 0)
        total = int(task.profiles_total or 0)
        analyzed_label.text = f"{analyzed} / {total}"
        matched_label.text = str(task.profiles_matched or 0)
        skipped_label.text = str(task.profiles_skipped or 0)
        failed_label.text = str(task.profiles_failed or 0)

        # Hashtag 进度
        ht_done = int(task.hashtags_completed or 0)
        ht_total = int(task.hashtags_total or 0)
        hashtag_progress_label.text = f"{ht_done} / {ht_total}"
        hashtag_progress_bar.value = (ht_done / ht_total) if ht_total > 0 else 0

        # 停止按钮：仅在任务运行中可点
        if is_running:
            stop_btn.enable()
        else:
            stop_btn.disable()

        # 详情面板：只在 task_id 或 progress_updated_at 变化时重建
        key = (task.task_id, str(task.progress_updated_at))
        if key != state["last_progress_updated_at"]:
            state["last_progress_updated_at"] = key
            _render_detail(task)

    def _refresh_logs() -> None:
        """从 gui_state 内存读取最新日志，增量推送到 log_area。"""
        with gui_state._lock:  # noqa: SLF001
            total = len(gui_state.progress_log)
            new_items = list(gui_state.progress_log[state["last_log_count"] :])
        state["last_log_count"] = total
        for item in new_items:
            ts = item.timestamp.strftime("%H:%M:%S") if isinstance(item.timestamp, datetime) else ""
            stage_zh = _STAGE_LABELS.get(item.stage, item.stage or "")
            log_area.push(f"[{ts}] {stage_zh} | {item.message}")

    def refresh() -> None:
        _refresh_from_db()
        _refresh_logs()

    # 刷新频率：1 秒（SQLite 单行查询足够轻量）
    ui.timer(1.0, refresh)
    # 首次立即刷新
    refresh()

    # 按钮事件
    refresh_btn.on("click", lambda _: refresh())

    def on_stop() -> None:
        ok, msg = gui_state.stop_search()
        ui.notify(msg, type=("positive" if ok else "warning"), position="top")
        # 立即刷新一次
        refresh()

    stop_btn.on("click", lambda _: on_stop())
