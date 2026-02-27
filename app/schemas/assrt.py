# ASSRT 字幕站 API 请求/响应模型
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AssrtLangList(BaseModel):
    """字幕语言列表（langlist）"""
    langdou: Optional[bool] = None
    langkor: Optional[bool] = None
    langeng: Optional[bool] = None
    langchs: Optional[bool] = None
    langcht: Optional[bool] = None
    langjpn: Optional[bool] = None


class AssrtLang(BaseModel):
    """字幕语言"""
    langlist: Optional[AssrtLangList] = None
    desc: Optional[str] = None


class AssrtSubItem(BaseModel):
    """字幕列表项（search / similar 返回）"""
    id: int
    native_name: Optional[str] = None
    revision: Optional[int] = 0
    subtype: Optional[str] = None
    upload_time: Optional[str] = None
    vote_score: Optional[int] = 0
    release_site: Optional[str] = None
    videoname: Optional[str] = None
    lang: Optional[AssrtLang] = None


class AssrtFileListItem(BaseModel):
    """压缩包内单个文件"""
    url: Optional[str] = None
    f: Optional[str] = None  # 文件名
    s: Optional[str] = None  # 大小描述如 52KB


class AssrtProducer(BaseModel):
    """发布人"""
    uploader: Optional[str] = None
    verifier: Optional[str] = None
    producer: Optional[str] = None
    source: Optional[str] = None


class AssrtSubDetail(AssrtSubItem):
    """字幕详情（detail 返回，含下载链接等）"""
    filename: Optional[str] = None
    size: Optional[int] = None
    url: Optional[str] = None
    view_count: Optional[int] = None
    down_count: Optional[int] = None
    title: Optional[str] = None
    filelist: Optional[List[AssrtFileListItem]] = None
    producer: Optional[AssrtProducer] = None


class AssrtSearchResponse(BaseModel):
    """搜索/相似 列表响应"""
    items: List[AssrtSubItem] = Field(default_factory=list)
    total: int = 0
    keyword: Optional[str] = None


class AssrtQuotaResponse(BaseModel):
    """配额查询响应"""
    quota: int = 0


class AssrtDownloadResponse(BaseModel):
    """字幕下载并加入任务队列的响应（由监控移动/重命名，不经过 qB）"""
    task_id: int
    task_name: str
    source_path: str
    target_path: str


class AssrtDownloadBatchItem(BaseModel):
    """批量下载中的单条：file_index 不传为整包"""
    file_index: Optional[int] = None
    file_rename: Optional[str] = None


class AssrtDownloadBatchRequest(BaseModel):
    """批量下载请求：同一字幕 ID，同一目标路径，多个文件"""
    id: int
    target_path: Optional[str] = None
    download_path: Optional[str] = None
    items: List[AssrtDownloadBatchItem] = Field(default_factory=list)


class AssrtDownloadBatchResponse(BaseModel):
    """批量下载响应（立即返回时 results 为空，message 提示后台下载中）"""
    results: List[AssrtDownloadResponse] = Field(default_factory=list)
    message: Optional[str] = None
