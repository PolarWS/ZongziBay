from typing import Any, List, Optional

from pydantic import BaseModel


class AnimeGardenPublisher(BaseModel):
    """发布者"""
    id: int
    name: str
    avatar: Optional[str] = None


class AnimeGardenFansub(BaseModel):
    """字幕组"""
    id: int
    name: str
    avatar: Optional[str] = None


class AnimeGardenResource(BaseModel):
    """动漫花园单条资源（publisher/fansub 上游有时不返回，故设为可选）"""
    id: int
    provider: str
    providerId: str
    title: str
    href: str
    type: str
    magnet: str
    size: int  # KB
    createdAt: str
    fetchedAt: str
    publisher: Optional[AnimeGardenPublisher] = None
    fansub: Optional[AnimeGardenFansub] = None
    subjectId: Optional[int] = None

    class Config:
        extra = "ignore"


class AnimeGardenPagination(BaseModel):
    """分页信息"""
    page: int
    pageSize: int
    complete: bool


class AnimeGardenResponse(BaseModel):
    """Anime Garden API 原始响应"""
    status: str
    complete: bool
    resources: List[AnimeGardenResource]
    pagination: Optional[AnimeGardenPagination] = None
    filter: Optional[dict] = None
    timestamp: Optional[str] = None

    class Config:
        extra = "allow"


class AnimeGardenSearchResult(BaseModel):
    """动漫花园搜索接口返回的 data 结构"""
    status: str
    complete: bool
    resources: List[AnimeGardenResource]
    pagination: Optional[AnimeGardenPagination] = None
    filter: Optional[dict] = None
    timestamp: Optional[str] = None


class AnimeGardenTeam(BaseModel):
    """字幕组（上游 teams 接口部分项可能无 provider/providerId）"""
    id: int
    name: str
    provider: Optional[str] = None
    providerId: Optional[str] = None
    avatar: Optional[Any] = None  # 上游可能为 str 或 dict

    class Config:
        extra = "ignore"


class AnimeGardenTeamsResponse(BaseModel):
    """字幕组列表响应"""
    status: str
    teams: List[AnimeGardenTeam]

    class Config:
        extra = "allow"
