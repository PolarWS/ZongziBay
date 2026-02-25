import asyncio
import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import config
from app.core.security import SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)

# =====================================================================
# 放行白名单：无需 JWT 认证的接口路径
# 后续需要放行新接口时，在此列表中添加即可
# 支持精确匹配和前缀匹配（路径本身及其子路径均放行）
# 例如: "/api/v1/health" 会同时放行 /api/v1/health 和 /api/v1/health/xxx
# =====================================================================
AUTH_WHITELIST = [
    "/api/v1/users/login",    # 登录接口
    "/api/v1/health",          # 健康检查
]


def _verify_token_sync(token: str) -> Optional[str]:
    """同步校验 JWT，在线程池中调用以避免阻塞事件循环。返回 username 或 None。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username or username != config.get("security.username"):
            return None
        return username
    except JWTError:
        return None


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    全局 JWT 认证中间件
    - 仅拦截 /api/ 开头的请求
    - 白名单中的路径无需认证，直接放行
    - 其余 API 请求必须携带有效的 Bearer Token
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")

        # 非 API 路径直接放行（静态文件、前端页面、Swagger 文档等）
        if not path.startswith("/api/"):
            return await call_next(request)

        # OPTIONS 预检请求直接放行（配合 CORS 中间件）
        if request.method == "OPTIONS":
            return await call_next(request)

        # 白名单路径直接放行
        for wp in AUTH_WHITELIST:
            wp_clean = wp.rstrip("/")
            if path == wp_clean or path.startswith(wp_clean + "/"):
                return await call_next(request)

        # 提取 Authorization 头
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._unauthorized("未登录，请先登录")

        token = auth_header[len("Bearer "):]
        username = await asyncio.to_thread(_verify_token_sync, token)
        if username is None:
            return self._unauthorized("无效的凭证")

        return await call_next(request)

    @staticmethod
    def _unauthorized(message: str) -> JSONResponse:
        """返回统一的未认证响应（与 BaseResponse 格式一致，code=40100）"""
        return JSONResponse(
            status_code=200,
            content={"code": 40100, "message": message, "data": None}
        )
