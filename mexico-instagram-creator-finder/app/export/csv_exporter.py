"""CSV 导出（UTF-8 BOM）。

使用 utf-8-sig 编码写入 BOM，确保 Excel 打开时中文与西班牙语重音字符不乱码。
CSV 表头使用「中文 (english)」双语格式，便于人工阅读与程序处理。
不导出密码、Cookie 或 Session。
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.export.common import EXPORT_FIELDS, get_header_labels, records_to_rows
from app.logging_config import get_logger
from app.models import CreatorRecord

logger = get_logger("export.csv")


def export_csv(records: list[CreatorRecord], output_path: str | Path) -> Path:
    """
    导出为 CSV（UTF-8 BOM，确保 Excel 中文与西语重音不乱码）。

    表头使用「中文 (english)」双语格式，例如「用户名 (username)」。
    数据行仍按 EXPORT_FIELDS 顺序写入。

    Args:
        records: 已排序的 CreatorRecord 列表
        output_path: 输出文件路径

    Returns:
        实际写入的文件路径。
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows, _fieldnames = records_to_rows(records)
    # 双语表头
    header_labels = get_header_labels(EXPORT_FIELDS)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        # 写入双语表头
        writer = csv.writer(f)
        writer.writerow(header_labels)
        # 数据行按 EXPORT_FIELDS 顺序取值
        for row in rows:
            writer.writerow([row.get(field, "") for field in EXPORT_FIELDS])

    logger.info("csv exported: %s (%d rows)", path, len(rows))
    return path
