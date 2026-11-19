"""下载器抽象基类

统一 qBittorrent / Transmission / Aria2 的下载能力接口。

设计要点：
1. 方法名与原有 qBittorrentClient 保持一致，上层服务（task_service / task_monitor /
   magnet_service）无需感知后端差异，改动最小。
2. get_torrent_info 返回**规范化 dict**，字段对齐 qB 兼容格式：
   hash / name / state / progress(0~1) / total_size / save_path / ratio / content_path
   state 为 qB 风格状态字符串，task_monitor._map_status 可直接复用。
3. get_torrent_files 返回 [{name, path, size, index}]，index 用于文件优先级操作。
4. capabilities 标记各后端能力，上层可据此做降级：
   - supports_file_selection：能否在下载时选择部分文件
   - supports_rename：能否在种子内重命名文件/目录（Aria2 不支持）
   - supports_set_location：能否移动已下载文件位置（Aria2 不支持）
   - supports_paused_metadata：暂停添加时是否仍拉取元数据（Aria2 / Transmission 不支持）
   - supports_runtime_file_selection：是否支持「运行态选文件」——添加时不暂停，
     等元数据就绪后再设优先级。Transmission 暂停时不连 peer，只能走这条路径。
"""

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.schemas.base import BusinessException, ErrorCode

logger = logging.getLogger(__name__)


@dataclass
class TorrentFile:
    """种子内的单个文件（规范化结构）"""
    index: int          # 文件索引，用于优先级/选择操作
    name: str           # 文件名
    path: str           # 种子内相对路径（可含子目录）
    size: int           # 字节大小


@dataclass
class DownloaderCapabilities:
    """后端能力标记，供上层做功能降级"""
    name: str = "unknown"
    supports_file_selection: bool = True    # 支持在下载时选择部分文件
    supports_rename: bool = True            # 支持种子内文件/目录重命名
    supports_set_location: bool = True      # 支持移动已下载文件位置
    supports_paused_metadata: bool = True   # 暂停添加时仍拉取元数据
    # 运行态选文件：添加时不暂停，等元数据就绪后再设置文件优先级。
    # 适用于「暂停时不连 peer、拿不到元数据」但仍支持文件选择的后端（Transmission）。
    supports_runtime_file_selection: bool = False
    supports_magnet: bool = True            # 支持磁力链接
    supports_torrent_file: bool = True      # 支持 .torrent 文件上传
    supports_seeding_ratio: bool = True     # 支持做种分享率限制


def _bdecode(data: bytes, pos: int = 0):
    """递归解析 bencode 数据，返回 (值, 新位置)"""
    if pos >= len(data):
        raise ValueError("bencode: 数据截断")
    c = data[pos:pos + 1]
    if c == b"i":  # 整数
        end = data.index(b"e", pos)
        return int(data[pos + 1:end]), end + 1
    if c == b"l":  # 列表
        pos += 1
        out = []
        while data[pos:pos + 1] != b"e":
            v, pos = _bdecode(data, pos)
            out.append(v)
        return out, pos + 1
    if c == b"d":  # 字典
        pos += 1
        out = {}
        while data[pos:pos + 1] != b"e":
            k, pos = _bdecode(data, pos)
            v, pos = _bdecode(data, pos)
            out[k.decode("utf-8", "replace")] = v
        return out, pos + 1
    # 字符串: <长度>:<内容>
    colon = data.index(b":", pos)
    length = int(data[pos:colon])
    start = colon + 1
    return data[start:start + length], start + length


def _bencode_torrent_info_hash(torrent_bytes: bytes) -> Optional[str]:
    """从 .torrent 文件的 info 段计算 info hash（40 位小写 hex）

    info hash = SHA1(bencode(info 字典) 原始字节)。通过 _bdecode 的位置追踪
    精确切分出 info 值在原始字节流中的区间，再计算 SHA1。
    """
    try:
        idx = torrent_bytes.find(b"4:info")
        if idx < 0:
            return None
        # 键 '4:info' 占 6 字节，其后为 info 字典的原始 bencode 字节
        value_start = idx + 6
        value, value_end = _bdecode(torrent_bytes, value_start)
        if not isinstance(value, dict):
            return None
        raw_info = torrent_bytes[value_start:value_end]
        return hashlib.sha1(raw_info).hexdigest()
    except Exception as e:
        logger.warning(f"解析 .torrent info hash 失败: {e}")
        return None


def _bencode_torrent_files(torrent_bytes: bytes) -> List[TorrentFile]:
    """从 .torrent 文件本地解析文件列表（不依赖下载器）"""
    try:
        torrent, _ = _bdecode(torrent_bytes)
        info = torrent.get("info", {})
        files_raw = info.get("files", [])
        if files_raw:  # 多文件
            result = []
            for i, f in enumerate(files_raw):
                path_parts = f.get("path", [])
                path = "/".join(p.decode("utf-8", "replace") if isinstance(p, bytes) else str(p) for p in path_parts)
                result.append(TorrentFile(
                    index=i,
                    name=path.split("/")[-1],
                    path=path,
                    size=int(f.get("length", 0) or 0),
                ))
            return result
        # 单文件
        name = info.get("name", b"")
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        return [TorrentFile(index=0, name=str(name), path=str(name), size=int(info.get("length", 0) or 0))]
    except Exception as e:
        logger.warning(f"解析 .torrent 文件列表失败: {e}")
        return []


def _extract_info_hash(url_or_magnet: str) -> Optional[str]:
    """从磁力链接或纯 hash 中提取 40 位小写 info hash"""
    if not url_or_magnet:
        return None
    m = re.search(r"btih:([a-zA-Z0-9]+)", url_or_magnet)
    if m:
        raw = m.group(1).lower()
        # 32 位 Base32 → 40 位 hex（复用 magnet_service 的规范化逻辑）
        if len(raw) == 32:
            try:
                import base64
                return base64.b32decode(raw.upper()).hex()
            except Exception:
                pass
        return raw
    s = url_or_magnet.strip().lower()
    if re.fullmatch(r"[a-f0-9]{40}", s):
        return s
    if re.fullmatch(r"[a-z0-9]{32}", s):
        try:
            import base64
            return base64.b32decode(s.upper()).hex()
        except Exception:
            pass
    return None


class BaseDownloader(ABC):
    """下载器抽象基类。

    子类需实现：check_connection / get_version / add_torrent / get_torrent_info /
    get_torrent_files / delete_torrents / set_file_priority / resume_torrents /
    pause_torrents / rename_file / rename_folder / set_location。
    parse_magnet / parse_torrent_file 提供基于「临时添加 → 轮询元数据 → 取文件 → 删除」的默认实现，
    各后端可在能力不支持时覆写。
    """

    capabilities: DownloaderCapabilities = field(
        default_factory=DownloaderCapabilities
    )

    # ------------------------------------------------------------------
    # 连接与状态
    # ------------------------------------------------------------------

    @abstractmethod
    def check_connection(self) -> bool:
        """检查后端是否可连接"""

    @abstractmethod
    def get_version(self) -> str:
        """返回后端版本号字符串"""

    # ------------------------------------------------------------------
    # 添加任务
    # ------------------------------------------------------------------

    @abstractmethod
    def add_torrent(
        self,
        urls: str,
        is_paused: bool = False,
        save_path: Optional[str] = None,
        content_layout: Optional[str] = None,
        torrent_file: Optional[bytes] = None,
    ) -> bool:
        """添加种子。

        - urls: 磁力链接（magnet:?xt=urn:btih:...）或 HTTP 种子地址
        - is_paused: 添加后是否暂停（等元数据 / 选文件）
        - save_path: 保存目录
        - content_layout: Original / NoSubfolder / Subfolder（不支持的后端可忽略）
        - torrent_file: .torrent 文件字节内容（与 urls 二选一）
        返回是否添加成功。
        """

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    @abstractmethod
    def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """按 info hash 获取种子信息，返回规范化 dict；不存在返回 None。

        规范化字段：hash / name / state(qB风格) / progress(0~1) / total_size /
        save_path / ratio / content_path
        """

    @abstractmethod
    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """按 info hash 获取种子文件列表，返回 [{name, path, size, index}]"""

    # ------------------------------------------------------------------
    # 任务控制
    # ------------------------------------------------------------------

    @abstractmethod
    def delete_torrents(self, hashes: str, delete_files: bool = True) -> bool:
        """删除种子，hashes 为单个 hash（为兼容保留复数参数名）"""

    @abstractmethod
    def set_file_priority(self, torrent_hash: str, file_ids: List[int], priority: int) -> bool:
        """设置文件优先级，0=不下载，1=普通"""

    @abstractmethod
    def resume_torrents(self, hashes: str) -> bool:
        """恢复（开始）种子"""

    @abstractmethod
    def pause_torrents(self, hashes: str) -> bool:
        """暂停种子"""

    @abstractmethod
    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """重命名种子内文件"""

    @abstractmethod
    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """重命名种子内文件夹"""

    @abstractmethod
    def set_location(self, hashes: str, location: str) -> bool:
        """移动种子文件到新位置"""

    # ------------------------------------------------------------------
    # 磁力解析（获取文件列表，不实际下载）
    # ------------------------------------------------------------------

    def parse_magnet(self, magnet_link: str, timeout: int = 60) -> List[TorrentFile]:
        """解析磁力链接获取文件列表。

        默认实现：暂停添加 → 轮询元数据 → 取文件列表 → 删除临时种子。
        Aria2 等「暂停不拉元数据」的后端应覆写（bt-metadata-only 方案）。
        """
        torrent_hash = _extract_info_hash(magnet_link)
        if not torrent_hash:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无效的磁力链接")

        try:
            self.add_torrent(urls=magnet_link, is_paused=True)
        except Exception as e:
            logger.error(f"解析磁力：添加临时种子失败 {e}")
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="添加种子失败")

        try:
            # 轮询等待元数据
            start = __import__("time").time()
            files: List[TorrentFile] = []
            while __import__("time").time() - start < timeout:
                info = self.get_torrent_info(torrent_hash)
                if info and (info.get("total_size") or 0) > 0:
                    files = self._normalize_files(self.get_torrent_files(torrent_hash))
                    return files
                __import__("time").sleep(2)
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="等待元数据超时")
        finally:
            try:
                self.delete_torrents(torrent_hash, delete_files=True)
            except Exception as e:
                logger.warning(f"解析磁力：删除临时种子失败 {torrent_hash}: {e}")

    def parse_torrent_file(self, torrent_bytes: bytes, timeout: int = 60) -> List[TorrentFile]:
        """解析 .torrent 文件获取文件列表。

        .torrent 内嵌元数据，直接在本地用 bencode 解析，不依赖下载器网络。
        返回的文件列表含 index / name / path / size。
        """
        files = _bencode_torrent_files(torrent_bytes)
        if not files:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="解析种子文件失败：无法读取文件列表")
        return files

    @staticmethod
    def torrent_info_hash(torrent_bytes: bytes) -> Optional[str]:
        """从 .torrent 文件计算 info hash（40 位小写 hex）"""
        return _bencode_torrent_info_hash(torrent_bytes)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_files(files: List[Dict[str, Any]]) -> List[TorrentFile]:
        """把后端文件列表规范化为 TorrentFile 列表"""
        out: List[TorrentFile] = []
        for i, f in enumerate(files):
            name = f.get("name", "")
            path = f.get("path", "") or name
            if not name and path:
                name = path.replace("\\", "/").split("/")[-1]
            out.append(TorrentFile(
                index=f.get("index", i),
                name=name,
                path=path,
                size=int(f.get("size", 0) or 0),
            ))
        return out

    def _find_just_added_torrent(self) -> Optional[Dict[str, Any]]:
        """子类可覆写：通过任务列表定位刚添加的种子（用于 .torrent 解析）"""
        return None

    @staticmethod
    def extract_info_hash(url: str) -> Optional[str]:
        return _extract_info_hash(url)
