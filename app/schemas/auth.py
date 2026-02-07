from typing import Optional
from pydantic import BaseModel

class Token(BaseModel):
    """
    Token 响应模型
    用于登录接口返回 Access Token
    """
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    Token 数据模型
    用于解析 Token 中的用户信息
    """
    username: Optional[str] = None
