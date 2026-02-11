from enum import Enum
from typing import Any, Generic, Optional, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T")


class ErrorCode(Enum):
    """错误码枚举"""
    SUCCESS = (0, "ok")
    PARAMS_ERROR = (40000, "请求参数错误")
    NOT_LOGIN_ERROR = (40100, "未登录")
    NO_AUTH_ERROR = (40101, "无权限")
    NOT_FOUND_ERROR = (40400, "请求数据不存在")
    FORBIDDEN_ERROR = (40300, "禁止访问")
    SYSTEM_ERROR = (50000, "系统内部异常")
    OPERATION_ERROR = (50001, "操作失败")

    def __init__(self, code: int, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> int:
        return self._code

    @property
    def message(self) -> str:
        return self._message


class BaseResponse(BaseModel, Generic[T]):
    """统一 API 响应结构"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

    @classmethod
    def success(cls, data: T = None, message: str = "success"):
        """构造成功响应"""
        return cls(code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: Union[int, Any] = 400, message: str = "fail", data: Any = None):
        """构造失败响应"""
        if isinstance(code, ErrorCode):
            return cls(code=code.code, message=message if message != "fail" else code.message, data=data)
        return cls(code=code, message=message, data=data)


class BusinessException(Exception):
    """业务异常，由全局异常处理器转换为 BaseResponse"""
    def __init__(self, error: Union[ErrorCode, int] = None, message: Optional[str] = None, data: Any = None, code: Union[int, ErrorCode] = None):
        actual_code = code if code is not None else error
        actual_message = message if message is not None else "fail"
        if actual_code is None:
            actual_code = ErrorCode.SYSTEM_ERROR
        response = BaseResponse.fail(code=actual_code, message=actual_message, data=data)
        self.code = response.code
        self.message = response.message
        self.data = response.data
        super().__init__(self.message)
