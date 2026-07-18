"""Typer CLI 入口。

命令：
- search：搜索创作者
- task-status：查看任务状态
- export：导出结果
- validate-config：校验配置
- show-config：显示配置（脱敏）
- clear-local-data：清除本地数据
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm
from rich.table import Table

from app import __version__
from app.config import (
    Settings,
    build_settings,
    load_hashtags,
    to_display_dict,
    validate_settings,
)
from app.exceptions import (
    FinderError,
    InstagramClientError,
    SecurityStopError,
)
from app.logging_config import get_logger, setup_logging
from app.models import TaskCheckpoint

logger = get_logger("cli")
console = Console()

# 初始化日志（CLI 启动时确保日志已配置）
setup_logging(level="INFO")

app = typer.Typer(
    name="mexico-finder",
    help="Mexico Instagram Creator Finder — 墨西哥 Instagram 内容创作者发现工具",
    no_args_is_help=True,
    add_completion=False,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _generate_task_id() -> str:
    return f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _print_no_credentials_hint() -> None:
    """未设置环境变量时显示清晰提示。"""
    console.print(
        Panel.fit(
            "[bold red]未检测到 Instagram 账号凭据[/bold red]\n\n"
            "请在项目根目录创建 `.env` 文件并配置：\n\n"
            "  IG_USERNAME=your_username\n"
            "  IG_PASSWORD=your_password\n\n"
            "或通过环境变量设置：\n\n"
            "  PowerShell:  $env:IG_USERNAME='your_username'; $env:IG_PASSWORD='your_password'\n"
            "  CMD:         set IG_USERNAME=your_username && set IG_PASSWORD=your_password\n\n"
            "[dim]注意：本项目仅读取公开数据，遇到平台限制会立即停止，不会绕过安全机制。[/dim]",
            title="凭据缺失",
            border_style="red",
        )
    )


def _get_settings(
    hashtags: list[str] | None = None,
    min_followers: int | None = None,
    max_followers: int | None = None,
    exclude: list[str] | None = None,
    resume: bool = False,
    reset_task: bool = False,
) -> Settings:
    """合并 CLI 参数到 settings。"""
    cli_overrides: dict = {}
    if hashtags:
        cli_overrides["hashtags"] = list(hashtags)
    if min_followers is not None:
        cli_overrides.setdefault("filters", {})["min_followers"] = min_followers
    if max_followers is not None:
        cli_overrides.setdefault("filters", {})["max_followers"] = max_followers
    if exclude:
        cli_overrides["exclude_files"] = list(exclude)
    if resume:
        cli_overrides["resume"] = True
    if reset_task:
        cli_overrides["reset_task"] = True

    return build_settings(cli_overrides=cli_overrides)


@app.command("validate-config")
def validate_config_cmd() -> None:
    """校验配置完整性。"""
    settings = build_settings()
    errors = validate_settings(settings)
    if not errors:
        console.print("[bold green]✓ 配置校验通过[/bold green]")
        table = Table(title="配置概览", show_header=False)
        table.add_row(
            "粉丝区间",
            f"{settings.filters.min_followers} - {settings.filters.max_followers}",
        )
        delay = settings.instagram.request_delay_min_seconds
        delay_max = settings.instagram.request_delay_max_seconds
        table.add_row("请求间隔", f"{delay}-{delay_max} 秒")
        table.add_row("最大 Hashtag 数", str(settings.discovery.max_hashtags))
        table.add_row("每 Hashtag 媒体数", str(settings.discovery.media_per_hashtag))
        table.add_row("最大候选账号数", str(settings.discovery.max_candidates))
        table.add_row("最大分析账号数", str(settings.discovery.max_profiles_to_analyze))
        table.add_row("近期内容数量", str(settings.analysis.recent_media_amount))
        table.add_row("断点续传", "启用" if settings.checkpoint.enabled else "禁用")
        table.add_row("导出格式", ", ".join(settings.output.formats))
        console.print(table)
    else:
        console.print("[bold red]✗ 配置校验失败[/bold red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(code=1)


@app.command("show-config")
def show_config_cmd() -> None:
    """显示最终合并后的配置（脱敏）。"""
    settings = build_settings()
    display = to_display_dict(settings)
    import json

    console.print_json(json.dumps(display, ensure_ascii=False, indent=2, default=str))


@app.command("task-status")
def task_status_cmd(
    task_id: str | None = typer.Option(None, "--task-id", help="任务 ID；不指定则显示最近任务"),
) -> None:
    """查看任务状态。"""
    from app.storage.checkpoint import load_checkpoint
    from app.storage.database import Database, TaskRow
    from app.storage.repositories import get_task

    settings = build_settings()
    db = Database(settings.checkpoint.database_file)
    session = db.get_session()
    try:
        if task_id is None:
            # 显示最近的任务
            from sqlalchemy import select

            stmt = select(TaskRow).order_by(TaskRow.updated_at.desc()).limit(5)
            rows = list(session.execute(stmt).scalars())
            if not rows:
                console.print("[yellow]当前没有任何任务记录[/yellow]")
                return
            table = Table(title="最近任务")
            table.add_column("任务 ID", style="cyan")
            table.add_column("状态")
            table.add_column("开始时间")
            table.add_column("更新时间")
            table.add_column("停止原因")
            for r in rows:
                table.add_row(
                    r.task_id,
                    r.status,
                    str(r.started_at) if r.started_at else "-",
                    str(r.updated_at) if r.updated_at else "-",
                    r.stop_reason or "-",
                )
            console.print(table)
            return

        cp = load_checkpoint(session, task_id)
        task = get_task(session, task_id)
        if cp is None and task is None:
            console.print(f"[yellow]未找到任务 {task_id}[/yellow]")
            return

        table = Table(title=f"任务状态: {task_id}")
        table.add_column("字段", style="cyan")
        table.add_column("值")
        if task:
            table.add_row("状态", task.status)
            table.add_row("开始时间", str(task.started_at) if task.started_at else "-")
            table.add_row("更新时间", str(task.updated_at) if task.updated_at else "-")
            table.add_row("完成时间", str(task.completed_at) if task.completed_at else "-")
            table.add_row("停止原因", task.stop_reason or "-")
        if cp:
            table.add_row("已完成 Hashtag", ", ".join(cp.completed_hashtags) or "-")
            table.add_row("已发现账号数", str(len(cp.discovered_usernames)))
            table.add_row("已分析账号数", str(len(cp.analyzed_usernames)))
            table.add_row("失败账号数", str(len(cp.failed_usernames)))
            if cp.failed_usernames:
                preview = ", ".join(cp.failed_usernames[:5])
                if len(cp.failed_usernames) > 5:
                    preview += "..."
                table.add_row("失败账号", preview)
        console.print(table)
    finally:
        session.close()
        db.close()


@app.command("search")
def search_cmd(
    hashtags: list[str] | None = typer.Option(None, "--hashtags", "-t", help="Hashtag 列表（不带 #）"),  # noqa: B008
    min_followers: int | None = typer.Option(None, "--min-followers", help="最小粉丝数"),
    max_followers: int | None = typer.Option(None, "--max-followers", help="最大粉丝数"),
    exclude: list[str] | None = typer.Option(None, "--exclude", "-e", help="排除名单文件路径或用户名（可多次指定）"),  # noqa: B008
    resume: bool = typer.Option(False, "--resume", help="恢复上次任务"),
    reset_task: bool = typer.Option(False, "--reset-task", help="重置任务后重新开始"),
) -> None:
    """搜索墨西哥 Instagram 内容创作者。"""
    settings = _get_settings(hashtags, min_followers, max_followers, exclude, resume, reset_task)

    # 检查凭据
    if not settings.ig_username or not settings.ig_password:
        _print_no_credentials_hint()
        raise typer.Exit(code=1)

    # 校验配置
    errors = validate_settings(settings)
    if errors:
        console.print("[bold red]配置校验失败：[/bold red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(code=1)

    # 加载默认 Hashtag（如未指定）
    if not settings.hashtags:
        hashtags_list = load_hashtags(settings.config_dir)
    else:
        hashtags_list = settings.hashtags

    console.print(
        Panel.fit(
            f"[bold]Mexico Instagram Creator Finder[/bold] v{__version__}\n"
            f"Hashtag 数: {len(hashtags_list)}  "
            f"粉丝区间: {settings.filters.min_followers}-{settings.filters.max_followers}\n"
            f"最大候选账号: {settings.discovery.max_candidates}  "
            f"最大分析账号: {settings.discovery.max_profiles_to_analyze}",
            title="开始搜索",
            border_style="green",
        )
    )

    # 调用主流程
    try:
        _run_search_pipeline(settings, hashtags_list)
    except SecurityStopError as e:
        console.print(
            Panel.fit(
                f"[bold red]安全停止[/bold red]\n\n原因: {e.reason}\n\n"
                f"已保存断点，可使用 [cyan]--resume[/cyan] 恢复任务。",
                title="任务停止",
                border_style="red",
            )
        )
        raise typer.Exit(code=2) from None
    except InstagramClientError as e:
        console.print(f"[bold red]Instagram 调用失败：[/bold red] {e}")
        raise typer.Exit(code=3) from None
    except FinderError as e:
        console.print(f"[bold red]运行失败：[/bold red] {e}")
        raise typer.Exit(code=4) from None


def _run_search_pipeline(settings: Settings, hashtags_list: list[str]) -> None:
    """串联主流程：登录 → 发现 → 去重 → 排除 → 资料 → 筛选 → 分析 → 评分 → 存储 → 导出。"""
    from sqlalchemy import select

    from app.analysis.account_classifier import classify_account_type
    from app.analysis.contact_extractor import extract_contacts
    from app.analysis.media_metrics import (
        analyze_media_metrics,
        extract_recent_captions,
        extract_recent_hashtags,
    )
    from app.analysis.mexico_detector import detect_mexico_signal
    from app.analysis.niche_classifier import classify_niche
    from app.analysis.scoring import compute_score
    from app.discovery.deduplication import deduplicate_candidates
    from app.discovery.hashtag import discover_from_hashtags
    from app.discovery.seeds import (
        ExclusionEntry,
        apply_exclusion,
        parse_exclude_paths,
        parse_exclude_strings,
    )
    from app.export import export_records
    from app.instagram.client import InstagramClient
    from app.storage.checkpoint import (
        is_user_analyzed,
        load_checkpoint,
        mark_hashtag_completed,
        mark_usernames_analyzed,
        record_failed_username,
        reset_task,
        save_checkpoint,
        update_status,
    )
    from app.storage.database import Database, TaskRow
    from app.storage.repositories import (
        load_all_records,
        upsert_account_type,
        upsert_candidate,
        upsert_contact,
        upsert_media_stats,
        upsert_mexico_signal,
        upsert_niche,
        upsert_profile,
        upsert_score,
        upsert_task,
    )

    # 任务 ID
    task_id = _generate_task_id()
    db = Database(settings.checkpoint.database_file)
    session = db.get_session()

    # 恢复任务
    if settings.resume:
        cp = load_checkpoint(session, task_id)
        if cp is None:
            # 找最近一个未完成的任务
            stmt = (
                select(TaskRow)
                .where(TaskRow.status.in_(["running", "paused", "stopped"]))
                .order_by(TaskRow.updated_at.desc())
                .limit(1)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is not None:
                task_id = row.task_id
                cp = load_checkpoint(session, task_id)
                console.print(f"[cyan]恢复任务 {task_id}[/cyan]")

    if settings.reset_task:
        reset_task(session, task_id)
        console.print(f"[yellow]已重置任务 {task_id}[/yellow]")

    # 初始化任务
    now = _utcnow()
    upsert_task(session, task_id, status="running", started_at=now)
    cp = load_checkpoint(session, task_id) or TaskCheckpoint(task_id=task_id, status="running", started_at=now)
    cp.status = "running"
    save_checkpoint(session, cp)

    try:
        # 1. 登录
        console.print("[bold]阶段 1/6: 登录 Instagram...[/bold]")
        client = InstagramClient(settings)
        client.login_from_env()

        # 2. 发现候选账号
        console.print("[bold]阶段 2/6: 从 Hashtag 发现候选账号...[/bold]")
        # 跳过已完成的 Hashtag
        completed_ht = set(cp.completed_hashtags)
        pending_ht = [h for h in hashtags_list if h.lower().lstrip("#") not in completed_ht]
        if not pending_ht:
            console.print("[yellow]所有 Hashtag 已完成，跳过发现阶段[/yellow]")
            candidates = []
        else:
            console.print(f"待处理 Hashtag: {len(pending_ht)} 个")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                progress_task = progress.add_task("发现候选...", total=len(pending_ht))

                def on_done(tag: str, count: int) -> None:
                    progress.advance(progress_task)
                    mark_hashtag_completed(session, task_id, tag)

                candidates = discover_from_hashtags(client, settings, pending_ht, on_hashtag_done=on_done)

        # 3. 去重
        console.print(f"[bold]阶段 3/6: 去重...[/bold]  候选数: {len(candidates)}")
        candidates = deduplicate_candidates(candidates)

        # 4. 应用排除名单
        exclusion_entries: list[ExclusionEntry] = []
        if settings.exclude_files:
            # 区分文件路径与字符串
            file_paths = [p for p in settings.exclude_files if Path(p).exists()]
            str_items = [p for p in settings.exclude_files if not Path(p).exists()]
            exclusion_entries.extend(parse_exclude_paths(file_paths))
            exclusion_entries.extend(parse_exclude_strings(str_items))

        kept_candidates, excluded_candidates = apply_exclusion(candidates, exclusion_entries)
        console.print(f"排除: {len(excluded_candidates)}  保留: {len(kept_candidates)}")

        # 保存候选到数据库
        for c in kept_candidates:
            upsert_candidate(session, c, task_id)
        for c in excluded_candidates:
            upsert_candidate(
                session,
                c,
                task_id,
                excluded=True,
                exclusion_source="exclude_list",
                exclusion_reason="用户排除名单匹配",
            )

        # 5. 资料获取 + 筛选 + 分析
        console.print(f"[bold]阶段 4/6: 获取资料与分析...[/bold]  待分析: {len(kept_candidates)}")
        analyzed_count = 0
        skipped_count = 0
        error_count = 0

        # 应用 max_profiles_to_analyze 上限
        to_analyze = kept_candidates[: settings.discovery.max_profiles_to_analyze]
        # 跳过已分析
        to_analyze = [c for c in to_analyze if not is_user_analyzed(session, task_id, c.username)]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            progress_task = progress.add_task("分析账号...", total=len(to_analyze))
            for candidate in to_analyze:
                username = candidate.username
                try:
                    # 获取资料
                    profile = client.user_info_by_username(username)

                    # 粉丝范围筛选
                    followers = profile.follower_count or 0
                    if followers < settings.filters.min_followers or followers > settings.filters.max_followers:
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue

                    # 私密账号筛选
                    if settings.filters.require_public_account and profile.is_private:
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue

                    # 获取近期内容
                    medias = client.user_medias(username, amount=settings.analysis.recent_media_amount)

                    # 分析
                    metrics = analyze_media_metrics(medias, settings)
                    captions = extract_recent_captions(medias, max_length=settings.analysis.maximum_caption_length)
                    media_hashtags = extract_recent_hashtags(medias)

                    mexico = detect_mexico_signal(
                        profile,
                        source_hashtags=candidate.source_hashtags,
                        recent_captions=captions,
                    )
                    niche = classify_niche(
                        profile,
                        source_hashtags=candidate.source_hashtags,
                        recent_captions=captions,
                        recent_media_hashtags=media_hashtags,
                    )
                    account_type = classify_account_type(profile, source_hashtags=candidate.source_hashtags)
                    contact = extract_contacts(profile)
                    score = compute_score(
                        profile,
                        mexico,
                        niche,
                        metrics,
                        contact,
                        account_type,
                        min_followers=settings.filters.min_followers,
                        max_followers=settings.filters.max_followers,
                        minimum_median_reel_views=settings.filters.minimum_median_reel_views,
                        maximum_days_since_last_post=settings.filters.maximum_days_since_last_post,
                    )

                    # 墨西哥信号筛选
                    if settings.filters.require_mexico_signal and mexico.mexico_confidence_score < 0.4:
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue

                    # 品牌/媒体筛选
                    if settings.filters.exclude_brands and account_type.account_type == "brand":
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue
                    if settings.filters.exclude_media_accounts and account_type.account_type in ("media", "news"):
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue

                    # 停更筛选
                    if (
                        metrics.days_since_last_post is not None
                        and metrics.days_since_last_post > settings.filters.maximum_days_since_last_post
                    ):
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue

                    # 最低 Reels 中位播放量筛选
                    if (
                        settings.filters.minimum_median_reel_views > 0
                        and metrics.reels_view_data_available == "available"
                        and metrics.median_visible_reel_views is not None
                        and metrics.median_visible_reel_views < settings.filters.minimum_median_reel_views
                    ):
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue

                    # 最低近期内容数量
                    if metrics.recent_media_checked < settings.filters.minimum_recent_media_count:
                        progress.advance(progress_task)
                        skipped_count += 1
                        continue

                    # 保存
                    upsert_profile(session, profile, task_id)
                    upsert_media_stats(session, metrics, task_id, username)
                    upsert_mexico_signal(session, mexico, task_id, username)
                    upsert_niche(session, niche, task_id, username)
                    upsert_account_type(session, account_type, task_id, username)
                    upsert_contact(session, contact, task_id, username)
                    upsert_score(session, score, task_id, username)
                    analyzed_count += 1
                    mark_usernames_analyzed(session, task_id, [username])

                    progress.advance(progress_task)

                except SecurityStopError:
                    raise
                except Exception as e:
                    error_count += 1
                    record_failed_username(session, task_id, username, str(e))
                    logger.error("analyze %s failed: %s", username, e)
                    progress.advance(progress_task)

        console.print(f"已分析: {analyzed_count}  已跳过: {skipped_count}  错误: {error_count}")

        # 6. 导出
        console.print("[bold]阶段 5/6: 导出结果...[/bold]")
        records = load_all_records(session, task_id)
        results = export_records(records, settings.output.directory, settings.output.formats, task_id=task_id)
        for fmt, path in results.items():
            console.print(f"  {fmt.upper()}: {path}")

        # 完成
        console.print("[bold]阶段 6/6: 任务完成[/bold]")
        update_status(session, task_id, "completed")
        upsert_task(session, task_id, status="completed", completed_at=_utcnow())

    except SecurityStopError as e:
        update_status(session, task_id, "stopped", stop_reason=e.reason)
        upsert_task(session, task_id, status="stopped", stop_reason=e.reason, completed_at=_utcnow())
        raise
    except Exception as e:
        update_status(session, task_id, "failed", stop_reason=str(e))
        upsert_task(session, task_id, status="failed", stop_reason=str(e), completed_at=_utcnow())
        raise
    finally:
        session.close()
        db.close()


@app.command("export")
def export_cmd(
    task_id: str | None = typer.Option(None, "--task-id", help="任务 ID；不指定则导出所有任务的结果"),
    formats: list[str] | None = typer.Option(None, "--formats", "-f", help="导出格式（csv/json/xlsx）"),  # noqa: B008
) -> None:
    """导出已分析的结果。"""
    from sqlalchemy import select

    from app.export import export_records
    from app.storage.database import Database, ProfileRow
    from app.storage.repositories import load_all_records

    settings = build_settings()
    fmt_list = formats or settings.output.formats
    db = Database(settings.checkpoint.database_file)
    session = db.get_session()
    try:
        records = []
        if task_id:
            records = load_all_records(session, task_id)

        if not records:
            # 未指定任务或该任务无记录：加载所有任务的记录
            console.print("[yellow]未找到指定任务的记录，尝试加载全部任务[/yellow]")
            stmt = select(ProfileRow.task_id).distinct()
            task_ids = list(session.execute(stmt).scalars())
            for tid in task_ids:
                records.extend(load_all_records(session, tid))

        if not records:
            console.print("[yellow]没有可导出的记录[/yellow]")
            raise typer.Exit(code=1)

        results = export_records(records, settings.output.directory, fmt_list, task_id=task_id)
        console.print("[bold green]导出完成[/bold green]")
        for fmt, path in results.items():
            console.print(f"  {fmt.upper()}: {path}")
    finally:
        session.close()
        db.close()


@app.command("clear-local-data")
def clear_local_data_cmd(
    confirm: bool = typer.Option(False, "--yes", "-y", help="跳过确认提示"),
) -> None:
    """清除本地数据（SQLite、Session、输出文件）。"""
    if not confirm:
        if not Confirm.ask("确认清除所有本地数据？此操作不可恢复（SQLite、Session、输出文件）"):
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit(code=0)

    settings = build_settings()
    cleared: list[str] = []

    # 删除数据库
    db_path = Path(settings.checkpoint.database_file)
    if db_path.exists():
        db_path.unlink()
        cleared.append(f"数据库: {db_path}")

    # 删除 Session
    from app.instagram.session import delete_session

    session_path = Path(settings.instagram.session_file)
    if session_path.exists():
        delete_session(session_path)
        cleared.append(f"Session: {session_path}")

    # 删除输出目录内容
    out_dir = Path(settings.output.directory)
    if out_dir.exists():
        for f in out_dir.glob("*"):
            if f.is_file():
                f.unlink()
        cleared.append(f"输出目录: {out_dir}")

    if cleared:
        console.print("[bold green]已清除：[/bold green]")
        for c in cleared:
            console.print(f"  - {c}")
    else:
        console.print("[yellow]无可清除的本地数据[/yellow]")


if __name__ == "__main__":
    app()
