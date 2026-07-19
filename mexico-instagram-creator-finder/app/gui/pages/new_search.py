"""新建搜索页面：核心页面，配置参数并启动 SearchService。

仅本地工具，不提供任何账号互动自动化功能。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import ui

from app.config import build_settings, load_hashtags, load_niche_keywords
from app.gui.state import gui_state

# ===== 搜索领域配置（与 niche_keywords.yaml 对应）=====
# (key, 显示名, 图标)
NICHE_OPTIONS: list[tuple[str, str, str]] = [
    ("perfume", "香水", "local_florist"),
    ("beauty", "美妆", "brush"),
    ("skincare", "护肤", "spa"),
    ("UGC", "UGC", "video_camera"),
    ("fashion", "穿搭", "checkroom"),
    ("lifestyle", "生活方式", "emoji_nature"),
]


def _count_excluded_usernames() -> int:
    """统计当前排除名单中的用户名数量（从 settings.exclude_files 解析）。"""
    settings = gui_state.settings
    if not settings.exclude_files:
        return 0
    try:
        from app.discovery.seeds import parse_exclude_paths, parse_exclude_strings

        file_paths = [p for p in settings.exclude_files if Path(p).exists()]
        str_items = [p for p in settings.exclude_files if not Path(p).exists()]
        entries = parse_exclude_paths(file_paths) + parse_exclude_strings(str_items)
        # 去重
        return len({e.username for e in entries})
    except Exception:  # noqa: BLE001 - UI 容错
        return 0


def _estimate_scale(hashtags: list[str], media_per_hashtag: int, max_profiles: int) -> str:
    """根据当前参数生成任务规模摘要。"""
    if not hashtags:
        return "请先输入至少一个 Hashtag。"
    n_ht = len(hashtags)
    n_media = n_ht * media_per_hashtag
    return f"本次任务将搜索 {n_ht} 个 Hashtag，最多读取 {n_media} 条公开内容，最多详细分析 {max_profiles} 个账号。"


def build_new_search_page() -> None:
    """构建「新建搜索」核心页面 UI。"""
    ui.label("配置参数后启动搜索任务。所有任务共享同一 SQLite 数据库（与 CLI 一致）。").classes(
        "text-grey-7 text-sm mb-4"
    )

    settings = gui_state.settings

    # ===== 搜索方式（单选）=====
    ui.label("搜索方式").classes("section-label")
    with ui.row().classes("w-full mt-1 mb-3"):
        # NiceGUI 2.24.2 dict 格式：{value: label}
        search_type = ui.toggle(
            options={
                "extension": "浏览器扩展发现",
                "hashtag": "Hashtag 搜索（实验）",
                "import": "导入用户名",
                "seed": "种子账号扩展",
            },
            value="extension",
        ).props("spread")

    # 模式说明
    with ui.row().classes("w-full items-center"):
        mode_hint = ui.label("").classes("text-grey-6 text-xs")

    # ===== 浏览器扩展使用说明卡片（默认显示）=====
    extension_card = ui.card().classes("w-full mb-3 hashtag-card")
    with extension_card:
        ui.label("浏览器扩展发现").classes("card-label")
        ui.label(
            "通过 Chrome 扩展在你已登录的 Instagram 官方网页中采集公开数据。\n"
            "本地 NiceGUI 不接收 Instagram 密码，不进行移动端 API 登录。"
        ).classes("text-grey-7 text-xs mb-2 whitespace-pre-wrap")
        ui.label("使用步骤：").classes("text-grey-8 text-sm mt-1")
        ui.label(
            "1. 在 Chrome 中登录 Instagram 官方网页\n"
            "2. 打开任意符合方向的创作者主页（如香水 / 美妆 / 护肤 / 穿搭博主）\n"
            "3. 点击浏览器工具栏的扩展图标，打开侧边栏\n"
            "4. 在侧边栏粘贴本地令牌（在「设置 → 浏览器扩展」可查看）\n"
            "5. 点击「保存到本地」，账号会自动进入本地任务\n"
            "6. 重复以上步骤采集更多账号，或前往「博主结果」页查看"
        ).classes("text-grey-7 text-sm whitespace-pre-wrap")
        ui.label(
            "本模式不调用 instagrapi，不会触发 ChallengeRequired 或 HTTP 429。"
        ).classes("text-green-7 text-xs mt-2")

    def on_type_change(_e: Any) -> None:
        v = search_type.value
        if v == "extension":
            mode_hint.text = "✓ 已选择浏览器扩展发现，按上方说明操作"
            mode_hint.classes(replace="text-green-7 text-xs")
            extension_card.set_visibility(True)
            hashtag_card.set_visibility(False)
        elif v == "hashtag":
            mode_hint.text = (
                "⚠️ 实验功能：instagrapi 移动端 API 登录已移除，"
                "仅 DRY-RUN 模式可运行真实搜索。可能触发 Instagram 验证。"
            )
            mode_hint.classes(replace="text-amber-7 text-xs")
            extension_card.set_visibility(False)
            hashtag_card.set_visibility(True)
        elif v == "import":
            mode_hint.text = "该模式将在后续版本支持；当前请使用浏览器扩展发现"
            mode_hint.classes(replace="text-amber-7 text-xs")
            extension_card.set_visibility(False)
            hashtag_card.set_visibility(True)
        else:
            mode_hint.text = "种子账号扩展将在后续版本支持；当前请使用浏览器扩展发现"
            mode_hint.classes(replace="text-amber-7 text-xs")
            extension_card.set_visibility(False)
            hashtag_card.set_visibility(True)

    search_type.on("update:model-value", on_type_change)
    # 初始化提示
    mode_hint.text = "✓ 已选择浏览器扩展发现，按上方说明操作"
    mode_hint.classes(replace="text-green-7 text-xs")

    # ===== 搜索领域 chips =====
    ui.label("搜索领域").classes("section-label")
    ui.label("点击领域标签自动加载对应 Hashtag 到下方输入框（可叠加选择）。").classes("text-grey-7 text-xs mb-1")
    niche_keywords_map = load_niche_keywords(settings.config_dir).get("niches", {}) or {}
    selected_niches: dict[str, bool] = {k: False for k, _, _ in NICHE_OPTIONS}

    niche_chips_row = ui.row().classes("w-full gap-2 mb-3 flex-wrap")
    with niche_chips_row:
        niche_chip_btns: dict[str, ui.button] = {}
        for key, label, icon in NICHE_OPTIONS:
            c = ui.button(label, icon=icon).props("outline rounded push dense size=sm color=green-8")
            niche_chip_btns[key] = c

    # ===== Hashtag 输入（核心卡片）=====
    hashtag_card = ui.card().classes("w-full mb-3 hashtag-card")
    hashtag_card.set_visibility(False)  # 默认隐藏，扩展模式下不显示
    with hashtag_card:
        ui.label("Hashtag").classes("card-label")
        ui.label("每行一个，不带 # 号；留空则使用 config/hashtags.yaml 默认值。").classes("text-grey-7 text-xs mb-1")
        default_tags = load_hashtags(settings.config_dir)
        hashtag_text = ui.textarea(
            placeholder="例如：perfumemexico\nfraganciasmexico",
            value="\n".join(default_tags) if default_tags else "",
        ).props("outlined rows=5 class=w-full")

    # 领域 chip 点击逻辑：追加该垂类的 hashtag 到 textarea
    def make_niche_click(niche_key: str) -> None:
        def _click(_e: Any) -> None:
            selected_niches[niche_key] = not selected_niches[niche_key]
            btn = niche_chip_btns[niche_key]
            if selected_niches[niche_key]:
                btn.props(remove="outline").props(add="solid unelevated color=green-8")
                # 追加该垂类的 hashtag
                niche_data = niche_keywords_map.get(niche_key, {}) or {}
                ht_list = niche_data.get("hashtags", []) or []
                current_lines = [h.strip() for h in (hashtag_text.value or "").splitlines() if h.strip()]
                for ht in ht_list:
                    if ht.lower() not in [c.lower() for c in current_lines]:
                        current_lines.append(ht)
                hashtag_text.value = "\n".join(current_lines)
                ui.notify(f"已添加「{niche_key}」领域 {len(ht_list)} 个 Hashtag", type="positive", position="top")
            else:
                btn.props(add="outline").props(remove="solid unelevated").props("color=green-8")
                # 移除该垂类的 hashtag
                niche_data = niche_keywords_map.get(niche_key, {}) or {}
                ht_list = [h.lower() for h in (niche_data.get("hashtags", []) or [])]
                current_lines = [h.strip() for h in (hashtag_text.value or "").splitlines() if h.strip()]
                kept = [c for c in current_lines if c.lower() not in ht_list]
                hashtag_text.value = "\n".join(kept)
                ui.notify(f"已移除「{niche_key}」领域 Hashtag", position="top")
            _update_scale()

        return _click

    for key, _, _ in NICHE_OPTIONS:
        niche_chip_btns[key].on("click", make_niche_click(key))

    # ===== 粉丝范围（双滑块 + 数字输入）=====
    ui.label("粉丝范围").classes("section-label mt-2")
    with ui.row().classes("w-full items-center mt-1"):
        min_followers = (
            ui.number(
                label="最小",
                value=settings.filters.min_followers,
                min=0,
                step=1000,
            )
            .props("outlined dense")
            .classes("followers-number")
        )
        ui.label("—").classes("mx-2")
        max_followers = (
            ui.number(
                label="最大",
                value=settings.filters.max_followers,
                min=0,
                step=1000,
            )
            .props("outlined dense")
            .classes("followers-number")
        )

    # 双滑块（视觉效果）
    FOLLOWERS_MIN = 0
    FOLLOWERS_MAX = 1_000_000
    with ui.row().classes("w-full items-center mt-1 mb-2"):
        slider_min = (
            ui.slider(
                min=FOLLOWERS_MIN,
                max=FOLLOWERS_MAX,
                step=1000,
                value=settings.filters.min_followers,
            )
            .props("color=green-8 label-always")
            .classes("flex-1")
        )
        ui.label("≤").classes("text-grey-6 mx-2")
        slider_max = (
            ui.slider(
                min=FOLLOWERS_MIN,
                max=FOLLOWERS_MAX,
                step=1000,
                value=settings.filters.max_followers,
            )
            .props("color=green-8 label-always")
            .classes("flex-1")
        )

    # 双向绑定：slider ↔ number input
    def on_slider_min(_e: Any) -> None:
        v = int(slider_min.value or 0)
        current_max = int(max_followers.value or 0)
        if v > current_max:
            v = current_max
            slider_min.value = v
        min_followers.value = v

    def on_slider_max(_e: Any) -> None:
        v = int(slider_max.value or 0)
        current_min = int(min_followers.value or 0)
        if v < current_min:
            v = current_min
            slider_max.value = v
        max_followers.value = v

    def on_min_input(_e: Any) -> None:
        slider_min.value = int(min_followers.value or 0)

    def on_max_input(_e: Any) -> None:
        slider_max.value = int(max_followers.value or 0)

    slider_min.on("update:model-value", on_slider_min)
    slider_max.on("update:model-value", on_slider_max)
    min_followers.on("update:model-value", on_min_input)
    max_followers.on("update:model-value", on_max_input)

    # ===== 最低 Reels 中位播放量 =====
    ui.label("最低 Reels 中位播放量").classes("section-label mt-2")
    min_reel_views = ui.number(
        value=settings.filters.minimum_median_reel_views,
        min=0,
        step=500,
    ).props("outlined dense class=w-full mt-1 mb-2")

    # ===== 最大分析账号 =====
    ui.label("最大分析账号").classes("section-label mt-2")
    max_profiles = ui.number(
        value=settings.discovery.max_profiles_to_analyze,
        min=1,
        max=500,
        step=10,
    ).props("outlined dense class=w-full mt-1 mb-3")

    # ===== 筛选条件复选框 =====
    ui.label("筛选条件").classes("section-label")
    with ui.row().classes("w-full gap-4 mt-1 mb-3 flex-wrap"):
        cb_public = ui.checkbox("只分析公开账号", value=settings.filters.require_public_account)
        cb_mexico = ui.checkbox("必须有墨西哥信号", value=settings.filters.require_mexico_signal)
        cb_no_brand = ui.checkbox(
            "排除品牌与商店", value=settings.filters.exclude_brands and settings.filters.exclude_media_accounts
        )
        cb_contact = ui.checkbox("必须有公开联系方式", value=False)
        cb_contact.tooltip("该筛选条件将在后续版本生效；当前作为标记展示")

    # ===== 排除名单状态 =====
    ui.label("排除名单").classes("section-label")
    excluded_count = _count_excluded_usernames()
    with ui.row().classes("w-full items-center mt-1 mb-3"):
        if excluded_count > 0:
            ui.icon("block").classes("text-green-7")
            ui.label(f"已加载 {excluded_count} 个账号").classes("text-green-7 text-sm")
        else:
            ui.icon("info").classes("text-grey-6")
            ui.label("未加载排除名单（可在「排除名单」页面或 .env 中配置）").classes("text-grey-6 text-sm")

    # ===== 高级选项（折叠）=====
    with ui.expansion("高级选项", icon="tune").classes("w-full mb-3").props("dense"):
        with ui.row().classes("w-full items-center gap-4"):
            dry_run_switch = ui.switch("DRY-RUN 模式（不登录 Instagram，用示例数据测试）", value=False)
        with ui.row().classes("w-full items-center gap-4"):
            resume_switch = ui.switch("恢复上次任务（--resume）", value=False)
            reset_switch = ui.switch("重置任务后重新开始（--reset-task）", value=False)

    # ===== 预计任务规模 =====
    scale_card = ui.card().classes("w-full mb-3 scale-card")
    with scale_card:
        with ui.row().classes("w-full items-center"):
            ui.icon("analytics").classes("text-green-7")
            ui.label("预计任务规模").classes("font-bold text-green-8")
        scale_label = ui.label("").classes("text-grey-8 text-sm mt-1")

    def _update_scale() -> None:
        raw = hashtag_text.value or ""
        hashtags = [h.strip().lstrip("#").lower() for h in raw.splitlines() if h.strip()]
        media_per_ht = settings.discovery.media_per_hashtag
        max_p = int(max_profiles.value or 1)
        scale_label.text = _estimate_scale(hashtags, media_per_ht, max_p)

    # 输入变化时刷新规模摘要
    hashtag_text.on("update:model-value", lambda _e: _update_scale())
    max_profiles.on("update:model-value", lambda _e: _update_scale())
    _update_scale()

    # ===== 启动/停止按钮 =====
    msg_label = ui.label("").classes("mt-2")

    with ui.row().classes("w-full justify-end items-center gap-2 mt-2"):
        stop_btn = ui.button("停止任务", color="red-5").props("outline unelevated")
        start_btn = ui.button("开始搜索", color="green-8").props("unelevinated icon=play_arrow")
        stop_btn.set_enabled(False)

    def update_buttons() -> None:
        if gui_state.is_running:
            start_btn.disable()
            stop_btn.enable()
        else:
            start_btn.enable()
            stop_btn.disable()

    ui.timer(0.5, update_buttons)

    def on_start() -> None:
        # 扩展模式：不启动 SearchService，提示用户去扩展操作
        if search_type.value == "extension":
            ui.notify(
                "浏览器扩展模式无需启动搜索。请在 Chrome 中打开 Instagram 主页并使用扩展采集。",
                type="info",
                position="top",
                timeout=6000,
            )
            msg_label.text = "请在 Chrome 扩展中采集账号，结果会自动进入本地数据库。"
            msg_label.classes(replace="text-blue-7")
            return

        # 解析 hashtag
        raw = hashtag_text.value or ""
        hashtags = [h.strip().lstrip("#").lower() for h in raw.splitlines() if h.strip()]
        if not hashtags:
            ui.notify("请输入至少一个 Hashtag", type="warning", position="top")
            return

        # 应用参数到 settings（克隆，避免污染原始）
        cli_overrides: dict = {
            "hashtags": hashtags,
            "filters": {
                "min_followers": int(min_followers.value or 0),
                "max_followers": int(max_followers.value or 0),
                "require_public_account": bool(cb_public.value),
                "require_mexico_signal": bool(cb_mexico.value),
                "exclude_brands": bool(cb_no_brand.value),
                "exclude_media_accounts": bool(cb_no_brand.value),
                "minimum_median_reel_views": int(min_reel_views.value or 0),
                # require_public_contact 为 UI 标记，当前 SearchService 暂未消费；
                # 通过 cli_overrides 传递以便后续版本扩展 FilterSettings 后自动生效。
                "require_public_contact": bool(cb_contact.value),
            },
            "discovery": {
                "max_profiles_to_analyze": int(max_profiles.value or 1),
            },
            "resume": bool(resume_switch.value),
            "reset_task": bool(reset_switch.value),
        }
        # 重建 settings，让 SearchService 拿到最新配置
        gui_state.settings = build_settings(cli_overrides=cli_overrides)

        ok, msg = gui_state.start_search(
            hashtags=hashtags,
            dry_run=bool(dry_run_switch.value),
            resume=bool(resume_switch.value),
            reset_task=bool(reset_switch.value),
        )
        if ok:
            ui.notify(msg, type="positive", position="top")
            msg_label.text = msg
            msg_label.classes(replace="text-green-7")
        else:
            ui.notify(msg, type="negative", position="top")
            msg_label.text = msg
            msg_label.classes(replace="text-red-7")

    def on_stop() -> None:
        ok, msg = gui_state.stop_search()
        ui.notify(msg, type=("positive" if ok else "warning"), position="top")
        msg_label.text = msg

    start_btn.on("click", lambda _: on_start())
    stop_btn.on("click", lambda _: on_stop())

    # ===== 提示 =====
    ui.separator().classes("my-4")
    with ui.expansion("使用提示", icon="lightbulb").classes("w-full").props("dense"):
        ui.label(
            "• DRY-RUN 模式不联网，使用预定义示例数据走完整流程，可随时测试 GUI。\n"
            "• 真实模式需要先在「设置」页面或 .env 配置 IG_USERNAME / IG_PASSWORD。\n"
            "• 启动后可前往「搜索任务」页面查看实时进度。\n"
            "• 任务运行中可点击「停止任务」请求取消，将保存断点后安全退出。\n"
            "• 点击「搜索领域」标签可快速加载该垂类的常用 Hashtag。"
        ).classes("text-grey-7 text-sm whitespace-pre-wrap")
