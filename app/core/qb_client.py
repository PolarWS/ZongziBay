"""qBittorrent 客户端兼容层（已迁移至 app.core.downloader）

原 QBittorrentClient 已重构为 app.core.downloader.qbittorrent.QBittorrentDownloader，
继承统一下载器抽象层 BaseDownloader。此文件保留原名作为向后兼容别名，
避免外部导入 `from app.core.qb_client import QBittorrentClient` 出错。

建议新代码直接使用 app.core.downloader.downloader_manager 获取统一后端。
"""

from app.core.downloader.qbittorrent import QBittorrentDownloader as QBittorrentClient

__all__ = ["QBittorrentClient"]
