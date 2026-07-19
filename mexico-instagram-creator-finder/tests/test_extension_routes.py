"""扩展 API 路由测试。

用 FastAPI TestClient 测试 /api/extension/* 端点。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.extension.service import ExtensionIngestService
from app.extension.token_store import ExtensionTokenStore


@pytest.fixture
def tmp_token_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "token.txt"
    monkeypatch.setattr(ExtensionTokenStore, "default_path", classmethod(lambda cls: path))
    return path


@pytest.fixture
def service(tmp_path: Path, tmp_token_path: Path) -> ExtensionIngestService:
    db_path = tmp_path / "app.db"
    exclude_path = tmp_path / "exclude.txt"
    exclude_path.write_text("excluded_one\n", encoding="utf-8")

    from app.config import Settings

    settings = Settings(
        checkpoint={"database_file": str(db_path)},
        exclude_files=[str(exclude_path)],
    )
    return ExtensionIngestService(settings=settings)


@pytest.fixture
def client(service: ExtensionIngestService) -> TestClient:
    from app.extension.routes import register_extension_routes

    app = FastAPI()
    register_extension_routes(app, local_api_url="http://127.0.0.1:8080")
    app.state.extension_ingest_service = service
    return TestClient(app)


@pytest.fixture
def token(service: ExtensionIngestService) -> str:
    return service.token


def _auth_headers(token: str) -> dict[str, str]:
    return {"X-Extension-Token": token}


def _make_creator_payload(username: str = "route_creator") -> dict[str, Any]:
    return {
        "source": "instagram_web_extension",
        "collected_at": datetime.now(UTC).isoformat(),
        "page_url": f"https://www.instagram.com/{username}/",
        "profile": {
            "username": username,
            "full_name": "Route Test Creator",
            "biography": "Beauty creator in CDMX",
            "follower_text": "52.4K",
            "following_text": "896",
            "post_count_text": "412",
            "external_links": ["https://linktr.ee/example"],
            "is_verified": False,
        },
    }


# ===== ping =====


class TestPing:
    def test_ping_no_token_required(self, client: TestClient) -> None:
        resp = client.get("/api/extension/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "service" in data


# ===== status =====


class TestStatus:
    def test_status_no_token_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/extension/status")
        assert resp.status_code == 401

    def test_status_wrong_token_returns_401(self, client: TestClient, token: str) -> None:
        resp = client.get(
            "/api/extension/status",
            headers={"X-Extension-Token": "wrong_token"},
        )
        assert resp.status_code == 401

    def test_status_correct_token(self, client: TestClient, token: str) -> None:
        resp = client.get("/api/extension/status", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False  # 还没握手
        assert data["today_collected"] == 0
        assert data["local_api_url"] == "http://127.0.0.1:8080"

    def test_status_after_handshake(self, client: TestClient, token: str) -> None:
        # 先握手
        client.post(
            "/api/extension/handshake",
            json={"extension_version": "0.1.0"},
            headers=_auth_headers(token),
        )
        resp = client.get("/api/extension/status", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["extension_version"] == "0.1.0"


# ===== handshake =====


class TestHandshake:
    def test_handshake_success(self, client: TestClient, token: str) -> None:
        resp = client.post(
            "/api/extension/handshake",
            json={
                "extension_version": "0.1.0",
                "chrome_version": "120.0",
                "user_agent": "Mozilla/5.0",
            },
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "local_api_url" in data

    def test_handshake_no_token_401(self, client: TestClient) -> None:
        resp = client.post(
            "/api/extension/handshake",
            json={"extension_version": "0.1.0"},
        )
        assert resp.status_code == 401


# ===== creator =====


class TestCreatorEndpoint:
    def test_creator_new(self, client: TestClient, token: str) -> None:
        payload = _make_creator_payload(username="route_new")
        resp = client.post(
            "/api/extension/creator",
            json=payload,
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_new"] is True
        assert data["is_duplicate"] is False
        assert data["is_excluded"] is False
        assert data["username"] == "route_new"

    def test_creator_duplicate(self, client: TestClient, token: str) -> None:
        payload = _make_creator_payload(username="route_dup")
        client.post("/api/extension/creator", json=payload, headers=_auth_headers(token))
        resp = client.post("/api/extension/creator", json=payload, headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_new"] is False
        assert data["is_duplicate"] is True

    def test_creator_excluded(self, client: TestClient, token: str) -> None:
        # service fixture 排除名单里有 excluded_one
        payload = _make_creator_payload(username="excluded_one")
        resp = client.post("/api/extension/creator", json=payload, headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_excluded"] is True

    def test_creator_no_token_401(self, client: TestClient) -> None:
        payload = _make_creator_payload()
        resp = client.post("/api/extension/creator", json=payload)
        assert resp.status_code == 401

    def test_creator_invalid_payload_422(self, client: TestClient, token: str) -> None:
        # 缺少必填字段
        resp = client.post(
            "/api/extension/creator",
            json={"source": "x"},  # 缺 page_url / profile / collected_at
            headers=_auth_headers(token),
        )
        assert resp.status_code == 422

    def test_status_reflects_ingest(self, client: TestClient, token: str) -> None:
        # 推送一个新博主
        client.post(
            "/api/extension/creator",
            json=_make_creator_payload(username="stat_check"),
            headers=_auth_headers(token),
        )
        # 状态应反映今日收集 +1
        resp = client.get("/api/extension/status", headers=_auth_headers(token))
        data = resp.json()
        assert data["today_collected"] == 1
        assert data["today_new_candidates"] == 1


class TestTaskDiagnosticsEndpoints:
    def test_events_and_retry_failed_require_token_and_return_data(self, client: TestClient, token: str) -> None:
        created = client.post(
            "/api/extension/tasks",
            json={"seeds": ["diagnostic.creator"], "max_profiles_to_analyze": 1},
            headers=_auth_headers(token),
        )
        task_id = created.json()["task_id"]

        unauthorized = client.get(f"/api/extension/tasks/{task_id}/events")
        events = client.get(f"/api/extension/tasks/{task_id}/events", headers=_auth_headers(token))
        retry = client.post(f"/api/extension/tasks/{task_id}/retry-failed", headers=_auth_headers(token))
        rerank_unauthorized = client.post(
            f"/api/extension/tasks/{task_id}/rerank",
            json={"brief": "墨西哥香水达人，粉丝大于1万"},
        )
        rerank = client.post(
            f"/api/extension/tasks/{task_id}/rerank",
            json={"brief": "墨西哥香水达人，粉丝大于1万"},
            headers=_auth_headers(token),
        )

        assert unauthorized.status_code == 401
        assert events.status_code == 200
        assert events.json()["events"][0]["event_type"] == "task_created"
        assert retry.status_code == 200
        assert retry.json()["retried"] == 0
        assert rerank_unauthorized.status_code == 401
        assert rerank.status_code == 200
        assert rerank.json()["intent"]["min_followers"] == 10_000


# ===== candidates =====


class TestCandidatesEndpoint:
    def test_candidates_push(self, client: TestClient, token: str) -> None:
        payload = {
            "source": "instagram_web_extension",
            "collected_at": datetime.now(UTC).isoformat(),
            "source_page_url": "https://www.instagram.com/seed/",
            "candidates": [
                {"username": "cand_a", "full_name": "A"},
                {"username": "cand_b", "full_name": "B"},
            ],
        }
        resp = client.post(
            "/api/extension/candidates",
            json=payload,
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["new"] == 2
        assert data["duplicates"] == 0

    def test_candidates_no_token_401(self, client: TestClient) -> None:
        payload = {
            "source": "instagram_web_extension",
            "collected_at": datetime.now(UTC).isoformat(),
            "source_page_url": "https://www.instagram.com/seed/",
            "candidates": [],
        }
        resp = client.post("/api/extension/candidates", json=payload)
        assert resp.status_code == 401


class TestTaskEndpoints:
    def test_create_active_claim_pause_resume_and_stop(self, client: TestClient, token: str) -> None:
        headers = _auth_headers(token)
        created = client.post(
            "/api/extension/tasks",
            json={
                "brief": "Mexico perfume creators, 20k-300k followers",
                "seeds": ["seed.creator"],
                "hashtags": ["perfumemexico"],
            },
            headers=headers,
        )
        assert created.status_code == 200
        task_id = created.json()["task_id"]

        active = client.get("/api/extension/tasks/active", headers=headers)
        assert active.status_code == 200
        assert active.json()["task"]["task_id"] == task_id

        claimed = client.post(f"/api/extension/tasks/{task_id}/next", headers=headers)
        assert claimed.status_code == 200
        assert claimed.json()["item"]["page_type"] == "profile"

        assert client.post(f"/api/extension/tasks/{task_id}/pause", headers=headers).json()["status"] == "paused"
        assert client.post(f"/api/extension/tasks/{task_id}/resume", headers=headers).json()["status"] == "running"
        assert client.post(f"/api/extension/tasks/{task_id}/stop", headers=headers).json()["status"] == "stopped"

    def test_review_creator_and_save_to_library(self, client: TestClient, token: str) -> None:
        headers = _auth_headers(token)
        created = client.post(
            "/api/extension/tasks",
            json={"seeds": ["review.creator"]},
            headers=headers,
        ).json()
        task_id = created["task_id"]
        item = client.post(f"/api/extension/tasks/{task_id}/next", headers=headers).json()["item"]
        profile = _make_creator_payload("review.creator")
        profile["queue_item_id"] = item["id"]
        response = client.post(
            f"/api/extension/tasks/{task_id}/profile",
            json=profile,
            headers=headers,
        )
        assert response.status_code == 200

        review = client.get(f"/api/extension/tasks/{task_id}/review/next", headers=headers)
        assert review.status_code == 200
        assert review.json()["creator"]["username"] == "review.creator"

        saved = client.post(
            f"/api/extension/tasks/{task_id}/review/review.creator/save",
            json={"list_name": "默认达人库"},
            headers=headers,
        )
        assert saved.status_code == 200
        assert saved.json()["review_status"] == "saved"


# ===== regenerate-token =====


class TestRegenerateToken:
    def test_regenerate_creates_new_token(self, client: TestClient, token: str) -> None:
        resp = client.post("/api/extension/regenerate-token")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["token"] != token

    def test_old_token_invalid_after_regenerate(self, client: TestClient, token: str) -> None:
        # 重新生成
        resp = client.post("/api/extension/regenerate-token")
        new_token = resp.json()["token"]
        # 旧令牌应失效
        resp = client.get("/api/extension/status", headers=_auth_headers(token))
        assert resp.status_code == 401
        # 新令牌可用
        resp = client.get("/api/extension/status", headers=_auth_headers(new_token))
        assert resp.status_code == 200
