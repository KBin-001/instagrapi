"""日志配置与脱敏过滤器。

禁止记录：密码、Cookie、完整 Session、Authorization Header、私信内容、私人联系方式。
允许记录：任务 ID、用户名、请求类型、成功/失败、错误分类、停止原因、运行时间。
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 需要脱敏的关键词模式
SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    # 密码相关
    (r"(?i)(password|passwd|pwd|ig_password)\s*[=:]\s*\S+", r"\1=***"),
    (r"(?i)(IG_PASSWORD)\s*=\s*[^\s&]+", r"\1=***"),
    # Authorization Header
    (r"(?i)(authorization)\s*:\s*bearer\s+\S+", r"\1: Bearer ***"),
    (r"(?i)(authorization)\s*:\s*\S+", r"\1: ***"),
    # Cookie
    (r"(?i)(cookie|set-cookie)\s*:\s*[^\r\n]+", r"\1: ***"),
    # Session ID / Token
    (r"(?i)(sessionid|session_id|access_token|csrf_token|mid|ig_did|ig_cb)\s*[=:]\s*\S+", r"\1=***"),
    # Instagram Bearer token
    (r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}", r"Bearer ***"),
    # 邮箱（保守脱敏：保留 @ 后域名）
    (r"[\w\.\-]+@[\w\.\-]+\.\w+", r"***@***"),
]

# 编译正则
_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str]] = [(re.compile(p), r) for p, r in SENSITIVE_PATTERNS]


class SensitiveDataFilter(logging.Filter):
    """日志脱敏过滤器，对每条日志的 message 做正则替换。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True

        sanitized = msg
        for pattern, replacement in _COMPILED_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        if sanitized != msg:
            # 替换 record.msg 与 args，让最终输出为脱敏后内容
            record.msg = sanitized
            record.args = ()
        return True


def setup_logging(
    level: str | int = logging.INFO,
    log_file: Path | str | None = None,
    *,
    enable_console: bool = True,
) -> logging.Logger:
    """
    配置项目日志。

    Args:
        level: 日志级别（"DEBUG"/"INFO"/"WARNING"/"ERROR" 或 logging 常量）
        log_file: 可选日志文件路径；None 则仅控制台
        enable_console: 是否启用控制台输出

    Returns:
        项目根 logger
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger("mexico_finder")
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sensitive_filter = SensitiveDataFilter()

    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(sensitive_filter)
        root_logger.addHandler(console_handler)

    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)

    # 同时降低 instagrapi 库的日志级别，避免泄露敏感请求
    logging.getLogger("instagrapi").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取项目子 logger。"""
    if not name.startswith("mexico_finder"):
        name = f"mexico_finder.{name}"
    return logging.getLogger(name)
