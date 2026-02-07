from fastapi import APIRouter
from app.schemas.base import BaseResponse

router = APIRouter()

@router.get("", response_model=BaseResponse, summary="服务健康检查")
async def health_check():
    """
    健康检查接口
    返回服务运行状态
    """
    return BaseResponse.success(message="ok")
