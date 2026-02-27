import base64
import logging
import re
import time
import urllib.parse
import uuid
from typing import List

from app.core import db
from app.core.config import config
from app.core.qb_client import QBittorrentClient
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.magnet import MagnetFile
from app.schemas.notification import NotificationType

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
    """磁链解析与 qBittorrent 下载服务"""

    def __init__(self):
        qb_config = config.get("qbittorrent", {})
        self.host = qb_config.get("host", "http://localhost:8080")
        self.username = qb_config.get("username", "admin")
        self.password = qb_config.get("password", "adminadmin")
        self.client = None
        self.trackers: List[str] = config.get("trackers", [])

    def _append_trackers(self, magnet_link: str) -> str:
        """在磁力链接后追加配置的 tracker 列表"""
        if not magnet_link or not self.trackers:
            return magnet_link or ""
        result = magnet_link.rstrip("&")
        for tr in self.trackers:
            if tr:
                result += f"&tr={urllib.parse.quote(tr, safe='')}"
        return result

    def _get_client(self):
        if not self.client:
            self.client = QBittorrentClient(self.host, self.username, self.password)
        return self.client

    def check_connection(self) -> bool:
        try:
            client = self._get_client()
            version = client.get_version()
            logger.info(f"连接 qBittorrent 成功, 版本: {version}")
            return True
        except Exception as e:
            logger.error(f"连接 qBittorrent 失败: {e}")
            return False

    def parse_magnet(self, magnet_link: str, timeout: int = 60):
        """解析磁链获取文件列表（暂停状态添加，只取元数据不下载）"""
        client = self._get_client()

        match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link)
        if not match:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无效的磁力链接")
        torrent_hash = normalize_info_hash(match.group(1))

        # 若种子已存在，直接读取文件列表
        try:
            existing = client.get_torrent_info(torrent_hash)
            if existing:
                return self.get_files_from_torrent(client, torrent_hash)
        except Exception as e:
            logger.warning(f"检查种子存在性出错: {e}")

        # 追加 trackers，暂停状态添加（只获取元数据）
        magnet_with_trackers = self._append_trackers(magnet_link)
        try:
            success = client.add_torrent(urls=magnet_with_trackers, is_paused=True)
            if not success:
                raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="添加种子失败")
        except Exception as e:
            logger.error(f"添加种子失败: {e}")
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"添加种子失败: {e}")

        # 轮询等待元数据
        start_time = time.time()
        fetched = False
        result = []
        try:
            while time.time() - start_time < timeout:
                try:
                    info = client.get_torrent_info(torrent_hash)
                    if info and info.get('total_size', 0) > 0:
                        result = self.get_files_from_torrent(client, torrent_hash)
                        fetched = True
                        break
                except Exception as e:
                    logger.warning(f"轮询元数据出错: {e}")
                time.sleep(2)
        finally:
            try:
                client.delete_torrents(hashes=torrent_hash, delete_files=True)
            except Exception as e:
                logger.error(f"删除临时种子失败 {torrent_hash}: {e}")

        if fetched:
            return result
        raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="等待元数据超时")

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
                db.insert_download_task(
                    taskName=torrent_hash, taskInfo="", sourceUrl=magnet_link,
                    sourcePath=None,
                    targetPath=existing_torrent.get("save_path") if isinstance(existing_torrent, dict) else None,
                    taskStatus="already_exists",
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
                sourcePath=None, targetPath=target_path, taskStatus="下载中",
            )
        except Exception as e:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"写入数据库失败: {e}")

        magnet_with_trackers = self._append_trackers(magnet_link)
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
