import logging
import mimetypes
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, Response

from app.api.v1.api import api_router
from app.core import db
from app.core.auth_middleware import JWTAuthMiddleware
from app.core.handlers import register_exception_handlers
from app.services.task_monitor import task_monitor

# 修复 Windows 下 MIME 类型可能不正确的问题
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")

# HTML 禁止缓存响应头，避免版本更新后用户被旧缓存"卡住"
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

def _file_response_with_nocache(filepath: str) -> Response:
    """返回带禁止缓存头的 FileResponse，用于 HTML 页面"""
    resp = FileResponse(filepath)
    resp.headers.update(_NO_CACHE_HEADERS)
    return resp
mimetypes.add_type("text/css", ".css")

# 配置日志格式
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    datefmt=_LOG_DATE_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],
)

# uvicorn 日志配置字典 — 统一格式，消除 uvicorn 默认的 INFO:     前缀
_UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": _LOG_FORMAT,
            "datefmt": _LOG_DATE_FORMAT,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
    },
}

logger = logging.getLogger("zongzibay")


# 获取项目根目录 (app/main.py -> app/ -> root)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_version():
    try:
        version_file = os.path.join(root_dir, "VERSION")
        if os.path.isfile(version_file):
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化数据库并启动任务监控
    logger.info(f"ZongziBay v{get_version()} 正在启动...")
    db.init_db()
    task_monitor.start()
    logger.info("服务已就绪，监听 http://127.0.0.1:8000")
    yield
    # 关闭：停止任务监控
    task_monitor.stop()
    logger.info("服务已停止")


# 根据环境变量控制是否启用 API 文档（生产环境关闭以减少攻击面）
_is_dev = os.getenv("APP_ENV", "").lower() in ("dev", "development", "")
_docs_enabled = _is_dev

app = FastAPI(
    title="ZongziBay",
    version=get_version(),
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    lifespan=lifespan
)

# 中间件顺序：后添加的先执行。先加 JWT，再加 CORS，这样 CORS 为最外层，能给所有响应加上 CORS 头。
app.add_middleware(JWTAuthMiddleware)

# 开发环境允许跨域请求的地址列表
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册路由
app.include_router(api_router, prefix="/api/v1")

# 静态文件服务配置
# Nuxt 打包输出目录
static_dir = os.path.join(root_dir, "web", ".output", "public")

if os.path.isdir(static_dir):
    # 挂载 Nuxt 的静态资源目录 _nuxt
    nuxt_assets_dir = os.path.join(static_dir, "_nuxt")
    if os.path.isdir(nuxt_assets_dir):
        app.mount("/_nuxt", StaticFiles(directory=nuxt_assets_dir), name="nuxt")
    
    # 根路径处理
    @app.get("/")
    async def serve_root():
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return _file_response_with_nocache(index_path)
        raise HTTPException(status_code=404, detail="Index not found")

    # 捕获所有其他路径，支持 SPA 路由
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # 如果请求的是 API 路径但未匹配到（404），则返回 404
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
            
        # 检查文件是否存在
        file_path = os.path.join(static_dir, path)
        if os.path.isfile(file_path):
            # HTML 文件禁止缓存，其他静态资源正常缓存
            if path.endswith(".html"):
                return _file_response_with_nocache(file_path)
            return FileResponse(file_path)
            
        # 默认返回 index.html（SPA fallback 禁止缓存）
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return _file_response_with_nocache(index_path)
            
        raise HTTPException(status_code=404, detail="Not Found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=_UVICORN_LOG_CONFIG)
