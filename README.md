<h1 align="center">ZongziBay（粽子湾）</h1>

<p align="center">
  <img src="/docs/image/ZongziBay_home.png" alt="Web 设置页示意">
</p>

<p align="center">
  自托管的媒体下载与管理工具<br>
  搜索种子、qBittorrent 下载、TMDB 元数据、字幕与智能重命名，一个 Web 界面搞定。
</p>

<p align="center">
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT">
  </a>
  <a href="https://hub.docker.com/r/polarws/zongzibay">
    <img src="https://img.shields.io/docker/pulls/polarws/zongzibay.svg" alt="Docker Pulls">
  </a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Nuxt-3-00DC82.svg?logo=nuxtdotjs&logoColor=white" alt="Nuxt 3">
  <img src="https://img.shields.io/badge/qBittorrent-API%20Integration-2E9FFF.svg?logo=qbittorrent&logoColor=white" alt="qBittorrent Integration">
</p>

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

- **后端**: Python / FastAPI / SQLite  
- **前端**: Nuxt 3 / Vue 3 / Tailwind / shadcn-nuxt  
- **下载**: qBittorrent Web API  

---

## 使用与安装文档

#### 推荐阅读：《[ZongziBay 项目使用教程](/docs/usage_guide.md)》

上述文档会从「准备工作 → Docker 部署 → Web 设置页配置」一步步带你跑通。

---

## 测试

```bash
python -m pytest tests/ -v
```

测试使用临时数据库，不影响本地数据。更多说明见 《[测试说明](/docs/readme_test.md)》

---

## 项目结构

```
├── app/                 # FastAPI 后端
│   ├── api/v1/          # API 路由
│   ├── core/            # 配置、数据库、qB 客户端、鉴权
│   ├── resources/       # 内置资源
│   ├── schemas/         # 请求/响应模型
│   └── services/        # 任务、监控、磁力、字幕等业务逻辑
├── web/                 # Nuxt 3 前端
├── tests/               # pytest 测试
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
