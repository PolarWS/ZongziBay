from typing import Optional, List
from enum import Enum
from pydantic import BaseModel

class DownloadTaskStatus(str, Enum):
    DOWNLOADING = "downloading"
    MOVING = "moving"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"

class FileTaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class FileTask(BaseModel):
    id: int
    downloadTaskId: int
    sourcePath: str
    targetPath: str
    file_rename: str
    file_status: FileTaskStatus
    errorMessage: Optional[str] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None

class DownloadTask(BaseModel):
    id: int
    taskName: str
    taskInfo: Optional[str] = None
    sourceUrl: Optional[str] = None
    sourcePath: Optional[str] = None
    targetPath: Optional[str] = None
    taskStatus: Optional[DownloadTaskStatus] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None
    isDelete: int
    file_tasks: List[FileTask] = []

class FileTaskRequest(BaseModel):
    sourcePath: str
    targetPath: str
    file_rename: str

class AddTaskRequest(BaseModel):
    taskName: str
    taskInfo: Optional[str] = None
    sourceUrl: str
    sourcePath: Optional[str] = None  # 如果不填，将根据 type 自动选择
    targetPath: Optional[str] = None  # 如果不填，将根据 type 自动选择
    file_tasks: List[FileTaskRequest] = []
    type: Optional[str] = "movie"     # movie | tv

class TaskListResponse(BaseModel):
    total: int
    items: List[DownloadTask]
