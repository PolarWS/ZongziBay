"""
动漫花园服务单元测试（mock HTTP）
覆盖：get_teams、search（关键字、分页、字幕组筛选）
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.anime_garden_service import AnimeGardenService


def _make_teams_response():
    return {
        "status": "ok",
        "teams": [
            {"id": 1, "provider": "dmhy", "providerId": "101", "name": "桜都字幕组", "avatar": ""},
            {"id": 2, "provider": "dmhy", "providerId": "102", "name": "LoliHouse", "avatar": ""},
        ]
    }


def _make_search_response():
    return {
        "status": "ok",
        "complete": True,
        "resources": [
            {
                "id": 12345,
                "provider": "dmhy",
                "providerId": "12345",
                "title": "[桜都字幕组] 测试动画 / Test Anime [01][1080p][简繁内封]",
                "href": "https://example.com/torrent/12345",
                "magnet": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "size": 1258291,
                "type": "動畫",
                "createdAt": "2026-07-18T12:00:00Z",
                "fetchedAt": "2026-07-18T12:05:00Z",
                "publisher": {"id": 1, "name": "桜都字幕组"},
                "fansub": {"id": 1, "name": "桜都字幕组"},
            },
            {
                "id": 12346,
                "provider": "dmhy",
                "providerId": "12346",
                "title": "[LoliHouse] 另一个动画 / Another Anime [02][1080p]",
                "href": "https://example.com/torrent/12346",
                "magnet": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef13",
                "size": 838860,
                "type": "動畫",
                "createdAt": "2026-07-18T10:00:00Z",
                "fetchedAt": "2026-07-18T10:05:00Z",
                "publisher": {"id": 2, "name": "LoliHouse"},
                "fansub": {"id": 2, "name": "LoliHouse"},
            },
        ],
        "pagination": {"page": 1, "pageSize": 20, "complete": True},
        "filter": {},
        "timestamp": "2026-07-18T12:00:00Z",
    }


# ---------------------------------------------------------------------------
# get_teams
# ---------------------------------------------------------------------------

class TestGetTeams:
    """get_teams：字幕组列表"""

    @patch("app.services.anime_garden_service.requests.get")
    @patch("app.services.anime_garden_service.config")
    def test_success(self, mock_config, mock_get):
        mock_config.get.return_value = "https://animes.garden/api/resources"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_teams_response()
        mock_get.return_value = mock_resp

        svc = AnimeGardenService()
        teams = svc.get_teams()

        assert len(teams) == 2
        assert teams[0]["name"] == "桜都字幕组"
        assert teams[1]["name"] == "LoliHouse"

    @patch("app.services.anime_garden_service.requests.get")
    def test_http_error_raises(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.RequestException("timeout")

        svc = AnimeGardenService()
        with pytest.raises(req_lib.RequestException):
            svc.get_teams()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    """search：按关键字搜索"""

    @patch("app.services.anime_garden_service.requests.get")
    @patch("app.services.anime_garden_service.config")
    def test_basic_search(self, mock_config, mock_get):
        mock_config.get.return_value = "https://animes.garden/api/resources"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_search_response()
        mock_get.return_value = mock_resp

        svc = AnimeGardenService()
        result = svc.search("测试动画")

        assert result["status"] == "ok"
        assert len(result["resources"]) == 2
        assert result["pagination"]["complete"] is True

    @patch("app.services.anime_garden_service.requests.get")
    @patch("app.services.anime_garden_service.config")
    def test_search_with_fansub_filter(self, mock_config, mock_get):
        mock_config.get.return_value = "https://animes.garden/api/resources"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_search_response()
        mock_get.return_value = mock_resp

        svc = AnimeGardenService()
        result = svc.search("测试", fansub="桜都字幕组")

        # 验证 fansub 参数被传递
        call_args = mock_get.call_args
        assert "fansub" in str(call_args) or "桜都字幕组" in str(call_args)

    @patch("app.services.anime_garden_service.requests.get")
    @patch("app.services.anime_garden_service.config")
    def test_search_with_pagination(self, mock_config, mock_get):
        mock_config.get.return_value = "https://animes.garden/api/resources"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_search_response()
        mock_get.return_value = mock_resp

        svc = AnimeGardenService()
        result = svc.search("test", page=2, page_size=10)
        assert result["pagination"]["page"] == 1  # 原始 API 返回的 page

    @patch("app.services.anime_garden_service.requests.get")
    @patch("app.services.anime_garden_service.config")
    def test_empty_search_results(self, mock_config, mock_get):
        mock_config.get.return_value = "https://animes.garden/api/resources"
        empty = {
            "status": "ok",
            "complete": True,
            "resources": [],
            "pagination": {"page": 1, "pageSize": 20, "complete": True},
            "filter": {},
            "timestamp": "2026-07-18T12:00:00Z",
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = empty
        mock_get.return_value = mock_resp

        svc = AnimeGardenService()
        result = svc.search("不存在的动画")
        assert len(result["resources"]) == 0
        assert result["pagination"]["complete"] is True

    @patch("app.services.anime_garden_service.requests.get")
    def test_http_error_raises(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.RequestException("timeout")

        svc = AnimeGardenService()
        with pytest.raises(req_lib.RequestException):
            svc.search("test")
