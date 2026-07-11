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


def _truncate_password(password: str) -> bytes:
    """bcrypt 最多处理 72 字节，截断超长密码并编码为 UTF-8"""
    return password.encode("utf-8")[:72]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码：支持 bcrypt 哈希和明文回退（兼容旧数据）"""
    if not hashed_password:
        return False
    # bcrypt 哈希以 $2b$ 或 $2a$ 开头
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
        try:
            return bcrypt.checkpw(
                _truncate_password(plain_password),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False
    # 回退：明文比对（用于旧数据的平滑升级）
    return plain_password == hashed_password


def hash_password(plain_password: str) -> str:
    """使用 bcrypt 哈希密码，自动截断超过 72 字节的密码"""
    return bcrypt.hashpw(
        _truncate_password(plain_password),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("utf-8")


def is_hashed(encoded: str) -> bool:
    """判断字符串是否已经是 bcrypt 哈希值"""
    return encoded.startswith("$2b$") or encoded.startswith("$2a$")


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
