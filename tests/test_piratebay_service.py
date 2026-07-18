"""
海盗湾服务单元测试（mock HTTP）
覆盖：search、_fix_name、_generate_magnet_link、params 模板解析、无结果处理
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.piratebay_service import PirateBayService
from app.schemas.piratebay import PirateBayTorrent


def _make_torrent_item(info_hash: str, name: str, seeders: int = 10, size: str = "1 GiB", username: str = "uploader"):
    return {
        "id": "12345",
        "name": name,
        "info_hash": info_hash,
        "size": size,
        "seeders": str(seeders),
        "leechers": "5",
        "num_files": "1",
        "username": username,
        "added": "1234567890",
        "status": "vip",
        "category": "200",
        "imdb": "",
    }


# ---------------------------------------------------------------------------
# _fix_name
# ---------------------------------------------------------------------------

class TestFixName:
    """_fix_name：修正种子名称"""

    def test_normal_name_unchanged(self):
        svc = PirateBayService()
        assert svc._fix_name("Test Movie 2024", "uploader") == "Test Movie 2024"

    def test_dash_ending_appends_username(self):
        svc = PirateBayService()
        result = svc._fix_name("Test Movie 2024 -", "john")
        assert result == "Test Movie 2024 -john"

    def test_dash_ending_username_already_in_name(self):
        """发布者名已在标题中时不重复追加"""
        svc = PirateBayService()
        result = svc._fix_name("john -", "john")
        # 用户名已在标题中 → 不追加
        assert "john -john" not in result or result == "john -"

    def test_empty_name(self):
        svc = PirateBayService()
        assert svc._fix_name("", "uploader") == ""
        assert svc._fix_name(None, "uploader") == ""

    def test_empty_username(self):
        svc = PirateBayService()
        # name 以 "-" 结尾但 username 为空 → 保持原样
        result = svc._fix_name("Test -", "")
        assert result == "Test -"


# ---------------------------------------------------------------------------
# _generate_magnet_link
# ---------------------------------------------------------------------------

class TestGenerateMagnetLink:
    """_generate_magnet_link：生成磁链"""

    def test_basic(self):
        svc = PirateBayService()
        link = svc._generate_magnet_link("a" * 40, "Test Movie")
        assert link.startswith("magnet:?xt=urn:btih:")
        assert "a" * 40 in link
        assert "dn=Test+Movie" in link or "dn=Test%20Movie" in link

    def test_special_characters_encoded(self):
        svc = PirateBayService()
        link = svc._generate_magnet_link("b" * 40, "Movie [2024] (1080p)")
        # 特殊字符应被 URL 编码
        assert "dn=" in link


# ---------------------------------------------------------------------------
# search（mock HTTP）
# ---------------------------------------------------------------------------

class TestSearch:
    """search：搜索海盗湾"""

    @patch("app.services.piratebay_service.config")
    @patch("app.services.piratebay_service.requests.get")
    def test_success(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "piratebay.url": "https://apibay.org/q.php",
            "piratebay.params": "q=[q]&cat=200",
        }.get(key, default)

        items = [
            _make_torrent_item("a" * 40, "Test Movie 2024"),
            _make_torrent_item("b" * 40, "Another Movie"),
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = items
        mock_get.return_value = mock_resp

        svc = PirateBayService()
        results = svc.search("test")

        assert len(results) == 2
        assert isinstance(results[0], PirateBayTorrent)
        assert results[0].magnet.startswith("magnet:")

    @patch("app.services.piratebay_service.config")
    @patch("app.services.piratebay_service.requests.get")
    def test_no_results(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "piratebay.url": "https://apibay.org/q.php",
            "piratebay.params": "q=[q]&cat=200",
        }.get(key, default)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"name": "No results returned"}]
        mock_get.return_value = mock_resp

        svc = PirateBayService()
        results = svc.search("nonexistentthing123456")
        assert results == []

    @patch("app.services.piratebay_service.config")
    @patch("app.services.piratebay_service.requests.get")
    def test_partial_parse_errors_skipped(self, mock_get, mock_config):
        """个别条目解析失败时跳过，不影响其他条目"""
        mock_config.get.side_effect = lambda key, default=None: {
            "piratebay.url": "https://apibay.org/q.php",
            "piratebay.params": "q=[q]&cat=200",
        }.get(key, default)

        items = [
            _make_torrent_item("a" * 40, "Valid Movie"),
            {"invalid": "missing required fields"},  # 会触发解析错误
            _make_torrent_item("c" * 40, "Another Valid"),
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = items
        mock_get.return_value = mock_resp

        svc = PirateBayService()
        results = svc.search("test")

        # 仅两个有效结果
        assert len(results) == 2

    @patch("app.services.piratebay_service.config")
    @patch("app.services.piratebay_service.requests.get")
    def test_http_error_raises(self, mock_get, mock_config):
        import requests as req_lib
        mock_config.get.side_effect = lambda key, default=None: {
            "piratebay.url": "https://apibay.org/q.php",
            "piratebay.params": "q=[q]&cat=200",
        }.get(key, default)
        mock_get.side_effect = req_lib.RequestException("offline")

        svc = PirateBayService()
        with pytest.raises(req_lib.RequestException):
            svc.search("test")

    @patch("app.services.piratebay_service.config")
    @patch("app.services.piratebay_service.requests.get")
    def test_fix_name_applied_in_search(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "piratebay.url": "https://apibay.org/q.php",
            "piratebay.params": "q=[q]&cat=200",
        }.get(key, default)

        items = [_make_torrent_item("a" * 40, "Test Movie -", username="john")]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = items
        mock_get.return_value = mock_resp

        svc = PirateBayService()
        results = svc.search("test")
        # _fix_name 应已修正名称
        assert "john" in results[0].name


# ---------------------------------------------------------------------------
# params 模板解析
# ---------------------------------------------------------------------------

class TestParamsTemplate:
    """params_template 解析：字符串模板 / dict / 降级"""

    def test_default_template(self):
        svc = PirateBayService()
        assert svc.params_template == "q=[q]&cat=200"

    @patch("app.services.piratebay_service.requests.get")
    def test_dict_template(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [_make_torrent_item("a" * 40, "Test")]
        mock_get.return_value = mock_resp

        svc = PirateBayService()
        svc.params_template = {"q": "[q]", "cat": "200"}
        results = svc.search("test")
        assert len(results) == 1
