"""Mexico Instagram Creator Finder 配置系统。

优先级：命令行参数 > 环境变量 > 用户 YAML > 默认配置。
密码仅从环境变量读取（IG_USERNAME/IG_PASSWORD），不写入 YAML/数据库/日志。

打包后路径解析（PyInstaller 目录模式）：
- 优先从可执行文件同级目录的 config/ 读取（用户可修改）
- 若不存在，回退到 _MEIPASS 内置 config/（spec 中 datas 打包的副本）
- 开发环境则用项目根目录的 config/
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _resolve_project_root() -> Path:
    """解析项目根目录（兼容开发环境与 PyInstaller 打包环境）。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包后
        # sys.executable 是 dist/MexicoCreatorFinder/MexicoCreatorFinder.exe
        return Path(sys.executable).resolve().parent
    # 开发环境：app/config.py 的上两级
    return Path(__file__).resolve().parent.parent


def _resolve_config_dir() -> Path:
    """解析 config/ 目录路径。

    打包模式下优先用 exe 同级目录的 config/（用户可修改覆盖）；
    若不存在则回退到 _MEIPASS 内置的 config/。
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        user_config = exe_dir / "config"
        if user_config.exists():
            return user_config
        # 回退到 PyInstaller 内置资源
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "config"
    return _resolve_project_root() / "config"


PROJECT_ROOT = _resolve_project_root()
DEFAULT_CONFIG_DIR = _resolve_config_dir()


def resolve_path(relative: str | Path) -> Path:
    """将相对路径解析为基于 PROJECT_ROOT 的绝对路径。

    GUI、CLI、pytest 和打包环境的工作目录可能不同，
    所有文件路径（session_file、database_file、output 等）都应通过此函数解析。
    已是绝对路径时直接返回。
    """
    p = Path(relative)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


class InstagramSettings(BaseModel):
    session_file: str = "data/instagram_session.json"
    request_delay_min_seconds: int = 4
    request_delay_max_seconds: int = 8
    retry_network_errors: int = 2
    stop_on_rate_limit: bool = True
    stop_on_challenge: bool = True

    @field_validator("request_delay_min_seconds", "request_delay_max_seconds")
    @classmethod
    def validate_delay_range(cls, v: int) -> int:
        if v < 0:
            raise ValueError("delay must be non-negative")
        return v

    @field_validator("retry_network_errors")
    @classmethod
    def validate_retry(cls, v: int) -> int:
        if v < 0 or v > 5:
            raise ValueError("retry_network_errors must be in [0, 5]")
        return v


class DiscoverySettings(BaseModel):
    max_hashtags: int = 15
    media_per_hashtag: int = 20
    max_candidates: int = 300
    max_profiles_to_analyze: int = 100
    seed_expansion_depth: int = 1
    max_accounts_per_seed: int = 20


class FilterSettings(BaseModel):
    min_followers: int = 20000
    max_followers: int = 300000
    require_public_account: bool = True
    require_mexico_signal: bool = True
    maximum_days_since_last_post: int = 90
    minimum_recent_media_count: int = 3
    minimum_median_reel_views: int = 2000
    exclude_brands: bool = True
    exclude_media_accounts: bool = True

    @field_validator("max_followers")
    @classmethod
    def validate_followers_range(cls, v: int, info) -> int:
        min_v = info.data.get("min_followers", 20000)
        if v < min_v:
            raise ValueError("max_followers must be >= min_followers")
        return v


class AnalysisSettings(BaseModel):
    recent_media_amount: int = 12
    maximum_caption_length: int = 3000


class CheckpointSettings(BaseModel):
    enabled: bool = True
    database_file: str = "data/app.db"


class OutputSettings(BaseModel):
    directory: str = "output"
    formats: list[str] = Field(default_factory=lambda: ["csv", "json", "xlsx"])


def _resolve_env_file() -> str:
    """解析 .env 文件路径（打包后从 exe 同级目录读取）。"""
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parent / ".env")
    return ".env"


class Settings(BaseSettings):
    """项目主配置。

    凭据从环境变量读取（IG_USERNAME/IG_PASSWORD），不进入 YAML。
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    instagram: InstagramSettings = Field(default_factory=InstagramSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    filters: FilterSettings = Field(default_factory=FilterSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    checkpoint: CheckpointSettings = Field(default_factory=CheckpointSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)

    # 环境变量凭据（不写入 YAML/数据库/日志）
    ig_username: str | None = Field(default=None, validation_alias="IG_USERNAME")
    ig_password: str | None = Field(default=None, validation_alias="IG_PASSWORD")

    # 运行时参数（命令行传入）
    hashtags: list[str] | None = None  # None 表示用 config/hashtags.yaml 默认
    exclude_files: list[str] | None = None
    resume: bool = False
    reset_task: bool = False

    # 配置目录（用于加载 YAML）
    config_dir: Path = Field(default_factory=lambda: DEFAULT_CONFIG_DIR)


def load_yaml(path: Path) -> dict[str, Any]:
    """加载 YAML 文件，返回字典。"""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_default_config(config_dir: Path | None = None) -> dict[str, Any]:
    """加载默认 YAML 配置（config/default.yaml）。"""
    cfg_dir = config_dir or DEFAULT_CONFIG_DIR
    return load_yaml(cfg_dir / "default.yaml")


def load_hashtags(config_dir: Path | None = None) -> list[str]:
    """加载默认 Hashtag 列表。"""
    cfg_dir = config_dir or DEFAULT_CONFIG_DIR
    data = load_yaml(cfg_dir / "hashtags.yaml")
    return list(data.get("hashtags", []))


def load_mexico_locations(config_dir: Path | None = None) -> dict[str, Any]:
    """加载墨西哥地区数据。"""
    cfg_dir = config_dir or DEFAULT_CONFIG_DIR
    return load_yaml(cfg_dir / "mexico_locations.yaml")


def load_niche_keywords(config_dir: Path | None = None) -> dict[str, Any]:
    """加载垂类关键词。"""
    cfg_dir = config_dir or DEFAULT_CONFIG_DIR
    return load_yaml(cfg_dir / "niche_keywords.yaml")


def load_excluded_terms(config_dir: Path | None = None) -> dict[str, Any]:
    """加载排除账号关键词。"""
    cfg_dir = config_dir or DEFAULT_CONFIG_DIR
    return load_yaml(cfg_dir / "excluded_account_terms.yaml")


def merge_configs(
    default: dict[str, Any],
    user_yaml: dict[str, Any] | None = None,
    env_overrides: dict[str, Any] | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    合并配置：默认 < 用户 YAML < 环境变量 < 命令行。

    支持嵌套字典深度合并。
    """
    import copy

    def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(base)
        for k, v in overlay.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge(result[k], v)
            elif v is not None:
                result[k] = v
        return result

    merged = deep_merge(default, user_yaml or {})
    merged = deep_merge(merged, env_overrides or {})
    merged = deep_merge(merged, cli_overrides or {})
    return merged


def build_settings(
    user_yaml_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
    config_dir: Path | None = None,
) -> Settings:
    """
    构建最终 Settings 实例。

    优先级：命令行参数 > 环境变量 > 用户 YAML > 默认 YAML。
    """
    cfg_dir = config_dir or DEFAULT_CONFIG_DIR
    default_data = load_default_config(cfg_dir)
    user_data = load_yaml(user_yaml_path) if user_yaml_path else {}

    # 环境变量层（仅识别 IG_ 前缀的运行时配置，密码单独处理）
    env_overrides: dict[str, Any] = {}
    for key in ("hashtags", "exclude_files", "resume", "reset_task"):
        env_val = os.environ.get(f"FINDER_{key.upper()}")
        if env_val is not None:
            if key in ("resume", "reset_task"):
                env_overrides[key] = env_val.lower() in ("1", "true", "yes")
            elif key == "hashtags":
                env_overrides[key] = [h.strip() for h in env_val.split(",") if h.strip()]

    merged = merge_configs(default_data, user_data, env_overrides, cli_overrides)

    # 创建 Settings，pydantic-settings 会从 .env 读取 IG_USERNAME/IG_PASSWORD
    settings = Settings(**merged, config_dir=cfg_dir)

    return settings


def validate_settings(settings: Settings, skip_credentials: bool = False) -> list[str]:
    """
    校验配置完整性。返回错误信息列表（空表示通过）。

    Args:
        settings: 项目配置
        skip_credentials: 为 True 时跳过 IG_USERNAME/IG_PASSWORD 检查，
                          供 dry-run 模式使用。
    """
    errors: list[str] = []

    if not skip_credentials:
        if not settings.ig_username:
            errors.append("IG_USERNAME 未设置（请在 .env 或环境变量中配置）")
        if not settings.ig_password:
            errors.append("IG_PASSWORD 未设置（请在 .env 或环境变量中配置）")

    if settings.instagram.request_delay_min_seconds > settings.instagram.request_delay_max_seconds:
        errors.append("request_delay_min_seconds 不能大于 request_delay_max_seconds")

    if settings.filters.min_followers > settings.filters.max_followers:
        errors.append("min_followers 不能大于 max_followers")

    if settings.discovery.max_hashtags < 1:
        errors.append("max_hashtags 必须 >= 1")
    if settings.discovery.media_per_hashtag < 1:
        errors.append("media_per_hashtag 必须 >= 1")
    if settings.discovery.max_candidates < 1:
        errors.append("max_candidates 必须 >= 1")

    if settings.analysis.recent_media_amount < 1 or settings.analysis.recent_media_amount > 50:
        errors.append("recent_media_amount 应在 [1, 50] 之间")

    if not settings.output.formats:
        errors.append("output.formats 不能为空")

    return errors


def to_display_dict(settings: Settings) -> dict[str, Any]:
    """
    返回脱敏后的配置字典（用于 show-config 命令）。
    密码字段以 *** 显示，不泄露明文。
    """
    data = settings.model_dump(mode="json")
    # 脱敏
    if "ig_password" in data:
        data["ig_password"] = "***" if data["ig_password"] else ""
    # 不输出 Session 内容
    return data
