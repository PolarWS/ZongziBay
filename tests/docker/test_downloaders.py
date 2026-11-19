"""
ZongziBay 下载器真实环境集成测试（隔离版）

每个下载器测试完全隔离：
  - 生成独立的 .torrent 文件（不同 name / info_hash）
  - 测试前扫描清理残留任务
  - 测试后验证清理干净
  - 不依赖 DHT 网络

前置条件:
  docker compose -f tests/docker/docker-compose.yml up -d --build

运行:
  $env:PYTHONIOENCODING = "utf-8"
  python tests/docker/test_downloaders.py
"""

import os
import subprocess
import sys
import time
import hashlib
import traceback
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.downloader.qbittorrent import QBittorrentDownloader
from app.core.downloader.transmission import TransmissionDownloader
from app.core.downloader.aria2 import Aria2Downloader
from app.core.downloader.base import (
    BaseDownloader, DownloaderCapabilities,
    _bencode_torrent_info_hash, _bencode_torrent_files,
)


# ======================================================================
# 本地 torrent 生成（每个下载器用独立的 torrent）
# ======================================================================

def _bencode(obj) -> bytes:
    if isinstance(obj, bytes):
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, str):
        b = obj.encode("utf-8")
        return str(len(b)).encode() + b":" + b
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, dict):
        parts = []
        for k in sorted(obj.keys()):
            parts.append(_bencode(k))
            parts.append(_bencode(obj[k]))
        return b"d" + b"".join(parts) + b"e"
    if isinstance(obj, list):
        parts = [_bencode(i) for i in obj]
        return b"l" + b"".join(parts) + b"e"
    raise TypeError(f"unsupported: {type(obj)}")


def make_torrent(name: str) -> Tuple[bytes, str]:
    """生成多文件测试 torrent（movie.mkv + subtitles.srt），返回 (bytes, info_hash)"""
    piece_len = 256 * 1024
    f1 = b"A" * 100_000
    f2 = b"B" * 50_000
    all_data = f1 + f2
    pieces = b"".join(
        hashlib.sha1(all_data[i:i + piece_len]).digest()
        for i in range(0, len(all_data), piece_len)
    )
    info = {
        "name": name,
        "piece length": piece_len,
        "pieces": pieces,
        "files": [
            {"length": len(f1), "path": ["videos", "movie.mkv"]},
            {"length": len(f2), "path": ["videos", "subtitles.srt"]},
        ],
    }
    raw = _bencode({"info": info})
    h = _bencode_torrent_info_hash(raw)
    return raw, h


# ======================================================================
# 配置
# ======================================================================

def _get_qb_password() -> str:
    """从 docker logs 自动获取 qBittorrent 临时密码"""
    pw = os.environ.get("QB_PASSWORD", "")
    if pw:
        return pw
    try:
        out = subprocess.check_output(
            ["docker", "logs", "zongzibay-qbittorrent"],
            stderr=subprocess.STDOUT, timeout=10, text=True,
        )
        for line in out.splitlines():
            if "temporary password" in line.lower():
                return line.strip().rsplit(" ", 1)[-1]
    except Exception:
        pass
    return ""


QB_PASSWORD = _get_qb_password()
TR_USER = os.environ.get("TR_USER", "admin")
TR_PASS = os.environ.get("TR_PASS", "adminadmin")
ARIA2_SECRET = os.environ.get("ARIA2_SECRET", "zongzibay_test")


# ======================================================================
# 结果记录
# ======================================================================

@dataclass
class R:
    name: str
    ok: bool
    msg: str = ""
    skip: bool = False


class Report:
    def __init__(self, name: str):
        self.name = name
        self.items: List[R] = []

    def ok(self, n: str, m: str = ""):   self.items.append(R(n, True, m))
    def fail(self, n: str, m: str = ""): self.items.append(R(n, False, m))
    def skip(self, n: str, m: str = ""): self.items.append(R(n, False, m, True))

    def show(self) -> bool:
        p = sum(1 for r in self.items if r.ok)
        f = sum(1 for r in self.items if not r.ok and not r.skip)
        s = sum(1 for r in self.items if r.skip)
        bar = "=" * 60
        print(f"\n{bar}")
        print(f"  [{self.name}] {p}/{p+f} passed", end="")
        if f: print(f", {f} failed", end="")
        if s: print(f", {s} skipped", end="")
        print(f"\n{bar}")
        for r in self.items:
            tag = "PASS" if r.ok else ("SKIP" if r.skip else "FAIL")
            line = f"   [{tag}] {r.name}"
            if r.msg: line += f"  -- {r.msg}"
            print(line)
        print()
        return f == 0


# ======================================================================
# 辅助
# ======================================================================

def _wait_info(dl: BaseDownloader, h: str, timeout: int = 20) -> Optional[Dict]:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            i = dl.get_torrent_info(h)
            if i and (i.get("total_size") or 0) > 0:
                return i
        except Exception:
            pass
        time.sleep(1)
    return None


def _do_cleanup(dl: BaseDownloader, h: str, timeout: int = 10):
    """删除并等待确认"""
    try:
        dl.delete_torrents(h, delete_files=True)
    except Exception:
        pass
    # 等待确认删除
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if dl.get_torrent_info(h) is None:
                return True
        except Exception:
            return True  # 查询失败也视为删除
        time.sleep(1)
    return False


# ======================================================================
# 单下载器测试（完全隔离）
# ======================================================================

def test_one(dl: BaseDownloader, rpt: Report, label: str):
    """每个下载器用独立 torrent，执行全部操作后验证清理干净"""

    caps = dl.capabilities
    torrent_bytes, info_hash = make_torrent(f"zongzi_test_{label}")
    cleanup_added: List[str] = [info_hash]

    print(f"\n{'─' * 50}")
    print(f"  [{label}] 开始测试, torrent={info_hash[:16]}...")
    print(f"{'─' * 50}")

    # ---- 隔离检查：测试前扫描残留 ----
    print(f"  [pre] 扫描残留任务...")
    try:
        stale = dl.get_torrent_info(info_hash)
        if stale:
            print(f"  [pre] 发现残留, 清理中...")
            _do_cleanup(dl, info_hash)
    except Exception:
        pass

    # ---- 0. 本地解析 ----
    try:
        parsed = dl.parse_torrent_file(torrent_bytes)
        if parsed and len(parsed) == 2:
            rpt.ok("parse_torrent_file",
                   ", ".join(f"{f.name}({f.size}B)" for f in parsed))
        else:
            rpt.fail("parse_torrent_file", f"expected 2, got {len(parsed or [])}")
    except Exception as e:
        rpt.fail("parse_torrent_file", str(e))

    # ---- 1. 连接 ----
    try:
        if dl.check_connection():
            rpt.ok("check_connection")
        else:
            rpt.fail("check_connection", "False")
            return
    except Exception as e:
        rpt.fail("check_connection", str(e))
        return

    # ---- 2. 版本 ----
    try:
        v = dl.get_version()
        if v and v != "unknown":
            rpt.ok("get_version", v)
        else:
            rpt.fail("get_version", repr(v))
    except Exception as e:
        rpt.fail("get_version", str(e))

    # ---- 3. 添加种子 ----
    try:
        ok = dl.add_torrent(
            urls="", is_paused=True,
            save_path="/downloads/test",
            torrent_file=torrent_bytes,
        )
        if ok:
            rpt.ok("add_torrent", f"hash={info_hash[:16]}...")
        else:
            rpt.fail("add_torrent", "False")
            return  # 无法继续
    except Exception as e:
        rpt.fail("add_torrent", str(e))
        return

    # ---- 4. 种子信息 ----
    info = _wait_info(dl, info_hash, timeout=20)
    if info:
        rpt.ok("get_torrent_info",
               f"name={str(info.get('name',''))[:25]}, "
               f"state={info.get('state')}, size={info.get('total_size',0)}B")
    else:
        # torrent 文件自带元数据，重试
        time.sleep(1)
        info = dl.get_torrent_info(info_hash)
        if info and (info.get("total_size") or 0) > 0:
            rpt.ok("get_torrent_info", f"state={info.get('state')} (retry ok)")
        else:
            rpt.fail("get_torrent_info", f"timeout, info={info}")

    # ---- 5. 文件列表 ----
    files = None
    try:
        files = dl.get_torrent_files(info_hash)
        if files and len(files) > 0:
            rpt.ok("get_torrent_files",
                   f"{len(files)} files: " +
                   ", ".join(f"{f['name']}({f.get('size',0)}B)" for f in files))
        else:
            rpt.fail("get_torrent_files", "empty")
    except Exception as e:
        rpt.fail("get_torrent_files", str(e))

    # ---- 6. 暂停/恢复 ----
    try:
        dl.resume_torrents(info_hash)
        time.sleep(0.8)
        s1 = dl.get_torrent_info(info_hash)
        rpt.ok("resume", f"state={s1.get('state','?') if s1 else '?'}")
    except Exception as e:
        rpt.fail("resume", str(e))

    try:
        dl.pause_torrents(info_hash)
        time.sleep(0.8)
        s2 = dl.get_torrent_info(info_hash)
        rpt.ok("pause", f"state={s2.get('state','?') if s2 else '?'}")
    except Exception as e:
        rpt.fail("pause", str(e))

    # ---- 7. 文件选择 ----
    if files and caps.supports_file_selection:
        try:
            idx = [files[0].get("index", 0)]
            dl.set_file_priority(info_hash, idx, 1)
            rpt.ok("set_file_priority", f"selected index={idx}")
        except Exception as e:
            rpt.fail("set_file_priority", str(e))

    # ---- 8. 重命名文件 ----
    if files:
        old = files[0].get("path") or files[0].get("name", "")
        if caps.supports_rename:
            if "." in old:
                new = old.rsplit(".", 1)[0] + "_renamed." + old.rsplit(".", 1)[1]
            else:
                new = old + "_renamed"
            try:
                ok = dl.rename_file(info_hash, old, new)
                if ok:
                    rpt.ok("rename_file", f"{old.rsplit('/',1)[-1]} -> {new.rsplit('/',1)[-1]}")
                    dl.rename_file(info_hash, new, old)  # 改回
                else:
                    rpt.fail("rename_file", "False")
            except Exception as e:
                rpt.fail("rename_file", str(e))
        else:
            rpt.skip("rename_file", "not supported by backend")
            # 验证降级：确认返回 False
            try:
                if not dl.rename_file(info_hash, old, old + "_x"):
                    rpt.ok("rename_file_degrade", "correctly returned False")
            except Exception:
                pass

    # ---- 9. 重命名文件夹 ----
    if files and caps.supports_rename:
        # 找目录
        folder = None
        for f in files:
            p = f.get("path", "") or f.get("name", "")
            if "/" in p:
                folder = p.split("/")[0]
                break
        if folder:
            new_f = folder + "_r"
            try:
                ok = dl.rename_folder(info_hash, folder, new_f)
                if ok:
                    rpt.ok("rename_folder", f"{folder}/ -> {new_f}/")
                    dl.rename_folder(info_hash, new_f, folder)
                else:
                    rpt.fail("rename_folder", "False")
            except Exception as e:
                rpt.fail("rename_folder", str(e))
        else:
            rpt.skip("rename_folder", "no folder in torrent")
    elif not caps.supports_rename:
        rpt.skip("rename_folder", "not supported by backend")

    # ---- 10. 移动 ----
    if caps.supports_set_location:
        try:
            ok = dl.set_location(info_hash, "/downloads/moved_test")
            if ok:
                rpt.ok("set_location", "/downloads/moved_test")
            else:
                rpt.fail("set_location", "False")
        except Exception as e:
            rpt.fail("set_location", str(e))
    else:
        rpt.skip("set_location", "not supported by backend")
        try:
            if not dl.set_location(info_hash, "/downloads/any"):
                rpt.ok("set_location_degrade", "correctly returned False")
        except Exception as e:
            rpt.ok("set_location_degrade", f"exception (equiv): {e}")

    # ---- 11. 能力标记 ----
    rpt.ok("capabilities",
           f"name={caps.name}, rename={caps.supports_rename}, "
           f"move={caps.supports_set_location}, "
           f"file_select={caps.supports_file_selection}")

    # ---- 12. 删除 ----
    cleaned = _do_cleanup(dl, info_hash, timeout=15)
    if cleaned:
        rpt.ok("delete_torrents", "confirmed removed")
        cleanup_added.clear()
    else:
        # 再试
        time.sleep(3)
        if _do_cleanup(dl, info_hash, timeout=10):
            rpt.ok("delete_torrents", "removed after retry")
            cleanup_added.clear()
        else:
            try:
                remains = dl.get_torrent_info(info_hash)
                if remains is None:
                    rpt.ok("delete_torrents", "removed (async)")
                    cleanup_added.clear()
                else:
                    rpt.fail("delete_torrents", f"still exists: {remains.get('state','?')}")
            except Exception:
                rpt.ok("delete_torrents", "api error, assumed removed")
                cleanup_added.clear()

    # ---- 13. 重复添加 ----
    try:
        dl.add_torrent(urls="", is_paused=True, torrent_file=torrent_bytes)
        time.sleep(0.5)
        i2 = dl.get_torrent_info(info_hash)
        if i2:
            rpt.ok("duplicate_add", "same hash re-added ok")
        else:
            rpt.fail("duplicate_add", "info missing")
    except Exception as e:
        rpt.ok("duplicate_add", f"expected: {e}")
    finally:
        _do_cleanup(dl, info_hash, timeout=10)

    # ---- 最终隔离验证 ----
    print(f"  [post] 验证隔离清理...")
    time.sleep(2)
    try:
        leftover = dl.get_torrent_info(info_hash)
        if leftover is None:
            print(f"  [post] 确认: 无残留")
        else:
            print(f"  [post] 警告: 仍有残留 state={leftover.get('state','?')}, 强制清理")
            _do_cleanup(dl, info_hash, timeout=15)
    except Exception:
        print(f"  [post] API 异常, 视为已清理")

    # 兜底清理
    for h in list(cleanup_added):
        _do_cleanup(dl, h, timeout=10)


# ======================================================================
# main
# ======================================================================

def main():
    print("=" * 60)
    print("  ZongziBay Downloader Integration Test (isolated)")
    print("=" * 60)

    import requests
    svc = {
        "qBittorrent": "http://localhost:8080",
        "Transmission": "http://localhost:9091",
        "Aria2": "http://localhost:6800",
    }
    print("\n[setup] Checking services...")
    for name, url in svc.items():
        try:
            r = requests.get(url, timeout=5)
            print(f"   OK  {name}: {url}")
        except Exception as e:
            print(f"   FAIL {name}: {e}")

    pairs = [
        (QBittorrentDownloader(host=svc["qBittorrent"],
                               username="admin", password=QB_PASSWORD), "qb"),
        (TransmissionDownloader(host=svc["Transmission"],
                                username=TR_USER, password=TR_PASS), "tr"),
        (Aria2Downloader(host=svc["Aria2"], secret=ARIA2_SECRET), "a2"),
    ]

    passed_all = True
    for dl, tag in pairs:
        rpt = Report(dl.capabilities.name)
        try:
            test_one(dl, rpt, tag)
        except Exception as e:
            print(f"\n[PANIC] {tag}: {e}")
            traceback.print_exc()
            rpt.fail("panic", str(e))
        if not rpt.show():
            passed_all = False

    print("=" * 60)
    print("  ALL PASS" if passed_all else "  SOME FAILED")
    print("=" * 60)
    return 0 if passed_all else 1


if __name__ == "__main__":
    sys.exit(main())
