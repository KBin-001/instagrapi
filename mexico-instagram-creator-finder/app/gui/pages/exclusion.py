"""排除名单页面：上传/输入用户名列表，生成排除文件供 SearchService 使用。

复用 app.discovery.seeds.parse_exclude_file / parse_username_list。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import ui

from app.config import build_settings


def _parse_uploaded_file(path: Path) -> tuple[list[str], list[str], list[str]]:
    """解析上传的文件，返回 (valid_usernames, invalid_raw, source_lines)。"""
    from app.discovery.seeds import parse_exclude_file

    entries = parse_exclude_file(path)
    valid = [e.username for e in entries]
    # 简单返回所有条目作为 valid（deduplication 模块已处理）
    return valid, [], [e.to_dict() for e in entries]


def _list_exclude_files() -> list[Path]:
    """列出 data/ 下的排除名单示例文件。"""
    settings = build_settings()
    project_root = settings.config_dir.parent
    data_dir = project_root / "data"
    if not data_dir.exists():
        return []
    return sorted(data_dir.glob("*.txt"))


def build_exclusion_page() -> None:
    """构建「排除名单」页面 UI。"""
    ui.label(
        "上传或手动输入要排除的用户名（每行一个，支持 @username / Instagram URL / # 注释）。"
        " 保存为 TXT 文件后，在「新建搜索」时通过 .env 或 FINDER_EXCLUDE_FILES 指定。"
    ).classes("text-grey-7 text-sm mb-4")

    # ===== 文件上传 =====
    ui.label("上传排除名单文件（.txt / .csv / .xlsx）").classes("font-bold")
    upload = ui.upload(
        label="选择文件",
        auto_upload=True,
        multiple=False,
        max_files=1,
        max_total_size=5 * 1024 * 1024,
    ).props("accept=.txt,.csv,.xlsx outlined")

    upload_result = ui.label("").classes("text-grey-7 text-sm mt-1")

    def handle_upload(e: Any) -> None:
        try:
            # NiceGUI 提供 e.content.read() 读取字节
            content = e.content.read()
            name = e.name
            # 暂存到临时文件
            tmp_dir = Path("data/uploads")
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = tmp_dir / name
            tmp_path.write_bytes(content)

            from app.discovery.seeds import parse_exclude_file

            entries = parse_exclude_file(tmp_path)
            upload_result.text = f"已解析 {len(entries)} 个有效用户名（文件：{name}）。临时文件：{tmp_path}"
            upload_result.classes(replace="text-green-7 text-sm mt-1")

            # 把解析出的用户名加入文本框
            existing = text_area.value or ""
            new_lines = [e.username for e in entries]
            combined = existing.strip()
            for u in new_lines:
                if u not in combined.splitlines():
                    combined = (combined + "\n" + u) if combined else u
            text_area.value = combined
            text_area.update()
            ui.notify(f"已加载 {len(new_lines)} 个用户名", type="positive", position="top")
        except Exception as ex:  # noqa: BLE001
            upload_result.text = f"解析失败：{ex}"
            upload_result.classes(replace="text-red-7 text-sm mt-1")
            ui.notify(f"解析失败：{ex}", type="negative", position="top")

    upload.on("upload", handle_upload)

    # ===== 手动输入 =====
    ui.separator().classes("my-4")
    ui.label("手动输入或编辑").classes("font-bold")
    ui.label("每行一个 username 或 Instagram URL；# 开头为注释。").classes("text-grey-7 text-xs mb-1")
    text_area = ui.textarea(placeholder="@username\nhttps://instagram.com/username\n# 注释").props(
        "outlined rows=10 class=w-full"
    )

    # ===== 保存为文件 =====
    with ui.row().classes("mt-2 items-center gap-2"):
        save_input = ui.input(
            label="保存文件名",
            value="my_exclusions.txt",
        ).props("outlined dense")
        save_btn = ui.button("保存到 data/", color="primary").props("unelevinated")
        save_result = ui.label("").classes("text-grey-7 text-sm")

        def on_save() -> None:
            try:
                from app.discovery.deduplication import parse_username_list

                raw_lines = (text_area.value or "").splitlines()
                valid, invalid = parse_username_list(raw_lines)
                fname = save_input.value or "my_exclusions.txt"
                if not fname.endswith((".txt", ".csv", ".xlsx")):
                    fname += ".txt"

                settings = build_settings()
                project_root = settings.config_dir.parent
                data_dir = project_root / "data"
                data_dir.mkdir(parents=True, exist_ok=True)
                save_path = data_dir / fname

                # 写入 TXT（每行一个 + 注释头）
                lines = ["# 排除名单 - 由 GUI 生成", f"# 共 {len(valid)} 个用户名", ""]
                lines.extend(valid)
                if invalid:
                    lines.append("")
                    lines.append("# 以下为无法解析的输入：")
                    lines.extend(f"# {x}" for x in invalid)
                save_path.write_text("\n".join(lines), encoding="utf-8")

                save_result.text = f"已保存：{save_path}（{len(valid)} 个有效，{len(invalid)} 个无效）"
                save_result.classes(replace="text-green-7 text-sm")
                ui.notify(f"已保存到 {save_path}", type="positive", position="top")
            except Exception as ex:  # noqa: BLE001
                save_result.text = f"保存失败：{ex}"
                save_result.classes(replace="text-red-7 text-sm")
                ui.notify(f"保存失败：{ex}", type="negative", position="top")

        save_btn.on("click", lambda _: on_save())

    # ===== 已存在的排除文件 =====
    ui.separator().classes("my-4")
    ui.label("data/ 目录下的排除名单文件").classes("font-bold")
    files_container = ui.column().classes("w-full mt-1")

    def refresh_files() -> None:
        files_container.clear()
        with files_container:
            files = _list_exclude_files()
            if not files:
                ui.label("（暂无 .txt 文件）").classes("text-grey-7 italic")
                return
            for f in files:
                try:
                    size = f.stat().st_size
                    ui.label(f"📄 {f.name}  ({size} bytes)  →  {f}").classes("text-grey-8 text-sm")
                except OSError:
                    ui.label(f"📄 {f.name}").classes("text-grey-8 text-sm")

    refresh_btn = ui.button("刷新文件列表", color="primary").props("flat")
    refresh_btn.on("click", lambda _: refresh_files())
    refresh_files()

    # ===== 提示 =====
    ui.separator().classes("my-4")
    ui.label("使用方法").classes("font-bold")
    ui.label(
        "1. 在上方手动输入或上传文件 → 保存为 data/xxx.txt\n"
        "2. 在「新建搜索」页面启动任务前，于 .env 中设置 FINDER_EXCLUDE_FILES=data/xxx.txt\n"
        "   或在命令行执行：python main.py search --exclude data/xxx.txt\n"
        "3. 排除名单仅作为筛选条件，不会删除已有数据。"
    ).classes("text-grey-7 text-sm whitespace-pre-wrap")
