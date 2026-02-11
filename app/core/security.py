from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import config
from app.schemas.auth import TokenData
from app.schemas.base import BusinessException, ErrorCode

SECRET_KEY = config.get("security.secret_key", "CHANGE_THIS_SECRET_KEY")
ALGORITHM = config.get("security.algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = config.get("security.access_token_expire_minutes", 30)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT Access Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """解析 Token 并返回当前用户，用于保护需认证的接口"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
        token_data = TokenData(username=username)
    except JWTError:
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")

    if username != config.get("security.username"):
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
    return token_data
