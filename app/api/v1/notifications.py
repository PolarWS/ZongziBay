import asyncio

from fastapi import APIRouter, Query

from app.core.db import db
from app.schemas.base import BaseResponse
from app.schemas.notification import NotificationPage

router = APIRouter()


@router.get("/", response_model=BaseResponse[NotificationPage])
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: bool = Query(None)
):
    """获取通知列表"""
    notifications, total = await asyncio.to_thread(db.get_notifications, page, page_size, is_read)
    return BaseResponse.success(data=NotificationPage(items=notifications, total=total))


@router.get("/unread_count", response_model=BaseResponse[int])
async def get_unread_count():
    """获取未读数量"""
    count = await asyncio.to_thread(db.get_unread_count)
    return BaseResponse.success(data=count)


@router.put("/{notification_id}/read", response_model=BaseResponse[bool])
async def mark_read(notification_id: int):
    """标记已读"""
    success = await asyncio.to_thread(db.mark_notification_read, notification_id)
    return BaseResponse.success(data=success)


@router.put("/read_all", response_model=BaseResponse[int])
async def mark_all_read():
    """全部标记已读"""
    count = await asyncio.to_thread(db.mark_all_notifications_read)
    return BaseResponse.success(data=count)


@router.delete("/{notification_id}", response_model=BaseResponse[bool])
async def delete_notification(notification_id: int):
    """删除通知"""
    success = await asyncio.to_thread(db.delete_notification, notification_id)
    return BaseResponse.success(data=success)
