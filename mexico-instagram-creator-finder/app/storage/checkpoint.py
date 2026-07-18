"""断点续传：保存与恢复任务状态。

恢复任务时不得重复请求已分析账号。
支持 AGENTS.md 第 22 节要求的：
- 已完成 Hashtag
- 已发现用户名
- 已分析用户名
- 失败账号与错误原因
- 当前任务状态
- 停止原因
- --resume / --reset-task
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import CheckpointError
from app.logging_config import get_logger
from app.models import TaskCheckpoint
from app.storage.database import CheckpointRow, TaskRow

logger = get_logger("storage.checkpoint")


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


def save_checkpoint(session: Session, checkpoint: TaskCheckpoint) -> None:
    """保存或更新断点。"""
    row = session.get(CheckpointRow, checkpoint.task_id)
    now = _now()
    if row is None:
        row = CheckpointRow(
            task_id=checkpoint.task_id,
            status=checkpoint.status,
            completed_hashtags=_json_dumps(checkpoint.completed_hashtags),
            discovered_usernames=_json_dumps(checkpoint.discovered_usernames),
            analyzed_usernames=_json_dumps(checkpoint.analyzed_usernames),
            failed_usernames=_json_dumps(checkpoint.failed_usernames),
            failed_reasons=_json_dumps(checkpoint.failed_reasons),
            stop_reason=checkpoint.stop_reason,
            started_at=checkpoint.started_at or now,
            updated_at=now,
            completed_at=checkpoint.completed_at,
        )
        session.add(row)
    else:
        row.status = checkpoint.status
        row.completed_hashtags = _json_dumps(checkpoint.completed_hashtags)
        row.discovered_usernames = _json_dumps(checkpoint.discovered_usernames)
        row.analyzed_usernames = _json_dumps(checkpoint.analyzed_usernames)
        row.failed_usernames = _json_dumps(checkpoint.failed_usernames)
        row.failed_reasons = _json_dumps(checkpoint.failed_reasons)
        row.stop_reason = checkpoint.stop_reason
        row.updated_at = now
        if checkpoint.completed_at:
            row.completed_at = checkpoint.completed_at
    session.commit()
    logger.debug("checkpoint saved: task=%s status=%s", checkpoint.task_id, checkpoint.status)


def load_checkpoint(session: Session, task_id: str) -> TaskCheckpoint | None:
    """加载断点。"""
    row = session.get(CheckpointRow, task_id)
    if row is None:
        return None
    return TaskCheckpoint(
        task_id=row.task_id,
        status=row.status or "pending",
        completed_hashtags=_json_loads(row.completed_hashtags, []),
        discovered_usernames=_json_loads(row.discovered_usernames, []),
        analyzed_usernames=_json_loads(row.analyzed_usernames, []),
        failed_usernames=_json_loads(row.failed_usernames, []),
        failed_reasons=_json_loads(row.failed_reasons, {}),
        stop_reason=row.stop_reason,
        started_at=row.started_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def reset_task(session: Session, task_id: str) -> None:
    """重置任务：删除断点与 task 记录。

    注意：candidates/profiles 等子表数据保留，由上层 clear-local-data 命令统一清理；
    本函数仅清理 task 自身与 checkpoint。
    """
    try:
        cp_row = session.get(CheckpointRow, task_id)
        if cp_row is not None:
            session.delete(cp_row)

        task_row = session.get(TaskRow, task_id)
        if task_row is not None:
            session.delete(task_row)

        session.commit()
        logger.info("task %s reset", task_id)
    except Exception as e:
        session.rollback()
        raise CheckpointError(f"failed to reset task {task_id}: {e}") from e


def mark_usernames_analyzed(session: Session, task_id: str, usernames: list[str]) -> None:
    """将用户名标记为已分析（用于增量恢复，避免重复请求）。"""
    cp = load_checkpoint(session, task_id)
    if cp is None:
        cp = TaskCheckpoint(task_id=task_id, status="running", started_at=_now())
    analyzed_set = set(cp.analyzed_usernames)
    for u in usernames:
        analyzed_set.add(u.lower())
    cp.analyzed_usernames = sorted(analyzed_set)
    save_checkpoint(session, cp)


def is_user_analyzed(session: Session, task_id: str, username: str) -> bool:
    """检查用户名是否已分析（恢复任务时跳过，避免重复请求）。"""
    cp = load_checkpoint(session, task_id)
    if cp is None:
        return False
    return username.lower() in set(cp.analyzed_usernames)


def mark_hashtag_completed(session: Session, task_id: str, hashtag: str) -> None:
    """标记 Hashtag 已完成。"""
    cp = load_checkpoint(session, task_id)
    if cp is None:
        cp = TaskCheckpoint(task_id=task_id, status="running", started_at=_now())
    if hashtag not in cp.completed_hashtags:
        cp.completed_hashtags.append(hashtag)
    save_checkpoint(session, cp)


def record_failed_username(session: Session, task_id: str, username: str, reason: str) -> None:
    """记录失败用户名与原因。"""
    cp = load_checkpoint(session, task_id)
    if cp is None:
        cp = TaskCheckpoint(task_id=task_id, status="running", started_at=_now())
    if username not in cp.failed_usernames:
        cp.failed_usernames.append(username)
    cp.failed_reasons[username] = reason
    save_checkpoint(session, cp)


def update_status(session: Session, task_id: str, status: str, stop_reason: str | None = None) -> None:
    """更新任务状态。

    status: pending/running/paused/completed/stopped/failed
    当进入终态（completed/stopped/failed）时自动写入 completed_at。
    """
    cp = load_checkpoint(session, task_id)
    if cp is None:
        cp = TaskCheckpoint(task_id=task_id, status=status, started_at=_now())
    else:
        cp.status = status
    if stop_reason is not None:
        cp.stop_reason = stop_reason
    if status in ("completed", "stopped", "failed"):
        cp.completed_at = _now()
    save_checkpoint(session, cp)
