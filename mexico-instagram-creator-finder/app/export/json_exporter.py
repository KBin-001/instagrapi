"""JSON 导出（UTF-8，ensure_ascii=False）。

保留 Unicode 字符，中文与西班牙语重音原样输出。
不导出密码、Cookie 或 Session。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.export.common import records_to_dicts
from app.logging_config import get_logger
from app.models import CreatorRecord

logger = get_logger("export.json")


def export_json(records: list[CreatorRecord], output_path: str | Path) -> Path:
    """
    导出为 JSON（UTF-8，preserve unicode）。

    Args:
        records: 已排序的 CreatorRecord 列表
        output_path: 输出文件路径

    Returns:
        实际写入的文件路径。
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = records_to_dicts(records)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    logger.info("json exported: %s (%d records)", path, len(data))
    return path
