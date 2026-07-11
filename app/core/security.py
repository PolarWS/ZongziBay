import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import config
from app.schemas.auth import TokenData
from app.schemas.base import BusinessException, ErrorCode

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login", auto_error=False)

# bcrypt 轮次数
_BCRYPT_ROUNDS = 12

# PBKDF2 方案标识（兼容旧版本 v1.0.0-rc.6 及之前）
_PBKDF2_SCHEME = "pbkdf2_sha256"


def _truncate_password(password: str) -> bytes:
    """bcrypt 最多处理 72 字节，截断超长密码并编码为 UTF-8"""
    return password.encode("utf-8")[:72]


def _parse_pbkdf2_hash(encoded: str) -> Optional[tuple]:
    """解析 pbkdf2_sha256$iterations$salt$digest 格式的旧密码哈希。
    返回 (iterations, salt_bytes, digest_bytes)，解析失败返回 None。"""
    if not isinstance(encoded, str) or not encoded.startswith(_PBKDF2_SCHEME + "$"):
        return None
    parts = encoded.split("$")
    if len(parts) != 4:
        return None
    _, iters_s, salt_b64, digest_b64 = parts
    try:
        iters = int(iters_s)
        if iters <= 0:
            return None
    except Exception:
        return None

    def _pad(b64: str) -> str:
        return b64 + "=" * ((4 - len(b64) % 4) % 4)

    try:
        salt = base64.urlsafe_b64decode(_pad(salt_b64).encode("utf-8"))
        digest = base64.urlsafe_b64decode(_pad(digest_b64).encode("utf-8"))
    except Exception:
        return None
    return (iters, salt, digest)


def is_pbkdf2_hash(encoded: str) -> bool:
    """判断字符串是否为旧版 PBKDF2-SHA256 哈希格式"""
    return _parse_pbkdf2_hash(encoded) is not None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码：支持 bcrypt 哈希、旧版 PBKDF2 哈希、明文回退（兼容历史数据）"""
    if not hashed_password:
        return False

    # 1. bcrypt 哈希以 $2b$ 或 $2a$ 开头
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
        try:
            return bcrypt.checkpw(
                _truncate_password(plain_password),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    # 2. 旧版 PBKDF2-SHA256 哈希（兼容 v1.0.0-rc.6 及之前版本）
    pbkdf2 = _parse_pbkdf2_hash(hashed_password)
    if pbkdf2 is not None:
        iters, salt, expected_digest = pbkdf2
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt, iters,
        )
        return hmac.compare_digest(actual_digest, expected_digest)

    # 3. 明文比对（用于旧数据的平滑升级）
    return plain_password == hashed_password


def hash_password(plain_password: str) -> str:
    """使用 bcrypt 哈希密码，自动截断超过 72 字节的密码"""
    return bcrypt.hashpw(
        _truncate_password(plain_password),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("utf-8")


def is_hashed(encoded: str) -> bool:
    """判断字符串是否已经是密码哈希值（bcrypt 或 PBKDF2）"""
    return (
        encoded.startswith("$2b$")
        or encoded.startswith("$2a$")
        or is_pbkdf2_hash(encoded)
    )


def get_secret_key() -> str:
    return config.get("security.secret_key", "CHANGE_THIS_SECRET_KEY")


def get_algorithm() -> str:
    return config.get("security.algorithm", "HS256")


def get_access_token_expire_minutes() -> int:
    return int(config.get("security.access_token_expire_minutes", 30) or 30)


def get_refresh_token_expire_days() -> int:
    """Refresh Token 过期时间（天），默认 7 天"""
    return int(config.get("security.refresh_token_expire_days", 7) or 7)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT Access Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=get_access_token_expire_minutes())
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=get_algorithm())
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT Refresh Token（过期时间更长）"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=get_refresh_token_expire_days())
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=get_algorithm())
    return encoded_jwt


def decode_refresh_token(token: str) -> Optional[dict]:
    """验证并解码 Refresh Token，只接受 type=refresh 的 token"""
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """解析 Token 并返回当前用户，用于保护需认证的接口"""
    if not token:
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="未提供凭证")
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
        if payload.get("type") != "access":
            raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证类型")
        username: str = payload.get("sub")
        if username is None:
            raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
        token_data = TokenData(username=username)
    except JWTError:
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")

    if username != config.get("security.username"):
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
    return token_data
