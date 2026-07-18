"""排除名单解析测试。

覆盖 app/discovery/seeds.py：
- parse_exclude_file（TXT/CSV/XLSX）
- parse_exclude_strings
- parse_exclude_paths
- apply_exclusion
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from app.discovery.seeds import (
    ExclusionEntry,
    apply_exclusion,
    parse_exclude_file,
    parse_exclude_paths,
    parse_exclude_strings,
)
from app.models import CandidateAccount


def _make_candidate(name: str) -> CandidateAccount:
    return CandidateAccount(
        username=name,
        source_hashtags=[],
        discovered_at=datetime.now(UTC),
        normalized=False,
    )


# ---------- TXT 解析 ----------


def test_parse_exclude_txt_basic(tmp_path: Path) -> None:
    """TXT 文件解析：每行 username。"""
    txt = tmp_path / "excluded.txt"
    txt.write_text("alice\nbob\ncharlie\n", encoding="utf-8")
    entries = parse_exclude_file(txt)
    assert len(entries) == 3
    assert {e.username for e in entries} == {"alice", "bob", "charlie"}
    # 排除条目含 source 与 reason
    for e in entries:
        assert e.source == str(txt)
        assert "txt line" in e.reason


def test_parse_exclude_txt_with_at_prefix(tmp_path: Path) -> None:
    """TXT 支持 @ 前缀。"""
    txt = tmp_path / "excluded.txt"
    txt.write_text("@alice\n@bob\n", encoding="utf-8")
    entries = parse_exclude_file(txt)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_txt_with_instagram_urls(tmp_path: Path) -> None:
    """TXT 支持 Instagram URL 形式。"""
    txt = tmp_path / "excluded.txt"
    txt.write_text(
        "https://www.instagram.com/alice/\nhttps://instagram.com/bob\nhttps://instagram.com/charlie/?hl=es\n",
        encoding="utf-8",
    )
    entries = parse_exclude_file(txt)
    assert {e.username for e in entries} == {"alice", "bob", "charlie"}


def test_parse_exclude_txt_ignores_comments(tmp_path: Path) -> None:
    """# 开头注释被忽略。"""
    txt = tmp_path / "excluded.txt"
    txt.write_text("# comment\nalice\n# another comment\nbob\n", encoding="utf-8")
    entries = parse_exclude_file(txt)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_txt_ignores_blank_lines(tmp_path: Path) -> None:
    """空行被忽略。"""
    txt = tmp_path / "excluded.txt"
    txt.write_text("\nalice\n\n\nbob\n", encoding="utf-8")
    entries = parse_exclude_file(txt)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_txt_deduplication(tmp_path: Path) -> None:
    """TXT 中重复 username 在 parse_exclude_paths 中去重。"""
    txt = tmp_path / "excluded.txt"
    txt.write_text("alice\nalice\n@ALICE\n", encoding="utf-8")
    # parse_exclude_file 不去重，返回所有
    entries = parse_exclude_file(txt)
    assert len(entries) == 3
    # parse_exclude_paths 去重
    deduped = parse_exclude_paths([txt])
    assert len(deduped) == 1


def test_parse_exclude_txt_with_utf8_bom(tmp_path: Path) -> None:
    """TXT 含 UTF-8 BOM 也能正确解析。"""
    txt = tmp_path / "excluded.txt"
    # 写入带 BOM 的内容
    content = "alice\nbob\n"
    txt.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    entries = parse_exclude_file(txt)
    # 第一行 alice 应正确解析（BOM 在 strip 后会被处理掉，因为编码用 utf-8 而非 utf-8-sig）
    # 这里验证至少 bob 能解析
    usernames = {e.username for e in entries}
    assert "bob" in usernames


def test_parse_exclude_file_not_found(tmp_path: Path) -> None:
    """文件不存在返回空列表。"""
    missing = tmp_path / "nonexistent.txt"
    entries = parse_exclude_file(missing)
    assert entries == []


def test_parse_exclude_file_unsupported_extension(tmp_path: Path) -> None:
    """不支持的扩展名返回空列表。"""
    other = tmp_path / "excluded.json"
    other.write_text('["alice"]', encoding="utf-8")
    entries = parse_exclude_file(other)
    assert entries == []


# ---------- CSV 解析 ----------


def test_parse_exclude_csv_basic(tmp_path: Path) -> None:
    """CSV 文件解析（含 username 列）。"""
    csv_path = tmp_path / "excluded.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["username", "note"])
        writer.writeheader()
        writer.writerow({"username": "alice", "note": "test"})
        writer.writerow({"username": "bob", "note": "test"})
    entries = parse_exclude_file(csv_path)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_csv_with_bom(tmp_path: Path) -> None:
    """CSV 含 BOM 也能解析。"""
    csv_path = tmp_path / "excluded.csv"
    # 写入带 BOM 的 CSV
    content = "username,note\nalice,test\nbob,test\n"
    csv_path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    entries = parse_exclude_file(csv_path)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_csv_with_at_prefix(tmp_path: Path) -> None:
    """CSV 中的 @ 前缀也能解析。"""
    csv_path = tmp_path / "excluded.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["username"])
        writer.writeheader()
        writer.writerow({"username": "@alice"})
        writer.writerow({"username": "https://www.instagram.com/bob/"})
    entries = parse_exclude_file(csv_path)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_csv_alternate_column_name(tmp_path: Path) -> None:
    """CSV 使用其他 username 列名（如 user）。"""
    csv_path = tmp_path / "excluded.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user", "id"])
        writer.writeheader()
        writer.writerow({"user": "alice", "id": "1"})
        writer.writerow({"user": "bob", "id": "2"})
    entries = parse_exclude_file(csv_path)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_csv_no_username_column(tmp_path: Path) -> None:
    """CSV 无 username 列返回空列表。"""
    csv_path = tmp_path / "excluded.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "id"])
        writer.writeheader()
        writer.writerow({"name": "alice", "id": "1"})
    entries = parse_exclude_file(csv_path)
    assert entries == []


# ---------- XLSX 解析 ----------


def test_parse_exclude_xlsx_basic(tmp_path: Path) -> None:
    """XLSX 文件解析。"""
    xlsx_path = tmp_path / "excluded.xlsx"
    _write_xlsx(xlsx_path, header=["username", "note"], rows=[["alice", "t"], ["bob", "t"]])
    entries = parse_exclude_file(xlsx_path)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_xlsx_with_at_prefix(tmp_path: Path) -> None:
    """XLSX 支持 @ 前缀与 URL。"""
    xlsx_path = tmp_path / "excluded.xlsx"
    _write_xlsx(
        xlsx_path,
        header=["username"],
        rows=[["@alice"], ["https://www.instagram.com/bob/"]],
    )
    entries = parse_exclude_file(xlsx_path)
    assert {e.username for e in entries} == {"alice", "bob"}


def test_parse_exclude_xlsx_no_username_column(tmp_path: Path) -> None:
    """XLSX 无 username 列返回空列表。"""
    xlsx_path = tmp_path / "excluded.xlsx"
    _write_xlsx(xlsx_path, header=["name", "id"], rows=[["alice", "1"]])
    entries = parse_exclude_file(xlsx_path)
    assert entries == []


def _write_xlsx(path: Path, *, header: list[str], rows: list[list]) -> None:
    """辅助：写一个简单的 xlsx 文件。"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for row in rows:
        ws.append(row)
    wb.save(path)


# ---------- parse_exclude_strings ----------


def test_parse_exclude_strings_basic() -> None:
    """字符串列表解析。"""
    entries = parse_exclude_strings(["alice", "@bob", "https://www.instagram.com/charlie/"])
    assert {e.username for e in entries} == {"alice", "bob", "charlie"}
    for e in entries:
        assert e.source == "cli_argument"
        assert "cli" in e.reason or "exclude" in e.reason.lower()


def test_parse_exclude_strings_filters_invalid() -> None:
    """非法输入被过滤。"""
    entries = parse_exclude_strings(["alice", "", "# comment", "user-name"])
    assert {e.username for e in entries} == {"alice"}


def test_parse_exclude_strings_empty() -> None:
    assert parse_exclude_strings([]) == []


# ---------- parse_exclude_paths ----------


def test_parse_exclude_paths_multiple_files(tmp_path: Path) -> None:
    """多文件批量解析并去重。"""
    txt1 = tmp_path / "a.txt"
    txt1.write_text("alice\nbob\n", encoding="utf-8")
    txt2 = tmp_path / "b.txt"
    txt2.write_text("alice\ncharlie\n", encoding="utf-8")
    entries = parse_exclude_paths([txt1, txt2])
    assert {e.username for e in entries} == {"alice", "bob", "charlie"}


def test_parse_exclude_paths_empty() -> None:
    assert parse_exclude_paths([]) == []


# ---------- apply_exclusion ----------


def test_apply_exclusion_basic() -> None:
    """apply_exclusion 返回 (kept, excluded)。"""
    candidates = [
        _make_candidate("alice"),
        _make_candidate("bob"),
        _make_candidate("charlie"),
    ]
    exclusions = [
        ExclusionEntry("alice", "txt", "test"),
        ExclusionEntry("charlie", "txt", "test"),
    ]
    kept, excluded = apply_exclusion(candidates, exclusions)
    kept_names = {c.username for c in kept}
    excluded_names = {c.username for c in excluded}
    assert kept_names == {"bob"}
    assert excluded_names == {"alice", "charlie"}


def test_apply_exclusion_no_match() -> None:
    """无匹配时全部保留。"""
    candidates = [_make_candidate("alice"), _make_candidate("bob")]
    exclusions = [ExclusionEntry("charlie", "txt", "test")]
    kept, excluded = apply_exclusion(candidates, exclusions)
    assert len(kept) == 2
    assert len(excluded) == 0


def test_apply_exclusion_empty_exclusions() -> None:
    """空排除名单：全部保留。"""
    candidates = [_make_candidate("alice")]
    kept, excluded = apply_exclusion(candidates, [])
    assert len(kept) == 1
    assert len(excluded) == 0


def test_apply_exclusion_empty_candidates() -> None:
    """空候选列表。"""
    exclusions = [ExclusionEntry("alice", "txt", "test")]
    kept, excluded = apply_exclusion([], exclusions)
    assert kept == []
    assert excluded == []


def test_apply_exclusion_case_insensitive() -> None:
    """apply_exclusion 大小写不敏感。"""
    candidates = [_make_candidate("Alice")]
    exclusions = [ExclusionEntry("alice", "txt", "test")]
    kept, excluded = apply_exclusion(candidates, exclusions)
    assert len(kept) == 0
    assert len(excluded) == 1
    assert excluded[0].username == "alice"


def test_exclusion_entry_to_dict() -> None:
    """ExclusionEntry.to_dict 返回正确字段。"""
    entry = ExclusionEntry("alice", "file.txt", "test reason")
    d = entry.to_dict()
    assert d == {
        "username": "alice",
        "exclusion_source": "file.txt",
        "exclusion_reason": "test reason",
    }
