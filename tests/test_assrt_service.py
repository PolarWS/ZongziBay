"""
ASSRT 字幕服务单元测试（mock HTTP）
覆盖：搜索、详情、相似字幕、配额、错误处理、URL 解析
不依赖真实 ASSRT API 或数据库
"""
import os
import ssl

import pytest
import requests
from unittest.mock import MagicMock, patch

from app.services.assrt_service import (
    AssrtService,
    _friendly_net_error,
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


# ---------------------------------------------------------------------------
# 旧版 assrt 接口字段兼容（镜像站如 api.makedie.me 仍返回旧版字段）
# ---------------------------------------------------------------------------

class TestLegacyFormatCompat:
    """旧版字段（fileid/m_subtype/m_langn）应被正确映射为新版字段。

    回归背景：部分可用镜像返回的是旧版结构，缺少 id/native_name/upload_time，
    旧实现直接按 s.get("id") 过滤，导致搜索结果恒为 0 条。
    """

    @staticmethod
    def _legacy_item():
        """一条真实旧版响应样例（字段截取自 api.makedie.me）。"""
        return {
            "videoname": "Show.S01E01.1080p.WEB-GRACE",
            "video_chinese_name": "剧名/第一集",
            "revision": "0",
            "uploadtime": "2026-09-18 07:59:54",
            "fileid": "801535",
            "subtype": "2",
            "m_subtype": "Subrip(srt)",
            "m_title_bot": "剧名 第一集",
            "m_lang": "英&nbsp;简&nbsp;繁&nbsp;双语",
            "m_langn": ["langeng", "langchs", "langcht", "langdou"],
            "m_extras": {"langeng": "1", "langchs": "1", "langcht": "1", "langdou": "1"},
            "score": "7",
            "score_cnt": "0",
        }

    @patch("app.services.assrt_service.config")
    @patch("app.services.assrt_service.requests.get")
    def test_legacy_item_is_parsed(self, mock_get, mock_config):
        mock_config.get.side_effect = lambda key, default=None: {
            "subtitle.assrt.token": "x" * 32,
            "subtitle.assrt.base_url": "http://api.makedie.me",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": 0, "sub": {"subs": [self._legacy_item()]}}
        mock_get.return_value = mock_resp

        items, total = AssrtService().search_subs("Test S01E01")

        assert total == 1
        item = items[0]
        # fileid -> id
        assert item.id == 801535
        # m_title_bot -> native_name
        assert item.native_name == "剧名 第一集"
        # uploadtime -> upload_time
        assert item.upload_time == "2026-09-18 07:59:54"
        # m_subtype 优先于数字代号 subtype
        assert item.subtype == "Subrip(srt)"
        # score -> vote_score
        assert item.vote_score == 7
        # m_langn + m_extras -> lang.langlist
        assert item.lang is not None
        assert item.lang.langlist.langchs is True
        assert item.lang.langlist.langeng is True
        assert item.lang.langlist.langcht is True
        assert item.lang.langlist.langdou is True
        # m_lang -> desc（含 &nbsp; 原样保留）
        assert "英" in item.lang.desc

    def test_legacy_item_without_valid_fileid_is_skipped(self):
        from app.services.assrt_service import _has_sub_id

        assert _has_sub_id({"fileid": "801535"}) is True
        assert _has_sub_id({"id": 123}) is True
        assert _has_sub_id({"fileid": ""}) is False
        assert _has_sub_id({"fileid": "abc"}) is False
        assert _has_sub_id({"fileid": None}) is False
        assert _has_sub_id("not-a-dict") is False

    def test_new_format_is_not_rewritten(self):
        """新版响应必须原样通过，不能被兼容逻辑改动。"""
        from app.services.assrt_service import _normalize_sub_raw

        raw = {
            "id": 999,
            "native_name": "New.Format",
            "upload_time": "2026-01-01",
            "subtype": "ass",
            "lang": {"langlist": {"langchs": True}, "desc": "简体"},
        }
        out = _normalize_sub_raw(dict(raw))
        assert out["id"] == 999
        assert out["native_name"] == "New.Format"
        assert out["upload_time"] == "2026-01-01"
        assert out["subtype"] == "ass"
        assert out["lang"] == raw["lang"]


# ---------------------------------------------------------------------------
# _friendly_net_error
# ---------------------------------------------------------------------------

class TestFriendlyNetError:
    """原始异常文本不能出现在用户可见的消息里，但结论要能区分原因"""

    def test_ssl_error(self):
        msg = _friendly_net_error(ssl.SSLEOFError(8, "[SSL: UNEXPECTED_EOF_WHILE_READING]"))
        assert "安全连接" in msg
        assert "SSLEOFError" not in msg and "file1.assrt.net" not in msg

    def test_unwraps_nested_cause(self):
        """requests 把真实原因挂在 __cause__ 上，必须剥到最内层"""
        inner = ssl.SSLEOFError(8, "EOF occurred in violation of protocol")
        wrapped = requests.ConnectionError("Max retries exceeded")
        wrapped.__cause__ = inner
        outer = requests.ConnectionError(
            "HTTPSConnectionPool(host='file1.assrt.net', port=443)"
        )
        outer.__cause__ = wrapped
        assert "安全连接" in _friendly_net_error(outer)

    def test_timeout(self):
        assert "超时" in _friendly_net_error(requests.ConnectTimeout("timed out"))
        assert "超时" in _friendly_net_error(requests.ReadTimeout("timed out"))

    def test_connection_error(self):
        assert "无法连接" in _friendly_net_error(
            requests.ConnectionError("Connection refused")
        )

    def test_unknown_falls_back_to_generic(self):
        msg = _friendly_net_error(ValueError("something odd"))
        assert "字幕服务器" in msg
        assert "something odd" not in msg

    def test_none_does_not_raise(self):
        """last_err 理论上可能是 None，不能因此炸掉"""
        assert isinstance(_friendly_net_error(None), str)


# ---------------------------------------------------------------------------
# _download_sub_to_path
# ---------------------------------------------------------------------------

class TestDownloadSubToPath:
    """下载目录不存在时必须先创建。

    缺陷：调用方显式传 download_path 时走 _resolve_download_path，不经过
    _get_subtitle_download_dir_for_target，目录不会被创建，open(..., "wb")
    直接 FileNotFoundError（用户看到「保存失败: [Errno 2] No such file or directory」）。
    """

    def _detail(self):
        return AssrtSubDetail(
            id=173817,
            filename="2010_Sintel.UTF-8.tw.rar",
            url="https://file1.assrt.net/onthefly/173817/-/1/x.rar",
        )

    @patch("app.services.assrt_service.requests.get")
    def test_creates_missing_download_dir(self, mock_get, tmp_path):
        target_dir = tmp_path / "not" / "yet" / "created"
        assert not target_dir.exists()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content.return_value = [b"subtitle-bytes"]
        mock_get.return_value = mock_resp

        saved, filename = AssrtService()._download_sub_to_path(
            self._detail(), 173817, download_dir=str(target_dir)
        )

        assert target_dir.is_dir()
        assert (target_dir / filename).read_bytes() == b"subtitle-bytes"
        assert saved == os.path.abspath(os.path.join(str(target_dir), filename))

    @patch("app.services.assrt_service.requests.get")
    def test_existing_download_dir_untouched(self, mock_get, tmp_path):
        """目录已存在时不应报错，也不该改动已有内容。"""
        existing = tmp_path / "dl"
        existing.mkdir()
        (existing / "keep.txt").write_text("keep", encoding="utf-8")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content.return_value = [b"x"]
        mock_get.return_value = mock_resp

        AssrtService()._download_sub_to_path(
            self._detail(), 173817, download_dir=str(existing)
        )

        assert (existing / "keep.txt").read_text(encoding="utf-8") == "keep"
