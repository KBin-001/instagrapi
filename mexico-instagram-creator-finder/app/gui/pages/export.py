"""导出页面：选择任务与格式，复用 app.export.export_records 生成 CSV/JSON/XLSX。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import ui

from app.config import build_settings


def _load_tasks() -> list[tuple[str, str]]:
    """加载任务列表。"""
    from sqlalchemy import select

    from app.storage.database import Database, TaskRow

    settings = build_settings()
    db = Database(settings.checkpoint.database_file)
    session = db.get_session()
    try:
        stmt = select(TaskRow).order_by(TaskRow.updated_at.desc()).limit(50)
        rows = list(session.execute(stmt).scalars())
        return [(r.task_id, r.status or "unknown") for r in rows]
    finally:
        session.close()
        db.close()


def _load_records(task_id: str) -> list[Any]:
    """加载任务记录。"""
    from app.storage.database import Database
    from app.storage.repositories import load_all_records

    settings = build_settings()
    db = Database(settings.checkpoint.database_file)
    session = db.get_session()
    try:
        return load_all_records(session, task_id)
    finally:
        session.close()
        db.close()


def _list_exported_files() -> list[Path]:
    """列出 output/ 目录下的导出文件。"""
    settings = build_settings()
    out_dir = Path(settings.output.directory)
    if not out_dir.exists():
        return []
    files: list[Path] = []
    for ext in ("*.csv", "*.json", "*.xlsx"):
        files.extend(out_dir.glob(ext))
    return sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)


def build_export_page() -> None:
    """构建「导出记录」页面 UI。"""
    ui.label(
        "选择任务和导出格式，复用 CLI 的导出器（CSV 使用 UTF-8 BOM，Excel 字段宽度合理，"
        "中文与西班牙语重音字符不乱码）。"
    ).classes("text-grey-7 text-sm mb-4")

    # ===== 任务选择 =====
    with ui.row().classes("w-full items-center mb-4"):
        ui.label("选择任务：").classes("font-bold")
        task_select = ui.select(options={}, label="任务 ID").props("outlined dense")

        def reload_tasks() -> None:
            try:
                tasks = _load_tasks()
                options = {tid: f"{tid} ({status})" for tid, status in tasks}
                task_select.options = options
                if tasks:
                    task_select.value = tasks[0][0]
                task_select.update()
            except Exception as e:  # noqa: BLE001
                ui.notify(f"加载任务失败：{e}", type="negative", position="top")

        reload_btn = ui.button("刷新", color="primary").props("flat")
        reload_btn.on("click", lambda _: reload_tasks())

    # ===== 格式选择 =====
    ui.label("导出格式").classes("font-bold")
    with ui.row().classes("w-full items-center mt-1 mb-4"):
        csv_cb = ui.checkbox("CSV (UTF-8 BOM)", value=True)
        json_cb = ui.checkbox("JSON", value=True)
        xlsx_cb = ui.checkbox("Excel (XLSX)", value=True)

    # ===== 导出按钮 =====
    export_btn = ui.button("开始导出", color="green").props("unelevinated")
    result_label = ui.label("").classes("text-grey-7 text-sm mt-2")

    def on_export() -> None:
        task_id = task_select.value
        if not task_id:
            ui.notify("请先选择任务", type="warning", position="top")
            return

        formats: list[str] = []
        if csv_cb.value:
            formats.append("csv")
        if json_cb.value:
            formats.append("json")
        if xlsx_cb.value:
            formats.append("xlsx")
        if not formats:
            ui.notify("至少选择一种格式", type="warning", position="top")
            return

        try:
            from app.export import export_records

            records = _load_records(task_id)
            if not records:
                ui.notify("该任务没有可导出的记录", type="warning", position="top")
                return

            settings = build_settings()
            exported = export_records(
                records,
                output_dir=settings.output.directory,
                formats=formats,
                task_id=task_id,
            )

            lines = [f"已导出 {len(records)} 条记录："]
            for fmt, path in exported.items():
                lines.append(f"  {fmt.upper()}: {path}")
            result_label.text = "\n".join(lines)
            result_label.classes(replace="text-green-7 text-sm mt-2")
            ui.notify(f"导出完成：{len(exported)} 个文件", type="positive", position="top")
            refresh_files()
        except Exception as e:  # noqa: BLE001
            result_label.text = f"导出失败：{e}"
            result_label.classes(replace="text-red-7 text-sm mt-2")
            ui.notify(f"导出失败：{e}", type="negative", position="top")

    export_btn.on("click", lambda _: on_export())

    # ===== 已导出文件 =====
    ui.separator().classes("my-4")
    ui.label("output/ 目录下的导出文件").classes("font-bold")
    files_container = ui.column().classes("w-full mt-1")

    def refresh_files() -> None:
        files_container.clear()
        with files_container:
            files = _list_exported_files()
            if not files:
                ui.label("（暂无导出文件）").classes("text-grey-7 italic")
                return
            for f in files[:30]:
                try:
                    size = f.stat().st_size
                    ui.label(f"📊 {f.name}  ({size} bytes)  →  {f}").classes("text-grey-8 text-sm")
                except OSError:
                    ui.label(f"📊 {f.name}").classes("text-grey-8 text-sm")

    refresh_btn2 = ui.button("刷新文件列表", color="primary").props("flat")
    refresh_btn2.on("click", lambda _: refresh_files())

    # ===== 首次加载 =====
    reload_tasks()
    refresh_files()

    # ===== 提示 =====
    ui.separator().classes("my-4")
    ui.label("说明").classes("font-bold")
    ui.label(
        "• 默认排序：total_score 降序 → median_visible_reel_views 降序 → followers 降序\n"
        "• CSV 使用 UTF-8 BOM，Excel 打开中文/西班牙语重音字符不乱码\n"
        "• Excel 字段宽度合理，长文本自动换行，URL 可点击\n"
        "• JSON 保持英文 key\n"
        "• 不导出密码、Cookie 或 Session"
    ).classes("text-grey-7 text-sm whitespace-pre-wrap")
