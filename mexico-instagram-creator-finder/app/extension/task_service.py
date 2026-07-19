"""Chrome 扩展驱动的达人发现任务服务。"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus, urlparse

from sqlalchemy import and_, func, or_, select, update

from app.analysis.account_classifier import classify_account_type
from app.analysis.brief_parser import parse_search_brief
from app.analysis.contact_extractor import extract_contacts
from app.analysis.media_metrics import analyze_media_metrics, extract_recent_captions, extract_recent_hashtags
from app.analysis.mexico_detector import detect_mexico_signal
from app.analysis.niche_classifier import classify_niche
from app.analysis.scoring import compute_score
from app.analysis.similarity import compute_local_similarity, profile_document
from app.config import Settings, build_settings
from app.extension.models import (
    ExtensionMediaPayload,
    ExtensionTaskCreate,
    QueueFailurePayload,
    TaskCandidatesPayload,
    TaskProfilePayload,
    TaskRerankPayload,
)
from app.extension.service import ExtensionIngestService, parse_count_text
from app.logging_config import get_logger
from app.models import CandidateAccount, ExtensionMediaData, ProfileData, SearchIntent
from app.storage.database import CandidateRow, Database, NicheRow, TaskQueueRow, TaskRow
from app.storage.repositories import (
    add_task_event,
    claim_next_task_item,
    enqueue_task_item,
    finish_task_item,
    get_active_extension_task,
    get_candidate,
    get_library_creator,
    get_profile,
    get_task,
    list_media_items,
    list_task_events,
    load_all_records,
    queue_counts,
    reset_claimed_task_items,
    retry_failed_task_items,
    save_creator_to_library,
    set_candidate_review_status,
    update_task_progress,
    upsert_account_type,
    upsert_candidate,
    upsert_contact,
    upsert_media_item,
    upsert_media_stats,
    upsert_mexico_signal,
    upsert_niche,
    upsert_profile,
    upsert_score,
    upsert_task,
)

_USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$", re.I)
_MEDIA_RE = re.compile(r"instagram\.com/(?:p|reel|tv)/([^/?#]+)", re.I)
logger = get_logger("extension.task")


def normalize_username(value: str) -> str | None:
    raw = value.strip().rstrip("/")
    if not raw:
        return None
    if "instagram.com" in raw.lower():
        path = urlparse(raw if "://" in raw else f"https://{raw}").path.strip("/")
        if not path or path.split("/")[0].lower() in {"p", "reel", "tv", "explore", "accounts"}:
            return None
        raw = path.split("/")[0]
    raw = raw.lstrip("@").lower()
    return raw if _USERNAME_RE.fullmatch(raw) else None


def profile_url(username: str) -> str:
    return f"https://www.instagram.com/{username}/"


class ExtensionTaskService:
    def __init__(
        self,
        settings: Settings | None = None,
        connected_service: ExtensionIngestService | None = None,
    ) -> None:
        self.settings = settings or build_settings()
        self.connected_service = connected_service
        self._lock = threading.Lock()
        self._excluded_cache: set[str] | None = None

    def _database(self) -> Database:
        return Database(self.settings.checkpoint.database_file)

    def create_task(self, payload: ExtensionTaskCreate) -> dict:
        intent = self._merge_intent(parse_search_brief(payload.brief), payload)
        task_id = f"extension_{datetime.now(UTC):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        connected = bool(self.connected_service and self.connected_service.status().connected)
        status = "running" if connected else "waiting_extension"
        db = self._database()
        session = db.get_session()
        try:
            upsert_task(
                session,
                task_id,
                status=status,
                config_snapshot={"max_profiles_to_analyze": payload.max_profiles_to_analyze},
                search_intent=intent.model_dump(mode="json"),
            )
            add_task_event(session, task_id, "task_created", message="扩展发现任务已创建")
            list_urls = [
                *payload.public_list_urls,
                *[url for url in payload.bulk_links if self._is_public_list_url(url)],
            ]
            seed_values = [*payload.seeds, *[url for url in payload.bulk_links if url not in list_urls]]
            seeds = self._unique_usernames(seed_values)[: payload.max_profiles_to_analyze]
            seeded_count = 0
            for index, username in enumerate(seeds):
                self._store_candidate(session, task_id, username, "seed", username)
                candidate = get_candidate(session, task_id, username)
                if (
                    not candidate.excluded
                    and candidate.review_status == "pending"
                    and self._enqueue_profile(session, task_id, username, "seed", username, priority=5 + index)
                ):
                    seeded_count += 1
            for index, hashtag in enumerate(payload.hashtags[: self.settings.discovery.max_hashtags]):
                tag = hashtag.strip().lstrip("#").lower()
                if tag:
                    enqueue_task_item(
                        session,
                        task_id=task_id,
                        page_type="hashtag",
                        url=f"https://www.instagram.com/explore/tags/{tag}/",
                        dedupe_key=f"hashtag:{tag}",
                        source_type="hashtag",
                        source_value=tag,
                        priority=10 + index,
                    )
            keywords = self._search_keywords(intent, payload)
            for index, keyword in enumerate(keywords):
                enqueue_task_item(
                    session,
                    task_id=task_id,
                    page_type="keyword",
                    url=f"https://www.instagram.com/explore/search/keyword/?q={quote_plus(keyword)}",
                    dedupe_key=f"keyword:{keyword.lower()}",
                    source_type="keyword",
                    source_value=keyword,
                    priority=15 + index,
                )
            for index, list_url in enumerate(dict.fromkeys(list_urls)):
                enqueue_task_item(
                    session,
                    task_id=task_id,
                    page_type="public_list",
                    url=list_url,
                    dedupe_key=f"public_list:{list_url.lower().rstrip('/')}",
                    source_type="public_list",
                    source_value=list_url,
                    priority=30 + index,
                )
            counts = queue_counts(session, task_id)
            update_task_progress(
                session,
                task_id,
                stage="discovery",
                message="等待 Chrome 扩展领取任务" if not connected else "任务已创建",
                hashtags_total=len(payload.hashtags),
                candidates_found=len(seeds),
                candidates_kept=seeded_count,
                profiles_total=seeded_count,
                overall_progress=1,
            )
            logger.info(
                "extension task created task_id=%s seeds=%d hashtags=%d", task_id, len(seeds), len(payload.hashtags)
            )
            return {"task_id": task_id, "status": status, "intent": intent.model_dump(), "queue": counts}
        finally:
            session.close()
            db.close()

    def active_task(self) -> dict | None:
        db = self._database()
        session = db.get_session()
        try:
            row = get_active_extension_task(session)
            return self._task_dict(session, row) if row else None
        finally:
            session.close()
            db.close()

    def review_task(self) -> dict | None:
        db = self._database()
        session = db.get_session()
        try:
            task = session.execute(
                select(TaskRow)
                .join(CandidateRow, CandidateRow.task_id == TaskRow.task_id)
                .where(
                    CandidateRow.review_status == "pending",
                    CandidateRow.last_analyzed_at.is_not(None),
                )
                .order_by(TaskRow.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            return self._task_dict(session, task) if task else None
        finally:
            session.close()
            db.close()

    def next_item(self, task_id: str) -> dict:
        with self._lock:
            db = self._database()
            session = db.get_session()
            try:
                task = get_task(session, task_id)
                if task is None:
                    raise KeyError("task not found")
                if task.status in {"paused", "stopped", "completed", "safe_stopped"}:
                    return {"task_id": task_id, "status": task.status, "item": None}
                task.status = "running"
                self._prune_discovery_at_budget(session, task_id)
                if task.status == "completed":
                    return {
                        "task_id": task_id,
                        "status": task.status,
                        "item": None,
                        "queue": queue_counts(session, task_id),
                    }
                item = claim_next_task_item(session, task_id)
                if item is None:
                    counts = queue_counts(session, task_id)
                    if not counts.get("claimed") and not counts.get("pending"):
                        task.status = "completed"
                        task.completed_at = datetime.now(UTC)
                        task.stage = "completed"
                        task.overall_progress = 100
                        session.commit()
                    return {"task_id": task_id, "status": task.status, "item": None, "queue": counts}
                task.current_username = item.username
                task.current_hashtag = item.source_value if item.page_type in {"hashtag", "keyword"} else None
                task.stage = "media_analysis" if item.page_type == "media" else "profile_enrichment"
                task.progress_message = f"正在访问 {item.url}"
                task.updated_at = datetime.now(UTC)
                session.commit()
                add_task_event(
                    session,
                    task_id,
                    "queue_claimed",
                    queue_item_id=item.id,
                    page_type=item.page_type,
                    username=item.username,
                    message=item.url,
                )
                return {"task_id": task_id, "status": task.status, "item": self._queue_item_dict(item)}
            finally:
                session.close()
                db.close()

    def submit_candidates(self, task_id: str, payload: TaskCandidatesPayload) -> dict:
        db = self._database()
        session = db.get_session()
        added = duplicate = 0
        try:
            task = get_task(session, task_id)
            limit = self._max_profiles(task)
            existing_total = task.profiles_total or 0
            for item in payload.candidates:
                if existing_total + added >= min(limit, self.settings.discovery.max_candidates):
                    break
                username = normalize_username(item.username or item.profile_url or "")
                if not username:
                    continue
                existing = get_candidate(session, task_id, username)
                self._store_candidate(session, task_id, username, payload.source_type, payload.source_page_url)
                stored = get_candidate(session, task_id, username)
                if stored.excluded or stored.review_status != "pending":
                    continue
                if existing:
                    duplicate += 1
                elif self._enqueue_profile(
                    session,
                    task_id,
                    username,
                    payload.source_type,
                    payload.source_page_url,
                    priority=6 if payload.source_type == "seed_recommendation" else 20,
                ):
                    added += 1
            media_added = 0
            queued_profiles = self._queued_profile_count(session, task_id)
            remaining_profiles = max(0, limit - queued_profiles)
            already_queued_media = self._discovery_media_count(session, task_id)
            global_media_remaining = max(0, self.settings.discovery.max_discovery_media - already_queued_media)
            media_budget = min(
                self.settings.discovery.media_per_hashtag,
                remaining_profiles * 3,
                global_media_remaining,
            )
            for index, media_url in enumerate(payload.media_urls[:media_budget]):
                match = _MEDIA_RE.search(media_url)
                if match and enqueue_task_item(
                    session,
                    task_id=task_id,
                    page_type="media",
                    url=media_url,
                    dedupe_key=f"media:{match.group(1).lower()}",
                    source_type=payload.source_type,
                    source_value=payload.source_page_url,
                    priority=8 + index,
                ):
                    media_added += 1
            if payload.queue_item_id:
                finish_task_item(session, payload.queue_item_id)
            task.candidates_found = (task.candidates_found or 0) + len(payload.candidates)
            task.candidates_kept = (task.candidates_kept or 0) + added
            task.profiles_total = (task.profiles_total or 0) + added
            session.commit()
            add_task_event(
                session,
                task_id,
                "discovery_completed",
                queue_item_id=payload.queue_item_id,
                page_type=payload.source_type,
                message=f"new={added} media_queued={media_added}",
            )
            self._refresh_progress(session, task_id)
            logger.info(
                "discovery page completed task_id=%s source=%s candidates=%d media_queued=%d",
                task_id,
                payload.source_type,
                added,
                media_added,
            )
            return {
                "total": len(payload.candidates),
                "new": added,
                "duplicates": duplicate,
                "media_queued": media_added,
            }
        finally:
            session.close()
            db.close()

    def submit_profile(self, task_id: str, payload: TaskProfilePayload) -> dict:
        username = normalize_username(payload.profile.username)
        if not username:
            raise ValueError("invalid username")
        db = self._database()
        session = db.get_session()
        try:
            source_item = session.get(TaskQueueRow, payload.queue_item_id) if payload.queue_item_id else None
            profile = ProfileData(
                username=username,
                full_name=payload.profile.full_name,
                biography=payload.profile.biography,
                profile_url=payload.page_url,
                profile_pic_url=payload.profile.profile_pic_url,
                follower_count=parse_count_text(payload.profile.follower_text),
                following_count=parse_count_text(payload.profile.following_text),
                media_count=parse_count_text(payload.profile.post_count_text),
                is_private=payload.profile.is_private,
                is_verified=payload.profile.is_verified,
                is_business=payload.profile.is_business,
                category_name=payload.profile.category_name,
                external_url=payload.profile.external_links[0] if payload.profile.external_links else None,
                public_email=payload.profile.public_email,
                field_sources=payload.profile.field_sources,
                collected_at=payload.collected_at,
            )
            self._store_candidate(session, task_id, username, payload.source, payload.page_url)
            upsert_profile(session, profile, task_id)
            candidate = get_candidate(session, task_id, username)
            if candidate:
                candidate.collection_version = payload.collection_version
                candidate.data_quality_status = "profile_collected"
                session.commit()
            media_queued = 0
            for media_url in payload.recent_media_urls[: self.settings.analysis.recent_media_amount]:
                match = _MEDIA_RE.search(media_url)
                if match:
                    dedupe_key = f"media:{match.group(1).lower()}"
                    created = enqueue_task_item(
                        session,
                        task_id=task_id,
                        page_type="media",
                        username=username,
                        url=media_url,
                        dedupe_key=dedupe_key,
                        source_type="profile_media",
                        source_value=username,
                        priority=70,
                    )
                    if created:
                        media_queued += 1
                        continue
                    existing_media = session.execute(
                        select(TaskQueueRow).where(
                            TaskQueueRow.task_id == task_id,
                            TaskQueueRow.dedupe_key == dedupe_key,
                        )
                    ).scalar_one_or_none()
                    if existing_media and existing_media.status in {"pending", "claimed"}:
                        existing_media.username = username
                        existing_media.source_type = "profile_media"
                        existing_media.source_value = username
                        media_queued += 1
                        session.commit()
            self._analyze(session, task_id, profile, data_complete=media_queued == 0)
            if payload.visible_recommendations and source_item and source_item.source_type == "seed":
                rec_payload = TaskCandidatesPayload(
                    source_page_url=payload.page_url,
                    source_type="seed_recommendation",
                    candidates=payload.visible_recommendations[: self.settings.discovery.max_accounts_per_seed],
                )
                self.submit_candidates(task_id, rec_payload)
            if payload.queue_item_id:
                finish_task_item(session, payload.queue_item_id)
            add_task_event(
                session,
                task_id,
                "profile_completed",
                queue_item_id=payload.queue_item_id,
                page_type="profile",
                username=username,
                message=f"media_queued={media_queued}",
            )
            self._refresh_progress(session, task_id)
            self._prune_discovery_at_budget(session, task_id)
            logger.info("profile completed task_id=%s username=%s", task_id, username)
            return {"username": username, "media_queued": media_queued, "ok": True}
        finally:
            session.close()
            db.close()

    def submit_media(self, task_id: str, payload: ExtensionMediaPayload) -> dict:
        media = ExtensionMediaData(**payload.model_dump(exclude={"queue_item_id"}))
        db = self._database()
        session = db.get_session()
        try:
            source_item = session.get(TaskQueueRow, payload.queue_item_id) if payload.queue_item_id else None
            username = normalize_username(media.username)
            if not username:
                raise ValueError("invalid media author")
            media.username = username
            existing_candidate = get_candidate(session, task_id, username)
            task = get_task(session, task_id)
            if existing_candidate is None and self._queued_profile_count(session, task_id) >= self._max_profiles(task):
                if payload.queue_item_id:
                    finish_task_item(session, payload.queue_item_id, status="skipped_budget")
                add_task_event(
                    session,
                    task_id,
                    "skipped_budget",
                    queue_item_id=payload.queue_item_id,
                    page_type="media",
                    username=username,
                    message="已达到最大分析账号数",
                )
                self._refresh_progress(session, task_id)
                return {"ok": True, "shortcode": media.shortcode, "skipped": "budget"}
            self._store_candidate(session, task_id, username, "media_author", media.media_url)
            candidate = get_candidate(session, task_id, username)
            if existing_candidate is None:
                task.candidates_found = (task.candidates_found or 0) + 1
                session.commit()
            queued_profiles = session.execute(
                select(func.count(TaskQueueRow.id)).where(
                    TaskQueueRow.task_id == task_id,
                    TaskQueueRow.page_type == "profile",
                )
            ).scalar_one()
            if (
                not candidate.excluded
                and candidate.review_status == "pending"
                and queued_profiles < self._max_profiles(task)
            ):
                self._enqueue_profile(session, task_id, username, "media_author", media.media_url, priority=6)
            upsert_media_item(session, task_id, media)
            candidate_sources = json.loads(candidate.discovery_sources or "[]") if candidate else []
            allow_mentions = bool(
                source_item
                and source_item.source_type == "profile_media"
                and any(source.startswith("seed:") for source in candidate_sources)
            )
            mentioned_usernames = payload.mentioned_usernames if allow_mentions else []
            for mentioned in self._unique_usernames(mentioned_usernames):
                if self._queued_profile_count(session, task_id) >= self._max_profiles(task):
                    break
                self._store_candidate(session, task_id, mentioned, "media_mention", media.media_url)
                mentioned_candidate = get_candidate(session, task_id, mentioned)
                if mentioned_candidate and not mentioned_candidate.excluded:
                    self._enqueue_profile(
                        session,
                        task_id,
                        mentioned,
                        "media_mention",
                        media.media_url,
                        priority=9,
                    )
            if payload.queue_item_id:
                finish_task_item(session, payload.queue_item_id)
            profile_row = get_profile(session, task_id, media.username.lower())
            if profile_row:
                profile = self._profile_from_row(profile_row)
                remaining_media = session.execute(
                    select(func.count(TaskQueueRow.id)).where(
                        TaskQueueRow.task_id == task_id,
                        TaskQueueRow.username == media.username.lower(),
                        TaskQueueRow.source_type == "profile_media",
                        TaskQueueRow.status.in_(("pending", "claimed")),
                    )
                ).scalar_one()
                self._analyze(session, task_id, profile, data_complete=remaining_media == 0)
            add_task_event(
                session,
                task_id,
                "media_completed",
                queue_item_id=payload.queue_item_id,
                page_type="media",
                username=username,
                message=media.shortcode,
            )
            self._refresh_progress(session, task_id)
            logger.info(
                "media author resolved task_id=%s username=%s shortcode=%s source=%s",
                task_id,
                username,
                media.shortcode,
                media.field_sources.get("username") or "unknown",
            )
            return {"ok": True, "shortcode": media.shortcode}
        finally:
            session.close()
            db.close()

    def report_failure(self, task_id: str, payload: QueueFailurePayload) -> dict:
        db = self._database()
        session = db.get_session()
        try:
            item = finish_task_item(
                session,
                payload.queue_item_id,
                status="failed",
                error_reason=payload.error,
                retryable=payload.retryable,
                error_code=payload.error_code,
            )
            task = get_task(session, task_id)
            if payload.safe_stop and task:
                task.status = "safe_stopped"
                task.stop_reason = payload.error
                task.progress_message = "检测到 Instagram 安全限制，已停止"
                session.commit()
            if item and item.status == "failed" and item.username:
                candidate = get_candidate(session, task_id, item.username)
                if candidate:
                    candidate.match_status = "failed" if item.page_type == "profile" else "incomplete"
                    candidate.data_quality_status = "failed" if item.page_type == "profile" else "media_incomplete"
                    candidate.filter_reasons = json.dumps([payload.error], ensure_ascii=False)
                    session.commit()
            diagnostic_text = json.dumps(payload.diagnostics, ensure_ascii=False, sort_keys=True)
            event_message = (
                payload.error
                if not diagnostic_text or diagnostic_text == "{}"
                else f"{payload.error} | {diagnostic_text}"
            )
            add_task_event(
                session,
                task_id,
                "queue_failure",
                queue_item_id=payload.queue_item_id,
                page_type=item.page_type if item else None,
                username=item.username if item else None,
                message=event_message,
                error_code=payload.error_code,
                retryable=payload.retryable,
            )
            self._refresh_progress(session, task_id)
            logger.warning(
                "queue failure task_id=%s item_id=%s code=%s retryable=%s diagnostics=%s",
                task_id,
                payload.queue_item_id,
                payload.error_code,
                payload.retryable,
                diagnostic_text,
            )
            return {
                "ok": True,
                "item_status": item.status if item else None,
                "task_status": task.status if task else None,
            }
        finally:
            session.close()
            db.close()

    def control(self, task_id: str, action: str) -> dict:
        status_map = {"pause": "paused", "resume": "running", "stop": "stopped"}
        db = self._database()
        session = db.get_session()
        try:
            task = get_task(session, task_id)
            if task is None:
                raise KeyError("task not found")
            task.status = status_map[action]
            if action == "resume":
                reset_claimed_task_items(session, task_id)
            task.updated_at = datetime.now(UTC)
            task.progress_message = {"pause": "任务已暂停", "resume": "任务继续", "stop": "任务已停止"}[action]
            if action == "stop":
                task.stop_reason = "用户停止"
            session.commit()
            return self._task_dict(session, task)
        finally:
            session.close()
            db.close()

    def next_review_creator(self, task_id: str) -> dict | None:
        """返回下一个已分析但尚未人工处理的候选。"""
        db = self._database()
        session = db.get_session()
        try:
            records = [
                record
                for record in load_all_records(session, task_id)
                if record.review_status == "pending"
                and record.last_analyzed_at is not None
                and not record.excluded
                and record.match_status != "private"
            ]
            records.sort(
                key=lambda record: (
                    record.match_status != "matched",
                    -record.similarity_score,
                    -(record.score.total_score if record.score else 0),
                    -(record.profile.follower_count or 0),
                )
            )
            if not records:
                return None
            record = records[0]
            return self._review_dict(record)
        finally:
            session.close()
            db.close()

    def review_creator(
        self,
        task_id: str,
        username: str,
        action: str,
        *,
        list_name: str = "默认达人库",
        note: str | None = None,
    ) -> dict:
        db = self._database()
        session = db.get_session()
        try:
            candidate = get_candidate(session, task_id, username.lower())
            if candidate is None:
                raise KeyError("candidate not found")
            if action == "save":
                save_creator_to_library(
                    session,
                    task_id,
                    username,
                    list_name=list_name,
                    note=note,
                )
                status = "saved"
            elif action == "skip":
                set_candidate_review_status(session, task_id, username, "skipped")
                status = "skipped"
            else:
                raise ValueError("unsupported review action")
            return {"ok": True, "username": username.lower(), "review_status": status}
        finally:
            session.close()
            db.close()

    def _analyze(self, session, task_id: str, profile: ProfileData, *, data_complete: bool = True) -> None:
        candidate = get_candidate(session, task_id, profile.username)
        sources = json.loads(candidate.discovery_sources or "[]") if candidate else []
        source_tags = [s.removeprefix("hashtag:") for s in sources if s.startswith("hashtag:")]
        media_rows = list_media_items(session, task_id, profile.username)
        medias = [
            SimpleNamespace(
                taken_at=row.taken_at,
                media_type=2 if row.is_reel else 1,
                product_type="clips" if row.is_reel else "feed",
                caption_text=row.caption or "",
                like_count=row.like_count,
                comment_count=row.comment_count,
                play_count=row.visible_play_count,
                view_count=row.visible_play_count,
                view_count_disabled=bool(row.is_reel and row.visible_play_count is None),
            )
            for row in media_rows
        ]
        captions = extract_recent_captions(medias)
        hashtags = extract_recent_hashtags(medias)
        niche = classify_niche(profile, source_tags, captions, hashtags)
        mexico = detect_mexico_signal(profile, source_tags, captions)
        contact = extract_contacts(profile)
        account_type = classify_account_type(profile, source_tags)
        upsert_niche(session, niche, task_id, profile.username)
        upsert_mexico_signal(session, mexico, task_id, profile.username)
        upsert_contact(session, contact, task_id, profile.username)
        upsert_account_type(session, account_type, task_id, profile.username)
        metrics = analyze_media_metrics(medias, self.settings)
        upsert_media_stats(session, metrics, task_id, profile.username)
        intent = self._intent(get_task(session, task_id))
        score = compute_score(
            profile,
            mexico,
            niche,
            metrics,
            contact,
            account_type,
            min_followers=intent.min_followers or self.settings.filters.min_followers,
            max_followers=intent.max_followers or self.settings.filters.max_followers,
            minimum_median_reel_views=intent.minimum_median_reel_views
            or self.settings.filters.minimum_median_reel_views,
            maximum_days_since_last_post=intent.maximum_days_since_last_post
            or self.settings.filters.maximum_days_since_last_post,
        )
        upsert_score(session, score, task_id, profile.username)
        self._apply_filters(
            session, candidate, profile, metrics, contact, niche, mexico, account_type, intent, data_complete
        )
        self._update_similarity(
            session,
            task_id,
            candidate,
            profile,
            niche,
            mexico,
            account_type,
            metrics,
            contact,
            captions,
            intent,
        )

    @staticmethod
    def _apply_filters(
        session, candidate, profile, metrics, contact, niche, mexico, account_type, intent, data_complete=True
    ) -> None:
        if candidate is None:
            return
        if candidate.excluded:
            candidate.match_status = "excluded"
            candidate.filter_reasons = json.dumps(
                [candidate.exclusion_reason or "用户排除名单匹配"], ensure_ascii=False
            )
            candidate.last_analyzed_at = datetime.now(UTC)
            session.commit()
            return
        reasons: list[str] = []
        status = "matched"
        if profile.is_private and intent.require_public_account:
            status, reasons = "private", ["账号为私密账号"]
        else:
            if intent.min_followers is not None and (
                profile.follower_count is None or profile.follower_count < intent.min_followers
            ):
                reasons.append("粉丝数低于 Brief 下限或不可用")
            if (
                intent.max_followers is not None
                and profile.follower_count is not None
                and profile.follower_count > intent.max_followers
            ):
                reasons.append("粉丝数高于 Brief 上限")
            if intent.require_mexico_signal and mexico.mexico_confidence_score < 0.4:
                reasons.append("墨西哥地区信号不足")
            if intent.target_niches and niche.primary_niche not in intent.target_niches:
                reasons.append(f"垂类 {niche.primary_niche} 不匹配")
            if intent.target_account_types and account_type.account_type not in intent.target_account_types:
                reasons.append(f"账号类型 {account_type.account_type} 不匹配")
            if intent.exclude_brands and account_type.account_type in {"brand", "shop"}:
                reasons.append(f"账号类型 {account_type.account_type} 已排除")
            if intent.exclude_media_accounts and account_type.account_type in {"media", "news", "agency", "marketing"}:
                reasons.append(f"账号类型 {account_type.account_type} 已排除")
            if intent.require_public_contact and not contact.has_public_contact:
                reasons.append("没有公开联系方式")
            if intent.minimum_median_reel_views and (
                metrics.median_visible_reel_views is None
                or metrics.median_visible_reel_views < intent.minimum_median_reel_views
            ):
                reasons.append("Reels 中位播放量不足或不可用")
            if not data_complete:
                status = "incomplete"
                reasons.append("近期媒体仍在补全")
            elif reasons:
                status = "filtered"
        candidate.match_status = status
        candidate.filter_reasons = json.dumps(reasons, ensure_ascii=False)
        candidate.last_analyzed_at = datetime.now(UTC)
        candidate.data_quality_status = "complete" if data_complete else "media_pending"
        session.commit()

    def _update_similarity(
        self, session, task_id, candidate, profile, niche, mexico, account_type, metrics, contact, captions, intent
    ) -> None:
        if candidate is None:
            return
        seed_rows = session.execute(
            select(CandidateRow).where(
                CandidateRow.task_id == task_id,
                CandidateRow.discovery_sources.like("%seed:%"),
            )
        ).scalars()
        seed_documents: dict[str, str] = {}
        for seed in seed_rows:
            profile_row = get_profile(session, task_id, seed.username)
            if profile_row:
                seed_documents[seed.username] = profile_document(self._profile_from_row(profile_row))
        sources = json.loads(candidate.discovery_sources or "[]")
        value, breakdown, reference = compute_local_similarity(
            profile,
            brief=intent.raw_brief,
            seed_documents=seed_documents,
            niche=niche,
            mexico=mexico,
            account_type=account_type,
            metrics=metrics,
            intent=intent,
            contact=contact,
            captions=captions,
            source_count=len(sources),
        )
        preference = self._preference_feedback(session, niche.primary_niche, intent.raw_brief)
        breakdown["preference_feedback"] = preference
        value = round(max(0.0, min(100.0, value + preference)), 2)
        candidate.similarity_score = value
        candidate.similarity_breakdown = json.dumps(breakdown, ensure_ascii=False)
        candidate.reference_seed = reference
        session.commit()

    @staticmethod
    def _preference_feedback(session, primary_niche: str, raw_brief: str) -> float:
        if not raw_brief:
            return 0.0
        rows = session.execute(
            select(CandidateRow.review_status, NicheRow.primary_niche, TaskRow.search_intent)
            .join(
                NicheRow,
                (NicheRow.task_id == CandidateRow.task_id) & (NicheRow.username == CandidateRow.username),
            )
            .join(TaskRow, TaskRow.task_id == CandidateRow.task_id)
            .where(CandidateRow.review_status.in_(("saved", "skipped")))
        ).all()
        saved = skipped = 0
        for review_status, niche, intent_json in rows:
            try:
                same_brief = json.loads(intent_json or "{}").get("raw_brief") == raw_brief
            except json.JSONDecodeError:
                same_brief = False
            if same_brief and niche == primary_niche:
                saved += review_status == "saved"
                skipped += review_status == "skipped"
        return float(max(-5, min(5, saved - skipped)))

    def _store_candidate(self, session, task_id: str, username: str, source_type: str, source_value: str) -> None:
        excluded = username in self._excluded_usernames()
        historical = session.execute(
            select(CandidateRow)
            .where(
                CandidateRow.username == username,
                CandidateRow.task_id != task_id,
                CandidateRow.review_status.in_(("saved", "skipped")),
            )
            .order_by(CandidateRow.reviewed_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        library_creator = get_library_creator(session, username)
        upsert_candidate(
            session,
            CandidateAccount(
                username=username,
                source_hashtags=[f"{source_type}:{source_value}"],
                discovered_at=datetime.now(UTC),
                normalized=True,
            ),
            task_id,
            excluded=excluded,
            exclusion_source="exclude_list" if excluded else None,
            exclusion_reason="用户排除名单匹配" if excluded else None,
        )
        row = get_candidate(session, task_id, username)
        sources = set(json.loads(row.discovery_sources or "[]"))
        sources.add(f"{source_type}:{source_value}")
        row.discovery_sources = json.dumps(sorted(sources), ensure_ascii=False)
        if row.last_analyzed_at is None and not row.excluded:
            row.match_status = "discovered"
            row.data_quality_status = "discovered"
        if excluded:
            row.match_status = "excluded"
            row.filter_reasons = json.dumps(["用户排除名单匹配"], ensure_ascii=False)
        elif library_creator:
            row.review_status = "saved"
            row.reviewed_at = library_creator.saved_at
        elif historical:
            row.review_status = historical.review_status
            row.reviewed_at = historical.reviewed_at
            reasons = set(json.loads(row.filter_reasons or "[]"))
            reasons.add("历史任务中已审核，自动去重")
            row.filter_reasons = json.dumps(sorted(reasons), ensure_ascii=False)
        session.commit()

    def _excluded_usernames(self) -> set[str]:
        if self._excluded_cache is not None:
            return self._excluded_cache
        from app.discovery.seeds import parse_exclude_paths, parse_exclude_strings

        configured = self.settings.exclude_files or []
        paths = [Path(value) for value in configured if Path(value).exists()]
        inline = [value for value in configured if not Path(value).exists()]
        entries = parse_exclude_paths(paths) + parse_exclude_strings(inline)
        self._excluded_cache = {entry.username.lower() for entry in entries}
        return self._excluded_cache

    @staticmethod
    def _enqueue_profile(
        session, task_id: str, username: str, source_type: str, source_value: str, priority: int = 100
    ):
        return enqueue_task_item(
            session,
            task_id=task_id,
            page_type="profile",
            username=username,
            url=profile_url(username),
            dedupe_key=f"profile:{username}",
            source_type=source_type,
            source_value=source_value,
            priority=priority,
        )

    @staticmethod
    def _unique_usernames(values: list[str]) -> list[str]:
        return list(dict.fromkeys(u for value in values if (u := normalize_username(value))))

    @staticmethod
    def _search_keywords(intent: SearchIntent, payload: ExtensionTaskCreate) -> list[str]:
        explicit = [keyword.strip() for keyword in payload.keywords if keyword.strip()]
        generated = [f"{niche.lower()} mexico" for niche in intent.target_niches]
        if not generated and not payload.seeds and not payload.hashtags:
            generated = intent.content_keywords[:3]
        return list(dict.fromkeys([*explicit, *generated]))[:5]

    @staticmethod
    def _is_public_list_url(value: str) -> bool:
        lowered = value.lower().rstrip("/")
        return "instagram.com/" in lowered and lowered.endswith(("/followers", "/following"))

    @staticmethod
    def _merge_intent(intent: SearchIntent, payload: ExtensionTaskCreate) -> SearchIntent:
        updates = {
            key: value
            for key, value in {
                "min_followers": payload.min_followers,
                "max_followers": payload.max_followers,
                "minimum_median_reel_views": payload.minimum_median_reel_views,
                "maximum_days_since_last_post": payload.maximum_days_since_last_post,
                "require_mexico_signal": payload.require_mexico_signal,
                "require_public_contact": payload.require_public_contact,
                "require_public_account": payload.require_public_account,
                "exclude_brands": payload.exclude_brands,
                "exclude_media_accounts": payload.exclude_media_accounts,
            }.items()
            if value is not None
        }
        if payload.target_niches:
            updates["target_niches"] = list(dict.fromkeys([*intent.target_niches, *payload.target_niches]))
        return intent.model_copy(update=updates)

    @staticmethod
    def _intent(task) -> SearchIntent:
        return SearchIntent.model_validate_json(task.search_intent) if task and task.search_intent else SearchIntent()

    @staticmethod
    def _max_profiles(task) -> int:
        if not task or not task.config_snapshot:
            return 100
        return int(json.loads(task.config_snapshot).get("max_profiles_to_analyze", 100))

    def _refresh_progress(self, session, task_id: str) -> None:
        task = get_task(session, task_id)
        counts = queue_counts(session, task_id)
        done = (
            counts.get("completed", 0)
            + counts.get("skipped", 0)
            + counts.get("skipped_budget", 0)
            + counts.get("failed", 0)
        )
        total = sum(counts.values()) or 1
        analyzed = session.execute(
            select(func.count(CandidateRow.id)).where(
                CandidateRow.task_id == task_id,
                CandidateRow.last_analyzed_at.is_not(None),
            )
        ).scalar_one()
        candidate_total = session.execute(
            select(func.count(CandidateRow.id)).where(CandidateRow.task_id == task_id)
        ).scalar_one()
        matched = session.execute(
            select(func.count(CandidateRow.id)).where(
                CandidateRow.task_id == task_id,
                CandidateRow.match_status == "matched",
            )
        ).scalar_one()
        filtered = session.execute(
            select(func.count(CandidateRow.id)).where(
                CandidateRow.task_id == task_id,
                CandidateRow.match_status.in_(("filtered", "private", "excluded")),
            )
        ).scalar_one()
        failed = counts.get("failed", 0)
        task.profiles_analyzed = analyzed
        task.profiles_total = candidate_total
        task.candidates_kept = candidate_total
        task.profiles_matched = matched
        task.profiles_skipped = filtered
        task.profiles_failed = failed
        task.overall_progress = min(99, int(done / total * 100))
        task.updated_at = datetime.now(UTC)
        task.progress_updated_at = datetime.now(UTC)
        session.commit()

    def _prune_discovery_at_budget(self, session, task_id: str) -> int:
        task = get_task(session, task_id)
        analyzed = session.execute(
            select(func.count(CandidateRow.id)).where(
                CandidateRow.task_id == task_id,
                CandidateRow.last_analyzed_at.is_not(None),
            )
        ).scalar_one()
        if analyzed < self._max_profiles(task):
            return 0
        result = session.execute(
            update(TaskQueueRow)
            .where(
                TaskQueueRow.task_id == task_id,
                TaskQueueRow.status == "pending",
                or_(
                    TaskQueueRow.page_type.in_(("profile", "hashtag", "keyword", "public_list")),
                    and_(TaskQueueRow.page_type == "media", TaskQueueRow.source_type != "profile_media"),
                ),
            )
            .values(status="skipped_budget", error_reason="已达到最大分析账号数")
        )
        pruned = int(result.rowcount or 0)
        remaining = session.execute(
            select(func.count(TaskQueueRow.id)).where(
                TaskQueueRow.task_id == task_id,
                TaskQueueRow.status.in_(("pending", "claimed")),
            )
        ).scalar_one()
        task.progress_message = (
            "已达到最大分析账号数，正在补全已分析账号媒体" if remaining else "已达到最大分析账号数，任务已完成"
        )
        if not remaining:
            task.status = "completed"
            task.stage = "completed"
            task.overall_progress = 100
            task.completed_at = datetime.now(UTC)
        session.commit()
        if pruned:
            add_task_event(
                session,
                task_id,
                "analysis_budget_reached",
                message=f"analyzed={analyzed} skipped_pending={pruned}",
            )
            logger.info(
                "analysis budget reached task_id=%s analyzed=%d skipped_pending=%d",
                task_id,
                analyzed,
                pruned,
            )
        return pruned

    @staticmethod
    def _queued_profile_count(session, task_id: str) -> int:
        return session.execute(
            select(func.count(TaskQueueRow.id)).where(
                TaskQueueRow.task_id == task_id,
                TaskQueueRow.page_type == "profile",
            )
        ).scalar_one()

    @staticmethod
    def _discovery_media_count(session, task_id: str) -> int:
        return session.execute(
            select(func.count(TaskQueueRow.id)).where(
                TaskQueueRow.task_id == task_id,
                TaskQueueRow.page_type == "media",
                TaskQueueRow.source_type != "profile_media",
            )
        ).scalar_one()

    @staticmethod
    def _profile_from_row(row) -> ProfileData:
        fields = {
            key: getattr(row, key) for key in ProfileData.model_fields if key != "field_sources" and hasattr(row, key)
        }
        fields["field_sources"] = json.loads(row.field_sources or "{}")
        return ProfileData.model_validate(fields)

    def events(self, task_id: str, limit: int = 200) -> list[dict]:
        db = self._database()
        session = db.get_session()
        try:
            return [
                {
                    "id": row.id,
                    "task_id": row.task_id,
                    "queue_item_id": row.queue_item_id,
                    "event_type": row.event_type,
                    "page_type": row.page_type,
                    "username": row.username,
                    "message": row.message,
                    "error_code": row.error_code,
                    "retryable": None if row.retryable is None else bool(row.retryable),
                    "created_at": row.created_at.isoformat(),
                }
                for row in list_task_events(session, task_id, limit)
            ]
        finally:
            session.close()
            db.close()

    def retry_failed(self, task_id: str) -> dict:
        db = self._database()
        session = db.get_session()
        try:
            retried = retry_failed_task_items(session, task_id)
            task = get_task(session, task_id)
            if task and retried:
                task.status = "running"
                task.stop_reason = None
                session.commit()
            add_task_event(session, task_id, "failed_items_retried", message=f"count={retried}")
            self._refresh_progress(session, task_id)
            return {"ok": True, "retried": retried}
        finally:
            session.close()
            db.close()

    def rerank_candidates(self, task_id: str, payload: TaskRerankPayload) -> dict:
        """使用新的自然语言 Brief 对已采集候选重新分析和排序，不访问 Instagram。"""
        intent = parse_search_brief(payload.brief)
        db = self._database()
        session = db.get_session()
        try:
            task = get_task(session, task_id)
            if task is None:
                raise KeyError("task not found")
            task.search_intent = intent.model_dump_json()
            task.progress_message = "已按新的 Brief 重新匹配现有候选"
            task.updated_at = datetime.now(UTC)
            session.commit()
            analyzed = 0
            candidates = session.execute(
                select(CandidateRow)
                .where(
                    CandidateRow.task_id == task_id,
                    CandidateRow.last_analyzed_at.is_not(None),
                )
                .order_by(CandidateRow.id)
            ).scalars()
            for candidate in candidates:
                profile_row = get_profile(session, task_id, candidate.username)
                if profile_row is None:
                    continue
                pending_media = session.execute(
                    select(func.count(TaskQueueRow.id)).where(
                        TaskQueueRow.task_id == task_id,
                        TaskQueueRow.username == candidate.username,
                        TaskQueueRow.source_type == "profile_media",
                        TaskQueueRow.status.in_(("pending", "claimed")),
                    )
                ).scalar_one()
                self._analyze(
                    session,
                    task_id,
                    self._profile_from_row(profile_row),
                    data_complete=pending_media == 0,
                )
                analyzed += 1
            add_task_event(
                session,
                task_id,
                "brief_reranked",
                message=f"profiles={analyzed}",
            )
            records = load_all_records(session, task_id)
            records.sort(key=lambda row: (-row.similarity_score, -(row.score.total_score if row.score else 0)))
            return {
                "ok": True,
                "task_id": task_id,
                "profiles_reranked": analyzed,
                "intent": intent.model_dump(mode="json"),
                "top_candidates": [
                    {
                        "username": row.username,
                        "similarity_score": row.similarity_score,
                        "similarity_breakdown": row.similarity_breakdown,
                        "total_score": row.score.total_score if row.score else 0,
                        "match_status": row.match_status,
                    }
                    for row in records[:20]
                ],
            }
        finally:
            session.close()
            db.close()

    @staticmethod
    def _queue_item_dict(item) -> dict:
        return {
            "id": item.id,
            "page_type": item.page_type,
            "username": item.username,
            "url": item.url,
            "source_type": item.source_type,
            "source_value": item.source_value,
            "depth": item.depth,
            "attempt_count": item.attempt_count,
        }

    def _task_dict(self, session, task) -> dict:
        recent_candidates = session.execute(
            select(CandidateRow).where(CandidateRow.task_id == task.task_id).order_by(CandidateRow.id.desc()).limit(5)
        ).scalars()
        return {
            "task_id": task.task_id,
            "status": task.status,
            "stage": task.stage,
            "message": task.progress_message,
            "current_username": task.current_username,
            "current_hashtag": task.current_hashtag,
            "candidates_found": task.candidates_found or 0,
            "profiles_total": task.profiles_total or 0,
            "profiles_analyzed": task.profiles_analyzed or 0,
            "profiles_matched": task.profiles_matched or 0,
            "profiles_skipped": task.profiles_skipped or 0,
            "profiles_failed": task.profiles_failed or 0,
            "overall_progress": task.overall_progress or 0,
            "request_delay_min_seconds": self.settings.instagram.request_delay_min_seconds,
            "request_delay_max_seconds": self.settings.instagram.request_delay_max_seconds,
            "queue": queue_counts(session, task.task_id),
            "recent_candidates": [
                {
                    "username": row.username,
                    "status": row.match_status,
                    "data_quality_status": row.data_quality_status,
                }
                for row in recent_candidates
            ],
        }

    @staticmethod
    def _review_dict(record) -> dict:
        profile = record.profile
        return {
            "username": record.username,
            "full_name": profile.full_name,
            "profile_url": profile.profile_url,
            "profile_pic_url": profile.profile_pic_url,
            "biography": profile.biography,
            "follower_count": profile.follower_count,
            "following_count": profile.following_count,
            "media_count": profile.media_count,
            "match_status": record.match_status,
            "filter_reasons": record.filter_reasons,
            "discovery_sources": record.discovery_sources,
            "total_score": record.score.total_score if record.score else 0,
            "recommendation_level": record.score.recommendation_level if record.score else "D",
            "primary_niche": record.niche.primary_niche if record.niche else "general",
            "mexico_confidence_score": record.mexico.mexico_confidence_score if record.mexico else 0,
            "median_visible_reel_views": (record.metrics.median_visible_reel_views if record.metrics else None),
            "public_email": record.contact.public_email if record.contact else profile.public_email,
            "public_whatsapp_url": record.contact.public_whatsapp_url if record.contact else None,
            "external_url": record.contact.external_url if record.contact else profile.external_url,
            "review_status": record.review_status,
            "similarity_score": record.similarity_score,
            "similarity_breakdown": record.similarity_breakdown,
            "reference_seed": record.reference_seed,
            "data_quality_status": record.data_quality_status,
        }
