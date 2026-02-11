from fastapi import APIRouter, Body, Query

from app.core.db import get_download_tasks
from app.schemas.base import BaseResponse
from app.schemas.task import AddTaskRequest, TaskListResponse
from app.services.task_service import task_service

router = APIRouter()


@router.post("/add", response_model=BaseResponse[int], summary="添加下载任务")
async def add_task(request: AddTaskRequest = Body(...)):
    """
    添加新的下载任务 (原子性操作)
    - 插入数据库
    - 提交到 qBittorrent
    """
    task_id = task_service.add_task(request)
    return BaseResponse.success(data=task_id)


@router.get("/list", response_model=BaseResponse[TaskListResponse], summary="获取任务列表")
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量")
):
    """
    获取下载任务列表，支持分页
    """
    tasks, total = get_download_tasks(page, page_size)
    return BaseResponse.success(data=TaskListResponse(total=total, items=tasks))


@router.post("/cancel/{task_id}", summary="取消任务")
async def cancel_task(task_id: int):
    """
    取消下载任务
    - 仅限 downloading 状态
    - 会从 qBittorrent 删除任务和文件
    - 更新数据库状态为 cancelled
    """
    task_service.cancel_task(task_id)
    return BaseResponse.success(message="任务已取消")
