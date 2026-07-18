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
| **番剧推荐** | Bangumi (bgm.tv) 每日放送「本周新番」周历 |
| **Web 界面** | Nuxt 3 现代 UI，深色模式，设置页可在线编辑配置 |

## 技术栈

- **后端**: Python / FastAPI / SQLite  
- **前端**: Nuxt 3 / Vue 3 / Tailwind / shadcn-nuxt  
- **下载**: qBittorrent Web API  

---

## 使用与安装文档

#### 推荐阅读：《[ZongziBay 项目使用教程](/docs/usage_guide.md)》
#### 飞牛OS图片安装指南：《[飞牛OS (FNOS) 部署 ZongziBay 全攻略](https://blog.polarws.moe/articlePage/21)》

上述文档会从「准备工作 → Docker 部署 → Web 设置页配置」一步步带你跑通。

---

## 测试

### 后端（pytest）

```bash
python -m pytest tests/ -v
```

共 **372 个测试用例**，覆盖：
- API 冒烟测试（登录、Token 刷新、认证守卫、Cookie 认证）
- JWT 中间件（白名单、Token 类型隔离、OPTIONS 放行）
- 配置模块（默认合并、环境变量覆盖、完整性检测）
- 密码哈希（PBKDF2-SHA256 编解码/验证、bcrypt）
- 登录限流器（滑动窗口、封禁/解封、过期清理）
- 数据模型（BaseResponse、BusinessException、ErrorCode、Bangumi/TMDB Schemas）
- 异常处理器（业务异常、参数校验、HTTP 异常、全局兜底）
- 服务层 mock 测试（Bangumi、TMDB、动漫花园、海盗湾、ASSRT 字幕、磁力链接）
- qBittorrent 任务（TaskService：tracker 追加、路径解析、推送/取消、路径规范化）
- 任务监控（单文件/嵌套检测、移动/复制决策、字幕任务复制、文件整理）

### 前端（vitest）

```bash
cd web && npm run test
```

共 **76 个测试用例**，覆盖：
- `utils/renamer.ts` — 智能重命名（电影/剧集/番剧模式、S/E 解析、中文集数、语言检测、自定义模板、force overrides）
- `lib/renamer.ts` — 旧版重命名逻辑
- `utils/crypto.ts` — SHA-256 哈希（Web Crypto API + crypto-js 降级）
- **9 个流程测试**模拟真实种子下载场景（美剧多集、电影+字幕、番剧剧场版、动漫花园双语、OVA 特别篇等）

测试使用 mock 隔离外部依赖，不依赖真实网络或 qBittorrent 实例。更多说明见 《[测试说明](/docs/readme_test.md)》

---

## 项目结构

```
├── app/                 # FastAPI 后端
│   ├── api/v1/          # API 路由
│   ├── core/            # 配置、数据库、qB 客户端、鉴权、限流
│   ├── resources/       # 内置资源（默认配置）
│   ├── schemas/         # 请求/响应 Pydantic 模型
│   └── services/        # 任务、监控、磁力、字幕、TMDB、Bangumi 等业务逻辑
├── web/                 # Nuxt 3 前端
│   ├── app/
│   │   ├── components/  # Vue 组件
│   │   ├── composables/ # 组合式函数（useAuth 等）
│   │   ├── lib/         # 工具库（重命名等）
│   │   ├── pages/       # 页面路由
│   │   └── utils/       # 工具函数（重命名、加密等）
│   ├── vitest.config.ts # 前端测试配置
│   └── package.json
├── tests/               # 后端 pytest 测试（372 用例）
├── .github/workflows/   # CI/CD（前后端自动化测试）
└── requirements.txt
```

---

## 数据来源和友链

本项目的搜索与字幕能力依赖以下第三方服务以及社区支持，感谢其开放接口与社区贡献：

| 用途 | 名称 | 链接 |
|------|------|------|
| 动漫资源搜索 | 动漫花园 (Anime Garden) | [GitHub](https://github.com/animegarden) · [镜像站](https://animes.garden/) |
| 电影/剧集种子搜索 | 海盗湾 (The Pirate Bay) | [thepiratebay.org](https://thepiratebay.org/) |
| 字幕搜索与下载 | 射手网(伪) (Assrt) | [assrt.net](https://assrt.net/) |
| 番剧周历（每日放送） | Bangumi (番组计划) | [bgm.tv](https://bgm.tv/) · [API](https://github.com/bangumi/api) |
| 社区支持 | LinuxDo | [linux.do](https://linux.do/) |

---

## 许可证

[MIT License](LICENSE) · Copyright (c) 2026 PolarWS
