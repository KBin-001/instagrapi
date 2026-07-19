"""扩展通信 API 路由（FastAPI）。

挂载到 NiceGUI 共享的 FastAPI app 上：
    from nicegui import app
    register_extension_routes(app)

端点：
- POST /api/extension/handshake       扩展握手
- POST /api/extension/creator         推送单个博主
- POST /api/extension/candidates      推送候选账号列表
- GET  /api/extension/status          查询状态
- GET  /api/extension/ping            无令牌健康检查
- POST /api/extension/regenerate-token 重新生成本地令牌（仅本机调用）

令牌校验：除 /ping 之外的所有端点都需要在请求头中携带 X-Extension-Token。
"""

from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException, Request

from app.extension.models import (
    CreatorReviewAction,
    ExtensionCandidatesPayload,
    ExtensionHandshake,
    ExtensionMediaPayload,
    ExtensionProfilePayload,
    ExtensionTaskCreate,
    QueueFailurePayload,
    TaskCandidatesPayload,
    TaskProfilePayload,
    TaskRerankPayload,
)
from app.logging_config import get_logger

logger = get_logger("extension.routes")


def _get_ingest_service(request: Request):
    """从 app.state 获取 ExtensionIngestService 单例。"""
    service = getattr(request.app.state, "extension_ingest_service", None)
    if service is None:
        from app.gui.dependencies import get_ingest_service

        service = get_ingest_service()
        request.app.state.extension_ingest_service = service
    return service


def _verify_token(service, token: str | None) -> None:
    """校验令牌；失败抛 401。"""
    if not service.verify_token(token):
        raise HTTPException(status_code=401, detail="invalid or missing X-Extension-Token")


def _get_task_service(request: Request):
    service = getattr(request.app.state, "extension_task_service", None)
    if service is None:
        from app.extension.task_service import ExtensionTaskService

        ingest = _get_ingest_service(request)
        service = ExtensionTaskService(settings=ingest.settings, connected_service=ingest)
        request.app.state.extension_task_service = service
    return service


def register_extension_routes(app: Any, local_api_url: str | None = None) -> None:
    """在 FastAPI app 上注册 /api/extension/* 路由。

    Args:
        app: nicegui.app（FastAPI 实例）
        local_api_url: 用于状态响应中告知扩展本机 API 地址
                       （如 "http://127.0.0.1:8080"）
    """

    @app.get("/api/extension/ping")
    async def extension_ping() -> dict:
        """健康检查（无需令牌）。"""
        return {"ok": True, "service": "mexico-creator-finder-extension"}

    @app.get("/api/extension/status")
    async def extension_status(
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        service = _get_ingest_service(request)
        _verify_token(service, x_extension_token)
        return service.status(local_api_url=local_api_url).model_dump(mode="json")

    @app.post("/api/extension/handshake")
    async def extension_handshake(
        payload: ExtensionHandshake,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        service = _get_ingest_service(request)
        _verify_token(service, x_extension_token)
        service.handshake(
            extension_version=payload.extension_version,
            chrome_version=payload.chrome_version,
            user_agent=payload.user_agent,
        )
        return {
            "ok": True,
            "message": "handshake accepted",
            "local_api_url": local_api_url,
        }

    @app.post("/api/extension/creator")
    async def extension_receive_creator(
        payload: ExtensionProfilePayload,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        service = _get_ingest_service(request)
        _verify_token(service, x_extension_token)
        result = service.ingest_creator(payload)
        logger.info(
            "creator ingested: %s new=%s dup=%s excl=%s",
            result.username,
            result.is_new,
            result.is_duplicate,
            result.is_excluded,
        )
        return result.model_dump(mode="json")

    @app.post("/api/extension/candidates")
    async def extension_receive_candidates(
        payload: ExtensionCandidatesPayload,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        service = _get_ingest_service(request)
        _verify_token(service, x_extension_token)
        result = service.ingest_candidates(payload)
        logger.info(
            "candidates ingested: total=%s new=%s dup=%s excl=%s",
            result.total,
            result.new,
            result.duplicates,
            result.excluded,
        )
        return result.model_dump(mode="json")

    @app.post("/api/extension/tasks")
    async def create_extension_task(
        payload: ExtensionTaskCreate,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).create_task(payload)

    @app.get("/api/extension/tasks/active")
    async def active_extension_task(
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return {"task": _get_task_service(request).active_task()}

    @app.get("/api/extension/tasks/review-active")
    async def review_active_task(
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return {"task": _get_task_service(request).review_task()}

    @app.post("/api/extension/tasks/{task_id}/next")
    async def next_extension_item(
        task_id: str,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).next_item(task_id)

    @app.post("/api/extension/tasks/{task_id}/candidates")
    async def submit_task_candidates(
        task_id: str,
        payload: TaskCandidatesPayload,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).submit_candidates(task_id, payload)

    @app.post("/api/extension/tasks/{task_id}/profile")
    async def submit_task_profile(
        task_id: str,
        payload: TaskProfilePayload,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).submit_profile(task_id, payload)

    @app.post("/api/extension/tasks/{task_id}/media")
    async def submit_task_media(
        task_id: str,
        payload: ExtensionMediaPayload,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).submit_media(task_id, payload)

    @app.post("/api/extension/tasks/{task_id}/failure")
    async def report_task_failure(
        task_id: str,
        payload: QueueFailurePayload,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).report_failure(task_id, payload)

    @app.get("/api/extension/tasks/{task_id}/events")
    async def task_events(
        task_id: str,
        request: Request,
        limit: int = 200,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return {"events": _get_task_service(request).events(task_id, limit)}

    @app.post("/api/extension/tasks/{task_id}/retry-failed")
    async def retry_failed_items(
        task_id: str,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).retry_failed(task_id)

    @app.post("/api/extension/tasks/{task_id}/rerank")
    async def rerank_task_candidates(
        task_id: str,
        payload: TaskRerankPayload,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return _get_task_service(request).rerank_candidates(task_id, payload)

    @app.get("/api/extension/tasks/{task_id}/review/next")
    async def next_review_creator(
        task_id: str,
        request: Request,
        x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
    ) -> dict:
        ingest = _get_ingest_service(request)
        _verify_token(ingest, x_extension_token)
        return {"creator": _get_task_service(request).next_review_creator(task_id)}

    def make_review_endpoint(action: str):
        async def review_creator(
            task_id: str,
            username: str,
            payload: CreatorReviewAction,
            request: Request,
            x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
        ) -> dict:
            ingest = _get_ingest_service(request)
            _verify_token(ingest, x_extension_token)
            return _get_task_service(request).review_creator(
                task_id,
                username,
                action,
                list_name=payload.list_name,
                note=payload.note,
            )

        return review_creator

    for review_action in ("save", "skip"):
        review_path = f"/api/extension/tasks/{{task_id}}/review/{{username}}/{review_action}"
        app.post(review_path, name=f"extension_review_{review_action}")(make_review_endpoint(review_action))

    def make_control_endpoint(action: str):
        async def control_extension_task(
            task_id: str,
            request: Request,
            x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
        ) -> dict:
            ingest = _get_ingest_service(request)
            _verify_token(ingest, x_extension_token)
            return _get_task_service(request).control(task_id, action)

        return control_extension_task

    for action in ("pause", "resume", "stop"):
        path = f"/api/extension/tasks/{{task_id}}/{action}"
        app.post(path, name=f"extension_task_{action}")(make_control_endpoint(action))

    @app.post("/api/extension/regenerate-token")
    async def extension_regenerate_token(request: Request) -> dict:
        """重新生成本地令牌。

        仅允许本机调用（FastAPI 已绑定 127.0.0.1，无需额外校验）。
        调用后旧令牌立即失效，已连接的扩展需重新输入新令牌。
        """
        service = _get_ingest_service(request)
        new_token = service.regenerate_token()
        logger.info("extension token regenerated")
        return {"ok": True, "token": new_token}

    logger.info("extension routes registered at /api/extension/*")
