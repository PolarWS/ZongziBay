"""
Bangumi 服务单元测试（mock HTTP）
覆盖：get_calendar、get_season、get_subject、_pick_image、_weekday_from_date
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from app.services.bangumi_service import BangumiService, _api_base


# ---------------------------------------------------------------------------
# 共享的 mock 数据
# ---------------------------------------------------------------------------

def _make_calendar_response():
    """构造 /calendar 的示例响应"""
    return [
        {
            "weekday": {"id": 1, "cn": "星期一", "en": "Mon", "ja": "月曜日"},
            "items": [
                {
                    "id": 1001,
                    "name": "テストアニメ",
                    "name_cn": "测试动画",
                    "air_date": "2026-07-18",
                    "air_weekday": 1,
                    "images": {"large": "https://img.example/1001_l.jpg", "common": "https://img.example/1001_c.jpg"},
                    "rating": {"score": 7.5, "total": 100},
                    "rank": 500,
                    "collection": {"doing": 1000},
                    "url": "https://bgm.tv/subject/1001",
                },
                {
                    "id": 1002,
                    "name": "Another Anime",
                    "name_cn": "",
                    "air_date": "2026-07-18",
                    "air_weekday": 1,
                    "images": {},
                    "rating": {},
                    "rank": None,
                    "collection": {"doing": 50},
                    "url": "https://bgm.tv/subject/1002",
                },
            ],
        },
        {
            "weekday": {"id": 2, "cn": "星期二", "en": "Tue", "ja": "火曜日"},
            "items": [],
        },
    ]


def _make_season_page(total: int, offset: int, items: list):
    """构造分页响应"""
    return {
        "data": items,
        "total": total,
        "limit": 50,
        "offset": offset,
    }


def _make_season_item(sid: int, name: str, date: str, platform: str = "TV"):
    return {
        "id": sid,
        "name": name,
        "name_cn": f"中文{sid}",
        "date": date,
        "platform": platform,
        "images": {"common": f"https://img.example/{sid}.jpg"},
        "rating": {"score": float(sid % 10), "total": sid * 10},
        "rank": sid,
        "collection": {"doing": sid * 5},
    }


def _make_subject_detail():
    return {
        "id": 1001,
        "name": "テストアニメ",
        "name_cn": "测试动画",
        "summary": "这是一部测试动画",
        "date": "2026-07-01",
        "platform": "TV",
        "eps": 12,
        "total_episodes": 12,
        "images": {
            "large": "https://img.example/1001_l.jpg",
            "common": "https://img.example/1001_c.jpg",
            "medium": "https://img.example/1001_m.jpg",
            "small": "https://img.example/1001_s.jpg",
        },
        "rating": {"score": 7.5, "total": 100, "rank": 500},
        "tags": [
            {"name": "科幻", "count": 50},
            {"name": "原创", "count": 30},
        ],
    }


# ---------------------------------------------------------------------------
# _pick_image 测试
# ---------------------------------------------------------------------------

class TestPickImage:
    """_pick_image：从 images dict 按优先级选择封面"""

    def test_prefer_large(self):
        svc = BangumiService()
        images = {"large": "L", "common": "C", "medium": "M", "small": "S", "grid": "G"}
        assert svc._pick_image(images, prefer="large") == "L"

    def test_prefer_common(self):
        svc = BangumiService()
        images = {"large": "L", "common": "C"}
        assert svc._pick_image(images, prefer="common") == "C"

    def test_fallback_when_preferred_missing(self):
        svc = BangumiService()
        images = {"small": "S", "grid": "G"}
        result = svc._pick_image(images, prefer="large")
        assert result == "S"  # large/medium/common 都没有 → small

    def test_empty_images(self):
        svc = BangumiService()
        assert svc._pick_image({}) == ""

    def test_non_dict_returns_empty(self):
        svc = BangumiService()
        assert svc._pick_image(None) == ""
        assert svc._pick_image([]) == ""

    def test_all_missing_returns_first_available(self):
        svc = BangumiService()
        images = {"grid": "G"}
        assert svc._pick_image(images, prefer="large") == "G"


# ---------------------------------------------------------------------------
# _weekday_from_date 测试
# ---------------------------------------------------------------------------

class TestWeekdayFromDate:
    """_weekday_from_date：YYYY-MM-DD → Bangumi 星期 id"""

    def test_known_date(self):
        # 2026-07-20 是周一 (Python weekday=0 → Bangumi=1)
        assert BangumiService._weekday_from_date("2026-07-20") == 1

    def test_sunday(self):
        # 2026-07-19 是周日 (Python weekday=6 → Bangumi=7)
        assert BangumiService._weekday_from_date("2026-07-19") == 7

    def test_null_or_short_returns_none(self):
        assert BangumiService._weekday_from_date(None) is None
        assert BangumiService._weekday_from_date("") is None
        assert BangumiService._weekday_from_date("2026") is None

    def test_invalid_date_returns_none(self):
        assert BangumiService._weekday_from_date("not-a-date") is None
        assert BangumiService._weekday_from_date("2026-13-01") is None


# ---------------------------------------------------------------------------
# get_calendar（mock HTTP）
# ---------------------------------------------------------------------------

class TestGetCalendar:
    """get_calendar：每日放送"""

    @patch("app.services.bangumi_service.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_calendar_response()
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_calendar()

        assert len(result) == 2
        # 第一天：星期一
        assert result[0]["weekday"]["cn"] == "星期一"
        assert len(result[0]["items"]) == 2
        assert result[0]["items"][0]["id"] == 1001
        assert result[0]["items"][0]["score"] == 7.5
        assert result[0]["items"][0]["image"] == "https://img.example/1001_l.jpg"
        # 无 image 的条目
        assert result[0]["items"][1]["image"] == ""
        # 第二天：星期二，空
        assert result[1]["weekday"]["cn"] == "星期二"
        assert result[1]["items"] == []

    @patch("app.services.bangumi_service.requests.get")
    def test_non_list_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"error": "something"}
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_calendar()
        assert result == []

    @patch("app.services.bangumi_service.requests.get")
    def test_http_error_raises(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.RequestException("timeout")

        svc = BangumiService()
        with pytest.raises(req_lib.RequestException):
            svc.get_calendar()


# ---------------------------------------------------------------------------
# get_season（mock HTTP 分页）
# ---------------------------------------------------------------------------

class TestGetSeason:
    """get_season：历史季度动画"""

    @patch("app.services.bangumi_service.requests.get")
    def test_single_page_no_pagination(self, mock_get):
        items = [_make_season_item(1, "Anime A", "2026-01-05"), _make_season_item(2, "Anime B", "2026-01-12")]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_season_page(2, 0, items)
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_season(2026, "winter")

        # 应返回 7 天（周一~周日）
        assert len(result) == 7
        # 条目按星期分组
        all_items = []
        for day in result:
            all_items.extend(day["items"])
        assert len(all_items) == 2

    @patch("app.services.bangumi_service.requests.get")
    def test_pagination_across_pages(self, mock_get):
        """单月的两页数据能正确合并（_fetch_subjects_month 内部分页）"""
        page1 = [_make_season_item(i, f"Anime {i}", "2026-01-01") for i in range(1, 51)]
        page2 = [_make_season_item(i, f"Anime {i}", "2026-01-01") for i in range(51, 81)]

        resp1 = MagicMock()
        resp1.raise_for_status = MagicMock()
        resp1.json.return_value = _make_season_page(80, 0, page1)

        resp2 = MagicMock()
        resp2.raise_for_status = MagicMock()
        resp2.json.return_value = _make_season_page(80, 50, page2)

        # 三月的 mock（都返回空，只测单月分页）
        empty_resp = MagicMock()
        empty_resp.raise_for_status = MagicMock()
        empty_resp.json.return_value = _make_season_page(0, 0, [])

        mock_get.side_effect = [resp1, resp2, empty_resp, empty_resp]

        svc = BangumiService()
        result = svc.get_season(2026, "winter")

        all_items = []
        for day in result:
            all_items.extend(day["items"])
        # 80 条来自月份 1
        assert len(all_items) == 80

    @patch("app.services.bangumi_service.requests.get")
    def test_non_tv_web_filtered(self, mock_get):
        """非 TV/WEB 平台条目被过滤"""
        items = [
            _make_season_item(1, "TV Show", "2026-01-01", "TV"),
            _make_season_item(2, "OVA", "2026-01-01", "OVA"),
            _make_season_item(3, "Movie", "2026-01-01", "MOVIE"),
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_season_page(3, 0, items)
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_season(2026, "winter")

        all_items = []
        for day in result:
            all_items.extend(day["items"])
        # 仅 TV 保留
        assert len(all_items) == 1
        assert all_items[0]["id"] == 1

    @patch("app.services.bangumi_service.requests.get")
    def test_duplicate_ids_deduplicated(self, mock_get):
        items = [_make_season_item(1, "Anime X", "2026-01-01"), _make_season_item(1, "Anime X", "2026-02-01")]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_season_page(2, 0, items)
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_season(2026, "winter")

        all_items = []
        for day in result:
            all_items.extend(day["items"])
        assert len(all_items) == 1

    def test_invalid_season_raises(self):
        svc = BangumiService()
        with pytest.raises(ValueError, match="无效季节"):
            svc.get_season(2026, "invalid")

    def test_invalid_year_raises(self):
        svc = BangumiService()
        with pytest.raises(ValueError, match="无效年份"):
            svc.get_season(1900, "summer")

    @patch("app.services.bangumi_service.requests.get")
    def test_unknown_weekday_items_appended(self, mock_get):
        """无首播日的条目归入「日期未定」"""
        items = [_make_season_item(1, "TBD Anime", "")]  # 无日期
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_season_page(1, 0, items)
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_season(2026, "winter")

        # 最后一个元素是「日期未定」
        unknown = result[-1]
        assert unknown["weekday"]["id"] == 0
        assert unknown["weekday"]["cn"] == "日期未定"
        assert len(unknown["items"]) == 1

    def test_all_four_seasons_accepted(self):
        svc = BangumiService()
        for season in ("winter", "spring", "summer", "autumn"):
            with patch("app.services.bangumi_service.requests.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json.return_value = _make_season_page(0, 0, [])
                mock_get.return_value = mock_resp
                result = svc.get_season(2026, season)
                assert len(result) == 7  # 没有「日期未定」分类时仅 7 天


# ---------------------------------------------------------------------------
# get_subject（mock HTTP）
# ---------------------------------------------------------------------------

class TestGetSubject:
    """get_subject：条目详情"""

    @patch("app.services.bangumi_service.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_subject_detail()
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_subject(1001)

        assert result["id"] == 1001
        assert result["name"] == "テストアニメ"
        assert result["summary"] == "这是一部测试动画"
        assert result["image"] == "https://img.example/1001_l.jpg"
        assert result["score"] == 7.5
        assert len(result["tags"]) == 2
        assert result["tags"][0]["name"] == "科幻"
        assert result["url"] == "https://bgm.tv/subject/1001"

    @patch("app.services.bangumi_service.requests.get")
    def test_empty_tags(self, mock_get):
        detail = _make_subject_detail()
        detail["tags"] = []
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = detail
        mock_get.return_value = mock_resp

        svc = BangumiService()
        result = svc.get_subject(1001)
        assert result["tags"] == []

    @patch("app.services.bangumi_service.requests.get")
    def test_http_error_raises(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.RequestException("timeout")
        svc = BangumiService()
        with pytest.raises(req_lib.RequestException):
            svc.get_subject(1001)


# ---------------------------------------------------------------------------
# _api_base 配置
# ---------------------------------------------------------------------------

class TestApiBase:
    """_api_base：从配置读取 API 地址"""

    def test_default(self):
        with patch("app.services.bangumi_service.config") as mock_cfg:
            mock_cfg.get.return_value = None
            assert _api_base() == "https://api.bgm.tv"

    def test_custom(self):
        with patch("app.services.bangumi_service.config") as mock_cfg:
            mock_cfg.get.return_value = "https://mirror.bgm.tv"
            assert _api_base() == "https://mirror.bgm.tv"
