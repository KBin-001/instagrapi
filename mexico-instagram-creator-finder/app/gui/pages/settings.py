"""设置页：4 个卡片（连接 / 默认参数 / 本地数据 / 高级）。

按用户产品化建议重构：
1. Instagram 连接：账号状态 + 登录账号 + Session + 最后验证 + 操作按钮
2. 默认搜索参数：粉丝范围 + 最大分析账号 + 请求间隔 + 最长停更时间
3. 本地数据：路径展示 + 打开目录 + 清理历史
4. 高级配置与日志（折叠）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from nicegui import ui

from app.config import to_display_dict, validate_settings
from app.gui.state import gui_state

# ===== .env 文件读写 =====


def _env_file_path() -> Path:
    """获取 .env 文件路径。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".env"
    return Path(".env").resolve()


def _read_env_file() -> dict[str, str]:
    """读取 .env 为字典。"""
    env_path = _env_file_path()
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    except OSError:
        pass
    return result


def _write_env_file(values: dict[str, str]) -> None:
    """写入 .env 文件（保留已有非注释行）。"""
    env_path = _env_file_path()
    existing = _read_env_file()
    existing.update({k: v for k, v in values.items() if v is not None})
    lines: list[str] = ["# Mexico Instagram Creator Finder - 本地凭据", "# 请勿提交到 Git"]
    for k, v in existing.items():
        lines.append(f"{k}={v}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _session_file_path() -> Path:
    """获取 Session 文件路径。"""
    return Path(gui_state.settings.instagram.session_file).resolve()


def _verify_file_path() -> Path:
    """获取「最后验证」时间记录文件。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".last_verify"
    return Path(".last_verify").resolve()


def _read_last_verify() -> str:
    """读取最后验证时间。"""
    path = _verify_file_path()
    if not path.exists():
        return "从未验证"
    try:
        ts = float(path.read_text(encoding="utf-8").strip())
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except (OSError, ValueError):
        return "从未验证"


def _write_last_verify() -> None:
    """记录当前时间为最后验证时间。"""
    path = _verify_file_path()
    path.write_text(str(time.time()), encoding="utf-8")


def _mask_username(user: str) -> str:
    """用户名脱敏：mexico123 → mex***123。"""
    if not user:
        return "—"
    if len(user) <= 4:
        return user[0] + "***"
    return user[:3] + "***" + user[-3:]


# ===== 目录工具 =====


def _output_dir() -> Path:
    return Path(gui_state.settings.output.directory).resolve()


def _logs_dir() -> Path:
    return Path("logs").resolve()


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


# ===== 卡片 1：Instagram 连接 =====


def _build_connection_card() -> None:
    """Instagram 连接卡片。"""
    with ui.card().classes("w-full mb-4"):
        with ui.row().classes("w-full items-center"):
            ui.icon("account_circle").classes("text-3xl text-green-7")
            ui.label("Instagram 连接").classes("text-lg font-bold")
            ui.space()
            # 状态徽章
            status_chip = ui.badge("未配置", color="grey-6").props("outline")

        ui.separator().classes("my-2")

        # 信息行（key-value 表格式）
        account_status_label = ui.label()
        login_user_label = ui.label()
        session_status_label = ui.label()
        last_verify_label = ui.label()

        with ui.column().classes("w-full gap-1"):
            with ui.row().classes("w-full items-center"):
                ui.label("账号状态").classes("text-grey-8 w-32")
                account_status_label.classes("text-grey-7 flex-1")
            with ui.row().classes("w-full items-center"):
                ui.label("登录账号").classes("text-grey-8 w-32")
                login_user_label.classes("text-grey-7 flex-1")
            with ui.row().classes("w-full items-center"):
                ui.label("Session").classes("text-grey-8 w-32")
                session_status_label.classes("text-grey-7 flex-1")
            with ui.row().classes("w-full items-center"):
                ui.label("最后验证").classes("text-grey-8 w-32")
                last_verify_label.classes("text-grey-7 flex-1")

        ui.separator().classes("my-2")

        with ui.row().classes("w-full gap-2"):
            ui.button("测试连接", color="blue").props("outline").on("click", lambda _: _test_connection(refresh_status))
            ui.button("更新凭据", color="primary").props("outline").on(
                "click", lambda _: _open_config_dialog(refresh_status)
            )
            ui.button("清除 Session", color="orange").props("outline").on(
                "click", lambda _: _clear_session(refresh_status)
            )

    def refresh_status() -> None:
        """刷新所有状态标签。"""
        env_values = _read_env_file()
        username = env_values.get("IG_USERNAME", "").strip()
        password = env_values.get("IG_PASSWORD", "").strip()

        # 账号状态
        if username and password:
            account_status_label.text = "已配置"
            account_status_label.classes(replace="text-green-7 flex-1")
            status_chip.text = "已配置"
            status_chip.props("color=green outline")
        elif username:
            account_status_label.text = "部分配置（缺密码）"
            account_status_label.classes(replace="text-orange-7 flex-1")
            status_chip.text = "不完整"
            status_chip.props("color=orange outline")
        else:
            account_status_label.text = "未配置"
            account_status_label.classes(replace="text-grey-7 flex-1")
            status_chip.text = "未配置"
            status_chip.props("color=grey-6 outline")

        # 登录账号
        login_user_label.text = _mask_username(username) if username else "—"
        login_user_label.classes(replace="text-grey-7 flex-1")

        # Session
        sess_path = _session_file_path()
        if sess_path.exists():
            session_status_label.text = f"已创建（{sess_path.stat().st_size // 1024} KB）"
            session_status_label.classes(replace="text-green-7 flex-1")
        else:
            session_status_label.text = "未创建"
            session_status_label.classes(replace="text-grey-7 flex-1")

        # 最后验证
        last_verify_label.text = _read_last_verify()
        last_verify_label.classes(replace="text-grey-7 flex-1")

    # 首次刷新
    refresh_status()


def _open_config_dialog(refresh_callback) -> None:
    """打开「更新凭据」对话框。"""
    env_values = _read_env_file()
    existing_user = env_values.get("IG_USERNAME", "")

    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("更新 Instagram 凭据").classes("text-lg font-bold mb-2")
        ui.label("凭据仅写入本地 .env 文件，不会出现在数据库、日志或 YAML 中。").classes("text-grey-7 text-xs mb-3")

        user_input = ui.input(
            label="Instagram 用户名",
            value=existing_user,
            placeholder="your_instagram_username",
        ).props("outlined dense class=w-full")

        pass_input = ui.input(
            label="Instagram 密码",
            value="",
            placeholder="（留空表示不修改）",
            password=True,
            password_toggle_button=True,
        ).props("outlined dense class=w-full")

        if existing_user:
            ui.label("未输入新密码时保留原密码。").classes("text-grey-7 text-xs mt-1")

        result_label = ui.label("").classes("text-grey-7 text-sm mt-1")

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("取消", color="grey").props("flat").on("click", lambda _: dialog.close())

            def on_save() -> None:
                try:
                    updates: dict[str, str] = {}
                    user = (user_input.value or "").strip()
                    if user:
                        updates["IG_USERNAME"] = user
                    elif existing_user:
                        updates["IG_USERNAME"] = existing_user

                    pwd = (pass_input.value or "").strip()
                    if pwd:
                        updates["IG_PASSWORD"] = pwd
                    elif env_values.get("IG_PASSWORD"):
                        updates["IG_PASSWORD"] = env_values["IG_PASSWORD"]

                    _write_env_file(updates)
                    for k, v in updates.items():
                        os.environ[k] = v
                    gui_state.reload_settings()

                    result_label.text = "✓ 已保存"
                    result_label.classes(replace="text-green-7 text-sm mt-1")
                    ui.notify("凭据已保存", type="positive", position="top")
                    refresh_callback()
                    dialog.close()
                except Exception as e:  # noqa: BLE001
                    result_label.text = f"保存失败：{e}"
                    result_label.classes(replace="text-red-7 text-sm mt-1")
                    ui.notify(f"保存失败：{e}", type="negative", position="top")

            ui.button("保存", color="primary").props("unelevinated").on("click", lambda _: on_save())

    dialog.open()


def _test_connection(refresh_callback) -> None:
    """测试 Instagram 连接。"""
    env_values = _read_env_file()
    if not env_values.get("IG_USERNAME") or not env_values.get("IG_PASSWORD"):
        ui.notify("请先配置账号凭据", type="warning", position="top")
        return

    ui.notify("正在测试连接…", type="info", position="top")

    def run_test() -> None:
        try:
            from app.instagram.client import InstagramClient

            client = InstagramClient(gui_state.settings)
            client.login_from_env()
            logged_in = client.is_logged_in
            if logged_in:
                _write_last_verify()
                ui.notify("✓ 连接成功，Session 已保存", type="positive", position="top", timeout=5000)
                refresh_callback()
            else:
                ui.notify("✗ 登录失败，请检查凭据", type="negative", position="top", timeout=5000)
        except Exception as e:  # noqa: BLE001
            ui.notify(f"连接失败：{e}", type="negative", position="top", timeout=8000)

    import threading

    t = threading.Thread(target=run_test, daemon=True)
    t.start()


def _clear_session(refresh_callback) -> None:
    """清除本地 Session 文件。"""
    try:
        sess_path = _session_file_path()
        if not sess_path.exists():
            ui.notify("Session 文件不存在，无需清除", type="info", position="top")
            return
        sess_path.unlink()
        ui.notify("Session 已清除，下次启动将需要重新登录", type="positive", position="top")
        refresh_callback()
    except Exception as e:  # noqa: BLE001
        ui.notify(f"清除失败：{e}", type="negative", position="top")


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

        # 粉丝范围（一行双输入框）
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

        # 最大分析账号
        with ui.row().classes("w-full items-center mt-2"):
            ui.label("最大分析账号").classes("text-grey-8 w-40")
            max_profiles = ui.number(
                value=settings.discovery.max_profiles_to_analyze,
                min=1,
                max=500,
                step=5,
            ).props("outlined dense")
            ui.label("个").classes("text-grey-7 text-sm")

        # 请求间隔（一行双输入框）
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

        # 最长停更时间
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

        # 导出格式
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

            ui.button("保存设置", color="primary").props("unelevinated").on("click", lambda _: on_save())


# ===== 卡片 3：本地数据 =====


def _build_local_data_card() -> None:
    """本地数据卡片。"""
    with ui.card().classes("w-full mb-4"):
        with ui.row().classes("w-full items-center"):
            ui.icon("folder_open").classes("text-3xl text-orange-7")
            ui.label("本地数据").classes("text-lg font-bold")

        ui.separator().classes("my-2")

        db_path = Path(gui_state.settings.checkpoint.database_file).resolve()
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

        ui.button("删除全部本地数据", color="red").props("unelevinated full-width").on(
            "click", lambda _: _confirm_delete_all()
        )


def _confirm_clear_history() -> None:
    """确认清理历史任务。"""
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("清理历史任务").classes("text-lg font-bold mb-2")
        ui.label(
            "将删除 SQLite 数据库中的所有任务记录、候选账号、分析结果与导出文件，"
            "但保留 .env、config/、Session 等配置。\n\n此操作不可撤销。"
        ).classes("text-grey-7 text-sm mb-3 whitespace-pre-wrap")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("取消", color="grey").props("flat").on("click", lambda _: dialog.close())

            def on_confirm() -> None:
                try:
                    db_path = Path(gui_state.settings.checkpoint.database_file).resolve()
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

            ui.button("确认清理", color="orange").props("unelevinated").on("click", lambda _: on_confirm())

    dialog.open()


def _confirm_delete_all() -> None:
    """确认删除全部本地数据。"""
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("删除全部本地数据").classes("text-lg font-bold mb-2 text-red-7")
        ui.label(
            "将删除所有本地数据，包括：\n"
            "• SQLite 数据库（任务与结果）\n"
            "• 导出文件（output/）\n"
            "• Session 文件（需重新登录）\n"
            "• .env 凭据文件\n\n"
            "config/ 目录的 YAML 配置会保留。\n\n此操作不可撤销。"
        ).classes("text-grey-7 text-sm mb-3 whitespace-pre-wrap")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("取消", color="grey").props("flat").on("click", lambda _: dialog.close())

            def on_confirm() -> None:
                try:
                    db_path = Path(gui_state.settings.checkpoint.database_file).resolve()
                    if db_path.exists():
                        db_path.unlink()
                    out_dir = _output_dir()
                    if out_dir.exists():
                        for f in out_dir.glob("*"):
                            if f.is_file():
                                f.unlink()
                    sess_path = _session_file_path()
                    if sess_path.exists():
                        sess_path.unlink()
                    env_path = _env_file_path()
                    if env_path.exists():
                        env_path.unlink()
                    ui.notify("全部本地数据已删除", type="positive", position="top")
                    dialog.close()
                except Exception as e:  # noqa: BLE001
                    ui.notify(f"删除失败：{e}", type="negative", position="top")

            ui.button("确认删除", color="red").props("unelevinated").on("click", lambda _: on_confirm())

    dialog.open()


# ===== 卡片 4：高级配置与日志（折叠面板） =====


def _build_advanced_card() -> None:
    """高级配置与日志折叠面板。"""
    with ui.expansion("高级配置与日志", icon="settings").classes("w-full").props("dense-toggle"):
        ui.label("普通用户无需修改以下内容。").classes("text-grey-7 text-xs mb-2")

        # 子面板 1：完整脱敏配置
        with ui.expansion("查看完整脱敏配置（JSON）", icon="code").classes("w-full"):
            ui.label("包含所有合并后的配置参数（密码已脱敏）。").classes("text-grey-7 text-xs mb-1")
            display = to_display_dict(gui_state.settings)
            ui.code(
                json.dumps(display, ensure_ascii=False, indent=2, default=str),
                language="json",
            ).classes("w-full")

        # 子面板 2：运行日志
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

        # 子面板 3：验证配置
        with ui.expansion("验证配置文件", icon="verified").classes("w-full"):
            ui.label("检查当前配置是否完整、合法。").classes("text-grey-7 text-xs mb-1")
            validate_result = ui.label("").classes("text-grey-7 text-sm")

            def on_validate() -> None:
                errors = validate_settings(gui_state.settings)
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
    ui.label("管理 Instagram 连接、搜索默认值和本地数据。").classes("text-grey-7 text-sm mb-4")

    _build_connection_card()
    _build_default_params_card()
    _build_local_data_card()
    _build_advanced_card()
