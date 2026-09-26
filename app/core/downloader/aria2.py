"""Aria2 下载器适配器（降级实现）

RPC 端点：POST /jsonrpc（JSON-RPC 2.0）
认证：rpc-secret token（参数首元素 "token:<secret>"）

能力（相比 qB/Transmission 有降级）：
- supports_rename: False —— Aria2 无种子内文件/目录重命名 API，需降级为复制归档模式
- supports_set_location: False —— 无移动已下载文件 API，需降级为复制归档模式
- supports_paused_metadata: False —— 暂停添加时不拉元数据，磁力解析需用 bt-metadata-only 方案
- supports_file_selection: True —— 通过 select-file 选项（需元数据就绪后设置）

关键方法映射：
- 添加磁力: aria2.addUri([magnet], options)
- 添加种子: aria2.addTorrent(base64, [], options)
- 文件列表: aria2.getFiles(gid)
- 状态: aria2.tellStatus(gid)
- 选择文件: aria2.changeOption(gid, {select-file: "1,2,3"})
- 删除: aria2.remove(gid) + aria2.removeDownloadResult(gid)

Aria2 以 gid 标识任务而非 info hash，本适配器通过扫描任务列表按 infoHash 匹配实现 hash→gid。
"""

import base64
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from app.core.downloader.base import BaseDownloader, DownloaderCapabilities, TorrentFile
from app.schemas.base import BusinessException, ErrorCode

logger = logging.getLogger(__name__)

# Aria2 status → qB 风格状态
_ARIA_STATUS_MAP = {
    "active": "downloading",
    "waiting": "queuedDL",
    "paused": "pausedDL",
    "error": "error",
    "complete": "uploading",   # 下载完成进入做种
    "removed": "removed",
}


class Aria2Downloader(BaseDownloader):
    """Aria2 下载后端（降级实现）"""

    capabilities = DownloaderCapabilities(
        name="aria2",
        supports_file_selection=True,
        supports_rename=False,
        supports_set_location=False,
        supports_paused_metadata=False,
        supports_magnet=True,
        supports_torrent_file=True,
        supports_seeding_ratio=True,
    )

    def __init__(self, host: str = "", secret: str = ""):
        self.host = (host or "http://localhost:6800").strip().rstrip("/")
        self.secret = secret
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # 内部 RPC
    # ------------------------------------------------------------------

    def _rpc(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """发送 JSON-RPC 请求。params 不含 token，由内部自动附加。"""
        full_params: List[Any] = []
        if self.secret:
            full_params.append(f"token:{self.secret}")
        if params:
            full_params.extend(params)

        payload = {
            "jsonrpc": "2.0",
            "id": "zongzibay",
            "method": method,
            "params": full_params,
        }
        url = f"{self.host}/jsonrpc"
        resp = self.session.post(url, json=payload, timeout=15)
        if resp.status_code != 200:
            raise BusinessException(
                code=ErrorCode.SYSTEM_ERROR,
                message=f"Aria2 RPC 失败: HTTP {resp.status_code}",
            )
        data = resp.json()
        if "error" in data:
            err = data.get("error", {})
            raise BusinessException(
                code=ErrorCode.SYSTEM_ERROR,
                message=f"Aria2 RPC 错误: {err.get('message', err)}",
            )
        return data.get("result")

    # ------------------------------------------------------------------
    # BaseDownloader 实现
    # ------------------------------------------------------------------

    def check_connection(self) -> bool:
        try:
            self._rpc("aria2.getVersion")
            return True
        except Exception as e:
            logger.error(f"Aria2 连接失败: {e}")
            return False

    def get_version(self) -> str:
        try:
            result = self._rpc("aria2.getVersion")
            return str((result or {}).get("version", "unknown"))
        except Exception as e:
            logger.error(f"Aria2 获取版本失败: {e}")
            return "unknown"

    def add_torrent(
        self,
        urls: str,
        is_paused: bool = False,
        save_path: Optional[str] = None,
        content_layout: Optional[str] = None,
        torrent_file: Optional[bytes] = None,
    ) -> bool:
        options: Dict[str, Any] = {}
        if save_path:
            options["dir"] = save_path
        # Aria2 无 contentLayout 概念；忽略该参数

        try:
            if torrent_file:
                b64 = base64.b64encode(torrent_file).decode("ascii")
                self._rpc("aria2.addTorrent", [b64, [], options])
                return True
            if urls:
                # 磁力链接（或 HTTP 种子）
                self._rpc("aria2.addUri", [[urls], options])
                return True
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="未提供种子地址或文件")
        except Exception as e:
            logger.error(f"Aria2 添加种子失败: {e}")
            if isinstance(e, BusinessException):
                raise
            return False

    @staticmethod
    def _is_metadata_only_task(task: Dict[str, Any]) -> bool:
        """是否为 bt-metadata-only 建出来的「只拉元数据」临时任务。

        这种任务与随后的真实下载任务共享同一个 infoHash。若不排除，按 hash
        查找就会命中它，上层拿到的 name / content_path 会变成 [METADATA] 占位文件，
        归档阶段找不到目标而无限重试。
        """
        # 真实 BT 任务带 mode（single/multi）；只拉元数据的任务没有
        if (task.get("bittorrent") or {}).get("mode"):
            return False
        files = task.get("files") or []
        if not files:
            return False
        return all(
            str(f.get("path", "")).replace("\\", "/").split("/")[-1].startswith("[METADATA]")
            for f in files
        )

    def _find_gid_by_hash(self, torrent_hash: str) -> Optional[str]:
        """通过扫描所有任务，按 infoHash 匹配定位 gid

        跳过 bt-metadata-only 的临时任务（见 _is_metadata_only_task）。
        """
        for state in ("tellActive", "tellWaiting", "tellStopped"):
            try:
                params = [0, 1000] if state in ("tellWaiting", "tellStopped") else []
                results = self._rpc(f"aria2.{state}", params) or []
                for t in results:
                    # Aria2 tellActive/tellWaiting/tellStopped 顶层即有 infoHash（bittorrent 子对象不含）
                    info_hash = t.get("infoHash") or ((t.get("bittorrent") or {}).get("infoHash"))
                    if (info_hash or "").lower() != torrent_hash.lower():
                        continue
                    if self._is_metadata_only_task(t):
                        continue
                    return t.get("gid")
            except Exception as e:
                logger.warning(f"Aria2 扫描 {state} 失败: {e}")
        return None

    def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        gid = self._find_gid_by_hash(torrent_hash)
        if not gid:
            return None
        try:
            t = self._rpc("aria2.tellStatus", [gid])
            # removed 状态：任务已被删除，视为不存在，供上层走「任务消失」分支
            if t.get("status") == "removed":
                return None
            return self._normalize_info(t, torrent_hash)
        except Exception as e:
            logger.error(f"Aria2 获取种子信息失败: {e}")
            return None

    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        gid = self._find_gid_by_hash(torrent_hash)
        if not gid:
            return []
        try:
            files = self._rpc("aria2.getFiles", [gid]) or []
            result = []
            for idx, f in enumerate(files):
                path = f.get("path", "")
                name = path.replace("\\", "/").split("/")[-1]
                result.append({
                    "index": idx,
                    "name": name,
                    "path": path,
                    "size": int(f.get("length", 0) or 0),
                })
            return result
        except Exception as e:
            logger.error(f"Aria2 获取文件列表失败: {e}")
            return []

    def delete_torrents(self, hashes: str, delete_files: bool = True) -> bool:
        """Aria2 无「删除时同时删文件」API；remove 仅移除任务记录。

        - 对 active/waiting/paused 任务：aria2.remove（立即停止并移除，任务进入 removed 状态）
        - 对已 error/complete 的任务：aria2.removeDownloadResult 直接清结果
        - removed 状态的任务 removeDownloadResult 会报 400（时序竞态），忽略即可
        """
        for h in hashes.split("|"):
            h = h.strip()
            if not h:
                continue
            gid = self._find_gid_by_hash(h)
            if not gid:
                continue
            try:
                status = None
                try:
                    t = self._rpc("aria2.tellStatus", [gid])
                    status = t.get("status")
                except Exception:
                    pass
                if status in ("error", "complete", "removed"):
                    # 已完成/出错/已移除的任务不在 active 队列，只能清结果
                    self._rpc("aria2.removeDownloadResult", [gid])
                else:
                    # active/waiting/paused：remove 后任务已从队列移除，无需再清结果
                    self._rpc("aria2.remove", [gid])
            except Exception as e:
                logger.warning(f"Aria2 删除种子失败 {gid}（可能已移除）: {e}")
        return True

    def set_file_priority(self, torrent_hash: str, file_ids: List[int], priority: int) -> bool:
        """Aria2 用 select-file 表达文件选择（select-file 为逗号分隔的 1-based 索引）。"""
        # 需要拿到当前全部文件以计算「要下载的集合」；select-file 是整体设置。
        # 由于 Aria2 以 add 时的选项一次性决定，这里仅当能取到完整列表时支持。
        try:
            gid = self._find_gid_by_hash(torrent_hash)
            if not gid:
                return False
            files = self._rpc("aria2.getFiles", [gid]) or []
            total = len(files)
            if total == 0:
                return False
            current = [i + 1 for i in range(total)]
            if priority == 0:
                current = [i for i in current if (i - 1) not in file_ids]
            else:
                current = sorted(set(current) | set(i + 1 for i in file_ids))
            select = ",".join(str(i) for i in current)
            self._rpc("aria2.changeOption", [gid, {"select-file": select}])
            return True
        except Exception as e:
            logger.error(f"Aria2 设置文件优先级失败: {e}")
            return False

    def resume_torrents(self, hashes: str) -> bool:
        for h in hashes.split("|"):
            h = h.strip()
            if not h:
                continue
            gid = self._find_gid_by_hash(h)
            if not gid:
                continue
            try:
                # aria2.unpause 仅在 paused/waiting 状态有效；active 状态调用会报错，
                # 但任务已在运行，视为恢复成功（幂等容错）。
                self._rpc("aria2.unpause", [gid])
            except Exception as e:
                logger.warning(f"Aria2 恢复种子失败 {gid}（可能已在运行）: {e}")
        return True

    def pause_torrents(self, hashes: str) -> bool:
        for h in hashes.split("|"):
            h = h.strip()
            if not h:
                continue
            gid = self._find_gid_by_hash(h)
            if not gid:
                continue
            try:
                # aria2.pause 对已 paused 任务会报错，视为已暂停（幂等容错）。
                self._rpc("aria2.pause", [gid])
            except Exception as e:
                logger.warning(f"Aria2 暂停种子失败 {gid}（可能已暂停）: {e}")
        return True

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """Aria2 不支持种子内重命名。返回 False，上层降级为复制归档。"""
        logger.warning(f"Aria2 不支持种子内文件重命名: {old_path} -> {new_path}")
        return False

    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """Aria2 不支持种子内重命名。返回 False，上层降级为复制归档。"""
        logger.warning(f"Aria2 不支持种子内目录重命名: {old_path} -> {new_path}")
        return False

    def set_location(self, hashes: str, location: str) -> bool:
        """Aria2 无移动已下载文件 API。返回 False，上层降级为复制归档。"""
        logger.warning(f"Aria2 不支持移动已下载文件: -> {location}")
        return False

    # ------------------------------------------------------------------
    # 磁力解析：Aria2 暂停时不拉元数据，用 bt-metadata-only 方案
    # ------------------------------------------------------------------

    def parse_magnet(self, magnet_link: str, timeout: int = 60) -> List[TorrentFile]:
        """通过 bt-metadata-only + bt-save-metadata 只拉元数据，不下载文件数据。"""
        torrent_hash = self.extract_info_hash(magnet_link)
        if not torrent_hash:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无效的磁力链接")

        options = {
            "bt-metadata-only": "true",
            "bt-save-metadata": "true",
        }
        gid = None
        try:
            gid = self._rpc("aria2.addUri", [[magnet_link], options])
        except Exception as e:
            logger.error(f"Aria2 解析磁力：添加失败 {e}")
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="添加种子失败")

        try:
            start = time.time()
            while time.time() - start < timeout:
                try:
                    t = self._rpc("aria2.tellStatus", [gid])
                    # 元数据就绪后 infoHash 出现（顶层）且 getFiles 可返回
                    info_hash = t.get("infoHash") or ((t.get("bittorrent") or {}).get("infoHash"))
                    if info_hash:
                        files = self._rpc("aria2.getFiles", [gid]) or []
                        if files:
                            normalized = self._normalize_files([
                                {
                                    "index": i,
                                    "name": f.get("path", "").replace("\\", "/").split("/")[-1],
                                    "path": f.get("path", ""),
                                    "size": int(f.get("length", 0) or 0),
                                }
                                for i, f in enumerate(files)
                            ])
                            # 过滤 Aria2 元数据阶段的占位文件 [METADATA]xxx（size=0 且路径含 METADATA）
                            real = [f for f in normalized if not f.name.startswith("[METADATA]")]
                            if real:
                                return real
                except Exception as e:
                    logger.warning(f"Aria2 轮询元数据出错: {e}")
                time.sleep(2)
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="等待元数据超时")
        finally:
            if gid:
                try:
                    # remove 后任务进入 removed 状态，removeDownloadResult 会报 400，忽略即可
                    self._rpc("aria2.remove", [gid])
                except Exception:
                    pass
                try:
                    self._rpc("aria2.removeDownloadResult", [gid])
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _normalize_info(self, t: Dict[str, Any], fallback_hash: str) -> Dict[str, Any]:
        status = t.get("status", "")
        state = _ARIA_STATUS_MAP.get(status, "downloading")
        if status == "complete" and t.get("seeder") is True:
            state = "uploading"

        total = int(t.get("totalLength", 0) or 0)
        completed = int(t.get("completedLength", 0) or 0)
        upload = int(t.get("uploadLength", 0) or 0)
        progress = (completed / total) if total else 0.0

        bt = t.get("bittorrent") or {}
        name = ""
        info = bt.get("info") or {}
        if isinstance(info, dict):
            name = info.get("name", "")
        if not name and t.get("files"):
            name = (t.get("files") or [{}])[0].get("path", "").replace("\\", "/").split("/")[-1]

        save_path = t.get("dir", "")
        # tellStatus 顶层即有 infoHash（bittorrent 子对象不含）
        info_hash = t.get("infoHash") or (bt.get("infoHash") or "")
        return {
            "hash": (info_hash or fallback_hash),
            "name": name,
            "state": state,
            "progress": float(progress),
            "total_size": total,
            "save_path": save_path,
            "ratio": (upload / total) if total else 0.0,
            "content_path": "",
            "files": t.get("files", []),
        }
