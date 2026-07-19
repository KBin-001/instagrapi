"""ExtensionIngestService 单元测试。

覆盖：
- 粉丝数文本解析（parse_count_text）
- ProfileData 转换（_to_profile_data）
- 令牌生成与校验
- 单个博主入库（新增 / 重复 / 排除名单）
- 候选账号列表入库
- 今日统计
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.extension.models import (
    ExtensionCandidateItem,
    ExtensionCandidatesPayload,
    ExtensionProfileData,
    ExtensionProfilePayload,
)
from app.extension.service import EXTENSION_TASK_ID, ExtensionIngestService, parse_count_text
from app.extension.token_store import ExtensionTokenStore


@pytest.fixture
def tmp_token_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """临时令牌文件路径。"""
    path = tmp_path / "token.txt"
    # 让 default_path 返回临时路径
    monkeypatch.setattr(ExtensionTokenStore, "default_path", classmethod(lambda cls: path))
    return path


@pytest.fixture
def service(tmp_path: Path, tmp_token_path: Path, monkeypatch: pytest.MonkeyPatch) -> ExtensionIngestService:
    """创建临时数据库与排除名单的 ExtensionIngestService 实例。"""
    db_path = tmp_path / "app.db"
    exclude_path = tmp_path / "exclude.txt"
    exclude_path.write_text("excluded_user_one\nexcluded_user_two\n", encoding="utf-8")

    from app.config import Settings

    settings = Settings(
        checkpoint={"database_file": str(db_path)},
        exclude_files=[str(exclude_path)],
    )
    return ExtensionIngestService(settings=settings)


# ===== parse_count_text =====


class TestParseCountText:
    """粉丝数文本解析。"""

    def test_plain_number(self) -> None:
        assert parse_count_text("1234") == 1234

    def test_thousands_with_comma(self) -> None:
        assert parse_count_text("1,234") == 1234
        assert parse_count_text("12,345,678") == 12345678

    def test_k_suffix(self) -> None:
        assert parse_count_text("52.4K") == 52400
        assert parse_count_text("1K") == 1000
        assert parse_count_text("12.5k") == 12500

    def test_m_suffix(self) -> None:
        assert parse_count_text("1.2M") == 1200000
        assert parse_count_text("3.5m") == 3500000

    def test_b_suffix(self) -> None:
        assert parse_count_text("1.5B") == 1500000000

    def test_with_text_around(self) -> None:
        # Instagram 网页文本通常带 "followers" 等字样
        assert parse_count_text("52.4K followers") == 52400
        assert parse_count_text("896 following") == 896

    def test_none(self) -> None:
        assert parse_count_text(None) is None

    def test_empty(self) -> None:
        assert parse_count_text("") is None

    def test_non_numeric(self) -> None:
        assert parse_count_text("N/A") is None
        assert parse_count_text("unknown") is None


# ===== Token =====


class TestTokenStore:
    """令牌存储。"""

    def test_get_or_create_generates_token(self, tmp_token_path: Path) -> None:
        store = ExtensionTokenStore()
        token = store.get_or_create()
        assert isinstance(token, str)
        assert len(token) >= 30
        assert tmp_token_path.exists()
        assert tmp_token_path.read_text(encoding="utf-8").strip() == token

    def test_get_or_create_returns_existing(self, tmp_token_path: Path) -> None:
        store = ExtensionTokenStore()
        token1 = store.get_or_create()
        token2 = store.get_or_create()
        assert token1 == token2

    def test_regenerate_creates_new_token(self, tmp_token_path: Path) -> None:
        store = ExtensionTokenStore()
        token1 = store.get_or_create()
        token2 = store.regenerate()
        assert token1 != token2
        assert tmp_token_path.read_text(encoding="utf-8").strip() == token2

    def test_verify_success(self, tmp_token_path: Path) -> None:
        store = ExtensionTokenStore()
        token = store.get_or_create()
        assert store.verify(token) is True

    def test_verify_none(self, tmp_token_path: Path) -> None:
        store = ExtensionTokenStore()
        assert store.verify(None) is False
        assert store.verify("") is False

    def test_verify_wrong_token(self, tmp_token_path: Path) -> None:
        store = ExtensionTokenStore()
        store.get_or_create()
        assert store.verify("wrong_token") is False

    def test_delete(self, tmp_token_path: Path) -> None:
        store = ExtensionTokenStore()
        store.get_or_create()
        assert store.delete() is True
        assert not tmp_token_path.exists()
        assert store.delete() is False


# ===== Ingest creator =====


def _make_profile_payload(
    username: str = "test_creator",
    full_name: str = "Test Creator",
    biography: str = "Beauty & lifestyle creator in CDMX",
    follower_text: str = "52.4K",
    following_text: str = "896",
    post_count_text: str = "412",
    external_links: list[str] | None = None,
    is_verified: bool = False,
) -> ExtensionProfilePayload:
    """构造测试用 ExtensionProfilePayload。"""
    return ExtensionProfilePayload(
        collected_at=datetime.now(UTC),
        page_url=f"https://www.instagram.com/{username}/",
        profile=ExtensionProfileData(
            username=username,
            full_name=full_name,
            biography=biography,
            follower_text=follower_text,
            following_text=following_text,
            post_count_text=post_count_text,
            external_links=external_links or [],
            is_verified=is_verified,
        ),
    )


class TestIngestCreator:
    """单个博主入库。"""

    def test_new_creator(self, service: ExtensionIngestService) -> None:
        payload = _make_profile_payload(username="new_creator")
        result = service.ingest_creator(payload)
        assert result.is_new is True
        assert result.is_duplicate is False
        assert result.is_excluded is False
        assert result.username == "new_creator"

    def test_duplicate_creator(self, service: ExtensionIngestService) -> None:
        payload = _make_profile_payload(username="dup_creator")
        service.ingest_creator(payload)
        result = service.ingest_creator(payload)
        assert result.is_new is False
        assert result.is_duplicate is True
        assert result.is_excluded is False

    def test_excluded_creator(self, service: ExtensionIngestService) -> None:
        # 排除名单里是 excluded_user_one / excluded_user_two
        payload = _make_profile_payload(username="excluded_user_one")
        result = service.ingest_creator(payload)
        assert result.is_new is False
        assert result.is_duplicate is False
        assert result.is_excluded is True

    def test_username_case_insensitive(self, service: ExtensionIngestService) -> None:
        # 大写用户名应被规范化为小写
        payload = _make_profile_payload(username="CaseTest")
        result = service.ingest_creator(payload)
        assert result.username == "casetest"
        assert result.is_new is True

    def test_empty_username_returns_error(self, service: ExtensionIngestService) -> None:
        payload = _make_profile_payload(username="")
        result = service.ingest_creator(payload)
        assert result.username == ""
        assert result.error is not None

    def test_profile_data_persisted(self, service: ExtensionIngestService) -> None:
        """落库后 ProfileData 字段正确解析。"""
        payload = _make_profile_payload(
            username="persist_test",
            follower_text="52.4K",
            following_text="896",
            post_count_text="412",
            external_links=["https://linktr.ee/example", "https://example.com"],
            is_verified=True,
        )
        service.ingest_creator(payload)

        # 从数据库查询
        from app.storage.database import Database, ProfileRow
        from sqlalchemy import select

        db = Database(service.settings.checkpoint.database_file)
        session = db.get_session()
        try:
            row = session.execute(
                select(ProfileRow).where(
                    ProfileRow.task_id == EXTENSION_TASK_ID,
                    ProfileRow.username == "persist_test",
                )
            ).scalar_one()
            assert row.follower_count == 52400
            assert row.following_count == 896
            assert row.media_count == 412
            assert row.external_url == "https://linktr.ee/example"
            assert row.is_verified == 1
        finally:
            session.close()
            db.close()


# ===== Ingest candidates =====


def _make_candidates_payload(candidates: list[ExtensionCandidateItem]) -> ExtensionCandidatesPayload:
    return ExtensionCandidatesPayload(
        collected_at=datetime.now(UTC),
        source_page_url="https://www.instagram.com/test_seed/",
        candidates=candidates,
    )


class TestIngestCandidates:
    """候选账号列表入库。"""

    def test_mixed_candidates(self, service: ExtensionIngestService) -> None:
        """新 / 重复 / 排除 混合。"""
        # 先入库一个，制造重复
        service.ingest_creator(_make_profile_payload(username="dup_user"))

        payload = _make_candidates_payload(
            [
                ExtensionCandidateItem(username="new_user_1"),
                ExtensionCandidateItem(username="dup_user"),
                ExtensionCandidateItem(username="excluded_user_one"),
                ExtensionCandidateItem(username="new_user_2"),
            ]
        )
        result = service.ingest_candidates(payload)
        assert result.total == 4
        assert result.new == 2
        assert result.duplicates == 1
        assert result.excluded == 1

    def test_empty_candidates(self, service: ExtensionIngestService) -> None:
        result = service.ingest_candidates(_make_candidates_payload([]))
        assert result.total == 0
        assert result.new == 0

    def test_empty_username_skipped(self, service: ExtensionIngestService) -> None:
        payload = _make_candidates_payload(
            [ExtensionCandidateItem(username=""), ExtensionCandidateItem(username="valid_user")]
        )
        result = service.ingest_candidates(payload)
        # 空 username 被跳过，不计入 total 之外的统计
        assert result.new == 1


# ===== Stats =====


class TestStats:
    """今日统计。"""

    def test_stats_increment_after_ingest(self, service: ExtensionIngestService) -> None:
        service.ingest_creator(_make_profile_payload(username="stat_user_1"))
        service.ingest_creator(_make_profile_payload(username="stat_user_2"))
        status = service.status()
        assert status.today_collected == 2
        assert status.today_new_candidates == 2

    def test_stats_duplicate_counts(self, service: ExtensionIngestService) -> None:
        service.ingest_creator(_make_profile_payload(username="stat_user"))
        service.ingest_creator(_make_profile_payload(username="stat_user"))
        status = service.status()
        assert status.today_collected == 2
        assert status.today_new_candidates == 1
        assert status.today_duplicates == 1

    def test_status_connected_false_initially(self, service: ExtensionIngestService) -> None:
        status = service.status()
        assert status.connected is False

    def test_status_connected_true_after_handshake(self, service: ExtensionIngestService) -> None:
        service.handshake(extension_version="0.1.0")
        status = service.status()
        assert status.connected is True
        assert status.extension_version == "0.1.0"
