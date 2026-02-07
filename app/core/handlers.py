import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.schemas.base import BaseResponse, BusinessException, ErrorCode

logger = logging.getLogger(__name__)

async def business_exception_handler(request: Request, exc: BusinessException):
    """
    业务异常处理器
    捕获 BusinessException 并将其转换为标准的 BaseResponse JSON 格式。
    注意：HTTP 状态码通常保持为 200，具体错误通过响应体中的 code 字段区分。
    """
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=exc.code, message=exc.message))
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    参数校验异常处理器
    捕获 FastAPI/Pydantic 的数据校验错误 (RequestValidationError)。
    """
    errors = []
    for error in exc.errors():
        # 格式化错误位置和信息，例如 "body.price: field required"
        errors.append(f"{'.'.join([str(x) for x in error['loc']])}: {error['msg']}")
    
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=ErrorCode.PARAMS_ERROR.code, message="参数校验错误", data=errors))
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    HTTP 异常处理器
    捕获 404 Not Found, 401 Unauthorized 等标准 HTTP 异常。
    将默认的 {"detail": "Not Found"} 转换为标准格式。
    """
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=exc.status_code, message=str(exc.detail)))
    )

async def global_exception_handler(request: Request, exc: Exception):
    """
    全局兜底异常处理器
    捕获所有未被其他处理器捕获的异常（如代码 bug、数据库连接失败等）。
    防止服务器内部错误细节直接暴露给客户端，统一返回 500 错误。
    建议在此处添加日志记录功能。
    """
    logger.error(f"服务器内部错误: {exc}", exc_info=True)
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR.code, message="服务器内部错误"))
    )

def register_exception_handlers(app: FastAPI):
    """
    注册所有异常处理器到 FastAPI 应用实例
    
    Args:
        app: FastAPI 应用实例
    """
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler) # 注册 HTTP 异常处理器
    app.add_exception_handler(Exception, global_exception_handler)
