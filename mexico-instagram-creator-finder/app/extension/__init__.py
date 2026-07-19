"""浏览器扩展通信模块。

为 Chrome 扩展（browser_extension/）提供本地 HTTP 接口，接收扩展从
Instagram 官方网页采集的公开数据，落库到 SQLite，复用现有的分析、
评分、导出模块。

接口列表（routes.py）：
- POST /api/extension/handshake     扩展握手，校验令牌
- POST /api/extension/creator       推送单个博主
- POST /api/extension/candidates    推送候选账号列表
- GET  /api/extension/status        查询连接状态与今日统计
"""

from app.extension.models import (
    ExtensionCandidateItem,
    ExtensionCandidatesPayload,
    ExtensionHandshake,
    ExtensionProfileData,
    ExtensionProfilePayload,
    ExtensionStatusResponse,
)
from app.extension.service import ExtensionIngestService
from app.extension.token_store import ExtensionTokenStore

__all__ = [
    "ExtensionCandidateItem",
    "ExtensionCandidatesPayload",
    "ExtensionHandshake",
    "ExtensionIngestService",
    "ExtensionProfileData",
    "ExtensionProfilePayload",
    "ExtensionStatusResponse",
    "ExtensionTokenStore",
]
