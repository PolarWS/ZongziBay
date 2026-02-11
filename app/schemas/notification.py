from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class NotificationType(str, Enum):
    """通知类型"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Notification(BaseModel):
    """通知实体"""
    id: int
    title: str
    content: Optional[str] = None
    type: NotificationType = NotificationType.INFO
    isRead: int
    createTime: Optional[str] = None
    isDelete: int


class NotificationPage(BaseModel):
    """通知分页响应"""
    items: List[Notification]
    total: int
