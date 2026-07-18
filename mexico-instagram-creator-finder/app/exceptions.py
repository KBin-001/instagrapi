"""Mexico Instagram Creator Finder 异常体系。"""


class FinderError(Exception):
    """项目所有异常的基类。"""


class ConfigError(FinderError):
    """配置加载或校验失败。"""


class InstagramClientError(FinderError):
    """Instagram 适配层调用失败（非安全停止）。"""


class SecurityStopError(FinderError):
    """
    遇到 Instagram 安全机制时的停止异常。

    触发场景：
    - ChallengeRequired
    - FeedbackRequired
    - PleaseWaitFewMinutes
    - ClientThrottledError
    - HTTP 429
    - 人工验证要求
    - 账号安全警告
    - Session 失效

    出现此异常时必须保存断点并停止，不得自动重试或绕过。
    """

    def __init__(self, message: str, *, reason: str = "", original: Exception | None = None):
        super().__init__(message)
        self.reason = reason or message
        self.original = original


class CheckpointError(FinderError):
    """断点保存或恢复失败。"""


class ExportError(FinderError):
    """导出失败。"""
