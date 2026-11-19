"""
下载器抽象层基类测试
覆盖：extract_info_hash、TorrentFile 规范化、parse_magnet 默认实现（qB 风格暂停添加拉元数据）
"""
import pytest
from unittest.mock import MagicMock, patch

from app.core.downloader.base import (
    BaseDownloader,
    DownloaderCapabilities,
    TorrentFile,
    _bencode_torrent_files,
    _bencode_torrent_info_hash,
    _extract_info_hash,
)


class TestExtractInfoHash:
    """_extract_info_hash：从磁链 / 纯 hash 提取 40 位 info hash"""

    def test_from_magnet(self):
        assert _extract_info_hash("magnet:?xt=urn:btih:" + "a" * 40) == "a" * 40

    def test_from_pure_hex(self):
        assert _extract_info_hash("b" * 40) == "b" * 40

    def test_uppercase_lowercased(self):
        assert _extract_info_hash("A" * 40) == "a" * 40

    def test_empty_returns_none(self):
        assert _extract_info_hash("") is None
        assert _extract_info_hash(None) is None

    def test_no_hash_returns_none(self):
        assert _extract_info_hash("http://example.com/x") is None


class TestNormalizeFiles:
    """BaseDownloader._normalize_files：后端文件列表 → TorrentFile"""

    def test_basic_normalize(self):
        raw = [
            {"name": "a.mkv", "path": "folder/a.mkv", "size": 100},
            {"name": "b.srt", "path": "b.srt", "size": 50},
        ]
        files = BaseDownloader._normalize_files(raw)
        assert len(files) == 2
        assert files[0].name == "a.mkv"
        assert files[0].path == "folder/a.mkv"
        assert files[0].size == 100
        assert files[0].index == 0
        assert files[1].index == 1

    def test_name_from_path_fallback(self):
        raw = [{"path": "dir/movie.mkv", "size": 10}]
        files = BaseDownloader._normalize_files(raw)
        assert files[0].name == "movie.mkv"

    def test_empty_list(self):
        assert BaseDownloader._normalize_files([]) == []


class _StubDownloader(BaseDownloader):
    """仅实现抽象方法的最小后端，用于验证基类默认 parse_magnet 流程"""
    capabilities = DownloaderCapabilities(name="stub")

    def __init__(self, files=None, info_total=1000):
        super().__init__()
        self.files = files or [{"name": "f1.mkv", "path": "f1.mkv", "size": 1000}]
        self.info_total = info_total
        self.add_called = []
        self.delete_called = []
        self.metadata_ready = True

    def check_connection(self) -> bool:
        return True

    def get_version(self) -> str:
        return "stub"

    def add_torrent(self, urls, is_paused=False, save_path=None, content_layout=None, torrent_file=None) -> bool:
        self.add_called.append((urls, is_paused))
        return True

    def get_torrent_info(self, torrent_hash):
        if not self.metadata_ready:
            return {"hash": torrent_hash, "total_size": 0}
        return {"hash": torrent_hash, "total_size": self.info_total, "state": "downloading"}

    def get_torrent_files(self, torrent_hash):
        return self.files

    def delete_torrents(self, hashes, delete_files=True) -> bool:
        self.delete_called.append(hashes)
        return True

    def set_file_priority(self, torrent_hash, file_ids, priority) -> bool:
        return True

    def resume_torrents(self, hashes) -> bool:
        return True

    def pause_torrents(self, hashes) -> bool:
        return True

    def rename_file(self, torrent_hash, old_path, new_path) -> bool:
        return True

    def rename_folder(self, torrent_hash, old_path, new_path) -> bool:
        return True

    def set_location(self, hashes, location) -> bool:
        return True


class TestParseMagnetDefault:
    """默认 parse_magnet：暂停添加 → 轮询元数据 → 取文件 → 删除临时种子"""

    @patch("time.sleep")
    def test_success_flow(self, mock_sleep):
        backend = _StubDownloader()
        files = backend.parse_magnet("magnet:?xt=urn:btih:" + "a" * 40, timeout=5)
        assert len(files) == 1
        assert files[0].name == "f1.mkv"
        # 应以暂停状态添加（只取元数据不下载）
        assert backend.add_called[0][1] is True
        # 解析完成后应删除临时种子
        assert backend.delete_called == ["a" * 40]

    @patch("time.sleep")
    def test_invalid_magnet_raises(self, mock_sleep):
        backend = _StubDownloader()
        from app.schemas.base import BusinessException
        with pytest.raises(BusinessException):
            backend.parse_magnet("http://invalid", timeout=1)

    @patch("time.sleep")
    def test_timeout_raises(self, mock_sleep):
        backend = _StubDownloader()
        backend.metadata_ready = False  # 一直无元数据
        with pytest.raises(Exception) as exc:
            backend.parse_magnet("magnet:?xt=urn:btih:" + "a" * 40, timeout=0.1)
        assert "超时" in str(exc.value)
        # 超时后也应清理临时种子
        assert backend.delete_called == ["a" * 40]


class TestBencodeTorrentParser:
    """本地 .torrent 解析（不依赖下载器网络）"""

    def _build_torrent(self, multi_file=False):
        """构造一个最小可用的 bencode .torrent 字节"""
        info = {
            "name": "MyMovie",
            "piece length": 262144,
            "pieces": b"x" * 20,
        }
        if multi_file:
            info["files"] = [
                {"length": 1000, "path": ["dir", "a.mkv"]},
                {"length": 500, "path": ["dir", "a.srt"]},
            ]
        else:
            info["length"] = 2000
        return b"d4:info" + self._encode(info) + b"e"

    @staticmethod
    def _encode(obj):
        if isinstance(obj, bytes):
            return str(len(obj)).encode() + b":" + obj
        if isinstance(obj, int):
            return b"i" + str(obj).encode() + b"e"
        if isinstance(obj, str):
            b = obj.encode("utf-8")
            return str(len(b)).encode() + b":" + b
        if isinstance(obj, dict):
            parts = []
            for k, v in obj.items():
                parts.append(TestBencodeTorrentParser._encode(k))
                parts.append(TestBencodeTorrentParser._encode(v))
            return b"d" + b"".join(parts) + b"e"
        if isinstance(obj, list):
            parts = [TestBencodeTorrentParser._encode(i) for i in obj]
            return b"l" + b"".join(parts) + b"e"
        raise TypeError(type(obj))

    def test_single_file(self):
        torrent = self._build_torrent(multi_file=False)
        files = _bencode_torrent_files(torrent)
        assert len(files) == 1
        assert files[0].name == "MyMovie"
        assert files[0].size == 2000

    def test_multi_file(self):
        torrent = self._build_torrent(multi_file=True)
        files = _bencode_torrent_files(torrent)
        assert len(files) == 2
        assert files[0].name == "a.mkv"
        assert files[0].path == "dir/a.mkv"
        assert files[0].size == 1000
        assert files[1].name == "a.srt"

    def test_info_hash_computed(self):
        torrent = self._build_torrent(multi_file=False)
        h = _bencode_torrent_info_hash(torrent)
        assert h and len(h) == 40
        assert all(c in "0123456789abcdef" for c in h)

    def test_invalid_bytes(self):
        assert _bencode_torrent_files(b"not a torrent") == []
        assert _bencode_torrent_info_hash(b"not a torrent") is None

    def test_parse_torrent_file_no_downloader(self):
        """parse_torrent_file 走本地解析，不依赖下载器"""
        torrent = self._build_torrent(multi_file=True)
        backend = _StubDownloader()
        files = backend.parse_torrent_file(torrent)
        assert len(files) == 2
        # 不应触发下载器操作
        assert backend.add_called == []
