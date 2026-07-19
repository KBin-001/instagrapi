"""领域模型：搜索相关的基础类型。

展示层（CLI/GUI）与服务层（SearchService）通过这些类型通信：
- SearchConfig：搜索输入参数（包装 Settings + hashtags + dry_run）
- SearchProgress：结构化进度回调
- SearchResult：搜索输出（task_id、记录数、导出路径、停止原因）
- CancellationToken：取消令牌（线程安全的协作式取消）
- TaskStatus：统一任务状态枚举
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class TaskStatus(StrEnum):
    """统一任务状态枚举。

    SQLite 表中使用字符串值（小写），与现有数据库兼容。
    """

    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"  # 用户请求取消，正在保存断点
    STOPPED = "stopped"  # 已安全停止（用户取消或安全异常）
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"  # 触发限流（HTTP 429 等）
    VERIFICATION_REQUIRED = "verification_required"  # 需要 Challenge 验证


# 阶段标识：作为 SearchProgress.stage 的值
STAGE_LOGIN = "login"
STAGE_DISCOVERY = "discovery"
STAGE_DEDUPLICATION = "deduplication"
STAGE_EXCLUSION = "exclusion"
STAGE_PROFILE_ANALYSIS = "profile_analysis"
STAGE_EXPORT = "export"
STAGE_COMPLETED = "completed"


@dataclass
class SearchConfig:
    """搜索输入参数。

    包装 Settings + 已解析的 hashtags + 运行模式标志。
    服务层只读此对象，不修改 Settings。
    """

    settings: object  # app.config.Settings，避免循环导入用 object
    hashtags: list[str]
    dry_run: bool = False
    resume: bool = False
    reset_task: bool = False


@dataclass
class SearchProgress:
    """结构化进度回调。

    GUI/CLI 收到此对象后更新 UI，不直接关心 Instagram 请求细节。
    所有字段都有默认值，便于服务层只填充当前阶段关心的字段。
    """

    stage: str = ""
    current_hashtag: str | None = None
    hashtags_completed: int = 0
    hashtags_total: int = 0
    candidates_found: int = 0
    candidates_kept: int = 0
    profiles_total: int = 0  # 待分析总数（PROFILE_ANALYSIS 阶段）
    profiles_analyzed: int = 0  # 已分析（含匹配+跳过+失败）
    profiles_matched: int = 0
    profiles_skipped: int = 0
    profiles_failed: int = 0
    current_username: str | None = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


# 进度回调签名
ProgressCallback = Callable[[SearchProgress], None]


@dataclass
class SearchResult:
    """搜索输出。

    服务层 run() 返回此对象，展示层据此决定如何显示结果。
    """

    task_id: str
    status: TaskStatus
    records_count: int = 0
    exported_files: dict[str, str] = field(default_factory=dict)  # {"csv": "/path/...", "json": "..."}
    stop_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CancellationToken:
    """线程安全的协作式取消令牌。

    使用方式：
        token = CancellationToken()
        # 在另一线程中：token.cancel()
        # 在服务循环中：
        if token.is_cancelled:
            save_checkpoint()
            return

    设计要点：
    - 不强制中断线程，避免 SQLite 写入中断或 Session 文件损坏
    - 服务循环在每个安全步骤（账号之间、Hashtag 之间）检查
    - 一旦取消，任务状态转为 STOPPING → STOPPED
    """

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        """请求取消。线程安全，可从任意线程调用。"""
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        """是否已请求取消。"""
        return self._cancelled.is_set()

    def reset(self) -> None:
        """重置令牌（用于复用）。"""
        self._cancelled.clear()
