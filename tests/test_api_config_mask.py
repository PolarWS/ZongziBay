"""
配置脱敏测试
覆盖：_mask_sensitive_keys / _restore_masked_keys 对 downloader 节
（Transmission password / Aria2 secret）的脱敏与恢复
"""
from unittest.mock import patch

from app.api.v1.system import _mask_sensitive_keys, _restore_masked_keys


def _full_config():
    return {
        "downloader": {
            "active": "transmission",
            "transmission": {"host": "http://t:9091", "username": "admin", "password": "secret123"},
            "aria2": {"host": "http://a:6800", "secret": "rpcsecret"},
        },
        "qbittorrent": {"host": "http://q:8080", "password": "qbpass", "api_key": "qbak"},
        "security": {"password": "hash123"},
        "tmdb": {"api_key": "tmdbkey"},
    }


class TestMaskSensitiveKeys:
    """_mask_sensitive_keys：脱敏 downloader 节敏感字段"""

    def test_masks_transmission_password(self):
        masked = _mask_sensitive_keys(_full_config())
        assert masked["downloader"]["transmission"]["password"] == "****"

    def test_masks_aria2_secret(self):
        masked = _mask_sensitive_keys(_full_config())
        assert masked["downloader"]["aria2"]["secret"] == "****"

    def test_keeps_non_sensitive_downloader_fields(self):
        masked = _mask_sensitive_keys(_full_config())
        assert masked["downloader"]["active"] == "transmission"
        assert masked["downloader"]["transmission"]["host"] == "http://t:9091"
        assert masked["downloader"]["transmission"]["username"] == "admin"

    def test_masks_qb_and_security(self):
        masked = _mask_sensitive_keys(_full_config())
        assert masked["qbittorrent"]["password"] == "****"
        assert masked["qbittorrent"]["api_key"] == "****"
        assert masked["security"]["password"] == "****"

    def test_empty_downloader_no_crash(self):
        masked = _mask_sensitive_keys({})
        assert masked == {}

    def test_no_secret_no_mask(self):
        cfg = {"downloader": {"aria2": {"host": "http://a:6800", "secret": ""}}}
        masked = _mask_sensitive_keys(cfg)
        assert masked["downloader"]["aria2"]["secret"] == ""


class TestRestoreMaskedKeys:
    """_restore_masked_keys：恢复 downloader 节脱敏值"""

    def _existing_config(self):
        return {
            "downloader": {
                "transmission": {"password": "real-trans-pass"},
                "aria2": {"secret": "real-aria-secret"},
            },
            "qbittorrent": {"password": "real-qb-pass", "api_key": "real-qb-key"},
        }

    def test_restores_transmission_password(self):
        body = {"downloader": {"transmission": {"password": "****"}}}
        with patch("app.api.v1.system.config") as mc:
            mc.get_file_config.return_value = self._existing_config()
            restored = _restore_masked_keys(body)
        assert restored["downloader"]["transmission"]["password"] == "real-trans-pass"

    def test_restores_aria2_secret(self):
        body = {"downloader": {"aria2": {"secret": "****"}}}
        with patch("app.api.v1.system.config") as mc:
            mc.get_file_config.return_value = self._existing_config()
            restored = _restore_masked_keys(body)
        assert restored["downloader"]["aria2"]["secret"] == "real-aria-secret"

    def test_keeps_real_values_when_not_masked(self):
        body = {"downloader": {"aria2": {"secret": "new-secret"}}}
        with patch("app.api.v1.system.config") as mc:
            mc.get_file_config.return_value = self._existing_config()
            restored = _restore_masked_keys(body)
        assert restored["downloader"]["aria2"]["secret"] == "new-secret"

    def test_keeps_blank_when_no_existing(self):
        body = {"downloader": {"aria2": {"secret": "****"}}}
        with patch("app.api.v1.system.config") as mc:
            mc.get_file_config.return_value = {}  # 无历史值
            restored = _restore_masked_keys(body)
        assert restored["downloader"]["aria2"]["secret"] == "****"

    def test_strips_whitespace_and_trailing_slash_from_hosts(self):
        """设置页粘贴地址常带首尾空格，落库前统一清理"""
        body = {
            "downloader": {
                "transmission": {"host": "  http://t:9091/  "},
                "aria2": {"host": " http://a:6800 "},
            },
            "qbittorrent": {"host": "  http://q:8080/ "},
        }
        with patch("app.api.v1.system.config") as mc:
            mc.get_file_config.return_value = self._existing_config()
            restored = _restore_masked_keys(body)
        assert restored["downloader"]["transmission"]["host"] == "http://t:9091"
        assert restored["downloader"]["aria2"]["host"] == "http://a:6800"
        assert restored["qbittorrent"]["host"] == "http://q:8080"
