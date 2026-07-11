"""
模拟 qBittorrent 下载任务测试
TaskService：tracker 追加、路径解析、add_task 流程、push_to_qb（mock qB 与 DB）
TaskMonitor：qb 状态映射、qB 中无任务时的状态同步（mock client）
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.task import AddTaskRequest
from app.services.task_monitor import TaskMonitor
from app.services.task_service import TaskService


# ---------------------------------------------------------------------------
# TaskService：_append_trackers
# ---------------------------------------------------------------------------

class TestTaskServiceAppendTrackers:
    """TaskService._append_trackers：磁链后追加 tracker"""

    def test_empty_trackers_returns_unchanged(self):
        magnet = "magnet:?xt=urn:btih:abc"
        assert TaskService._append_trackers(magnet, []) == magnet
        assert TaskService._append_trackers(magnet, None) == magnet

    def test_empty_magnet_returns_empty(self):
        assert TaskService._append_trackers("", ["http://t1"]) == ""
        assert TaskService._append_trackers(None, ["http://t1"]) == ""

    def test_single_tracker(self):
        magnet = "magnet:?xt=urn:btih:abc"
        out = TaskService._append_trackers(magnet, ["http://tracker.example/announce"])
        assert out.startswith(magnet)
        assert "tr=" in out
        assert "tracker.example" in out

    def test_multiple_trackers(self):
        magnet = "magnet:?xt=urn:btih:def"
        trackers = ["udp://a:80/announce", "udp://b:1337/announce"]
        out = TaskService._append_trackers(magnet, trackers)
        assert out.count("tr=") == 2


# ---------------------------------------------------------------------------
# TaskService：路径解析（通过 add_task 入口，mock qB 与 DB）
# ---------------------------------------------------------------------------

class TestTaskServicePathResolution:
    """add_task 时按 type 与 sourcePath/targetPath 解析出的路径"""

    @pytest.fixture
    def mock_config_paths(self):
        def get(key, default=None):
            if key == "paths.tv_download_path":
                return "/dl/tv"
            if key == "paths.tv_target_path":
                return "/nas/tv"
            if key == "paths.movie_download_path":
                return "/dl/movies"
            if key == "paths.movie_target_path":
                return "/nas/movies"
            if key == "paths.anime_download_path":
                return "/dl/anime"
            if key == "paths.anime_target_path":
                return "/nas/anime"
            if key == "paths.default_download_path":
                return "/downloads"
            if key == "paths.default_target_path":
                return "/nas/default"
            if key == "trackers":
                return []
            if key == "qbittorrent":
                return {"host": "http://localhost:8080", "username": "admin", "password": "admin", "api_key": ""}
            return default
        return get

    @patch("app.services.task_service.db")
    @patch("app.services.task_service.config")
    def test_tv_type_uses_tv_paths(self, mock_config, mock_db, mock_config_paths):
        mock_config.get.side_effect = mock_config_paths
        mock_db.get_conn.return_value = MagicMock()
        mock_db.insert_download_task.return_value = 1
        mock_db.insert_file_task.return_value = None
        mock_db.insert_notification.return_value = None
        mock_db.get_tasks_by_hash.return_value = []

        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.add_torrent.return_value = True
        ts.qb_client.get_torrent_info.return_value = None

        req = AddTaskRequest(
            taskName="Test TV",
            sourceUrl="magnet:?xt=urn:btih:a" + "0" * 39,
            type="tv",
        )
        ts.add_task(req)

        call_kw = mock_db.insert_download_task.call_args[1]
        assert call_kw["sourcePath"] == "/dl/tv"
        assert call_kw["targetPath"] == "/nas/tv"

    @patch("app.services.task_service.db")
    @patch("app.services.task_service.config")
    def test_movie_type_uses_movie_paths(self, mock_config, mock_db, mock_config_paths):
        mock_config.get.side_effect = mock_config_paths
        mock_db.get_conn.return_value = MagicMock()
        mock_db.insert_download_task.return_value = 1
        mock_db.insert_file_task.return_value = None
        mock_db.insert_notification.return_value = None
        mock_db.get_tasks_by_hash.return_value = []

        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.add_torrent.return_value = True
        ts.qb_client.get_torrent_info.return_value = None

        req = AddTaskRequest(
            taskName="Test Movie",
            sourceUrl="magnet:?xt=urn:btih:b" + "0" * 39,
            type="movie",
        )
        ts.add_task(req)

        call_kw = mock_db.insert_download_task.call_args[1]
        assert call_kw["sourcePath"] == "/dl/movies"
        assert call_kw["targetPath"] == "/nas/movies"

    @patch("app.services.task_service.db")
    @patch("app.services.task_service.config")
    def test_relative_source_and_target_appended(self, mock_config, mock_db, mock_config_paths):
        mock_config.get.side_effect = mock_config_paths
        mock_db.get_conn.return_value = MagicMock()
        mock_db.insert_download_task.return_value = 1
        mock_db.insert_file_task.return_value = None
        mock_db.insert_notification.return_value = None
        mock_db.get_tasks_by_hash.return_value = []

        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.add_torrent.return_value = True
        ts.qb_client.get_torrent_info.return_value = None

        req = AddTaskRequest(
            taskName="Test",
            sourceUrl="magnet:?xt=urn:btih:c" + "0" * 39,
            sourcePath="subdir",
            targetPath="movies/MyMovie",
            type="movie",
        )
        ts.add_task(req)

        call_kw = mock_db.insert_download_task.call_args[1]
        assert "subdir" in call_kw["sourcePath"]
        assert "movies" in call_kw["targetPath"] or "MyMovie" in call_kw["targetPath"]


# ---------------------------------------------------------------------------
# TaskService：路径规范化 _norm_path
# ---------------------------------------------------------------------------

class TestTaskServiceNormPath:
    """_norm_path：路径规范化用于比较"""

    def test_normalize_slashes(self):
        ts = TaskService()
        p1 = ts._norm_path("/path\\to\\\\folder/")
        p2 = ts._norm_path("\\path/to//folder")
        assert p1 == p2

    def test_normalize_empty(self):
        ts = TaskService()
        assert ts._norm_path("") == ""
        assert ts._norm_path(None) == ""

    def test_same_path_equal(self):
        ts = TaskService()
        assert ts._norm_path("/downloads/movies") == ts._norm_path("\\downloads\\movies")


# ---------------------------------------------------------------------------
# TaskService：push_to_qb（单独测试，不含事务所绑定）
# ---------------------------------------------------------------------------

class TestTaskServicePushToQb:
    """push_to_qb：推送任务到 qBittorrent"""

    def test_new_task_adds_torrent(self):
        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.get_torrent_info.return_value = None
        ts.qb_client.add_torrent.return_value = True
        ts.trackers = []
        success = ts.push_to_qb(
            task_id=1,
            source_url="magnet:?xt=urn:btih:" + "d" * 40,
            source_path="/downloads",
            torrent_hash="d" * 40,
        )
        assert success is True
        ts.qb_client.add_torrent.assert_called_once()

    def test_existing_task_skips_add_and_resumes(self):
        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.get_torrent_info.return_value = {"save_path": "/downloads", "state": "pausedUP"}
        ts.trackers = []
        success = ts.push_to_qb(
            task_id=1,
            source_url="magnet:?xt=urn:btih:" + "e" * 40,
            source_path="/downloads",
            torrent_hash="e" * 40,
        )
        assert success is True
        ts.qb_client.add_torrent.assert_not_called()
        ts.qb_client.resume_torrents.assert_called()

    def test_existing_task_different_path_sets_location(self):
        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.get_torrent_info.return_value = {"save_path": "/old/path", "state": "downloading"}
        ts.trackers = []
        ts.push_to_qb(
            task_id=1,
            source_url="magnet:?xt=urn:btih:" + "f" * 40,
            source_path="/new/path",
            torrent_hash="f" * 40,
        )
        ts.qb_client.set_location.assert_called_once_with("f" * 40, "/new/path")

    def test_add_torrent_failure_raises(self):
        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.get_torrent_info.return_value = None
        ts.qb_client.add_torrent.return_value = False
        ts.trackers = []
        from app.schemas.base import BusinessException
        with pytest.raises(BusinessException) as exc:
            ts.push_to_qb(
                task_id=1,
                source_url="magnet:?xt=urn:btih:" + "g" * 40,
                source_path="/downloads",
                torrent_hash="g" * 40,
            )
        assert "无法添加" in str(exc.value)


# ---------------------------------------------------------------------------
# TaskService：取消任务
# ---------------------------------------------------------------------------

class TestTaskServiceCancelTask:
    """cancel_task：取消下载/做种中的任务"""

    @patch("app.services.task_service.db")
    def test_cancel_downloading_deletes_files(self, mock_db):
        mock_db.get_download_task_by_id.return_value = {
            "id": 1,
            "taskName": "test",
            "sourceUrl": "magnet:?xt=urn:btih:" + "h" * 40,
            "taskStatus": "downloading",
        }
        ts = TaskService()
        ts.qb_client = MagicMock()
        ts.qb_client.get_torrent_info.return_value = {"hash": "h" * 40}
        ts.cancel_task(1)
        ts.qb_client.delete_torrents.assert_called_with("h" * 40, delete_files=True)
        mock_db.update_download_task_status.assert_called_with(1, "cancelled")

    @patch("app.services.task_service.db")
    def test_cancel_seeding_checks_temp_folder(self, mock_db):
        mock_db.get_download_task_by_id.return_value = {
            "id": 2,
            "taskName": "test_seeding",
            "sourceUrl": "magnet:?xt=urn:btih:" + "j" * 40,
            "taskStatus": "seeding",
            "targetPath": "/nas/tv/show",
        }
        ts = TaskService()
        ts.qb_client = MagicMock()
        # 第一次返回有效信息（做种中），后续轮询返回 None 表示 qB 已移除
        ts.qb_client.get_torrent_info.side_effect = [
            {"hash": "j" * 40, "save_path": "/temp/download"},  # 首次调用
        ] + [None] * 10  # 轮询确认时返回 None
        mock_db.get_file_tasks.return_value = []
        ts.cancel_task(2)
        # 做种中文件仍在临时目录 -> 删除文件
        ts.qb_client.delete_torrents.assert_called_with("j" * 40, delete_files=True)

    @patch("app.services.task_service.db")
    def test_cancel_completed_raises_error(self, mock_db):
        mock_db.get_download_task_by_id.return_value = {
            "id": 3,
            "taskName": "done",
            "sourceUrl": "magnet:?xt=urn:btih:" + "k" * 40,
            "taskStatus": "completed",
        }
        ts = TaskService()
        from app.schemas.base import BusinessException
        with pytest.raises(BusinessException) as exc:
            ts.cancel_task(3)
        assert "取消" in str(exc.value)


# ---------------------------------------------------------------------------
# TaskMonitor：qb 状态映射 _map_status
# ---------------------------------------------------------------------------

class TestTaskMonitorMapStatus:
    """_map_status：qb state -> 系统状态"""

    def test_uploading_seeding_when_limit_ratio_configured(self):
        monitor = TaskMonitor()
        with patch("app.services.task_monitor.config") as mock_cfg:
            mock_cfg.get.return_value = 2.0
            assert monitor._map_status("uploading") == "seeding"
            assert monitor._map_status("stalledUP") == "seeding"

    def test_uploading_completed_when_no_seeding_config(self):
        monitor = TaskMonitor()
        with patch("app.services.task_monitor.config") as mock_cfg:
            mock_cfg.get.return_value = -1.0
            assert monitor._map_status("uploading") == "completed"
            assert monitor._map_status("stalledUP") == "completed"

    def test_error_states(self):
        monitor = TaskMonitor()
        assert monitor._map_status("error") == "error"
        assert monitor._map_status("missingFiles") == "error"

    def test_downloading_states(self):
        monitor = TaskMonitor()
        assert monitor._map_status("downloading") == "downloading"
        assert monitor._map_status("stalledDL") == "downloading"
        assert monitor._map_status("metaDL") == "downloading"

    def test_checking_states(self):
        monitor = TaskMonitor()
        assert monitor._map_status("checkingUP") == "checking"
        assert monitor._map_status("checkingDL") == "checking"
        assert monitor._map_status("checkingResumeData") == "checking"

    def test_queued_up_states(self):
        monitor = TaskMonitor()
        with patch("app.services.task_monitor.config") as mock_cfg:
            mock_cfg.get.return_value = -1.0
            assert monitor._map_status("queuedUP") == "completed"
            assert monitor._map_status("pausedUP") == "completed"


# ---------------------------------------------------------------------------
# TaskMonitor：模拟 qB 返回无任务 / 已完成 时的行为
# ---------------------------------------------------------------------------

class TestTaskMonitorQbSimulation:
    """模拟 qB 客户端返回：无任务时同步取消/完成；有任务时状态更新"""

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.magnet_service")
    def test_qb_no_torrent_seeding_marked_completed(self, mock_magnet, mock_db):
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = None
        mock_magnet._get_client.return_value = mock_client

        task = {
            "id": 1,
            "taskName": "a" * 40,
            "sourceUrl": "magnet:?xt=urn:btih:" + "a" * 40,
            "taskStatus": "seeding",
        }
        mock_db.get_active_tasks.return_value = [task]

        monitor = TaskMonitor()
        monitor._check_tasks()

        mock_db.update_task_status.assert_called_once_with(1, "completed")

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.magnet_service")
    def test_qb_no_torrent_downloading_recovered(self, mock_magnet, mock_db):
        """qB 中无该种子 -> 先尝试重推（push_to_qb），成功则继续"""
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = None
        mock_magnet._get_client.return_value = mock_client

        task = {
            "id": 2,
            "taskName": "b" * 40,
            "sourceUrl": "magnet:?xt=urn:btih:" + "b" * 40,
            "sourcePath": "/downloads",
            "taskStatus": "downloading",
        }
        mock_db.get_active_tasks.return_value = [task]
        mock_db.get_file_tasks.return_value = []

        monitor = TaskMonitor()
        with patch("app.services.task_service.TaskService.push_to_qb", return_value=True):
            monitor._check_tasks()

    @patch("app.services.task_monitor.db")
    @patch("app.services.task_monitor.magnet_service")
    def test_qb_returns_downloading_updates_status(self, mock_magnet, mock_db):
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = {
            "hash": "c" * 40,
            "state": "downloading",
            "progress": 0.5,
        }
        mock_magnet._get_client.return_value = mock_client

        task = {
            "id": 3,
            "taskName": "c" * 40,
            "sourceUrl": "magnet:?xt=urn:btih:" + "c" * 40,
            "taskStatus": "downloading",
        }
        mock_db.get_active_tasks.return_value = [task]
        mock_db.get_file_tasks.return_value = []

        monitor = TaskMonitor()
        monitor._check_tasks()

        mock_db.update_task_status.assert_called_with(3, "downloading", 50.0)
