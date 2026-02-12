import asyncio

from fastapi import APIRouter

from app.schemas.base import BaseResponse, BusinessException, ErrorCode
from app.schemas.magnet import MagnetDownloadRequest, MagnetParseResponse, MagnetRequest
from app.services.magnet_service import magnet_service

router = APIRouter()


@router.post("/parse", response_model=BaseResponse[MagnetParseResponse], summary="解析 Magnet 链接")
async def parse_magnet(request: MagnetRequest):
    """通过 Magnet 链接获取文件列表（在线程池执行，不阻塞其他 API）"""
    try:
        files = await asyncio.to_thread(magnet_service.parse_magnet, request.magnet_link)
        return BaseResponse.success(data={"files": files})
    except ValueError:
        return BaseResponse.fail(code=ErrorCode.PARAMS_ERROR, message="无效的 Magnet 链接")
    except BusinessException as e:
        return BaseResponse.fail(code=e.code, message=e.message)
    except Exception as e:
        if "元数据超时" in str(e) or isinstance(e, TimeoutError):
            return BaseResponse.fail(code=ErrorCode.OPERATION_ERROR, message="等待元数据超时")
        raise


@router.get("/check", response_model=BaseResponse[bool], summary="检查 qBittorrent 连接")
async def check_connection():
    """检查是否能成功连接到配置的 qBittorrent 服务"""
    success = await asyncio.to_thread(magnet_service.check_connection)
    if success:
        return BaseResponse.success(data=True, message="连接成功")
    return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="无法连接到 qBittorrent 服务", data=False)


@router.post("/download", response_model=BaseResponse[dict], summary="推送 Magnet 链接到 qBittorrent 下载")
async def download_magnet(request: MagnetDownloadRequest):
    """推送 Magnet 链接到 qBittorrent 下载（在线程池执行，不阻塞其他 API）"""
    try:
        result = await asyncio.to_thread(
            magnet_service.add_magnet_download,
            request.magnet_link,
            request.save_path,
        )
        return BaseResponse.success(data=result)
    except BusinessException as e:
        return BaseResponse.fail(code=e.code, message="添加磁力链接失败")
    except Exception as e:
        return BaseResponse.fail(code=ErrorCode.OPERATION_ERROR, message="操作失败")
