"""导出子包。

负责将筛选结果导出为 CSV、JSON、XLSX 三种格式。
- CSV 使用 UTF-8 BOM，确保 Excel 打开中文与西班牙语重音字符不乱码
- 默认排序：total_score 降序 → median_visible_reel_views 降序 → followers 降序
- 不导出密码、Cookie 或 Session
"""

from __future__ import annotations

from pathlib import Path

from app.logging_config import get_logger
from app.models import CreatorRecord

logger = get_logger("export")


def export_records(
    records: list[CreatorRecord],
    output_dir: str | Path,
    formats: list[str] | None = None,
    task_id: str | None = None,
) -> dict[str, Path]:
    """
    按指定格式导出记录到 output_dir。

    Args:
        records: 已分析的 CreatorRecord 列表（会按默认排序输出）
        output_dir: 输出目录
        formats: 格式列表（csv/json/xlsx）；None 则全部三种
        task_id: 可选任务 ID，用于文件名后缀

    Returns:
        格式 -> 实际文件路径 的映射。
    """
    from app.export.common import sort_records
    from app.export.csv_exporter import export_csv
    from app.export.excel_exporter import export_xlsx
    from app.export.json_exporter import export_json

    if formats is None:
        formats = ["csv", "json", "xlsx"]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sorted_records = sort_records(records)
    suffix = f"_{task_id}" if task_id else ""
    results: dict[str, Path] = {}

    if "csv" in formats:
        results["csv"] = export_csv(sorted_records, out_dir / f"creators{suffix}.csv")
    if "json" in formats:
        results["json"] = export_json(sorted_records, out_dir / f"creators{suffix}.json")
    if "xlsx" in formats:
        results["xlsx"] = export_xlsx(sorted_records, out_dir / f"creators{suffix}.xlsx")

    logger.info("export complete: formats=%s, output_dir=%s", list(results.keys()), out_dir)
    return results
