import logging
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import config
from app.core.rate_limiter import login_rate_limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_access_token_expire_minutes,
    get_current_user,
    hash_password,
    is_hashed,
    verify_password,
)
from app.schemas.auth import Token, TokenData
from app.schemas.base import BaseResponse, BusinessException, ErrorCode

router = APIRouter()
logger = logging.getLogger(__name__)

# Cookie 安全配置
_COOKIE_HTTP_ONLY = True
_COOKIE_SECURE = False  # 开发环境不强制 HTTPS，生产环境通过反向代理处理
_COOKIE_SAMESITE = "lax"
_COOKIE_PATH = "/api"


def _set_access_token_cookie(response: Response, token: str) -> None:
    """在响应中设置 httpOnly Cookie 存储 Access Token"""
    max_age = get_access_token_expire_minutes() * 60
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=max_age,
        httponly=_COOKIE_HTTP_ONLY,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
    )


def _set_refresh_token_cookie(response: Response, token: str) -> None:
    """在响应中设置 httpOnly Cookie 存储 Refresh Token"""
    # Refresh Token 过期时间从 security.py 读取，默认 7 天
    refresh_days = int(config.get("security.refresh_token_expire_days", 7) or 7)
    max_age = refresh_days * 24 * 60 * 60
    response.set_cookie(
        key="refresh_token",
        value=token,
        max_age=max_age,
        httponly=_COOKIE_HTTP_ONLY,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    """清除认证相关的 Cookie"""
    response.delete_cookie(
        key="access_token",
        httponly=_COOKIE_HTTP_ONLY,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
    )
    response.delete_cookie(
        key="refresh_token",
        httponly=_COOKIE_HTTP_ONLY,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
    )


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP，优先从 X-Forwarded-For 头获取（适配反向代理）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=BaseResponse[Token], summary="用户登录接口")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """用户登录并获取 Access Token。返回 httpOnly Cookie 和响应体中的 Token。"""
    # 登录限流检查
    client_ip = _get_client_ip(request)
    allowed, limit_msg = login_rate_limiter.check(client_ip)
    if not allowed:
        raise BusinessException(code=ErrorCode.RATE_LIMIT_ERROR, message=limit_msg)

    conf_username = config.get("security.username")
    conf_password = config.get("security.password")

    logger.info(f"登录尝试: username={form_data.username}, config_username={conf_username}, password_len={len(form_data.password)}, config_password_is_hashed={is_hashed(conf_password or '')}")

    # 使用 bcrypt 验证密码（后续前端均已做 SHA-256，此处直接做 bcrypt 校验）
    if form_data.username != conf_username or not verify_password(form_data.password, conf_password or ""):
        logger.warning(f"登录失败: username_match={form_data.username == conf_username}")
        raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="用户名或密码错误")

    # 如果文件中的密码是明文（非环境变量注入），自动升级为 bcrypt 哈希
    file_cfg = config.get_file_config()
    file_password = (file_cfg.get("security") or {}).get("password", "")
    if file_password and not is_hashed(file_password):
        try:
            file_cfg.setdefault("security", {})
            file_cfg["security"]["password"] = hash_password(form_data.password)
            config.save_file_config(file_cfg)
            logger.info("密码已从明文升级为 bcrypt 哈希")
        except Exception:
            logger.warning("密码哈希升级失败，将在下次登录时重试", exc_info=True)

    access_token_expires = timedelta(minutes=get_access_token_expire_minutes())
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": form_data.username})

    # 设置 httpOnly Cookie
    _set_access_token_cookie(response, access_token)
    _set_refresh_token_cookie(response, refresh_token)

    token_data = Token(access_token=access_token, token_type="bearer")
    return BaseResponse.success(data=token_data)


@router.post("/refresh", response_model=BaseResponse[Token], summary="刷新 Access Token")
async def refresh_access_token(
    response: Response,
    refresh_token: str = Cookie(default=None, alias="refresh_token"),
):
    """使用 Refresh Token 获取新的 Access Token。
    从 httpOnly Cookie 中读取 refresh_token 进行验证。"""
    if not refresh_token:
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="未提供 Refresh Token")

    payload = decode_refresh_token(refresh_token)
    if payload is None:
        _clear_auth_cookies(response)
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="Refresh Token 无效或已过期")

    username = payload.get("sub")
    if not username or username != config.get("security.username"):
        _clear_auth_cookies(response)
        raise BusinessException(code=ErrorCode.NOT_LOGIN_ERROR, message="无效的凭证")

    # 签发新的 Access Token
    access_token_expires = timedelta(minutes=get_access_token_expire_minutes())
    new_access_token = create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )
    _set_access_token_cookie(response, new_access_token)

    return BaseResponse.success(data=Token(access_token=new_access_token, token_type="bearer"))


@router.post("/logout", response_model=BaseResponse, summary="用户登出接口")
async def logout(
    response: Response,
    current_user: TokenData = Depends(get_current_user),
):
    """用户登出：清除 httpOnly Cookie 中的 Token"""
    _clear_auth_cookies(response)
    return BaseResponse.success(data="登出成功")


@router.get("/me", response_model=BaseResponse, summary="获取当前用户信息")
async def read_users_me(current_user: TokenData = Depends(get_current_user)):
    """获取当前登录用户信息（需携带 httpOnly Cookie 或 Authorization: Bearer <token>）"""
    return BaseResponse.success(data={"username": current_user.username})
