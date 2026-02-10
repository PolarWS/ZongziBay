import time
import re
import logging
import uuid
from typing import List

from app.core.config import Config
from app.core.qb_client import QBittorrentClient
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.magnet import MagnetFile
from app.schemas.notification import NotificationType
from app.core import db

logger = logging.getLogger(__name__)

class MagnetService:
    def __init__(self):
        self.config = Config()
        self.qb_config = self.config.get("qbittorrent", {})
        self.host = self.qb_config.get("host", "http://localhost:8080")
        self.username = self.qb_config.get("username", "admin")
        self.password = self.qb_config.get("password", "adminadmin")
        self.client = None

    def _get_client(self):
        if not self.client:
            self.client = QBittorrentClient(self.host, self.username, self.password)
        return self.client

    def check_connection(self) -> bool:
        """检查 qBittorrent 连接状态"""
        try:
            client = self._get_client()
            version = client.get_version()
            logger.info(f"成功连接到 qBittorrent, 版本: {version}")
            return True
        except Exception as e:
            logger.error(f"连接 qBittorrent 失败: {e}")
            return False

    def parse_magnet(self, magnet_link: str, timeout: int = 60):
        client = self._get_client()

        # 提取哈希
        match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link)
        if not match:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无效的磁力链接")
        
        torrent_hash = match.group(1).lower()
        
        # 检查种子是否已存在
        try:
            existing_torrent = client.get_torrent_info(torrent_hash)
            if existing_torrent:
                logger.info(f"种子 {torrent_hash} 已存在，直接使用现有信息。")
                return self.get_files_from_torrent(client, torrent_hash)
        except Exception as e:
            logger.warning(f"检查种子存在性时出错: {e}")

        # 添加新种子
        try:
            # 正常添加 (不暂停) 以获取元数据
            success = client.add_torrent(urls=magnet_link, is_paused=False)
            if not success:
                 raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="添加种子失败")
        except Exception as e:
            logger.error(f"添加种子失败: {e}")
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"添加种子失败: {e}")

        # 等待元数据获取
        start_time = time.time()
        fetched = False
        result = []
        
        try:
            while time.time() - start_time < timeout:
                try:
                    info = client.get_torrent_info(torrent_hash)
                    # total_size > 0 通常表示元数据已获取
                    if info and info.get('total_size', 0) > 0:
                        result = self.get_files_from_torrent(client, torrent_hash)
                        fetched = True
                        break
                except Exception as e:
                    logger.warning(f"检查种子信息出错: {e}")
                
                time.sleep(2)
        finally:
            # 清理：删除种子（因为我们只是为了解析）
            try:
                client.delete_torrents(hashes=torrent_hash, delete_files=True)
            except Exception as e:
                logger.error(f"删除种子 {torrent_hash} 出错: {e}")

        if fetched:
            return result
        else:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="等待元数据超时")

    def get_files_from_torrent(self, client, torrent_hash: str) -> List[MagnetFile]:
        """
        从种子中获取文件列表
        """
        try:
            files_data = client.get_torrent_files(torrent_hash)
            result = []
            for f in files_data:
                full_path = f.get('name', '')
                # 简单处理文件名
                file_name = full_path.replace('\\', '/').split('/')[-1]
                
                result.append(MagnetFile(
                    name=file_name,
                    path=full_path,
                    size=f.get('size', 0)
                ))
            return result
        except Exception as e:
            logger.error(f"获取种子文件列表失败: {e}")
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"获取文件列表失败: {e}")

    def add_magnet_download(self, magnet_link: str, save_path: str = None) -> dict:
        client = self._get_client()
        match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link)
        if not match:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无效的磁力链接")
        torrent_hash = match.group(1).lower()
    
        # 1. 检查已有种子
        try:
            existing_torrent = client.get_torrent_info(torrent_hash)
            if existing_torrent:
                db.insert_download_task(
                    taskName=torrent_hash,
                    taskInfo="",
                    sourceUrl=magnet_link,
                    sourcePath=None,
                    targetPath=existing_torrent.get("save_path") if isinstance(existing_torrent, dict) else None,
                    taskStatus="already_exists",
                )
                return {"hash": torrent_hash, "status": "already_exists"}
        except Exception as e:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR,
                                    message=f"检查已有种子失败: {e}")
    
        # 2. 生成下载路径
        temp_dir = self.config.get("magnet.temp_dir")
        if save_path:
            target_path = save_path
        elif temp_dir:
            sep = '\\' if ('\\' in temp_dir and '/' not in temp_dir) else '/'
            target_path = temp_dir.rstrip('/\\') + sep + uuid.uuid4().hex[:8]
        else:
            target_path = None
    
        # 3. 先写入数据库，写入失败就抛异常
        try:
            db.insert_download_task(
                taskName=torrent_hash,
                taskInfo="",
                sourceUrl=magnet_link,
                sourcePath=None,
                targetPath=target_path,
                taskStatus="下载中",
            )
        except Exception as e:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR,
                                    message=f"写入数据库失败，中断下载: {e}")
    
        # 4. 添加下载任务
        try:
            success = client.add_torrent(urls=magnet_link, is_paused=False, save_path=target_path)
            if not success:
                raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="添加下载任务失败")
            db.insert_notification(title="开始下载", content=f"开始下载任务: {torrent_hash}", type=NotificationType.INFO.value)
        except Exception as e:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR,
                                    message=f"添加下载任务失败: {e}")
    
        return {"hash": torrent_hash, "status": "下载中", "save_path": target_path}

magnet_service = MagnetService()
