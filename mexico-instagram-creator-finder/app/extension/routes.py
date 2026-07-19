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
from fastapi.responses import JSONResponse

from app.extension.models import (
    ExtensionCandidatesPayload,
    ExtensionHandshake,
    ExtensionProfilePayload,
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
        logger.info("creator ingested: %s new=%s dup=%s excl=%s",
                    result.username, result.is_new, result.is_duplicate, result.is_excluded)
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
        logger.info("candidates ingested: total=%s new=%s dup=%s excl=%s",
                    result.total, result.new, result.duplicates, result.excluded)
        return result.model_dump(mode="json")

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
