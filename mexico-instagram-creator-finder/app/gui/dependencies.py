"""GUI 应用级依赖容器。

所有页面通过此模块获取共享服务实例，不直接创建 Client 或 IngestService。
"""

from __future__ import annotations

from app.extension.service import ExtensionIngestService

_ingest_service: ExtensionIngestService | None = None


def get_ingest_service() -> ExtensionIngestService:
    """获取全局 ExtensionIngestService 单例（延迟初始化）。"""
    global _ingest_service
    if _ingest_service is None:
        _ingest_service = ExtensionIngestService()
    return _ingest_service


def reset_ingest_service() -> None:
    """重置 IngestService（令牌重新生成等场景调用）。"""
    global _ingest_service
    if _ingest_service is not None:
        _ingest_service.close()
    _ingest_service = None
