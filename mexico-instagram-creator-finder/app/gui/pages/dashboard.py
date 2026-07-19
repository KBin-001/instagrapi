"""概览页：应用首页仪表盘。

显示：
- 当前任务状态卡片
- 数据统计卡片（任务数、博主数、导出文件数）
- 快捷入口
"""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from app.config import build_settings
from app.gui.state import gui_state


def _count_tasks() -> tuple[int, str]:
    """返回 (任务总数, 最近任务状态)。"""
    from sqlalchemy import select

    from app.storage.database import Database, TaskRow

    try:
        settings = build_settings()
        db = Database(settings.checkpoint.database_file)
        session = db.get_session()
        try:
            stmt = select(TaskRow).order_by(TaskRow.updated_at.desc())
            rows = list(session.execute(stmt).scalars())
            if not rows:
                return 0, "-"
            return len(rows), rows[0].status or "unknown"
        finally:
            session.close()
            db.close()
    except Exception:  # noqa: BLE001
        return 0, "-"


def _count_creators() -> int:
    """返回已分析的博主总数（去重）。"""
    from sqlalchemy import distinct, func, select

    from app.storage.database import Database, ProfileRow

    try:
        settings = build_settings()
        db = Database(settings.checkpoint.database_file)
        session = db.get_session()
        try:
            stmt = select(func.count(distinct(ProfileRow.username)))
            return int(session.execute(stmt).scalar() or 0)
        finally:
            session.close()
            db.close()
    except Exception:  # noqa: BLE001
        return 0


def _count_exports() -> int:
    """返回导出目录中的文件数。"""
    try:
        settings = build_settings()
        out_dir = Path(settings.output.directory)
        if not out_dir.exists():
            return 0
        return sum(1 for _ in out_dir.glob("*") if _.is_file())
    except Exception:  # noqa: BLE001
        return 0


def _stat_card(icon: str, icon_color: str, label: str, value: str, sub: str = "") -> None:
    """单个统计卡片。"""
    with ui.card().classes("flex-1 min-w-[180px]"):
        with ui.row().classes("w-full items-center no-wrap"):
            ui.icon(icon).classes(f"text-3xl {icon_color}")
            with ui.column().classes("flex-1 gap-0"):
                ui.label(value).classes("text-2xl font-bold")
                ui.label(label).classes("text-grey-7 text-sm")
                if sub:
                    ui.label(sub).classes("text-grey-6 text-xs")


def build_dashboard_page() -> None:
    """构建「概览」页面 UI。"""
    ui.label("墨西哥 Instagram 内容创作者发现工具").classes("text-grey-7 text-sm mb-4")

    # ===== 当前任务状态卡片 =====
    with ui.card().classes("w-full mb-4"):
        with ui.row().classes("w-full items-center"):
            ui.icon("play_circle").classes("text-3xl text-green-7")
            ui.label("当前任务").classes("text-lg font-bold")
            ui.space()
            # 状态徽章
            status_chip = ui.badge("空闲", color="green").props("outline")

        ui.separator().classes("my-2")

        with ui.column().classes("w-full gap-1"):
            task_status_row = ui.row().classes("w-full items-center")
            with task_status_row:
                ui.label("状态：").classes("text-grey-8 w-24")
                task_status_label = ui.label("空闲").classes("text-grey-7")

            task_msg_row = ui.row().classes("w-full items-center")
            with task_msg_row:
                ui.label("阶段：").classes("text-grey-8 w-24")
                task_stage_label = ui.label("-").classes("text-grey-7")

            task_elapsed_row = ui.row().classes("w-full items-center")
            with task_elapsed_row:
                ui.label("已用时：").classes("text-grey-8 w-24")
                task_elapsed_label = ui.label("-").classes("text-grey-7")

        ui.separator().classes("my-2")

        with ui.row().classes("w-full gap-2"):
            ui.button("前往新建搜索", color="primary").props("outline").on("click", lambda _: ui.navigate_to("/"))
            ui.button("查看任务进度", color="blue").props("outline").on("click", lambda _: ui.navigate_to("/"))

    # ===== 数据统计卡片 =====
    ui.label("数据统计").classes("text-lg font-bold mt-4 mb-2")

    task_count, last_status = _count_tasks()
    creator_count = _count_creators()
    export_count = _count_exports()

    with ui.row().classes("w-full gap-2 mb-4 wrap"):
        _stat_card(
            "assignment",
            "text-blue-7",
            "历史任务",
            str(task_count),
            f"最近：{last_status}" if task_count else "暂无",
        )
        _stat_card(
            "person",
            "text-green-7",
            "已分析博主",
            str(creator_count),
            "去重计数" if creator_count else "暂无",
        )
        _stat_card(
            "file_download",
            "text-orange-7",
            "导出文件",
            str(export_count),
            "CSV / JSON / XLSX" if export_count else "暂无",
        )

    # ===== 快捷入口 =====
    ui.label("快捷入口").classes("text-lg font-bold mt-4 mb-2")
    with ui.row().classes("w-full gap-2 wrap"):
        ui.button("新建搜索", icon="search", color="primary").props("outline").on(
            "click", lambda _: ui.navigate_to("/")
        )
        ui.button("排除名单", icon="block", color="orange").props("outline").on("click", lambda _: ui.navigate_to("/"))
        ui.button("导出记录", icon="download", color="blue").props("outline").on("click", lambda _: ui.navigate_to("/"))
        ui.button("设置", icon="settings", color="grey").props("outline").on("click", lambda _: ui.navigate_to("/"))

    # ===== 实时刷新任务状态 =====
    def refresh() -> None:
        is_running = gui_state.is_running
        p = gui_state.latest_progress
        elapsed = gui_state.elapsed_seconds()

        # 徽章
        if is_running:
            status_chip.text = "运行中"
            status_chip.props("color=orange outline")
            task_status_label.text = "运行中"
            task_status_label.classes(replace="text-orange-7")
        elif gui_state.latest_result is not None:
            r = gui_state.latest_result
            status_chip.text = r.status.value
            status_chip.props("color=green outline")
            task_status_label.text = r.status.value
            task_status_label.classes(replace="text-green-7")
        else:
            status_chip.text = "空闲"
            status_chip.props("color=green outline")
            task_status_label.text = "空闲"
            task_status_label.classes(replace="text-grey-7")

        # 阶段
        if p is not None:
            task_stage_label.text = p.message or "-"
        else:
            task_stage_label.text = "-"

        # 已用时
        if elapsed is not None and elapsed > 0:
            seconds = int(elapsed)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                task_elapsed_label.text = f"{h}:{m:02d}:{s:02d}"
            else:
                task_elapsed_label.text = f"{m:02d}:{s:02d}"
        else:
            task_elapsed_label.text = "-"

    ui.timer(1.0, refresh)


# 防止 build_settings 慢加载导致的副作用
_ = gui_state  # 保留单例引用
