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


class TMDBGenre(BaseModel):
    """TMDB 类型（题材）"""
    id: Optional[int] = None
    name: Optional[str] = None


class TMDBCountry(BaseModel):
    """TMDB 制作国家/地区"""
    iso_3166_1: Optional[str] = None
    name: Optional[str] = None


class TMDBSpokenLanguage(BaseModel):
    """TMDB 语言"""
    iso_639_1: Optional[str] = None
    name: Optional[str] = None
    english_name: Optional[str] = None


class TMDBCompany(BaseModel):
    """TMDB 制作公司 / 电视网"""
    id: Optional[int] = None
    name: Optional[str] = None
    logo_path: Optional[str] = None
    origin_country: Optional[str] = None


class TMDBCreatedBy(BaseModel):
    """TMDB 剧集主创"""
    id: Optional[int] = None
    name: Optional[str] = None
    profile_path: Optional[str] = None


class TMDBCastMember(BaseModel):
    """TMDB 演员"""
    id: Optional[int] = None
    name: Optional[str] = None
    character: Optional[str] = None
    profile_path: Optional[str] = None


class TMDBMovieDetail(TMDBMovie):
    """TMDB 电影详情（比列表项包含更丰富的信息）"""
    tagline: Optional[str] = None
    status: Optional[str] = None
    runtime: Optional[int] = None
    vote_count: Optional[int] = None
    homepage: Optional[str] = None
    imdb_id: Optional[str] = None
    budget: Optional[int] = None
    revenue: Optional[int] = None
    genres: List[TMDBGenre] = []
    production_countries: List[TMDBCountry] = []
    spoken_languages: List[TMDBSpokenLanguage] = []
    production_companies: List[TMDBCompany] = []
    cast: List[TMDBCastMember] = []


class TMDBTVDetail(TMDBTV):
    """TMDB 剧集详情（比列表项包含更丰富的信息）"""
    tagline: Optional[str] = None
    status: Optional[str] = None
    vote_count: Optional[int] = None
    homepage: Optional[str] = None
    number_of_seasons: Optional[int] = None
    number_of_episodes: Optional[int] = None
    last_air_date: Optional[str] = None
    episode_run_time: List[int] = []
    origin_country: List[str] = []
    genres: List[TMDBGenre] = []
    production_countries: List[TMDBCountry] = []
    spoken_languages: List[TMDBSpokenLanguage] = []
    networks: List[TMDBCompany] = []
    created_by: List[TMDBCreatedBy] = []
    cast: List[TMDBCastMember] = []


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
