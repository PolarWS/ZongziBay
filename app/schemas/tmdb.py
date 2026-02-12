from typing import Any, List, Optional

from pydantic import BaseModel


class TMDBBaseItem(BaseModel):
    """TMDB 基础项"""
    id: int
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    original_language: Optional[str] = None


class TMDBMovie(TMDBBaseItem):
    """TMDB 电影"""
    title: Optional[str] = None
    original_title: Optional[str] = None
    release_date: Optional[str] = None


class TMDBTV(TMDBBaseItem):
    """TMDB 剧集"""
    name: Optional[str] = None
    original_name: Optional[str] = None
    first_air_date: Optional[str] = None


class TMDBSuggestionResponse(BaseModel):
    """搜索建议响应"""
    suggestions: List[str]


class TMDBMovieListResponse(BaseModel):
    """电影列表分页响应"""
    total: int
    items: List[TMDBMovie]


class TMDBTVListResponse(BaseModel):
    """剧集列表分页响应"""
    total: int
    items: List[TMDBTV]


class TMDBEnglishTitleResponse(BaseModel):
    """英文标题响应（供海盗湾等英文搜索使用）"""
    english_title: Optional[str] = None
