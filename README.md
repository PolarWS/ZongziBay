# ZongziBay（粽子湾）

> 自托管的媒体下载与管理工具：搜索种子、qBittorrent 下载、TMDB 元数据、字幕与智能重命名，一个 Web 界面搞定。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 功能

| 功能 | 说明 |
|------|------|
| **资源搜索** | 海盗湾、动漫花园等 API 搜索种子，支持电影 / 剧集 / 动漫 |
| **下载管理** | 对接 qBittorrent：添加任务、监控进度、做种到指定分享率后自动删除 |
| **文件整理** | 下载完成后按类型归档，支持复制或 qB 移动、智能重命名 |
| **字幕** | Assrt 字幕搜索与下载，字幕任务队列与自动移动重命名 |
| **媒体信息** | TMDB 海报、简介等元数据展示 |
| **Web 界面** | Nuxt 3 现代 UI，深色模式，设置页可在线编辑配置 |

## 技术栈

- **后端**: Python 3.12+ / FastAPI / SQLite  
- **前端**: Nuxt 3 / Vue 3 / Tailwind / shadcn-nuxt  
- **下载**: qBittorrent Web API  

---

## 前置要求

- 已安装并运行 [qBittorrent](https://www.qbittorrent.org/)
- [TMDB](https://www.themoviedb.org/) API Key（用于封面与元数据）
- [Assrt](https://assrt.net/) Token（用于字幕搜索）

---

## 快速开始

### Docker（推荐）

```bash
# 构建镜像
docker build -t zongzibay .

# 创建配置目录并启动
mkdir -p config
docker run -d \
  --name zongzibay \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  zongzibay
```

首次运行会在 `config` 目录下自动生成 `config.yml` 和 `ZongziBay.db`。浏览器访问 `http://localhost:8000`。

### 本地运行

**1. 后端**

```bash
pip install -r requirements.txt
python -m app.main
```

服务地址：`http://localhost:8000`，API 文档：`http://localhost:8000/docs`。

**2. 前端**

```bash
cd web
npm install
npm run dev
```

前端开发服务器：`http://localhost:3001`，会代理请求到后端。

**3. 环境变量（可选）**

- `APP_ENV=prod` — 加载 `config-prod.yml` 覆盖默认配置  
- `ZONGZI_*` — 按需覆盖配置项，例如：`ZONGZI_SECURITY_USERNAME=admin`  

---

## 配置

主配置为根目录或 Docker 内 `/app/config` 下的 `config.yml`。首次启动会根据 `config_default.yml` 自动补全缺失项。

| 配置项 | 说明 |
|--------|------|
| **security** | 登录账号、密码、JWT `secret_key`。生产环境请务必修改 `secret_key`。 |
| **qbittorrent** | WebUI 地址与账号；文件处理（复制/移动）、做种分享率与达标后是否删除。 |
| **tmdb** | API Key、语言（封面与元数据）。 |
| **paths** | 下载路径与归档目标路径（电影/剧集/动漫等）。 |
| **trackers** | 添加任务时自动追加的 BT Tracker 列表。 |
| **subtitle.assrt** | Assrt 字幕 API 的 token 与 base_url。 |

可在 Web 设置页中直接编辑并保存 `config.yml`；环境变量 `ZONGZI_*` 的覆盖仍然生效。

---

## 测试

```bash
python -m pytest tests/ -v
```

测试使用临时数据库，不影响本地数据。更多说明见 [tests/README_TESTS.md](tests/README_TESTS.md)。

---

## 项目结构

```
├── app/                 # FastAPI 后端
│   ├── api/v1/          # API 路由
│   ├── core/            # 配置、数据库、qB 客户端、鉴权
│   ├── schemas/         # 请求/响应模型
│   └── services/        # 任务、监控、磁力、字幕等业务逻辑
├── web/                 # Nuxt 3 前端
├── tests/               # pytest 测试
├── config_default.yml   # 默认配置模板（自动合并到 config.yml）
└── requirements.txt
```

---

## 数据来源

本项目的搜索与字幕能力依赖以下第三方服务，感谢其开放接口与社区贡献：

| 用途 | 名称 | 链接 |
|------|------|------|
| 动漫资源搜索 | 动漫花园 (Anime Garden) | [GitHub](https://github.com/animegarden) · [镜像站](https://animes.garden/) |
| 电影/剧集种子搜索 | 海盗湾 (The Pirate Bay) | [thepiratebay.org](https://thepiratebay.org/) |
| 字幕搜索与下载 | 射手网(伪) (Assrt) | [assrt.net](https://assrt.net/) |

---

## 许可证

[MIT License](LICENSE) · Copyright (c) 2026 PolarWS
