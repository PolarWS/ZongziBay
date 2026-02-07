from fastapi import APIRouter
from app.services.magnet_service import magnet_service
from app.schemas.magnet import MagnetParseResponse, MagnetRequest, MagnetDownloadRequest
from app.schemas.base import BaseResponse, ErrorCode, BusinessException

router = APIRouter()

@router.post("/parse", response_model=BaseResponse[MagnetParseResponse], summary="解析 Magnet 链接")
async def parse_magnet(request: MagnetRequest):
    """
    通过 Magnet 链接获取文件列表。

    - **magnet_link**: 磁力链接地址

    返回:
    - **files**: 文件列表，包含文件名和大小
    """
    try:
        files = magnet_service.parse_magnet(request.magnet_link)
        return BaseResponse.success(data={"files": files})
    except ValueError as e:
        return BaseResponse.fail(code=ErrorCode.PARAMS_ERROR, message="无效的 Magnet 链接")
    except TimeoutError as e:
        return BaseResponse.fail(code=ErrorCode.OPERATION_ERROR, message="等待元数据超时")

@router.get("/check", response_model=BaseResponse[bool], summary="检查 qBittorrent 连接")
async def check_connection():
    """
    检查是否能成功连接到配置的 qBittorrent 服务。
    """
    success = magnet_service.check_connection()
    if success:
        return BaseResponse.success(data=True, message="连接成功")
    else:
        return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="无法连接到 qBittorrent 服务", data=False)

@router.post("/download", response_model=BaseResponse[dict], summary="推送 Magnet 链接到 qBittorrent 下载")
async def download_magnet(request: MagnetDownloadRequest):
    """
    推送 Magnet 链接到 qBittorrent 下载
    
    - **magnet_link**: 磁力链接地址
    - **save_path**: 下载存放路径（可选）
    - **start_immediately**: 是否立即开始下载（默认 True）
    """
    try:
        result = magnet_service.add_magnet_download(
            magnet_link=request.magnet_link,
            save_path=request.save_path,
        )
        return BaseResponse.success(data=result)
    except BusinessException as e:
        return BaseResponse.fail(code=e.code, message="添加磁力链接失败")
    except Exception as e:
        return BaseResponse.fail(code=ErrorCode.OPERATION_ERROR, message="操作失败")
