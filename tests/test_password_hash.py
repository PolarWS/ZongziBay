"""
PBKDF2-SHA256 密码哈希模块单元测试
覆盖：hash_password、verify_password、is_password_hash、PasswordHash 编解码
"""
import pytest

from app.core.password_hash import (
    PasswordHash,
    _parse_hash,
    hash_password,
    is_password_hash,
    verify_password,
)


class TestPasswordHashEncode:
    """PasswordHash 编码为 pbkdf2_sha256$iterations$salt$digest 格式"""

    def test_encode_format(self):
        ph = PasswordHash(
            scheme="pbkdf2_sha256",
            iterations=310000,
            salt_b64="abc123",
            digest_b64="xyz789",
        )
        encoded = ph.encode()
        assert encoded == "pbkdf2_sha256$310000$abc123$xyz789"

    def test_encode_iterations_int(self):
        ph = PasswordHash("pbkdf2_sha256", 100000, "salt", "digest")
        assert "$100000$" in ph.encode()


class TestHashPassword:
    """hash_password：明文 → pbkdf2_sha256$... 格式"""

    def test_returns_correct_scheme(self):
        h = hash_password("test123")
        assert h.startswith("pbkdf2_sha256$")
        assert h.count("$") == 3

    def test_default_iterations(self):
        h = hash_password("password")
        parts = h.split("$")
        assert int(parts[1]) == 310000

    def test_custom_iterations(self):
        h = hash_password("pwd", iterations=100000)
        parts = h.split("$")
        assert int(parts[1]) == 100000

    def test_with_salt_b64(self):
        import base64, secrets
        salt = secrets.token_bytes(16)
        # hash_password 解码 salt_b64 时需要标准 padding
        salt_b64 = base64.urlsafe_b64encode(salt).decode("utf-8")
        h = hash_password("pwd", salt_b64=salt_b64)
        # 输出中 salt 不含 =
        assert salt_b64.rstrip("=") in h

    def test_empty_password_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            hash_password("")

    def test_none_password_raises(self):
        with pytest.raises(ValueError):
            hash_password(None)

    def test_deterministic_with_same_salt(self):
        import base64, secrets
        salt = secrets.token_bytes(16)
        salt_b64 = base64.urlsafe_b64encode(salt).decode("utf-8")
        h1 = hash_password("abc", salt_b64=salt_b64)
        h2 = hash_password("abc", salt_b64=salt_b64)
        assert h1 == h2

    def test_different_salts_different_outputs(self):
        h1 = hash_password("abc")
        h2 = hash_password("abc")
        # 不同盐值 → 不同输出（概率极高）
        assert h1 != h2


class TestVerifyPassword:
    """verify_password：验证密码与哈希匹配"""

    def test_correct_password(self):
        h = hash_password("correct")
        assert verify_password("correct", h) is True

    def test_wrong_password(self):
        h = hash_password("correct")
        assert verify_password("wrong", h) is False

    def test_empty_stored_returns_false(self):
        assert verify_password("anything", "") is False

    def test_none_stored_returns_false(self):
        assert verify_password("anything", None) is False

    def test_none_password_returns_false(self):
        h = hash_password("pwd")
        assert verify_password(None, h) is False

    def test_plaintext_fallback(self):
        """明文存储时做常量时间比对（兼容旧数据）"""
        assert verify_password("admin", "admin") is True
        assert verify_password("admin", "wrong") is False

    def test_invalid_hash_format_falls_back_to_plaintext(self):
        """非 pbkdf2_sha256$ 格式回退到明文比对"""
        assert verify_password("hello", "hello") is True
        assert verify_password("hello", "world") is False

    def test_unicode_password(self):
        pwd = "密码测试123!@#"
        h = hash_password(pwd)
        assert verify_password(pwd, h) is True

    def test_long_password(self):
        pwd = "a" * 200
        h = hash_password(pwd)
        assert verify_password(pwd, h) is True


class TestParseHash:
    """_parse_hash：解析存储的哈希字符串"""

    def test_valid_hash(self):
        h = hash_password("test")
        parsed = _parse_hash(h)
        assert parsed is not None
        assert parsed.scheme == "pbkdf2_sha256"
        assert parsed.iterations == 310000
        assert len(parsed.salt_b64) > 0
        assert len(parsed.digest_b64) > 0

    def test_wrong_scheme(self):
        assert _parse_hash("argon2$100$salt$digest") is None

    def test_too_few_parts(self):
        assert _parse_hash("only$two") is None

    def test_too_many_parts(self):
        assert _parse_hash("a$b$c$d$e") is None

    def test_non_string_returns_none(self):
        assert _parse_hash(12345) is None
        assert _parse_hash(None) is None

    def test_negative_iterations(self):
        assert _parse_hash("pbkdf2_sha256$-1$salt$digest") is None

    def test_non_int_iterations(self):
        assert _parse_hash("pbkdf2_sha256$abc$salt$digest") is None

    def test_empty_salt_or_digest(self):
        assert _parse_hash("pbkdf2_sha256$100$" + "$digest") is None
        assert _parse_hash("pbkdf2_sha256$100$salt$") is None


class TestIsPasswordHash:
    """is_password_hash：判断字符串是否为 PBKDF2 哈希"""

    def test_valid_hash(self):
        h = hash_password("test")
        assert is_password_hash(h) is True

    def test_plain_text(self):
        assert is_password_hash("admin") is False
        assert is_password_hash("password123") is False

    def test_empty_string(self):
        assert is_password_hash("") is False

    def test_bcrypt_hash(self):
        """bcrypt 格式不被 is_password_hash 识别（属于另一个模块）"""
        assert is_password_hash("$2b$12$abc123def456ghi789jkl012mnop345") is False
