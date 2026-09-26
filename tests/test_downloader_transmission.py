"""
Transmission 下载器适配器测试（mock RPC 请求）
覆盖：session-id 协商、添加磁力/种子、文件选择、重命名、移动、删除、状态映射
"""
import pytest
from unittest.mock import MagicMock, patch

from app.core.downloader.transmission import TransmissionDownloader


class TestTransmissionRpc:
    """_rpc：session-id 协商与结果解析"""

    def test_409_session_negotiation(self):
        """首次 409 后带 session-id 重发成功"""
        dl = TransmissionDownloader(host="http://t:9091")
        first = MagicMock()
        first.status_code = 409
        first.headers = {"X-Transmission-Session-Id": "abc123"}
        second = MagicMock()
        second.status_code = 200
        second.json.return_value = {"result": "success", "arguments": {"version": "4.0.5"}}
        with patch.object(dl.session, "post", side_effect=[first, second]) as mock_post:
            args = dl._rpc("session-get", {"fields": ["version"]})
        assert args["version"] == "4.0.5"
        assert dl._session_id == "abc123"
        # 第二次请求应带 session-id 头
        assert mock_post.call_count == 2

    def test_result_error_raises(self):
        dl = TransmissionDownloader()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"result": "invalid torrent"}
        with patch.object(dl.session, "post", return_value=resp):
            with pytest.raises(Exception):
                dl._rpc("torrent-add", {})

    def test_http_error_raises(self):
        dl = TransmissionDownloader()
        resp = MagicMock()
        resp.status_code = 500
        with patch.object(dl.session, "post", return_value=resp):
            with pytest.raises(Exception):
                dl._rpc("torrent-add", {})


class TestTransmissionAdd:
    """add_torrent：磁力 / 种子文件两种输入"""

    def test_add_magnet(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        ok = dl.add_torrent("magnet:?xt=urn:btih:" + "a" * 40, save_path="/dl")
        assert ok is True
        method, args = dl._rpc.call_args[0]
        assert method == "torrent-add"
        assert args["filename"] == "magnet:?xt=urn:btih:" + "a" * 40
        assert args["download-dir"] == "/dl"
        assert args["paused"] is False

    def test_add_magnet_paused(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        dl.add_torrent("magnet:?xt=urn:btih:" + "b" * 40, is_paused=True)
        _, args = dl._rpc.call_args[0]
        assert args["paused"] is True

    def test_add_torrent_file_base64(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        import base64
        payload = b"fake-torrent-bytes"
        dl.add_torrent("", torrent_file=payload)
        _, args = dl._rpc.call_args[0]
        assert args["metainfo"] == base64.b64encode(payload).decode("ascii")

    def test_add_no_input_raises(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        from app.schemas.base import BusinessException
        with pytest.raises(BusinessException):
            dl.add_torrent("")


class TestTransmissionGetInfo:
    """get_torrent_info：Transmission 原始字段 → 规范化 dict"""

    def _make(self, status=4, is_finished=False, percent=0.5):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={
            "torrents": [{
                "hashString": "h" * 40,
                "name": "Movie",
                "status": status,
                "percentDone": percent,
                "totalSize": 1000,
                "downloadDir": "/dl",
                "ratio": 1.2,
                "isFinished": is_finished,
                "files": [],
            }]
        })
        return dl

    def test_downloading_state(self):
        dl = self._make(status=4, percent=0.5)
        info = dl.get_torrent_info("h" * 40)
        assert info["state"] == "downloading"
        assert info["progress"] == 0.5
        assert info["total_size"] == 1000
        assert info["save_path"] == "/dl"
        assert info["ratio"] == 1.2
        assert info["hash"] == "h" * 40

    def test_seeding_state(self):
        dl = self._make(status=6, percent=1.0)
        info = dl.get_torrent_info("h" * 40)
        assert info["state"] == "uploading"
        assert info["progress"] == 1.0

    def test_paused_finished_up(self):
        dl = self._make(status=0, is_finished=True)
        info = dl.get_torrent_info("h" * 40)
        assert info["state"] == "pausedUP"

    def test_not_found_returns_none(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={"torrents": []})
        assert dl.get_torrent_info("h" * 40) is None


class TestTransmissionFiles:
    """get_torrent_files：Transmission files → 规范化 [{index,name,path,size}]"""

    def test_normalize(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={
            "torrents": [{"files": [
                {"name": "dir/a.mkv", "length": 100},
                {"name": "dir/b.srt", "length": 50},
            ]}]
        })
        files = dl.get_torrent_files("h" * 40)
        assert len(files) == 2
        assert files[0]["index"] == 0
        assert files[0]["name"] == "a.mkv"
        assert files[0]["path"] == "dir/a.mkv"
        assert files[0]["size"] == 100


class TestTransmissionControls:
    """文件选择 / 重命名 / 移动 / 删除 / 暂停恢复"""

    def test_set_file_priority_wanted(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        dl.set_file_priority("h" * 40, [0, 1], 1)
        method, args = dl._rpc.call_args[0]
        assert method == "torrent-set"
        assert args["files-wanted"] == [0, 1]

    def test_set_file_priority_unwanted(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        dl.set_file_priority("h" * 40, [2], 0)
        method, args = dl._rpc.call_args[0]
        assert method == "torrent-set"
        assert args["files-unwanted"] == [2]

    def test_rename_file(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        dl.rename_file("h" * 40, "dir/a.mkv", "dir/New.mkv")
        method, args = dl._rpc.call_args[0]
        assert method == "torrent-rename-path"
        assert args["path"] == "dir/a.mkv"
        assert args["name"] == "New.mkv"

    def test_set_location_move(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        dl.set_location("h" * 40, "/target")
        method, args = dl._rpc.call_args[0]
        assert method == "torrent-set-location"
        assert args["location"] == "/target"
        assert args["move"] is True

    def test_delete_with_files(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        dl.delete_torrents("h" * 40, delete_files=True)
        method, args = dl._rpc.call_args[0]
        assert method == "torrent-remove"
        assert args["delete-local-data"] is True

    def test_resume_pause(self):
        dl = TransmissionDownloader()
        dl._rpc = MagicMock(return_value={})
        dl.resume_torrents("h" * 40)
        assert dl._rpc.call_args[0][0] == "torrent-start"
        dl.pause_torrents("h" * 40)
        assert dl._rpc.call_args[0][0] == "torrent-stop"


class TestTransmissionCapabilities:
    """能力标记：支持选文件，但暂停态拿不到元数据"""

    def test_capabilities(self):
        dl = TransmissionDownloader()
        assert dl.capabilities.name == "transmission"
        assert dl.capabilities.supports_rename is True
        assert dl.capabilities.supports_set_location is True
        # Transmission 暂停时不连 peer，元数据永远拉不到 → 只能运行态选文件
        assert dl.capabilities.supports_paused_metadata is False
        assert dl.capabilities.supports_runtime_file_selection is True
        assert dl.capabilities.supports_file_selection is True


class TestTransmissionParseMagnet:
    """parse_magnet：必须运行态添加，暂停态拉不到元数据"""

    @staticmethod
    def _downloader():
        dl = TransmissionDownloader(host="http://t:9091")
        dl.add_torrent = MagicMock(return_value=True)
        dl.delete_torrents = MagicMock(return_value=True)
        return dl

    def test_parse_adds_unpaused(self):
        dl = self._downloader()
        dl.get_torrent_info = MagicMock(return_value={"total_size": 1024})
        dl.get_torrent_files = MagicMock(return_value=[
            {"name": "a.mkv", "path": "a.mkv", "size": 1024, "index": 0},
        ])

        files = dl.parse_magnet("magnet:?xt=urn:btih:" + "a" * 40, timeout=5)

        # 关键：非暂停添加，否则元数据永远等不到
        assert dl.add_torrent.call_args[1]["is_paused"] is False
        assert len(files) == 1
        # 临时种子连同解析期间的数据一起清理
        dl.delete_torrents.assert_called_once_with("a" * 40, delete_files=True)

    def test_parse_timeout_cleans_up(self):
        from app.schemas.base import BusinessException

        dl = self._downloader()
        dl.get_torrent_info = MagicMock(return_value=None)

        with pytest.raises(BusinessException):
            dl.parse_magnet("magnet:?xt=urn:btih:" + "a" * 40, timeout=0.1)

        dl.delete_torrents.assert_called_once()
