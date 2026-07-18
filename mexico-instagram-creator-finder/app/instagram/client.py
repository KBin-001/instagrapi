"""Instagram 统一适配层。

所有 instagrapi.Client 调用通过本模块封装。业务模块禁止直接创建 Client()。
"""

from __future__ import annotations

from typing import Any

from app.config import InstagramSettings, Settings
from app.exceptions import InstagramClientError, SecurityStopError
from app.instagram.mappers import map_user_to_profile
from app.instagram.rate_limit import RateLimiter, retry_network_errors
from app.instagram.session import load_session, save_session
from app.logging_config import get_logger
from app.models import ProfileData

logger = get_logger("instagram.client")

# 安全异常类型，触发即停止
_SECURITY_EXCEPTION_NAMES = (
    "ChallengeRequired",
    "FeedbackRequired",
    "PleaseWaitFewMinutes",
    "ClientThrottledError",
    "RateLimitError",
    "SentryBlock",
    "LoginRequired",
    "AccountSuspended",
    "ProxyAddressIsBlocked",
    "ChallengeSelfieCaptcha",
    "ChallengeUnknownStep",
)


def _is_security_exception(exc: Exception) -> bool:
    """判断是否为安全相关异常（按类名匹配，避免 import 失败）。"""
    name = type(exc).__name__
    return name in _SECURITY_EXCEPTION_NAMES


def _is_http_429(exc: Exception) -> bool:
    """检查异常是否对应 HTTP 429。"""
    code = getattr(exc, "code", None)
    response = getattr(exc, "response", None)
    if code == 429:
        return True
    if response is not None and getattr(response, "status_code", None) == 429:
        return True
    return False


class InstagramClient:
    """Instagram 统一适配层。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.ig_settings: InstagramSettings = settings.instagram
        self._client: Any | None = None  # instagrapi.Client 实例
        self._rate_limiter = RateLimiter(
            min_seconds=self.ig_settings.request_delay_min_seconds,
            max_seconds=self.ig_settings.request_delay_max_seconds,
        )
        self._username: str | None = settings.ig_username
        self._logged_in = False

    @property
    def client(self) -> Any:
        """延迟初始化 instagrapi.Client。"""
        if self._client is None:
            from instagrapi import Client

            self._client = Client()
        return self._client

    def login_from_env(self) -> None:
        """
        从环境变量登录 Instagram。

        - 若 Session 文件存在，先加载复用
        - 失败则用 IG_USERNAME/IG_PASSWORD 登录
        - 登录成功后保存 Session
        - 密码不写入日志、数据库、YAML
        """
        if not self._username:
            raise InstagramClientError("IG_USERNAME 未设置；请在 .env 或环境变量中配置 IG_USERNAME 和 IG_PASSWORD")

        # 先尝试 Session 复用
        session_data = load_session(self.ig_settings.session_file)
        if session_data:
            try:
                self.client.set_settings(session_data)
                # 验证 session 是否有效
                try:
                    self._rate_limiter.wait()
                    self.client.user_info_by_username(self._username)
                    self._logged_in = True
                    logger.info("session reused for user %s", self._username)
                    return
                except Exception as e:
                    if _is_security_exception(e) or _is_http_429(e):
                        # 安全异常：转换为 SecurityStopError 并立即停止
                        reason = f"session validation security stop: {type(e).__name__}"
                        raise SecurityStopError(reason, reason=reason, original=e) from e
                    logger.warning("session invalid, will re-login: %s", e)
            except SecurityStopError:
                raise
            except Exception as e:
                logger.warning("session load failed: %s", e)

        # 用密码登录
        password = self.settings.ig_password
        if not password:
            raise InstagramClientError("IG_PASSWORD 未设置；请在 .env 或环境变量中配置")

        try:
            self._rate_limiter.wait()
            self.client.login(self._username, password)
            self._logged_in = True
            # 保存 Session
            save_session(self.ig_settings.session_file, self.client.get_settings())
            logger.info("login successful for user %s; session saved", self._username)
        except Exception as e:
            if _is_security_exception(e):
                reason = f"login security stop: {type(e).__name__}: {e}"
                raise SecurityStopError(reason, reason=reason, original=e) from e
            if _is_http_429(e):
                reason = "login blocked by HTTP 429"
                raise SecurityStopError(reason, reason=reason, original=e) from e
            raise InstagramClientError(f"login failed: {e}") from e
        finally:
            # 不在日志中保留 password 变量
            password = None  # type: ignore

    def _safe_call(self, func_name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """
        安全调用 Instagram API：间隔 + 重试 + 异常转换。
        """
        if not self._logged_in:
            raise InstagramClientError("client not logged in; call login_from_env() first")

        self._rate_limiter.wait()

        try:
            return retry_network_errors(
                func,
                *args,
                max_retries=self.ig_settings.retry_network_errors,
                **kwargs,
            )
        except Exception as e:
            if _is_security_exception(e):
                reason = f"{func_name} security stop: {type(e).__name__}"
                logger.error("security stop in %s: %s", func_name, type(e).__name__)
                raise SecurityStopError(reason, reason=reason, original=e) from e
            if _is_http_429(e):
                reason = f"{func_name} blocked by HTTP 429"
                logger.error("HTTP 429 in %s", func_name)
                raise SecurityStopError(reason, reason=reason, original=e) from e
            logger.error("instagram call %s failed: %s", func_name, e)
            raise InstagramClientError(f"{func_name} failed: {e}") from e

    def hashtag_medias(self, name: str, amount: int = 20) -> list[Any]:
        """
        获取 Hashtag 的近期媒体 + Reels。

        Args:
            name: Hashtag 名称（不带 #）
            amount: 每类最多获取数量

        Returns:
            instagrapi.types.Media 列表
        """
        medias: list[Any] = []

        # recent
        try:
            recent = self._safe_call(
                "hashtag_medias_recent",
                self.client.hashtag_medias_recent,
                name,
                amount,
            )
            medias.extend(recent or [])
        except InstagramClientError as e:
            logger.warning("hashtag_medias_recent failed for %s: %s", name, e)

        # reels
        try:
            reels = self._safe_call(
                "hashtag_medias_reels_v1",
                self.client.hashtag_medias_reels_v1,
                name,
                amount,
            )
            medias.extend(reels or [])
        except InstagramClientError as e:
            logger.warning("hashtag_medias_reels_v1 failed for %s: %s", name, e)

        # 去重（按 pk）
        seen: set[str] = set()
        unique: list[Any] = []
        for m in medias:
            pk = str(getattr(m, "pk", id(m)))
            if pk not in seen:
                seen.add(pk)
                unique.append(m)
        return unique

    def user_info_by_username(self, username: str) -> ProfileData:
        """获取账号公开资料。"""
        user = self._safe_call(
            "user_info_by_username",
            self.client.user_info_by_username,
            username,
        )
        return map_user_to_profile(user, username=username)

    def user_medias(self, username: str, amount: int = 12) -> list[Any]:
        """获取账号近期公开内容。"""
        # 先拿 user_id
        user_id = self._safe_call(
            "user_id_from_username",
            self.client.user_id_from_username,
            username,
        )
        medias = self._safe_call(
            "user_medias",
            self.client.user_medias,
            user_id,
            amount,
        )
        return medias or []

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
