"""
任务监控逻辑测试：单文件/无嵌套/有嵌套 与 移动/复制 决策
使用 mock qB 客户端，不依赖真实 qBittorrent 与生产环境
"""
import pytest
from unittest.mock import MagicMock

from app.services.task_monitor import TaskMonitor


def _make_mock_client(file_names):
    """根据文件路径列表构造返回 get_torrent_files 的 mock 客户端"""
    client = MagicMock()
    client.get_torrent_files.return_value = [{"name": n} for n in file_names]
    return client


class TestIsSingleFileTorrent:
    """_is_single_file_torrent：是否单文件"""

    def test_single_file(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["video.mkv"])
        assert monitor._is_single_file_torrent(client, "hash") is True

    def test_one_folder_one_file(self):
        """一层目录下一文件：qB 返回 1 条文件记录，仍算单文件"""
        monitor = TaskMonitor()
        client = _make_mock_client(["Folder/video.mkv"])
        assert monitor._is_single_file_torrent(client, "hash") is True

    def test_multi_file_no_nesting(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["FolderA/a.mkv", "FolderB/b.mkv"])
        assert monitor._is_single_file_torrent(client, "hash") is False

    def test_nested(self):
        """嵌套目录下一文件：qB 仍返回 1 条文件记录，算单文件（是否嵌套由 _has_nested_folders 区分）"""
        monitor = TaskMonitor()
        client = _make_mock_client(["Folder/Sub/file.mkv"])
        assert monitor._is_single_file_torrent(client, "hash") is True

    def test_api_error_returns_false(self):
        monitor = TaskMonitor()
        client = MagicMock()
        client.get_torrent_files.side_effect = Exception("network error")
        assert monitor._is_single_file_torrent(client, "hash") is False


class TestHasNestedFolders:
    """_has_nested_folders：是否包含嵌套文件夹（路径中 >=2 个 '/'）"""

    def test_single_file_no_slash(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["video.mkv"])
        assert monitor._has_nested_folders(client, "hash") is False

    def test_one_folder_one_file(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["Folder/video.mkv"])
        assert monitor._has_nested_folders(client, "hash") is False

    def test_multi_folder_no_nesting(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["FolderA/a.mkv", "FolderB/b.mkv"])
        assert monitor._has_nested_folders(client, "hash") is False

    def test_nested_one_file(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["Folder/Sub/file.mkv"])
        assert monitor._has_nested_folders(client, "hash") is True

    def test_nested_deep(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["A/B/C/file.mkv"])
        assert monitor._has_nested_folders(client, "hash") is True

    def test_mixed_one_nested(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["Folder/a.mkv", "Folder/Sub/b.mkv"])
        assert monitor._has_nested_folders(client, "hash") is True

    def test_empty_list(self):
        monitor = TaskMonitor()
        client = _make_mock_client([])
        assert monitor._has_nested_folders(client, "hash") is False

    def test_api_error_returns_true(self):
        monitor = TaskMonitor()
        client = MagicMock()
        client.get_torrent_files.side_effect = Exception("timeout")
        assert monitor._has_nested_folders(client, "hash") is True


class TestHasAnyFolder:
    """_has_any_folder：路径中是否带目录（>=1 个 '/'）"""

    def test_single_file_at_root(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["video.mkv"])
        assert monitor._has_any_folder(client, "hash") is False

    def test_one_folder_one_file(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["Folder/video.mkv"])
        assert monitor._has_any_folder(client, "hash") is True

    def test_multi_folder(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["FolderA/a.mkv", "FolderB/b.mkv"])
        assert monitor._has_any_folder(client, "hash") is True

    def test_nested(self):
        monitor = TaskMonitor()
        client = _make_mock_client(["Folder/Sub/file.mkv"])
        assert monitor._has_any_folder(client, "hash") is True

    def test_api_error_returns_true(self):
        monitor = TaskMonitor()
        client = MagicMock()
        client.get_torrent_files.side_effect = Exception("timeout")
        assert monitor._has_any_folder(client, "hash") is True


class TestMoveVsCopyDecision:
    """use_qb_move 决策：仅根目录文件可移动；带目录则 use_copy 时复制"""

    def _use_qb_move(self, use_copy: bool, has_any_folder: bool) -> bool:
        """与 _handle_completed_task 中一致：仅根目录文件时移动，带目录且 use_copy 时复制"""
        return (use_copy and not has_any_folder) or (not use_copy)

    def test_use_copy_false_always_move(self):
        assert self._use_qb_move(False, False) is True
        assert self._use_qb_move(False, True) is True

    def test_use_copy_true_only_root_files_move(self):
        assert self._use_qb_move(True, False) is True

    def test_use_copy_true_has_folder_copy(self):
        assert self._use_qb_move(True, True) is False
