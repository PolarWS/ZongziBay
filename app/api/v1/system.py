import copy
import logging
import os
import secrets
import string

import requests
from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException

from app.core.config import config
from app.core.security import hash_password, is_hashed
from app.schemas.base import BaseResponse
from app.services.assrt_service import assrt_service
from app.services.magnet_service import magnet_service
from app.services.task_service import task_service
from app.services.tmdb_service import tmdb_service

router = APIRouter()
logger = logging.getLogger(__name__)

# 项目默认密钥（供未自行申请 API 密钥的用户使用，仅存于服务端）
_DEFAULT_TMDB_API_KEY = "4c378e70c91136dcf1d9e2c115c56156"
_DEFAULT_ASSRT_TOKEN = "WDUM3zs7WXByxJLwPwQM7MkZqmSGmS1f"

# 脱敏占位符（GET /config 返回此项代替真实密钥，PUT /config 收到此项时保留原值）
_MASKED_PLACEHOLDER = "****"


def _mask_sensitive_keys(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """对配置中的 TMDB api_key、ASSRT token、qBittorrent password/api_key、安全密码 进行脱敏"""
    cfg = copy.deepcopy(cfg)
    tmdb = cfg.get("tmdb")
    if isinstance(tmdb, dict) and tmdb.get("api_key"):
        tmdb["api_key"] = _MASKED_PLACEHOLDER
    subtitle = cfg.get("subtitle")
    if isinstance(subtitle, dict):
        assrt = subtitle.get("assrt")
        if isinstance(assrt, dict) and assrt.get("token"):
            assrt["token"] = _MASKED_PLACEHOLDER
    qb = cfg.get("qbittorrent")
    if isinstance(qb, dict):
        if qb.get("password"):
            qb["password"] = _MASKED_PLACEHOLDER
        if qb.get("api_key"):
            qb["api_key"] = _MASKED_PLACEHOLDER
    security = cfg.get("security")
    if isinstance(security, dict):
        if security.get("password"):
            security["password"] = _MASKED_PLACEHOLDER
    return cfg


def _restore_masked_keys(body: Dict[str, Any]) -> Dict[str, Any]:
    """若前端上传的密钥字段为脱敏占位符，则从已有配置中恢复真实值"""
    body = copy.deepcopy(body)
    existing = config.get_file_config()
    tmdb = body.get("tmdb")
    if isinstance(tmdb, dict) and tmdb.get("api_key") == _MASKED_PLACEHOLDER:
        old_key = (existing.get("tmdb") or {}).get("api_key") or ""
        if old_key and old_key != _MASKED_PLACEHOLDER:
            tmdb["api_key"] = old_key
    subtitle = body.get("subtitle")
    if isinstance(subtitle, dict):
        assrt = subtitle.get("assrt")
        if isinstance(assrt, dict) and assrt.get("token") == _MASKED_PLACEHOLDER:
            old_token = ((existing.get("subtitle") or {}).get("assrt") or {}).get("token") or ""
            if old_token and old_token != _MASKED_PLACEHOLDER:
                assrt["token"] = old_token
    qb = body.get("qbittorrent")
    if isinstance(qb, dict):
        if qb.get("password") == _MASKED_PLACEHOLDER:
            old_pwd = (existing.get("qbittorrent") or {}).get("password") or ""
            if old_pwd and old_pwd != _MASKED_PLACEHOLDER:
                qb["password"] = old_pwd
        if qb.get("api_key") == _MASKED_PLACEHOLDER:
            old_key = (existing.get("qbittorrent") or {}).get("api_key") or ""
            if old_key and old_key != _MASKED_PLACEHOLDER:
                qb["api_key"] = old_key
    return body


@router.get("/config", response_model=BaseResponse, summary="获取完整配置（供设置页编辑）")
async def get_config():
    """返回当前配置文件内容（未叠加环境变量），密钥字段脱敏处理"""
    data = config.get_file_config()
    return BaseResponse.success(data=_mask_sensitive_keys(data))


@router.put("/config", response_model=BaseResponse, summary="保存配置")
async def save_config(body: Dict[str, Any] = Body(..., embed=False)):
    """将配置写回 config 文件并生效；请求体为完整配置对象（JSON）"""
    if not body or not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体须为配置对象")
    try:
        safe_body = _restore_masked_keys(body)
        # 安全密码使用 bcrypt 哈希存储
        security = safe_body.get("security") or {}
        plain_password = security.get("password")
        if plain_password is not None:
            if len(plain_password) < 6:
                raise HTTPException(status_code=400, detail="密码长度至少 6 个字符")
            if not is_hashed(plain_password):
                security["password"] = hash_password(plain_password)
        # JWT 密钥不允许为空或默认值
        secret_key = security.get("secret_key")
        if secret_key is not None:
            if not secret_key or secret_key == "CHANGE_THIS_SECRET_KEY":
                raise HTTPException(status_code=400, detail="JWT 密钥不能为空或使用默认值，请设置一个安全密钥")
            if len(secret_key) < 16:
                raise HTTPException(status_code=400, detail="JWT 密钥长度至少 16 个字符，请重新生成")
        # 清理 TMDB 域名：去掉多余的 https:// 前缀
        tmdb = safe_body.get("tmdb")
        if isinstance(tmdb, dict):
            for key in ("api_domain", "image_domain"):
                val = tmdb.get(key)
                if isinstance(val, str):
                    tmdb[key] = _strip_protocol(val)
        config.save_file_config(safe_body)
        # 部分服务启动时会缓存配置，这里主动刷新，确保"保存后立即生效"
        tmdb_service.reload_config()
        assrt_service.reload_config()
        magnet_service.reload_config()
        task_service.reload_config()
        return BaseResponse.success(message="配置已保存")
    except HTTPException:
        raise
    except Exception:
        logger.error(f"保存配置失败", exc_info=True)
        raise HTTPException(status_code=500, detail="保存配置失败，请稍后重试")


@router.post("/config/apply-default-tmdb-key", response_model=BaseResponse, summary="使用项目提供的 TMDB 默认密钥")
async def apply_default_tmdb_key():
    """将 TMDB API Key 设置为项目内建的默认值，前端不会看到实际密钥内容"""
    try:
        cfg = config.get_file_config()
        cfg.setdefault("tmdb", {})
        cfg["tmdb"]["api_key"] = _DEFAULT_TMDB_API_KEY
        config.save_file_config(cfg)
        tmdb_service.reload_config()
        return BaseResponse.success(message="TMDB 默认密钥已应用")
    except HTTPException:
        raise
    except Exception:
        logger.error("应用 TMDB 默认密钥失败", exc_info=True)
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")


@router.post("/config/apply-default-assrt-key", response_model=BaseResponse, summary="使用项目提供的 ASSRT 默认密钥")
async def apply_default_assrt_key():
    """将 ASSRT Token 设置为项目内建的默认值，前端不会看到实际密钥内容"""
    try:
        cfg = config.get_file_config()
        cfg.setdefault("subtitle", {}).setdefault("assrt", {})
        cfg["subtitle"]["assrt"]["token"] = _DEFAULT_ASSRT_TOKEN
        config.save_file_config(cfg)
        assrt_service.reload_config()
        return BaseResponse.success(message="ASSRT 默认密钥已应用")
    except HTTPException:
        raise
    except Exception:
        logger.error("应用 ASSRT 默认密钥失败", exc_info=True)
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")


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


# ================================================================
# 初始化引导相关 API（无需认证，在白名单中）
# ================================================================

def _is_initialized() -> bool:
    """判断系统是否已完成初始化：
    - 从 YAML 文件（非环境变量叠加后的 _config）读取 secret_key
    - secret_key 不能为空
    - secret_key 不能是默认值 "CHANGE_THIS_SECRET_KEY"
    - secret_key 长度不能小于 16 字符
    优先读取 YAML 文件值，避免 Docker 环境变量注入导致反复进入引导页。
    """
    # 优先从 YAML 文件读取，避免被环境变量覆盖导致的误判
    file_cfg = config._file_config
    secret_key = ""
    if isinstance(file_cfg, dict):
        security = file_cfg.get("security") or {}
        secret_key = security.get("secret_key", "")
    if not isinstance(secret_key, str):
        secret_key = ""
    if not secret_key or secret_key == "CHANGE_THIS_SECRET_KEY":
        return False
    if len(secret_key) < 16:
        return False
    return True


def _strip_protocol(value: str) -> str:
    """去掉域名前的 http:// / https:// 前缀和末尾的 /（TMDB api_domain / image_domain 只需要纯域名）"""
    v = value.strip()
    if v.startswith("https://"):
        v = v[8:]
    elif v.startswith("http://"):
        v = v[7:]
    v = v.rstrip("/")
    return v

def _generate_secret_key(length: int = 32) -> str:
    """生成随机密钥"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _scan_env_vars() -> Dict[str, str]:
    """扫描 ZONGZI_ 开头的环境变量，返回前端可用的配置映射"""
    env_map: Dict[str, str] = {}
    for key, value in os.environ.items():
        if key.startswith("ZONGZI_"):
            env_map[key] = value
    return env_map


@router.get("/status", response_model=BaseResponse, summary="检查系统初始化状态")
async def get_system_status():
    """返回系统是否已完成初始化配置"""
    initialized = _is_initialized()
    return BaseResponse.success(data={
        "initialized": initialized,
        "username": config.get("security.username", ""),
    })


@router.get("/env-config", response_model=BaseResponse, summary="获取 Docker 环境变量配置")
async def get_env_config():
    """返回从 Docker 环境变量中注入的 ZONGZI_ 前缀配置。敏感字段仅返回是否存在标记。"""
    env_vars = _scan_env_vars()
    parsed: Dict[str, Any] = {}

    # 解析常见环境变量 — 敏感字段仅返回是否存在
    if "ZONGZI_TMDB_API_KEY" in env_vars:
        parsed["tmdb_api_key"] = True
        parsed["tmdb_api_key_masked"] = _MASKED_PLACEHOLDER
    if "ZONGZI_ASSRT_TOKEN" in env_vars or "ZONGZI_SUBTITLE_ASSRT_TOKEN" in env_vars:
        parsed["assrt_token"] = True
        parsed["assrt_token_masked"] = _MASKED_PLACEHOLDER
    if "ZONGZI_QBITTORRENT_HOST" in env_vars:
        parsed["qb_host"] = env_vars["ZONGZI_QBITTORRENT_HOST"]
    if "ZONGZI_QBITTORRENT_USERNAME" in env_vars:
        parsed["qb_username"] = env_vars["ZONGZI_QBITTORRENT_USERNAME"]
    if "ZONGZI_QBITTORRENT_PASSWORD" in env_vars:
        parsed["qb_password"] = True
        parsed["qb_password_masked"] = _MASKED_PLACEHOLDER
    if "ZONGZI_QBITTORRENT_API_KEY" in env_vars:
        parsed["qb_api_key"] = True
        parsed["qb_api_key_masked"] = _MASKED_PLACEHOLDER
    if "ZONGZI_SECURITY_USERNAME" in env_vars:
        parsed["username"] = env_vars["ZONGZI_SECURITY_USERNAME"]
    if "ZONGZI_SECURITY_PASSWORD" in env_vars:
        parsed["password"] = True
        parsed["password_masked"] = _MASKED_PLACEHOLDER
    if "ZONGZI_SECURITY_SECRET_KEY" in env_vars:
        parsed["secret_key"] = True
        parsed["secret_key_masked"] = _MASKED_PLACEHOLDER

    # 把所有原始环境变量也带回去（过滤掉敏感值）
    raw_safe: Dict[str, str] = {}
    sensitive_keys = {"ZONGZI_SECURITY_PASSWORD", "ZONGZI_SECURITY_SECRET_KEY",
                      "ZONGZI_TMDB_API_KEY", "ZONGZI_ASSRT_TOKEN",
                      "ZONGZI_SUBTITLE_ASSRT_TOKEN", "ZONGZI_QBITTORRENT_PASSWORD",
                      "ZONGZI_QBITTORRENT_API_KEY"}
    for key, value in env_vars.items():
        if key in sensitive_keys:
            raw_safe[key] = _MASKED_PLACEHOLDER
        else:
            raw_safe[key] = value

    return BaseResponse.success(data={
        "parsed": parsed,
        "raw": raw_safe,
    })


@router.get("/existing-config", response_model=BaseResponse, summary="读取已有配置文件供引导页预填")
async def get_existing_config():
    """读取 config.yml 中已有的配置值，供初始化引导页预填表单。
    敏感字段（密码、密钥）不返回明文，仅返回是否已填充的标记。
    系统初始化完成后此接口不可访问。"""
    if _is_initialized():
        raise HTTPException(status_code=403, detail="系统已初始化，此接口不可访问")
    cfg = config.get_file_config() or {}

    security = cfg.get("security") or {}
    tmdb_cfg = cfg.get("tmdb") or {}
    qb = cfg.get("qbittorrent") or {}
    assrt_cfg = (cfg.get("subtitle") or {}).get("assrt") or {}
    paths = cfg.get("paths") or {}
    piratebay_cfg = cfg.get("piratebay") or {}
    anime_garden_cfg = cfg.get("anime_garden") or {}

    return BaseResponse.success(data={
        "security": {
            "username": security.get("username", ""),
            "password": bool(security.get("password", "")),
        },
        "tmdb": {
            "api_key": bool(tmdb_cfg.get("api_key", "")),
            "language": tmdb_cfg.get("language", ""),
            "api_domain": tmdb_cfg.get("api_domain", ""),
            "image_domain": tmdb_cfg.get("image_domain", ""),
        },
        "qbittorrent": {
            "host": qb.get("host", ""),
            "username": qb.get("username", ""),
            "password": bool(qb.get("password", "")),
            "api_key": bool(qb.get("api_key", "")),
        },
        "subtitle": {
            "assrt": {
                "token": bool(assrt_cfg.get("token", "")),
                "base_url": assrt_cfg.get("base_url", ""),
            },
        },
        "paths": {
            "download_root_path": paths.get("download_root_path", ""),
            "target_root_path": paths.get("target_root_path", ""),
            "root_path": paths.get("root_path", ""),
            "default_download_path": paths.get("default_download_path", ""),
            "movie_download_path": paths.get("movie_download_path", ""),
            "tv_download_path": paths.get("tv_download_path", ""),
            "anime_download_path": paths.get("anime_download_path", ""),
            "temp_download_path": paths.get("temp_download_path", ""),
            "default_target_path": paths.get("default_target_path", ""),
            "movie_target_path": paths.get("movie_target_path", ""),
            "tv_target_path": paths.get("tv_target_path", ""),
            "anime_target_path": paths.get("anime_target_path", ""),
        },
        "piratebay": {
            "url": piratebay_cfg.get("url", ""),
            "params": piratebay_cfg.get("params", ""),
        },
        "anime_garden": {
            "url": anime_garden_cfg.get("url", ""),
            "page_size": anime_garden_cfg.get("page_size", 20),
        },
    })


@router.post("/test-connection", response_model=BaseResponse, summary="测试各服务连通性")
async def test_connection(body: Dict[str, Any] = Body(..., embed=False)):
    """根据传入的配置参数测试各服务连通性，返回每个服务的测试结果。
    此接口需要 JWT 认证。"""
    results: Dict[str, Dict[str, Any]] = {}

    # --- TMDB ---
    tmdb_api_key = body.get("tmdb_api_key", "")
    if not tmdb_api_key:
        tmdb_api_key = config.get("tmdb.api_key", "")
    if tmdb_api_key:
        try:
            test_url = f"https://api.themoviedb.org/3/movie/550?api_key={tmdb_api_key}&language=zh-CN"
            resp = requests.get(test_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results["tmdb"] = {
                    "success": True,
                    "message": "连接成功",
                }
            elif resp.status_code == 401:
                results["tmdb"] = {"success": False, "message": "API Key 无效 (401)"}
            else:
                results["tmdb"] = {"success": False, "message": f"请求失败: HTTP {resp.status_code}"}
        except requests.RequestException as e:
            results["tmdb"] = {"success": False, "message": f"网络错误: {str(e)}"}
    else:
        results["tmdb"] = {"success": False, "message": "未配置 API Key"}

    # --- qBittorrent ---
    qb_host = body.get("qb_host", "") or config.get("qbittorrent.host", "")
    qb_username = body.get("qb_username", "") or config.get("qbittorrent.username", "")
    qb_password = body.get("qb_password", "") or config.get("qbittorrent.password", "")
    qb_api_key = body.get("qb_api_key", "") or config.get("qbittorrent.api_key", "")
    if qb_host:
        try:
            session = requests.Session()
            session.headers.update({"Referer": qb_host})
            if qb_api_key:
                session.headers["Authorization"] = f"Bearer {qb_api_key}"
                version_resp = session.get(f"{qb_host.rstrip('/')}/api/v2/app/version", timeout=10)
                if version_resp.status_code == 200:
                    results["qbittorrent"] = {
                        "success": True,
                        "message": "连接成功",
                    }
                else:
                    results["qbittorrent"] = {"success": False, "message": f"API Key 无效: HTTP {version_resp.status_code}"}
            elif qb_username and qb_password:
                login_resp = session.post(
                    f"{qb_host.rstrip('/')}/api/v2/auth/login",
                    data={"username": qb_username, "password": qb_password},
                    timeout=10,
                )
                if login_resp.status_code == 200 and "Ok." in login_resp.text:
                    version_resp = session.get(f"{qb_host.rstrip('/')}/api/v2/app/version", timeout=10)
                    if version_resp.status_code == 200:
                        results["qbittorrent"] = {
                            "success": True,
                            "message": "连接成功",
                        }
                    else:
                        results["qbittorrent"] = {"success": False, "message": "登录成功但获取版本失败"}
                elif login_resp.status_code == 204:
                    version_resp = session.get(f"{qb_host.rstrip('/')}/api/v2/app/version", timeout=10)
                    if version_resp.status_code == 200:
                        results["qbittorrent"] = {
                            "success": True,
                            "message": "连接成功",
                        }
                    else:
                        results["qbittorrent"] = {"success": False, "message": "登录成功但获取版本失败"}
                else:
                    results["qbittorrent"] = {"success": False, "message": "用户名或密码错误"}
            else:
                results["qbittorrent"] = {"success": False, "message": "未配置认证信息"}
        except requests.RequestException as e:
            results["qbittorrent"] = {"success": False, "message": f"无法连接: {str(e)}"}
    else:
        results["qbittorrent"] = {"success": False, "message": "未配置 Host 地址"}

    # --- PirateBay ---
    piratebay_url = body.get("piratebay_url", "https://apibay.org/q.php")
    try:
        test_url = f"{piratebay_url.rstrip('/')}?q=test&cat=200"
        resp = requests.get(test_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                results["piratebay"] = {
                    "success": True,
                    "message": "连接成功",
                }
            else:
                results["piratebay"] = {"success": True, "message": "连接成功"}
        else:
            results["piratebay"] = {"success": False, "message": f"请求失败: HTTP {resp.status_code}"}
    except requests.RequestException as e:
        results["piratebay"] = {"success": False, "message": f"网络错误: {str(e)}"}

    # --- Anime Garden ---
    anime_url = body.get("anime_url", "https://animes.garden/api/resources")
    try:
        test_url = f"{anime_url.rstrip('/')}?search=test&pageSize=1"
        resp = requests.get(test_url, timeout=10)
        if resp.status_code == 200:
            results["anime_garden"] = {
                "success": True,
                "message": "连接成功",
            }
        else:
            results["anime_garden"] = {"success": False, "message": f"请求失败: HTTP {resp.status_code}"}
    except requests.RequestException as e:
        results["anime_garden"] = {"success": False, "message": f"网络错误: {str(e)}"}

    # --- ASSRT ---
    assrt_token = body.get("assrt_token", "") or config.get("subtitle.assrt.token", "")
    assrt_base_url = body.get("assrt_base_url", "") or config.get("subtitle.assrt.base_url", "https://api.assrt.net")
    if assrt_token:
        try:
            resp = requests.get(
                f"{assrt_base_url.rstrip('/')}/v1/user/quota",
                params={"token": assrt_token},
                timeout=10,
            )
            if resp.status_code == 200:
                results["assrt"] = {
                    "success": True,
                    "message": "连接成功",
                }
            else:
                results["assrt"] = {"success": False, "message": f"Token 无效: HTTP {resp.status_code}"}
        except requests.RequestException as e:
            results["assrt"] = {"success": False, "message": f"网络错误: {str(e)}"}
    else:
        results["assrt"] = {"success": False, "message": "未配置 Token"}

    all_success = all(v.get("success", False) for v in results.values())
    return BaseResponse.success(data={
        "results": results,
        "all_success": all_success,
    })


@router.post("/setup", response_model=BaseResponse, summary="一键初始化系统配置")
async def setup_system(body: Dict[str, Any] = Body(..., embed=False)):
    """接收引导页提交的完整设置，生成密钥并写入配置文件"""
    if _is_initialized():
        raise HTTPException(status_code=400, detail="系统已完成初始化，请直接登录")

    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    secret_key = body.get("secret_key", "").strip()
    qb_host = body.get("qb_host", "").strip()
    qb_username = body.get("qb_username", "").strip()
    qb_password = body.get("qb_password", "").strip()
    qb_api_key = body.get("qb_api_key", "").strip()
    tmdb_api_key = body.get("tmdb_api_key", "").strip()
    tmdb_api_domain = _strip_protocol(body.get("tmdb_api_domain", "https://api.themoviedb.org"))
    assrt_token = body.get("assrt_token", "").strip()
    assrt_base_url = body.get("assrt_base_url", "https://api.assrt.net")
    piratebay_url = body.get("piratebay_url", "https://apibay.org/q.php")
    anime_garden_url = body.get("anime_garden_url", "https://animes.garden/api/resources")

    # 路径配置
    download_root_path = body.get("download_root_path", "")
    target_root_path = body.get("target_root_path", "")
    root_path = body.get("root_path", "")
    default_download_path = body.get("default_download_path", "/temp")
    movie_download_path = body.get("movie_download_path", "/temp")
    tv_download_path = body.get("tv_download_path", "/temp")
    anime_download_path = body.get("anime_download_path", "/temp")
    temp_download_path = body.get("temp_download_path", "/temp")
    default_target_path = body.get("default_target_path", "/nas/movies")
    movie_target_path = body.get("movie_target_path", "/nas/movies")
    tv_target_path = body.get("tv_target_path", "/nas/tv")
    anime_target_path = body.get("anime_target_path", "/nas/anime")

    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if not secret_key or secret_key == "CHANGE_THIS_SECRET_KEY":
        raise HTTPException(status_code=400, detail="请设置一个安全的 JWT 密钥，不要使用默认值")
    if len(secret_key) < 16:
        raise HTTPException(status_code=400, detail="JWT 密钥长度至少 16 个字符，请重新生成")

    try:
        cfg = config.get_file_config()

        # 安全配置
        cfg.setdefault("security", {})
        cfg["security"]["username"] = username
        if password:
            if len(password) < 6:
                raise HTTPException(status_code=400, detail="密码长度至少 6 个字符")
            cfg["security"]["password"] = hash_password(password)
        cfg["security"]["secret_key"] = secret_key if secret_key else _generate_secret_key(32)

        # TMDB
        if tmdb_api_key:
            cfg.setdefault("tmdb", {})
            cfg["tmdb"]["api_key"] = tmdb_api_key
        if tmdb_api_domain:
            cfg.setdefault("tmdb", {})
            cfg["tmdb"]["api_domain"] = tmdb_api_domain

        # qBittorrent
        if qb_host:
            cfg.setdefault("qbittorrent", {})
            cfg["qbittorrent"]["host"] = qb_host
            cfg["qbittorrent"]["username"] = qb_username
            if qb_password:
                cfg["qbittorrent"]["password"] = qb_password
            if qb_api_key:
                cfg["qbittorrent"]["api_key"] = qb_api_key

        # ASSRT
        if assrt_token:
            cfg.setdefault("subtitle", {}).setdefault("assrt", {})
            cfg["subtitle"]["assrt"]["token"] = assrt_token
        if assrt_base_url:
            cfg.setdefault("subtitle", {}).setdefault("assrt", {})
            cfg["subtitle"]["assrt"]["base_url"] = assrt_base_url

        # PirateBay
        if piratebay_url:
            cfg.setdefault("piratebay", {})
            cfg["piratebay"]["url"] = piratebay_url

        # Anime Garden
        if anime_garden_url:
            cfg.setdefault("anime_garden", {})
            cfg["anime_garden"]["url"] = anime_garden_url

        # 路径配置
        cfg.setdefault("paths", {})
        cfg["paths"]["download_root_path"] = download_root_path
        cfg["paths"]["target_root_path"] = target_root_path
        cfg["paths"]["root_path"] = root_path
        cfg["paths"]["default_download_path"] = default_download_path
        cfg["paths"]["movie_download_path"] = movie_download_path
        cfg["paths"]["tv_download_path"] = tv_download_path
        cfg["paths"]["anime_download_path"] = anime_download_path
        cfg["paths"]["temp_download_path"] = temp_download_path
        cfg["paths"]["default_target_path"] = default_target_path
        cfg["paths"]["movie_target_path"] = movie_target_path
        cfg["paths"]["tv_target_path"] = tv_target_path
        cfg["paths"]["anime_target_path"] = anime_target_path

        config.save_file_config(cfg)
        tmdb_service.reload_config()
        assrt_service.reload_config()
        magnet_service.reload_config()
        task_service.reload_config()

        return BaseResponse.success(message="系统初始化完成，请使用设置的用户名和密码登录")
    except HTTPException:
        raise
    except Exception:
        logger.error(f"系统初始化失败", exc_info=True)
        raise HTTPException(status_code=500, detail="初始化失败，请稍后重试")


# ================================================================
# 显示偏好（无需 JWT 可读，写需要 JWT）
# ================================================================

@router.get("/preferences", response_model=BaseResponse, summary="获取显示偏好")
async def get_preferences():
    """返回 display 偏好配置（供各页面读取）"""
    show = config.get("display.show_zongzibay_chan", True)
    return BaseResponse.success(data={"show_zongzibay_chan": show})


@router.put("/preferences", response_model=BaseResponse, summary="保存显示偏好")
async def save_preferences(body: Dict[str, Any] = Body(..., embed=False)):
    """写入 display 偏好配置到文件"""
    try:
        cfg = config.get_file_config()
        cfg.setdefault("display", {})
        if "show_zongzibay_chan" in body:
            cfg["display"]["show_zongzibay_chan"] = bool(body["show_zongzibay_chan"])
        config.save_file_config(cfg)
        return BaseResponse.success(message="偏好已保存")
    except HTTPException:
        raise
    except Exception:
        logger.error(f"保存偏好失败", exc_info=True)
        raise HTTPException(status_code=500, detail="保存偏好失败，请稍后重试")
