"""
下载器管理器测试
覆盖：根据 config downloader.active 选择后端、reload 切换后端
"""
import pytest
from unittest.mock import MagicMock, patch

from app.core.downloader.manager import DownloaderManager, downloader_manager


@pytest.fixture
def fresh_manager():
    """返回一个全新 manager（避免单例状态污染）"""
    m = DownloaderManager.__new__(DownloaderManager)
    m._backend = None
    m._active = None
    return m


class TestManagerSelection:
    """根据 downloader.active 选择后端"""

    @patch("app.core.downloader.manager.config")
    def test_default_qbittorrent(self, mock_config, fresh_manager):
        mock_config.get.side_effect = lambda key, default=None: {
            "downloader": {},
            "qbittorrent": {"host": "http://qb:8080"},
        }.get(key, default)
        fresh_manager.reload()
        from app.core.downloader.qbittorrent import QBittorrentDownloader
        assert isinstance(fresh_manager.get_backend(), QBittorrentDownloader)
        assert fresh_manager.active == "qbittorrent"

    @patch("app.core.downloader.manager.config")
    def test_select_transmission(self, mock_config, fresh_manager):
        def get(key, default=None):
            if key == "downloader":
                return {"active": "transmission", "transmission": {"host": "http://t:9091"}}
            if key == "qbittorrent":
                return {}
            return default
        mock_config.get.side_effect = get
        fresh_manager.reload()
        from app.core.downloader.transmission import TransmissionDownloader
        assert isinstance(fresh_manager.get_backend(), TransmissionDownloader)

    @patch("app.core.downloader.manager.config")
    def test_select_aria2(self, mock_config, fresh_manager):
        def get(key, default=None):
            if key == "downloader":
                return {"active": "aria2", "aria2": {"host": "http://a:6800", "secret": "s"}}
            if key == "qbittorrent":
                return {}
            return default
        mock_config.get.side_effect = get
        fresh_manager.reload()
        from app.core.downloader.aria2 import Aria2Downloader
        assert isinstance(fresh_manager.get_backend(), Aria2Downloader)

    @patch("app.core.downloader.manager.config")
    def test_switch_backend_on_reload(self, mock_config, fresh_manager):
        """reload 后从 qB 切换到 Transmission"""
        state = {"active": "qbittorrent"}
        def get(key, default=None):
            if key == "downloader":
                return {"active": state["active"], "transmission": {}}
            if key == "qbittorrent":
                return {}
            return default
        mock_config.get.side_effect = get
        fresh_manager.reload()
        from app.core.downloader.qbittorrent import QBittorrentDownloader
        assert isinstance(fresh_manager.get_backend(), QBittorrentDownloader)

        state["active"] = "transmission"
        fresh_manager.reload()
        from app.core.downloader.transmission import TransmissionDownloader
        assert isinstance(fresh_manager.get_backend(), TransmissionDownloader)
        assert fresh_manager.active == "transmission"

    @patch("app.core.downloader.manager.config")
    def test_unknown_active_falls_back_qb(self, mock_config, fresh_manager):
        def get(key, default=None):
            if key == "downloader":
                return {"active": "unknown_backend"}
            if key == "qbittorrent":
                return {}
            return default
        mock_config.get.side_effect = get
        fresh_manager.reload()
        from app.core.downloader.qbittorrent import QBittorrentDownloader
        assert isinstance(fresh_manager.get_backend(), QBittorrentDownloader)
