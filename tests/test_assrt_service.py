"""
ASSRT 字幕服务单元测试（mock HTTP）
覆盖：搜索、详情、相似字幕、配额、错误处理、URL 解析
不依赖真实 ASSRT API 或数据库
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.assrt_service import (
    AssrtService,
    _raise_if_error,
    _resolve_download_path,
    _choose_subtitle_download_relative_by_target,
    ASSRT_ERROR_MESSAGES,
)
from app.schemas.base import BusinessException
from app.schemas.assrt import AssrtSubItem, AssrtSubDetail


# ---------------------------------------------------------------------------
# _resolve_download_path
# ---------------------------------------------------------------------------

class TestResolveDownloadPath:
    """_resolve_download_path：相对路径解析为本机路径"""

    def test_absolute_path_unchanged(self, tmp_path):
        result = _resolve_download_path(str(tmp_path))
        assert result == str(tmp_path)

    def test_relative_with_root_path(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.return_value = {"root_path": "/data"}
            result = _resolve_download_path("/downloads")
            assert result.replace("\\", "/") == "/data/downloads"

    def test_empty_returns_empty(self):
        assert _resolve_download_path("") == ""
        assert _resolve_download_path(None) == ""

    def test_tilde_expansion(self):
        import os
        result = _resolve_download_path("~/downloads")
        expected = os.path.normpath(os.path.expanduser("~/downloads"))
        assert os.path.normpath(result) == expected


# ---------------------------------------------------------------------------
# _choose_subtitle_download_relative_by_target
# ---------------------------------------------------------------------------

class TestChooseSubtitleDownloadRelative:
    """_choose_subtitle_download_relative_by_target：按目标路径选下载目录"""

    def test_movie_target(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.return_value = {
                "movie_target_path": "/nas/movies",
                "movie_download_path": "/dl/movies",
            }
            rel = _choose_subtitle_download_relative_by_target("/nas/movies")
            assert rel == "/dl/movies"

    def test_tv_target(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.return_value = {
                "tv_target_path": "/nas/tv",
                "tv_download_path": "/dl/tv",
            }
            rel = _choose_subtitle_download_relative_by_target("/nas/tv")
            assert rel == "/dl/tv"

    def test_anime_target(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.return_value = {
                "anime_target_path": "/nas/anime",
                "anime_download_path": "/dl/anime",
            }
            rel = _choose_subtitle_download_relative_by_target("/nas/anime")
            assert rel == "/dl/anime"

    def test_unknown_target_defaults(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.return_value = {"default_download_path": "/temp"}
            rel = _choose_subtitle_download_relative_by_target("/unknown")
            assert rel == "/temp"

    def test_empty_target(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.return_value = {"default_download_path": "/temp"}
            rel = _choose_subtitle_download_relative_by_target(None)
            assert rel == "/temp"


# ---------------------------------------------------------------------------
# _raise_if_error
# ---------------------------------------------------------------------------

class TestRaiseIfError:
    """_raise_if_error：ASSRT 错误码 → BusinessException"""

    def test_status_0_no_error(self):
        _raise_if_error({"status": 0})  # 不抛异常

    def test_known_error_code(self):
        with pytest.raises(BusinessException) as exc:
            _raise_if_error({"status": 101})
        assert "101" in exc.value.message or "搜索" in exc.value.message

    def test_unknown_error_code(self):
        with pytest.raises(BusinessException):
            _raise_if_error({"status": 99999})

    def test_client_error_range(self):
        """20000-29999 → PARAMS_ERROR"""
        with pytest.raises(BusinessException) as exc:
            _raise_if_error({"status": 20001})
        assert exc.value.code == 40000

    def test_server_error_range(self):
        """30000+ → SYSTEM_ERROR"""
        with pytest.raises(BusinessException) as exc:
            _raise_if_error({"status": 30000})
        assert exc.value.code == 50000


# ---------------------------------------------------------------------------
# AssrtService: is_available / 配置
# ---------------------------------------------------------------------------

class TestAssrtServiceAvailability:
    """is_available：Token 长度 >= 32 时可用"""

    def test_available_with_long_token(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.side_effect = lambda key, default=None: {
                "subtitle.assrt.token": "x" * 32,
                "subtitle.assrt.base_url": "https://api.assrt.net",
            }.get(key, default)
            svc = AssrtService()
            svc.reload_config()
            assert svc.is_available() is True

    def test_not_available_with_short_token(self):
        with patch("app.services.assrt_service.config") as mock_cfg:
            mock_cfg.get.side_effect = lambda key, default=None: {
                "subtitle.assrt.token": "short",
                "subtitle.assrt.base_url": "https://api.assrt.net",
            }.get(key, default)
            svc = AssrtService()
            svc.reload_config()
            assert svc.is_available() is False

    def test_not_available_with_empty_token(self):
        svc = AssrtService()
        svc._token = ""
        assert svc.is_available() is False

    def test_request_when_unavailable(self):
        svc = AssrtService()
        svc._token = ""
        with pytest.raises(BusinessException, match="未配置"):
            svc._request("/test")


# ---------------------------------------------------------------------------
# search_subs（mock HTTP）
# ---------------------------------------------------------------------------

class TestSearchSubs:
    """search_subs：搜索字幕"""

    def _make_search_response(self, items=None):
        return {
            "status": 0,
            "sub": {
                "subs": items or [
                    {
                        "id": 12345,
                        "native_name": "Test.S01E01.1080p.WEB-DL",
                        "revision": 1,
                        "subtype": "srt",
                        "upload_time": "2026-07-18",
                        "vote_score": 100,
                        "release_site": "NETFLIX",
                        "videoname": "Test S01E01",
                        "lang": {"langlist": {"chn": 1}, "desc": "简体中文"},
                    },
                    {
                        "id": 12346,
                        "native_name": "Test.S01E01.720p.HDTV",
                        "revision": 2,
                        "subtype": "ass",
                        "upload_time": "2026-07-17",
                        "vote_score": 50,
                        "release_site": "AMZN",
                        "videoname": "Test S01E01",
                        "lang": {"langlist": {"chs": 1, "eng": 1}, "desc": "简英双语"},
                    },
                ]
            }
        }

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_basic_search(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = self._make_search_response()
        mock_get.return_value = mock_resp

        svc = AssrtService()
        items, total = svc.search_subs("Test S01E01")

        assert len(items) == 2
        assert items[0].id == 12345
        assert items[0].native_name == "Test.S01E01.1080p.WEB-DL"
        assert total == 2

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_search_keyword_too_short(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)

        svc = AssrtService()
        with pytest.raises(BusinessException, match="长度"):
            svc.search_subs("ab")

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_search_empty_results(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": 0, "sub": {"subs": []}}
        mock_get.return_value = mock_resp

        svc = AssrtService()
        items, total = svc.search_subs("不存在的内容")
        assert items == []
        assert total == 0

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_search_with_is_file_and_no_muxer(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = self._make_search_response()
        mock_get.return_value = mock_resp

        svc = AssrtService()
        items, total = svc.search_subs("Test Show", is_file=True, no_muxer=True)

        # 验证参数被传递
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params.get("is_file") == 1
        assert params.get("no_muxer") == 1


# ---------------------------------------------------------------------------
# get_sub_detail（mock HTTP）
# ---------------------------------------------------------------------------

class TestGetSubDetail:
    """get_sub_detail：字幕详情"""

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_success(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": 0,
            "sub": {
                "subs": [{
                    "id": 12345,
                    "native_name": "Test.S01E01",
                    "filename": "test.srt",
                    "size": 50000,
                    "url": "https://sub.example.com/test.srt",
                    "vote_score": 100,
                    "filelist": [{"url": "https://sub.example.com/test.srt", "f": "test.srt", "s": "50KB"}],
                    "producer": {"uploader": "user1", "verifier": "mod1"},
                }]
            }
        }
        mock_get.return_value = mock_resp

        svc = AssrtService()
        detail = svc.get_sub_detail(12345)

        assert isinstance(detail, AssrtSubDetail)
        assert detail.id == 12345
        assert detail.native_name == "Test.S01E01"
        assert detail.url == "https://sub.example.com/test.srt"

    def test_invalid_id(self):
        svc = AssrtService()
        svc._token = "x" * 32
        with pytest.raises(BusinessException):
            svc.get_sub_detail(0)
        with pytest.raises(BusinessException):
            svc.get_sub_detail(-1)
        with pytest.raises(BusinessException):
            svc.get_sub_detail(10**8)

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_not_found(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": 0, "sub": {"subs": []}}
        mock_get.return_value = mock_resp

        svc = AssrtService()
        with pytest.raises(BusinessException, match="不存在"):
            svc.get_sub_detail(999999)


# ---------------------------------------------------------------------------
# get_similar_subs（mock HTTP）
# ---------------------------------------------------------------------------

class TestGetSimilarSubs:
    """get_similar_subs：相似字幕"""

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_success(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": 0,
            "sub": {
                "subs": [
                    {"id": 20001, "native_name": "Similar Sub 1", "revision": 1,
                     "subtype": "srt", "upload_time": "2026-01-01", "vote_score": 80},
                ]
            }
        }
        mock_get.return_value = mock_resp

        svc = AssrtService()
        items = svc.get_similar_subs(12345)

        assert len(items) == 1
        assert items[0].id == 20001


# ---------------------------------------------------------------------------
# get_quota（mock HTTP）
# ---------------------------------------------------------------------------

class TestGetQuota:
    """get_quota：API 配额"""

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_success(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": 0, "user": {"quota": 100}}
        mock_get.return_value = mock_resp

        svc = AssrtService()
        quota = svc.get_quota()
        assert quota == 100

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_default_zero(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": 0, "user": {}}
        mock_get.return_value = mock_resp

        svc = AssrtService()
        quota = svc.get_quota()
        assert quota == 0


# ---------------------------------------------------------------------------
# HTTP 错误码处理
# ---------------------------------------------------------------------------

class TestAssrtHTTPErrors:
    """HTTP 错误响应处理"""

    @patch("app.services.assrt_service.config")
    def test_509_rate_limit(self, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        import requests as req_lib
        mock_resp = MagicMock()
        mock_resp.status_code = 509
        http_err = req_lib.HTTPError(response=mock_resp)

        svc = AssrtService()
        with patch("app.services.assrt_service.requests.get") as mock_get:
            mock_get.side_effect = http_err
            with pytest.raises(BusinessException, match="509"):
                svc._request("/test")

    @patch("app.services.assrt_service.config")
    def test_429_rate_limit(self, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "https://api.assrt.net",
        }.get(key, default)
        import requests as req_lib
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        http_err = req_lib.HTTPError(response=mock_resp)

        svc = AssrtService()
        with patch("app.services.assrt_service.requests.get") as mock_get:
            mock_get.side_effect = http_err
            with pytest.raises(BusinessException, match="429"):
                svc._request("/test")


# ---------------------------------------------------------------------------
# ASSRT_ERROR_MESSAGES 字典
# ---------------------------------------------------------------------------

class TestAssrtErrorMessages:
    """ASSRT_ERROR_MESSAGES：错误码映射"""

    def test_known_codes(self):
        assert ASSRT_ERROR_MESSAGES[1] == "用户不存在"
        assert ASSRT_ERROR_MESSAGES[101] == "搜索关键词长度必须大于3"
        assert ASSRT_ERROR_MESSAGES[20001] == "Token不存在或无效"
        assert ASSRT_ERROR_MESSAGES[30000] == "服务器异常"
        assert ASSRT_ERROR_MESSAGES[30900] == "请求配额超限"
