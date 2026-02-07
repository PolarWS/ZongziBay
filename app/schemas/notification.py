from typing import Optional, List
from pydantic import BaseModel

class Notification(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    type: str = 'info'
    isRead: int
    createTime: Optional[str] = None
    isDelete: int

class NotificationPage(BaseModel):
    items: List[Notification]
    total: int
