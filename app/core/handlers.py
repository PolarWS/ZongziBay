import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from app.schemas.base import BaseResponse, BusinessException, ErrorCode

logger = logging.getLogger(__name__)


async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常：转为 BaseResponse JSON，HTTP 状态码保持 200"""
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=exc.code, message=exc.message))
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验异常：转为 BaseResponse JSON"""
    errors = []
    for error in exc.errors():
        errors.append(f"{'.'.join([str(x) for x in error['loc']])}: {error['msg']}")
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=ErrorCode.PARAMS_ERROR, message="参数校验错误", data=errors))
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 异常（404、401 等）：转为 BaseResponse JSON"""
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=exc.status_code, message=str(exc.detail)))
    )


async def global_exception_handler(request: Request, exc: Exception):
    """全局兜底：捕获未处理异常，记录日志并返回 500"""
    logger.error(f"服务器内部错误: {exc}", exc_info=True)
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR.code, message="服务器内部错误"))
    )


class CatchAllExceptionMiddleware:
    """兜底中间件：在异常逃出路由后立刻接住，返回统一 JSON。

    为什么不能只靠 add_exception_handler(Exception, ...)：该注册项由 Starlette 的
    ServerErrorMiddleware 承载，它在调用处理器发出响应之后**会重新抛出异常**，
    uvicorn 发现"响应已开始"便强制关闭连接，且不带 Connection: close 头。
    客户端连接池以为这条连接仍可复用，于是下一个请求直接 RemoteDisconnected——
    表现为调用方约一半请求"网络错误"，而服务端只留下一条 50000 日志。
    在中间件层接住就不会有异常继续上抛，连接得以正常复用。

    这里刻意写成**原生 ASGI 中间件**而不是 BaseHTTPMiddleware：后者会把响应包进
    自己的 _StreamingResponse 并逐块重建消息，遇到挂载在 /mcp 的 SSE 长连接时
    会因收到多次 http.response.start 而抛
    `AssertionError: Unexpected message: {'type': 'http.response.start', ...}`
    （MCP 的 202 空响应同样会踩到）。原生中间件只是旁路转发消息，流式响应不受影响。
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # 非 HTTP 作用域（lifespan / websocket）不处理
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            if response_started:
                # 响应头已下发，内容无法再改写。这类异常（例如 BaseHTTPMiddleware
                # 包装 SSE 长连接/202 空响应时的 AssertionError）交给外层记录即可，
                # 这里不再重复打一条 ERROR 日志。
                raise
            logger.error(f"服务器内部错误: {exc}", exc_info=True)
            response = JSONResponse(
                status_code=200,
                content=jsonable_encoder(
                    BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR.code, message="服务器内部错误")
                ),
            )
            await response(scope, receive, send)


def register_exception_handlers(app: FastAPI):
    """注册所有异常处理器到 FastAPI 应用"""
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    # 仍然保留兜底处理器：万一有异常没被上面那层中间件接住（例如在更外层中间件里抛出），
    # 至少还能返回统一的 JSON 结构。
    app.add_exception_handler(Exception, global_exception_handler)
