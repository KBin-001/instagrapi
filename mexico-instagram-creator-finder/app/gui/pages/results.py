"""搜索结果页面：统计卡片 + 筛选栏 + 紧凑博主表格 + 右侧详情抽屉。

主表只显示 7 列（博主/粉丝/Reels中位播放/类型/墨西哥可信度/评分/联系方式），
点击行后右侧抽屉显示完整资料。避免主表变成 Excel。

数据源：SQLite（与 CLI 共用同一数据库）。
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.config import build_settings
from app.gui.state import gui_state

# 垂类中文映射
_NICHE_LABELS: dict[str, str] = {
    "perfume": "香水",
    "beauty": "美妆",
    "skincare": "护肤",
    "makeup": "彩妆",
    "fashion": "穿搭",
    "lifestyle": "生活方式",
    "UGC": "UGC",
    "general": "综合",
    "brand": "品牌",
    "media": "媒体",
    "agency": "经纪",
}

# 推荐级别颜色
_LEVEL_COLORS: dict[str, str] = {
    "A": "green-8",
    "B": "blue-6",
    "C": "amber-7",
    "D": "grey-6",
}


def _format_followers(n: Any) -> str:
    """粉丝数格式化：1.2K / 15K / 1.2M。"""
    if n is None:
        return "-"
    try:
        v = int(n)
    except (TypeError, ValueError):
        return str(n)
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(v)


def _format_views(n: Any) -> str:
    """播放量格式化。"""
    return _format_followers(n)


def _format_score(n: Any) -> str:
    if n is None:
        return "-"
    try:
        return str(int(n))
    except (TypeError, ValueError):
        return str(n)


def _format_confidence(n: Any) -> str:
    """墨西哥可信度：0-1 显示为百分比，0-100 直接显示。"""
    if n is None:
        return "-"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return str(n)
    if v <= 1.0:
        return f"{int(v * 100)}"
    return str(int(v))


def _format_contact(row: dict[str, Any]) -> str:
    """联系方式摘要：邮箱 / WhatsApp / 链接 / -。"""
    parts: list[str] = []
    if row.get("public_email"):
        parts.append("邮箱")
    if row.get("public_whatsapp_url"):
        parts.append("WhatsApp")
    if row.get("linktree_url") or row.get("beacons_url"):
        parts.append("链接树")
    if row.get("external_url"):
        parts.append("网站")
    if not parts:
        return "—"
    return " / ".join(parts)


def _niche_label(niche: str | None) -> str:
    if not niche:
        return "-"
    return _NICHE_LABELS.get(niche, niche)


def _load_tasks() -> list[tuple[str, str]]:
    """加载所有任务（task_id, status），按更新时间倒序。"""
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


def _load_records(task_id: str) -> list[dict[str, Any]]:
    """从数据库加载某任务的全部 CreatorRecord，转为扁平字典列表。"""
    from app.export.common import records_to_dicts, sort_records
    from app.storage.database import Database
    from app.storage.repositories import load_all_records

    settings = build_settings()
    db = Database(settings.checkpoint.database_file)
    session = db.get_session()
    try:
        records = load_all_records(session, task_id)
        sorted_records = sort_records(records)
        return records_to_dicts(sorted_records)
    finally:
        session.close()
        db.close()


def _compute_stats(records: list[dict[str, Any]]) -> dict[str, int | float]:
    """计算统计指标。"""
    if not records:
        return {
            "total": 0,
            "level_a": 0,
            "level_b": 0,
            "level_c": 0,
            "level_d": 0,
            "with_contact": 0,
            "avg_score": 0.0,
            "avg_followers": 0,
        }
    level_a = sum(1 for r in records if r.get("recommendation_level") == "A")
    level_b = sum(1 for r in records if r.get("recommendation_level") == "B")
    level_c = sum(1 for r in records if r.get("recommendation_level") == "C")
    level_d = sum(1 for r in records if r.get("recommendation_level") == "D")
    with_contact = sum(1 for r in records if r.get("has_public_contact"))
    scores = [r.get("total_score") or 0 for r in records]
    followers = [r.get("follower_count") or 0 for r in records]
    return {
        "total": len(records),
        "level_a": level_a,
        "level_b": level_b,
        "level_c": level_c,
        "level_d": level_d,
        "with_contact": with_contact,
        "avg_score": sum(scores) / len(scores) if scores else 0.0,
        "avg_followers": int(sum(followers) / len(followers)) if followers else 0,
    }


def _apply_filters(
    records: list[dict[str, Any]],
    *,
    level: str,
    niche: str,
    min_followers: int,
    min_score: int,
    keyword: str,
    match_status: str = "matched",
    review_status: str = "全部",
) -> list[dict[str, Any]]:
    """应用筛选条件。"""
    filtered: list[dict[str, Any]] = []
    keyword_lower = keyword.strip().lower() if keyword else ""
    for r in records:
        if match_status != "全部" and r.get("match_status", "incomplete") != match_status:
            continue
        if review_status == "pending" and r.get("review_status", "pending") != "pending":
            continue
        if review_status == "saved" and not r.get("in_library"):
            continue
        if review_status == "skipped" and r.get("review_status") != "skipped":
            continue
        if level != "全部" and r.get("recommendation_level") != level:
            continue
        if niche != "全部" and r.get("primary_niche") != niche:
            continue
        if (r.get("follower_count") or 0) < min_followers:
            continue
        if (r.get("total_score") or 0) < min_score:
            continue
        if keyword_lower:
            username = (r.get("username") or "").lower()
            full_name = (r.get("full_name") or "").lower()
            bio = (r.get("biography") or "").lower()
            if keyword_lower not in username and keyword_lower not in full_name and keyword_lower not in bio:
                continue
        filtered.append(r)
    return filtered


def _row_to_table(row: dict[str, Any]) -> dict[str, Any]:
    """将记录转换为主表显示用的字典（含格式化字段）。"""
    return {
        "username": row.get("username") or "",
        "username_display": f"@{row.get('username', '')}",
        "follower_count": row.get("follower_count") or 0,
        "follower_display": _format_followers(row.get("follower_count")),
        "median_visible_reel_views": row.get("median_visible_reel_views") or 0,
        "reels_display": _format_views(row.get("median_visible_reel_views")),
        "primary_niche": row.get("primary_niche") or "general",
        "niche_display": _niche_label(row.get("primary_niche")),
        "mexico_confidence_score": row.get("mexico_confidence_score") or 0,
        "mexico_display": _format_confidence(row.get("mexico_confidence_score")),
        "total_score": row.get("total_score") or 0,
        "score_display": _format_score(row.get("total_score")),
        "similarity_display": _format_score(row.get("similarity_score")),
        "recommendation_level": row.get("recommendation_level") or "D",
        "contact_summary": _format_contact(row),
        "activity_display": (
            "数据不可用" if row.get("days_since_last_post") is None else f"{row['days_since_last_post']} 天前"
        ),
        "match_status": row.get("match_status") or "incomplete",
        "filter_reasons": "；".join(row.get("filter_reasons") or []),
        "review_display": "已入库"
        if row.get("in_library")
        else {"pending": "待审核", "skipped": "已跳过"}.get(
            row.get("review_status"), row.get("review_status") or "待审核"
        ),
        "_full_record": row,  # 完整记录用于详情抽屉
    }


def build_results_page() -> None:
    """构建「博主结果」页面 UI。"""
    ui.label("默认显示全部可人工判断候选并按匹配分排序；可切换严格匹配视图。点击行查看完整资料。").classes(
        "text-grey-7 text-sm mb-4"
    )

    # 当前页面共享状态
    page_state: dict[str, Any] = {
        "records": [],  # 当前任务的全部记录
        "filtered": [],  # 筛选后
        "selected_username": None,
    }

    # ===== 任务选择 =====
    with ui.row().classes("w-full items-center mb-3"):
        ui.label("任务：").classes("font-bold text-grey-8")
        task_select = ui.select(options={}, label="选择任务").props("outlined dense").classes("task-select")
        refresh_tasks_btn = ui.button("刷新", icon="refresh").props("flat dense color=green-8")

    with ui.card().classes("w-full mb-3 filter-card"):
        ui.label("用自然语言重新匹配现有候选").classes("font-bold text-grey-8")
        ui.label("只在本地重新计算排序，不会再次访问 Instagram。").classes("text-grey-6 text-xs")
        with ui.row().classes("w-full items-center gap-2"):
            rerank_brief = (
                ui.input(
                    label="Brief",
                    placeholder="例如：墨西哥香水个人创作者，粉丝大于1万，必须有公开联系方式",
                )
                .props("outlined dense clearable")
                .classes("flex-1")
            )
            rerank_button = ui.button("重新匹配排序", icon="tune", color="green-8").props("unelevated")

    def rerank_existing_candidates() -> None:
        task_id = task_select.value
        brief = (rerank_brief.value or "").strip()
        if not task_id or not brief:
            ui.notify("请先选择任务并填写 Brief", type="warning", position="top")
            return
        from app.extension.models import TaskRerankPayload
        from app.extension.task_service import ExtensionTaskService

        try:
            result = ExtensionTaskService(settings=build_settings()).rerank_candidates(
                task_id,
                TaskRerankPayload(brief=brief),
            )
            page_state["records"] = _load_records(task_id)
            page_state["current_task"] = task_id
            render_table()
            ui.notify(
                f"已重新匹配 {result['profiles_reranked']} 个候选",
                type="positive",
                position="top",
            )
        except Exception as error:  # noqa: BLE001
            ui.notify(f"重新匹配失败：{error}", type="negative", position="top")

    rerank_button.on("click", lambda _: rerank_existing_candidates())

    # ===== 统计卡片 =====
    stats_container = ui.row().classes("w-full gap-3 mb-3 flex-wrap")

    def render_stats(stats: dict[str, int | float]) -> None:
        stats_container.clear()
        with stats_container:
            # 总数
            with ui.card().classes("stat-card stat-total"):
                ui.label("总博主数").classes("stat-label")
                ui.label(str(stats["total"])).classes("stat-value-lg text-green-8")
            # A 级
            with ui.card().classes("stat-card"):
                ui.label("A 级（重点）").classes("stat-label")
                ui.label(str(stats["level_a"])).classes("stat-value-lg text-green-8")
            # B 级
            with ui.card().classes("stat-card"):
                ui.label("B 级（值得）").classes("stat-label")
                ui.label(str(stats["level_b"])).classes("stat-value-lg text-blue-8")
            # C 级
            with ui.card().classes("stat-card"):
                ui.label("C 级（不足）").classes("stat-label")
                ui.label(str(stats["level_c"])).classes("stat-value-lg text-amber-7")
            # 有联系方式
            with ui.card().classes("stat-card"):
                ui.label("有联系方式").classes("stat-label")
                ui.label(str(stats["with_contact"])).classes("stat-value-lg text-purple-8")
            # 平均评分
            with ui.card().classes("stat-card"):
                ui.label("平均评分").classes("stat-label")
                ui.label(f"{stats['avg_score']:.1f}").classes("stat-value-lg text-grey-8")
            # 平均粉丝
            with ui.card().classes("stat-card"):
                ui.label("平均粉丝").classes("stat-label")
                ui.label(_format_followers(stats["avg_followers"])).classes("stat-value-lg text-grey-8")

    # ===== 筛选栏 =====
    with ui.card().classes("w-full mb-3 filter-card"):
        with ui.row().classes("w-full items-center flex-wrap gap-2"):
            ui.label("筛选：").classes("font-bold text-grey-8 text-sm")
            level_select = (
                ui.select(
                    options=["全部", "A", "B", "C", "D"],
                    value="全部",
                    label="推荐级别",
                )
                .props("outlined dense")
                .classes("filter-select")
            )
            match_select = (
                ui.select(
                    options={
                        "matched": "匹配达人",
                        "filtered": "被筛选",
                        "private": "私密账号",
                        "failed": "采集失败",
                        "discovered": "已发现待补全",
                        "incomplete": "数据补全中",
                        "全部": "全部",
                    },
                    value="全部",
                    label="匹配状态",
                )
                .props("outlined dense")
                .classes("filter-select")
            )
            niche_select = (
                ui.select(
                    options=[
                        "全部",
                        "perfume",
                        "beauty",
                        "skincare",
                        "makeup",
                        "fashion",
                        "lifestyle",
                        "UGC",
                        "general",
                    ],
                    value="全部",
                    label="垂类",
                )
                .props("outlined dense")
                .classes("filter-select")
            )
            review_select = (
                ui.select(
                    options={"全部": "全部审核状态", "pending": "待审核", "saved": "已入库", "skipped": "已跳过"},
                    value="全部",
                    label="达人库",
                )
                .props("outlined dense")
                .classes("filter-select")
            )
            min_followers_input = (
                ui.number(
                    label="最小粉丝",
                    value=0,
                    min=0,
                    step=1000,
                )
                .props("outlined dense")
                .classes("filter-select")
            )
            min_score_input = (
                ui.number(
                    label="最低评分",
                    value=0,
                    min=0,
                    max=100,
                    step=5,
                )
                .props("outlined dense")
                .classes("filter-select")
            )
            keyword_input = (
                ui.input(
                    label="关键词（用户名/姓名/Bio）",
                    placeholder="例如：alice",
                )
                .props("outlined dense")
                .classes("filter-input")
            )
            ui.button("应用筛选", color="green-8").props("unelevinated dense").on("click", lambda _: render_table())
            ui.button("重置", color="grey-6").props("flat dense").on("click", lambda _: reset_filters())

    def reset_filters() -> None:
        level_select.value = "全部"
        match_select.value = "全部"
        niche_select.value = "全部"
        review_select.value = "全部"
        min_followers_input.value = 0
        min_score_input.value = 0
        keyword_input.value = ""
        render_table()

    # ===== 表格区 + 详情抽屉 =====
    with ui.row().classes("w-full no-wrap items-start gap-3 results-layout"):
        # 左侧：表格
        table_container = ui.column().classes("results-table-col")
        count_label = ui.label("").classes("text-grey-7 text-sm mb-2")

        # 右侧：详情抽屉（默认隐藏）
        detail_container = ui.column().classes("results-detail-col hidden")

    def apply_review(record: dict[str, Any], action: str) -> None:
        task_id = task_select.value
        username = record.get("username")
        if not task_id or not username:
            return
        from app.config import build_settings
        from app.storage.database import Database
        from app.storage.repositories import save_creator_to_library, set_candidate_review_status

        database = Database(build_settings().checkpoint.database_file)
        session = database.get_session()
        try:
            if action == "save":
                save_creator_to_library(session, task_id, username)
                ui.notify(f"@{username} 已加入达人库", type="positive", position="top")
            else:
                set_candidate_review_status(session, task_id, username, "skipped")
                ui.notify(f"@{username} 已跳过", position="top")
        finally:
            session.close()
            database.close()
        page_state["records"] = _load_records(task_id)
        render_detail(None)
        render_table()

    # ===== 详情抽屉渲染 =====
    def render_detail(record: dict[str, Any] | None) -> None:
        """渲染右侧详情抽屉。"""
        detail_container.clear()
        if record is None:
            detail_container.classes(add="hidden")
            return
        detail_container.classes(remove="hidden")
        with detail_container:
            with ui.card().classes("w-full detail-card"):
                # 头部：用户名 + 关闭按钮
                with ui.row().classes("w-full items-center"):
                    ui.label(f"@{record.get('username', '')}").classes("text-xl font-bold text-green-8")
                    ui.space()
                    close_btn = ui.button(icon="close").props("flat dense round")
                    close_btn.on("click", lambda _: render_detail(None))

                # 姓名 + 推荐级别徽章
                with ui.row().classes("w-full items-center mt-1 mb-2"):
                    ui.label(record.get("full_name") or "").classes("text-grey-8")
                    level = record.get("recommendation_level") or "D"
                    level_color = _LEVEL_COLORS.get(level, "grey-6")
                    ui.badge(f"级别 {level}").props(f"color={level_color}")

                # 头像（如果有）
                pic_url = record.get("profile_pic_url")
                if pic_url:
                    ui.image(pic_url).classes("detail-avatar").props("round")

                # Bio
                bio = record.get("biography")
                if bio:
                    ui.label("Bio").classes("detail-section-label mt-2")
                    ui.label(bio).classes("detail-bio")

                # 关键指标网格
                ui.label("关键指标").classes("detail-section-label mt-3")
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    _detail_metric("粉丝", _format_followers(record.get("follower_count")))
                    _detail_metric("关注", _format_followers(record.get("following_count")))
                    _detail_metric("帖子数", str(record.get("media_count") or "-"))
                    _detail_metric("Reels 中位播放", _format_views(record.get("median_visible_reel_views")))
                    _detail_metric("Reels 最高播放", _format_views(record.get("maximum_visible_reel_views")))
                    _detail_metric("平均点赞", _format_views(record.get("median_likes")))
                    _detail_metric("停更天数", str(record.get("days_since_last_post") or "-"))
                    _detail_metric(
                        "发布频率",
                        f"{record.get('posting_frequency') or 0:.1f}/周" if record.get("posting_frequency") else "-",
                    )

                # 评分明细
                ui.label("评分明细").classes("detail-section-label mt-3")
                _detail_kv("本地相似度", _format_score(record.get("similarity_score")))
                _detail_kv("参考种子", record.get("reference_seed") or "-")
                _detail_kv("数据质量", record.get("data_quality_status") or "incomplete")
                score_breakdown = record.get("score_breakdown") or {}
                total = record.get("total_score") or 0
                with ui.row().classes("w-full items-center mb-1"):
                    ui.label("总分").classes("text-grey-7 text-sm w-24")
                    ui.label(str(int(total))).classes("text-lg font-bold text-green-8")
                if isinstance(score_breakdown, dict):
                    for k, v in score_breakdown.items():
                        with ui.row().classes("w-full items-start"):
                            ui.label(k).classes("text-grey-6 text-xs w-32")
                            ui.label(f"{v:.1f}" if isinstance(v, (int, float)) else str(v)).classes(
                                "text-grey-8 text-xs flex-1"
                            )
                reasons = record.get("recommendation_reasons") or []
                if reasons:
                    ui.label("推荐理由").classes("detail-section-label mt-2")
                    for r in reasons:
                        ui.label(f"• {r}").classes("text-grey-7 text-xs")

                ui.label("匹配与数据状态").classes("detail-section-label mt-3")
                _detail_kv("匹配状态", record.get("match_status") or "incomplete")
                filter_reasons = record.get("filter_reasons") or []
                _detail_kv("筛选原因", " / ".join(filter_reasons) if filter_reasons else "-")
                _detail_kv("发现来源", " / ".join(record.get("discovery_sources") or []) or "-")
                missing: list[str] = []
                if record.get("follower_count") is None:
                    missing.append("粉丝数")
                if record.get("days_since_last_post") is None:
                    missing.append("最后发布时间")
                if record.get("reels_view_data_available") == "not_visible":
                    missing.append("Reels 播放量不可见")
                elif record.get("reels_view_data_available") == "no_reels":
                    missing.append("没有发现 Reels")
                _detail_kv("数据缺失", " / ".join(missing) if missing else "无")

                with ui.row().classes("w-full gap-2 mt-3"):
                    ui.button("加入达人库", icon="star", color="green-8").on(
                        "click", lambda _, item=record: apply_review(item, "save")
                    )
                    ui.button("跳过", icon="skip_next", color="grey-6").props("outline").on(
                        "click", lambda _, item=record: apply_review(item, "skip")
                    )

                # 垂类与墨西哥信号
                ui.label("垂类与地区").classes("detail-section-label mt-3")
                _detail_kv("主垂类", _niche_label(record.get("primary_niche")))
                niche_scores = record.get("niche_scores") or {}
                if isinstance(niche_scores, dict) and niche_scores:
                    niche_str = " / ".join(f"{_niche_label(k)}: {v:.2f}" for k, v in niche_scores.items())
                    _detail_kv("垂类得分", niche_str)
                _detail_kv("国家", record.get("detected_country") or "-")
                _detail_kv("州", record.get("detected_state") or "-")
                _detail_kv("城市", record.get("detected_city") or "-")
                _detail_kv(
                    "墨西哥可信度",
                    _format_confidence(record.get("mexico_confidence_score")) + "%",
                )
                mexico_signals = record.get("mexico_signals") or []
                if mexico_signals:
                    _detail_kv("墨西哥信号", " / ".join(mexico_signals))

                # 账号类型
                ui.label("账号类型").classes("detail-section-label mt-3")
                _detail_kv("类型", record.get("account_type") or "-")
                _detail_kv(
                    "类型可信度",
                    f"{(record.get('account_type_confidence') or 0) * 100:.0f}%"
                    if record.get("account_type_confidence") is not None
                    else "-",
                )

                # 联系方式
                ui.label("公开联系方式").classes("detail-section-label mt-3")
                if record.get("public_email"):
                    _detail_kv("邮箱", record["public_email"])
                if record.get("public_whatsapp_url"):
                    _detail_kv("WhatsApp", record["public_whatsapp_url"])
                if record.get("external_url"):
                    _detail_kv("网站", record["external_url"])
                if record.get("linktree_url"):
                    _detail_kv("Linktree", record["linktree_url"])
                if record.get("beacons_url"):
                    _detail_kv("Beacons", record["beacons_url"])
                if not (
                    record.get("public_email")
                    or record.get("public_whatsapp_url")
                    or record.get("external_url")
                    or record.get("linktree_url")
                    or record.get("beacons_url")
                ):
                    ui.label("（无公开联系方式）").classes("text-grey-6 italic text-sm")

                # 主页链接
                profile_url = record.get("profile_url")
                if profile_url:
                    ui.label("Instagram 主页").classes("detail-section-label mt-3")
                    ui.link(profile_url, target=profile_url).classes("text-green-8 text-sm break-all")

    def _detail_metric(label: str, value: str) -> None:
        with ui.card().classes("detail-metric-card"):
            ui.label(label).classes("detail-metric-label")
            ui.label(value).classes("detail-metric-value")

    def _detail_kv(label: str, value: str) -> None:
        with ui.row().classes("w-full items-start"):
            ui.label(label).classes("text-grey-6 text-sm w-24")
            ui.label(str(value)).classes("text-grey-8 text-sm flex-1 break-all")

    # ===== 表格渲染 =====
    def render_table() -> None:
        task_id = task_select.value
        if not task_id:
            table_container.clear()
            with table_container:
                ui.label("请先选择一个任务").classes("text-grey-7")
            count_label.text = ""
            render_stats(_compute_stats([]))
            return

        # 首次加载任务时拉取全部记录
        if not page_state["records"] or page_state.get("current_task") != task_id:
            try:
                page_state["records"] = _load_records(task_id)
                page_state["current_task"] = task_id
            except Exception as e:  # noqa: BLE001
                table_container.clear()
                with table_container:
                    ui.label(f"加载失败：{e}").classes("text-red-7")
                return

        # 应用筛选
        filtered = _apply_filters(
            page_state["records"],
            level=level_select.value or "全部",
            niche=niche_select.value or "全部",
            min_followers=int(min_followers_input.value or 0),
            min_score=int(min_score_input.value or 0),
            keyword=keyword_input.value or "",
            match_status=match_select.value or "全部",
            review_status=review_select.value or "全部",
        )
        page_state["filtered"] = filtered

        # 更新统计（基于筛选后）
        render_stats(_compute_stats(filtered))
        count_label.text = f"共 {len(filtered)} 条记录（任务 {task_id}，总计 {len(page_state['records'])} 条）"

        table_container.clear()
        with table_container:
            if not filtered:
                ui.label("（无匹配记录，尝试调整筛选条件）").classes("text-grey-7 italic")
                return

            # 构建表格行
            table_rows = [_row_to_table(r) for r in filtered]

            # Quasar 列定义
            # 注意：format 字段必须是 JS 函数字符串或留空；Python lambda 无法 JSON 序列化。
            # 解决方案：在 _row_to_table 中预格式化好字符串字段，这里 field 直接指向字符串字段。
            # 数字列排序：用专门的 *_sort_key 字段（数字），通过 Quasar 的 field 函数无法实现，
            # 所以数字列 sortable=False，改由筛选栏的「最小粉丝」「最低评分」过滤。
            columns = [
                {
                    "name": "username_display",
                    "label": "博主",
                    "field": "username_display",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "follower_display",
                    "label": "粉丝",
                    "field": "follower_display",
                    "align": "right",
                    "sortable": False,
                },
                {
                    "name": "reels_display",
                    "label": "Reels中位播放",
                    "field": "reels_display",
                    "align": "right",
                    "sortable": False,
                },
                {
                    "name": "niche_display",
                    "label": "类型",
                    "field": "niche_display",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "mexico_display",
                    "label": "墨西哥可信度",
                    "field": "mexico_display",
                    "align": "right",
                    "sortable": False,
                },
                {
                    "name": "similarity_display",
                    "label": "相似度",
                    "field": "similarity_display",
                    "align": "right",
                    "sortable": False,
                },
                {
                    "name": "score_display",
                    "label": "评分",
                    "field": "score_display",
                    "align": "right",
                    "sortable": False,
                },
                {
                    "name": "contact_summary",
                    "label": "联系方式",
                    "field": "contact_summary",
                    "align": "left",
                    "sortable": False,
                },
                {
                    "name": "activity_display",
                    "label": "活跃状态",
                    "field": "activity_display",
                    "align": "left",
                    "sortable": False,
                },
                {
                    "name": "match_status",
                    "label": "匹配状态",
                    "field": "match_status",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "filter_reasons",
                    "label": "筛选原因",
                    "field": "filter_reasons",
                    "align": "left",
                    "sortable": False,
                },
                {
                    "name": "review_display",
                    "label": "达人库",
                    "field": "review_display",
                    "align": "left",
                    "sortable": True,
                },
            ]

            table = ui.table(
                columns=columns,
                rows=table_rows,
                row_key="username",
                pagination={"rowsPerPage": 25},
            )
            table.props(
                'flat dense :rows-per-page-options="[10, 25, 50, 100, 0]" selection="single" :selected="selected"'
            )
            table.classes("results-table")

            # 行点击事件 → 显示详情
            def on_row_click(e: Any) -> None:
                try:
                    row = e.args[1] if len(e.args) > 1 else None
                except (IndexError, TypeError):
                    row = None
                if row is None:
                    return
                # row 是字典，从中取出完整记录
                full = row.get("_full_record") if isinstance(row, dict) else None
                if full:
                    page_state["selected_username"] = full.get("username")
                    render_detail(full)

            table.on("row-click", on_row_click)

    # ===== 任务加载 =====
    def reload_tasks() -> None:
        try:
            tasks = _load_tasks()
            if not tasks:
                task_select.options = {}
                task_select.update()
                table_container.clear()
                with table_container:
                    ui.label("数据库中暂无任务，请先在「新建搜索」页面启动一个任务。").classes("text-grey-7")
                render_stats(_compute_stats([]))
                return
            # dict 格式：{value: label}
            options = {tid: f"{tid[:16]}... ({status})" for tid, status in tasks}
            task_select.options = options
            task_select.value = tasks[0][0]
            task_select.update()
            # 重置记录缓存，触发表格加载
            page_state["records"] = []
            page_state["current_task"] = None
            render_table()
        except Exception as e:  # noqa: BLE001
            ui.notify(f"加载任务列表失败：{e}", type="negative", position="top")

    # ===== 事件绑定 =====
    task_select.on("update:model-value", lambda _: render_table())
    refresh_tasks_btn.on("click", lambda _: reload_tasks())
    level_select.on("update:model-value", lambda _: render_table())
    niche_select.on("update:model-value", lambda _: render_table())
    min_followers_input.on("update:model-value", lambda _: render_table())
    min_score_input.on("update:model-value", lambda _: render_table())
    keyword_input.on("update:model-value", lambda _: render_table())

    # 首次加载
    reload_tasks()


# 防止 GUI 模式下 build_settings 慢加载导致的副作用
_ = gui_state  # 保留单例引用，避免被回收
