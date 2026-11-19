---
name: docker-compose-test-env
description: 本地 Docker 集成测试环境：App+qBittorrent+Transmission+Aria2，测试脚本 script/test_downloaders.py
metadata:
  type: reference
---

## 两层测试

**Mock 单测（pytest）：** `tests/test_downloader_*.py` — 68 用例，mock 请求，不依赖外部服务。
```bash
python -m pytest tests/test_downloader_*.py -v
```

**真实集成测试（独立脚本）：** `script/test_downloaders.py` — 连真实 Docker 服务，每个下载器用独立 torrent 隔离。
```bash
docker compose up -d --build
$env:PYTHONIOENCODING = "utf-8"
python script/test_downloaders.py
```

## Docker 服务（docker-compose.yml）

| 服务 | 端口 | 凭据 |
|------|------|------|
| App | 8000 | admin / admin123 |
| qBittorrent | 8080 | admin / 见日志 `docker logs zongzibay-qbittorrent \| grep temporary` |
| Transmission | 9091 | admin / adminadmin |
| Aria2 | 6800 | RPC_SECRET=zongzibay_test |

qBittorrent 的 linuxserver 镜像 (5.1.4+) 不支持 WEBUI_PASSWORD env var，每次重建 volume 生成临时密码。
