"""扩展数据接收服务。

职责：
- 校验扩展令牌
- 接收扩展推送的博主 / 候选账号
- 解析网页文本数字（如 "52.4K" → 52400）
- 转换为 ProfileData / CandidateAccount 落库（task_id = EXTENSION_TASK_ID）
- 维护今日统计（按 UTC 日期重置）

仅处理公开数据；不接收 Cookie / Session / 密码；不实现账号互动。
"""

from __future__ import annotations

import re
import threading
from datetime import UTC, date, datetime
from pathlib import Path

from app.config import Settings, build_settings
from app.extension.models import (
    CandidatesIngestResult,
    ExtensionCandidatesPayload,
    ExtensionProfilePayload,
    ExtensionStatusResponse,
    IngestResult,
)
from app.extension.token_store import ExtensionTokenStore
from app.logging_config import get_logger
from app.models import CandidateAccount, ProfileData
from app.storage.database import Database
from app.storage.repositories import (
    get_candidate,
    upsert_account_type,
    upsert_candidate,
    upsert_contact,
    upsert_mexico_signal,
    upsert_niche,
    upsert_profile,
)

logger = get_logger("extension.ingest")

# 扩展采集的所有账号统一归属此 task_id
EXTENSION_TASK_ID = "extension_ingest"


# 数字文本解析正则：匹配 "52.4K"、"1,234"、"1.2M"、"1,234,567" 等
_COUNT_RE = re.compile(r"([\d][\d.,]*)\s*([kKmMbB]|万)?")


def parse_count_text(text: str | None) -> int | None:
    """解析 Instagram 网页上显示的数字文本。

    Examples:
        "52.4K" → 52400
        "1,234" → 1234
        "1.2M"  → 1200000
        "12,345" → 12345
        None / "" / "N/A" → None

    仅取第一个匹配的数字段；遇到非数字返回 None。
    """
    if not text:
        return None
    m = _COUNT_RE.search(text)
    if not m:
        return None
    num_str = m.group(1).replace(",", "")
    suffix = (m.group(2) or "").lower()
    try:
        num = float(num_str)
    except ValueError:
        return None
    if suffix == "k":
        num *= 1_000
    elif suffix == "m":
        num *= 1_000_000
    elif suffix == "b":
        num *= 1_000_000_000
    elif suffix == "万":
        num *= 10_000
    return int(num)


class ExtensionIngestService:
    """扩展数据接收服务（线程安全单例）。"""

    def __init__(self, settings: Settings | None = None, local_api_url: str | None = None) -> None:
        self.settings: Settings = settings or build_settings()
        self.local_api_url: str | None = local_api_url
        self.token_store = ExtensionTokenStore()
        self._lock = threading.Lock()
        # 连接状态
        self._extension_version: str | None = None
        self._last_handshake_at: datetime | None = None
        # 今日统计（按 UTC 日期重置）
        self._stats_date: date | None = None
        self._today_collected = 0
        self._today_new_candidates = 0
        self._today_duplicates = 0
        self._today_excluded = 0

    def close(self) -> None:
        """资源释放占位（当前无外部资源需要释放）。"""
        return

    def set_local_api_url(self, url: str) -> None:
        """设置本地 API 地址（gui_main.py 启动时调用）。"""
        self.local_api_url = url

    # ===== 令牌 =====

    @property
    def token(self) -> str:
        """当前令牌（不存在则自动生成）。"""
        return self.token_store.get_or_create()

    def regenerate_token(self) -> str:
        """重新生成令牌（旧扩展需要重新输入新令牌）。"""
        return self.token_store.regenerate()

    def verify_token(self, token: str | None) -> bool:
        return self.token_store.verify(token)

    # ===== 握手与状态 =====

    def handshake(
        self,
        extension_version: str,
        chrome_version: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """记录扩展握手信息。"""
        with self._lock:
            self._extension_version = extension_version
            self._last_handshake_at = datetime.now(UTC)
            logger.info(
                "extension handshake: version=%s chrome=%s",
                extension_version,
                chrome_version,
            )

    def status(self, local_api_url: str | None = None) -> ExtensionStatusResponse:
        """返回当前扩展连接状态与今日统计。

        local_api_url 优先使用参数（路由调用），否则使用 self.local_api_url
        （gui_main.py 启动时注入），保证设置页/概览页直接调用 service.status()
        也能拿到正确的接口地址。
        """
        url = local_api_url or self.local_api_url
        with self._lock:
            self._reset_stats_if_new_day()
            return ExtensionStatusResponse(
                connected=self._last_handshake_at is not None,
                extension_version=self._extension_version,
                last_handshake_at=self._last_handshake_at,
                today_collected=self._today_collected,
                today_new_candidates=self._today_new_candidates,
                today_duplicates=self._today_duplicates,
                today_excluded=self._today_excluded,
                local_api_url=url,
            )

    # ===== 数据接收 =====

    def ingest_creator(self, payload: ExtensionProfilePayload) -> IngestResult:
        """接收一个博主并落库（场景一：保存当前博主）。"""
        username = (payload.profile.username or "").strip().lower()
        if not username:
            return IngestResult(username="", error="username is empty")

        with self._lock:
            self._reset_stats_if_new_day()
            self._today_collected += 1

        excluded_usernames = self._load_excluded_usernames()

        db = Database(self.settings.checkpoint.database_file)
        session = db.get_session()
        try:
            existing = get_candidate(session, EXTENSION_TASK_ID, username)
            is_duplicate = existing is not None
            is_excluded = username in excluded_usernames

            profile = self._to_profile_data(payload)
            upsert_profile(session, profile, EXTENSION_TASK_ID)

            candidate = CandidateAccount(
                username=username,
                source_hashtags=["extension"],
                discovered_at=payload.collected_at,
                normalized=True,
            )
            upsert_candidate(
                session,
                candidate,
                EXTENSION_TASK_ID,
                excluded=is_excluded,
                exclusion_source="exclude_list" if is_excluded else None,
                exclusion_reason="用户排除名单匹配" if is_excluded else None,
            )

            # 步骤 8：调用分析模块对博主进行分类（niche / mexico / contact / account_type）
            # 注意：扩展不提供 recent media，所以 media_metrics / scoring 跳过
            self._analyze_creator(session, profile)

            session.commit()
        except Exception as e:  # noqa: BLE001
            logger.exception("ingest_creator failed for %s", username)
            return IngestResult(username=username, error=str(e))
        finally:
            session.close()
            db.close()

        with self._lock:
            if is_excluded:
                self._today_excluded += 1
            elif is_duplicate:
                self._today_duplicates += 1
            else:
                self._today_new_candidates += 1

        return IngestResult(
            username=username,
            is_new=not is_duplicate and not is_excluded,
            is_duplicate=is_duplicate,
            is_excluded=is_excluded,
        )

    def ingest_candidates(self, payload: ExtensionCandidatesPayload) -> CandidatesIngestResult:
        """接收候选账号列表并落库（场景二/三）。"""

        with self._lock:
            self._reset_stats_if_new_day()
            self._today_collected += len(payload.candidates)

        excluded_usernames = self._load_excluded_usernames()

        db = Database(self.settings.checkpoint.database_file)
        session = db.get_session()
        new_count = 0
        dup_count = 0
        excl_count = 0
        skipped = 0
        try:
            for item in payload.candidates:
                username = (item.username or "").strip().lower()
                if not username:
                    skipped += 1
                    continue

                existing = get_candidate(session, EXTENSION_TASK_ID, username)
                is_dup = existing is not None
                is_excl = username in excluded_usernames

                candidate = CandidateAccount(
                    username=username,
                    source_hashtags=["extension"],
                    discovered_at=payload.collected_at,
                    normalized=True,
                )
                upsert_candidate(
                    session,
                    candidate,
                    EXTENSION_TASK_ID,
                    excluded=is_excl,
                    exclusion_source="exclude_list" if is_excl else None,
                    exclusion_reason="用户排除名单匹配" if is_excl else None,
                )
                if is_excl:
                    excl_count += 1
                elif is_dup:
                    dup_count += 1
                else:
                    new_count += 1
            session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("ingest_candidates failed")
            return CandidatesIngestResult(total=len(payload.candidates))
        finally:
            session.close()
            db.close()

        with self._lock:
            self._today_new_candidates += new_count
            self._today_duplicates += dup_count
            self._today_excluded += excl_count

        return CandidatesIngestResult(
            total=len(payload.candidates),
            new=new_count,
            duplicates=dup_count,
            excluded=excl_count,
        )

    # ===== 内部辅助 =====

    def _load_excluded_usernames(self) -> set[str]:
        """加载排除名单中的用户名集合（小写）。"""
        if not self.settings.exclude_files:
            return set()
        try:
            from app.discovery.seeds import parse_exclude_paths, parse_exclude_strings

            file_paths = [p for p in self.settings.exclude_files if Path(p).exists()]
            str_items = [p for p in self.settings.exclude_files if not Path(p).exists()]
            entries = parse_exclude_paths(file_paths) + parse_exclude_strings(str_items)
            return {e.username.lower() for e in entries}
        except Exception:  # noqa: BLE001
            return set()

    def _to_profile_data(self, payload: ExtensionProfilePayload) -> ProfileData:
        """将扩展 payload 转为 ProfileData。"""
        p = payload.profile
        followers = parse_count_text(p.follower_text)
        following = parse_count_text(p.following_text)
        posts = parse_count_text(p.post_count_text)

        external_url = p.external_links[0] if p.external_links else None

        return ProfileData(
            username=p.username,
            full_name=p.full_name,
            biography=p.biography,
            profile_url=payload.page_url,
            profile_pic_url=p.profile_pic_url,
            follower_count=followers,
            following_count=following,
            media_count=posts,
            is_private=p.is_private,
            is_verified=p.is_verified,
            is_business=p.is_business,
            category_name=p.category_name,
            external_url=external_url,
            public_email=p.public_email,
            field_sources=p.field_sources,
            collected_at=payload.collected_at,
        )

    def _analyze_creator(self, session, profile: ProfileData) -> None:
        """调用分析模块对博主进行分类（步骤 8）。

        仅基于 ProfileData 即可分析：
        - classify_niche：基于 bio、name、category、来源 hashtag（无 recent captions）
        - detect_mexico_signal：基于 bio、name、来源 hashtag
        - extract_contacts：基于 bio 中的邮箱/wa.me/linktree
        - classify_account_type：基于 follower 区间、bio 关键词

        跳过（需要 recent media）：
        - analyze_media_metrics：无 recent media
        - compute_score：scoring 依赖 media_metrics
        """
        from app.analysis.account_classifier import classify_account_type
        from app.analysis.contact_extractor import extract_contacts
        from app.analysis.mexico_detector import detect_mexico_signal
        from app.analysis.niche_classifier import classify_niche

        try:
            niche = classify_niche(
                profile,
                source_hashtags=["extension"],
                recent_captions=None,
                recent_media_hashtags=None,
            )
            upsert_niche(session, niche, EXTENSION_TASK_ID, profile.username)
        except Exception:  # noqa: BLE001
            logger.exception("classify_niche failed for %s", profile.username)

        try:
            mexico = detect_mexico_signal(
                profile,
                source_hashtags=["extension"],
                recent_captions=None,
            )
            upsert_mexico_signal(session, mexico, EXTENSION_TASK_ID, profile.username)
        except Exception:  # noqa: BLE001
            logger.exception("detect_mexico_signal failed for %s", profile.username)

        try:
            contact = extract_contacts(profile)
            upsert_contact(session, contact, EXTENSION_TASK_ID, profile.username)
        except Exception:  # noqa: BLE001
            logger.exception("extract_contacts failed for %s", profile.username)

        try:
            account_type = classify_account_type(
                profile,
                source_hashtags=["extension"],
            )
            upsert_account_type(session, account_type, EXTENSION_TASK_ID, profile.username)
        except Exception:  # noqa: BLE001
            logger.exception("classify_account_type failed for %s", profile.username)

    def _reset_stats_if_new_day(self) -> None:
        """跨 UTC 日时重置今日统计。"""
        today = datetime.now(UTC).date()
        if self._stats_date != today:
            self._stats_date = today
            self._today_collected = 0
            self._today_new_candidates = 0
            self._today_duplicates = 0
            self._today_excluded = 0
