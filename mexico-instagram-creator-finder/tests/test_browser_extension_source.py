import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


def test_manifest_uses_current_tab_without_sensitive_permissions() -> None:
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))

    permissions = set(manifest["permissions"])
    assert {"activeTab", "scripting", "storage", "sidePanel", "tabs"}.issubset(permissions)
    assert permissions.isdisjoint({"cookies", "webRequest", "webRequestBlocking", "proxy"})


def test_batch_loop_is_sequential_bounded_and_has_safety_stop() -> None:
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")

    assert "chrome.tabs.update" in background
    assert "chrome.tabs.create" not in background
    assert "state.delayMin + Math.random()" in background
    assert "Challenge" in content
    assert "登录状态失效" in content
    assert "限流或安全警告" in content
    assert "result.ok !== true || !result.payload" in background
    assert "payload_validation" in background
    assert "profile_empty_state" in content
    assert "/private|私密|privada/i.test(text(document.body))" not in content


def test_dom_collector_keeps_missing_counts_as_null() -> None:
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")

    assert "return null" in content
    assert "visible_play_count: parse" in content
    assert ".slice(0, 12)" in content
    assert 'keyword: "a[href*=' in content
    assert 'url.hostname === "l.instagram.com"' in content
    assert 'url.searchParams.get("u")' in content


def test_media_author_uses_multiple_public_page_signals_and_reports_diagnostics() -> None:
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")

    assert "function metaAuthor()" in content
    assert "function domAuthor()" in content
    assert "function embeddedAuthor(shortcode)" in content
    assert 'errorCode: "media_author_unresolved"' in content
    assert "mediaDiagnostics()" in content
    assert "retryable: false" in content
    assert "result?.diagnostics" in background


def test_sidepanel_supports_human_review_and_library_save() -> None:
    html = (EXTENSION / "sidepanel.html").read_text(encoding="utf-8")
    script = (EXTENSION / "sidepanel.js").read_text(encoding="utf-8")

    assert "加入达人库" in html
    assert "跳过" in html
    assert "/review/next" in script
    assert "/${action}" in script
