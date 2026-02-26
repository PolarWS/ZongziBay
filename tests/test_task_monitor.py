"""
任务监控逻辑测试：单文件/无嵌套/有嵌套 与 移动/复制 决策
使用 mock qB 客户端，不依赖真实 qBittorrent 与生产环境

移动/复制测试：用临时目录生成假文件，验证 _handle_subtitle_task 与 _process_copy 的复制与清理行为（不依赖 qB 下载）
"""
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# 移动/复制集成测试：用临时目录生成文件，不依赖 qB 下载
# ---------------------------------------------------------------------------

class TestSubtitleTaskMoveCopy:
    """字幕任务 _handle_subtitle_task：复制到目标并重命名，复制后删除源文件"""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """创建源目录、目标目录及默认目标根"""
        src = tmp_path / "source"
        dest_root = tmp_path / "target_root"
        default_target = tmp_path / "default_target"
        src.mkdir()
        dest_root.mkdir()
        default_target.mkdir()
        return {"source": src, "target_root": dest_root, "default_target": default_target}

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.config")
    def test_subtitle_copy_and_rename_then_remove_source(self, mock_config, mock_db, temp_dirs):
        """生成一个字幕文件，执行字幕任务：应复制到目标并重命名，并删除源文件"""
        src_dir = temp_dirs["source"]
        default_target = temp_dirs["default_target"]
        # 在源目录下放一个字幕文件
        sub_file = src_dir / "original.srt"
        sub_file.write_text("1\n00:00:00 --> 00:01:00\n测试字幕", encoding="utf-8")

        task = {
            "id": 1,
            "taskName": "字幕任务测试",
            "sourcePath": str(src_dir),
            "targetPath": "movies/MyMovie",  # 相对路径，会拼到 default_target
            "taskStatus": "moving",
        }
        file_tasks = [
            {
                "id": 101,
                "sourcePath": "original.srt",
                "targetPath": "",  # 放到任务目标根
                "file_rename": "MyMovie.zh.srt",
                "file_status": "pending",
            }
        ]
        mock_db.get_file_tasks.return_value = file_tasks
        mock_config.get.side_effect = lambda k, d=None: (
            str(default_target) if k == "paths.default_target_path" else ({} if k == "paths" else d)
        )

        monitor = TaskMonitor()
        monitor._handle_subtitle_task(task)

        # 目标：default_target/movies/MyMovie/MyMovie.zh.srt
        dest_file = default_target / "movies" / "MyMovie" / "MyMovie.zh.srt"
        assert dest_file.exists(), f"目标文件应存在: {dest_file}"
        assert dest_file.read_text(encoding="utf-8") == "1\n00:00:00 --> 00:01:00\n测试字幕"
        # 源文件应被删除（字幕任务复制后删源）
        assert not sub_file.exists(), "源字幕文件应已被清理"
        mock_db.update_file_task_status.assert_any_call(101, "completed")
        mock_db.update_task_status.assert_called_with(1, "completed")

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.config")
    def test_subtitle_multiple_files_with_subdir_target(self, mock_config, mock_db, temp_dirs):
        """多个字幕文件，部分带 targetPath 子目录，验证复制与重命名"""
        src_dir = temp_dirs["source"]
        default_target = temp_dirs["default_target"]
        (src_dir / "a.srt").write_text("a", encoding="utf-8")
        (src_dir / "b.ass").write_text("b", encoding="utf-8")

        task = {
            "id": 2,
            "taskName": "多字幕测试",
            "sourcePath": str(src_dir),
            "targetPath": "tv/Show",
            "taskStatus": "moving",
        }
        file_tasks = [
            {"id": 201, "sourcePath": "a.srt", "targetPath": "S01", "file_rename": "Show.S01.zh.srt", "file_status": "pending"},
            {"id": 202, "sourcePath": "b.ass", "targetPath": "", "file_rename": "Show.zh.ass", "file_status": "pending"},
        ]
        mock_db.get_file_tasks.return_value = file_tasks
        mock_config.get.side_effect = lambda k, d=None: (
            str(default_target) if k == "paths.default_target_path" else ({} if k == "paths" else d)
        )

        monitor = TaskMonitor()
        monitor._handle_subtitle_task(task)

        assert (default_target / "tv" / "Show" / "S01" / "Show.S01.zh.srt").exists()
        assert (default_target / "tv" / "Show" / "Show.zh.ass").exists()
        assert not (src_dir / "a.srt").exists()
        assert not (src_dir / "b.ass").exists()
        assert mock_db.update_task_status.called

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.config")
    def test_subtitle_target_exists_skips_copy_removes_source(self, mock_config, mock_db, temp_dirs):
        """目标文件已存在时跳过复制，但仍删除源文件"""
        src_dir = temp_dirs["source"]
        default_target = temp_dirs["default_target"]
        (src_dir / "only.srt").write_text("only", encoding="utf-8")
        dest_dir = default_target / "movie"
        dest_dir.mkdir(parents=True)
        (dest_dir / "Movie.zh.srt").write_text("existing", encoding="utf-8")

        task = {"id": 3, "taskName": "已存在", "sourcePath": str(src_dir), "targetPath": "movie", "taskStatus": "moving"}
        file_tasks = [{"id": 301, "sourcePath": "only.srt", "targetPath": "", "file_rename": "Movie.zh.srt", "file_status": "pending"}]
        mock_db.get_file_tasks.return_value = file_tasks
        mock_config.get.side_effect = lambda k, d=None: (
            str(default_target) if k == "paths.default_target_path" else ({} if k == "paths" else d)
        )

        monitor = TaskMonitor()
        monitor._handle_subtitle_task(task)

        # 目标内容应仍是 existing，未被覆盖
        assert (default_target / "movie" / "Movie.zh.srt").read_text(encoding="utf-8") == "existing"
        # 源应被删除
        assert not (src_dir / "only.srt").exists()
        mock_db.update_file_task_status.assert_any_call(301, "completed")


class TestProcessCopyWithFakeFiles:
    """_process_copy：用临时目录模拟 content_path，测试复制到目标（不依赖 qB 下载）"""

    @pytest.fixture
    def fake_download_layout(self, tmp_path):
        """模拟 qB 下载完成后的目录：content_path 下已有文件（可带重命名后名称）"""
        root = tmp_path / "qb_download"
        root.mkdir()
        (root / "Movie.2024.1080p.mkv").write_bytes(b"fake video content")
        (root / "Movie.zh.srt").write_text("subtitle", encoding="utf-8")
        return root

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.config")
    def test_process_copy_with_file_tasks(self, mock_config, mock_db, tmp_path, fake_download_layout):
        """有 file_tasks 时：从 content_path 按 file_rename 复制到目标目录"""
        content_path = str(fake_download_layout)
        target_base = tmp_path / "archive"
        target_base.mkdir()

        def config_get(key, default=None):
            if key == "paths.default_target_path":
                return str(tmp_path)
            if key == "paths":
                return {}
            if key == "paths.target_root_path":
                return ""
            if key == "paths.download_root_path":
                return ""
            if key == "paths.root_path":
                return ""
            if key == "qbittorrent.file_handling.copy_delete_on_complete":
                return False
            return default

        mock_config.get.side_effect = config_get

        task = {
            "id": 10,
            "taskName": "copy_test",
            "targetPath": "archive",
        }
        file_tasks = [
            {"id": 1, "sourcePath": "Movie.2024.1080p.mkv", "targetPath": "", "file_rename": "Movie.2024.1080p.mkv", "file_status": "completed"},
            {"id": 2, "sourcePath": "Movie.zh.srt", "targetPath": "", "file_rename": "Movie.zh.srt", "file_status": "completed"},
        ]
        torrent_info = {
            "content_path": content_path,
            "save_path": os.path.dirname(content_path),
            "name": os.path.basename(content_path),
        }
        client = MagicMock()

        monitor = TaskMonitor()
        # _resolve_path_for_local 在无 target_root_path 时可能原样返回路径，这里 content_path 已是绝对路径
        result = monitor._process_copy(client, task, "hash", torrent_info, "archive", file_tasks)

        dest_dir = tmp_path / "archive"
        assert (dest_dir / "Movie.2024.1080p.mkv").exists()
        assert (dest_dir / "Movie.zh.srt").exists()
        assert (dest_dir / "Movie.2024.1080p.mkv").read_bytes() == b"fake video content"
        assert (dest_dir / "Movie.zh.srt").read_text(encoding="utf-8") == "subtitle"

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.config")
    def test_process_copy_whole_folder_no_file_tasks(self, mock_config, mock_db, tmp_path, fake_download_layout):
        """无 file_tasks：复制整个 content_path 到目标（保留根目录名）"""
        content_path = str(fake_download_layout)
        target_base = tmp_path / "archive"
        target_base.mkdir()

        def config_get(key, default=None):
            if key == "paths.default_target_path":
                return str(tmp_path)
            if key == "paths" or key == "paths.target_root_path":
                return {} if key == "paths" else ""
            if key == "paths.download_root_path":
                return ""
            if key == "qbittorrent.file_handling.copy_delete_on_complete":
                return False
            return default

        mock_config.get.side_effect = config_get

        task = {"id": 11, "taskName": "copy_whole", "targetPath": "archive"}
        torrent_info = {
            "content_path": content_path,
            "save_path": os.path.dirname(content_path),
            "name": os.path.basename(content_path),
        }
        client = MagicMock()

        monitor = TaskMonitor()
        result = monitor._process_copy(client, task, "hash", torrent_info, "archive", file_tasks=None)

        dest_folder = target_base / fake_download_layout.name
        assert dest_folder.is_dir()
        assert (dest_folder / "Movie.2024.1080p.mkv").exists()
        assert (dest_folder / "Movie.zh.srt").exists()
