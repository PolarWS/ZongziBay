from fastapi import APIRouter

from app.core.config import config
from app.schemas.base import BaseResponse

router = APIRouter()


@router.get("/paths", response_model=BaseResponse)
async def get_path_config():
    """获取系统路径配置（下载路径、归档路径等）"""
    paths = config.get("paths", {})
    return BaseResponse.success(data=paths)
