import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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


def register_exception_handlers(app: FastAPI):
    """注册所有异常处理器到 FastAPI 应用"""
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
