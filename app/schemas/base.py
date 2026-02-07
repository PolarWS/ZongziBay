from enum import Enum
from typing import Generic, TypeVar, Optional, Any, Union
from pydantic import BaseModel

class ErrorCode(Enum):
    """
    错误码枚举
    """
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

# 定义泛型变量，用于支持 BaseResponse 中的 data 字段类型
T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    """
    统一 API 响应结构
    
    Attributes:
        code (int): 业务状态码，默认 200 表示成功
        message (str): 提示信息，默认 "success"
        data (Optional[T]): 返回的数据，支持泛型
    """
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

    @classmethod
    def success(cls, data: T = None, message: str = "success"):
        """
        快速构造成功响应
        
        Args:
            data: 返回的数据对象
            message: 成功提示信息
            
        Returns:
            BaseResponse: 填充了成功状态和数据的响应对象
        """
        return cls(code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: Union[int, Any] = 400, message: str = "fail", data: Any = None):
        """
        快速构造失败响应
        
        Args:
            code: 错误状态码
            message: 错误提示信息
            data: 附加的错误数据（可选）
            
        Returns:
            BaseResponse: 填充了错误状态和信息的响应对象
        """
        if isinstance(code, ErrorCode):
            return cls(code=code.code, message=message if message != "fail" else code.message, data=data)
        return cls(code=code, message=message, data=data)

class BusinessException(Exception):
    """
    自定义业务异常类
    用于在业务逻辑中主动抛出可预期的错误，由全局异常处理器统一捕获并转换为标准响应。
    """
    def __init__(self, error: Union[ErrorCode, int] = None, message: Optional[str] = None, data: Any = None, code: Union[int, ErrorCode] = None):
        """
        构造函数
        """
        # 确定主要的 code 参数
        actual_code = code if code is not None else error
        
        # 默认使用 "fail" 作为 message 传递给 BaseResponse.fail
        actual_message = message if message is not None else "fail"

        if actual_code is None:
            actual_code = ErrorCode.SYSTEM_ERROR

        response = BaseResponse.fail(code=actual_code, message=actual_message, data=data)
            
        self.code = response.code
        self.message = response.message
        self.data = response.data
        super().__init__(self.message)
