"""搜索服务：CLI 与 GUI 共用的核心搜索逻辑。

将原 CLI._run_search_pipeline 中的业务流程抽取为独立服务，
通过 SearchConfig / SearchProgress / CancellationToken / SearchResult 与展示层解耦。

遵守 AGENTS.md：
- 单实例、顺序请求、4-8 秒间隔
- 遇 SecurityStopError 立即停止并保存断点，不自动重试
- CancellationToken 实现协作式取消，不强制中断线程
- 日志脱敏，不输出密码/Cookie/Session
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.exceptions import SecurityStopError
from app.logging_config import get_logger
from app.models import TaskCheckpoint
from app.services.domain import (
    STAGE_COMPLETED,
    STAGE_DEDUPLICATION,
    STAGE_DISCOVERY,
    STAGE_EXCLUSION,
    STAGE_EXPORT,
    STAGE_LOGIN,
    STAGE_PROFILE_ANALYSIS,
    CancellationToken,
    ProgressCallback,
    SearchConfig,
    SearchProgress,
    SearchResult,
    TaskStatus,
)

logger = get_logger("services.search")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _generate_task_id() -> str:
    return f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


class SearchService:
    """搜索服务：执行完整的创作者发现流程。

    使用方式：
        service = SearchService()
        result = service.run(config, progress_callback, cancellation_token)

    线程模型：
    - run() 在调用方线程中同步执行（GUI 可放入后台线程）
    - cancellation_token.cancel() 可从其他线程调用
    - progress_callback 在 run() 所在线程中被同步调用
    """

    def run(
        self,
        config: SearchConfig,
        progress_callback: ProgressCallback | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> SearchResult:
        """执行完整搜索流程。

        Args:
            config: 搜索配置（Settings + hashtags + dry_run + resume + reset_task）
            progress_callback: 进度回调，每个阶段/每个账号分析后调用
            cancellation_token: 取消令牌，None 表示不可取消

        Returns:
            SearchResult：任务 ID、状态、记录数、导出文件路径

        Raises:
            SecurityStopError: 遇到 Instagram 安全机制（仅在异常向上抛时）
            FinderError: 其他业务异常
        """
        settings: Settings = config.settings  # type: ignore[assignment]
        hashtags_list = list(config.hashtags)
        token = cancellation_token or CancellationToken()

        def emit(progress: SearchProgress) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(progress)
                except Exception:  # noqa: BLE001 - 回调异常不应影响主流程
                    logger.warning("progress_callback raised, ignored", exc_info=True)
            # 持久化进度到 SQLite（即使 GUI 重启也能恢复显示）
            persist_progress(progress)

        task_id = _generate_task_id()
        started_at = _utcnow()

        # 初始化数据库
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
            compute_overall_progress,
            load_all_records,
            update_task_progress,
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

        db = Database(settings.checkpoint.database_file)
        session = db.get_session()

        # 进度持久化：每次 emit 同时写入 SQLite，GUI 可从数据库恢复
        def persist_progress(progress: SearchProgress) -> None:
            try:
                overall = compute_overall_progress(
                    stage=progress.stage,
                    hashtags_completed=progress.hashtags_completed,
                    hashtags_total=progress.hashtags_total,
                    profiles_analyzed=progress.profiles_analyzed,
                    profiles_total=progress.profiles_total,
                )
                # 注意：SearchProgress 的计数器字段默认为 0，但 emit 调用点
                # 通常只传当前阶段关心的字段。为避免 0 覆盖之前已写入的非零累计值，
                # 对于单调递增的累计计数器，只在 progress 显式传入非零值时才更新。
                # stage/message/current_hashtag/current_username 用 None 跳过。
                update_task_progress(
                    session,
                    task_id,
                    stage=progress.stage or None,
                    message=progress.message or None,
                    current_hashtag=progress.current_hashtag or None,
                    current_username=progress.current_username or None,
                    hashtags_total=progress.hashtags_total or None,
                    hashtags_completed=progress.hashtags_completed or None,
                    candidates_found=progress.candidates_found or None,
                    candidates_kept=progress.candidates_kept or None,
                    profiles_total=progress.profiles_total or None,
                    profiles_analyzed=progress.profiles_analyzed or None,
                    profiles_matched=progress.profiles_matched or None,
                    profiles_skipped=progress.profiles_skipped or None,
                    profiles_failed=progress.profiles_failed or None,
                    overall_progress=overall,
                )
            except Exception:  # noqa: BLE001 - 持久化失败不应阻塞主流程
                logger.warning("persist_progress failed", exc_info=True)

        # 恢复任务
        if config.resume:
            cp = load_checkpoint(session, task_id)
            if cp is None:
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
                    logger.info("resuming task %s", task_id)

        if config.reset_task:
            reset_task(session, task_id)
            logger.info("task %s reset", task_id)

        # 初始化任务
        now = _utcnow()
        upsert_task(session, task_id, status=TaskStatus.RUNNING.value, started_at=now)
        cp = load_checkpoint(session, task_id) or TaskCheckpoint(
            task_id=task_id, status=TaskStatus.RUNNING.value, started_at=now
        )
        cp.status = TaskStatus.RUNNING.value
        save_checkpoint(session, cp)

        # 选择客户端
        if config.dry_run:
            from app.instagram.fake_client import FakeInstagramClient

            client: Any = FakeInstagramClient(settings)
        else:
            from app.instagram.client import InstagramClient

            client = InstagramClient(settings)

        try:
            # ===== 阶段 1：登录 =====
            emit(SearchProgress(stage=STAGE_LOGIN, message="登录 Instagram" if not config.dry_run else "模拟登录"))
            client.login_from_env()

            if token.is_cancelled:
                return self._stop_cancelled(session, db, task_id, started_at, emit)

            # ===== 阶段 2：发现候选账号 =====
            completed_ht = set(cp.completed_hashtags)
            pending_ht = [h for h in hashtags_list if h.lower().lstrip("#") not in completed_ht]
            total_ht = len(hashtags_list)
            completed_count = total_ht - len(pending_ht)

            emit(
                SearchProgress(
                    stage=STAGE_DISCOVERY,
                    hashtags_completed=completed_count,
                    hashtags_total=total_ht,
                    message=f"待处理 Hashtag: {len(pending_ht)} 个",
                )
            )

            from app.discovery.deduplication import deduplicate_candidates
            from app.discovery.hashtag import discover_from_hashtags

            if not pending_ht:
                logger.info("all hashtags already completed, skip discovery")
                candidates = []
            else:

                def on_hashtag_done(tag: str, count: int) -> None:
                    mark_hashtag_completed(session, task_id, tag)
                    new_completed = completed_count + 1
                    emit(
                        SearchProgress(
                            stage=STAGE_DISCOVERY,
                            current_hashtag=tag,
                            hashtags_completed=new_completed,
                            hashtags_total=total_ht,
                            candidates_found=count,
                            message=f"完成 #{tag}，发现 {count} 个账号",
                        )
                    )

                candidates = discover_from_hashtags(client, settings, pending_ht, on_hashtag_done=on_hashtag_done)

            if token.is_cancelled:
                return self._stop_cancelled(session, db, task_id, started_at, emit)

            # ===== 阶段 3：去重 =====
            emit(
                SearchProgress(
                    stage=STAGE_DEDUPLICATION,
                    candidates_found=len(candidates),
                    hashtags_completed=total_ht,
                    hashtags_total=total_ht,
                    message=f"去重中，候选数 {len(candidates)}",
                )
            )
            candidates = deduplicate_candidates(candidates)

            # ===== 阶段 4：排除名单 =====
            from app.discovery.seeds import (
                ExclusionEntry,
                apply_exclusion,
                parse_exclude_paths,
                parse_exclude_strings,
            )

            exclusion_entries: list[ExclusionEntry] = []
            if settings.exclude_files:
                file_paths = [p for p in settings.exclude_files if Path(p).exists()]
                str_items = [p for p in settings.exclude_files if not Path(p).exists()]
                exclusion_entries.extend(parse_exclude_paths(file_paths))
                exclusion_entries.extend(parse_exclude_strings(str_items))

            kept_candidates, excluded_candidates = apply_exclusion(candidates, exclusion_entries)

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

            emit(
                SearchProgress(
                    stage=STAGE_EXCLUSION,
                    candidates_found=len(candidates),
                    candidates_kept=len(kept_candidates),
                    message=f"排除 {len(excluded_candidates)}，保留 {len(kept_candidates)}",
                )
            )

            if token.is_cancelled:
                return self._stop_cancelled(session, db, task_id, started_at, emit)

            # ===== 阶段 5：资料获取 + 筛选 + 分析 =====
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

            to_analyze = kept_candidates[: settings.discovery.max_profiles_to_analyze]
            to_analyze = [c for c in to_analyze if not is_user_analyzed(session, task_id, c.username)]

            total_to_analyze = len(to_analyze)
            analyzed_count = 0
            skipped_count = 0
            matched_count = 0
            error_count = 0

            emit(
                SearchProgress(
                    stage=STAGE_PROFILE_ANALYSIS,
                    candidates_kept=len(kept_candidates),
                    hashtags_total=total_ht,
                    hashtags_completed=total_ht,
                    profiles_total=total_to_analyze,
                    message=f"待分析 {total_to_analyze} 个账号",
                )
            )

            for idx, candidate in enumerate(to_analyze, start=1):
                # 取消检查（每个账号之前）
                if token.is_cancelled:
                    logger.info("cancellation requested, stopping before %s", candidate.username)
                    return self._stop_cancelled(session, db, task_id, started_at, emit)

                username = candidate.username
                # 开始处理前 emit 一次（用上次的累计值）
                emit(
                    SearchProgress(
                        stage=STAGE_PROFILE_ANALYSIS,
                        current_username=username,
                        current_hashtag=candidate.source_hashtags[0] if candidate.source_hashtags else None,
                        profiles_total=total_to_analyze,
                        profiles_analyzed=analyzed_count + skipped_count + error_count,
                        profiles_matched=matched_count,
                        profiles_skipped=skipped_count,
                        profiles_failed=error_count,
                        message=f"正在分析 @{username}（{idx}/{total_to_analyze}）",
                    )
                )

                try:
                    profile = client.user_info_by_username(username)

                    # 粉丝范围筛选
                    followers = profile.follower_count or 0
                    if followers < settings.filters.min_followers or followers > settings.filters.max_followers:
                        skipped_count += 1
                        continue

                    # 私密账号筛选
                    if settings.filters.require_public_account and profile.is_private:
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
                        skipped_count += 1
                        continue
                    # 品牌/媒体筛选
                    if settings.filters.exclude_brands and account_type.account_type == "brand":
                        skipped_count += 1
                        continue
                    if settings.filters.exclude_media_accounts and account_type.account_type in ("media", "news"):
                        skipped_count += 1
                        continue
                    # 停更筛选
                    if (
                        metrics.days_since_last_post is not None
                        and metrics.days_since_last_post > settings.filters.maximum_days_since_last_post
                    ):
                        skipped_count += 1
                        continue
                    # 最低 Reels 中位播放量筛选
                    if (
                        settings.filters.minimum_median_reel_views > 0
                        and metrics.reels_view_data_available == "available"
                        and metrics.median_visible_reel_views is not None
                        and metrics.median_visible_reel_views < settings.filters.minimum_median_reel_views
                    ):
                        skipped_count += 1
                        continue
                    # 最低近期内容数量
                    if metrics.recent_media_checked < settings.filters.minimum_recent_media_count:
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
                    matched_count += 1
                    mark_usernames_analyzed(session, task_id, [username])

                except SecurityStopError:
                    raise
                except Exception as e:  # noqa: BLE001 - 单账号失败不应中断整体任务
                    error_count += 1
                    record_failed_username(session, task_id, username, str(e))
                    logger.error("analyze %s failed: %s", username, e)

            emit(
                SearchProgress(
                    stage=STAGE_PROFILE_ANALYSIS,
                    profiles_analyzed=analyzed_count + skipped_count + error_count,
                    profiles_matched=matched_count,
                    profiles_skipped=skipped_count,
                    profiles_failed=error_count,
                    message=f"分析完成：匹配 {matched_count}，跳过 {skipped_count}，错误 {error_count}",
                )
            )

            # ===== 阶段 6：导出 =====
            from app.export import export_records

            records = load_all_records(session, task_id)
            exported = export_records(records, settings.output.directory, settings.output.formats, task_id=task_id)

            emit(
                SearchProgress(
                    stage=STAGE_EXPORT,
                    profiles_matched=matched_count,
                    message=f"已导出 {len(records)} 条记录",
                )
            )

            # ===== 完成 =====
            completed_at = _utcnow()
            update_status(session, task_id, TaskStatus.COMPLETED.value)
            upsert_task(
                session,
                task_id,
                status=TaskStatus.COMPLETED.value,
                completed_at=completed_at,
            )

            emit(
                SearchProgress(
                    stage=STAGE_COMPLETED,
                    message="任务完成",
                )
            )

            return SearchResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                records_count=len(records),
                exported_files=exported,
                started_at=started_at,
                completed_at=completed_at,
            )

        except SecurityStopError as e:
            return self._handle_security_stop(session, task_id, started_at, e, emit)
        except Exception as e:
            return self._handle_failure(session, task_id, started_at, e, emit)
        finally:
            session.close()
            db.close()

    # ===== 内部辅助方法 =====

    def _stop_cancelled(
        self,
        session: Session,
        db: Any,
        task_id: str,
        started_at: datetime,
        emit: ProgressCallback,
    ) -> SearchResult:
        """用户请求取消：保存断点，标记为 STOPPED。"""
        from app.storage.checkpoint import update_status
        from app.storage.repositories import upsert_task

        completed_at = _utcnow()
        update_status(session, task_id, TaskStatus.STOPPED.value, stop_reason="用户取消")
        upsert_task(
            session,
            task_id,
            status=TaskStatus.STOPPED.value,
            stop_reason="用户取消",
            completed_at=completed_at,
        )
        session.close()
        db.close()

        emit(SearchProgress(stage=STAGE_COMPLETED, message="任务已取消，断点已保存"))

        return SearchResult(
            task_id=task_id,
            status=TaskStatus.STOPPED,
            stop_reason="用户取消",
            started_at=started_at,
            completed_at=completed_at,
        )

    def _handle_security_stop(
        self,
        session: Session,
        task_id: str,
        started_at: datetime,
        error: SecurityStopError,
        emit: ProgressCallback,
    ) -> SearchResult:
        """安全停止：保存断点，标记为 STOPPED（或 VERIFICATION_REQUIRED）。"""
        from app.storage.checkpoint import update_status
        from app.storage.repositories import upsert_task

        reason = error.reason or "security_stop"
        # 区分 Challenge 与限流
        status = TaskStatus.VERIFICATION_REQUIRED if "challenge" in reason.lower() else TaskStatus.RATE_LIMITED
        # 兼容现有数据库，统一存为 stopped
        update_status(session, task_id, TaskStatus.STOPPED.value, stop_reason=reason)
        upsert_task(
            session,
            task_id,
            status=TaskStatus.STOPPED.value,
            stop_reason=reason,
            completed_at=_utcnow(),
        )

        emit(SearchProgress(stage=STAGE_COMPLETED, message=f"安全停止：{reason}"))

        return SearchResult(
            task_id=task_id,
            status=status,
            stop_reason=reason,
            started_at=started_at,
            completed_at=_utcnow(),
        )

    def _handle_failure(
        self,
        session: Session,
        task_id: str,
        started_at: datetime,
        error: Exception,
        emit: ProgressCallback,
    ) -> SearchResult:
        """其他异常：标记为 FAILED。"""
        from app.storage.checkpoint import update_status
        from app.storage.repositories import upsert_task

        reason = str(error) or type(error).__name__
        update_status(session, task_id, TaskStatus.FAILED.value, stop_reason=reason)
        upsert_task(
            session,
            task_id,
            status=TaskStatus.FAILED.value,
            stop_reason=reason,
            completed_at=_utcnow(),
        )

        emit(SearchProgress(stage=STAGE_COMPLETED, message=f"任务失败：{reason}"))

        return SearchResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            stop_reason=reason,
            started_at=started_at,
            completed_at=_utcnow(),
        )
