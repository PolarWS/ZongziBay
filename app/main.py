from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os
import mimetypes

# 修复 Windows 下 MIME 类型可能不正确的问题
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app.core import db
from app.core.handlers import register_exception_handlers
from app.api.v1.api import api_router
from app.services.task_monitor import task_monitor

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.init_db()
    task_monitor.start()
    yield
    # Shutdown
    task_monitor.stop()

app = FastAPI(
    title="ZongziBay",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI 文档地址
    redoc_url="/redoc",     # ReDoc 文档地址
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册路由
app.include_router(api_router, prefix="/api/v1")


# 静态文件服务配置
# 获取项目根目录 (app/main.py -> app/ -> root)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
            return FileResponse(index_path)
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
            return FileResponse(file_path)
            
        # 默认返回 index.html
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
            
        raise HTTPException(status_code=404, detail="Not Found")



if __name__ == "__main__":
    import uvicorn
    # 启动开发服务器
    # reload=True 仅在开发模式下开启
    uvicorn.run(app, host="127.0.0.1", port=8000)
