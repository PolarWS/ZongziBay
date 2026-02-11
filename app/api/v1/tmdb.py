from typing import Any, List

from fastapi import APIRouter, Query

from app.schemas.base import BaseResponse
from app.schemas.tmdb import (
    TMDBMovie,
    TMDBMovieListResponse,
    TMDBTV,
    TMDBTVListResponse,
    TMDBSuggestionResponse,
)
from app.services.tmdb_service import tmdb_service

router = APIRouter()


@router.get("/search/movie", response_model=BaseResponse[TMDBMovieListResponse], summary="搜索电影")
async def search_movie(
    query: str = Query(..., description="搜索关键词"),
    page: int = Query(1, description="页码"),
):
    """根据关键词搜索电影"""
    results, total = tmdb_service.search_movies_with_total(query, page)
    items = [_convert_result(r) for r in results]
    return BaseResponse.success(data=TMDBMovieListResponse(total=total, items=items))


@router.get("/search/tv", response_model=BaseResponse[TMDBTVListResponse], summary="搜索电视剧/番剧")
async def search_tv(
    query: str = Query(..., description="搜索关键词"),
    page: int = Query(1, description="页码"),
):
    """根据关键词搜索电视剧或番剧"""
    results, total = tmdb_service.search_tv_shows_with_total(query, page)
    items = [_convert_result(r) for r in results]
    return BaseResponse.success(data=TMDBTVListResponse(total=total, items=items))


@router.get("/suggestions", response_model=BaseResponse[TMDBSuggestionResponse], summary="搜索提示补全")
async def get_suggestions(
    query: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, description="返回数量限制"),
    type: str = Query("", description="媒体类型: movie / tv，为空则混合搜索"),
):
    """根据输入返回搜索建议（标题补全）"""
    suggestions = tmdb_service.get_search_suggestions(query, limit, media_type=type)
    return BaseResponse.success(data={"suggestions": suggestions})


@router.get("/movie/{movie_id}", response_model=BaseResponse[TMDBMovie], summary="获取电影详情")
async def get_movie_detail(movie_id: int):
    """获取指定电影的详细信息"""
    result = tmdb_service.get_movie_details(movie_id)
    return BaseResponse.success(data=_convert_result(result))


@router.get("/tv/{tv_id}", response_model=BaseResponse[TMDBTV], summary="获取电视剧详情")
async def get_tv_detail(tv_id: int):
    """获取指定电视剧的详细信息"""
    result = tmdb_service.get_tv_details(tv_id)
    return BaseResponse.success(data=_convert_result(result))


def _convert_result(result: Any) -> dict:
    """将 TMDB 对象转换为字典，过滤私有属性"""
    if isinstance(result, dict):
        return result
    if hasattr(result, "__dict__"):
        return {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
    return result
