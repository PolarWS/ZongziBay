"""
异常处理器单元测试
覆盖：BusinessException → BaseResponse、参数校验异常、HTTP 异常、全局兜底
使用 mock Request 测试处理器返回值
"""
import json
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.handlers import (
    business_exception_handler,
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.schemas.base import BaseResponse, BusinessException, ErrorCode


@pytest.fixture
def mock_request():
    """构造 mock Request（处理器中仅用于日志，不直接访问 request 属性）"""
    req = MagicMock(spec=Request)
    return req


class TestBusinessExceptionHandler:
    """business_exception_handler：业务异常 → BaseResponse JSON"""

    @pytest.mark.asyncio
    async def test_params_error(self, mock_request):
        exc = BusinessException(error=ErrorCode.PARAMS_ERROR, message="缺少字段")
        resp = await business_exception_handler(mock_request, exc)
        assert resp.status_code == 200
        body = _json_body(resp)
        assert body["code"] == 40000
        assert "缺少字段" in body["message"]

    @pytest.mark.asyncio
    async def test_not_login_error(self, mock_request):
        exc = BusinessException(error=ErrorCode.NOT_LOGIN_ERROR)
        resp = await business_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert body["code"] == 40100

    @pytest.mark.asyncio
    async def test_system_error(self, mock_request):
        exc = BusinessException(error=ErrorCode.SYSTEM_ERROR)
        resp = await business_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert body["code"] == 50000

    @pytest.mark.asyncio
    async def test_with_data(self, mock_request):
        exc = BusinessException(error=ErrorCode.PARAMS_ERROR, data=["error1", "error2"])
        resp = await business_exception_handler(mock_request, exc)
        body = _json_body(resp)
        # handler 只传递 code + message，不传递 data（data 保留在 exc.data 上）
        assert body["code"] == 40000
        assert exc.data == ["error1", "error2"]


class TestValidationExceptionHandler:
    """validation_exception_handler：RequestValidationError → BaseResponse"""

    @pytest.mark.asyncio
    async def test_missing_field(self, mock_request):
        from pydantic import BaseModel, ValidationError as PydanticValidationError

        class TestModel(BaseModel):
            name: str
            age: int

        try:
            TestModel()
        except PydanticValidationError as e:
            # FastAPI 将 pydantic ValidationError 包装为 RequestValidationError
            exc = RequestValidationError(errors=e.errors())
            resp = await validation_exception_handler(mock_request, exc)
            body = _json_body(resp)
            assert body["code"] == 40000
            assert "参数校验" in body["message"]
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    async def test_type_error(self, mock_request):
        errors = [
            {
                "loc": ["body", "age"],
                "msg": "value is not a valid integer",
                "type": "type_error.integer",
            }
        ]
        exc = RequestValidationError(errors=errors)
        resp = await validation_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert body["code"] == 40000
        assert len(body["data"]) == 1

    @pytest.mark.asyncio
    async def test_multiple_errors(self, mock_request):
        errors = [
            {"loc": ["body", "name"], "msg": "field required", "type": "missing"},
            {"loc": ["body", "email"], "msg": "not a valid email", "type": "type_error"},
        ]
        exc = RequestValidationError(errors=errors)
        resp = await validation_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert len(body["data"]) == 2


class TestHTTPExceptionHandler:
    """http_exception_handler：StarletteHTTPException → BaseResponse"""

    @pytest.mark.asyncio
    async def test_404(self, mock_request):
        exc = StarletteHTTPException(status_code=404, detail="Not Found")
        resp = await http_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert body["code"] == 404
        assert "Not Found" in body["message"]

    @pytest.mark.asyncio
    async def test_405(self, mock_request):
        exc = StarletteHTTPException(status_code=405, detail="Method Not Allowed")
        resp = await http_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert body["code"] == 405


class TestGlobalExceptionHandler:
    """global_exception_handler：未处理异常 → 50000 系统错误"""

    @pytest.mark.asyncio
    async def test_generic_exception(self, mock_request):
        exc = ValueError("something went wrong")
        resp = await global_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert body["code"] == 50000
        assert "内部错误" in body["message"]

    @pytest.mark.asyncio
    async def test_runtime_error(self, mock_request):
        exc = RuntimeError("unexpected")
        resp = await global_exception_handler(mock_request, exc)
        body = _json_body(resp)
        assert body["code"] == 50000


def _json_body(resp) -> dict:
    """从 FastAPI/Starlette Response 中解析 JSON body"""
    return json.loads(resp.body.decode("utf-8"))
