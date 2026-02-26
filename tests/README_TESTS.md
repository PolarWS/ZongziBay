# 后端测试说明与建议

## 当前已有测试

| 文件 | 覆盖范围 |
|------|----------|
| `test_api.py` | API 冒烟：健康检查、登录/失败、/me 未授权/已授权、任务列表、通知列表、系统路径 |
| `test_task_monitor.py` | 任务监控：单文件/嵌套判断、移动 vs 复制决策、**字幕任务移动/复制**、**_process_copy 复制**（临时目录+假文件，不依赖 qB） |
| `test_magnet_service.py` | 磁力：`normalize_info_hash`（40/32 位）、`MagnetService._append_trackers`（mock config） |
| `test_security.py` | JWT：`create_access_token` 生成与可解析性、过期时间 |

## 建议补充的测试（按优先级）

### 高优先级（核心逻辑、易测、无外部依赖）

1. **`magnet_service` 单元测试**（`tests/test_magnet_service.py`）
   - `normalize_info_hash`：40 位 hex、32 位 Base32 转 hex、非法输入
   - `_append_trackers`：空/有 tracker 时磁链拼接（可 mock 配置）

2. **`task_service` 路径与 tracker 逻辑**（`tests/test_task_service.py`）
   - `_append_trackers`：与 magnet_service 类似，可单独测
   - 路径解析：`sourcePath`/`targetPath` 为空、相对、绝对时与 type（movie/tv/anime）的拼接（mock config + db，不调 qB）

3. **安全与 JWT**（`tests/test_security.py`）
   - `create_access_token` 生成、`get_current_user` 解析合法/过期/篡改 token（mock config 用户名）

### 中优先级（API 扩展、边界）

4. **API 路由补充**（在 `test_api.py` 或单独文件）
   - 任务：`POST /tasks/add`（mock task_service 或 qB）、`POST /tasks/cancel/{id}`（如可 mock）
   - 通知：`PUT /notifications/{id}/read`、`PUT /read_all`、`DELETE /{id}`、`GET /unread_count`
   - Magnet：`POST /magnet/parse`、`POST /magnet/download`（mock magnet_service）
   - 字幕：`GET /subtitle/sub/search`、`POST /subtitle/sub/download`（mock assrt_service）
   - 系统：`GET /system/rename-templates`、`GET /system/trackers`

5. **数据库层**（`tests/test_db.py`，使用 conftest 临时 DB）
   - 任务 CRUD：插入任务 + file_tasks、分页列表、更新状态、get_download_task_by_id
   - 通知：insert、分页、已读/全部已读、删除

### 低优先级（依赖外部服务，适合集成/手动）

6. **TMDB / 海盗湾 / 动漫花园 / Assrt 字幕**
   - 适合用 mock HTTP 响应测「解析与返回结构」，或标记为集成测试、需 mock 或 stub 服务。

7. **qBittorrent 相关**
   - `task_service.add_task`、`magnet_service.parse_magnet` 等真实调 qB 的流程，用 mock QB 客户端做单元测试；真实 qB 仅集成/手动验证。

## 运行方式

```bash
# 全部测试
python -m pytest tests/ -v

# 仅 API
python -m pytest tests/test_api.py -v

# 仅任务监控（含移动/复制）
python -m pytest tests/test_task_monitor.py -v
```

测试使用临时数据库（见 `conftest.py`），不污染本地数据。
