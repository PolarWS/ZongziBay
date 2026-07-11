# 测试说明

## 当前已有测试（共 133 个用例）

| 文件 | 覆盖范围 |
|------|----------|
| `test_api.py` | **API 冒烟**：健康检查、登录/失败、Cookie 设置、Refresh Token 刷新/无效/拒绝Access Token、Logout、Cookie+Header 双通道认证、中间件拦截、白名单放行（system/status, env-config, existing-config）、任务列表、通知列表、系统路径 |
| `test_security.py` | **JWT + 密码**：`create_access_token`/`create_refresh_token` 生成与解析、过期校验、Token 类型隔离（access/refresh 互斥）、`decode_refresh_token` 拒绝 Access Token、`hash_password`/`verify_password`/`is_hashed`、明文密码回退兼容、超长密码截断 |
| `test_auth_middleware.py` | **认证中间件**：白名单 10 个路径确认、`_verify_token_sync` 6 种场景（有效/Refresh拦截/无效/空值/用户名不匹配/无sub）、`_unauthorized` 响应格式 |
| `test_config.py` | **配置**：`_deep_merge_default` 合并、`Config.get` 点号键、`_all_keys_set` 叶子键、环境变量覆盖（ZONGZI_*，含 bool/int 类型转换） |
| `test_qb_task.py` | **任务服务 + 监控**：`_append_trackers`、按 type 路径解析、`_norm_path` 路径规范化、`push_to_qb`（新任务/已存在跳过+恢复/路径不匹配+set_location/添加失败）、`cancel_task`（下载中删文件/做种中判断/已完成拒绝）、`_map_status`（含 checking/queuedUP/pausedUP）、qB 模拟（无种子时同步/重推、状态更新） |
| `test_task_monitor.py` | **任务监控**：单文件/嵌套/目录检测、移动 vs 复制决策、字幕任务移动/复制/重命名/源清理/目标已存在跳过、`_process_copy` 复制（含 file_tasks / 无 file_tasks 全目录复制） |
| `test_magnet_service.py` | **磁力**：`normalize_info_hash`（40/32 位、非法输入）、`MagnetService._append_trackers`（mock config） |

## 建议补充的测试（按优先级）

### 高优先级（核心逻辑、易测、无外部依赖）

1. **数据库层**（`tests/test_db.py`，使用 conftest 临时 DB）
   - 任务 CRUD：插入任务 + file_tasks、分页列表、`get_tasks_by_hash`、更新状态、`get_download_task_by_id`
   - 通知：insert、分页、已读/全部已读、`get_unread_count`、删除

2. **API 路由补充**（在 `test_api.py` 或单独文件）
   - 通知：`PUT /notifications/{id}/read`、`PUT /read_all`、`DELETE /{id}`、`GET /unread_count`
   - 系统：`GET /system/rename-templates`、`GET /system/trackers`、`POST /system/setup`
   - 限流器：`POST /users/login` 频繁请求触达限流（`test_rate_limiter.py`）

### 中优先级（Mock 外部依赖）

3. **Magnet / 任务 API 扩展**
   - `POST /magnet/parse`、`POST /magnet/download`（mock MagnetService）
   - `POST /tasks/add`、`POST /tasks/cancel/{id}`（mock TaskService + qB）

4. **TMDB / 海盗湾 / 动漫花园 / Assrt**
   - 适合 mock HTTP 响应测「解析与返回结构」，保证上游 API 变更时能及早发现

### 低优先级（依赖外部服务，适合集成/手动）

5. **qBittorrent 真实集成**
   - 在有 qB 的环境中运行 `test_magnet_service.py` 和 `test_qb_task.py` 的真实流程，验证 set_location / add_torrent / delete_torrents 等交互

## 运行方式

```bash
# 全部测试（133 个用例）
python -m pytest tests/ -v

# 仅 API
python -m pytest tests/test_api.py -v

# 仅认证/安全
python -m pytest tests/test_security.py tests/test_auth_middleware.py -v

# 仅任务监控（含移动/复制）
python -m pytest tests/test_task_monitor.py -v

# 仅配置
python -m pytest tests/test_config.py -v

# 仅任务与 qB 模拟
python -m pytest tests/test_qb_task.py -v
```

## 测试环境

- 测试使用临时 SQLite 数据库文件（见 `conftest.py`），不污染本地数据
- 异步模式：`asyncio_mode = auto`（见 `pytest.ini`）
- 无需真实 qBittorrent / TMDB / 网络连接
