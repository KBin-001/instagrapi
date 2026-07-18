"""排除名单解析（TXT/CSV/XLSX/Instagram URL/已导出结果）。

支持格式：
- TXT：每行一个 username 或 Instagram URL，# 开头为注释
- CSV：包含 username 列的 CSV
- XLSX：包含 username 列的 Excel
- 之前导出的结果文件：自动识别 username 列
- 直接传入的 username 或 URL 字符串列表
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from app.discovery.deduplication import normalize_username, parse_username_list
from app.logging_config import get_logger
from app.models import CandidateAccount

logger = get_logger("discovery.seeds")


class ExclusionEntry:
    """单个排除条目。"""

    def __init__(self, username: str, source: str, reason: str):
        self.username = username
        self.source = source
        self.reason = reason

    def to_dict(self) -> dict[str, str]:
        return {
            "username": self.username,
            "exclusion_source": self.source,
            "exclusion_reason": self.reason,
        }


def parse_exclude_file(path: str | Path) -> list[ExclusionEntry]:
    """
    解析单个排除名单文件（支持 .txt/.csv/.xlsx）。
    """
    p = Path(path)
    if not p.exists():
        logger.warning("exclude file not found: %s", p)
        return []
    suffix = p.suffix.lower()
    if suffix == ".txt":
        return _parse_txt(p)
    if suffix == ".csv":
        return _parse_csv(p)
    if suffix == ".xlsx":
        return _parse_xlsx(p)
    logger.warning("unsupported exclude file type: %s", p)
    return []


def _parse_txt(path: Path) -> list[ExclusionEntry]:
    entries: list[ExclusionEntry] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                norm = normalize_username(line)
                if norm:
                    entries.append(ExclusionEntry(norm, str(path), f"txt line {line_no}"))
    except OSError as e:
        logger.error("failed to read txt %s: %s", path, e)
    return entries


def _parse_csv(path: Path) -> list[ExclusionEntry]:
    entries: list[ExclusionEntry] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return entries
            # 寻找 username 列
            username_col = _find_username_column(reader.fieldnames)
            if username_col is None:
                logger.warning("csv %s has no username column; fields=%s", path, reader.fieldnames)
                return entries
            for row_no, row in enumerate(reader, start=2):
                raw = row.get(username_col, "")
                norm = normalize_username(raw)
                if norm:
                    entries.append(ExclusionEntry(norm, str(path), f"csv column={username_col} row={row_no}"))
    except OSError as e:
        logger.error("failed to read csv %s: %s", path, e)
    return entries


def _parse_xlsx(path: Path) -> list[ExclusionEntry]:
    entries: list[ExclusionEntry] = []
    try:
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return entries
        header = list(rows[0])
        username_col_idx = _find_username_column_index(header)
        if username_col_idx is None:
            logger.warning("xlsx %s has no username column; header=%s", path, header)
            return entries
        for row_no, row in enumerate(rows[1:], start=2):
            if username_col_idx >= len(row):
                continue
            raw = row[username_col_idx]
            if raw is None:
                continue
            norm = normalize_username(str(raw))
            if norm:
                entries.append(ExclusionEntry(norm, str(path), f"xlsx column={username_col_idx + 1} row={row_no}"))
        wb.close()
    except Exception as e:
        logger.error("failed to read xlsx %s: %s", path, e)
    return entries


def _find_username_column(fieldnames: list[str]) -> str | None:
    """在 CSV/XLSX 表头中查找 username 列。"""
    candidates = ["username", "user", "usuario", "ig_username", "instagram_username", "user_name", "cuenta"]
    lower_fields = [(f, f.lower()) for f in fieldnames]
    for c in candidates:
        for orig, low in lower_fields:
            if low == c:
                return orig
    # 模糊匹配
    for orig, low in lower_fields:
        if "user" in low or "cuenta" in low:
            return orig
    return None


def _find_username_column_index(header: list[Any]) -> int | None:
    """XLSX 用，返回列索引。"""
    fieldnames = [str(h) if h is not None else "" for h in header]
    col_name = _find_username_column(fieldnames)
    if col_name is None:
        return None
    return fieldnames.index(col_name)


def parse_exclude_paths(paths: list[str | Path]) -> list[ExclusionEntry]:
    """
    批量解析排除名单文件路径列表。
    """
    all_entries: list[ExclusionEntry] = []
    seen: set[str] = set()
    for p in paths:
        entries = parse_exclude_file(p)
        for e in entries:
            if e.username not in seen:
                seen.add(e.username)
                all_entries.append(e)
    return all_entries


def parse_exclude_strings(items: list[str]) -> list[ExclusionEntry]:
    """
    解析直接传入的字符串列表（username 或 Instagram URL）。
    """
    valid, _ = parse_username_list(items)
    return [ExclusionEntry(u, "cli_argument", "passed via --exclude") for u in valid]


def apply_exclusion(
    candidates: list[CandidateAccount],
    exclusions: list[ExclusionEntry],
) -> tuple[list[CandidateAccount], list[CandidateAccount]]:
    """
    将排除名单应用到候选账号列表。

    Returns:
        (kept, excluded) — 保留的候选 + 被排除的候选（带 exclusion 信息）。
    """
    excluded_set = {e.username for e in exclusions}

    kept: list[CandidateAccount] = []
    excluded: list[CandidateAccount] = []
    for c in candidates:
        uname = c.username.lower() if c.normalized else (normalize_username(c.username) or c.username.lower())
        if uname in excluded_set:
            excluded_c = CandidateAccount(
                username=uname,
                source_hashtags=c.source_hashtags,
                discovered_at=c.discovered_at,
                normalized=True,
            )
            excluded.append(excluded_c)
            # CandidateAccount 模型本身不包含 exclusion 字段，
            # 上层存储时通过 CreatorRecord.excluded/exclusion_source/exclusion_reason 处理
        else:
            kept.append(c)
    return kept, excluded
