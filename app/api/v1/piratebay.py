from typing import List

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

from app.schemas.base import BaseResponse, ErrorCode
from app.schemas.piratebay import PirateBayTorrent
from app.services.piratebay_service import PirateBayService

router = APIRouter()
service = PirateBayService()


@router.get("/search", response_model=BaseResponse[List[PirateBayTorrent]], summary="搜索海盗湾")
async def search_torrents(
    q: str = Query(..., description="搜索关键词")
):
    """
    在海盗湾搜索种子资源。
    """
    try:
        results = await run_in_threadpool(service.search, query=q)
        return BaseResponse.success(data=results)
    except Exception as e:
        return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="搜索失败")
