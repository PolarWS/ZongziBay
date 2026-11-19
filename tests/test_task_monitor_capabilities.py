"""
TaskMonitor 能力感知降级测试
覆盖：后端不支持重命名/移动（如 Aria2）时，_handle_completed_task 跳过种子内重命名并走复制归档
"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.downloader.aria2 import Aria2Downloader
from app.core.downloader.base import DownloaderCapabilities
from app.services.task_monitor import TaskMonitor


class TestTaskMonitorCapabilities:
    """_supports：能力感知辅助方法"""

    def test_missing_capabilities_default_true(self):
        """无 capabilities 属性（旧客户端/mock）→ 默认支持"""
        client = MagicMock()
        assert TaskMonitor._supports(client, "supports_rename") is True

    def test_supported_capability(self):
        client = MagicMock()
        client.capabilities = DownloaderCapabilities(name="qbittorrent", supports_rename=True)
        assert TaskMonitor._supports(client, "supports_rename") is True

    def test_unsupported_capability(self):
        client = MagicMock()
        client.capabilities = Aria2Downloader().capabilities  # rename=False, set_location=False
        assert TaskMonitor._supports(client, "supports_rename") is False
        assert TaskMonitor._supports(client, "supports_set_location") is False


class TestHandleCompletedDegrade:
    """Aria2 后端：不支持重命名/移动 → 跳过重命名、强制复制"""

    def _make_aria2_client(self):
        client = MagicMock()
        client.capabilities = Aria2Downloader().capabilities
        client.get_torrent_info.return_value = {
            "hash": "a" * 40, "state": "uploading", "progress": 1.0,
            "save_path": "/dl", "ratio": 1.0, "content_path": "/dl/name",
        }
        client.get_torrent_files.return_value = [{"name": "a.mkv", "path": "a.mkv", "size": 100}]
        client.rename_file.return_value = False
        client.rename_folder.return_value = False
        client.set_location.return_value = False
        return client

    @patch("app.services.task_monitor.config")
    @patch("app.services.task_monitor.db")
    def test_skips_rename_and_forces_copy(self, mock_db, mock_config):
        """Aria2 不支持重命名/移动：不调用 rename_file，走 _process_copy"""
        client = self._make_aria2_client()
        # _has_any_folder 内部调用 get_torrent_files
        file_tasks = [
            {"id": 1, "sourcePath": "a.mkv", "targetPath": "", "file_rename": "Movie.mkv", "file_status": "pending"},
        ]
        mock_db.get_file_tasks.return_value = file_tasks

        def cfg_get(key, default=None):
            if key == "qbittorrent.file_handling.use_copy":
                return True
            if key == "qbittorrent.seeding.limit_ratio":
                return -1.0
            if key == "paths.default_target_path":
                return "/nas"
            return default
        mock_config.get.side_effect = cfg_get

        monitor = TaskMonitor()
        # 隔离实际文件系统操作：_process_copy 内会访问路径，这里仅验证走复制分支
        with patch.object(monitor, "_process_copy", return_value="completed") as mock_copy:
            result = monitor._handle_completed_task(
                client, {"id": 1, "targetPath": "/nas/Movie"}, "a" * 40, client.get_torrent_info("a" * 40),
            )
        # 复制被调用
        mock_copy.assert_called_once()
        # 重命名不应被调用
        client.rename_file.assert_not_called()
        client.rename_folder.assert_not_called()
        # set_location 不应被调用
        client.set_location.assert_not_called()
        assert result == "completed"

    @patch("app.services.task_monitor.config")
    @patch("app.services.task_monitor.db")
    def test_qb_backend_still_uses_move(self, mock_db, mock_config):
        """qB 后端：支持移动 → 走移动分支（不降级）"""
        from app.core.downloader.qbittorrent import QBittorrentDownloader
        client = MagicMock()
        client.capabilities = QBittorrentDownloader().capabilities
        client.get_torrent_info.return_value = {
            "hash": "b" * 40, "state": "uploading", "progress": 1.0,
            "save_path": "/dl", "ratio": 1.0, "content_path": "/dl/name",
        }
        client.get_torrent_files.return_value = [{"name": "a.mkv", "path": "a.mkv", "size": 100}]
        mock_db.get_file_tasks.return_value = []

        def cfg_get(key, default=None):
            if key == "qbittorrent.file_handling.use_copy":
                return False
            if key == "qbittorrent.seeding.limit_ratio":
                return -1.0
            return default
        mock_config.get.side_effect = cfg_get

        monitor = TaskMonitor()
        with patch.object(monitor, "_maybe_move_location", return_value=(True, "/nas", "/nas/Movie")) as mock_move, \
             patch.object(monitor, "_verify_move", return_value=True):
            result = monitor._handle_completed_task(
                client, {"id": 2, "targetPath": "/nas/Movie"}, "b" * 40, client.get_torrent_info("b" * 40),
            )
        mock_move.assert_called_once()
        assert result == "completed"
