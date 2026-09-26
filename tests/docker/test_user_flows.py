"""用户流程端到端测试。

与 test_e2e_full.py 的区别：
  - test_e2e_full.py 按「阶段」组织，重点是三个下载器各自的下载→重命名→归档管道；
  - 本文件按**用户流程**组织，模拟真人打开产品后的操作顺序，每条流程是一个
    有状态、有前后依赖的完整闭环（登录 → 搜索 → 选种 → 解析 → 提交 → 归档）。

每条流程内的步骤共享状态（token、task_id、磁链等），前一步失败会直接影响后续断言，
因此断言信息里保留了上一步的真实响应，便于定位。

用法::

    python tests/docker/test_user_flows.py --reset          # 从首次安装开始，跑全部流程
    python tests/docker/test_user_flows.py                  # 沿用当前已初始化的环境
    python tests/docker/test_user_flows.py --flow F3        # 只跑某一条流程
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

# 断言行里有 ✅/❌ 这类字符。Windows 上把输出重定向到文件时 stdout 默认用 GBK，
# 写这些字符会直接 UnicodeEncodeError 把脚本打断，所以先固定成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from test_e2e_full import (  # noqa: E402
    API,
    BASE,
    DOWNLOAD_DIR,
    MAX_SIZE_MB,
    MIN_SEEDERS,
    PASSWORD,
    QB_HOST,
    QB_PASSWORD,
    QB_USER,
    RPT,
    SEARCH_QUERY,
    SECRET_KEY,
    SHARED_ROOT,
    TARGET_DIR,
    Api,
    docker_exec,
    reset_to_uninitialized,
    sha256,
)

FLOW_TARGET = f"{SHARED_ROOT}/e2e/userflow"


class FlowApi(Api):
    """补上 Api 缺的 delete（通知/Token 流程要用）。"""

    def delete(self, path, **kw):
        return self.s.delete(f"{API}{path}", timeout=kw.pop("timeout", 60), **kw)


# ======================== 通用助手 ========================

def body_of(resp):
    """尽量把响应解析成 JSON，解析不了就返回原始文本。"""
    try:
        return resp.json()
    except ValueError:
        return {"_raw": resp.text[:300], "_status": resp.status_code}


def code_of(resp):
    b = body_of(resp)
    return b.get("code") if isinstance(b, dict) else None


def api_ok(api, resp):
    """成功则返回 data，失败抛 RuntimeError（带业务 code 与消息）。"""
    b = body_of(resp)
    if not isinstance(b, dict) or b.get("code") not in (200, None):
        raise RuntimeError(f"code={b.get('code') if isinstance(b, dict) else '?'} "
                           f"message={b.get('message') if isinstance(b, dict) else resp.text[:200]}")
    return b.get("data")


def wait_task(api, task_id, want, timeout=900, poll=5):
    """轮询任务列表直到 task_id 进入 want 中的任一状态，返回最后一次见到的任务。"""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            data = api_ok(api, api.get("/tasks/list", params={"page": 1, "page_size": 100}))
        except Exception:
            time.sleep(poll)
            continue
        for it in (data or {}).get("items", []):
            if it.get("id") == task_id:
                last = it
                if it.get("taskStatus") in want:
                    return it
        time.sleep(poll)
    return last


def container_path_exists(path):
    r = docker_exec("sh", "-c", f"test -e {path} && echo YES || echo NO")
    return "YES" in (r.stdout or "")


def container_list_dir(path):
    r = docker_exec("sh", "-c", f"ls -A {path} 2>/dev/null || true")
    return [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]


def banner(idx, title):
    print("\n" + "=" * 64)
    print(f"流程 {idx}  {title}")
    print("=" * 64)


# ======================== 流程 F1：首次安装引导 ========================
def flow_f1_setup(api, ctx, reset):
    """真人第一次打开产品：状态检测 → 环境变量预填 → 测试连接 → 一键初始化 → 登录。"""
    banner("F1", "首次安装引导")

    if reset and not getattr(api, "_reset_done", False):
        if not reset_to_uninitialized():
            RPT.fail("重置到未初始化状态")
            return False
        api._reset_done = True
        # 配置被删除后 JWT 密钥也换了，旧 token 已失效；引导页此时是未登录状态
        api.s.headers.pop("Authorization", None)
        api.s.cookies.clear()

    st = body_of(api.get("/system/status"))
    if (st.get("data") or {}).get("initialized"):
        RPT.check("引导页判断系统未初始化（环境已初始化，跳过 F1 的真实初始化）", True,
                  "未加 --reset 时无法验证，已跳过")
        return True

    RPT.check("引导页判断系统未初始化", True, json.dumps(st.get("data"), ensure_ascii=False)[:120])

    # 引导页会同时读「环境变量预填」和「已有配置文件」两个来源
    env = body_of(api.get("/system/env-config"))
    env_data = env.get("data") or {}
    RPT.check("读取环境变量预填", env.get("code") == 200,
              f"字段 {len(env_data)} 个: {', '.join(list(env_data)[:6])}")

    existing = body_of(api.get("/system/existing-config"))
    RPT.check("读取已有配置文件（无配置文件时应被拦下）",
              existing.get("code") in (200, 403, 40400, 50000),
              f"code={existing.get('code')} {str(existing.get('message'))[:60]}")

    # 引导页「测试连接」按钮
    tc = body_of(api.post("/system/test-connection", json={
        "downloader": {"active": "qbittorrent"},
        "qb_host": QB_HOST, "qb_username": QB_USER, "qb_password": QB_PASSWORD,
    }, timeout=90))
    qb_res = ((tc.get("data") or {}).get("results") or {}).get("qbittorrent") or {}
    RPT.check("引导页测试下载器连接", tc.get("code") == 200 and qb_res.get("success") is True,
              str(qb_res.get("message"))[:80])

    # 引导页「使用项目提供的默认密钥」两个按钮
    for label, path in (("TMDB", "/system/config/apply-default-tmdb-key"),
                        ("ASSRT", "/system/config/apply-default-assrt-key")):
        r = body_of(api.post(path, timeout=60))
        RPT.check(f"应用项目默认 {label} 密钥", r.get("code") == 200, str(r.get("message"))[:80])

    # 提交初始化
    setup_body = {
        "username": "admin",
        "password": sha256(PASSWORD),
        "secret_key": SECRET_KEY,
        "qb_host": QB_HOST, "qb_username": QB_USER, "qb_password": QB_PASSWORD,
        "downloader": {
            "active": "qbittorrent",
            "transmission": {"host": "http://transmission:9091", "username": "admin", "password": "adminadmin"},
            "aria2": {"host": "http://aria2:6800", "secret": "zongzibay_test"},
        },
        "download_root_path": "", "target_root_path": "", "root_path": "",
        "default_download_path": DOWNLOAD_DIR, "movie_download_path": DOWNLOAD_DIR,
        "tv_download_path": DOWNLOAD_DIR, "anime_download_path": DOWNLOAD_DIR,
        "temp_download_path": DOWNLOAD_DIR,
        "default_target_path": TARGET_DIR, "movie_target_path": TARGET_DIR,
        "tv_target_path": f"{SHARED_ROOT}/e2e/nas/tv",
        "anime_target_path": f"{SHARED_ROOT}/e2e/nas/anime",
    }
    r = body_of(api.post("/system/setup", json=setup_body))
    RPT.check("提交初始化配置", r.get("code") == 200, str(r.get("message"))[:100])
    if r.get("code") != 200:
        return False

    st2 = body_of(api.get("/system/status"))
    RPT.check("初始化状态已写入", (st2.get("data") or {}).get("initialized") is True,
              json.dumps(st2.get("data"), ensure_ascii=False)[:100])

    # 重复初始化必须被挡住
    again = body_of(api.post("/system/setup", json=setup_body))
    RPT.check("重复初始化被拒绝", again.get("code") != 200, f"code={again.get('code')}")

    # 用刚设置的账号登录
    try:
        api.login()
        RPT.check("用初始化时设置的账号登录", True)
    except Exception as e:
        RPT.fail("用初始化时设置的账号登录", str(e))
        return False
    return True


# ======================== 流程 F2：登录与会话 ========================
def flow_f2_session(api, ctx, reset):
    """登录 → 身份确认 → 刷新令牌 → 登出。"""
    banner("F2", "登录与会话")

    bad = requests.post(f"{API}/users/login",
                        data={"username": "admin", "password": sha256("definitely-wrong")}, timeout=20)
    RPT.check("错误密码被拒绝", code_of(bad) not in (None, 200), f"code={code_of(bad)}")

    fresh = requests.Session()
    r = fresh.post(f"{API}/users/login",
                   data={"username": "admin", "password": sha256(PASSWORD)}, timeout=20)
    d = body_of(r).get("data") or {}
    token = d.get("access_token")
    RPT.check("正确密码登录成功并下发 access_token", bool(token), f"返回字段: {list(d)}")

    has_cookie = any(c.name == "refresh_token" for c in fresh.cookies)
    RPT.check("refresh_token 以 httpOnly Cookie 下发", has_cookie,
              f"Cookie: {[c.name for c in fresh.cookies]}")

    # 登出前后各刷一次，确认 refresh 的真实行为
    rr = body_of(fresh.post(f"{API}/users/refresh", timeout=20))
    new_tok = (rr.get("data") or {}).get("access_token")
    RPT.check("刷新 access_token", rr.get("code") == 200 and bool(new_tok),
              f"新 token 前缀 {str(new_tok)[:12]}…")

    if new_tok:
        me = body_of(requests.get(f"{API}/users/me",
                                  headers={"Authorization": f"Bearer {new_tok}"}, timeout=20))
        RPT.check("刷新出的 token 可访问受保护接口", me.get("code") == 200,
                  json.dumps(me.get("data"), ensure_ascii=False)[:80])

    lo = body_of(fresh.post(f"{API}/users/logout", timeout=20))
    RPT.check("登出成功", lo.get("code") == 200, str(lo.get("message"))[:60])

    me2 = body_of(fresh.get(f"{API}/users/me", timeout=20))
    RPT.check("登出后 Cookie 不再能访问受保护接口", me2.get("code") != 200,
              f"code={me2.get('code')}")

    # 无 token 访问受保护接口
    anon = body_of(requests.get(f"{API}/tasks/list", timeout=20))
    RPT.check("未登录取任务列表被拒绝", anon.get("code") not in (200,), f"code={anon.get('code')}")
    return True


# ======================== 流程 F3：搜索 → 下载 → 归档（核心闭环）========================
def flow_f3_download(api, ctx, reset):
    """海盗湾搜索 → 跳磁链页 → 解析 → 勾选改名 → 提交 → 等完成 → 校验归档与源目录清理。"""
    banner("F3", "搜索 → 下载 → 重命名 → 归档（核心闭环）")

    # 1) 搜索页
    r = api.get("/piratebay/search", params={"q": SEARCH_QUERY}, timeout=60)
    items = api_ok(api, r) or []
    RPT.check("搜索页拿到种子列表", len(items) > 0, f"关键词={SEARCH_QUERY!r}，{len(items)} 条")
    if not items:
        return False

    def size_mb(x):
        return int(x.get("size") or 0) / 1024 / 1024

    viable = [x for x in items if x.get("magnet") and size_mb(x) <= MAX_SIZE_MB
              and int(x.get("seeders") or 0) >= MIN_SEEDERS]
    if not viable:
        RPT.fail("挑到体积/热度达标的种子",
                 f"约束 ≤{MAX_SIZE_MB}MB / ≥{MIN_SEEDERS} seeders，{len(items)} 条无一满足")
        return False
    viable.sort(key=lambda x: (size_mb(x), -int(x.get("seeders") or 0)))
    top = viable[:3]
    RPT.check("挑到体积/热度达标的种子", True,
              f"{top[0]['name'][:44]} | {size_mb(top[0]):.0f}MB | seeders={top[0].get('seeders')}"
              f"（共 {len(viable)} 个候选）")

    # 2) 跳到磁链页解析文件列表。
    # 磁力元数据要靠外部 peer 回传，服务端只等 60s；某个种子此刻拉不到元数据是常态
    # （libtorrent 连不上该 swarm），真实用户遇到就会换个资源重试。所以这里按体积
    # 从小到大依次尝试，取第一个能解析出文件的候选。
    file_list, pick, note = [], None, ""
    for cand in top:
        res = body_of(api.post("/magnet/parse", json={"magnet_link": cand["magnet"]}, timeout=180))
        n = len(((res.get("data") or {}).get("files")) or [])
        note += f"{size_mb(cand):.0f}MB/seeders={cand.get('seeders')}→code={res.get('code')} {n} 文件；"
        if n:
            pick, file_list = cand, res["data"]["files"]
            break
    detail = (f"命中第 {top.index(pick) + 1}/{len(top)} 个候选，{len(file_list)} 个文件；"
              if pick else f"{len(top)} 个候选均超时；") + note.rstrip("；")
    RPT.check("磁链页解析出文件列表", len(file_list) > 0, detail)
    if not file_list:
        return False
    magnet = pick["magnet"]
    ctx["magnet"], ctx["files"] = magnet, file_list

    # 3) 用户在磁链页勾选文件并改写文件名（对应 magnet.vue 的 file_tasks 构造）
    rename = f"UserFlow ({pick['name'][:12].strip()}).mkv"
    file_tasks = []
    for f in file_list:
        path = f.get("path") or f.get("name") or ""
        file_tasks.append({
            "sourcePath": path,
            "targetPath": "",
            "file_rename": rename if path.lower().endswith(".mkv") else "",
        })
    renamed_count = sum(1 for ft in file_tasks if ft["file_rename"])
    RPT.check("勾选文件并给主视频填写新文件名", renamed_count == 1,
              f"新名={rename}，共 {len(file_tasks)} 个文件")

    # 4) 提交任务（magnet.vue 走的就是 /tasks/add）
    task_id = api_ok(api, api.post("/tasks/add", json={
        "taskName": pick["name"],
        "sourceUrl": magnet,
        "file_tasks": file_tasks,
        "type": "movie",
        "sourcePath": f"{DOWNLOAD_DIR}/qbittorrent",
        "targetPath": FLOW_TARGET,
    }, timeout=120))
    RPT.check("提交下载任务", isinstance(task_id, int), f"task_id={task_id}")
    if not isinstance(task_id, int):
        return False
    ctx["task_id"] = task_id

    # 5) 首页任务列表应立刻出现这条任务
    listed = api_ok(api, api.get("/tasks/list", params={"page": 1, "page_size": 20})) or {}
    hit = next((x for x in listed.get("items", []) if x.get("id") == task_id), None)
    RPT.check("首页任务列表出现新任务", hit is not None,
              f"状态={hit.get('taskStatus') if hit else '未找到'}")
    if hit:
        RPT.check("新任务状态是合法枚举值",
                  hit.get("taskStatus") in {
                      "fetching_metadata", "fetching_metadata_failed", "downloading",
                      "pending_download", "moving", "seeding", "paused",
                      "completed", "cancelled", "error"},
                  f"taskStatus={hit.get('taskStatus')!r}")

    # 6) 等下载完成 + 监控归档。
    # qB 默认无限做种（seeding.limit_ratio=-1），下完即进入 seeding，不会再到 completed——
    # 两者都代表「文件已就绪、归档已处理」，都是可接受的终态。
    print("      …等待下载与归档（最多 15 分钟）")
    final = wait_task(api, task_id, {"completed", "seeding", "error", "cancelled"}, timeout=900)
    st = (final or {}).get("taskStatus")
    RPT.check("任务下载完成", st in ("completed", "seeding"), f"taskStatus={st}")

    # 7) 归档结果：目标目录有改名后的文件
    listing = container_list_dir(FLOW_TARGET)
    RPT.check("归档目录已生成", bool(listing), f"{FLOW_TARGET}: {listing[:6]}")
    renamed = any(rename in p for p in listing)
    RPT.check("归档文件使用了用户填写的新名字", renamed, f"期望包含 {rename!r}")

    # 8) 归档语义由设置页的「复制模式」决定，校验与当前配置一致
    hf = ((api_ok(api, api.get("/system/config")) or {}).get("qbittorrent") or {}).get("file_handling") or {}
    use_copy = bool(hf.get("use_copy", False))
    remaining = container_list_dir(f"{DOWNLOAD_DIR}/qbittorrent")
    if use_copy:
        # 默认配置是复制：种子带 Screens/ 子目录时走复制归档，源文件按预期保留
        RPT.check("复制模式（默认）：源文件保留，归档为独立副本",
                  any(rename in p for p in remaining),
                  f"use_copy=true，源目录保留 {len(remaining)} 项")
    else:
        RPT.check("移动模式：源目录已清空", not remaining, f"残留: {remaining[:6]}")
    return True


# ======================== 流程 F4：任务管理 ========================
def flow_f4_task_manage(api, ctx, reset):
    """任务列表分页/详情 → 取消一条正在下载的任务。"""
    banner("F4", "任务列表与取消")

    p1 = api_ok(api, api.get("/tasks/list", params={"page": 1, "page_size": 1})) or {}
    RPT.check("任务列表分页生效", len(p1.get("items", [])) <= 1,
              f"total={p1.get('total')}，本页 {len(p1.get('items', []))} 条")

    if p1.get("items"):
        it = p1["items"][0]
        need = {"id", "taskName", "taskStatus", "file_tasks", "isDelete"}
        missing = need - set(it)
        RPT.check("列表项含详情页所需字段", not missing,
                  f"缺失={sorted(missing)}" if missing else f"字段 {len(it)} 个")

    # 取消要挑一个**没在下载器里出现过**的种子：同一 hash 复用旧任务时，监控会
    # 立刻按下载器真实状态把它纠正为 completed，取消会变成竞态。
    items = api_ok(api, api.get("/piratebay/search", params={"q": SEARCH_QUERY}, timeout=60)) or []

    def size_mb(x):
        return int(x.get("size") or 0) / 1024 / 1024

    # 约束放宽到「有条目、有磁链」即可：这里只要求种子没在下载器里出现过
    # （F3 那个只有 1 个候选，用不了），能提交、能取消就够了，不需要真下完。
    fresh = [x for x in items
             if x.get("magnet") and x["magnet"] != ctx.get("magnet")
             and int(x.get("seeders") or 0) >= 1]
    fresh.sort(key=lambda x: (size_mb(x), -int(x.get("seeders") or 0)))
    if not fresh:
        RPT.check("取消流程（无可用的独立种子，跳过）", True)
        return True
    magnet = fresh[0]["magnet"]

    api_ok(api, api.post("/magnet/download", json={
        "magnet_link": magnet, "save_path": f"{DOWNLOAD_DIR}/cancel-test"}, timeout=120))

    lst = api_ok(api, api.get("/tasks/list", params={"page": 1, "page_size": 100})) or {}
    body = lst.get("items", [])
    if body:
        new_id = max(x["id"] for x in body)
        RPT.check("磁链下载接口提交成功", True, f"新增任务 id={new_id}")
    else:
        RPT.fail("磁链下载接口提交成功", "提交后任务列表仍为空")
        return False

    r = body_of(api.post(f"/tasks/cancel/{new_id}", timeout=120))
    RPT.check("取消任务接口返回成功", r.get("code") == 200, str(r.get("message"))[:80])

    after = wait_task(api, new_id, {"cancelled"}, timeout=90)
    RPT.check("取消后任务状态变为 cancelled",
              (after or {}).get("taskStatus") == "cancelled",
              f"taskStatus={(after or {}).get('taskStatus')}")

    bogus = body_of(api.post("/tasks/cancel/999999", timeout=30))
    RPT.check("取消不存在的任务被拒绝", bogus.get("code") != 200,
              f"code={bogus.get('code')} {str(bogus.get('message'))[:60]}")
    return True


# ======================== 流程 F5：电影探索 ========================
def flow_f5_movie(api, ctx, reset):
    """推荐/热播 → 搜索电影 → 打开详情 → 取英文名 → 拿去搜种。"""
    banner("F5", "电影探索")

    for label, path in (("热播", "/tmdb/trending/movie"), ("热门", "/tmdb/popular/movie"),
                        ("高分", "/tmdb/list/top_rated/movie")):
        d = api_ok(api, api.get(path, params={"page": 1}, timeout=60)) or {}
        RPT.check(f"电影页-{label}列表加载", len(d.get("items") or []) > 0,
                  f"{len(d.get('items') or [])} 部，total={d.get('total')}")

    sug = api_ok(api, api.get("/tmdb/suggestions",
                              params={"query": SEARCH_QUERY[:4], "limit": 8}, timeout=60)) or {}
    suggestions = (sug or {}).get("suggestions") or []
    RPT.check("搜索框补全提示返回候选", len(suggestions) > 0,
              f"{len(suggestions)} 条: {', '.join(str(s) for s in suggestions[:3])}")

    res = api_ok(api, api.get("/tmdb/search/movie",
                              params={"query": SEARCH_QUERY, "page": 1}, timeout=60)) or {}
    movies = res.get("items") or []
    RPT.check("按关键词搜到电影", len(movies) > 0, f"{len(movies)} 部")
    if not movies:
        return False
    mid = movies[0].get("id")
    ctx["movie_id"] = mid

    detail = api_ok(api, api.get(f"/tmdb/movie/{mid}", timeout=60)) or {}
    RPT.check("打开电影详情弹窗", bool(detail), f"{str(detail.get('title'))[:40]}")
    RPT.check("详情含演员阵容", isinstance(detail.get("cast"), list),
              f"cast {len(detail.get('cast') or [])} 人")

    en = body_of(api.get(f"/tmdb/movie/{mid}/english-title", timeout=60))
    title = (en.get("data") or {}).get("english_title")
    RPT.check("取到英文标题（用于英文站搜种）", en.get("code") == 200 and bool(title),
              f"english_title={title!r}")

    if title:
        found = api_ok(api, api.get("/piratebay/search", params={"q": title}, timeout=60)) or []
        RPT.check("用英文标题在海盗湾搜到资源", len(found) > 0, f"{len(found)} 条")

    # 不存在的电影应给出可读错误而不是 50000
    nf = body_of(api.get("/tmdb/movie/99999999", timeout=60))
    RPT.check("不存在的电影返回友好错误", nf.get("code") == 40400,
              f"code={nf.get('code')} {str(nf.get('message'))[:50]}")
    return True


# ======================== 流程 F6：剧集探索 ========================
def flow_f6_tv(api, ctx, reset):
    """搜索剧集 → 详情 → 英文名；顺带覆盖剧集相关列表页。"""
    banner("F6", "剧集探索")

    for label, path in (("热播", "/tmdb/trending/tv"), ("热门", "/tmdb/popular/tv"),
                        ("高分", "/tmdb/list/top_rated/tv"), ("高分番剧", "/tmdb/list/top_rated/anime")):
        d = api_ok(api, api.get(path, params={"page": 1}, timeout=60)) or {}
        RPT.check(f"剧集页-{label}列表加载", len(d.get("items") or []) > 0,
                  f"{len(d.get('items') or [])} 部，total={d.get('total')}")

    res = api_ok(api, api.get("/tmdb/search/tv", params={"query": "breaking", "page": 1}, timeout=60)) or {}
    shows = res.get("items") or []
    RPT.check("按关键词搜到剧集", len(shows) > 0, f"{len(shows)} 部")
    if not shows:
        return False
    tid = shows[0].get("id")

    detail = api_ok(api, api.get(f"/tmdb/tv/{tid}", timeout=60)) or {}
    RPT.check("打开剧集详情", bool(detail), f"{str(detail.get('name'))[:40]}")
    RPT.check("剧集详情含演员阵容", isinstance(detail.get("cast"), list),
              f"cast {len(detail.get('cast') or [])} 人")

    en = body_of(api.get(f"/tmdb/tv/{tid}/english-title", timeout=60))
    en_title = (en.get("data") or {}).get("english_title")
    RPT.check("取到剧集英文名", en.get("code") == 200 and bool(en_title),
              f"english_title={en_title!r}")

    nf = body_of(api.get("/tmdb/tv/99999999", timeout=60))
    RPT.check("不存在的剧集返回友好错误", nf.get("code") == 40400,
              f"code={nf.get('code')} {str(nf.get('message'))[:50]}")
    return True


# ======================== 流程 F7：番剧追番 ========================
def flow_f7_anime(api, ctx, reset):
    """番剧页：本周周历 → 条目详情 → 历史季度 → 动画花园搜资源 → 字幕组。"""
    banner("F7", "番剧追番")

    cal = api_ok(api, api.get("/bangumi/calendar", timeout=90)) or []
    days = cal if isinstance(cal, list) else []
    RPT.check("番剧周历加载（按周一到周日分组）", len(days) >= 1, f"{len(days)} 组")
    if not days:
        return False

    first_day = days[0]
    items = first_day.get("items") or []
    RPT.check("周历某天有条目", len(items) > 0, f"{len(items)} 部")
    if not items:
        return False

    subject = items[0]
    sid = subject.get("id")
    name = subject.get("name_cn") or subject.get("name") or ""
    ctx["anime_name"] = name

    detail = api_ok(api, api.get(f"/bangumi/subject/{sid}", timeout=90)) or {}
    RPT.check("打开番剧条目详情", bool(detail), f"{str(name)[:34]} → {str(detail.get('name_cn') or detail.get('name'))[:30]}")

    # 该接口会顺序翻页拉 Bangumi 三个月的条目（实测 ~30s），任何一次上游连接超时
    # 都会让整体返回 50000。真实用户此时会刷新页面重试，这里同样给一次机会。
    spring, err = [], ""
    for attempt in (1, 2):
        try:
            spring = api_ok(api, api.get("/bangumi/season",
                                         params={"year": 2024, "season": "spring"}, timeout=180)) or []
            break
        except RuntimeError as e:
            err = f"第 {attempt} 次: {e}"
    RPT.check("历史季度新番加载", isinstance(spring, list) and len(spring) >= 1,
              f"{len(spring) if isinstance(spring, list) else 0} 组" if spring else err)

    teams = api_ok(api, api.get("/anime/teams", timeout=90)) or []
    RPT.check("字幕组列表加载", isinstance(teams, list) and len(teams) > 0,
              f"{len(teams) if isinstance(teams, list) else 0} 个字幕组")

    if not name:
        RPT.check("番剧名可用（无法拿到名字，跳过搜资源）", True)
        return True

    # 动画花园按发布名索引，番剧的中文全名常常搜不到；真人会退而用短名/原名再搜一次。
    # 上游偶发 15s 读超时（无重试），所以每个关键词多试一次。
    resources, attempts = [], []
    for q in (name, name[:6]):
        if not q or q in [a[0] for a in attempts]:
            continue
        for _ in range(2):
            r = body_of(api.get("/anime/search", params={"q": q, "page": 1}, timeout=120))
            got = ((r.get("data") or {}).get("resources")) or []
            attempts.append((q, r.get("code"), len(got)))
            if got:
                resources = got
                break
        if resources:
            break
    detail = "；".join(f"{q[:12]!r}→code={c} {n} 条" for q, c, n in attempts)
    RPT.check("用番剧名在动画花园搜到资源", len(resources) > 0, detail)

    with_magnet = [x for x in resources if x.get("magnet")]
    RPT.check("资源里带磁力链接", len(with_magnet) > 0, f"{len(with_magnet)} 条带磁链")
    if not with_magnet:
        return True

    # 番剧老种子的 peer 早没了，拉元数据必然超时——那是选种问题，不是产品问题。
    # 真人会挑最新发布的资源，这里按 createdAt 倒序试前 2 个，任一能解析即通过。
    newest = sorted(with_magnet, key=lambda x: str(x.get("createdAt") or ""), reverse=True)[:2]
    note, ok_parse = "", False
    for res_item in newest:
        r = body_of(api.post("/magnet/parse", json={"magnet_link": res_item["magnet"]}, timeout=180))
        n = len(((r.get("data") or {}).get("files")) or [])
        note += f"{str(res_item.get('title'))[:14]!r}→code={r.get('code')} {n} 文件；"
        if n:
            ok_parse, ctx["anime_magnet"] = True, res_item["magnet"]
            break
    RPT.check("番剧资源可解析（能进入下载流程）", ok_parse, note.rstrip("；"))
    return True


# ======================== 流程 F8：字幕下载 ========================
def flow_f8_subtitle(api, ctx, reset):
    """字幕页：配额 → 搜索 → 详情 → 相似 → 下载 → 任务队列归档 → 批量下载。"""
    banner("F8", "字幕搜索与下载")

    quota = body_of(api.get("/subtitle/user/quota", timeout=60))
    RPT.check("字幕页显示配额", quota.get("code") == 200,
              f"quota={(quota.get('data') or {}).get('quota')}")

    res = api_ok(api, api.get("/subtitle/sub/search",
                              params={"q": SEARCH_QUERY, "pos": 0, "cnt": 15}, timeout=90)) or {}
    subs = res.get("items") or []
    RPT.check("搜到字幕", len(subs) > 0, f"{len(subs)} 条，total={res.get('total')}")
    if not subs:
        return False

    sid = subs[0].get("id")
    detail = api_ok(api, api.get("/subtitle/sub/detail", params={"id": sid}, timeout=90)) or {}
    RPT.check("打开字幕详情", bool(detail), f"id={sid}")

    sim = api_ok(api, api.get("/subtitle/sub/similar", params={"id": sid}, timeout=90)) or {}
    RPT.check("相似字幕推荐可用", isinstance(sim.get("items"), list),
              f"{len(sim.get('items') or [])} 条")

    # 单条下载 → 生成任务。字幕包由 ASSRT 的文件服务器（file1.assrt.net）提供，
    # 该域名在受限网络下不可达；此时接口会明确回报网络错误，据此区分「产品问题」与「环境问题」。
    dl = body_of(api.post("/subtitle/sub/download",
                          params={"id": sid, "target_path": FLOW_TARGET}, timeout=180))
    tid = (dl.get("data") or {}).get("task_id")
    dl_msg = str(dl.get("message") or "")
    unreachable = any(k in dl_msg for k in ("Max retries", "SSLError", "file1.assrt.net"))
    if unreachable:
        RPT.check("单条字幕下载并加入任务队列", False,
                  "字幕文件服务器 file1.assrt.net 在本环境不可达（网络受限，非代码缺陷）")
    else:
        RPT.check("单条字幕下载并加入任务队列", isinstance(tid, int),
                  f"task_id={tid} 目标={str((dl.get('data') or {}).get('target_path'))[:60]}")
    if isinstance(tid, int):
        print("      …等待字幕任务落盘并归档（最多 6 分钟）")
        final = wait_task(api, tid, {"completed", "moving", "error"}, timeout=360)
        RPT.check("字幕任务完成归档",
                  (final or {}).get("taskStatus") in ("completed", "moving"),
                  f"taskStatus={(final or {}).get('taskStatus')}")

    batch = body_of(api.post("/subtitle/sub/download/batch", json={
        "id": sid,
        "target_path": FLOW_TARGET,
        "items": [{"file_index": 0, "file_rename": "userflow-sub.srt"}],
    }, timeout=180))
    RPT.check("批量字幕下载接口受理", batch.get("code") == 200,
              str((batch.get("data") or {}).get("message"))[:70])
    return True


# ======================== 流程 F9：设置管理 ========================
def flow_f9_settings(api, ctx, reset):
    """设置页：读配置 → 改偏好 → 测连接 → 掩码保存 → 切后端 → 连接检查。"""
    banner("F9", "设置管理")

    cfg = api_ok(api, api.get("/system/config", timeout=60)) or {}
    RPT.check("设置页读取配置", bool(cfg), f"顶层节: {', '.join(list(cfg)[:8])}")
    secret_masked = (((cfg.get("qbittorrent") or {}).get("password")) or "")
    RPT.check("敏感字段以掩码返回", secret_masked in ("", "****") or set(secret_masked) == {"*"},
              f"qbittorrent.password={secret_masked!r}")

    paths = api_ok(api, api.get("/system/paths", timeout=60)) or {}
    RPT.check("路径设置可读", "movie_download_path" in paths,
              f"movie_download_path={paths.get('movie_download_path')}")

    tmpl = api_ok(api, api.get("/system/rename-templates", timeout=60)) or {}
    RPT.check("重命名模板可读", bool(tmpl), str(tmpl)[:80])

    trk = api_ok(api, api.get("/system/trackers", timeout=60)) or {}
    RPT.check("tracker 列表可读", trk is not None, str(trk)[:60])

    before = api_ok(api, api.get("/system/preferences", timeout=60)) or {}
    target = not before.get("show_zongzibay_chan", True)
    p = body_of(api.put("/system/preferences", json={"show_zongzibay_chan": target}, timeout=60))
    after = api_ok(api, api.get("/system/preferences", timeout=60)) or {}
    RPT.check("保存显示偏好后立即生效", p.get("code") == 200 and after.get("show_zongzibay_chan") is target,
              f"{before.get('show_zongzibay_chan')} → {after.get('show_zongzibay_chan')}")
    api.put("/system/preferences", json={"show_zongzibay_chan": before.get("show_zongzibay_chan", True)})

    tc = body_of(api.post("/system/test-connection", json={
        "downloader": {"active": "qbittorrent"},
        "qb_host": QB_HOST, "qb_username": QB_USER, "qb_password": QB_PASSWORD,
    }, timeout=120))
    results = (tc.get("data") or {}).get("results") or {}
    RPT.check("设置页测试各服务连接", tc.get("code") == 200 and bool(results),
              f"服务: {', '.join(f'{k}={"OK" if v.get("success") else "FAIL"}' for k, v in results.items())}")

    # 掩码回写：设置页保存时会把 **** 原样提交回来，不能因此清空真实密码
    cfg2 = api_ok(api, api.get("/system/config", timeout=60)) or {}
    save = body_of(api.put("/system/config", json=cfg2, timeout=90))
    RPT.check("保存配置（掩码原样回写）成功", save.get("code") == 200, str(save.get("message"))[:70])

    relogin = requests.post(f"{API}/users/login",
                            data={"username": "admin", "password": sha256(PASSWORD)}, timeout=20)
    RPT.check("掩码回写后账号仍可登录（密码未被覆盖）", code_of(relogin) == 200,
              f"code={code_of(relogin)}")

    check = body_of(api.get("/magnet/check", timeout=90))
    RPT.check("下载器连接检查通过", check.get("code") == 200, str(check.get("message"))[:60])
    return True


# ======================== 流程 F10：通知 ========================
def flow_f10_notifications(api, ctx, reset):
    """通知铃铛：未读数 → 列表 → 单条已读 → 全部已读 → 删除。"""
    banner("F10", "通知")

    cnt0 = api_ok(api, api.get("/notifications/unread_count", timeout=30))
    RPT.check("铃铛读到未读数", isinstance(cnt0, int), f"未读 {cnt0}")

    page = api_ok(api, api.get("/notifications/", params={"page": 1, "page_size": 20}, timeout=30)) or {}
    items = page.get("items") or []
    RPT.check("通知列表加载", "total" in page, f"total={page.get('total')}，本页 {len(items)} 条")
    if not items:
        RPT.check("无通知可操作（跳过已读/删除）", True)
        return True

    nid = items[0]["id"]
    unread_before = sum(1 for x in items if not x.get("isRead", x.get("is_read")))
    r = body_of(api.put(f"/notifications/{nid}/read", timeout=30))
    RPT.check("单条标记已读", r.get("code") == 200, str(r.get("data"))[:40])

    cnt2 = api_ok(api, api.get("/notifications/unread_count", timeout=30))
    RPT.check("未读数随之减少", isinstance(cnt2, int) and cnt2 <= (cnt0 or 0),
              f"{cnt0} → {cnt2}（该页原本未读 {unread_before} 条）")

    if len(items) > 1:
        d = body_of(api.delete(f"/notifications/{items[-1]['id']}", timeout=30))
        RPT.check("删除通知", d.get("code") == 200, str(d.get("data"))[:40])
        page2 = api_ok(api, api.get("/notifications/", params={"page": 1, "page_size": 20}, timeout=30)) or {}
        RPT.check("删除后列表总数减少", (page2.get("total") or 0) < (page.get("total") or 0),
                  f"{page.get('total')} → {page2.get('total')}")

    ra = body_of(api.put("/notifications/read_all", timeout=30))
    RPT.check("全部标记已读", ra.get("code") == 200, f"影响 {ra.get('data')} 条")
    cnt3 = api_ok(api, api.get("/notifications/unread_count", timeout=30))
    RPT.check("全部已读后未读数归零", cnt3 == 0, f"未读 {cnt3}")
    return True


# ======================== 流程 F11：API Token 生命周期 ========================
def flow_f11_token(api, ctx, reset):
    """设置页 API Token：创建 → 列表 → 禁用 → 启用 → 删除 → 失效验证。"""
    banner("F11", "API Token 生命周期")

    created = api_ok(api, api.post("/api-tokens", json={
        "name": "userflow-token", "scopes": "read"}, timeout=60)) or {}
    tok = created.get("token")
    tok_id = created.get("id")
    RPT.check("创建 API Token", bool(tok and tok_id),
              f"id={tok_id} masked={created.get('masked')}")
    if not tok or not tok_id:
        return False

    RPT.check("创建时只展示一次完整 token", "token" in created and created.get("masked") != tok,
              f"masked={created.get('masked')}")

    lst = api_ok(api, api.get("/api-tokens", timeout=30)) or {}
    RPT.check("Token 列表加载", (lst.get("total") or 0) >= 1, f"total={lst.get('total')}")
    listed = next((x for x in (lst.get("items") or []) if x["id"] == tok_id), None)
    RPT.check("列表里不含完整 token（只回掩码）", listed is not None and "token" not in listed,
              f"字段: {sorted(listed) if listed else '未找到'}")

    off = body_of(api.put(f"/api-tokens/{tok_id}/toggle", json={"is_active": False}, timeout=30))
    RPT.check("禁用 Token", off.get("code") == 200, str(off.get("message"))[:40])

    async def probe(t):
        from mcp import ClientSession
        from mcp.client.sse import sse_client
        async with sse_client(f"{BASE}/mcp/sse", headers={"Authorization": f"Bearer {t}"}) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                res = await s.call_tool("get_system_status", {})
                return res.content[0].text if res.content else ""

    try:
        txt = asyncio.run(probe(tok))
        denied = ("Error executing tool" in txt) or ("权限" in txt) or ("无效" in txt)
        RPT.check("禁用后 Token 立即失效", denied, txt.replace("\n", " ")[:90])
    except Exception as e:
        RPT.check("禁用后 Token 立即失效", True, f"连接被拒: {type(e).__name__}")

    on = body_of(api.put(f"/api-tokens/{tok_id}/toggle", json={"is_active": True}, timeout=30))
    RPT.check("重新启用 Token", on.get("code") == 200, str(on.get("message"))[:40])
    try:
        txt = asyncio.run(probe(tok))
        RPT.check("启用后 Token 恢复可用", "Error executing tool" not in txt,
                  txt.replace("\n", " ")[:90])
    except Exception as e:
        RPT.fail("启用后 Token 恢复可用", f"{type(e).__name__}: {e}")

    dl = body_of(api.delete(f"/api-tokens/{tok_id}", timeout=30))
    RPT.check("删除 Token", dl.get("code") == 200, str(dl.get("message"))[:40])
    try:
        txt = asyncio.run(probe(tok))
        RPT.check("删除后 Token 彻底失效",
                  ("Error executing tool" in txt) or ("无效" in txt), txt.replace("\n", " ")[:80])
    except Exception as e:
        RPT.check("删除后 Token 彻底失效", True, f"连接被拒: {type(e).__name__}")

    bogus = body_of(api.delete("/api-tokens/999999", timeout=30))
    RPT.check("删除不存在的 Token 被拒绝", bogus.get("code") != 200, f"code={bogus.get('code')}")
    return True


# ======================== 流程 F12：外部 AI 接入（MCP 全旅程）========================
def flow_f12_mcp(api, ctx, reset):
    """外部 AI 客户端接入：建 token → 连 SSE → 列工具 → 搜种 → 解析 → 加下载 → 查状态。"""
    banner("F12", "外部 AI 接入（MCP 全旅程）")

    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except Exception as e:
        RPT.fail("MCP 客户端依赖可用", f"{type(e).__name__}: {e}")
        return False

    dl_tok = (api_ok(api, api.post("/api-tokens", json={
        "name": "userflow-mcp-dl", "scopes": "download"}, timeout=60)) or {}).get("token")
    read_tok = (api_ok(api, api.post("/api-tokens", json={
        "name": "userflow-mcp-read", "scopes": "read"}, timeout=60)) or {}).get("token")
    RPT.check("为外部 AI 客户端创建 Token", bool(dl_tok and read_tok),
              f"download={str(dl_tok)[:10]}… read={str(read_tok)[:10]}…")
    if not dl_tok or not read_tok:
        return False

    async def with_session(tok, fn):
        async with sse_client(f"{BASE}/mcp/sse", headers={"Authorization": f"Bearer {tok}"}) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                return await fn(s)

    async def main():
        try:
            await with_session("", lambda s: s.list_tools())
            RPT.check("无 Token 连接被拒绝", False, "竟然连上了")
        except Exception as e:
            RPT.check("无 Token 连接被拒绝", True, type(e).__name__)

        async def journey(s):
            tools = [t.name for t in (await s.list_tools()).tools]
            RPT.check("外部客户端看到完整工具集", len(tools) >= 12, f"{len(tools)} 个")

            txt = (await s.call_tool("get_system_status", {})).content[0].text
            RPT.check("AI 查询系统状态", "总任务数" in txt or "系统已初始化" in txt,
                      txt.replace("\n", " ")[:80])

            txt = (await s.call_tool("search_torrents",
                                     {"query": SEARCH_QUERY, "source": "piratebay"})).content[0].text
            RPT.check("AI 搜索资源", "Error executing tool" not in txt, txt.replace("\n", " ")[:80])

            magnet = ctx.get("magnet")
            if magnet:
                txt = (await s.call_tool("parse_magnet", {"magnet_link": magnet})).content[0].text
                RPT.check("AI 解析磁链", "Error executing tool" not in txt, txt.replace("\n", " ")[:80])

                txt = (await s.call_tool("add_download", {"magnet_link": magnet})).content[0].text
                RPT.check("AI 提交下载任务", "Error executing tool" not in txt,
                          txt.replace("\n", " ")[:90])

                txt = (await s.call_tool("list_downloads", {})).content[0].text
                RPT.check("AI 读取任务列表", "任务列表" in txt or "下载" in txt,
                          txt.replace("\n", " ")[:80])

                txt = (await s.call_tool("search_subtitles", {"keyword": SEARCH_QUERY})).content[0].text
                RPT.check("AI 搜索字幕", "Error executing tool" not in txt, txt.replace("\n", " ")[:80])

                txt = (await s.call_tool("get_media_detail",
                                         {"media_type": "movie", "tmdb_id": ctx.get("movie_id", 550)})).content[0].text
                RPT.check("AI 查询媒体详情", "Error executing tool" not in txt, txt.replace("\n", " ")[:80])

                txt = (await s.call_tool("get_bangumi_calendar", {})).content[0].text
                RPT.check("AI 查询新番周历", "Error executing tool" not in txt, txt.replace("\n", " ")[:80])

        await with_session(dl_tok, journey)

        # scope 层级是 read ⊂ search ⊂ download：read Token 只能读，不能搜、更不能下
        async def denied(s):
            txt = (await s.call_tool("add_download",
                                     {"magnet_link": "magnet:?xt=urn:btih:" + "0" * 40})).content[0].text
            return "权限不足" in txt or "Error executing tool" in txt

        RPT.check("read 权限 Token 不能提交下载", await with_session(read_tok, denied))

        async def search_denied(s):
            txt = (await s.call_tool("search_torrents",
                                     {"query": SEARCH_QUERY, "source": "piratebay"})).content[0].text
            return "权限不足" in txt or "Error executing tool" in txt

        RPT.check("read 权限 Token 不能搜索（需 search 权限）", await with_session(read_tok, search_denied))

        async def read_allowed(s):
            txt = (await s.call_tool("list_downloads", {})).content[0].text
            return "Error executing tool" not in txt

        RPT.check("read 权限 Token 可以读任务列表", await with_session(read_tok, read_allowed))

    try:
        asyncio.run(main())
    except Exception as e:
        RPT.fail("MCP 全旅程", f"{type(e).__name__}: {e}")
        return False
    finally:
        for t in (dl_tok, read_tok):
            lst = api.get("/api-tokens").json().get("data") or {}
            for x in lst.get("items", []):
                if x.get("name", "").startswith("userflow-mcp"):
                    api.delete(f"/api-tokens/{x['id']}")
    return True


# ======================== 主入口 ========================
FLOWS = [
    ("F1", "首次安装引导", flow_f1_setup, True),
    ("F2", "登录与会话", flow_f2_session, False),
    ("F3", "搜索→下载→重命名→归档", flow_f3_download, False),
    ("F4", "任务列表与取消", flow_f4_task_manage, False),
    ("F5", "电影探索", flow_f5_movie, False),
    ("F6", "剧集探索", flow_f6_tv, False),
    ("F7", "番剧追番", flow_f7_anime, False),
    ("F8", "字幕搜索与下载", flow_f8_subtitle, False),
    ("F9", "设置管理", flow_f9_settings, False),
    ("F10", "通知", flow_f10_notifications, False),
    ("F11", "API Token 生命周期", flow_f11_token, False),
    ("F12", "外部 AI 接入（MCP）", flow_f12_mcp, False),
]


def main():
    ap = argparse.ArgumentParser(description="ZongziBay 用户流程端到端测试")
    ap.add_argument("--reset", action="store_true",
                    help="先清空配置/数据库/下载器，从「首次安装」开始跑")
    ap.add_argument("--flow", action="append",
                    help="只跑指定流程（如 --flow F3 --flow F9）")
    args = ap.parse_args()

    print("ZongziBay 用户流程端到端测试")
    print(f"  目标: {BASE}")

    api = FlowApi()
    ctx = {}
    api._reset_done = False

    wanted = set(args.flow or [])
    results = {}

    # F1 若要求重置，必须先于登录；其余流程都基于已初始化的环境
    for key, title, fn, needs_reset in FLOWS:
        if wanted and key not in wanted:
            continue
        try:
            if key != "F1":
                api.login()
        except Exception as e:
            RPT.fail(f"{key} 登录前置", f"{type(e).__name__}: {e}")
            results[key] = False
            continue

        before = len(RPT.rows)
        try:
            ok = fn(api, ctx, args.reset)
        except Exception as e:
            RPT.fail(f"{key} {title} 执行异常", f"{type(e).__name__}: {e}")
            ok = False
        fails = [n for n, o, _ in RPT.rows[before:] if not o]
        results[key] = (bool(ok) and not fails, fails)
        print(f"  → 流程 {key} {'通过' if results[key][0] else '未通过'}")

    print("\n" + "=" * 64)
    print("用户流程结果")
    print("=" * 64)
    for key, title, _, _ in FLOWS:
        if key not in results:
            continue
        ok, fails = results[key]
        mark = "✅" if ok else "❌"
        extra = "" if ok else f"  失败: {', '.join(fails)}"
        print(f"  {mark} {key}  {title}{extra}")

    flow_ok = sum(1 for v in results.values() if v[0])
    print(f"\n流程通过: {flow_ok}/{len(results)}")
    return RPT.summary() and flow_ok == len(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
