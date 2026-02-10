# 本项目是一个还未完成开发的项目

# ZongziBay

ZongziBay 是一个自托管的媒体管理工具，集成了搜索、磁力链接管理、TMDB 元数据获取以及 qBittorrent 下载管理功能

## ✨ 主要功能

- **资源搜索**: 集成各类网站API进行种子搜索
- **媒体信息**: 对接 TMDB API 获取电影和电视剧的详细元数据（海报、简介等）
- **下载管理**: 与 qBittorrent 无缝集成，支持添加任务、监控进度
- **文件整理**: 自动将下载完成的文件整理到指定的电影或电视剧目录
- **现代化 UI**: 简洁美观的 Web 界面，支持深色模式

## 🚀 部署指南

### Docker 部署 (推荐)

本指引适用于使用打包好的镜像文件（如 `zongzibay_latest.tar`）或自行构建镜像进行部署

#### 1. 导入/获取镜像
如果您有离线镜像包：
```bash
docker load -i zongzibay_latest.tar
```
或者自行构建：
```bash
docker build -t zongzibay .
```

#### 2. 准备配置目录
在宿主机创建一个 `config` 目录，用于持久化保存配置文件和数据库
```bash
mkdir config
```

#### 3. 启动容器
```bash
docker run -d \
  --name zongzibay \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  zongzibay
```
*注：首次启动会自动在挂载的 `config` 目录下生成 `config.yml` 和 `ZongziBay.db`。*

### 本地开发运行

#### 后端 (FastAPI)
1. 确保安装 Python 3.12+。
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 启动服务：
   ```bash
   python -m app.main
   # 或者
   uvicorn app.main:app --reload
   ```
   后端服务默认运行在 `http://localhost:8000`。

#### 前端 (Nuxt 3)
1. 确保安装 Node.js 18+。
2. 进入 `web` 目录并安装依赖：
   ```bash
   cd web
   npm install
   ```
3. 启动开发服务器：
   ```bash
   npm run dev
   ```
   前端服务默认运行在 `http://localhost:3001`。

## ⚙️ 配置说明

首次运行后生成的 `config.yml` 包含以下核心配置项，请根据实际情况修改：

- **security**: 系统登录账号密码及 JWT 密钥（生产环境请务必修改 `secret_key`）
- **tmdb**: TMDB API Key（必需，用于获取媒体封面和信息）
- **qbittorrent**: qBittorrent WebUI 的地址和账号密码
- **piratebay**: 搜索源配置
- **paths**: 下载路径和归档路径映射
- **trackers**: 自定义 BT Tracker 列表以加速下载