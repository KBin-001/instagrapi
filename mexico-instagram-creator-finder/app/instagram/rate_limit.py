"""请求间隔与指数退避重试。

约束：
- 默认请求之间随机等待 4-8 秒
- 网络错误最多重试 2 次，指数退避
- 安全异常（429/Challenge/FeedbackRequired 等）不重试
- 不使用线程池或异步并发
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger("mexico_finder.instagram.rate_limit")


class RateLimiter:
    """请求间隔控制器。"""

    def __init__(self, min_seconds: int = 4, max_seconds: int = 8):
        if min_seconds < 0 or max_seconds < min_seconds:
            raise ValueError("invalid delay range")
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds

    def wait(self) -> None:
        """随机等待 min~max 秒。"""
        delay = random.uniform(self.min_seconds, self.max_seconds)
        logger.debug("sleeping %.2fs before next request", delay)
        time.sleep(delay)


def retry_network_errors(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 2,
    base_backoff: float = 2.0,
    **kwargs: Any,
) -> T:
    """
    对临时网络错误进行指数退避重试。

    仅捕获可明确判断为短暂网络异常的问题：
    - DNS 错误
    - 连接超时
    - 临时服务器错误（5xx）

    不重试：
    - 429
    - ChallengeRequired
    - FeedbackRequired
    - PleaseWaitFewMinutes
    - ClientThrottledError
    - 登录验证
    - Session 安全警告
    - 权限拒绝
    """

    from instagrapi.exceptions import (  # type: ignore
        ChallengeRequired,
        ClientConnectionError,
        ClientRequestTimeout,
        ClientThrottledError,
        FeedbackRequired,
        PleaseWaitFewMinutes,
        RateLimitError,
        SentryBlock,
    )

    # 不重试的异常类型
    non_retryable: tuple[type[Exception], ...] = (
        ClientThrottledError,
        FeedbackRequired,
        PleaseWaitFewMinutes,
        RateLimitError,
        SentryBlock,
        ChallengeRequired,
    )

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except non_retryable:
            # 安全异常，立即向上抛出，不重试
            raise
        except (ClientConnectionError, ClientRequestTimeout, ConnectionError, TimeoutError, OSError) as e:
            last_exc = e
            if attempt >= max_retries:
                logger.warning("network error after %d attempts: %s", attempt + 1, e)
                raise
            backoff = base_backoff * (2**attempt) + random.uniform(0, 1)
            logger.warning(
                "network error (attempt %d/%d): %s; retrying in %.2fs",
                attempt + 1,
                max_retries + 1,
                e,
                backoff,
            )
            time.sleep(backoff)
    # 不应到达
    assert last_exc is not None
    raise last_exc
