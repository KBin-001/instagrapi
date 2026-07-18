"""SQLite 仓储层：各表 CRUD 操作。

仅保存公开数据，不保存密码、完整 Session、私信、私密账号内容、未公开电话号码、
推测邮箱、下载视频、大量原始图片。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import (
    AccountTypeClassification,
    CandidateAccount,
    ContactInfo,
    CreatorRecord,
    MediaMetrics,
    MexicoSignal,
    NicheClassification,
    ProfileData,
    ScoreResult,
)
from app.storage.database import (
    AccountTypeRow,
    CandidateRow,
    ContactRow,
    HashtagRow,
    MediaStatsRow,
    MexicoSignalRow,
    NicheRow,
    ProfileRow,
    ScoreRow,
    TaskRow,
)

logger = get_logger("storage.repositories")


def _now() -> datetime:
    return datetime.now(UTC)


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default if default is not None else []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


# ---- Task ----


def upsert_task(
    session: Session,
    task_id: str,
    *,
    status: str = "pending",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    stop_reason: str | None = None,
    config_snapshot: dict | None = None,
) -> None:
    row = session.get(TaskRow, task_id)
    now = _now()
    if row is None:
        row = TaskRow(
            task_id=task_id,
            status=status,
            started_at=started_at or now,
            updated_at=now,
            completed_at=completed_at,
            stop_reason=stop_reason,
            config_snapshot=_json_dumps(config_snapshot) if config_snapshot else None,
        )
        session.add(row)
    else:
        row.status = status
        row.updated_at = now
        if started_at:
            row.started_at = started_at
        if completed_at:
            row.completed_at = completed_at
        if stop_reason is not None:
            row.stop_reason = stop_reason
        if config_snapshot is not None:
            row.config_snapshot = _json_dumps(config_snapshot)
    session.commit()


def get_task(session: Session, task_id: str) -> TaskRow | None:
    return session.get(TaskRow, task_id)


# ---- Hashtag ----


def mark_hashtag_completed(session: Session, task_id: str, hashtag: str, candidates_found: int = 0) -> None:
    stmt = select(HashtagRow).where(HashtagRow.task_id == task_id, HashtagRow.hashtag == hashtag)
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        row = HashtagRow(
            task_id=task_id,
            hashtag=hashtag,
            completed=1,
            candidates_found=candidates_found,
            completed_at=_now(),
        )
        session.add(row)
    else:
        row.completed = 1
        row.candidates_found = candidates_found
        row.completed_at = _now()
    session.commit()


def list_completed_hashtags(session: Session, task_id: str) -> list[str]:
    stmt = select(HashtagRow.hashtag).where(HashtagRow.task_id == task_id, HashtagRow.completed == 1)
    return [r for r in session.execute(stmt).scalars()]


# ---- Candidate ----


def upsert_candidate(
    session: Session,
    candidate: CandidateAccount,
    task_id: str,
    excluded: bool = False,
    exclusion_source: str | None = None,
    exclusion_reason: str | None = None,
) -> None:
    stmt = select(CandidateRow).where(
        CandidateRow.task_id == task_id,
        CandidateRow.username == candidate.username,
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        row = CandidateRow(
            task_id=task_id,
            username=candidate.username,
            source_hashtags=_json_dumps(candidate.source_hashtags),
            discovered_at=candidate.discovered_at,
            normalized=1 if candidate.normalized else 0,
            excluded=1 if excluded else 0,
            exclusion_source=exclusion_source,
            exclusion_reason=exclusion_reason,
        )
        session.add(row)
    else:
        if excluded:
            row.excluded = 1
            row.exclusion_source = exclusion_source
            row.exclusion_reason = exclusion_reason
        # 合并 source_hashtags
        existing_ht = set(_json_loads(row.source_hashtags, []))
        for h in candidate.source_hashtags:
            existing_ht.add(h)
        row.source_hashtags = _json_dumps(list(existing_ht))
    session.commit()


def list_candidates(session: Session, task_id: str, include_excluded: bool = False) -> list[CandidateRow]:
    stmt = select(CandidateRow).where(CandidateRow.task_id == task_id)
    if not include_excluded:
        stmt = stmt.where(CandidateRow.excluded == 0)
    return list(session.execute(stmt).scalars())


def get_candidate(session: Session, task_id: str, username: str) -> CandidateRow | None:
    stmt = select(CandidateRow).where(CandidateRow.task_id == task_id, CandidateRow.username == username)
    return session.execute(stmt).scalar_one_or_none()


# ---- Profile ----


def upsert_profile(session: Session, profile: ProfileData, task_id: str) -> None:
    stmt = select(ProfileRow).where(ProfileRow.task_id == task_id, ProfileRow.username == profile.username)
    row = session.execute(stmt).scalar_one_or_none()
    fields = dict(
        pk=profile.pk,
        full_name=profile.full_name,
        biography=profile.biography,
        profile_url=profile.profile_url,
        profile_pic_url=profile.profile_pic_url,
        follower_count=profile.follower_count,
        following_count=profile.following_count,
        media_count=profile.media_count,
        is_private=int(profile.is_private) if profile.is_private is not None else None,
        is_verified=int(profile.is_verified) if profile.is_verified is not None else None,
        is_business=int(profile.is_business) if profile.is_business is not None else None,
        category_name=profile.category_name,
        business_category_name=profile.business_category_name,
        external_url=profile.external_url,
        public_email=profile.public_email,
        collected_at=profile.collected_at,
    )
    if row is None:
        row = ProfileRow(task_id=task_id, username=profile.username, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.commit()


def get_profile(session: Session, task_id: str, username: str) -> ProfileRow | None:
    stmt = select(ProfileRow).where(ProfileRow.task_id == task_id, ProfileRow.username == username)
    return session.execute(stmt).scalar_one_or_none()


# ---- MediaStats ----


def upsert_media_stats(session: Session, metrics: MediaMetrics, task_id: str, username: str) -> None:
    stmt = select(MediaStatsRow).where(MediaStatsRow.task_id == task_id, MediaStatsRow.username == username)
    row = session.execute(stmt).scalar_one_or_none()
    fields = dict(
        recent_media_checked=metrics.recent_media_checked,
        recent_reels_checked=metrics.recent_reels_checked,
        last_post_date=metrics.last_post_date,
        days_since_last_post=metrics.days_since_last_post,
        average_likes=metrics.average_likes,
        median_likes=metrics.median_likes,
        average_comments=metrics.average_comments,
        median_comments=metrics.median_comments,
        average_visible_reel_views=metrics.average_visible_reel_views,
        median_visible_reel_views=metrics.median_visible_reel_views,
        maximum_visible_reel_views=metrics.maximum_visible_reel_views,
        posting_frequency=metrics.posting_frequency,
        reels_view_data_available=metrics.reels_view_data_available,
    )
    if row is None:
        row = MediaStatsRow(task_id=task_id, username=username, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.commit()


# ---- Score ----


def upsert_score(session: Session, score: ScoreResult, task_id: str, username: str) -> None:
    stmt = select(ScoreRow).where(ScoreRow.task_id == task_id, ScoreRow.username == username)
    row = session.execute(stmt).scalar_one_or_none()
    fields = dict(
        total_score=score.total_score,
        score_breakdown=_json_dumps(score.score_breakdown),
        recommendation_level=score.recommendation_level,
        recommendation_reasons=_json_dumps(score.recommendation_reasons),
    )
    if row is None:
        row = ScoreRow(task_id=task_id, username=username, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.commit()


# ---- Contact ----


def upsert_contact(session: Session, contact: ContactInfo, task_id: str, username: str) -> None:
    stmt = select(ContactRow).where(ContactRow.task_id == task_id, ContactRow.username == username)
    row = session.execute(stmt).scalar_one_or_none()
    fields = dict(
        public_email=contact.public_email,
        public_whatsapp_url=contact.public_whatsapp_url,
        external_url=contact.external_url,
        linktree_url=contact.linktree_url,
        beacons_url=contact.beacons_url,
        contact_source=contact.contact_source,
        has_public_contact=1 if contact.has_public_contact else 0,
    )
    if row is None:
        row = ContactRow(task_id=task_id, username=username, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.commit()


# ---- Niche ----


def upsert_niche(session: Session, niche: NicheClassification, task_id: str, username: str) -> None:
    stmt = select(NicheRow).where(NicheRow.task_id == task_id, NicheRow.username == username)
    row = session.execute(stmt).scalar_one_or_none()
    fields = dict(
        primary_niche=niche.primary_niche,
        niche_scores=_json_dumps(niche.niche_scores),
        niche_signals=_json_dumps(niche.niche_signals),
        classification_reasons=_json_dumps(niche.classification_reasons),
    )
    if row is None:
        row = NicheRow(task_id=task_id, username=username, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.commit()


# ---- MexicoSignal ----


def upsert_mexico_signal(session: Session, signal: MexicoSignal, task_id: str, username: str) -> None:
    stmt = select(MexicoSignalRow).where(MexicoSignalRow.task_id == task_id, MexicoSignalRow.username == username)
    row = session.execute(stmt).scalar_one_or_none()
    fields = dict(
        mexico_confidence_score=signal.mexico_confidence_score,
        mexico_signals=_json_dumps(signal.mexico_signals),
        detected_country=signal.detected_country,
        detected_state=signal.detected_state,
        detected_city=signal.detected_city,
    )
    if row is None:
        row = MexicoSignalRow(task_id=task_id, username=username, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.commit()


# ---- AccountType ----


def upsert_account_type(session: Session, atype: AccountTypeClassification, task_id: str, username: str) -> None:
    stmt = select(AccountTypeRow).where(AccountTypeRow.task_id == task_id, AccountTypeRow.username == username)
    row = session.execute(stmt).scalar_one_or_none()
    fields = dict(
        account_type=atype.account_type,
        account_type_confidence=atype.account_type_confidence,
        account_type_reasons=_json_dumps(atype.account_type_reasons),
    )
    if row is None:
        row = AccountTypeRow(task_id=task_id, username=username, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.commit()


# ---- 全量加载（用于导出）----


def load_all_records(session: Session, task_id: str) -> list[CreatorRecord]:
    """加载任务下所有分析完成的账号为 CreatorRecord 列表（用于导出）。"""
    records: list[CreatorRecord] = []

    profile_rows = session.execute(select(ProfileRow).where(ProfileRow.task_id == task_id)).scalars()

    for prow in profile_rows:
        username = prow.username

        # 加载关联数据
        mrow = session.execute(
            select(MediaStatsRow).where(MediaStatsRow.task_id == task_id, MediaStatsRow.username == username)
        ).scalar_one_or_none()
        srow = session.execute(
            select(ScoreRow).where(ScoreRow.task_id == task_id, ScoreRow.username == username)
        ).scalar_one_or_none()
        crow = session.execute(
            select(ContactRow).where(ContactRow.task_id == task_id, ContactRow.username == username)
        ).scalar_one_or_none()
        nrow = session.execute(
            select(NicheRow).where(NicheRow.task_id == task_id, NicheRow.username == username)
        ).scalar_one_or_none()
        mxrow = session.execute(
            select(MexicoSignalRow).where(MexicoSignalRow.task_id == task_id, MexicoSignalRow.username == username)
        ).scalar_one_or_none()
        arow = session.execute(
            select(AccountTypeRow).where(AccountTypeRow.task_id == task_id, AccountTypeRow.username == username)
        ).scalar_one_or_none()

        profile = ProfileData(
            username=username,
            pk=prow.pk,
            full_name=prow.full_name,
            biography=prow.biography,
            profile_url=prow.profile_url,
            profile_pic_url=prow.profile_pic_url,
            follower_count=prow.follower_count,
            following_count=prow.following_count,
            media_count=prow.media_count,
            is_private=bool(prow.is_private) if prow.is_private is not None else None,
            is_verified=bool(prow.is_verified) if prow.is_verified is not None else None,
            is_business=bool(prow.is_business) if prow.is_business is not None else None,
            category_name=prow.category_name,
            business_category_name=prow.business_category_name,
            external_url=prow.external_url,
            public_email=prow.public_email,
            collected_at=prow.collected_at or _now(),
        )

        metrics = None
        if mrow is not None:
            metrics = MediaMetrics(
                recent_media_checked=mrow.recent_media_checked,
                recent_reels_checked=mrow.recent_reels_checked,
                last_post_date=mrow.last_post_date,
                days_since_last_post=mrow.days_since_last_post,
                average_likes=mrow.average_likes,
                median_likes=mrow.median_likes,
                average_comments=mrow.average_comments,
                median_comments=mrow.median_comments,
                average_visible_reel_views=mrow.average_visible_reel_views,
                median_visible_reel_views=mrow.median_visible_reel_views,
                maximum_visible_reel_views=mrow.maximum_visible_reel_views,
                posting_frequency=mrow.posting_frequency,
                reels_view_data_available=mrow.reels_view_data_available or "no_reels",
            )

        score = None
        if srow is not None:
            score = ScoreResult(
                total_score=srow.total_score,
                score_breakdown=_json_loads(srow.score_breakdown, {}),
                recommendation_level=srow.recommendation_level,
                recommendation_reasons=_json_loads(srow.recommendation_reasons, []),
            )

        contact = None
        if crow is not None:
            contact = ContactInfo(
                public_email=crow.public_email,
                public_whatsapp_url=crow.public_whatsapp_url,
                external_url=crow.external_url,
                linktree_url=crow.linktree_url,
                beacons_url=crow.beacons_url,
                contact_source=crow.contact_source or "none",
                has_public_contact=bool(crow.has_public_contact),
            )

        niche = None
        if nrow is not None:
            niche = NicheClassification(
                primary_niche=nrow.primary_niche or "general",
                niche_scores=_json_loads(nrow.niche_scores, {}),
                niche_signals=_json_loads(nrow.niche_signals, []),
                classification_reasons=_json_loads(nrow.classification_reasons, []),
            )

        mexico = None
        if mxrow is not None:
            mexico = MexicoSignal(
                mexico_confidence_score=mxrow.mexico_confidence_score,
                mexico_signals=_json_loads(mxrow.mexico_signals, []),
                detected_country=mxrow.detected_country,
                detected_state=mxrow.detected_state,
                detected_city=mxrow.detected_city,
            )

        account_type = None
        if arow is not None:
            account_type = AccountTypeClassification(
                account_type=arow.account_type or "personal_creator",
                account_type_confidence=arow.account_type_confidence,
                account_type_reasons=_json_loads(arow.account_type_reasons, []),
            )

        records.append(
            CreatorRecord(
                username=username,
                profile=profile,
                metrics=metrics,
                contact=contact,
                niche=niche,
                mexico=mexico,
                account_type=account_type,
                score=score,
            )
        )

    return records
