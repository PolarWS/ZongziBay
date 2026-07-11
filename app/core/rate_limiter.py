"""
登录限流器：基于 IP 的滑动窗口限流
- 每分钟最多 30 次登录尝试
- 超过限制后封禁 10 分钟
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict

logger = logging.getLogger(__name__)

# 限流参数
_MAX_ATTEMPTS = 30       # 每分钟最大尝试次数
_WINDOW_SECONDS = 60     # 统计窗口（秒）
_BLOCK_SECONDS = 600     # 封禁时长（秒），10 分钟


@dataclass
class _RateLimitEntry:
    """单个 IP 的限流记录"""
    timestamps: list = field(default_factory=list)  # 最近尝试的时间戳列表
    blocked_until: float = 0.0  # 封禁截止时间戳（秒）


class LoginRateLimiter:
    """登录限流器（线程安全、单例）"""

    _instance: "LoginRateLimiter | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self._entries: Dict[str, _RateLimitEntry] = {}
        self._cleanup_lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    @classmethod
    def get_instance(cls) -> "LoginRateLimiter":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _cleanup_expired(self):
        """清理过期记录，防止内存泄漏"""
        now = time.monotonic()
        # 每 5 分钟清理一次
        if now - self._last_cleanup < 300:
            return
        self._last_cleanup = now

        with self._cleanup_lock:
            expired_ips = []
            for ip, entry in self._entries.items():
                # 如果封禁已过期且没有活跃的时间戳记录
                if now > entry.blocked_until:
                    # 清理超过窗口 2 倍时间的旧记录
                    entry.timestamps = [t for t in entry.timestamps if now - t < _WINDOW_SECONDS * 2]
                    if not entry.timestamps:
                        expired_ips.append(ip)

            for ip in expired_ips:
                del self._entries[ip]
                logger.debug(f"限流记录已清理: {ip}")

    def check(self, ip: str) -> tuple[bool, str]:
        """
        检查 IP 是否允许登录。

        返回:
            (allowed, message)
            - allowed=True: 允许登录
            - allowed=False: 被限流，message 包含原因
        """
        now = time.monotonic()
        self._cleanup_expired()

        with self._cleanup_lock:
            entry = self._entries.get(ip)

            if entry is None:
                entry = _RateLimitEntry()
                self._entries[ip] = entry

            # 检查是否处于封禁期
            if now < entry.blocked_until:
                remaining = int(entry.blocked_until - now)
                minutes = remaining // 60
                seconds = remaining % 60
                logger.warning(f"IP {ip} 处于封禁期，剩余 {minutes} 分 {seconds} 秒")
                return False, f"登录尝试过于频繁，请等待 {minutes} 分 {seconds} 秒后再试"

            # 清理窗口外的旧记录
            window_start = now - _WINDOW_SECONDS
            entry.timestamps = [t for t in entry.timestamps if t > window_start]

            # 记录本次尝试
            entry.timestamps.append(now)
            attempt_count = len(entry.timestamps)

            # 超过限制则封禁
            if attempt_count > _MAX_ATTEMPTS:
                entry.blocked_until = now + _BLOCK_SECONDS
                logger.warning(f"IP {ip} 登录次数达到 {attempt_count} 次，封禁 {_BLOCK_SECONDS // 60} 分钟")
                return False, f"登录尝试过于频繁，请等待 {_BLOCK_SECONDS // 60} 分钟后再试"

            logger.debug(f"IP {ip} 登录尝试 {attempt_count}/{_MAX_ATTEMPTS}")
            return True, ""

    def reset(self, ip: str):
        """手动重置某个 IP 的限流记录（调试用）"""
        with self._cleanup_lock:
            self._entries.pop(ip, None)
            logger.info(f"已手动重置 IP {ip} 的限流记录")


# 模块级单例
login_rate_limiter = LoginRateLimiter.get_instance()
