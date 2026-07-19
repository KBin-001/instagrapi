"""配置系统测试。

覆盖 app/config.py：
- build_settings
- validate_settings
- to_display_dict
- merge_configs
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import (
    DEFAULT_CONFIG_DIR,
    build_settings,
    merge_configs,
    to_display_dict,
    validate_settings,
)

# ---------- 默认配置加载 ----------


def test_default_config_loads_correctly() -> None:
    """默认配置加载：粉丝区间 20000-300000、请求间隔 4-8。"""
    settings = build_settings()
    assert settings.filters.min_followers == 20000
    assert settings.filters.max_followers == 300000
    assert settings.instagram.request_delay_min_seconds == 4
    assert settings.instagram.request_delay_max_seconds == 8


def test_default_config_has_output_formats() -> None:
    """默认输出格式。"""
    settings = build_settings()
    assert "csv" in settings.output.formats
    assert "json" in settings.output.formats
    assert "xlsx" in settings.output.formats


def test_default_config_has_discovery_limits() -> None:
    """默认 discovery 限制。"""
    settings = build_settings()
    assert settings.discovery.max_hashtags == 15
    assert settings.discovery.media_per_hashtag == 20
    assert settings.discovery.max_candidates == 300


def test_default_config_has_analysis_settings() -> None:
    """默认 analysis 设置。"""
    settings = build_settings()
    assert settings.analysis.recent_media_amount == 12


# ---------- YAML 用户配置覆盖 ----------


def test_yaml_user_config_overrides_default(tmp_path: Path) -> None:
    """YAML 用户配置覆盖默认（覆盖 min_followers）。"""
    user_yaml = tmp_path / "user.yaml"
    user_yaml.write_text(
        "filters:\n  min_followers: 50000\n  max_followers: 200000\n",
        encoding="utf-8",
    )
    settings = build_settings(user_yaml_path=user_yaml)
    assert settings.filters.min_followers == 50000
    assert settings.filters.max_followers == 200000


def test_yaml_user_config_partial_override(tmp_path: Path) -> None:
    """YAML 部分覆盖（其他字段保持默认）。"""
    user_yaml = tmp_path / "user.yaml"
    user_yaml.write_text("filters:\n  min_followers: 10000\n", encoding="utf-8")
    settings = build_settings(user_yaml_path=user_yaml)
    assert settings.filters.min_followers == 10000
    # 其他字段保持默认
    assert settings.filters.max_followers == 300000


def test_yaml_user_config_override_request_delay(tmp_path: Path) -> None:
    """YAML 覆盖请求间隔。"""
    user_yaml = tmp_path / "user.yaml"
    user_yaml.write_text(
        "instagram:\n  request_delay_min_seconds: 10\n  request_delay_max_seconds: 20\n",
        encoding="utf-8",
    )
    settings = build_settings(user_yaml_path=user_yaml)
    assert settings.instagram.request_delay_min_seconds == 10
    assert settings.instagram.request_delay_max_seconds == 20


# ---------- 环境变量覆盖 ----------


def test_env_credentials_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """环境变量覆盖 IG_USERNAME/IG_PASSWORD。"""
    monkeypatch.setenv("IG_USERNAME", "test_user")
    monkeypatch.setenv("IG_PASSWORD", "test_pass")
    settings = build_settings()
    assert settings.ig_username == "test_user"
    assert settings.ig_password == "test_pass"


def test_env_overrides_finder_hashtags(monkeypatch: pytest.MonkeyPatch) -> None:
    """FINDER_HASHTAGS 环境变量覆盖。"""
    monkeypatch.setenv("FINDER_HASHTAGS", "perfume,beauty,skincare")
    settings = build_settings()
    assert settings.hashtags == ["perfume", "beauty", "skincare"]


# ---------- 命令行参数覆盖 ----------


def test_cli_overrides_hashtags() -> None:
    """命令行参数覆盖（cli_overrides={"hashtags": ["foo"]}）。"""
    settings = build_settings(cli_overrides={"hashtags": ["foo", "bar"]})
    assert settings.hashtags == ["foo", "bar"]


def test_cli_overrides_filters() -> None:
    """命令行覆盖 filters。"""
    settings = build_settings(cli_overrides={"filters": {"min_followers": 30000, "max_followers": 250000}})
    assert settings.filters.min_followers == 30000
    assert settings.filters.max_followers == 250000


# ---------- 优先级验证 ----------


def test_priority_cli_over_yaml_over_default(tmp_path: Path) -> None:
    """优先级验证：命令行 > 用户 YAML > 默认。"""
    user_yaml = tmp_path / "user.yaml"
    user_yaml.write_text("filters:\n  min_followers: 50000\n", encoding="utf-8")
    settings = build_settings(
        user_yaml_path=user_yaml,
        cli_overrides={"filters": {"min_followers": 80000}},
    )
    assert settings.filters.min_followers == 80000


def test_priority_yaml_over_default(tmp_path: Path) -> None:
    """YAML 覆盖默认。"""
    user_yaml = tmp_path / "user.yaml"
    user_yaml.write_text("filters:\n  min_followers: 50000\n", encoding="utf-8")
    settings = build_settings(user_yaml_path=user_yaml)
    assert settings.filters.min_followers == 50000


# ---------- validate_settings ----------


def test_validate_settings_missing_username(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """validate_settings：缺 IG_USERNAME 返回错误。"""
    monkeypatch.delenv("IG_USERNAME", raising=False)
    monkeypatch.delenv("IG_PASSWORD", raising=False)
    # 切到临时目录避免读到真实 .env
    monkeypatch.chdir(tmp_path)
    settings = build_settings()
    errors = validate_settings(settings)
    assert any("IG_USERNAME" in e for e in errors)
    assert any("IG_PASSWORD" in e for e in errors)


def test_validate_settings_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """validate_settings：有凭据时无相关错误。"""
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "pass")
    settings = build_settings()
    errors = validate_settings(settings)
    assert not any("IG_USERNAME" in e for e in errors)
    assert not any("IG_PASSWORD" in e for e in errors)


def test_validate_settings_invalid_follower_range() -> None:
    """min_followers > max_followers 应报错（pydantic 已校验，但 validate_settings 也会检测）。"""
    settings = build_settings()
    # 手动构造错误状态
    settings.filters.min_followers = 500000
    settings.filters.max_followers = 100000
    errors = validate_settings(settings)
    assert any("min_followers" in e or "max_followers" in e for e in errors)


# ---------- to_display_dict ----------


def test_to_display_dict_masks_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """to_display_dict：密码字段为 ***，不泄露明文。"""
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "super_secret_password_123")
    settings = build_settings()
    display = to_display_dict(settings)
    assert display["ig_password"] == "***"
    # 明文不应出现
    assert "super_secret_password_123" not in str(display)


def test_to_display_dict_shows_username(monkeypatch: pytest.MonkeyPatch) -> None:
    """to_display_dict：用户名正常显示。"""
    monkeypatch.setenv("IG_USERNAME", "my_user")
    monkeypatch.setenv("IG_PASSWORD", "pass")
    settings = build_settings()
    display = to_display_dict(settings)
    assert display["ig_username"] == "my_user"


def test_to_display_dict_no_password_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """to_display_dict：无密码时为空字符串。"""
    monkeypatch.delenv("IG_USERNAME", raising=False)
    monkeypatch.delenv("IG_PASSWORD", raising=False)
    settings = build_settings()
    display = to_display_dict(settings)
    # 无密码时应为空字符串或 ***
    assert display["ig_password"] in ("", "***", None)


# ---------- merge_configs ----------


def test_merge_configs_deep_merge() -> None:
    """merge_configs 深度合并。"""
    default = {
        "filters": {"min_followers": 20000, "max_followers": 300000},
        "instagram": {"request_delay_min_seconds": 4},
    }
    user = {
        "filters": {"min_followers": 50000},
    }
    merged = merge_configs(default, user)
    assert merged["filters"]["min_followers"] == 50000
    # 未覆盖的保持默认
    assert merged["filters"]["max_followers"] == 300000
    assert merged["instagram"]["request_delay_min_seconds"] == 4


def test_merge_configs_priority_order() -> None:
    """merge_configs 优先级：cli > env > user > default。"""
    default = {"filters": {"min_followers": 20000}}
    user = {"filters": {"min_followers": 30000}}
    env = {"filters": {"min_followers": 40000}}
    cli = {"filters": {"min_followers": 50000}}
    merged = merge_configs(default, user, env, cli)
    assert merged["filters"]["min_followers"] == 50000


def test_merge_configs_none_overlays_ignored() -> None:
    """None 值的覆盖层被忽略。"""
    default = {"filters": {"min_followers": 20000}}
    user = {"filters": None}
    merged = merge_configs(default, user)
    # None 值不应覆盖
    assert merged["filters"]["min_followers"] == 20000


def test_merge_configs_empty_overlays() -> None:
    """空覆盖层不影响默认。"""
    default = {"filters": {"min_followers": 20000}}
    merged = merge_configs(default, None, None, None)
    assert merged["filters"]["min_followers"] == 20000


def test_merge_configs_non_dict_value_overrides() -> None:
    """非字典值直接覆盖。"""
    default = {"hashtags": ["a", "b"]}
    user = {"hashtags": ["c"]}
    merged = merge_configs(default, user)
    assert merged["hashtags"] == ["c"]


# ---------- config_dir 参数 ----------


def test_custom_config_dir(tmp_path: Path) -> None:
    """自定义 config_dir。"""
    # 复制默认配置到临时目录
    custom_dir = tmp_path / "config"
    custom_dir.mkdir()
    # 复制 default.yaml
    (custom_dir / "default.yaml").write_text(
        "filters:\n  min_followers: 10000\n  max_followers: 100000\n",
        encoding="utf-8",
    )
    settings = build_settings(config_dir=custom_dir)
    assert settings.filters.min_followers == 10000
    assert settings.filters.max_followers == 100000


def test_default_config_dir_constant() -> None:
    """DEFAULT_CONFIG_DIR 常量存在且为 Path。"""
    assert isinstance(DEFAULT_CONFIG_DIR, Path)
    assert DEFAULT_CONFIG_DIR.exists()
