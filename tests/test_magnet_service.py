"""
磁力服务单元测试：normalize_info_hash、tracker 追加
不依赖 qBittorrent 或网络
"""
import pytest
from unittest.mock import patch

from app.services.magnet_service import normalize_info_hash, MagnetService


class TestNormalizeInfoHash:
    """normalize_info_hash：40 位 hex / 32 位 Base32 转 40 位小写 hex"""

    def test_40_lowercase(self):
        assert normalize_info_hash("a" * 40) == "a" * 40

    def test_40_uppercase(self):
        assert normalize_info_hash("A" * 40) == "a" * 40

    def test_32_base32_to_hex(self):
        # 32 位 Base32 会按 b32decode 转 hex；典型 40 位 hex 的前 32 位 base32 编码
        # 简单用例：已知 Base32 "JQ6YIR2R4E3V3E2T6Y6M4S2R2E3V3E2T" 等
        out = normalize_info_hash("a" * 32)
        assert len(out) == 40
        assert all(c in "0123456789abcdef" for c in out)

    def test_32_invalid_base32_returns_lower(self):
        # 非合法 Base32 时保留原样并 lower
        raw = "0O1I" * 8  # 32 字符但可能 b32decode 失败
        out = normalize_info_hash(raw)
        assert out == raw.lower() or len(out) == 40

    def test_empty_strip(self):
        assert normalize_info_hash("  abcdef" + "0" * 32) != ""


class TestMagnetServiceAppendTrackers:
    """MagnetService._append_trackers：在磁链后追加 tracker"""

    def _config_get(self, trackers):
        def get(key, default=None):
            if key == "trackers":
                return trackers
            if key == "qbittorrent":
                return {}
            return default
        return get

    @patch("app.services.magnet_service.config")
    def test_no_trackers_unchanged(self, mock_config):
        mock_config.get.side_effect = self._config_get([])
        svc = MagnetService()
        link = "magnet:?xt=urn:btih:abc"
        assert svc._append_trackers(link) == link

    @patch("app.services.magnet_service.config")
    def test_with_trackers_appended(self, mock_config):
        mock_config.get.side_effect = self._config_get(["https://tracker.example/announce"])
        svc = MagnetService()
        link = "magnet:?xt=urn:btih:abc123"
        result = svc._append_trackers(link)
        assert result.startswith(link)
        assert "tr=" in result

    @patch("app.services.magnet_service.config")
    def test_empty_link_returns_empty(self, mock_config):
        mock_config.get.side_effect = self._config_get(["https://t.com"])
        svc = MagnetService()
        assert svc._append_trackers("") == ""
