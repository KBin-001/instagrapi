"""Instagram Session 文件加载/保存。

约束：
- Session 文件路径来自配置
- Session 内容不写入日志、数据库
- 仅保存到本地文件，不上传到 Git
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("mexico_finder.instagram.session")


def load_session(session_file: Path | str) -> dict[str, Any] | None:
    """
    从文件加载 Session。

    Returns:
        Session 字典；文件不存在时返回 None。
    """
    path = Path(session_file)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("session file %s is not a dict; ignoring", path)
            return None
        logger.info("session loaded from %s", path)
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("failed to load session file %s: %s", path, e)
        return None


def save_session(session_file: Path | str, settings: dict[str, Any]) -> None:
    """
    保存 Session 到文件。

    注意：日志只记录保存动作，不记录 Session 内容。
    """
    path = Path(session_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False)
        logger.info("session saved to %s", path)
    except OSError as e:
        logger.error("failed to save session file %s: %s", path, e)
        raise


def delete_session(session_file: Path | str) -> None:
    """删除 Session 文件（用于 clear-local-data）。"""
    path = Path(session_file)
    if path.exists():
        path.unlink()
        logger.info("session file deleted: %s", path)
