from typing import Optional, List
from enum import Enum
from pydantic import BaseModel

class NotificationType(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class Notification(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    type: NotificationType = NotificationType.INFO
    isRead: int
    createTime: Optional[str] = None
    isDelete: int

class NotificationPage(BaseModel):
    items: List[Notification]
    total: int
