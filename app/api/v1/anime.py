from typing import List, Optional

from fastapi import APIRouter, Query

from app.schemas.anime_garden import AnimeGardenSearchResult, AnimeGardenTeam
from app.schemas.base import BaseResponse, ErrorCode
from app.services.anime_garden_service import AnimeGardenService

router = APIRouter()
service = AnimeGardenService()


@router.get(
    "/search",
    response_model=BaseResponse[AnimeGardenSearchResult],
    operation_id="animeGardenSearch",
    summary="动漫花园关键字搜索",
)
async def anime_garden_search(
    q: str = Query(..., description="搜索关键词，支持中文/繁体"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="每页数量"),
    fansub: Optional[str] = Query(None, description="字幕组筛选（名称）"),
):
    """调用 Anime Garden /resources，传 search、page、pageSize、fansub。"""
    try:
        data = service.search(q=q, page=page, page_size=page_size, fansub=fansub)
        return BaseResponse.success(data=data)
    except Exception:
        return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="搜索失败")


@router.get(
    "/teams",
    response_model=BaseResponse[List[AnimeGardenTeam]],
    operation_id="animeGardenTeams",
    summary="获取所有字幕组信息",
)
async def anime_garden_teams():
    """调用 Anime Garden 字幕组列表接口。"""
    try:
        teams = service.get_teams()
        return BaseResponse.success(data=teams)
    except Exception:
        return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="获取字幕组列表失败")
