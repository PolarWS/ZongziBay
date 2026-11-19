"""下载器管理器

根据 config.yml 的 downloader.active 选择当前后端（qbittorrent / transmission / aria2），
并向上层服务（task_service / task_monitor / magnet_service）提供统一的后端实例。

配置结构（config.yml）：
    downloader:
      active: qbittorrent        # qbittorrent | transmission | aria2
      transmission:
        host: "http://localhost:9091"
        username: ""
        password: ""
      aria2:
        host: "http://localhost:6800"
        secret: ""

qBittorrent 的连接信息仍使用原有 qbittorrent 配置节。
"""

import logging

from app.core.config import config
from app.core.downloader.base import BaseDownloader
from app.core.downloader.qbittorrent import QBittorrentDownloader
from app.core.downloader.transmission import TransmissionDownloader
from app.core.downloader.aria2 import Aria2Downloader

logger = logging.getLogger(__name__)


class DownloaderManager:
    """下载器管理器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DownloaderManager, cls).__new__(cls)
            cls._instance._backend = None
            cls._instance._active = None
        return cls._instance

    def reload(self) -> None:
        """从配置重建后端实例（设置页保存配置后调用）"""
        dl_config = config.get("downloader", {}) or {}
        active = (dl_config.get("active") or "qbittorrent").lower()

        try:
            if active == "transmission":
                t = dl_config.get("transmission", {}) or {}
                self._backend = TransmissionDownloader(
                    host=t.get("host", "http://localhost:9091"),
                    username=t.get("username", ""),
                    password=t.get("password", ""),
                )
            elif active == "aria2":
                a = dl_config.get("aria2", {}) or {}
                self._backend = Aria2Downloader(
                    host=a.get("host", "http://localhost:6800"),
                    secret=a.get("secret", ""),
                )
            else:
                qb = config.get("qbittorrent", {}) or {}
                self._backend = QBittorrentDownloader(
                    host=qb.get("host", "http://localhost:8080"),
                    username=qb.get("username", "admin"),
                    password=qb.get("password", "adminadmin"),
                    api_key=qb.get("api_key", "") or "",
                )
            self._active = active
            logger.info(f"下载器后端已切换为: {active} ({self._backend.capabilities.name})")
        except Exception as e:
            logger.error(f"创建下载器后端失败: {e}")
            # 回退到 qBittorrent
            qb = config.get("qbittorrent", {}) or {}
            self._backend = QBittorrentDownloader(
                host=qb.get("host", "http://localhost:8080"),
                username=qb.get("username", "admin"),
                password=qb.get("password", "adminadmin"),
                api_key=qb.get("api_key", "") or "",
            )
            self._active = "qbittorrent"

    def get_backend(self) -> BaseDownloader:
        """获取当前后端实例（惰性初始化）"""
        if self._backend is None:
            self.reload()
        return self._backend

    @property
    def active(self) -> str:
        return self._active or "qbittorrent"

    @property
    def capabilities(self):
        return self.get_backend().capabilities


downloader_manager = DownloaderManager()
