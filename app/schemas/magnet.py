from typing import List, Optional

from pydantic import BaseModel


class MagnetFile(BaseModel):
    """磁链解析后的单个文件"""
    name: str
    path: str
    size: int


class MagnetParseResponse(BaseModel):
    """磁链解析响应"""
    files: List[MagnetFile]


class MagnetRequest(BaseModel):
    """磁链解析请求"""
    magnet_link: str


class MagnetDownloadRequest(BaseModel):
    """磁链下载请求"""
    magnet_link: str
    save_path: Optional[str] = None
