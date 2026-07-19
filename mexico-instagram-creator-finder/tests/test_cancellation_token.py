"""CancellationToken 单元测试。"""

from __future__ import annotations

import threading
import time

from app.services.domain import CancellationToken


def test_token_initial_not_cancelled() -> None:
    token = CancellationToken()
    assert token.is_cancelled is False


def test_token_cancel_sets_flag() -> None:
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True


def test_token_idempotent_cancel() -> None:
    token = CancellationToken()
    token.cancel()
    token.cancel()  # 重复取消不应出错
    assert token.is_cancelled is True


def test_token_reset() -> None:
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True
    token.reset()
    assert token.is_cancelled is False


def test_token_thread_safe_cancel_from_another_thread() -> None:
    """从另一个线程取消令牌。"""
    token = CancellationToken()

    def cancel_after_delay() -> None:
        time.sleep(0.05)
        token.cancel()

    t = threading.Thread(target=cancel_after_delay)
    t.start()

    # 主线程轮询检查
    waited = 0.0
    while not token.is_cancelled and waited < 1.0:
        time.sleep(0.01)
        waited += 0.01

    t.join()
    assert token.is_cancelled is True


def test_token_independent_instances() -> None:
    """多个 CancellationToken 互不影响。"""
    t1 = CancellationToken()
    t2 = CancellationToken()
    t1.cancel()
    assert t1.is_cancelled is True
    assert t2.is_cancelled is False
