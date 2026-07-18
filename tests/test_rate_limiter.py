"""
登录限流器单元测试
覆盖：滑动窗口计数、封禁/解封、过期清理、单例模式
使用 mock time 控制时间推进，不依赖真实时钟
"""
import time
import pytest
from unittest.mock import patch

from app.core.rate_limiter import LoginRateLimiter, login_rate_limiter


class TestLoginRateLimiterBasic:
    """基础功能：正常通过、超限封禁、解封后恢复"""

    def setup_method(self):
        """每个测试前创建新的限流器实例，避免状态污染"""
        self.limiter = LoginRateLimiter()

    def test_first_attempt_allowed(self):
        allowed, msg = self.limiter.check("192.168.1.1")
        assert allowed is True
        assert msg == ""

    def test_within_limit(self):
        """29 次请求在限制内均放行"""
        for i in range(29):
            allowed, _ = self.limiter.check("10.0.0.1")
            assert allowed is True

    def test_exceed_limit_blocks(self):
        """第 31 次请求触发封禁"""
        ip = "10.0.0.2"
        for _ in range(30):
            allowed, _ = self.limiter.check(ip)
            assert allowed is True
        # 第 31 次应被封禁
        allowed, msg = self.limiter.check(ip)
        assert allowed is False
        assert "过于频繁" in msg

    def test_blocked_during_ban(self):
        """封禁期间所有请求都被拒绝"""
        ip = "10.0.0.3"
        # 触发封禁
        for _ in range(31):
            self.limiter.check(ip)

        for _ in range(5):
            allowed, msg = self.limiter.check(ip)
            assert allowed is False
            assert "过于频繁" in msg

    def test_different_ips_independent(self):
        """不同 IP 的限流状态独立"""
        self.limiter.check("1.1.1.1")
        for _ in range(30):
            self.limiter.check("2.2.2.2")
        # 1.1.1.1 只请求了 1 次，应未被封
        allowed, _ = self.limiter.check("1.1.1.1")
        assert allowed is True

    def test_ban_expires_after_block_seconds(self):
        """封禁期满后恢复放行"""
        ip = "10.0.0.4"
        # 第一轮：触发封禁
        for _ in range(31):
            self.limiter.check(ip)

        # 验证被封
        allowed, _ = self.limiter.check(ip)
        assert allowed is False

        # 直接修改 blocked_until 模拟时间过期
        self.limiter._entries[ip].blocked_until = 0
        # 窗口内旧记录也需要清理
        self.limiter._entries[ip].timestamps = []

        allowed, _ = self.limiter.check(ip)
        assert allowed is True

    def test_reset_clears_entry(self):
        ip = "10.0.0.5"
        for _ in range(31):
            self.limiter.check(ip)

        self.limiter.reset(ip)
        assert ip not in self.limiter._entries

        allowed, _ = self.limiter.check(ip)
        assert allowed is True


class TestLoginRateLimiterTimeSimulation:
    """使用 mock time 模拟真实时间推进"""

    def test_window_slides_with_time(self):
        """窗口滑动：旧请求过期后不计入窗口"""
        limiter = LoginRateLimiter()
        fake_now = 1000.0

        with patch.object(time, 'monotonic', return_value=fake_now):
            # 在时刻 1000 发起 30 次请求
            for _ in range(30):
                allowed, _ = limiter.check("10.0.0.6")
                assert allowed is True
            # 第 31 次 — 被封
            allowed, _ = limiter.check("10.0.0.6")
            assert allowed is False

        # 时间推进到 2000（远超窗口期 60s + 封禁 600s）
        fake_now = 2000.0
        with patch.object(time, 'monotonic', return_value=fake_now):
            allowed, _ = limiter.check("10.0.0.6")
            assert allowed is True  # 封禁期满 + 窗口外的旧记录已过期

    def test_partial_window_expiry(self):
        """窗口部分过期后计数减少"""
        limiter = LoginRateLimiter()
        base_time = 1000.0

        with patch.object(time, 'monotonic', return_value=base_time):
            # 在时刻 1000 发起 20 次
            for _ in range(20):
                limiter.check("10.0.0.7")

        # 推进 70 秒（窗口 60s 全部过期）
        with patch.object(time, 'monotonic', return_value=base_time + 70):
            # 此时窗口内记录已全部过期
            entry = limiter._entries.get("10.0.0.7")
            if entry:
                # 旧记录被清除后，计数从 0 开始
                pass
            # 新请求不被封禁
            allowed, _ = limiter.check("10.0.0.7")
            assert allowed is True

    def test_cleanup_removes_stale_entries(self):
        """过期条目在 cleanup 时被清除"""
        limiter = LoginRateLimiter()

        with patch.object(time, 'monotonic', return_value=1000.0):
            limiter.check("10.0.0.8")
            assert "10.0.0.8" in limiter._entries

        # 强制触发清理：设置 last_cleanup 为很早
        limiter._last_cleanup = 0
        # 推进时间到远超窗口期
        with patch.object(time, 'monotonic', return_value=2000.0):
            # 清理条件: now - last_cleanup >= 300
            limiter._cleanup_expired()
            # 记录应被清除（无时间戳、封禁已过期）
            assert "10.0.0.8" not in limiter._entries


class TestLoginRateLimiterSingleton:
    """单例模式验证"""

    def test_get_instance_returns_same(self):
        a = LoginRateLimiter.get_instance()
        b = LoginRateLimiter.get_instance()
        assert a is b

    def test_module_level_singleton(self):
        assert login_rate_limiter is LoginRateLimiter.get_instance()


class TestLoginRateLimiterEdgeCases:
    """边界情况"""

    def setup_method(self):
        self.limiter = LoginRateLimiter()

    def test_empty_ip_string(self):
        allowed, _ = self.limiter.check("")
        assert allowed is True

    def test_ipv6_address(self):
        allowed, _ = self.limiter.check("::1")
        assert allowed is True

    def test_rapid_sequential_same_ip(self):
        """快速连续请求不应有并发问题（单线程下验证）"""
        for _ in range(25):
            allowed, _ = self.limiter.check("10.0.0.9")
            assert allowed is True
        # 还未达封禁阈值
        entry = self.limiter._entries.get("10.0.0.9")
        assert entry.blocked_until == 0.0
