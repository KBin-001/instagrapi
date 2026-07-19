"""设置页：4 个卡片（浏览器扩展 / 默认参数 / 本地数据 / 高级）。

新架构（Chrome 扩展 + 用户已登录的 Instagram 官方网页）：
1. 浏览器扩展：扩展状态 + 本地接口 + 最近同步 + 安装扩展 + 测试连接 + 重新生成令牌
2. 默认搜索参数：粉丝范围 + 最大分析账号 + 请求间隔 + 最长停更时间
3. 本地数据：路径展示 + 打开目录 + 清理历史
4. 高级配置与日志（折叠）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from nicegui import ui

from app.config import to_display_dict, validate_settings
from app.gui.state import gui_state


# ===== 目录工具 =====


def _output_dir() -> Path:
    return Path(gui_state.settings.output.directory).resolve()


def _logs_dir() -> Path:
    return Path("logs").resolve()


def _db_path() -> Path:
    return Path(gui_state.settings.checkpoint.database_file).resolve()


def _open_in_explorer(path: Path) -> None:
    """在系统资源管理器中打开目录。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)  # noqa: S603, S607
        else:
            subprocess.run(["xdg-open", str(path)], check=False)  # noqa: S603, S607
    except Exception as e:  # noqa: BLE001
        ui.notify(f"打开目录失败：{e}", type="negative", position="top")


def _extension_dir() -> Path:
    """Chrome 扩展所在目录（dist/chrome_extension/）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "chrome_extension"
    # app/gui/pages/settings.py → mexico-instagram-creator-finder/dist/chrome_extension
    return Path(__file__).resolve().parents[3] / "dist" / "chrome_extension"


# ===== 卡片 1：浏览器扩展 =====


def _build_extension_card() -> None:
    """浏览器扩展卡片：状态 + 本地接口 + 令牌管理。"""
    from app.gui.dependencies import get_ingest_service

    with ui.card().classes("w-full mb-4"):
        with ui.row().classes("w-full items-center"):
            ui.icon("extension").classes("text-3xl text-green-7")
            ui.label("浏览器扩展").classes("text-lg font-bold")
            ui.space()
            status_chip = ui.badge("未连接", color="grey-6").props("outline")

        ui.separator().classes("my-2")

        ui.label(
            "新架构：通过 Chrome 扩展在用户已登录的 Instagram 官方网页中采集公开数据。\n"
            "本地 NiceGUI 不接收 Instagram 密码，不进行移动端 API 登录。"
        ).classes("text-grey-7 text-sm mb-3 whitespace-pre-wrap")

        ext_status_label = ui.label()
        ext_version_label = ui.label()
        api_url_label = ui.label()
        last_sync_label = ui.label()
        token_label = ui.label()

        with ui.column().classes("w-full gap-1"):
            with ui.row().classes("w-full items-center"):
                ui.label("扩展状态").classes("text-grey-8 w-32")
                ext_status_label.classes("text-grey-7 flex-1")
            with ui.row().classes("w-full items-center"):
                ui.label("扩展版本").classes("text-grey-8 w-32")
                ext_version_label.classes("text-grey-7 flex-1")
            with ui.row().classes("w-full items-center"):
                ui.label("本地接口").classes("text-grey-8 w-32")
                api_url_label.classes("text-grey-7 flex-1")
            with ui.row().classes("w-full items-center"):
                ui.label("最近同步").classes("text-grey-8 w-32")
                last_sync_label.classes("text-grey-7 flex-1")
            with ui.row().classes("w-full items-center"):
                ui.label("本地令牌").classes("text-grey-8 w-32")
                token_label.classes("text-grey-7 flex-1")

        ui.separator().classes("my-2")

        with ui.row().classes("w-full gap-2"):
            install_btn = ui.button("打开扩展目录", color="blue").props("outline")
            copy_btn = ui.button("复制接口地址", color="teal").props("outline")
            test_btn = ui.button("测试扩展接口", color="teal").props("outline")
            regen_btn = ui.button("重新生成本地令牌", color="orange").props("outline")

        result_label = ui.label("").classes("text-grey-7 text-sm mt-2")

        def refresh_status() -> None:
            try:
                service = get_ingest_service()
                status = service.status()
            except Exception as e:  # noqa: BLE001
                ext_status_label.text = f"查询失败：{e}"
                ext_status_label.classes(replace="text-red-7 flex-1")
                status_chip.text = "错误"
                status_chip.props("color=red outline")
                return

            if status.connected:
                ext_status_label.text = "已连接"
                ext_status_label.classes(replace="text-green-7 flex-1")
                status_chip.text = "已连接"
                status_chip.props("color=green outline")
            else:
                ext_status_label.text = "未连接（请安装并启用扩展）"
                ext_status_label.classes(replace="text-grey-7 flex-1")
                status_chip.text = "未连接"
                status_chip.props("color=grey-6 outline")

            ext_version_label.text = status.extension_version or "—"
            ext_version_label.classes(replace="text-grey-7 flex-1")

            api_url_label.text = status.local_api_url or "—"
            api_url_label.classes(replace="text-grey-7 flex-1")

            if status.last_handshake_at:
                last_sync_label.text = status.last_handshake_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_sync_label.text = "从未同步"
            last_sync_label.classes(replace="text-grey-7 flex-1")

            token = service.token
            token_label.text = (token[:8] + "…") if token else "—"
            token_label.classes(replace="text-grey-7 flex-1")

        def on_install(_):
            ext_dir = _extension_dir()
            if not ext_dir.exists():
                ui.notify(f"扩展目录不存在：{ext_dir}", type="warning", position="top")
                return
            _open_in_explorer(ext_dir)

        def on_copy(_):
            """复制接口地址到剪贴板，方便贴到 Chrome 扩展侧边栏。"""
            try:
                service = get_ingest_service()
                url = service.status().local_api_url
                if not url:
                    ui.notify("本地接口地址尚未就绪，请先重启 NiceGUI", type="warning", position="top")
                    return
                # 通过前端 JS 写入剪贴板
                import json

                ui.run_javascript(
                    f"navigator.clipboard.writeText({json.dumps(url)})"
                )
                ui.notify(f"已复制：{url}", type="positive", position="top", timeout=3000)
            except Exception as e:  # noqa: BLE001
                ui.notify(f"复制失败：{e}", type="negative", position="top")

        async def on_test(_):
            test_btn.disable()
            try:
                service = get_ingest_service()
                # 自检：令牌能正常生成并通过校验
                token = service.token
                ok = service.verify_token(token)
                if ok:
                    ui.notify("✓ 本地扩展接口正常", type="positive", position="top")
                    result_label.text = (
                        "✓ 本地接口可达。请在 Chrome 扩展中粘贴令牌并点击「测试连接」。\n"
                        f"  接口地址：{service.status().local_api_url}"
                    )
                    result_label.classes(replace="text-green-7 text-sm mt-2 whitespace-pre-wrap")
                else:
                    ui.notify("令牌无效", type="negative", position="top")
            finally:
                test_btn.enable()
                refresh_status()

        def on_regen(_):
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("重新生成本地令牌").classes("text-lg font-bold mb-2")
                ui.label(
                    "已连接的扩展将立即断开。需要在 Chrome 扩展中重新粘贴新令牌才能恢复。"
                ).classes("text-grey-7 text-sm mb-3")
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("取消", color="grey").props("flat").on("click", lambda _: dialog.close())

                    def on_confirm():
                        try:
                            new_token = get_ingest_service().regenerate_token()
                            ui.notify("已重新生成令牌", type="positive", position="top")
                            result_label.text = f"新令牌（前 8 位）：{new_token[:8]}…"
                            result_label.classes(replace="text-green-7 text-sm mt-2")
                            dialog.close()
                            refresh_status()
                        except Exception as e:  # noqa: BLE001
                            ui.notify(f"生成失败：{e}", type="negative", position="top")

                    ui.button("确认", color="orange").props("unelevated").on("click", lambda _: on_confirm())
            dialog.open()

        install_btn.on("click", on_install)
        copy_btn.on("click", on_copy)
        test_btn.on("click", on_test)
        regen_btn.on("click", on_regen)

        ui.timer(3.0, refresh_status)
        refresh_status()


# ===== 卡片 2：默认搜索参数 =====


def _build_default_params_card() -> None:
    """默认搜索参数卡片（精简版）。"""
    settings = gui_state.settings

    with ui.card().classes("w-full mb-4"):
        with ui.row().classes("w-full items-center"):
            ui.icon("tune").classes("text-3xl text-blue-7")
            ui.label("默认搜索参数").classes("text-lg font-bold")

        ui.separator().classes("my-2")

        ui.label("这些参数会保存到 config/user.yaml，作为「新建搜索」页面的默认值。").classes(
            "text-grey-7 text-xs mb-3"
        )

        with ui.row().classes("w-full items-center"):
            ui.label("粉丝范围").classes("text-grey-8 w-40")
            min_followers = ui.number(
                value=settings.filters.min_followers,
                min=0,
                step=1000,
            ).props("outlined dense")
            ui.label("—").classes("mx-2 text-grey-7")
            max_followers = ui.number(
                value=settings.filters.max_followers,
                min=0,
                step=1000,
            ).props("outlined dense")
            ui.label("人").classes("text-grey-7 text-sm")

        with ui.row().classes("w-full items-center mt-2"):
            ui.label("最大分析账号").classes("text-grey-8 w-40")
            max_profiles = ui.number(
                value=settings.discovery.max_profiles_to_analyze,
                min=1,
                max=500,
                step=5,
            ).props("outlined dense")
            ui.label("个").classes("text-grey-7 text-sm")

        with ui.row().classes("w-full items-center mt-2"):
            ui.label("请求间隔").classes("text-grey-8 w-40")
            delay_min = ui.number(
                value=settings.instagram.request_delay_min_seconds,
                min=0,
                max=60,
                step=1,
            ).props("outlined dense")
            ui.label("—").classes("mx-2 text-grey-7")
            delay_max = ui.number(
                value=settings.instagram.request_delay_max_seconds,
                min=0,
                max=120,
                step=1,
            ).props("outlined dense")
            ui.label("秒").classes("text-grey-7 text-sm")

        with ui.row().classes("w-full items-center mt-2"):
            ui.label("最长停更时间").classes("text-grey-8 w-40")
            max_days = ui.number(
                value=settings.filters.maximum_days_since_last_post,
                min=1,
                max=365,
                step=1,
            ).props("outlined dense")
            ui.label("天").classes("text-grey-7 text-sm")

        ui.separator().classes("my-2")

        with ui.row().classes("w-full items-center"):
            ui.label("导出格式").classes("text-grey-8 w-40")
            csv_cb = ui.checkbox("CSV", value="csv" in settings.output.formats)
            json_cb = ui.checkbox("JSON", value="json" in settings.output.formats)
            xlsx_cb = ui.checkbox("Excel (XLSX)", value="xlsx" in settings.output.formats)

        with ui.row().classes("w-full justify-end mt-2 gap-2"):
            result_label = ui.label("").classes("text-grey-7 text-sm flex-1")

            def on_save() -> None:
                try:
                    import yaml

                    user_yaml_path = gui_state.settings.config_dir / "user.yaml"
                    existing: dict = {}
                    if user_yaml_path.exists():
                        loaded = yaml.safe_load(user_yaml_path.read_text(encoding="utf-8"))
                        if isinstance(loaded, dict):
                            existing = loaded

                    existing.setdefault("instagram", {})
                    existing["instagram"]["request_delay_min_seconds"] = int(delay_min.value or 4)
                    existing["instagram"]["request_delay_max_seconds"] = int(delay_max.value or 8)

                    existing.setdefault("discovery", {})
                    existing["discovery"]["max_profiles_to_analyze"] = int(max_profiles.value or 100)

                    existing.setdefault("filters", {})
                    existing["filters"]["min_followers"] = int(min_followers.value or 20000)
                    existing["filters"]["max_followers"] = int(max_followers.value or 300000)
                    existing["filters"]["maximum_days_since_last_post"] = int(max_days.value or 90)

                    formats: list[str] = []
                    if csv_cb.value:
                        formats.append("csv")
                    if json_cb.value:
                        formats.append("json")
                    if xlsx_cb.value:
                        formats.append("xlsx")
                    if formats:
                        existing.setdefault("output", {})
                        existing["output"]["formats"] = formats

                    user_yaml_path.write_text(
                        yaml.safe_dump(existing, allow_unicode=True, sort_keys=False),
                        encoding="utf-8",
                    )
                    gui_state.reload_settings()
                    result_label.text = "✓ 已保存到 user.yaml"
                    result_label.classes(replace="text-green-7 text-sm flex-1")
                    ui.notify("参数已保存", type="positive", position="top")
                except Exception as e:  # noqa: BLE001
                    result_label.text = f"保存失败：{e}"
                    result_label.classes(replace="text-red-7 text-sm flex-1")
                    ui.notify(f"保存失败：{e}", type="negative", position="top")

            ui.button("保存设置", color="primary").props("unelevated").on("click", lambda _: on_save())


# ===== 卡片 3：本地数据 =====


def _build_local_data_card() -> None:
    """本地数据卡片。"""
    with ui.card().classes("w-full mb-4"):
        with ui.row().classes("w-full items-center"):
            ui.icon("folder_open").classes("text-3xl text-orange-7")
            ui.label("本地数据").classes("text-lg font-bold")

        ui.separator().classes("my-2")

        db_path = _db_path()
        out_dir = _output_dir()

        with ui.column().classes("w-full gap-1"):
            with ui.row().classes("w-full items-center"):
                ui.label("数据库").classes("text-grey-8 w-24")
                ui.label(str(db_path)).classes("text-grey-7 text-sm flex-1 break-all")
            with ui.row().classes("w-full items-center"):
                ui.label("导出目录").classes("text-grey-8 w-24")
                ui.label(str(out_dir)).classes("text-grey-7 text-sm flex-1 break-all")

        ui.separator().classes("my-2")

        with ui.row().classes("w-full gap-2"):
            ui.button("打开目录", color="blue").props("outline").on("click", lambda _: _open_in_explorer(out_dir))
            ui.button("清理历史任务", color="orange").props("outline").on("click", lambda _: _confirm_clear_history())

        ui.separator().classes("my-2")

        with ui.row().classes("w-full items-center"):
            ui.icon("warning").classes("text-red-6")
            ui.label("危险操作").classes("text-red-7 font-bold")

        ui.button("删除全部本地数据", color="red").props("unelevated full-width").on(
            "click", lambda _: _confirm_delete_all()
        )


def _confirm_clear_history() -> None:
    """确认清理历史任务。"""
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("清理历史任务").classes("text-lg font-bold mb-2")
        ui.label(
            "将删除 SQLite 数据库中的所有任务记录、候选账号、分析结果与导出文件，"
            "但保留 .env、config/、扩展令牌等配置。\n\n此操作不可撤销。"
        ).classes("text-grey-7 text-sm mb-3 whitespace-pre-wrap")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("取消", color="grey").props("flat").on("click", lambda _: dialog.close())

            def on_confirm() -> None:
                try:
                    db_path = _db_path()
                    if db_path.exists():
                        db_path.unlink()
                    out_dir = _output_dir()
                    if out_dir.exists():
                        for f in out_dir.glob("*"):
                            if f.is_file():
                                f.unlink()
                    ui.notify("历史任务已清理", type="positive", position="top")
                    dialog.close()
                except Exception as e:  # noqa: BLE001
                    ui.notify(f"清理失败：{e}", type="negative", position="top")

            ui.button("确认清理", color="orange").props("unelevated").on("click", lambda _: on_confirm())

    dialog.open()


def _confirm_delete_all() -> None:
    """确认删除全部本地数据。"""
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("删除全部本地数据").classes("text-lg font-bold mb-2 text-red-7")
        ui.label(
            "将删除所有本地数据，包括：\n"
            "• SQLite 数据库（任务与结果）\n"
            "• 导出文件（output/）\n"
            "• 浏览器扩展令牌（data/extension_token.txt）\n"
            "• .env 凭据文件\n\n"
            "config/ 目录的 YAML 配置会保留。\n\n此操作不可撤销。"
        ).classes("text-grey-7 text-sm mb-3 whitespace-pre-wrap")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("取消", color="grey").props("flat").on("click", lambda _: dialog.close())

            def on_confirm() -> None:
                try:
                    db_path = _db_path()
                    if db_path.exists():
                        db_path.unlink()
                    out_dir = _output_dir()
                    if out_dir.exists():
                        for f in out_dir.glob("*"):
                            if f.is_file():
                                f.unlink()
                    # 清理扩展令牌
                    from app.extension.token_store import ExtensionTokenStore

                    token_path = ExtensionTokenStore.default_path()
                    if token_path.exists():
                        token_path.unlink()
                    # 清理 .env
                    env_path = Path(".env").resolve()
                    if getattr(sys, "frozen", False):
                        env_path = Path(sys.executable).resolve().parent / ".env"
                    if env_path.exists():
                        env_path.unlink()
                    ui.notify("全部本地数据已删除", type="positive", position="top")
                    dialog.close()
                except Exception as e:  # noqa: BLE001
                    ui.notify(f"删除失败：{e}", type="negative", position="top")

            ui.button("确认删除", color="red").props("unelevated").on("click", lambda _: on_confirm())

    dialog.open()


# ===== 卡片 4：高级配置与日志（折叠面板） =====


def _build_advanced_card() -> None:
    """高级配置与日志折叠面板。"""
    with ui.expansion("高级配置与日志", icon="settings").classes("w-full").props("dense-toggle"):
        ui.label("普通用户无需修改以下内容。").classes("text-grey-7 text-xs mb-2")

        with ui.expansion("查看完整脱敏配置（JSON）", icon="code").classes("w-full"):
            ui.label("包含所有合并后的配置参数。").classes("text-grey-7 text-xs mb-1")
            display = to_display_dict(gui_state.settings)
            ui.code(
                json.dumps(display, ensure_ascii=False, indent=2, default=str),
                language="json",
            ).classes("w-full")

        with ui.expansion("查看运行日志", icon="description").classes("w-full"):
            ui.label("显示最近 200 行日志（实时刷新）。").classes("text-grey-7 text-xs mb-1")
            log_area = ui.log(max_lines=200).classes("w-full h-64").props("outlined")
            state = {"offset": 0}

            def read_log_tail() -> None:
                logs_dir = _logs_dir()
                if not logs_dir.exists():
                    return
                log_files = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
                if not log_files:
                    return
                try:
                    text = log_files[0].read_text(encoding="utf-8", errors="ignore")
                    lines = text.splitlines()
                    new_lines = lines[state["offset"] :]
                    state["offset"] = len(lines)
                    for line in new_lines[-200:]:
                        log_area.push(line)
                except OSError:
                    pass

            ui.timer(2.0, read_log_tail)
            ui.button("立即刷新", color="primary").props("flat").on("click", lambda _: read_log_tail())

        with ui.expansion("验证配置文件", icon="verified").classes("w-full"):
            ui.label("检查当前配置是否完整、合法。").classes("text-grey-7 text-xs mb-1")
            validate_result = ui.label("").classes("text-grey-7 text-sm")

            def on_validate() -> None:
                errors = validate_settings(gui_state.settings, skip_credentials=True)
                if not errors:
                    validate_result.text = "✓ 配置校验通过，可以开始搜索"
                    validate_result.classes(replace="text-green-7 text-sm")
                    ui.notify("配置校验通过", type="positive", position="top")
                else:
                    validate_result.text = "✗ " + " | ".join(errors)
                    validate_result.classes(replace="text-red-7 text-sm")
                    ui.notify("校验失败：" + "; ".join(errors), type="negative", position="top")

            ui.button("验证配置", color="primary").props("outline").on("click", lambda _: on_validate())


# ===== 主入口 =====


def build_settings_page() -> None:
    """构建「设置」页面 UI（4 个卡片）。"""
    ui.label("管理浏览器扩展、搜索默认值和本地数据。").classes("text-grey-7 text-sm mb-4")

    _build_extension_card()
    _build_default_params_card()
    _build_local_data_card()
    _build_advanced_card()
