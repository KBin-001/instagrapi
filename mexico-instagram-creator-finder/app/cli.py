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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="使用预定义示例数据测试完整流程，不登录 Instagram、不联网",
    ),
) -> None:
    """搜索墨西哥 Instagram 内容创作者。"""
    settings = _get_settings(hashtags, min_followers, max_followers, exclude, resume, reset_task)

    # dry-run 模式跳过凭据检查
    if not dry_run:
        # 检查凭据
        if not settings.ig_username or not settings.ig_password:
            _print_no_credentials_hint()
            raise typer.Exit(code=1)

    # 校验配置（dry-run 模式跳过凭据检查）
    errors = validate_settings(settings, skip_credentials=dry_run)
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

    mode_label = " [cyan][DRY-RUN 示例数据][/cyan]" if dry_run else ""
    console.print(
        Panel.fit(
            f"[bold]Mexico Instagram Creator Finder[/bold] v{__version__}\n"
            f"Hashtag 数: {len(hashtags_list)}  "
            f"粉丝区间: {settings.filters.min_followers}-{settings.filters.max_followers}\n"
            f"最大候选账号: {settings.discovery.max_candidates}  "
            f"最大分析账号: {settings.discovery.max_profiles_to_analyze}{mode_label}",
            title="开始搜索",
            border_style="green",
        )
    )

    # 调用 SearchService 执行核心流程
    from app.services import SearchService
    from app.services.domain import (
        STAGE_COMPLETED,
        STAGE_DEDUPLICATION,
        STAGE_DISCOVERY,
        STAGE_EXCLUSION,
        STAGE_EXPORT,
        STAGE_LOGIN,
        STAGE_PROFILE_ANALYSIS,
        CancellationToken,
        SearchConfig,
        SearchProgress,
        TaskStatus,
    )

    config = SearchConfig(
        settings=settings,
        hashtags=hashtags_list,
        dry_run=dry_run,
        resume=settings.resume,
        reset_task=settings.reset_task,
    )
    token = CancellationToken()

    # CLI 进度展示：根据 stage 切换 Rich Progress
    current_progress: Progress | None = None
    current_task_id: int | None = None

    def on_progress(p: SearchProgress) -> None:
        nonlocal current_progress, current_task_id

        # 阶段切换
        if p.stage == STAGE_LOGIN:
            console.print(f"[bold]阶段 1/6: {p.message}...[/bold]")
        elif p.stage == STAGE_DISCOVERY:
            if current_progress is None:
                console.print("[bold]阶段 2/6: 从 Hashtag 发现候选账号...[/bold]")
                console.print(f"待处理 Hashtag: {p.hashtags_total - p.hashtags_completed} 个")
                current_progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
                )
                current_progress.start()
                current_task_id = current_progress.add_task("发现候选...", total=p.hashtags_total or 1)
            if current_task_id is not None and current_progress is not None:
                current_progress.update(
                    current_task_id,
                    completed=p.hashtags_completed,
                    description=f"#{p.current_hashtag or ''} {p.message}",
                )
        elif p.stage == STAGE_DEDUPLICATION:
            if current_progress is not None:
                current_progress.stop()
                current_progress = None
                current_task_id = None
            console.print(f"[bold]阶段 3/6: 去重...[/bold]  {p.message}")
        elif p.stage == STAGE_EXCLUSION:
            console.print(f"[bold]阶段 4/6: 应用排除名单...[/bold]  {p.message}")
        elif p.stage == STAGE_PROFILE_ANALYSIS:
            if current_progress is None:
                console.print(f"[bold]阶段 5/6: 获取资料与分析...[/bold]  {p.message}")
                current_progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
                )
                current_progress.start()
                total_to_analyze = p.profiles_total or 1
                current_task_id = current_progress.add_task(
                    f"分析 @{p.current_username or ''}",
                    total=total_to_analyze,
                )
            if current_task_id is not None and current_progress is not None:
                # profiles_analyzed 已包含 matched + skipped + failed（在 service 中累加）
                current_progress.update(
                    current_task_id,
                    completed=p.profiles_analyzed,
                    description=f"分析 @{p.current_username or ''}（匹配 {p.profiles_matched}）",
                )
        elif p.stage == STAGE_EXPORT:
            if current_progress is not None:
                current_progress.stop()
                current_progress = None
                current_task_id = None
            console.print("[bold]阶段 6/6: 导出结果...[/bold]")
            console.print(f"已分析: {p.profiles_matched}  已跳过: {p.profiles_skipped}  错误: {p.profiles_failed}")
        elif p.stage == STAGE_COMPLETED:
            if current_progress is not None:
                current_progress.stop()
                current_progress = None
                current_task_id = None
            console.print(f"[bold green]{p.message}[/bold green]")

    try:
        result = SearchService().run(config, progress_callback=on_progress, cancellation_token=token)

        # 输出导出文件路径
        for fmt, path in result.exported_files.items():
            console.print(f"  {fmt.upper()}: {path}")

        # 根据状态返回退出码
        if result.status == TaskStatus.COMPLETED:
            console.print(f"[bold green]任务完成[/bold green]  任务 ID: {result.task_id}")
        elif result.status == TaskStatus.STOPPED:
            console.print(
                Panel.fit(
                    f"[bold red]安全停止[/bold red]\n\n原因: {result.stop_reason}\n\n"
                    f"已保存断点，可使用 [cyan]--resume[/cyan] 恢复任务。",
                    title="任务停止",
                    border_style="red",
                )
            )
            raise typer.Exit(code=2) from None
        elif result.status == TaskStatus.FAILED:
            console.print(f"[bold red]任务失败：[/bold red] {result.stop_reason}")
            raise typer.Exit(code=4) from None
        elif result.status in (TaskStatus.RATE_LIMITED, TaskStatus.VERIFICATION_REQUIRED):
            console.print(
                Panel.fit(
                    f"[bold red]任务停止[/bold red]\n\n原因: {result.stop_reason}\n\n"
                    f"已保存断点，可使用 [cyan]--resume[/cyan] 恢复任务。",
                    title="任务停止",
                    border_style="red",
                )
            )
            raise typer.Exit(code=2) from None
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

    # 删除浏览器扩展令牌
    from app.extension.token_store import ExtensionTokenStore

    token_path = ExtensionTokenStore.default_path()
    if token_path.exists():
        token_path.unlink()
        cleared.append(f"扩展令牌: {token_path}")

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
