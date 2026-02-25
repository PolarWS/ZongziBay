from typing import Any, Dict, List

from fastapi import APIRouter

from app.core.config import config
from app.schemas.base import BaseResponse

router = APIRouter()

# 仅允许暴露的路径配置键（不含账号密码等敏感项，避免 config 结构变更导致泄露）
ALLOWED_PATH_KEYS = {
    "default_download_path", "movie_download_path", "tv_download_path", "anime_download_path",
    "download_root_path", "target_root_path", "root_path",
    "default_target_path", "movie_target_path", "tv_target_path", "anime_target_path",
}


# 智能重命名默认模板（未配置时使用）
DEFAULT_SMART_RENAME = {
    "movie": "{name} ({year})/{name} ({year}){extra}{sub_suffix}{ext}",
    "tv": "{name}/Season {season}/{name} S{ss}E{ee}{extra}{sub_suffix}{ext}",
    "anime": "{name}/Season {season}/{name} S{ss}E{ee}{extra}{sub_suffix}{ext}",
}


@router.get("/paths", response_model=BaseResponse)
async def get_path_config():
    """获取系统路径配置（下载路径、归档路径等）。仅返回路径相关字段，不含任何账号密码。"""
    raw = config.get("paths", {}) or {}
    paths: Dict[str, Any] = {k: v for k, v in raw.items() if k in ALLOWED_PATH_KEYS}
    return BaseResponse.success(data=paths)


@router.get("/rename-templates", response_model=BaseResponse)
async def get_rename_templates():
    """获取智能重命名模板（movie / tv / anime）。用于磁力解析页自定义命名格式。"""
    raw = config.get("smart_rename", {}) or {}
    templates: Dict[str, str] = {k: v for k, v in raw.items() if isinstance(v, str)}
    for key in ("movie", "tv", "anime"):
        if key not in templates and key in DEFAULT_SMART_RENAME:
            templates[key] = DEFAULT_SMART_RENAME[key]
    return BaseResponse.success(data=templates)


@router.get("/trackers", response_model=BaseResponse)
async def get_trackers():
    """获取 BT Tracker 列表"""
    trackers: List[str] = config.get("trackers", [])
    return BaseResponse.success(data=trackers)
