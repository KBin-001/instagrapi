"""用户名标准化、URL 解析与去重测试。

覆盖 app/discovery/deduplication.py：
- normalize_username
- parse_username_list
- deduplicate_candidates
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.discovery.deduplication import (
    deduplicate_candidates,
    normalize_username,
    parse_username_list,
)
from app.models import CandidateAccount

# ---------- normalize_username ----------


def test_normalize_strips_at_prefix() -> None:
    """去除 @ 前缀。"""
    assert normalize_username("@UserName") == "username"


def test_normalize_strips_at_multiple() -> None:
    """去除多个 @ 前缀。"""
    assert normalize_username("@@user") == "user"


def test_normalize_from_instagram_url() -> None:
    """从 Instagram URL 提取 username。"""
    assert normalize_username("https://www.instagram.com/username/") == "username"


def test_normalize_lowercases() -> None:
    """转小写。"""
    assert normalize_username("UserName") == "username"


def test_normalize_strips_trailing_slash() -> None:
    """去除末尾 /。"""
    assert normalize_username("username/") == "username"


def test_normalize_empty_string_returns_none() -> None:
    """忽略空行。"""
    assert normalize_username("") is None


def test_normalize_whitespace_only_returns_none() -> None:
    """纯空白返回 None。"""
    assert normalize_username("   ") is None


def test_normalize_none_returns_none() -> None:
    """None 输入返回 None。"""
    assert normalize_username(None) is None  # type: ignore[arg-type]


def test_normalize_comment_line_returns_none() -> None:
    """忽略 # 开头的注释。"""
    assert normalize_username("# this is a comment") is None


def test_normalize_comment_with_at_returns_none() -> None:
    """以 # 开头即使含 @ 也视为注释。"""
    assert normalize_username("# @username") is None


def test_normalize_reserved_word_accounts() -> None:
    """保留字 accounts → None。"""
    assert normalize_username("accounts") is None


def test_normalize_reserved_word_explore() -> None:
    assert normalize_username("explore") is None


def test_normalize_reserved_word_tags() -> None:
    assert normalize_username("tags") is None


def test_normalize_reserved_word_locations() -> None:
    assert normalize_username("locations") is None


def test_normalize_reserved_word_reel() -> None:
    assert normalize_username("reel") is None


def test_normalize_reserved_word_reels() -> None:
    assert normalize_username("reels") is None


def test_normalize_reserved_word_stories() -> None:
    assert normalize_username("stories") is None


def test_normalize_reserved_word_p() -> None:
    assert normalize_username("p") is None


def test_normalize_illegal_character_dash() -> None:
    """含 - 等非法字符 → None。"""
    assert normalize_username("user-name") is None


def test_normalize_illegal_character_space() -> None:
    """含空格 → None。"""
    assert normalize_username("user name") is None


def test_normalize_full_url_with_query() -> None:
    """完整 URL 含查询参数。"""
    assert normalize_username("https://instagram.com/foo/?bar=1") == "foo"


def test_normalize_full_url_no_www() -> None:
    assert normalize_username("https://instagram.com/foo/") == "foo"


def test_normalize_http_url() -> None:
    assert normalize_username("http://instagram.com/foo") == "foo"


def test_normalize_url_uppercase() -> None:
    """URL 大写也匹配。"""
    assert normalize_username("HTTPS://WWW.INSTAGRAM.COM/Foo/") == "foo"


def test_normalize_username_with_dots() -> None:
    """合法字符 . 应保留。"""
    assert normalize_username("user.name") == "user.name"


def test_normalize_username_with_underscores() -> None:
    """合法字符 _ 应保留。"""
    assert normalize_username("user_name") == "user_name"


def test_normalize_username_with_numbers() -> None:
    """合法字符数字应保留。"""
    assert normalize_username("user123") == "user123"


def test_normalize_at_then_url() -> None:
    """先 @ 后 URL 也应正确解析。"""
    assert normalize_username("@https://instagram.com/foo/") == "foo"


# ---------- parse_username_list ----------


def test_parse_username_list_deduplication() -> None:
    """去重。"""
    valid, invalid = parse_username_list(["alice", "Alice", "@ALICE", "bob", "bob"])
    assert valid == ["alice", "bob"]
    assert invalid == []


def test_parse_username_list_filters_invalid() -> None:
    """过滤无效项。"""
    valid, invalid = parse_username_list(["alice", "", "# comment", "user-name", "bob"])
    assert valid == ["alice", "bob"]
    # 空串与注释不计入 invalid；非法字符计入
    assert "user-name" in invalid


def test_parse_username_list_urls() -> None:
    """支持 URL 形式。"""
    valid, _ = parse_username_list(
        [
            "https://www.instagram.com/alice/",
            "https://instagram.com/bob",
            "@charlie",
        ]
    )
    assert valid == ["alice", "bob", "charlie"]


def test_parse_username_list_empty_input() -> None:
    valid, invalid = parse_username_list([])
    assert valid == []
    assert invalid == []


def test_parse_username_list_reserved_words_filtered() -> None:
    """保留字被过滤且不计入 invalid。"""
    valid, invalid = parse_username_list(["accounts", "explore", "alice"])
    assert valid == ["alice"]
    # 保留字 normalize 返回 None 但不是非法字符，不计入 invalid
    assert "accounts" not in invalid


# ---------- deduplicate_candidates ----------


def _make_candidate(name: str, hashtags: list[str] | None = None) -> CandidateAccount:
    return CandidateAccount(
        username=name,
        source_hashtags=hashtags or [],
        discovered_at=datetime.now(UTC),
        normalized=False,
    )


def test_deduplicate_candidates_merges_hashtags() -> None:
    """重复账号合并 source_hashtags。"""
    candidates = [
        _make_candidate("alice", ["perfume"]),
        _make_candidate("@Alice", ["beauty"]),
        _make_candidate("bob", ["fashion"]),
    ]
    result = deduplicate_candidates(candidates)
    assert len(result) == 2
    by_user = {c.username: c for c in result}
    assert "alice" in by_user
    assert "bob" in by_user
    assert set(by_user["alice"].source_hashtags) == {"perfume", "beauty"}


def test_deduplicate_candidates_normalizes_urls() -> None:
    """URL 形式 username 也正确去重。"""
    candidates = [
        _make_candidate("https://www.instagram.com/alice/", ["a"]),
        _make_candidate("alice", ["b"]),
    ]
    result = deduplicate_candidates(candidates)
    assert len(result) == 1
    assert result[0].username == "alice"
    assert set(result[0].source_hashtags) == {"a", "b"}


def test_deduplicate_candidates_marks_normalized() -> None:
    """去重后 normalized=True。"""
    candidates = [_make_candidate("alice", ["a"])]
    result = deduplicate_candidates(candidates)
    assert result[0].normalized is True


def test_deduplicate_candidates_empty_input() -> None:
    assert deduplicate_candidates([]) == []


def test_deduplicate_candidates_filters_invalid() -> None:
    """无效 username 被过滤。"""
    candidates = [
        _make_candidate("alice", ["a"]),
        _make_candidate("user-name", ["b"]),  # 非法字符
        _make_candidate("accounts", ["c"]),  # 保留字
    ]
    result = deduplicate_candidates(candidates)
    assert len(result) == 1
    assert result[0].username == "alice"
