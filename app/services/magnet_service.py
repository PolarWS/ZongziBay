import base64
import logging
import re
import time
import urllib.parse
import uuid
from typing import List

from app.core import db
from app.core.config import config
from app.core.downloader.manager import downloader_manager
from app.core.downloader.base import BaseDownloader
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.magnet import MagnetFile
from app.schemas.notification import NotificationType
from app.services.download_path import ensure_download_dir

logger = logging.getLogger(__name__)


def normalize_info_hash(raw_hash: str) -> str:
    """将 info_hash 统一为 40 位小写 hex（兼容 Base32）"""
    h = raw_hash.strip()
    if len(h) == 40:
        return h.lower()
    if len(h) == 32:
        try:
            return base64.b32decode(h.upper()).hex()
        except Exception:
            pass
    return h.lower()


class MagnetService:
    """磁链解析与下载服务（后端由 downloader_manager 决定）"""

    def __init__(self):
        self.client = None
        self.reload_config()

    def reload_config(self) -> None:
        """从当前运行时配置刷新下载器后端与 trackers（设置页保存后可立即生效）。"""
        self.trackers = config.get("trackers", []) or []
        # 连接参数变更后重建后端实例，避免沿用旧 host 的 session
        downloader_manager.reload()
        self.client = None

    def _append_trackers(self, magnet_link: str) -> str:
        """在磁力链接后追加配置的 tracker 列表"""
        if not magnet_link or not self.trackers:
            return magnet_link or ""
        result = magnet_link.rstrip("&")
        for tr in self.trackers:
            if tr:
                result += f"&tr={urllib.parse.quote(tr, safe='')}"
        return result

    def _get_client(self) -> BaseDownloader:
        return downloader_manager.get_backend()

    def check_connection(self) -> bool:
        try:
            client = self._get_client()
            version = client.get_version()
            logger.info(f"连接下载器 {client.capabilities.name} 成功, 版本: {version}")
            return True
        except Exception as e:
            logger.error(f"连接下载器失败: {e}")
            return False

    def parse_magnet(self, magnet_link: str, timeout: int = 60):
        """解析磁链获取文件列表（不实际下载数据）

        委托给当前下载器后端的统一接口 parse_magnet：
        - qB / Transmission：暂停添加拉元数据
        - Aria2：bt-metadata-only 只拉元数据
        """
        client = self._get_client()

        # 若种子已存在，直接读取文件列表
        torrent_hash = normalize_info_hash(self._extract_hash(magnet_link) or "")
        if torrent_hash:
            try:
                existing = client.get_torrent_info(torrent_hash)
                if existing:
                    return [MagnetFile(name=f.get("name", ""), path=f.get("path", ""), size=f.get("size", 0))
                            for f in client.get_torrent_files(torrent_hash)]
            except Exception as e:
                logger.warning(f"检查种子存在性出错: {e}")

        # 追加 trackers 后委托后端解析
        magnet_with_trackers = self._append_trackers(magnet_link)
        files = client.parse_magnet(magnet_with_trackers, timeout=timeout)
        return [MagnetFile(name=f.name, path=f.path, size=f.size) for f in files]

    @staticmethod
    def _extract_hash(magnet_link: str) -> str:
        match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link or "")
        return match.group(1) if match else ""

    def add_magnet_download(self, magnet_link: str, save_path: str = None) -> dict:
        """添加磁链下载任务到 qBittorrent"""
        client = self._get_client()
        match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link)
        if not match:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无效的磁力链接")
        torrent_hash = normalize_info_hash(match.group(1))

        try:
            existing_torrent = client.get_torrent_info(torrent_hash)
            if existing_torrent:
                # 状态必须是 DownloadTaskStatus 里的合法值："already_exists" 不在枚举中，
                # 会让 /tasks/list 构造响应模型时 ValidationError → 该接口整体 500。
                # 下载器里已有该种子，与 task_service 的既有约定一致，按 downloading 录入，
                # 由 task_monitor 按下载器真实状态纠正。
                db.insert_download_task(
                    taskName=torrent_hash, taskInfo="", sourceUrl=magnet_link,
                    sourcePath=None,
                    targetPath=existing_torrent.get("save_path") if isinstance(existing_torrent, dict) else None,
                    taskStatus="downloading",
                )
                return {"hash": torrent_hash, "status": "already_exists"}
        except Exception as e:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"检查已有种子失败: {e}")

        temp_dir = config.get("paths.temp_download_path") or config.get("magnet.temp_dir")
        if save_path:
            target_path = save_path
        elif temp_dir:
            sep = '\\' if ('\\' in temp_dir and '/' not in temp_dir) else '/'
            target_path = temp_dir.rstrip('/\\') + sep + uuid.uuid4().hex[:8]
        else:
            target_path = None

        try:
            db.insert_download_task(
                taskName=torrent_hash, taskInfo="", sourceUrl=magnet_link,
                sourcePath=None, targetPath=target_path, taskStatus="downloading",
            )
        except Exception as e:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"写入数据库失败: {e}")

        magnet_with_trackers = self._append_trackers(magnet_link)
        # target_path 带了随机子目录，通常并不存在；下载器多半能自己建，但如果
        # 上级目录是本程序以 root 建的，下载器就会 Permission denied（任务直接 error）。
        # 这里先建好并放权，失败不影响下载，只是退回「交给下载器自己建」。
        ensure_download_dir(target_path)
        try:
            # 解析时不关心目录结构，这里保持默认布局
            success = client.add_torrent(urls=magnet_with_trackers, is_paused=False, save_path=target_path)
            if not success:
                raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="添加下载任务失败")
            db.insert_notification(title="开始下载", content=f"开始下载任务: {torrent_hash}", type=NotificationType.INFO.value)
        except Exception as e:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"添加下载任务失败: {e}")
        return {"hash": torrent_hash, "status": "下载中", "save_path": target_path}

    def get_files_from_torrent(self, client, torrent_hash: str) -> List[MagnetFile]:
        try:
            files_data = client.get_torrent_files(torrent_hash)
            result = []
            for f in files_data:
                full_path = f.get('name', '')
                file_name = full_path.replace('\\', '/').split('/')[-1]
                result.append(MagnetFile(name=file_name, path=full_path, size=f.get('size', 0)))
            return result
        except Exception as e:
            logger.error(f"获取种子文件列表失败: {e}")
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"获取文件列表失败: {e}")


magnet_service = MagnetService()
