from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import config
from app.schemas.auth import TokenData
from app.schemas.base import BusinessException, ErrorCode

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def get_secret_key() -> str:
    return config.get("security.secret_key", "CHANGE_THIS_SECRET_KEY")


def get_algorithm() -> str:
    return config.get("security.algorithm", "HS256")


def get_access_token_expire_minutes() -> int:
    return int(config.get("security.access_token_expire_minutes", 30) or 30)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT Access Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=get_access_token_expire_minutes())
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=get_algorithm())
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """解析 Token 并返回当前用户，用于保护需认证的接口"""
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
        username: str = payload.get("sub")
        if username is None:
            raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
        token_data = TokenData(username=username)
    except JWTError:
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")

    if username != config.get("security.username"):
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
    return token_data
