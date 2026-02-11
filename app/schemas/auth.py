from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """登录接口返回的 Access Token"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token 解析后的用户信息"""
    username: Optional[str] = None
