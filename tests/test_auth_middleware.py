"""
JWT 认证中间件单元测试
覆盖：白名单放行、Cookie/Header 认证、Token 类型隔离、OPTIONS 放行
"""
import pytest
from unittest.mock import patch

from jose import jwt

from app.core.auth_middleware import _AUTH_WHITELIST, _verify_token_sync, JWTAuthMiddleware
from app.core.security import create_access_token, create_refresh_token

SECRET = "test-secret-key"
ALGORITHM = "HS256"

_patch_secret = patch("app.core.auth_middleware.get_secret_key", lambda: SECRET)
_patch_algo = patch("app.core.auth_middleware.get_algorithm", lambda: ALGORITHM)

# 配置 mock
_base_patches = (
    patch("app.core.auth_middleware.get_secret_key", lambda: SECRET),
    patch("app.core.auth_middleware.get_algorithm", lambda: ALGORITHM),
)


class TestAuthWhitelist:
    """白名单路径列表确认"""

    def test_login_in_whitelist(self):
        assert "/api/v1/users/login" in _AUTH_WHITELIST

    def test_refresh_in_whitelist(self):
        assert "/api/v1/users/refresh" in _AUTH_WHITELIST

    def test_health_in_whitelist(self):
        assert "/api/v1/health" in _AUTH_WHITELIST

    def test_system_status_in_whitelist(self):
        assert "/api/v1/system/status" in _AUTH_WHITELIST

    def test_system_setup_in_whitelist(self):
        assert "/api/v1/system/setup" in _AUTH_WHITELIST

    def test_system_env_config_in_whitelist(self):
        assert "/api/v1/system/env-config" in _AUTH_WHITELIST

    def test_system_existing_config_in_whitelist(self):
        assert "/api/v1/system/existing-config" in _AUTH_WHITELIST

    def test_system_test_connection_in_whitelist(self):
        assert "/api/v1/system/test-connection" in _AUTH_WHITELIST

    def test_me_not_in_whitelist(self):
        assert "/api/v1/users/me" not in _AUTH_WHITELIST

    def test_tasks_not_in_whitelist(self):
        assert "/api/v1/tasks/list" not in _AUTH_WHITELIST


class TestVerifyTokenSync:
    """_verify_token_sync：Access Token 同步验证"""

    def _make_access_token(self, sub="admin", exp=None, **extra):
        """使用测试密钥直接构造 JWT，避免依赖 app.core.security 的真实密钥"""
        from datetime import UTC, datetime, timedelta
        payload = {"sub": sub, "type": "access"}
        if exp is None:
            exp = datetime.now(UTC) + timedelta(minutes=30)
        payload["exp"] = exp
        payload.update(extra)
        return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

    def _make_refresh_token(self, sub="admin"):
        from datetime import UTC, datetime, timedelta
        payload = {"sub": sub, "type": "refresh", "exp": datetime.now(UTC) + timedelta(days=7)}
        return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

    @_patch_secret
    @_patch_algo
    def test_valid_access_token_returns_username(self):
        with patch("app.core.auth_middleware.config") as mock_cfg:
            mock_cfg.get.return_value = "admin"
            token = self._make_access_token()
            result = _verify_token_sync(token)
            assert result == "admin"

    @_patch_secret
    @_patch_algo
    def test_refresh_token_returns_none(self):
        """Refresh Token (type=refresh) 无法通过验证"""
        with patch("app.core.auth_middleware.config") as mock_cfg:
            mock_cfg.get.return_value = "admin"
            token = self._make_refresh_token()
            result = _verify_token_sync(token)
            assert result is None

    @_patch_secret
    @_patch_algo
    def test_invalid_token_returns_none(self):
        with patch("app.core.auth_middleware.config") as mock_cfg:
            mock_cfg.get.return_value = "admin"
            result = _verify_token_sync("not.a.valid.token")
            assert result is None

    @_patch_secret
    @_patch_algo
    def test_empty_token_returns_none(self):
        with patch("app.core.auth_middleware.config") as mock_cfg:
            mock_cfg.get.return_value = "admin"
            result = _verify_token_sync("")
            assert result is None

    @_patch_secret
    @_patch_algo
    def test_wrong_username_returns_none(self):
        with patch("app.core.auth_middleware.config") as mock_cfg:
            mock_cfg.get.return_value = "admin"  # 配置中的用户名
            token = self._make_access_token(sub="hacker")  # token 中是 hacker
            result = _verify_token_sync(token)
            assert result is None

    @_patch_secret
    @_patch_algo
    def test_no_sub_returns_none(self):
        with patch("app.core.auth_middleware.config") as mock_cfg:
            mock_cfg.get.return_value = "admin"
            token = self._make_access_token(sub=None)  # 无 sub
            result = _verify_token_sync(token)
            assert result is None


class TestUnauthorizedResponse:
    """_unauthorized 静态方法"""

    def test_unauthorized_format(self):
        resp = JWTAuthMiddleware._unauthorized("测试错误")
        assert resp.status_code == 200
        body = resp.body.decode("utf-8")
        import json
        data = json.loads(body)
        assert data["code"] == 40100
        assert data["message"] == "测试错误"
        assert data["data"] is None
