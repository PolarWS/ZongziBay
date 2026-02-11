from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import config
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
)
from app.schemas.auth import Token, TokenData
from app.schemas.base import BaseResponse, BusinessException, ErrorCode

router = APIRouter()


@router.post("/login", response_model=BaseResponse[Token], summary="用户登录接口")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录并获取 Access Token"""
    conf_username = config.get("security.username")
    conf_password = config.get("security.password")
    if form_data.username != conf_username or form_data.password != conf_password:
        raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="用户名或密码错误")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    token_data = Token(access_token=access_token, token_type="bearer")
    return BaseResponse.success(data=token_data)


@router.post("/logout", response_model=BaseResponse, summary="用户登出接口")
async def logout(current_user: TokenData = Depends(get_current_user)):
    """用户登出（JWT 无状态，客户端丢弃 Token 即可）"""
    return BaseResponse.success(data="登出成功")


@router.get("/me", response_model=BaseResponse, summary="获取当前用户信息")
async def read_users_me(current_user: TokenData = Depends(get_current_user)):
    """获取当前登录用户信息（需携带 Authorization: Bearer <token>）"""
    return BaseResponse.success(data={"username": current_user.username})
