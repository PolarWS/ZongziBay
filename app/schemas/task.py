from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class DownloadTaskStatus(str, Enum):
    """下载任务状态"""
    DOWNLOADING = "downloading"
    MOVING = "moving"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class FileTaskStatus(str, Enum):
    """文件任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileTask(BaseModel):
    """文件操作任务"""
    id: int
    downloadTaskId: int
    sourcePath: str
    targetPath: str
    file_rename: str
    file_status: FileTaskStatus
    errorMessage: Optional[str] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None


class FileTaskRequest(BaseModel):
    """添加任务时的文件任务请求"""
    sourcePath: str
    targetPath: str
    file_rename: str


class DownloadTask(BaseModel):
    """下载任务"""
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


class AddTaskRequest(BaseModel):
    """添加下载任务请求，sourcePath/targetPath 不填时按 type 自动选择"""
    taskName: str
    taskInfo: Optional[str] = None
    sourceUrl: str
    sourcePath: Optional[str] = None
    targetPath: Optional[str] = None
    file_tasks: List[FileTaskRequest] = []
    type: Optional[str] = "movie"


class TaskListResponse(BaseModel):
    """任务列表分页响应"""
    total: int
    items: List[DownloadTask]
