# 测试说明

## 后端测试（pytest — 372 个用例）

### 测试文件总览

| 文件 | 覆盖范围 |
|------|----------|
| `test_api.py` | **API 冒烟**：健康检查、登录/失败、Cookie 设置、Refresh Token 刷新/无效/拒绝Access Token、Logout、Cookie+Header 双通道认证、中间件拦截、白名单放行（system/status, env-config, existing-config）、任务列表、通知列表、系统路径 |
| `test_security.py` | **JWT + 密码**：`create_access_token`/`create_refresh_token` 生成与解析、过期校验、Token 类型隔离（access/refresh 互斥）、`decode_refresh_token` 拒绝 Access Token、bcrypt `hash_password`/`verify_password`/`is_hashed`、旧版 PBKDF2 兼容验证（`is_pbkdf2_hash`）、明文密码回退、超长密码截断 |
| `test_auth_middleware.py` | **认证中间件**：白名单路径确认、`_verify_token_sync` 6 种场景（有效/Refresh拦截/无效/空值/用户名不匹配/无sub）、`_unauthorized` 响应格式 |
| `test_config.py` | **配置**：`_deep_merge_default` 合并、`Config.get` 点号键、`_all_keys_set` 叶子键、环境变量覆盖（ZONGZI_*，含 bool/int 类型转换） |
| `test_password_hash.py` | **PBKDF2 密码哈希**：`hash_password`（默认/自定义迭代/指定盐值/空密码异常）、`verify_password`（正确/错误/明文回退/Unicode/超长）、`_parse_hash`（有效/错误格式/边界）、`is_password_hash`、`PasswordHash` 编解码 |
| `test_rate_limiter.py` | **登录限流器**：单例模式、滑动窗口内放行、超限封禁、不同 IP 独立、封禁期满恢复、手动重置、mock time 模拟时间推进、窗口过期、过期清理 |
| `test_schemas.py` | **数据模型**：`ErrorCode` 枚举、`BaseResponse.success/fail`、`BusinessException` 构造（code/data/precedence）、Auth/Bangumi/TMDB Pydantic 模型校验 |
| `test_handlers.py` | **异常处理器**：`BusinessException` → BaseResponse、参数校验异常 → 40000、HTTP 异常 → 对应状态码、全局兜底 → 50000 |
| `test_qb_task.py` | **任务服务 + 监控**：`_append_trackers`、按 type 路径解析、`_norm_path` 路径规范化、`push_to_qb`（新任务/已存在跳过+恢复/路径不匹配+set_location/添加失败）、`cancel_task`（下载中删文件/做种中判断/已完成拒绝）、`_map_status`（含 checking/queuedUP/pausedUP）、qB 模拟（无种子时同步/重推、状态更新） |
| `test_task_monitor.py` | **任务监控**：单文件/嵌套/目录检测、移动 vs 复制决策、字幕任务移动/复制/重命名/源清理/目标已存在跳过、`_process_copy` 复制（含 file_tasks / 无 file_tasks 全目录复制） |
| `test_magnet_service.py` | **磁力**：`normalize_info_hash`（40/32 位、非法输入）、`MagnetService._append_trackers`（mock config） |
| `test_bangumi_service.py` | **Bangumi 番剧服务**（mock HTTP）：`get_calendar` 每日放送、`get_season` 历史季度（分页/TV/WEB过滤/去重/日期未定归类）、`get_subject` 条目详情、`_pick_image` 封面选择、`_weekday_from_date` 日期→星期 |
| `test_tmdb_service.py` | **TMDB 服务**（mock tmdbv3api）：搜索电影/剧集/混合、详情（含演员阵容）、英文标题提取（主标题/alternative_titles fallback）、趋势/热门/高分/TopRated/番剧、搜索建议补全、`reload_config` 域名配置 |
| `test_anime_garden_service.py` | **动漫花园服务**（mock HTTP）：`get_teams` 字幕组列表、`search` 关键字搜索/分页/字幕组筛选/空结果 |
| `test_piratebay_service.py` | **海盗湾服务**（mock HTTP）：`search` 关键字搜索、`_fix_name` 名称修正、`_generate_magnet_link` 磁链生成、params 模板解析、无结果/部分解析错误处理 |
| `test_assrt_service.py` | **ASSRT 字幕服务**（mock HTTP）：`search_subs`（关键词/文件/无封装）、`get_sub_detail`（含 filelist/producer）、`get_similar_subs`、`get_quota`、错误码处理（509/429）、Token 可用性检查、下载路径解析 |

### 运行方式

```bash
# 全部测试
python -m pytest tests/ -v

# 仅 API
python -m pytest tests/test_api.py -v

# 仅认证/安全
python -m pytest tests/test_security.py tests/test_auth_middleware.py -v

# 仅密码哈希
python -m pytest tests/test_password_hash.py -v

# 仅限流器
python -m pytest tests/test_rate_limiter.py -v

# 仅服务层 mock 测试
python -m pytest tests/test_bangumi_service.py tests/test_tmdb_service.py tests/test_anime_garden_service.py tests/test_piratebay_service.py tests/test_assrt_service.py -v

# 仅任务与 qB 模拟
python -m pytest tests/test_qb_task.py tests/test_task_monitor.py -v
```

---

## 前端测试（vitest — 76 个用例）

| 文件 | 覆盖范围 |
|------|----------|
| `utils/__tests__/renamer.test.ts` | **V2 智能重命名**（58 用例）：`getExt`、`parseYearFromFilename`、`applyTemplate`、电影/剧集/番剧模式、SxxExx/1x05/E0S01/中文集数/方括号集数、分辨率过滤、Season 0/OVA、字幕语言检测（CHS/CHT/JP/EN/双语/字幕组名过滤）、自定义模板、force overrides、**9 个流程测试**（美剧多集+字幕、番剧字幕匹配、电影+多语言字幕+Sample、剧场版电影格式、嵌套目录季号提取、OVA 特别篇、动漫花园中日双语繁简、全部 unchecked、default 兜底） |
| `utils/__tests__/crypto.test.ts` | **SHA-256**（6 用例）：hex 长度、确定性、不同输入、空字符串、中文、已知向量验证 |
| `lib/__tests__/renamer.test.ts` | **旧版重命名**（12 用例）：`getExt`、电影/剧集模式、字幕匹配、完整种子流程 |

### 运行方式

```bash
cd web

# 全部测试
npm run test

# 持续监听模式
npm run test:watch

# 仅重命名测试
npx vitest run app/utils/__tests__/renamer.test.ts

# 仅加密测试
npx vitest run app/utils/__tests__/crypto.test.ts
```

---

## CI/CD

GitHub Actions 工作流（`.github/workflows/test.yml`）在 push/PR 到 `main`/`master`/`develop` 时自动运行：

- **后端**：Python 3.11 + 3.12 矩阵，pytest 全部 372 个测试
- **前端**：Node 20，vitest 全部 76 个测试

两个 job 并行执行，fail-fast 关闭（一个版本失败不影响另一个）。

---

## 测试环境

- 后端测试使用临时 SQLite 数据库文件（见 `conftest.py`），不污染本地数据
- 异步模式：`asyncio_mode = auto`（见 `pytest.ini`）
- 前端测试使用 `happy-dom` 模拟浏览器环境
- 所有外部依赖（HTTP 请求、TMDB API、qBittorrent 等）均使用 mock 隔离
- 无需真实网络连接或外部服务
