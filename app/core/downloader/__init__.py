"""下载器抽象层

统一 qBittorrent / Transmission / Aria2 三种下载后端的接口。
- BaseDownloader 定义统一能力接口，各后端实现内部转换
- 规范化返回 dict（qB 兼容字段），上层服务无需感知后端差异
- capabilities 标记各后端能力，供上层做降级（Aria2 不支持重命名/移动 → 复制归档）
"""

from app.core.downloader.base import BaseDownloader, DownloaderCapabilities, TorrentFile
from app.core.downloader.manager import DownloaderManager, downloader_manager

__all__ = [
    "BaseDownloader",
    "DownloaderCapabilities",
    "TorrentFile",
    "DownloaderManager",
    "downloader_manager",
]
