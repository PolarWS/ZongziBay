#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZongziBay 端到端全链路测试
==========================

覆盖真实用户路径的每一环：

    初始化 → 登录 → 搜索 → 磁力解析 → 提交下载 → 等待完成 → 重命名 → 归档移动

三个下载器后端（qbittorrent / transmission / aria2）各跑一遍，最后验证 MCP。

与 tests/docker/test_downloaders.py 的分工
------------------------------------------
那个脚本直接 import 下载器适配器，测的是「适配器本身能不能用」；
本脚本只走 HTTP API，测的是「这些零件拼起来能不能用」。

历史上漏掉的 bug 恰好都落在后者：
  · 环境变量预填把 qbittorrent.host 填成 localhost（容器里指向自己）
  · 保存配置后内存密码退回环境变量明文，导致初始化完登录不上
单测和适配器测试结构上都覆盖不到这类「组装」缺陷，所以需要这一层。

运行前提
--------
    docker compose -f tests/docker/docker-compose.yml up -d --build

用法
----
    python tests/docker/test_e2e_full.py                 # 完整跑一遍
    python tests/docker/test_e2e_full.py --reset         # 先重置到未初始化状态再跑
    python tests/docker/test_e2e_full.py -d qbittorrent  # 只测某个后端
    python tests/docker/test_e2e_full.py --skip-mcp      # 跳过 MCP 段
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time

import requests

# ======================== 环境参数 ========================
APP_CONTAINER = os.environ.get("ZONGZI_APP_CONTAINER", "zongzibay-app")
BASE = os.environ.get("ZONGZI_BASE_URL", "http://localhost:8000")
API = f"{BASE}/api/v1"

USERNAME = os.environ.get("ZONGZI_USER", "admin")
PASSWORD = os.environ.get("ZONGZI_PASSWORD", "admin123")
SECRET_KEY = os.environ.get("ZONGZI_SECRET_KEY", "test_secret_key_123456")

ALL_DOWNLOADERS = ["qbittorrent", "transmission", "aria2"]

# 三个下载器容器与 app 共享同一个卷，挂载点都是 /downloads。
# 因此推给下载器的路径必须写成容器内真实路径，且 download_root_path 留空
# （root 只在 app 与下载器看到的路径不一致时才需要）。
SHARED_ROOT = "/downloads"
DOWNLOAD_DIR = f"{SHARED_ROOT}/e2e/temp"
TARGET_DIR = f"{SHARED_ROOT}/e2e/nas"

# 选种约束：足够小以便快速跑完，又要有真实 peer 可连
# 做种者门槛不能太低：实测 5 seeders 的种子 DHT 里拉不到元数据，
# 解析会空转到超时——那是种子不可用，不是产品缺陷，会把测试结果带偏。
MAX_SIZE_MB = 900
MIN_SEEDERS = 15
SEARCH_QUERY = os.environ.get("ZONGZI_E2E_QUERY", "sintel")

# 等待下载的上限。600s 曾经不够：实测 qB 轮的 557MB 种子冷启动下载整整用了
# 600s（22:20:58 提交 → 22:30:50 完成），脚本恰好在 22:30:58 放弃，只差 8 秒，
# 于是把「下载慢」误报成失败并跳过后面的归档断言。同一网络下 transmission
# 只需 120s、aria2 88s，说明是 qB 建立 peer 慢，不是种子或链路问题。
DOWNLOAD_TIMEOUT = 1200    # 单个任务等待下载完成的上限（秒）
MOVE_TIMEOUT = 180         # 下载完成后再等重命名/归档的上限（秒）


# ======================== 结果记录 ========================
class Report:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), detail))
        mark = "✅" if ok else "❌"
        line = f"  {mark} {name}"
        if detail:
            line += f"  — {detail}"
        print(line, flush=True)
        return bool(ok)

    def fail(self, name, detail=""):
        return self.check(name, False, detail)

    def summary(self):
        passed = sum(1 for _, ok, _ in self.rows if ok)
        total = len(self.rows)
        print("\n" + "=" * 64)
        print(f"结果汇总: {passed}/{total} 通过")
        if passed != total:
            print("\n失败项:")
            for name, ok, detail in self.rows:
                if not ok:
                    print(f"  ❌ {name}  — {detail}")
        print("=" * 64)
        return passed == total


RPT = Report()


# ======================== 工具函数 ========================
def sha256(text: str) -> str:
    """前端在提交密码前会做一次 SHA-256，后端再做 bcrypt。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def docker_exec(*args, timeout=120):
    """在 app 容器内执行命令，返回 CompletedProcess。

    显式指定 utf-8：Windows 默认按 GBK 解码，容器输出里的中文会直接报错。
    """
    return subprocess.run(
        ["docker", "exec", APP_CONTAINER, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )


def container_path_exists(path: str) -> bool:
    return docker_exec("test", "-e", path).returncode == 0


def container_list_dir(path: str):
    r = docker_exec("sh", "-c", f"find {shlex_quote(path)} -maxdepth 3 2>/dev/null")
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def shlex_quote(s: str) -> str:
    """最小可用的 shell 引号转义（路径里有空格，不能直接拼）。"""
    return "'" + str(s).replace("'", "'\\''") + "'"


# ======================== API 客户端 ========================
class Api:
    def __init__(self):
        self.s = requests.Session()

    def login(self):
        r = self.s.post(
            f"{API}/users/login",
            data={"username": USERNAME, "password": sha256(PASSWORD)},
            timeout=20,
        )
        r.raise_for_status()
        body = r.json()
        token = (body.get("data") or {}).get("access_token")
        if not token:
            raise RuntimeError(f"登录响应里没有 access_token: {body}")
        self.s.headers["Authorization"] = f"Bearer {token}"
        return token

    def get(self, path, **kw):
        return self.s.get(f"{API}{path}", timeout=kw.pop("timeout", 60), **kw)

    def post(self, path, **kw):
        return self.s.post(f"{API}{path}", timeout=kw.pop("timeout", 60), **kw)

    def put(self, path, **kw):
        return self.s.put(f"{API}{path}", timeout=kw.pop("timeout", 60), **kw)

    def data(self, resp):
        body = resp.json()
        if body.get("code") not in (200, None):
            raise RuntimeError(f"接口返回错误 {body.get('code')}: {body.get('message')}")
        return body.get("data")


# ======================== 阶段 1：重置与初始化 ========================
# 测试环境凭据（与 setup 提交的一致；docker-compose 的服务名即容器内可达地址）
QB_HOST = "http://qbittorrent:8080"
TR_HOST = "http://transmission:9091"
ARIA2_HOST = "http://aria2:6800"
QB_USER, QB_PASSWORD = "admin", os.environ.get("ZONGZI_QB_PASSWORD", "nzN3M8FW7")
TR_USER, TR_PASSWORD = "admin", "adminadmin"
ARIA2_SECRET = "zongzibay_test"

# 在 app 容器内执行：清空三个下载器里的全部种子。
# 必须走容器内网络——qBittorrent 会因宿主机 IP 认证失败次数过多而封禁该 IP。
_PURGE_DOWNLOADERS_PY = r'''
import requests


def _log(msg):
    print("[purge] " + str(msg))


try:
    s = requests.Session()
    s.post("__QB_HOST__/api/v2/auth/login",
           data={"username": "__QB_USER__", "password": "__QB_PASS__"}, timeout=20)
    r = s.post("__QB_HOST__/api/v2/torrents/delete",
               data={"hashes": "all", "deleteFiles": "true"}, timeout=60)
    _log("qBittorrent 已清空 (HTTP %s)" % r.status_code)
except Exception as e:
    _log("qBittorrent 跳过: %s" % e)

try:
    ts = requests.Session()
    ts.auth = ("__TR_USER__", "__TR_PASS__")
    url = "__TR_HOST__/transmission/rpc"

    def trpc(method, args=None):
        for _ in range(2):
            r = ts.post(url, json={"method": method, "arguments": args or {}}, timeout=20)
            if r.status_code == 409:
                ts.headers["X-Transmission-Session-Id"] = r.headers["X-Transmission-Session-Id"]
                continue
            return r.json()
        return {}

    ids = [x["id"] for x in
           trpc("torrent-get", {"fields": ["id"]}).get("arguments", {}).get("torrents", [])]
    if ids:
        trpc("torrent-remove", {"ids": ids, "delete-local-data": True})
    _log("Transmission 已清空 (%d 个)" % len(ids))
except Exception as e:
    _log("Transmission 跳过: %s" % e)

try:
    def arpc(method, params=None):
        return requests.post(
            "__ARIA2_HOST__/jsonrpc",
            json={"jsonrpc": "2.0", "id": "1", "method": method,
                  "params": ["token:__ARIA2_SECRET__"] + (params or [])},
            timeout=20).json()

    for g in [x["gid"] for x in arpc("aria2.tellActive").get("result", [])]:
        arpc("aria2.remove", [g])
        arpc("aria2.forceRemove", [g])
    for g in [x["gid"] for x in arpc("aria2.tellWaiting", [0, 100]).get("result", [])]:
        arpc("aria2.remove", [g])
    arpc("aria2.purgeDownloadResult")
    _log("Aria2 已清空")
except Exception as e:
    _log("Aria2 跳过: %s" % e)
'''
for _ph, _val in (("__QB_HOST__", QB_HOST), ("__QB_USER__", QB_USER),
                  ("__QB_PASS__", QB_PASSWORD), ("__TR_HOST__", TR_HOST),
                  ("__TR_USER__", TR_USER), ("__TR_PASS__", TR_PASSWORD),
                  ("__ARIA2_HOST__", ARIA2_HOST), ("__ARIA2_SECRET__", ARIA2_SECRET)):
    _PURGE_DOWNLOADERS_PY = _PURGE_DOWNLOADERS_PY.replace(_ph, _val)

# 磁力解析失败时打印三个下载器的现场。
# 解析依赖 DHT/peer，是整条链路里唯一不可控的一环：只留一句「等待元数据超时」，
# 分不清是种子没人做种、下载器没连上网，还是代码本身的问题。
_PARSE_DIAG_PY = r'''
import requests


def _p(msg):
    print("  " + str(msg))


try:
    s = requests.Session()
    s.post("__QB_HOST__/api/v2/auth/login",
           data={"username": "__QB_USER__", "password": "__QB_PASS__"}, timeout=20)
    ti = s.get("__QB_HOST__/api/v2/transfer/info", timeout=20).json()
    _p("qB connection=%s dht_nodes=%s"
       % (ti.get("connection_status"), ti.get("dht_nodes")))
    for t in s.get("__QB_HOST__/api/v2/torrents/info", timeout=20).json():
        _p("qB state=%s total_size=%s peers=%s seeds=%s dht=%s name=%s"
           % (t.get("state"), t.get("total_size"), t.get("num_leechs"),
              t.get("num_seeds"), t.get("dht"), str(t.get("name"))[:36]))
        trs = s.get("__QB_HOST__/api/v2/torrents/trackers",
                    params={"hash": t["hash"]}, timeout=20).json()
        _p("qB trackers=%d working=%d"
           % (len(trs), len([x for x in trs if x.get("status") == 2])))
        for x in trs[:4]:
            _p("     [%s] %s | %s" % (x.get("status"), str(x.get("url"))[:46],
                                      str(x.get("msg"))[:38]))
except Exception as e:
    _p("qB 诊断失败: %s" % e)

try:
    def trpc(method, args=None):
        body = {"method": method, "arguments": args or {}}
        r = requests.post("__TR_HOST__/transmission/rpc", json=body,
                          auth=("__TR_USER__", "__TR_PASS__"), timeout=20)
        if r.status_code == 409:
            r = requests.post(
                "__TR_HOST__/transmission/rpc", json=body,
                headers={"X-Transmission-Session-Id":
                         r.headers.get("X-Transmission-Session-Id")},
                auth=("__TR_USER__", "__TR_PASS__"), timeout=20)
        return r.json()

    got = trpc("torrent-get",
               {"fields": ["name", "status", "totalSize", "percentDone"]})
    for t in (got.get("arguments") or {}).get("torrents", []):
        _p("tr status=%s totalSize=%s name=%s"
           % (t.get("status"), t.get("totalSize"), str(t.get("name"))[:36]))
except Exception as e:
    _p("Transmission 诊断失败: %s" % e)

try:
    def arpc(method, params=None):
        return requests.post(
            "__ARIA2_HOST__/jsonrpc",
            json={"jsonrpc": "2.0", "id": "1", "method": method,
                  "params": ["token:__ARIA2_SECRET__"] + (params or [])},
            timeout=20).json()

    for m, a in (("aria2.tellActive", None), ("aria2.tellWaiting", [0, 50])):
        for t in arpc(m, a).get("result", []):
            files = t.get("files") or [{}]
            _p("aria2 %s status=%s names=%s"
               % (m.split(".")[-1], t.get("status"),
                  [f.get("path", "").split("/")[-1] for f in files][:3]))
except Exception as e:
    _p("Aria2 诊断失败: %s" % e)
'''
for _ph, _val in (("__QB_HOST__", QB_HOST), ("__QB_USER__", QB_USER),
                  ("__QB_PASS__", QB_PASSWORD), ("__TR_HOST__", TR_HOST),
                  ("__TR_USER__", TR_USER), ("__TR_PASS__", TR_PASSWORD),
                  ("__ARIA2_HOST__", ARIA2_HOST), ("__ARIA2_SECRET__", ARIA2_SECRET)):
    _PARSE_DIAG_PY = _PARSE_DIAG_PY.replace(_ph, _val)


def dump_parse_context():
    """打印三个下载器的当前状态，用于磁力解析失败时定位原因。"""
    print("  ---- 失败现场 ----")
    r = docker_exec("python", "-c", _PARSE_DIAG_PY, timeout=120)
    out = (r.stdout or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print(f"  (诊断退出码 {r.returncode}) {(r.stderr or '').strip()[:300]}")


def reset_to_uninitialized():
    """回到「首次启动」状态：清空下载器与共享卷残留 → 删配置与数据库 → 重启 app。

    这是唯一能真正验证初始化流程的办法——否则 setup 接口会因
    「系统已完成初始化」直接 400。

    下载器里的种子必须一起清：同一个 hash 的旧种子会被 add_task 判定为
    「已存在」而复用它的数据和 save_path，测试会拿旧文件假装成一次新下载。
    """
    print("\n[重置] 清空下载器中的残留种子…")
    r = docker_exec("python", "-c", _PURGE_DOWNLOADERS_PY, timeout=180)
    for line in (r.stdout or "").splitlines():
        if line.strip():
            print(f"       {line.strip()}")
    if r.returncode != 0:
        print(f"       (purge 退出码 {r.returncode}) {(r.stderr or '').strip()[:200]}")

    print("[重置] 清空共享卷中的测试目录…")
    docker_exec("sh", "-c", f"rm -rf {shlex_quote(SHARED_ROOT + '/e2e')}")

    print("[重置] 清除配置与数据库，重启 app 容器…")
    docker_exec("sh", "-c", "rm -f /app/config/config.yml /app/config/ZongziBay.db")
    subprocess.run(["docker", "restart", APP_CONTAINER],
                   capture_output=True, text=True, timeout=180)

    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            r = requests.get(f"{API}/system/status", timeout=10)
            if r.status_code == 200:
                print(f"[重置] app 已就绪: {r.text[:120]}")
                return True
        except Exception:
            pass
        time.sleep(3)
    print("[重置] 等待 app 就绪超时")
    return False


def step_setup(api, reset=False):
    """初始化：未初始化时提交引导页配置。"""
    print("\n" + "=" * 64)
    print("阶段 1/6  初始化")
    print("=" * 64)

    if reset:
        if not reset_to_uninitialized():
            RPT.fail("重置到未初始化状态")
            return False
    else:
        st = api.get("/system/status").json()
        if (st.get("data") or {}).get("initialized"):
            RPT.check("系统已初始化（跳过 setup，如需完整验证请加 --reset）", True)
            return True

    body = {
        "username": USERNAME,
        "password": sha256(PASSWORD),  # 前端同样先做 SHA-256
        "secret_key": SECRET_KEY,
        "qb_host": QB_HOST,
        "qb_username": QB_USER,
        "qb_password": QB_PASSWORD,
        "downloader": {
            "active": "qbittorrent",
            "transmission": {"host": TR_HOST, "username": TR_USER, "password": TR_PASSWORD},
            "aria2": {"host": ARIA2_HOST, "secret": ARIA2_SECRET},
        },
        # 三个容器共享 /downloads，路径写成容器内绝对路径，root 留空
        "download_root_path": "", "target_root_path": "", "root_path": "",
        "default_download_path": DOWNLOAD_DIR, "movie_download_path": DOWNLOAD_DIR,
        "tv_download_path": DOWNLOAD_DIR, "anime_download_path": DOWNLOAD_DIR,
        "temp_download_path": DOWNLOAD_DIR,
        "default_target_path": TARGET_DIR, "movie_target_path": TARGET_DIR,
        "tv_target_path": f"{SHARED_ROOT}/e2e/nas/tv",
        "anime_target_path": f"{SHARED_ROOT}/e2e/nas/anime",
    }
    r = api.post("/system/setup", json=body)
    ok = r.status_code == 200 and (r.json().get("code") == 200)
    RPT.check("提交初始化配置", ok, r.text[:160])
    if not ok:
        return False

    st = api.get("/system/status").json()
    RPT.check("初始化状态写入", (st.get("data") or {}).get("initialized") is True,
              json.dumps(st.get("data"), ensure_ascii=False))
    # 路径配置的校验放在登录之后（/system/paths 需要认证）
    return True


# ======================== 阶段 2：登录 ========================
def step_login(api):
    print("\n" + "=" * 64)
    print("阶段 2/6  登录")
    print("=" * 64)

    # 错误密码必须被拒绝（本项目业务异常统一返回 HTTP 200 + 非 200 业务 code）
    bad = requests.post(f"{API}/users/login",
                        data={"username": USERNAME, "password": sha256("wrong-password")},
                        timeout=20)
    try:
        bad_code = (bad.json() or {}).get("code")
    except ValueError:
        bad_code = None
    RPT.check("错误密码被拒绝", bad_code not in (None, 200),
              f"HTTP {bad.status_code}, code={bad_code}")

    try:
        api.login()
        RPT.check("用 SHA-256 密码登录成功", True)
    except Exception as e:
        RPT.fail("用 SHA-256 密码登录成功", str(e))
        return False

    me = api.get("/users/me")
    RPT.check("Token 可访问受保护接口", me.status_code == 200, me.text[:120])

    # 初始化时写入的路径配置应已持久化（/system/paths 需登录后才能读）
    paths = api.data(api.get("/system/paths"))
    RPT.check("路径配置已持久化", paths.get("movie_download_path") == DOWNLOAD_DIR,
              f"movie_download_path={paths.get('movie_download_path')}")
    return True


# ======================== 阶段 3：搜索 ========================
def pick_torrent(api, magnet_override=None):
    """通过项目自己的搜索接口挑一个「小且热」的种子。

    刻意不在代码里硬编码磁力链接：公开种子会失效，而且把具体盗版资源写进
    仓库也不合适。运行时挑选顺带把搜索接口也覆盖了。
    """
    print("\n" + "=" * 64)
    print("阶段 3/6  搜索并挑选种子")
    print("=" * 64)

    if magnet_override:
        RPT.check("使用命令行指定的磁力链接", True, magnet_override[:70])
        return magnet_override

    r = api.get("/piratebay/search", params={"q": SEARCH_QUERY}, timeout=60)
    items = api.data(r) or []
    RPT.check("搜索接口返回结果", len(items) > 0, f"关键词={SEARCH_QUERY!r}，{len(items)} 条")
    if not items:
        return None

    def size_mb(x):
        return int(x.get("size") or 0) / 1024 / 1024

    viable = [x for x in items
              if x.get("magnet") and size_mb(x) <= MAX_SIZE_MB
              and int(x.get("seeders") or 0) >= MIN_SEEDERS]
    if not viable:
        # 刻意不退回冷门种子：做种者太少时元数据/DHT 都拉不动，
        # 测出来的失败反映的是种子不可用，而不是产品缺陷。
        RPT.fail("找到满足体积/热度约束的种子",
                 f"约束: ≤{MAX_SIZE_MB}MB, ≥{MIN_SEEDERS} seeders，"
                 f"{len(items)} 条结果无一满足（可调 ZONGZI_E2E_QUERY 换关键词）")
        return None

    # 热度达标后，体积小的优先——先保可用性，再求快
    viable.sort(key=lambda x: (size_mb(x), -int(x.get("seeders") or 0)))
    pick = viable[0]
    RPT.check("找到满足体积/热度约束的种子", True,
              f"{pick['name'][:48]} | {size_mb(pick):.0f}MB | "
              f"seeders={pick.get('seeders')} | 候选 {len(viable)} 个")
    return pick["magnet"]


def step_parse(api, magnet):
    print("\n" + "=" * 64)
    print("阶段 4/6  磁力解析")
    print("=" * 64)
    r = api.post("/magnet/parse", json={"magnet_link": magnet}, timeout=180)
    try:
        data = api.data(r)
    except RuntimeError:
        dump_parse_context()
        raise
    files = (data or {}).get("files") or []
    RPT.check("解析出文件列表", len(files) > 0, f"{len(files)} 个文件")
    if not files:
        dump_parse_context()
    if files:
        RPT.check("文件条目含 name/path/size",
                  all(k in files[0] for k in ("name", "path", "size")),
                  json.dumps(files[0], ensure_ascii=False)[:120])
    return files


# ======================== 阶段 5：下载 → 重命名 → 归档 ========================
def switch_downloader(api, name, use_move=False):
    """切换后端。use_move=True 时关掉 use_copy，让支持 set_location 的后端走「移动」归档。

    默认 use_copy=true 且本测试种子带 Screens/ 子目录时，
    task_monitor._handle_completed_task 的 use_qb_move 判据
    `(use_copy and not has_any_folder) or (not use_copy)` 恒为 False，
    移动分支永远不会被走到——这正是此前「移动」从未被端到端覆盖的原因。
    """
    cfg = api.data(api.get("/system/config"))
    cfg.setdefault("downloader", {})["active"] = name
    cfg.setdefault("qbittorrent", {}).setdefault("file_handling", {})["use_copy"] = not use_move
    # 只补默认值、不做清洗：地址归一化（去首尾空白/末尾斜杠）由后端负责，
    # 这样脏数据一旦回归就能被下面的断言抓到。
    tr = cfg["downloader"].setdefault("transmission", {})
    tr.setdefault("host", TR_HOST)
    tr.setdefault("username", TR_USER)
    tr.setdefault("password", TR_PASSWORD)
    ar = cfg["downloader"].setdefault("aria2", {})
    ar.setdefault("host", ARIA2_HOST)
    ar.setdefault("secret", ARIA2_SECRET)
    # 测试期间不要因分享率达标把源文件删掉，否则没法校验重命名结果
    cfg.setdefault("qbittorrent", {}).setdefault("seeding", {})
    cfg["qbittorrent"]["seeding"]["limit_ratio"] = -1
    cfg["qbittorrent"]["seeding"]["delete_on_ratio_reached"] = False
    r = api.put("/system/config", json=cfg)
    if r.status_code != 200:
        return False

    # 落库的地址必须是归一化过的
    saved = (api.data(api.get("/system/config")) or {}).get("downloader") or {}
    for backend in ("transmission", "aria2"):
        host = (saved.get(backend) or {}).get("host") or ""
        if host != host.strip().rstrip("/"):
            RPT.fail(f"[{name}] 下载器地址归一化", f"{backend}.host={host!r} 仍含多余空白")
            return False
    return True


def build_file_tasks(files):
    """给主视频和 nfo 起新名字，其余保持原名。

    file_rename 不含 '/' 时只替换文件名、保留原目录——正好用来验证
    「重命名」这一步真的作用到了下载器里。
    """
    out = []
    for f in files:
        path = f["path"]
        rename = ""
        if path.lower().endswith(".mkv"):
            rename = "Renamed (2010).mkv"
        elif path.lower().endswith(".nfo"):
            rename = "Renamed (2010).nfo"
        out.append({"sourcePath": path, "targetPath": "", "file_rename": rename})
    return out


def wait_for_status(api, task_id, want, timeout):
    """轮询任务，直到到达期望状态或超时。返回 (最终状态, 任务对象)。"""
    terminal = {"completed", "error", "cancelled", "fetching_metadata_failed"}
    t0 = time.time()
    last = None
    task = None
    while time.time() - t0 < timeout:
        items = (api.data(api.get("/tasks/list", params={"page": 1, "page_size": 100})) or {}).get("items") or []
        me = [x for x in items if x["id"] == task_id]
        if not me:
            return "gone", None
        task = me[0]
        st = task["taskStatus"]
        if st != last:
            print(f"      [{int(time.time() - t0):>4}s] {st}  {task.get('taskInfo')}", flush=True)
            last = st
        if st == want or st in terminal:
            return st, task
        time.sleep(8)
    return last, task


def run_pipeline(api, downloader, magnet, files, seen_ids=None, use_move=False):
    """对单个下载器跑：切换后端 → 提交任务 → 等下载 → 等重命名/归档 → 校验磁盘。

    seen_ids：本次运行已用过的 task_id 集合。三个后端跑同一个磁力时，只要上一轮
    任务还没到终态，add_task 就会按 hash 判重直接复用它的 id —— 本轮变成空跑，
    却会伪装成「下载完成、归档失败」，极难排查。
    """
    print("\n" + "-" * 64)
    print(f"下载器后端: {downloader}")
    print("-" * 64)

    if not switch_downloader(api, downloader, use_move=use_move):
        RPT.fail(f"[{downloader}] 切换下载器后端")
        return

    # 支持 rename / set_location 的后端走移动，Aria2 两者皆无 → 走复制归档降级
    ok_conn = api.data(api.post("/system/test-connection",
                                json={"downloader": {"active": downloader}}, timeout=120))
    qb_res = ((ok_conn or {}).get("results") or {}).get("qbittorrent") or {}
    RPT.check(f"[{downloader}] 后端连接正常", qb_res.get("success") is True,
              str(qb_res.get("message"))[:90])

    # 每个后端用独立的下载/归档目录，避免与上一轮的残留互相干扰
    src = f"{DOWNLOAD_DIR}/{downloader}"
    tgt_name = f"Renamed Movie [{downloader}]"
    body = {
        "taskName": f"E2E {downloader}",
        "taskInfo": "e2e-full",
        "sourceUrl": magnet,
        "sourcePath": src,
        "targetPath": tgt_name,
        "file_tasks": build_file_tasks(files),
        "type": "movie",
    }
    r = api.post("/tasks/add", json=body, timeout=60)
    if r.status_code != 200 or r.json().get("code") != 200:
        RPT.fail(f"[{downloader}] 提交下载任务", r.text[:180])
        return
    task_id = api.data(r)
    if seen_ids is not None:
        if task_id in seen_ids:
            RPT.fail(f"[{downloader}] 提交下载任务",
                     f"task_id={task_id} 与前一个后端相同——app 按 hash 判重复用了旧任务，"
                     f"本轮并未真实下载（上一轮多半没到终态）")
            return
        seen_ids.add(task_id)
    RPT.check(f"[{downloader}] 提交下载任务", True, f"task_id={task_id}")

    # --- 等待下载完成 ---
    # 必须等到 completed，不能提前接受 moving：moving 期间任务在 DB 里仍算「活跃」，
    # 下一轮换后端提交同一磁力时会被 add_task 判重、直接复用上一轮的任务，
    # 表现为后一个下载器「秒完成」却什么都没下。
    st, task = wait_for_status(api, task_id, "completed", DOWNLOAD_TIMEOUT)
    if st not in ("completed", "seeding"):
        hint = ""
        if st == "fetching_metadata":
            # 常见死锁：提交了 file_tasks 时，push_to_downloader 会按后端能力二选一：
            #   暂停态能拉元数据 → 「暂停添加 → 等元数据筛文件 → 恢复」
            #   仅运行态能拉元数据 → 「正常添加 → 等元数据筛文件」
            # 若能力标记与后端实际行为不符（把暂停态拉不到元数据的后端标成能），
            # 元数据永远等不到，必然超时。
            hint = ("（疑似卡在「等元数据筛文件」死锁：元数据始终拉不到。"
                    "检查 app/core/downloader/ 下该后端的 supports_paused_metadata / "
                    "supports_runtime_file_selection 是否与实际行为一致）")
        RPT.fail(f"[{downloader}] 下载完成", f"最终状态={st} {hint}")
        return
    RPT.check(f"[{downloader}] 下载完成", True)

    # --- 等重命名 + 归档（monitor 每 10s 一轮，完成后状态才落 final）---
    deadline = time.time() + MOVE_TIMEOUT
    target_path = f"{TARGET_DIR}/{tgt_name}"
    renamed_ok = archived_ok = False
    while time.time() < deadline:
        if container_path_exists(f"{target_path}/Renamed (2010).mkv"):
            renamed_ok = archived_ok = True
            break
        # Aria2 不支持种子内重命名：复制归档时按 file_rename 改名，源文件保持原名
        if container_path_exists(target_path) and downloader == "aria2":
            files_in_target = container_list_dir(target_path)
            renamed_ok = any("Renamed" in p for p in files_in_target)
            archived_ok = renamed_ok
            if archived_ok:
                break
        time.sleep(6)

    if downloader == "aria2":
        # Aria2 capabilities: supports_rename=False / supports_set_location=False
        RPT.check(f"[{downloader}] 按 file_rename 归档（复制降级路径）", archived_ok,
                  f"目标目录 {target_path}")
    else:
        RPT.check(f"[{downloader}] 文件已重命名", renamed_ok,
                  f"期望 {target_path}/Renamed (2010).mkv")
        RPT.check(f"[{downloader}] 已归档到目标文件夹", archived_ok,
                  target_path)

    # 复制路径必须把「没有改名要求」的文件也一并归档。
    # 回归：_process_copy 曾对空 file_rename 直接 continue，于是只有主视频和 nfo
    # 被搬走，字幕/截图/样片静默丢失——aria2 只能走复制，用户根本无从察觉。
    # 移动路径是整目录搬家，天然不会暴露这个问题，所以只对复制路径断言。
    unrenamed = sorted({
        os.path.basename(f["path"].replace("\\", "/"))
        for f in files
        if not f["path"].lower().endswith((".mkv", ".nfo"))
    })
    if downloader != "qbittorrent" and unrenamed:
        # 复制归档是平铺的：文件直接落在目标目录下，不保留种子内的子目录层级
        landed = [n for n in unrenamed
                  if container_path_exists(f"{target_path}/{n}")]
        RPT.check(f"[{downloader}] 未改名的文件也已归档", bool(landed),
                  f"{len(landed)}/{len(unrenamed)} 个" if landed
                  else f"目标目录缺少 {unrenamed}")

    if use_move:
        # 移动的决定性证据：下载目录被搬空。复制会原样留下源文件，
        # 只看目标目录有文件无法区分二者。
        # find 总会把路径自身也算进去，先剔除才能判断目录是否真的空了。
        leftover = [p for p in container_list_dir(src) if p.rstrip("/") != src.rstrip("/")]
        RPT.check(f"[{downloader}] 源目录已清空（确系移动而非复制）", not leftover,
                  f"{src} 残留 {leftover[:4]}" if leftover else src)

    print(f"      目标目录内容: {container_list_dir(target_path)[:6]}")


# ======================== 阶段 6：MCP ========================
def step_mcp(api):
    print("\n" + "=" * 64)
    print("阶段 6/6  MCP")
    print("=" * 64)

    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except Exception as e:
        RPT.fail("mcp 客户端可用", f"{type(e).__name__}: {e}")
        return

    # read 权限 token：用于验证「权限不足」的拒绝路径
    read_tok = api.data(api.post("/api-tokens",
                                 json={"name": "e2e-read", "scopes": "read"}))["token"]
    dl_tok = api.data(api.post("/api-tokens",
                               json={"name": "e2e-download", "scopes": "download"}))["token"]
    RPT.check("创建 API Token", bool(read_tok and dl_tok), f"read={read_tok[:10]}… download={dl_tok[:10]}…")

    async def call(tok, tool, args=None):
        async with sse_client(f"{BASE}/mcp/sse",
                              headers={"Authorization": f"Bearer {tok}"}) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                res = await s.call_tool(tool, args or {})
                return res.content[0].text if res.content else ""

    async def main():
        # 无 token 必须被拒
        try:
            await call("", "get_system_status")
            RPT.check("无 Token 访问 MCP 被拒绝", False, "竟然调通了")
        except Exception as e:
            RPT.check("无 Token 访问 MCP 被拒绝", True, f"{type(e).__name__}")

        async with sse_client(f"{BASE}/mcp/sse",
                              headers={"Authorization": f"Bearer {dl_tok}"}) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                tools = await s.list_tools()
                names = [t.name for t in tools.tools]
                RPT.check("MCP 暴露工具列表", len(names) >= 12,
                          f"{len(names)} 个: {', '.join(names[:5])}…")

                txt = (await s.call_tool("get_system_status", {})).content[0].text
                RPT.check("调用 get_system_status", "系统已初始化" in txt or "总任务数" in txt,
                          txt.replace("\n", " ")[:100])

                txt = (await s.call_tool("list_downloads", {})).content[0].text
                RPT.check("调用 list_downloads", len(txt) > 0, txt.replace("\n", " ")[:100])

                # 参数名是 query（不是 keyword）
                txt = (await s.call_tool("search_torrents",
                                         {"query": SEARCH_QUERY, "source": "piratebay"})).content[0].text
                RPT.check("调用 search_torrents", "Error executing tool" not in txt,
                          txt.replace("\n", " ")[:100])

        # read token 调 download 工具应被 scope 拦住
        txt = await call(read_tok, "add_download", {"magnet_link": "magnet:?xt=urn:btih:" + "0" * 40})
        blocked = ("权限不足" in txt) or ("Error executing tool" in txt)
        RPT.check("read Token 调用 add_download 被拒绝", blocked, txt.replace("\n", " ")[:110])

    try:
        asyncio.run(main())
    except Exception as e:
        RPT.fail("MCP 端到端调用", f"{type(e).__name__}: {e}")


# ======================== 主流程 ========================
def main():
    ap = argparse.ArgumentParser(description="ZongziBay 端到端全链路测试")
    ap.add_argument("-d", "--downloader", action="append", choices=ALL_DOWNLOADERS,
                    help="只测指定后端，可重复；默认三个都测")
    ap.add_argument("--reset", action="store_true",
                    help="先清除 config.yml/数据库并重启，完整验证初始化流程")
    ap.add_argument("--magnet", help="跳过搜索，直接使用指定磁力链接")
    ap.add_argument("--skip-mcp", action="store_true", help="跳过 MCP 段")
    args = ap.parse_args()

    print("ZongziBay 端到端全链路测试")
    print(f"  目标: {BASE}   容器: {APP_CONTAINER}")

    api = Api()

    if not step_setup(api, reset=args.reset):
        RPT.summary()
        return 1
    if not step_login(api):
        RPT.summary()
        return 1

    magnet = pick_torrent(api, args.magnet)
    if not magnet:
        RPT.summary()
        return 1

    files = step_parse(api, magnet)
    if not files:
        RPT.summary()
        return 1

    print("\n" + "=" * 64)
    print("阶段 5/6  下载 → 重命名 → 归档")
    print("=" * 64)
    seen_ids = set()
    for d in (args.downloader or ALL_DOWNLOADERS):
        # qB 支持 set_location → 用它覆盖「移动」归档；transmission 走「带子目录→复制」，
        # aria2 走「能力降级→复制」。三种后端恰好覆盖归档的三条路径。
        run_pipeline(api, d, magnet, files, seen_ids, use_move=(d == "qbittorrent"))

    if not args.skip_mcp:
        step_mcp(api)

    ok = RPT.summary()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
