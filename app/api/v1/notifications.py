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
    notifications, total = db.get_notifications(page, page_size, is_read)
    return BaseResponse.success(data=NotificationPage(items=notifications, total=total))

@router.get("/unread_count", response_model=BaseResponse[int])
async def get_unread_count():
    count = db.get_unread_count()
    return BaseResponse.success(data=count)

@router.put("/{notification_id}/read", response_model=BaseResponse[bool])
async def mark_read(notification_id: int):
    success = db.mark_notification_read(notification_id)
    return BaseResponse.success(data=success)

@router.put("/read_all", response_model=BaseResponse[int])
async def mark_all_read():
    count = db.mark_all_notifications_read()
    return BaseResponse.success(data=count)

@router.delete("/{notification_id}", response_model=BaseResponse[bool])
async def delete_notification(notification_id: int):
    success = db.delete_notification(notification_id)
    return BaseResponse.success(data=success)
