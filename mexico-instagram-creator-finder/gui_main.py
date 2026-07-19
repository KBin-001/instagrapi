"""NiceGUI 入口：Mexico Instagram Creator Finder 本地界面。

启动：
    python gui_main.py

特性：
- GUI 与 CLI 共用同一个 SQLite 数据库（默认 data/app.db）
- 通过 SearchService 在后台线程运行搜索，UI 不阻塞
- 左侧导航 + 顶部状态栏的桌面软件风格
- 7 个页面：概览 / 新建搜索 / 搜索任务 / 博主结果 / 排除名单 / 导出记录 / 设置
- 仅本地使用，不提供任何自动互动功能（自动关注/点赞/私信/评论均禁止）
"""

from __future__ import annotations

# ---- Python 3.14 兼容性 shim ----
# vbuild 0.8.2（nicegui 依赖）调用 pkgutil.find_loader，但该函数自 3.12 弃用、3.14 移除。
# 在导入 nicegui 之前先打补丁，用 importlib.util.find_spec 提供等价实现。
import importlib.util
import pkgutil
from typing import Any

if not hasattr(pkgutil, "find_loader"):  # pragma: no cover - 兼容性补丁

    def _find_loader(full_name: str):
        try:
            spec = importlib.util.find_spec(full_name)
            return spec.loader if spec is not None else None
        except (ImportError, AttributeError, ValueError):
            return None

    pkgutil.find_loader = _find_loader  # type: ignore[attr-defined]

from app.gui.state import gui_state
from app.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger("gui.main")


# ===== 导航配置 =====
# (key, 显示名, 图标)
NAV_ITEMS: list[tuple[str, str, str]] = [
    ("dashboard", "概览", "dashboard"),
    ("new_search", "新建搜索", "search"),
    ("progress", "搜索任务", "assignment"),
    ("results", "博主结果", "person"),
    ("exclusion", "排除名单", "block"),
    ("export", "导出记录", "file_download"),
]


def build_app() -> None:
    """构建 NiceGUI 应用页面（左侧导航 + 顶部状态栏）。"""
    from nicegui import ui

    from app.gui.pages.dashboard import build_dashboard_page
    from app.gui.pages.exclusion import build_exclusion_page
    from app.gui.pages.export import build_export_page
    from app.gui.pages.new_search import build_new_search_page
    from app.gui.pages.progress import build_progress_page
    from app.gui.pages.results import build_results_page
    from app.gui.pages.settings import build_settings_page

    # ===== 全局样式 =====
    ui.add_head_html(
        """
        <style>
            /* 整体布局：去掉默认 padding，让侧边栏顶到边 */
            .q-page { padding: 0 !important; }
            body { background: #f5f5f5; }

            /* 顶部状态栏 */
            .app-header {
                background: #1f7a4d;
                color: white;
                height: 56px;
                padding: 0 20px;
                display: flex;
                align-items: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .app-header .title { font-size: 18px; font-weight: bold; }

            /* 左侧导航 */
            .app-sidebar {
                background: white;
                width: 220px;
                min-width: 220px;
                height: calc(100vh - 56px);
                border-right: 1px solid #e0e0e0;
                padding: 12px 8px;
                display: flex;
                flex-direction: column;
                transition: width 0.2s, min-width 0.2s;
                overflow: hidden;
            }
            .app-sidebar.collapsed {
                width: 60px;
                min-width: 60px;
            }
            .app-sidebar.collapsed .nav-label,
            .app-sidebar.collapsed .sidebar-section-label,
            .app-sidebar.collapsed .app-sidebar-header {
                display: none;
            }
            .app-sidebar.collapsed .nav-item {
                justify-content: center;
                padding: 10px 0;
            }

            .nav-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 14px;
                margin: 2px 0;
                border-radius: 8px;
                cursor: pointer;
                color: #424242;
                font-size: 14px;
                transition: background 0.15s, color 0.15s;
                text-decoration: none;
            }
            .nav-item:hover {
                background: #f0f7f4;
                color: #1f7a4d;
            }
            .nav-item.active {
                background: #e6f2ec;
                color: #1f7a4d;
                font-weight: 500;
            }
            .nav-item .q-icon { font-size: 20px; }
            .nav-label { white-space: nowrap; }

            .sidebar-section-label {
                color: #9e9e9e;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 12px 14px 4px 14px;
            }

            .app-sidebar-header {
                padding: 4px 14px 12px 14px;
                border-bottom: 1px solid #f0f0f0;
                margin-bottom: 8px;
            }
            .app-sidebar-header .brand {
                font-size: 16px;
                font-weight: bold;
                color: #1f7a4d;
            }
            .app-sidebar-header .subtitle {
                font-size: 11px;
                color: #9e9e9e;
            }

            /* 主内容区 */
            .app-content {
                flex: 1;
                padding: 24px;
                overflow-y: auto;
                height: calc(100vh - 56px);
            }

            .page-title-row {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 16px;
            }
            .page-title {
                font-size: 22px;
                font-weight: bold;
                color: #212121;
            }

            /* 状态徽章 */
            .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 12px;
                border-radius: 16px;
                font-size: 13px;
                background: rgba(255,255,255,0.15);
            }
            .status-pill .dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #4caf50;
            }
            .status-pill.running .dot { background: #ff9800; }
            .status-pill.error .dot { background: #f44336; }

            /* 折叠按钮 */
            .collapse-btn {
                cursor: pointer;
                color: #757575;
                padding: 4px;
                border-radius: 4px;
            }
            .collapse-btn:hover { background: #f0f0f0; }

            /* ===== 新建搜索页面 ===== */
            .section-label {
                font-size: 13px;
                font-weight: 600;
                color: #424242;
                margin-top: 8px;
                margin-bottom: 2px;
            }

            .hashtag-card {
                background: #f7fbf8 !important;
                border: 1px solid #e0efe6 !important;
                box-shadow: none !important;
                padding: 16px !important;
                border-radius: 10px !important;
            }
            .hashtag-card .card-label {
                font-size: 14px;
                font-weight: 600;
                color: #1f7a4d;
                margin-bottom: 4px;
                display: block;
            }

            .scale-card {
                background: #eef5ff !important;
                border: 1px solid #d4e4f7 !important;
                box-shadow: none !important;
                padding: 14px 18px !important;
                border-radius: 10px !important;
            }

            .followers-number {
                min-width: 160px;
                max-width: 220px;
            }

            /* ===== 任务进度页面 ===== */
            .status-card {
                background: #fafafa !important;
                border: 1px solid #e0e0e0 !important;
                box-shadow: none !important;
                padding: 14px 18px !important;
                border-radius: 10px !important;
            }
            .progress-card {
                background: linear-gradient(135deg, #f7fbf8 0%, #eef5ff 100%) !important;
                border: 1px solid #d4e4f7 !important;
                box-shadow: none !important;
                padding: 18px 22px !important;
                border-radius: 10px !important;
            }
            .hashtag-progress-card {
                background: #fafafa !important;
                border: 1px solid #eceff1 !important;
                box-shadow: none !important;
                padding: 12px 16px !important;
                border-radius: 8px !important;
            }

            .metric-card {
                background: white !important;
                border: 1px solid #eceff1 !important;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
                padding: 12px 16px !important;
                border-radius: 10px !important;
                transition: box-shadow 0.15s;
            }
            .metric-card:hover {
                box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
            }
            .metric-label {
                font-size: 12px;
                color: #757575;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 4px;
                display: block;
            }
            .metric-value {
                font-size: 18px;
                font-weight: 600;
                color: #424242;
                display: block;
            }
            .metric-value-large {
                font-size: 28px;
                font-weight: bold;
                display: block;
                line-height: 1.2;
            }

            /* 状态点（与顶部一致） */
            .status-dot {
                display: inline-flex;
                align-items: center;
                margin-right: 6px;
            }
            .status-dot .dot {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: #9e9e9e;
                display: inline-block;
            }
            .status-dot.running .dot { background: #ff9800; animation: pulse 1.2s infinite; }
            .status-dot.error .dot { background: #f44336; }
            .status-dot .dot,
            .status-pill .dot { animation: none; }
            .status-dot.running .dot { animation: pulse 1.2s infinite; }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.4; }
                100% { opacity: 1; }
            }

            .min-w-180 { min-width: 180px; }
            .min-w-200 { min-width: 200px; }

            /* ===== 搜索结果页面 ===== */
            .task-select { min-width: 280px; }

            .stat-card {
                background: white !important;
                border: 1px solid #eceff1 !important;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
                padding: 12px 16px !important;
                border-radius: 10px !important;
                min-width: 110px;
                flex: 1;
                transition: box-shadow 0.15s;
            }
            .stat-card:hover {
                box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
            }
            .stat-card.stat-total {
                background: linear-gradient(135deg, #f7fbf8 0%, #eef5ff 100%) !important;
                border: 1px solid #d4e4f7 !important;
            }
            .stat-label {
                font-size: 11px;
                color: #757575;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                display: block;
                margin-bottom: 4px;
            }
            .stat-value-lg {
                font-size: 24px;
                font-weight: bold;
                display: block;
                line-height: 1.2;
            }

            .filter-card {
                background: #fafafa !important;
                border: 1px solid #eceff1 !important;
                box-shadow: none !important;
                padding: 12px 16px !important;
                border-radius: 10px !important;
            }
            .filter-select { min-width: 140px; }
            .filter-input { min-width: 200px; flex: 1; }

            /* 表格 + 详情抽屉布局 */
            .results-layout {
                align-items: flex-start;
            }
            .results-table-col {
                flex: 1;
                min-width: 0;
            }
            .results-detail-col {
                width: 380px;
                min-width: 380px;
                max-width: 380px;
                position: sticky;
                top: 16px;
            }
            .results-detail-col.hidden { display: none; }

            .results-table .q-table {
                border: 1px solid #eceff1;
                border-radius: 10px;
            }
            .results-table .q-table tbody tr {
                cursor: pointer;
            }
            .results-table .q-table tbody tr:hover {
                background: #f0f7f4 !important;
            }
            .results-table .q-table thead th {
                font-weight: 600;
                color: #424242;
                background: #f7f9fa;
            }

            /* 详情卡片 */
            .detail-card {
                background: white !important;
                border: 1px solid #eceff1 !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
                padding: 18px 22px !important;
                border-radius: 12px !important;
                max-height: calc(100vh - 200px);
                overflow-y: auto;
            }

            .detail-avatar {
                width: 80px !important;
                height: 80px !important;
                border-radius: 50% !important;
                object-fit: cover;
                margin: 8px 0;
                border: 2px solid #1f7a4d;
            }

            .detail-section-label {
                font-size: 12px;
                font-weight: 600;
                color: #1f7a4d;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-top: 12px;
                margin-bottom: 4px;
                display: block;
                border-bottom: 1px solid #e0efe6;
                padding-bottom: 4px;
            }

            .detail-bio {
                font-size: 13px;
                color: #424242;
                white-space: pre-wrap;
                line-height: 1.5;
                background: #f7fbf8;
                padding: 8px 12px;
                border-radius: 6px;
                border-left: 3px solid #1f7a4d;
                display: block;
            }

            .detail-metric-card {
                background: #f7fbf8 !important;
                border: 1px solid #e0efe6 !important;
                box-shadow: none !important;
                padding: 8px 12px !important;
                border-radius: 8px !important;
                min-width: 90px;
                flex: 1;
            }
            .detail-metric-label {
                font-size: 10px;
                color: #757575;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                display: block;
            }
            .detail-metric-value {
                font-size: 16px;
                font-weight: 600;
                color: #1f7a4d;
                display: block;
                margin-top: 2px;
            }
        </style>
        """
    )

    # 当前选中页面状态
    current_page = {"name": "dashboard"}

    # ===== 顶部状态栏 =====
    with ui.header().classes("app-header items-center"):
        # 折叠按钮（用 button 包装图标，点击事件更可靠）
        collapse_btn = ui.button(icon="menu", color="white").props("flat dense round size=sm").classes("q-mr-md")

        ui.label("Mexico Creator Finder").classes("title")

        ui.space()

        # 状态指示
        ui.html('<span class="dot"></span>').classes("status-pill")
        status_label = ui.label("Instagram 未连接 · 空闲").classes("status-pill text-white")

        def update_status_label() -> None:
            env_user = _read_env_username()
            connected = bool(env_user)
            connected_text = "Instagram 已连接" if connected else "Instagram 未连接"

            if gui_state.is_running:
                status_label.text = f"{connected_text} · 任务运行中"
                status_label.classes(replace="status-pill running text-white")
            elif gui_state.last_error:
                status_label.text = f"{connected_text} · 错误"
                status_label.classes(replace="status-pill error text-white")
            else:
                status_label.text = f"{connected_text} · 空闲"
                status_label.classes(replace="status-pill text-white")

        ui.timer(1.0, update_status_label)

    # ===== 主体：左侧导航 + 右侧内容 =====
    with ui.row().classes("w-full no-wrap items-start"):
        # 左侧导航
        sidebar = ui.column().classes("app-sidebar")

        def rebuild_sidebar() -> None:
            sidebar.clear()
            with sidebar:
                # 品牌 header
                with ui.element("div").classes("app-sidebar-header"):
                    ui.label("Mexico Creator Finder").classes("brand")
                    ui.label("本地内容创作者发现工具").classes("subtitle")

                # 主导航
                ui.label("导航").classes("sidebar-section-label")
                nav_buttons: dict[str, Any] = {}
                for key, label, icon in NAV_ITEMS:
                    btn = (
                        ui.element("a")
                        .classes("nav-item")
                        .props('href="javascript:void(0)"')
                        .on("click", lambda _e, k=key: show_page(k))
                    )
                    with btn:
                        ui.icon(icon)
                        ui.label(label).classes("nav-label")
                    nav_buttons[key] = btn

                ui.element("div").classes("flex-1")  # 占位让设置靠底

                # 设置（靠底）
                ui.label("系统").classes("sidebar-section-label")
                settings_btn = (
                    ui.element("a")
                    .classes("nav-item")
                    .props('href="javascript:void(0)"')
                    .on("click", lambda _: show_page("settings"))
                )
                with settings_btn:
                    ui.icon("settings")
                    ui.label("设置").classes("nav-label")
                nav_buttons["settings"] = settings_btn

            # 高亮当前页
            _highlight_current(nav_buttons, current_page["name"])

        # 右侧内容区
        content = ui.column().classes("app-content")

        def show_page(name: str) -> None:
            current_page["name"] = name
            content.clear()
            with content:
                # 页面标题行
                with ui.row().classes("page-title-row"):
                    ui.label(_page_title(name)).classes("page-title")

                # 渲染对应页面
                if name == "dashboard":
                    build_dashboard_page()
                elif name == "new_search":
                    build_new_search_page()
                elif name == "progress":
                    build_progress_page()
                elif name == "results":
                    build_results_page()
                elif name == "exclusion":
                    build_exclusion_page()
                elif name == "export":
                    build_export_page()
                elif name == "settings":
                    build_settings_page()

            rebuild_sidebar()  # 刷新高亮

        # 折叠按钮
        sidebar_collapsed = {"state": False}

        def toggle_sidebar() -> None:
            sidebar_collapsed["state"] = not sidebar_collapsed["state"]
            if sidebar_collapsed["state"]:
                sidebar.classes(add="collapsed")
                collapse_btn.icon = "chevron_right"
            else:
                sidebar.classes(remove="collapsed")
                collapse_btn.icon = "menu"

        collapse_btn.on("click", toggle_sidebar)

        # 初始化
        rebuild_sidebar()
        show_page("dashboard")


def _page_title(name: str) -> str:
    """根据 page key 返回页面中文标题。"""
    titles = {
        "dashboard": "概览",
        "new_search": "新建搜索",
        "progress": "搜索任务",
        "results": "博主结果",
        "exclusion": "排除名单",
        "export": "导出记录",
        "settings": "设置",
    }
    return titles.get(name, name)


def _highlight_current(nav_buttons: dict, current: str) -> None:
    """高亮当前选中的导航项。"""
    for key, btn in nav_buttons.items():
        if key == current:
            btn.classes(add="active")
        else:
            btn.classes(remove="active")


def _read_env_username() -> str:
    """读取 .env 中的 IG_USERNAME（用于状态显示）。"""
    import os
    import sys
    from pathlib import Path

    # 优先从环境变量读取（运行时已同步）
    user = os.environ.get("IG_USERNAME", "").strip()
    if user:
        return user

    # 回退到 .env 文件
    if getattr(sys, "frozen", False):
        env_path = Path(sys.executable).resolve().parent / ".env"
    else:
        env_path = Path(".env").resolve()

    if not env_path.exists():
        return ""

    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("IG_USERNAME="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def main() -> None:
    """启动 NiceGUI 服务。"""
    from nicegui import ui

    build_app()
    logger.info("starting NiceGUI on http://127.0.0.1:8080")
    ui.run(
        title="Mexico Creator Finder",
        host="127.0.0.1",
        port=8080,
        reload=False,
        show=False,
        favicon="🇲🇽",
    )


if __name__ == "__main__":
    main()
