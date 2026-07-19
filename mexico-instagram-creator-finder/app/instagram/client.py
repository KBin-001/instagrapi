"""Instagram 统一适配层（实验性）。

⚠️ 本模块依赖 instagrapi 模拟移动端私有 API，可能触发 ChallengeRequired、
HTTP 429 等安全机制。**已不再作为默认数据采集通道**，仅供实验性使用。

默认数据采集通道为浏览器扩展（正式源码参见 browser_extension/，dist/chrome_extension/ 为兼容产物）。

业务模块禁止直接创建 instagrapi.Client()。
"""

from __future__ import annotations

from typing import Any

from app.config import InstagramSettings, Settings
from app.exceptions import InstagramClientError, SecurityStopError
from app.instagram.mappers import map_user_to_profile
from app.instagram.rate_limit import RateLimiter, retry_network_errors
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


def create_instagram_client() -> Any:
    """创建统一配置的 instagrapi.Client 实例（实验性）。

    所有 Client 创建都应通过此工厂函数，确保配置一致。
    业务层仍需维持顺序请求及 4-8 秒间隔（由 RateLimiter 控制）。
    """
    from instagrapi import Client

    client = Client()
    client.delay_range = [4, 8]
    client.num_retries = 1
    return client


class InstagramClient:
    """Instagram 业务适配层（实验性）。

    ⚠️ 本类**不再包含登录方法**。instagrapi 移动端登录已从产品中移除，
    默认数据采集通道改为浏览器扩展。本类仅保留 user_info_by_username /
    user_medias / hashtag_medias 等只读 API 调用方法，供实验性路径使用，
    不保证可用，SearchService 默认不会调用本类。

    调用方需自行通过其他方式完成 instagrapi Client 的认证
    （例如外部加载 settings 后 set_settings），再使用本类的只读方法。
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.ig_settings: InstagramSettings = settings.instagram
        self._client: Any | None = None
        self._rate_limiter = RateLimiter(
            min_seconds=self.ig_settings.request_delay_min_seconds,
            max_seconds=self.ig_settings.request_delay_max_seconds,
        )

    @property
    def client(self) -> Any:
        """延迟初始化 instagrapi.Client。"""
        if self._client is None:
            self._client = create_instagram_client()
        return self._client

    def _safe_call(self, func_name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """安全调用 Instagram API：间隔 + 重试 + 异常转换。

        调用方需自行保证 instagrapi.Client 已通过其他方式完成认证。
        """
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
        """[实验] 获取 Hashtag 的近期媒体 + Reels。

        Args:
            name: Hashtag 名称（不带 #）
            amount: 每类最多获取数量

        Returns:
            instagrapi.types.Media 列表
        """
        medias: list[Any] = []

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

        seen: set[str] = set()
        unique: list[Any] = []
        for m in medias:
            pk = str(getattr(m, "pk", id(m)))
            if pk not in seen:
                seen.add(pk)
                unique.append(m)
        return unique

    def user_info_by_username(self, username: str) -> ProfileData:
        """[实验] 获取账号公开资料。"""
        user = self._safe_call(
            "user_info_by_username",
            self.client.user_info_by_username,
            username,
        )
        return map_user_to_profile(user, username=username)

    def user_medias(self, username: str, amount: int = 12) -> list[Any]:
        """[实验] 获取账号近期公开内容。"""
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

    def search_users(self, query: str, amount: int = 20) -> list[Any]:
        """[实验] 使用已认证本地 Session 低频搜索公开账号。"""
        users = self._safe_call(
            "search_users",
            self.client.search_users,
            query,
            amount,
        )
        return list(users or [])[:amount]

    def related_profiles(self, username: str, amount: int = 20) -> list[Any]:
        """[实验] 读取公开 GraphQL 返回的相似账号；不可用时由安全异常策略停止。"""
        user_id = self._safe_call(
            "user_id_from_username",
            self.client.user_id_from_username,
            username,
        )
        users = self._safe_call(
            "user_related_profiles_gql",
            self.client.user_related_profiles_gql,
            user_id,
        )
        return list(users or [])[:amount]
