from typing import List, Literal

from fastapi import APIRouter, Path, Query
from fastapi.concurrency import run_in_threadpool

from app.schemas.bangumi import BangumiCalendarDay, BangumiSubjectDetail
from app.schemas.base import BaseResponse, ErrorCode
from app.services.bangumi_service import bangumi_service

router = APIRouter()

SeasonName = Literal["winter", "spring", "summer", "autumn"]


@router.get(
    "/calendar",
    response_model=BaseResponse[List[BangumiCalendarDay]],
    operation_id="bangumiCalendar",
    summary="每日放送（本周新番周历）",
)
async def bangumi_calendar():
    """调用 Bangumi /calendar，返回按周一到周日分组的正在放送番剧。"""
    try:
        data = await run_in_threadpool(bangumi_service.get_calendar)
        return BaseResponse.success(data=data)
    except Exception:
        return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="获取番剧周历失败")


@router.get(
    "/season",
    response_model=BaseResponse[List[BangumiCalendarDay]],
    operation_id="bangumiSeason",
    summary="历史季度新番（按首播日周一到周日）",
)
async def bangumi_season(
    year: int = Query(..., ge=1980, le=2100, description="年份"),
    season: SeasonName = Query(..., description="季节：winter/spring/summer/autumn"),
):
    """调用 Bangumi /v0/subjects 按季度三个月聚合 TV/WEB 动画，按首播日归到周一–周日。"""
    try:
        data = await run_in_threadpool(bangumi_service.get_season, year, season)
        return BaseResponse.success(data=data)
    except ValueError as e:
        return BaseResponse.fail(code=ErrorCode.PARAMS_ERROR, message=str(e))
    except Exception:
        return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="获取季度新番失败")


@router.get(
    "/subject/{subject_id}",
    response_model=BaseResponse[BangumiSubjectDetail],
    operation_id="bangumiSubject",
    summary="番剧条目详情",
)
async def bangumi_subject(subject_id: int = Path(..., description="Bangumi 条目 ID")):
    """调用 Bangumi /v0/subjects/{id}，返回番剧条目详情。"""
    try:
        data = await run_in_threadpool(bangumi_service.get_subject, subject_id)
        return BaseResponse.success(data=data)
    except Exception:
        return BaseResponse.fail(code=ErrorCode.SYSTEM_ERROR, message="获取番剧详情失败")
