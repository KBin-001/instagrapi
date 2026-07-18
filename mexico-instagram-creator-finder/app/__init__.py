"""Mexico Instagram Creator Finder 应用包。"""

__version__ = "0.1.0"

# 默认初始化 INFO 级别日志（可被 setup_logging 覆盖）
from app.logging_config import get_logger, setup_logging  # noqa: E402

setup_logging(level="INFO")

__all__ = ["__version__", "get_logger", "setup_logging"]
