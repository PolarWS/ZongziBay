"""
Aria2 下载器适配器测试（mock JSON-RPC 请求）
覆盖：token 认证、addTorrent/addUri、hash→gid 解析、状态映射、bt-metadata-only 磁力解析、
能力降级（不支持重命名/移动 → 返回 False）
"""
import pytest
from unittest.mock import MagicMock, patch

from app.core.downloader.aria2 import Aria2Downloader


class TestAria2Rpc:
    """_rpc：token 注入与错误处理"""

    def test_token_injected(self):
        dl = Aria2Downloader(host="http://a:6800", secret="mytoken")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"result": "gid123"}
        with patch.object(dl.session, "post", return_value=resp) as mock_post:
            dl._rpc("aria2.addUri", [["magnet:?x"], {}])
            payload = mock_post.call_args[1]["json"]
        assert payload["method"] == "aria2.addUri"
        assert payload["params"][0] == "token:mytoken"

    def test_error_raises(self):
        dl = Aria2Downloader()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"error": {"message": "unauthorized"}}
        with patch.object(dl.session, "post", return_value=resp):
            with pytest.raises(Exception) as exc:
                dl._rpc("aria2.getVersion")
        assert "unauthorized" in str(exc.value)

    def test_http_error_raises(self):
        dl = Aria2Downloader()
        resp = MagicMock()
        resp.status_code = 500
        with patch.object(dl.session, "post", return_value=resp):
            with pytest.raises(Exception):
                dl._rpc("aria2.getVersion")


class TestAria2Add:
    """add_torrent：磁力 / 种子文件两种输入"""

    def test_add_magnet_uri(self):
        dl = Aria2Downloader()
        dl._rpc = MagicMock(return_value="gid1")
        ok = dl.add_torrent("magnet:?xt=urn:btih:" + "a" * 40, save_path="/dl")
        assert ok is True
        method, params = dl._rpc.call_args[0]
        assert method == "aria2.addUri"
        assert params[0] == ["magnet:?xt=urn:btih:" + "a" * 40]
        assert params[1]["dir"] == "/dl"

    def test_add_torrent_file_base64(self):
        dl = Aria2Downloader()
        dl._rpc = MagicMock(return_value="gid2")
        import base64
        payload = b"fake-torrent"
        dl.add_torrent("", torrent_file=payload)
        method, params = dl._rpc.call_args[0]
        assert method == "aria2.addTorrent"
        assert params[0] == base64.b64encode(payload).decode("ascii")

    def test_add_no_input_raises(self):
        dl = Aria2Downloader()
        dl._rpc = MagicMock(return_value="gid3")
        from app.schemas.base import BusinessException
        with pytest.raises(BusinessException):
            dl.add_torrent("")


class TestAria2FindGid:
    """_find_gid_by_hash：扫描任务列表按 infoHash 匹配"""

    def _make(self):
        dl = Aria2Downloader()
        dl._rpc = MagicMock()
        return dl

    def test_found_in_active(self):
        dl = self._make()
        dl._rpc.side_effect = [
            [{"gid": "g1", "infoHash": "h" * 40}],  # tellActive（顶层有 infoHash）
            [],  # tellWaiting
            [],  # tellStopped
        ]
        assert dl._find_gid_by_hash("h" * 40) == "g1"

    def test_found_in_stopped(self):
        dl = self._make()
        dl._rpc.side_effect = [
            [],  # tellActive
            [],  # tellWaiting
            [{"gid": "g9", "infoHash": "x" * 40}],  # tellStopped（顶层有 infoHash）
        ]
        assert dl._find_gid_by_hash("x" * 40) == "g9"

    def test_info_hash_in_bittorrent_fallback(self):
        """infoHash 在 bittorrent 子对象（老版本 aria2）时也能匹配"""
        dl = self._make()
        dl._rpc.side_effect = [
            [{"gid": "g1", "bittorrent": {"infoHash": "y" * 40}}],
            [], [],
        ]
        assert dl._find_gid_by_hash("y" * 40) == "g1"

    def test_not_found(self):
        dl = self._make()
        dl._rpc.side_effect = [[], [], []]
        assert dl._find_gid_by_hash("z" * 40) is None

    def test_case_insensitive(self):
        dl = self._make()
        dl._rpc.side_effect = [[{"gid": "g1", "bittorrent": {"infoHash": "ABCDEF" + "a" * 34}}], [], []]
        assert dl._find_gid_by_hash("abcdef" + "a" * 34) == "g1"

    def test_skips_metadata_only_task(self):
        """bt-metadata-only 的临时任务与真实下载任务同 hash，必须跳过前者。

        命中元数据任务会拿到 [METADATA] 占位路径，归档阶段找不到目标而无限重试。
        """
        dl = self._make()
        dl._rpc.side_effect = [
            [],  # tellActive
            [],  # tellWaiting
            [    # tellStopped：元数据任务排在真实下载任务前面
                {"gid": "meta", "infoHash": "m" * 40, "status": "complete",
                 "files": [{"path": "/downloads/[METADATA]Movie", "length": "1945"}]},
                {"gid": "real", "infoHash": "m" * 40, "status": "complete",
                 "bittorrent": {"mode": "multi"},
                 "files": [{"path": "/downloads/Movie/a.mkv", "length": "100"}]},
            ],
        ]
        assert dl._find_gid_by_hash("m" * 40) == "real"

    def test_metadata_only_task_alone_returns_none(self):
        """只剩元数据任务时返回 None，让上层走「任务不存在」而不是拿到假路径"""
        dl = self._make()
        dl._rpc.side_effect = [
            [],  # tellActive
            [],  # tellWaiting
            [{"gid": "meta", "infoHash": "m" * 40, "status": "complete",
              "files": [{"path": "/downloads/[METADATA]Movie", "length": "1945"}]}],
        ]
        assert dl._find_gid_by_hash("m" * 40) is None

    def test_real_single_file_task_kept(self):
        """真实任务靠 bittorrent.mode 识别，文件名以 [METADATA] 开头也不误伤"""
        dl = self._make()
        dl._rpc.side_effect = [
            [{"gid": "g1", "infoHash": "s" * 40,
              "bittorrent": {"mode": "single"},
              "files": [{"path": "/downloads/[METADATA]Trick.mkv", "length": "100"}]}],
            [], [],
        ]
        assert dl._find_gid_by_hash("s" * 40) == "g1"


class TestAria2GetInfo:
    """get_torrent_info：Aria2 tellStatus → 规范化 dict"""

    def _make(self, status="active", total=1000, completed=500, seeder=False, name="Movie"):
        dl = Aria2Downloader()
        dl._find_gid_by_hash = MagicMock(return_value="g1")
        dl._rpc = MagicMock(return_value={
            "gid": "g1",
            "status": status,
            "totalLength": str(total),
            "completedLength": str(completed),
            "uploadLength": "0",
            "dir": "/dl",
            "seeder": seeder,
            "infoHash": "h" * 40,   # 真实 Aria2 顶层即含 infoHash
            "bittorrent": {"info": {"name": name}},
            "files": [],
        })
        return dl

    def test_downloading(self):
        dl = self._make()
        info = dl.get_torrent_info("h" * 40)
        assert info["state"] == "downloading"
        assert info["progress"] == 0.5
        assert info["total_size"] == 1000
        assert info["save_path"] == "/dl"
        assert info["name"] == "Movie"
        assert info["hash"] == "h" * 40

    def test_complete_seeding(self):
        dl = self._make(status="complete", completed=1000, seeder=True)
        info = dl.get_torrent_info("h" * 40)
        assert info["state"] == "uploading"
        assert info["progress"] == 1.0

    def test_paused(self):
        dl = self._make(status="paused", completed=0)
        info = dl.get_torrent_info("h" * 40)
        assert info["state"] == "pausedDL"

    def test_error(self):
        dl = self._make(status="error")
        info = dl.get_torrent_info("h" * 40)
        assert info["state"] == "error"

    def test_not_found(self):
        dl = Aria2Downloader()
        dl._find_gid_by_hash = MagicMock(return_value=None)
        assert dl.get_torrent_info("h" * 40) is None


class TestAria2ParseMagnet:
    """parse_magnet：bt-metadata-only 只拉元数据不下载数据"""

    @patch("time.sleep")
    def test_success(self, mock_sleep):
        dl = Aria2Downloader()
        dl._rpc = MagicMock()
        dl._rpc.side_effect = [
            "gid_meta",   # aria2.addUri
            {"infoHash": "h" * 40, "status": "active"},   # tellStatus 元数据就绪（顶层 infoHash）
            [{"path": "/dl/f1.mkv", "length": "100"}],                    # getFiles
            None,          # remove
            None,          # removeDownloadResult
        ]
        files = dl.parse_magnet("magnet:?xt=urn:btih:" + "h" * 40, timeout=5)
        assert len(files) == 1
        assert files[0].name == "f1.mkv"
        assert files[0].size == 100
        # 确认 addUri 使用 bt-metadata-only
        add_call = dl._rpc.call_args_list[0]
        params = add_call[0][1]
        assert add_call[0][0] == "aria2.addUri"
        assert params[1]["bt-metadata-only"] == "true"
        # 清理调用
        dl._rpc.assert_any_call("aria2.remove", ["gid_meta"])

    @patch("time.sleep")
    def test_metadata_placeholder_filtered(self, mock_sleep):
        """过滤 Aria2 元数据阶段的 [METADATA] 占位文件，返回真实文件"""
        dl = Aria2Downloader()
        dl._rpc = MagicMock()
        dl._rpc.side_effect = [
            "gid_meta",
            {"infoHash": "h" * 40, "status": "active"},
            [{"path": "/dl/[METADATA]ubuntu.iso", "length": "0"},
             {"path": "/dl/ubuntu.iso", "length": "4762707968"}],  # 真实文件
            None,
            None,
        ]
        files = dl.parse_magnet("magnet:?xt=urn:btih:" + "h" * 40, timeout=5)
        assert len(files) == 1
        assert files[0].name == "ubuntu.iso"
        assert files[0].size == 4762707968

    @patch("time.sleep")
    def test_timeout(self, mock_sleep):
        dl = Aria2Downloader()
        dl._rpc = MagicMock()
        # tellStatus 一直无 infoHash
        dl._rpc.side_effect = [
            "gid_meta",
            {"status": "active"},
            None,
            None,
        ]
        with pytest.raises(Exception) as exc:
            dl.parse_magnet("magnet:?xt=urn:btih:" + "h" * 40, timeout=0.1)
        assert "超时" in str(exc.value)
        # 超时后应清理
        dl._rpc.assert_any_call("aria2.remove", ["gid_meta"])


class TestAria2Delete:
    """delete_torrents：不同状态任务的删除策略与幂等容错"""

    def _make(self):
        dl = Aria2Downloader()
        dl._rpc = MagicMock()
        return dl

    def test_active_task_uses_remove(self):
        """active 任务 → aria2.remove"""
        dl = self._make()
        dl._find_gid_by_hash = MagicMock(return_value="g1")
        dl._rpc.return_value = {"status": "active"}  # tellStatus
        ok = dl.delete_torrents("h" * 40)
        assert ok is True
        dl._rpc.assert_any_call("aria2.tellStatus", ["g1"])
        dl._rpc.assert_any_call("aria2.remove", ["g1"])

    def test_error_task_uses_remove_download_result(self):
        """error 任务 → aria2.removeDownloadResult"""
        dl = self._make()
        dl._find_gid_by_hash = MagicMock(return_value="g1")
        dl._rpc.return_value = {"status": "error"}  # tellStatus
        ok = dl.delete_torrents("h" * 40)
        assert ok is True
        dl._rpc.assert_any_call("aria2.removeDownloadResult", ["g1"])

    def test_remove_raises_is_tolerated(self):
        """aria2.remove 抛异常 → 视为已删除（幂等容错），仍返回 True"""
        dl = self._make()
        dl._find_gid_by_hash = MagicMock(return_value="g1")
        dl._rpc.side_effect = [{"status": "active"}, Exception("HTTP 400")]
        ok = dl.delete_torrents("h" * 40)
        assert ok is True

    def test_no_gid_returns_true(self):
        """gid 找不到 → 视为无需删除，返回 True"""
        dl = self._make()
        dl._find_gid_by_hash = MagicMock(return_value=None)
        assert dl.delete_torrents("z" * 40) is True


class TestAria2ResumePauseIdempotent:
    """resume/pause：对状态不匹配的任务幂等容错（不中断流程）"""

    def test_resume_active_tolerates_error(self):
        """任务已在运行 → unpause 报错但返回 True"""
        dl = Aria2Downloader()
        dl._find_gid_by_hash = MagicMock(return_value="g1")
        dl._rpc = MagicMock(side_effect=Exception("HTTP 400"))
        assert dl.resume_torrents("h" * 40) is True

    def test_pause_paused_tolerates_error(self):
        """任务已暂停 → pause 报错但返回 True"""
        dl = Aria2Downloader()
        dl._find_gid_by_hash = MagicMock(return_value="g1")
        dl._rpc = MagicMock(side_effect=Exception("HTTP 400"))
        assert dl.pause_torrents("h" * 40) is True


class TestAria2Capabilities:
    """能力降级：不支持重命名 / 移动"""

    def test_capabilities(self):
        dl = Aria2Downloader()
        assert dl.capabilities.name == "aria2"
        assert dl.capabilities.supports_rename is False
        assert dl.capabilities.supports_set_location is False
        assert dl.capabilities.supports_paused_metadata is False
        assert dl.capabilities.supports_file_selection is True

    def test_rename_returns_false(self):
        dl = Aria2Downloader()
        assert dl.rename_file("h" * 40, "a.mkv", "b.mkv") is False
        assert dl.rename_folder("h" * 40, "dir", "dir2") is False

    def test_set_location_returns_false(self):
        dl = Aria2Downloader()
        assert dl.set_location("h" * 40, "/new") is False
