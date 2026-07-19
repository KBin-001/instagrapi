"""扩展通信令牌存储。

随机生成 32 字节 URL-safe 令牌，持久化到 data/extension_token.txt。
- 令牌仅本机使用，扩展与 NiceGUI 共享同一台机器
- 令牌文件权限默认仅当前用户可读写（依赖文件系统默认权限）
- 不写入日志、不写入数据库
"""

from __future__ import annotations

import secrets
from pathlib import Path

from app.config import resolve_path


class ExtensionTokenStore:
    """扩展通信令牌存储（持久化到本地文件）。"""

    DEFAULT_FILE = "data/extension_token.txt"

    def __init__(self, path: str | Path | None = None) -> None:
        self.path: Path = self.default_path() if path is None else resolve_path(path)

    @classmethod
    def default_path(cls) -> Path:
        """默认令牌文件路径（基于 PROJECT_ROOT 解析）。"""
        return resolve_path(cls.DEFAULT_FILE)

    def get_or_create(self) -> str:
        """获取当前令牌；若不存在则生成并持久化。"""
        if self.path.exists():
            token = self.path.read_text(encoding="utf-8").strip()
            if token:
                return token
        return self.regenerate()

    def regenerate(self) -> str:
        """重新生成随机令牌并原子写入文件。"""
        token = secrets.token_urlsafe(32)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(token, encoding="utf-8")
        tmp.replace(self.path)
        return token

    def verify(self, token: str | None) -> bool:
        """校验令牌是否匹配（常数时间比较，防时序攻击）。"""
        if not token:
            return False
        expected = self.get_or_create()
        return secrets.compare_digest(token, expected)

    def delete(self) -> bool:
        """删除令牌文件；返回是否确实删除了。"""
        if self.path.exists():
            self.path.unlink()
            return True
        return False
