from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import config
from app.schemas.auth import TokenData
from app.schemas.base import BusinessException, ErrorCode

SECRET_KEY = config.get("security.secret_key", "CHANGE_THIS_SECRET_KEY")
ALGORITHM = config.get("security.algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = config.get("security.access_token_expire_minutes", 30)

# OAuth2 密码模式
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    生成 JWT Access Token
    
    Args:
        data (dict): 需要加密到 Token 中的数据（Payload）
        expires_delta (Optional[timedelta]): 过期时间增量
        
    Returns:
        str: 加密后的 Token 字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 添加过期时间 claim
    to_encode.update({"exp": expire})
    
    # 使用指定算法和密钥进行编码
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    获取当前登录用户依赖函数
    用于保护需要认证的接口，验证 Token 有效性并解析用户信息
    
    Args:
        token (str): 请求头中的 Bearer Token
        
    Returns:
        TokenData: 解析后的用户数据
        
    Raises:
        BusinessException: 认证失败
    """
    try:
        # 解码 Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
        token_data = TokenData(username=username)
    except JWTError:
        # Token 格式错误或签名无效
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
    
    # 验证用户是否存在（这里简单比对配置文件中的用户名）
    # 实际项目中应查询数据库
    if username != config.get("security.username"):
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")
        
    return token_data
