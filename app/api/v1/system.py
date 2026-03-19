from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException

from app.core.config import config
from app.core.password_hash import hash_password
from app.schemas.base import BaseResponse
from app.services.assrt_service import assrt_service
from app.services.magnet_service import magnet_service
from app.services.task_service import task_service
from app.services.tmdb_service import tmdb_service

router = APIRouter()


@router.get("/config", response_model=BaseResponse, summary="获取完整配置（供设置页编辑）")
async def get_config():
    """返回当前配置文件内容（未叠加环境变量），用于设置页展示与修改"""
    data = config.get_file_config()
    # 避免把登录密码（哈希或明文）直接下发到前端
    if isinstance(data.get("security"), dict) and "password" in data["security"]:
        data["security"]["password"] = ""
    return BaseResponse.success(data=data)


@router.put("/config", response_model=BaseResponse, summary="保存配置")
async def save_config(body: Dict[str, Any] = Body(..., embed=False)):
    """将配置写回 config 文件并生效；请求体为完整配置对象（JSON）"""
    if not body or not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体须为配置对象")
    try:
        # security.password：允许前端传明文用于改密；若为空字符串则保留原值
        if isinstance(body.get("security"), dict) and "password" in body["security"]:
            pwd = body["security"].get("password")
            if pwd == "" or pwd is None:
                old = config.get_file_config()
                if isinstance(old.get("security"), dict) and "password" in old["security"]:
                    body["security"]["password"] = old["security"]["password"]
            elif isinstance(pwd, str) and not pwd.startswith("pbkdf2_sha256$"):
                body["security"]["password"] = hash_password(pwd)

        config.save_file_config(body)
        # 部分服务启动时会缓存配置，这里主动刷新，确保“保存后立即生效”
        tmdb_service.reload_config()
        assrt_service.reload_config()
        magnet_service.reload_config()
        task_service.reload_config()
        return BaseResponse.success(message="配置已保存")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
