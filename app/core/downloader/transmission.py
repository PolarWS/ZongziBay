"""Transmission 下载器适配器

RPC 端点：POST /transmission/rpc（JSON-RPC 风格）
认证：首次请求会返回 409 + X-Transmission-Session-Id 头，需带该头重发。
能力：支持文件选择、种子内重命名、移动位置、做种分享率。
注意：Transmission 在暂停态下不会连接 peer，拿不到元数据（supports_paused_metadata=False），
所以选文件与磁力解析都必须「运行态添加 → 等元数据就绪 → 再操作」。

关键方法映射：
- 添加: torrent-add（filename=磁力/URL，或 metainfo=base64 种子）
- 文件选择: torrent-set 的 files-wanted / files-unwanted
- 重命名: torrent-rename-path
- 移动: torrent-set-location
- 删除: torrent-remove（delete-local-data）
"""

import base64
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from app.core.downloader.base import BaseDownloader, DownloaderCapabilities, TorrentFile
from app.schemas.base import BusinessException, ErrorCode

logger = logging.getLogger(__name__)

# Transmission 状态码 → qB 风格状态
_TR_STATUS_MAP = {
    0: "pausedDL",      # STOPPED
    1: "queuedDL",      # CHECK_WAIT
    2: "checkingDL",    # CHECK
    3: "queuedDL",      # DOWNLOAD_WAIT
    4: "downloading",   # DOWNLOAD
    5: "queuedUP",      # SEED_WAIT
    6: "uploading",     # SEED
}


class TransmissionDownloader(BaseDownloader):
    """Transmission 下载后端"""

    capabilities = DownloaderCapabilities(
        name="transmission",
        supports_file_selection=True,
        supports_rename=True,
        supports_set_location=True,
        # Transmission 暂停时不连 peer，元数据永远拉不到，
        # 因此只能「运行态添加 → 等元数据 → 再筛选文件」。
        supports_paused_metadata=False,
        supports_runtime_file_selection=True,
        supports_magnet=True,
        supports_torrent_file=True,
        supports_seeding_ratio=True,
    )

    def __init__(self, host: str = "", username: str = "", password: str = ""):
        # 去掉首尾空白：设置页粘贴地址时容易带上空格，会污染落库值
        self.host = (host or "http://localhost:9091").strip().rstrip("/")
        self.username = username
        self.password = password
        self._session_id: Optional[str] = None
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # 内部 RPC
    # ------------------------------------------------------------------

    def _rpc(self, method: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送 RPC 请求，自动处理 session-id 协商"""
        payload = {"method": method, "arguments": arguments or {}}
        url = f"{self.host}/transmission/rpc"
        headers = {}
        if self._session_id:
            headers["X-Transmission-Session-Id"] = self._session_id
        if self.username or self.password:
            auth = requests.auth.HTTPBasicAuth(self.username, self.password)
        else:
            auth = None

        resp = self.session.post(url, json=payload, headers=headers, auth=auth, timeout=15)
        if resp.status_code == 409:
            self._session_id = resp.headers.get("X-Transmission-Session-Id")
            if not self._session_id:
                raise BusinessException(code=ErrorCode.SYSTEM_ERROR, message="Transmission 返回 409 但无 Session-Id")
            headers["X-Transmission-Session-Id"] = self._session_id
            resp = self.session.post(url, json=payload, headers=headers, auth=auth, timeout=15)

        if resp.status_code != 200:
            raise BusinessException(
                code=ErrorCode.SYSTEM_ERROR,
                message=f"Transmission RPC 失败: HTTP {resp.status_code}",
            )
        data = resp.json()
        if data.get("result") != "success":
            raise BusinessException(
                code=ErrorCode.SYSTEM_ERROR,
                message=f"Transmission RPC 错误: {data.get('result')}",
            )
        return data.get("arguments", {})

    # ------------------------------------------------------------------
    # BaseDownloader 实现
    # ------------------------------------------------------------------

    def check_connection(self) -> bool:
        try:
            self._rpc("session-get", {"fields": ["version"]})
            return True
        except Exception as e:
            logger.error(f"Transmission 连接失败: {e}")
            return False

    def get_version(self) -> str:
        try:
            args = self._rpc("session-get", {"fields": ["version"]})
            return str(args.get("version", "unknown"))
        except Exception as e:
            logger.error(f"Transmission 获取版本失败: {e}")
            return "unknown"

    def add_torrent(
        self,
        urls: str,
        is_paused: bool = False,
        save_path: Optional[str] = None,
        content_layout: Optional[str] = None,
        torrent_file: Optional[bytes] = None,
    ) -> bool:
        try:
            arguments: Dict[str, Any] = {"paused": is_paused}
            if torrent_file:
                arguments["metainfo"] = base64.b64encode(torrent_file).decode("ascii")
            elif urls:
                arguments["filename"] = urls
            else:
                raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="未提供种子地址或文件")
            if save_path:
                arguments["download-dir"] = save_path
            # Transmission 不直接支持 contentLayout；保持默认目录结构即可
            self._rpc("torrent-add", arguments)
            return True
        except Exception as e:
            logger.error(f"Transmission 添加种子失败: {e}")
            if isinstance(e, BusinessException):
                raise
            return False

    def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        try:
            args = self._rpc("torrent-get", {
                "ids": [torrent_hash],
                "fields": [
                    "hashString", "name", "status", "percentDone", "totalSize",
                    "downloadDir", "ratio", "isFinished", "metadataPercentComplete",
                    "files",
                ],
            })
            torrents = args.get("torrents", [])
            if not torrents:
                return None
            t = torrents[0]
            state = self._map_state(t.get("status"), t.get("isFinished", False))
            return {
                "hash": t.get("hashString") or torrent_hash,
                "name": t.get("name", ""),
                "state": state,
                "progress": float(t.get("percentDone", 0) or 0),
                "total_size": int(t.get("totalSize", 0) or 0),
                "save_path": t.get("downloadDir", ""),
                "ratio": float(t.get("ratio", 0) or 0),
                "content_path": "",
                "files": t.get("files", []),
            }
        except Exception as e:
            logger.error(f"Transmission 获取种子信息失败: {e}")
            return None

    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        try:
            args = self._rpc("torrent-get", {
                "ids": [torrent_hash],
                "fields": ["files"],
            })
            torrents = args.get("torrents", [])
            if not torrents:
                return []
            files = torrents[0].get("files", [])
            result = []
            for idx, f in enumerate(files):
                name = f.get("name", "")
                result.append({
                    "index": idx,
                    "name": name.replace("\\", "/").split("/")[-1],
                    "path": name,
                    "size": int(f.get("length", 0) or 0),
                })
            return result
        except Exception as e:
            logger.error(f"Transmission 获取文件列表失败: {e}")
            return []

    def delete_torrents(self, hashes: str, delete_files: bool = True) -> bool:
        try:
            ids = [h.strip() for h in hashes.split("|") if h.strip()] or [hashes]
            self._rpc("torrent-remove", {
                "ids": ids,
                "delete-local-data": delete_files,
            })
            return True
        except Exception as e:
            logger.error(f"Transmission 删除种子失败: {e}")
            return False

    def set_file_priority(self, torrent_hash: str, file_ids: List[int], priority: int) -> bool:
        """Transmission 用 files-wanted / files-unwanted 表达文件选择"""
        try:
            if priority == 0:
                self._rpc("torrent-set", {"ids": [torrent_hash], "files-unwanted": list(file_ids)})
            else:
                self._rpc("torrent-set", {"ids": [torrent_hash], "files-wanted": list(file_ids)})
            return True
        except Exception as e:
            logger.error(f"Transmission 设置文件优先级失败: {e}")
            return False

    def resume_torrents(self, hashes: str) -> bool:
        try:
            ids = [h.strip() for h in hashes.split("|") if h.strip()] or [hashes]
            self._rpc("torrent-start", {"ids": ids})
            return True
        except Exception as e:
            logger.error(f"Transmission 恢复种子失败: {e}")
            return False

    def pause_torrents(self, hashes: str) -> bool:
        try:
            ids = [h.strip() for h in hashes.split("|") if h.strip()] or [hashes]
            self._rpc("torrent-stop", {"ids": ids})
            return True
        except Exception as e:
            logger.error(f"Transmission 暂停种子失败: {e}")
            return False

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        try:
            new_name = new_path
            # 若 new_path 含目录，仅取文件名部分（Transmission rename 只改单个路径节点）
            if "/" in new_path:
                new_name = new_path.rstrip("/").split("/")[-1]
            self._rpc("torrent-rename-path", {
                "ids": [torrent_hash],
                "path": old_path,
                "name": new_name,
            })
            return True
        except Exception as e:
            logger.error(f"Transmission 重命名文件失败: {e}")
            return False

    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        try:
            new_name = new_path.rstrip("/").split("/")[-1]
            self._rpc("torrent-rename-path", {
                "ids": [torrent_hash],
                "path": old_path,
                "name": new_name,
            })
            return True
        except Exception as e:
            logger.error(f"Transmission 重命名文件夹失败: {e}")
            return False

    def set_location(self, hashes: str, location: str) -> bool:
        try:
            ids = [h.strip() for h in hashes.split("|") if h.strip()] or [hashes]
            self._rpc("torrent-set-location", {
                "ids": ids,
                "location": location,
                "move": True,
            })
            return True
        except Exception as e:
            logger.error(f"Transmission 移动种子失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 磁力解析：必须运行态添加，暂停态拉不到元数据
    # ------------------------------------------------------------------

    def parse_magnet(self, magnet_link: str, timeout: int = 60) -> List[TorrentFile]:
        torrent_hash = self.extract_info_hash(magnet_link)
        if not torrent_hash:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无效的磁力链接")
        try:
            # 不能用 is_paused=True：Transmission 暂停时不连 peer，元数据永远拿不到。
            # 解析期间会有少量数据写入，finally 中连同临时种子一起删除。
            self.add_torrent(urls=magnet_link, is_paused=False)
        except Exception:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="添加种子失败")

        try:
            start = time.time()
            while time.time() - start < timeout:
                info = self.get_torrent_info(torrent_hash)
                if info and (info.get("total_size") or 0) > 0:
                    return self._normalize_files(self.get_torrent_files(torrent_hash))
                time.sleep(2)
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="等待元数据超时")
        finally:
            try:
                self.delete_torrents(torrent_hash, delete_files=True)
            except Exception as e:
                logger.warning(f"解析磁力：删除临时种子失败 {torrent_hash}: {e}")

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _map_state(status: int, is_finished: bool) -> str:
        state = _TR_STATUS_MAP.get(status, "downloading")
        if state == "pausedDL" and is_finished:
            return "pausedUP"
        return state
