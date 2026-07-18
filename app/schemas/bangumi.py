from typing import List, Optional

from pydantic import BaseModel


class BangumiWeekday(BaseModel):
    """星期信息"""
    id: Optional[int] = None
    cn: Optional[str] = None
    en: Optional[str] = None
    ja: Optional[str] = None


class BangumiCalendarItem(BaseModel):
    """每日放送中的单个番剧条目（精简）"""
    id: Optional[int] = None
    name: Optional[str] = None
    name_cn: Optional[str] = None
    air_date: Optional[str] = None
    air_weekday: Optional[int] = None
    image: Optional[str] = None
    score: Optional[float] = None
    rating_total: Optional[int] = None
    rank: Optional[int] = None
    doing: Optional[int] = None
    url: Optional[str] = None
    summary: Optional[str] = None


class BangumiCalendarDay(BaseModel):
    """每日放送按星期分组"""
    weekday: BangumiWeekday
    items: List[BangumiCalendarItem] = []


class BangumiTag(BaseModel):
    """条目标签"""
    name: Optional[str] = None
    count: Optional[int] = None


class BangumiSubjectDetail(BaseModel):
    """番剧条目详情"""
    id: Optional[int] = None
    name: Optional[str] = None
    name_cn: Optional[str] = None
    summary: Optional[str] = None
    date: Optional[str] = None
    platform: Optional[str] = None
    eps: Optional[int] = None
    total_episodes: Optional[int] = None
    image: Optional[str] = None
    score: Optional[float] = None
    rating_total: Optional[int] = None
    rank: Optional[int] = None
    tags: List[BangumiTag] = []
    url: Optional[str] = None
