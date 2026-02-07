from datetime import timedelta
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from app.schemas.base import BaseResponse, BusinessException, ErrorCode
from app.schemas.auth import Token, TokenData
from app.core.security import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.config import config

router = APIRouter()

@router.post("/login", response_model=BaseResponse[Token], summary="用户登录接口")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    用户登录并获取 Access Token
    
    - **username**: 用户名 (从 config.yml 配置中读取)
    - **password**: 密码 (从 config.yml 配置中读取)
    """
    # 从配置文件读取用户名和密码
    conf_username = config.get("security.username")
    conf_password = config.get("security.password")
    
    # 验证用户名和密码
    if form_data.username != conf_username or form_data.password != conf_password:
        # 认证失败
        raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="用户名或密码错误")
    
    # 计算 Token 过期时间
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 生成 Access Token
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    
    # 返回 Token 和类型
    token_data = Token(access_token=access_token, token_type="bearer")
    return BaseResponse.success(data=token_data)

@router.post("/logout", response_model=BaseResponse, summary="用户登出接口")
async def logout(current_user: TokenData = Depends(get_current_user)):
    """
    用户登出
    
    注意：JWT 是无状态的，服务端无法强制使 Token 失效。
    通常由客户端丢弃 Token 即可。
    如果需要强制失效，需配合 Redis 黑名单机制。
    """
    return BaseResponse.success(data="登出成功")

@router.get("/me", response_model=BaseResponse, summary="获取当前用户信息")
async def read_users_me(current_user: TokenData = Depends(get_current_user)):
    """
    获取当前登录用户的详细信息
    
    需要 Header 中携带 Authorization: Bearer <token>
    """
    return BaseResponse.success(data={"username": current_user.username})
