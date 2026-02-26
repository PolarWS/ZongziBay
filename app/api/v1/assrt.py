# 字幕服务 API：ASSRT 搜索、详情、相似；字幕为 HTTP 直链，由本程序下载后走任务队列
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

from app.schemas.assrt import (
    AssrtDownloadBatchRequest,
    AssrtDownloadBatchResponse,
    AssrtDownloadResponse,
    AssrtQuotaResponse,
    AssrtSearchResponse,
    AssrtSubDetail,
)
from app.schemas.base import BaseResponse
from app.services.assrt_service import assrt_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/sub/search", response_model=BaseResponse[AssrtSearchResponse], summary="搜索字幕")
async def search_subs(
    q: str = Query(..., min_length=3, description="搜索关键词，至少 3 个字符"),
    pos: int = Query(0, ge=0, description="分页起始位置"),
    cnt: int = Query(15, ge=1, le=15, description="返回数量，最多 15"),
    is_file: bool = Query(False, description="为 true 时按视频文件名搜索"),
    no_muxer: bool = Query(False, description="为 true 时忽略压制组与视频参数"),
):
    """ASSRT 字幕搜索。"""
    items, total = await run_in_threadpool(
        assrt_service.search_subs,
        q,
        pos,
        cnt,
        is_file,
        no_muxer,
    )
    return BaseResponse.success(
        data=AssrtSearchResponse(items=items, total=total, keyword=q)
    )


@router.get("/sub/detail", response_model=BaseResponse[AssrtSubDetail], summary="字幕详情")
async def get_sub_detail(
    id: int = Query(..., description="字幕 ID，6 位整数"),
):
    """获取字幕详情（含下载链接、filelist 等）。"""
    detail = await run_in_threadpool(assrt_service.get_sub_detail, id)
    return BaseResponse.success(data=detail)


@router.get("/sub/similar", response_model=BaseResponse[AssrtSearchResponse], summary="相似字幕")
async def get_similar_subs(
    id: int = Query(..., description="字幕 ID"),
):
    """获取与某字幕类似的其他字幕（最多 5 条）。"""
    items = await run_in_threadpool(assrt_service.get_similar_subs, id)
    return BaseResponse.success(data=AssrtSearchResponse(items=items, total=len(items)))


@router.get("/user/quota", response_model=BaseResponse[AssrtQuotaResponse], summary="查询配额")
async def get_quota():
    """获取当前 ASSRT API 配额（次/分钟）。"""
    quota = await run_in_threadpool(assrt_service.get_quota)
    return BaseResponse.success(data=AssrtQuotaResponse(quota=quota))


@router.post("/sub/download", response_model=BaseResponse[AssrtDownloadResponse], summary="字幕下载并加入任务队列")
async def download_sub(
    id: int = Query(..., description="字幕 ID"),
    file_index: Optional[int] = Query(None, description="压缩包内文件索引（0-based），不传则下载整包"),
    target_path: Optional[str] = Query(None, description="目标路径（不传则使用 paths.default_target_path）"),
    file_rename: Optional[str] = Query(None, description="保存时的文件名（不传则使用原文件名）"),
):
    """qB 不支持 HTTP 直链；由本程序 HTTP 下载到 paths.subtitle_download_path，写入任务表，由监控移动/重命名到目标路径。"""
    task_id, task_name, source_path, final_target = await run_in_threadpool(
        assrt_service.create_subtitle_download_task,
        id,
        file_index,
        target_path,
        file_rename,
    )
    return BaseResponse.success(
        data=AssrtDownloadResponse(
            task_id=task_id,
            task_name=task_name,
            source_path=source_path,
            target_path=final_target,
        )
    )


def _run_fill_downloads_in_background(task_id: int, sub_id: int, item_tuples: list) -> None:
    """后台线程：拉取 ASSRT 详情、下载文件、回填 sourcePath，并将任务状态改为 moving。"""
    try:
        assrt_service.fill_subtitle_downloads_and_start_moving(task_id, sub_id, item_tuples)
    except Exception as e:
        logger.exception("字幕后台下载/回填失败 task_id=%s sub_id=%s: %s", task_id, sub_id, e)


@router.post("/sub/download/batch", response_model=BaseResponse[AssrtDownloadBatchResponse], summary="批量字幕下载并加入任务队列")
async def download_subs_batch(body: AssrtDownloadBatchRequest):
    """先同步写入一条任务（立即出现在列表），再在后台下载并回填，最后由监控移动。"""
    if not body.items:
        return BaseResponse.success(data=AssrtDownloadBatchResponse(results=[]))
    item_tuples = [(it.file_index, it.file_rename) for it in body.items]
    task_id = await run_in_threadpool(
        assrt_service.create_subtitle_download_task_placeholder,
        body.id,
        body.target_path,
        item_tuples,
    )
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        lambda: _run_fill_downloads_in_background(task_id, body.id, item_tuples),
    )
    return BaseResponse.success(
        data=AssrtDownloadBatchResponse(results=[], message="任务已加入队列，正在后台下载"),
    )
