import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Optional


_SCHEME = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 310_000
_SALT_BYTES = 16


@dataclass(frozen=True)
class PasswordHash:
    scheme: str
    iterations: int
    salt_b64: str
    digest_b64: str

    def encode(self) -> str:
        return f"{self.scheme}${self.iterations}${self.salt_b64}${self.digest_b64}"


def hash_password(password: str, *, iterations: int = _DEFAULT_ITERATIONS, salt_b64: Optional[str] = None) -> str:
    """将明文密码转换为可存储的哈希字符串（PBKDF2-HMAC-SHA256）。"""
    if not isinstance(password, str) or not password:
        raise ValueError("password 不能为空")
    if salt_b64:
        salt = base64.urlsafe_b64decode(salt_b64.encode("utf-8"))
    else:
        salt = secrets.token_bytes(_SALT_BYTES)
        salt_b64 = base64.urlsafe_b64encode(salt).decode("utf-8").rstrip("=")

    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    digest_b64 = base64.urlsafe_b64encode(dk).decode("utf-8").rstrip("=")
    return PasswordHash(_SCHEME, int(iterations), salt_b64, digest_b64).encode()


def _parse_hash(encoded: str) -> Optional[PasswordHash]:
    if not isinstance(encoded, str):
        return None
    parts = encoded.split("$")
    if len(parts) != 4:
        return None
    scheme, iters_s, salt_b64, digest_b64 = parts
    if scheme != _SCHEME:
        return None
    try:
        iters = int(iters_s)
        if iters <= 0:
            return None
    except Exception:
        return None
    if not salt_b64 or not digest_b64:
        return None
    return PasswordHash(scheme, iters, salt_b64, digest_b64)


def verify_password(password: str, stored: str) -> bool:
    """验证输入密码是否匹配配置中的存储值（支持明文与 pbkdf2_sha256$...）。"""
    if not isinstance(password, str) or not isinstance(stored, str):
        return False

    parsed = _parse_hash(stored)
    if not parsed:
        return hmac.compare_digest(password, stored)

    # urlsafe base64 可能缺少 padding
    def _pad(b64: str) -> str:
        return b64 + "=" * ((4 - len(b64) % 4) % 4)

    try:
        salt = base64.urlsafe_b64decode(_pad(parsed.salt_b64).encode("utf-8"))
        expected = base64.urlsafe_b64decode(_pad(parsed.digest_b64).encode("utf-8"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, parsed.iterations)
    return hmac.compare_digest(actual, expected)


def is_password_hash(value: str) -> bool:
    """判断字符串是否为受支持的密码哈希格式。"""
    return _parse_hash(value) is not None
