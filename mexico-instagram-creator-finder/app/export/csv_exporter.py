"""CSV 导出（UTF-8 BOM）。

使用 utf-8-sig 编码写入 BOM，确保 Excel 打开时中文与西班牙语重音字符不乱码。
不导出密码、Cookie 或 Session。
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.export.common import records_to_rows
from app.logging_config import get_logger
from app.models import CreatorRecord

logger = get_logger("export.csv")


def export_csv(records: list[CreatorRecord], output_path: str | Path) -> Path:
    """
    导出为 CSV（UTF-8 BOM，确保 Excel 中文与西语重音不乱码）。

    Args:
        records: 已排序的 CreatorRecord 列表
        output_path: 输出文件路径

    Returns:
        实际写入的文件路径。
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows, fieldnames = records_to_rows(records)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    logger.info("csv exported: %s (%d rows)", path, len(rows))
    return path
