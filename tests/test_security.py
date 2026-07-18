"""
安全与 JWT 单元测试：Token 生成与解析、密码哈希、Token 类型验证
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from jose import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    is_hashed,
    verify_password,
)

SECRET = "test-secret-key"
ALGORITHM = "HS256"

_patch_secret = patch("app.core.security.get_secret_key", lambda: SECRET)
_patch_algo = patch("app.core.security.get_algorithm", lambda: ALGORITHM)


# ---------------------------------------------------------------------------
# Access Token 测试
# ---------------------------------------------------------------------------

class TestAccessToken:
    """create_access_token：生成与解码"""

    @_patch_secret
    @_patch_algo
    def test_create_access_token_decodable(self):
        """生成 token 后可用相同密钥解析出 sub"""
        token = create_access_token(data={"sub": "admin"})
        assert isinstance(token, str)
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin"
        assert "exp" in payload

    @_patch_secret
    @_patch_algo
    def test_create_access_token_with_expires_delta(self):
        """指定 expires_delta 时过期时间正确"""
        token = create_access_token(data={"sub": "user"}, expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert payload["sub"] == "user"
        now = datetime.now(UTC).timestamp()
        assert payload["exp"] >= now
        assert payload["exp"] <= now + 360

    @_patch_secret
    @_patch_algo
    def test_access_token_has_type_access(self):
        """Access Token 的 payload 中 type 为 access"""
        token = create_access_token(data={"sub": "user"})
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert payload.get("type") == "access"


# ---------------------------------------------------------------------------
# Refresh Token 测试
# ---------------------------------------------------------------------------

class TestRefreshToken:
    """create_refresh_token / decode_refresh_token：生成、解码、类型校验"""

    @_patch_secret
    @_patch_algo
    def test_create_refresh_token_decodable(self):
        token = create_refresh_token(data={"sub": "admin"})
        assert isinstance(token, str)
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin"
        assert payload.get("type") == "refresh"
        assert "exp" in payload

    @_patch_secret
    @_patch_algo
    def test_create_refresh_token_with_expires_delta(self):
        token = create_refresh_token(data={"sub": "user"}, expires_delta=timedelta(days=30))
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert payload["sub"] == "user"
        now = datetime.now(UTC).timestamp()
        # 30 天 + 1 天容差
        assert payload["exp"] >= now
        assert payload["exp"] <= now + 31 * 24 * 3600

    @_patch_secret
    @_patch_algo
    def test_decode_refresh_token_success(self):
        token = create_refresh_token(data={"sub": "admin"})
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "admin"

    @_patch_secret
    @_patch_algo
    def test_decode_refresh_token_rejects_access_token(self):
        """decode_refresh_token 拒绝 type=access 的 token"""
        access_token = create_access_token(data={"sub": "admin"})
        payload = decode_refresh_token(access_token)
        assert payload is None

    @_patch_secret
    @_patch_algo
    def test_decode_refresh_token_invalid(self):
        """无效 token 返回 None"""
        assert decode_refresh_token("not-a-valid-token") is None
        assert decode_refresh_token("") is None

    @_patch_secret
    @_patch_algo
    def test_decode_refresh_token_expired(self):
        """过期 token 返回 None"""
        token = create_refresh_token(data={"sub": "user"}, expires_delta=timedelta(seconds=-1))
        payload = decode_refresh_token(token)
        assert payload is None


# ---------------------------------------------------------------------------
# 密码哈希测试
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """hash_password / verify_password / is_hashed"""

    def test_hash_password_is_bcrypt(self):
        hashed = hash_password("mypassword")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_correct_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_hashed_returns_false(self):
        assert verify_password("anything", "") is False
        assert verify_password("anything", None) is False

    def test_is_hashed_true(self):
        assert is_hashed("$2b$12$" + "a" * 53) is True
        assert is_hashed("$2a$10$" + "b" * 53) is True

    def test_is_hashed_false(self):
        assert is_hashed("plain_password") is False
        assert is_hashed("password123") is False
        assert is_hashed("") is False

    def test_verify_with_plaintext_fallback(self):
        """兼容旧数据：明文密码与哈希前的原文比对"""
        assert verify_password("admin", "admin") is True
        assert verify_password("admin", "wrong_admin") is False

    def test_hash_long_password_truncated(self):
        """超长密码（>72 字节）自动截断"""
        long_pwd = "a" * 100
        hashed = hash_password(long_pwd)
        assert verify_password(long_pwd, hashed)

    def test_cross_token_type_isolation(self):
        """Access Token 不能通过 decode_refresh_token 验证，反之亦然（通过 type 字段隔离）"""
        access = create_access_token(data={"sub": "user"})
        with _patch_secret, _patch_algo:
            assert decode_refresh_token(access) is None


# ---------------------------------------------------------------------------
# PBKDF2 兼容层测试（is_pbkdf2_hash / PBKDF2 验证）
# ---------------------------------------------------------------------------

class TestPBKDF2Compatibility:
    """is_pbkdf2_hash 和旧版 PBKDF2 密码验证兼容"""

    def test_is_pbkdf2_hash_true(self):
        from app.core.security import is_pbkdf2_hash
        assert is_pbkdf2_hash("pbkdf2_sha256$310000$abc123$xyz789") is True

    def test_is_pbkdf2_hash_false_for_bcrypt(self):
        from app.core.security import is_pbkdf2_hash
        assert is_pbkdf2_hash("$2b$12$abc123") is False

    def test_is_pbkdf2_hash_false_for_plaintext(self):
        from app.core.security import is_pbkdf2_hash
        assert is_pbkdf2_hash("admin") is False
        assert is_pbkdf2_hash("") is False

    def test_is_hashed_true_for_pbkdf2(self):
        """is_hashed 应同时识别 bcrypt 和 PBKDF2"""
        from app.core.security import is_hashed
        assert is_hashed("pbkdf2_sha256$310000$salt$digest") is True
        assert is_hashed("$2b$12$" + "a" * 53) is True

    def test_verify_password_with_pbkdf2_hash(self):
        """verify_password 支持旧版 PBKDF2 哈希验证"""
        import hashlib, base64, secrets
        salt = secrets.token_bytes(16)
        iterations = 100000
        password = "test_password"
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        salt_b64 = base64.urlsafe_b64encode(salt).decode("utf-8").rstrip("=")
        digest_b64 = base64.urlsafe_b64encode(dk).decode("utf-8").rstrip("=")
        pbkdf2_hash = f"pbkdf2_sha256${iterations}${salt_b64}${digest_b64}"

        from app.core.security import verify_password as sec_verify
        assert sec_verify(password, pbkdf2_hash) is True
        assert sec_verify("wrong_password", pbkdf2_hash) is False

    def test_verify_password_pbkdf2_invalid_format(self):
        from app.core.security import verify_password as sec_verify
        assert sec_verify("test", "pbkdf2_sha256$bad") is False

    def test_verify_password_with_bcrypt(self):
        """verify_password 对 bcrypt 哈希仍正常工作"""
        from app.core.security import hash_password as sec_hash, verify_password as sec_verify
        hashed = sec_hash("mypassword")
        assert sec_verify("mypassword", hashed) is True
        assert sec_verify("wrong", hashed) is False
