"""
TMDB 服务单元测试（mock tmdbv3api）
覆盖：search_movies/search_tv_shows、详情、英文标题提取、趋势、热门、建议
"""
import pytest
from unittest.mock import MagicMock, PropertyMock, patch

from app.services.tmdb_service import TMDBService, _attr_or_key


# ---------------------------------------------------------------------------
# _attr_or_key 工具函数
# ---------------------------------------------------------------------------

class TestAttrOrKey:
    """_attr_or_key：从 AsObj 或 dict 中取属性/键值"""

    def test_from_object_attr(self):
        obj = MagicMock()
        obj.title = "Test"
        assert _attr_or_key(obj, "title") == "Test"

    def test_from_dict(self):
        assert _attr_or_key({"name": "Foo"}, "name") == "Foo"

    def test_none_input(self):
        assert _attr_or_key(None, "key") is None

    def test_none_value_returns_none(self):
        obj = MagicMock()
        obj.title = None
        assert _attr_or_key(obj, "title") is None

    def test_empty_string_value(self):
        obj = MagicMock()
        obj.title = ""
        # 空字符串 strip 后为假值 → 返回 None
        assert _attr_or_key(obj, "title") is None


# ---------------------------------------------------------------------------
# _extract_results / _extract_total
# ---------------------------------------------------------------------------

class TestExtractResults:
    """_extract_results：安全提取 tmdbv3api 返回的结果列表"""

    def test_list_direct(self):
        svc = TMDBService()
        assert svc._extract_results([1, 2, 3]) == [1, 2, 3]

    def test_asobj_iterable(self):
        """正常 AsObj 迭代出非字符串对象"""
        mock_raw = MagicMock()
        mock_raw.__iter__.return_value = iter([
            MagicMock(title="Movie A"),
            MagicMock(title="Movie B"),
        ])
        result = svc = TMDBService()._extract_results(mock_raw)
        assert len(result) == 2

    def test_asobj_degraded_to_string_keys(self):
        """AsObj 降级为 dict keys（字符串迭代）"""
        mock_raw = MagicMock()
        mock_raw.__iter__.return_value = iter(["title", "overview"])
        mock_raw.results = [MagicMock(title="Movie X")]
        svc = TMDBService()
        result = svc._extract_results(mock_raw)
        assert len(result) == 1

    def test_exception_returns_empty(self):
        mock_raw = MagicMock()
        mock_raw.__iter__.side_effect = Exception("broken")
        svc = TMDBService()
        assert svc._extract_results(mock_raw) == []

    def test_none_input(self):
        svc = TMDBService()
        # 会变成 list 迭代 None → TypeError → 返回 []
        result = svc._extract_results(None)
        assert result == []


class TestExtractTotal:
    """_extract_total：安全提取 total_results"""

    def test_from_result(self):
        mock_raw = MagicMock()
        mock_raw.total_results = 42
        assert TMDBService._extract_total(mock_raw) == 42

    def test_from_fallback(self):
        mock_raw = MagicMock()
        mock_raw.total_results = None
        mock_fallback = MagicMock()
        mock_fallback.total_results = 99
        assert TMDBService._extract_total(mock_raw, mock_fallback) == 99

    def test_none_returns_zero(self):
        mock_raw = MagicMock()
        mock_raw.total_results = None
        assert TMDBService._extract_total(mock_raw) == 0


# ---------------------------------------------------------------------------
# search_movies / search_tv_shows（mock Movie/TV）
# ---------------------------------------------------------------------------

class TestSearch:
    """搜索电影/剧集"""

    def test_search_movies(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        mock_result = MagicMock()
        mock_iter = iter([MagicMock(title="Inception"), MagicMock(title="Interstellar")])
        mock_result.__iter__.return_value = mock_iter
        svc.movie.search.return_value = mock_result

        results = svc.search_movies("Inception")
        assert len(results) == 2

    def test_search_movies_empty_query(self):
        svc = TMDBService()
        results = svc.search_movies("")
        assert results == []

    def test_search_movies_whitespace_query(self):
        svc = TMDBService()
        results = svc.search_movies("   ")
        assert results == []

    def test_search_tv_shows(self):
        svc = TMDBService()
        svc.tv = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock(name="Breaking Bad")])
        svc.tv.search.return_value = mock_result

        results = svc.search_tv_shows("Breaking Bad")
        assert len(results) == 1

    def test_search_movies_with_total(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock()])
        mock_result.total_results = None
        svc.movie.total_results = 100
        svc.movie.search.return_value = mock_result

        results, total = svc.search_movies_with_total("test")
        assert len(results) == 1
        # total 来自 movie.total_results fallback
        assert total > 0

    def test_search_tv_with_total(self):
        svc = TMDBService()
        svc.tv = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock()])
        mock_result.total_results = None
        svc.tv.total_results = 200
        svc.tv.search.return_value = mock_result

        results, total = svc.search_tv_shows_with_total("test")
        assert total > 0


# ---------------------------------------------------------------------------
# get_movie_details / get_tv_details（mock Movie/TV）
# ---------------------------------------------------------------------------

class TestDetails:
    """电影/剧集详情"""

    def test_movie_details(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        detail_obj = MagicMock()
        detail_obj._json = {"id": 550, "title": "Fight Club", "overview": "..."}
        svc.movie.details.return_value = detail_obj

        # mock credits
        cast_member = MagicMock()
        cast_member.name = "Brad Pitt"
        cast_member.character = "Tyler Durden"
        cast_member.profile_path = "/path.jpg"
        credits_obj = MagicMock()
        credits_obj.cast = [cast_member]
        svc.movie.credits.return_value = credits_obj

        result = svc.get_movie_details(550)
        assert result["id"] == 550
        assert result["title"] == "Fight Club"
        assert len(result["cast"]) == 1
        assert result["cast"][0]["name"] == "Brad Pitt"

    def test_tv_details(self):
        svc = TMDBService()
        svc.tv = MagicMock()
        detail_obj = MagicMock()
        detail_obj._json = {"id": 1399, "name": "GoT", "overview": "..."}
        svc.tv.details.return_value = detail_obj
        credits_obj = MagicMock()
        credits_obj.cast = []
        svc.tv.credits.return_value = credits_obj

        result = svc.get_tv_details(1399)
        assert result["id"] == 1399
        assert result["name"] == "GoT"


# ---------------------------------------------------------------------------
# get_movie_english_title / get_tv_english_title（mock Movie/TV）
# ---------------------------------------------------------------------------

class TestEnglishTitle:
    """英文标题提取"""

    def test_movie_english_title_from_detail(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        detail = MagicMock()
        detail.title = "Inception"
        svc.movie.details.return_value = detail

        title = svc.get_movie_english_title(550)
        assert title == "Inception"

    def test_movie_english_title_fallback_to_alternative(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        # 第一次 detail 返回空 title
        detail1 = MagicMock()
        detail1.title = None
        # alternative_titles 返回英文标题
        alt = MagicMock()
        alt.iso_3166_1 = "US"
        alt.title = "English Title"
        svc.movie.details.return_value = detail1
        svc.movie.alternative_titles.return_value = [alt]

        title = svc.get_movie_english_title(550)
        assert title == "English Title"

    def test_tv_english_title_from_detail(self):
        svc = TMDBService()
        svc.tv = MagicMock()
        detail = MagicMock()
        detail.name = "Breaking Bad"
        svc.tv.details.return_value = detail

        title = svc.get_tv_english_title(1399)
        assert title == "Breaking Bad"

    def test_tv_english_title_exception_returns_none(self):
        svc = TMDBService()
        svc.tv = MagicMock()
        svc.tv.details.side_effect = Exception("API error")
        svc.tv.alternative_titles.side_effect = Exception("also failed")

        title = svc.get_tv_english_title(1399)
        assert title is None


# ---------------------------------------------------------------------------
# 趋势/热门/高分（mock Trending/Discover/Movie/TV）
# ---------------------------------------------------------------------------

class TestTrendingAndPopular:
    """趋势、热门、高分"""

    def test_trending_movies(self):
        svc = TMDBService()
        svc.trending = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock(title="A")])
        mock_result.total_results = 1
        svc.trending.movie_week.return_value = mock_result

        results, total = svc.get_trending_movies()
        assert len(results) == 1
        assert total == 1

    def test_trending_tv(self):
        svc = TMDBService()
        svc.trending = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock(name="B")])
        mock_result.total_results = 2
        svc.trending.tv_week.return_value = mock_result

        results, total = svc.get_trending_tv()
        assert len(results) == 1
        assert total == 2

    def test_popular_movies(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock()])
        mock_result.total_results = 10
        svc.movie.popular.return_value = mock_result

        results, total = svc.get_popular_movies()
        assert len(results) == 1
        assert total == 10

    def test_top_rated_movies(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock(), MagicMock()])
        mock_result.total_results = 20
        svc.movie.top_rated.return_value = mock_result

        results, total = svc.get_top_rated_movies()
        assert len(results) == 2
        assert total == 20

    def test_top_rated_anime(self):
        svc = TMDBService()
        svc.discover = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([MagicMock(), MagicMock(), MagicMock()])
        mock_result.total_results = 3
        svc.discover.discover_tv_shows.return_value = mock_result

        results, total = svc.get_top_rated_anime()
        assert len(results) == 3
        assert total == 3

    def test_request_exception_returns_empty(self):
        import requests as req_lib
        svc = TMDBService()
        svc.movie = MagicMock()
        svc.movie.popular.side_effect = req_lib.RequestException("offline")

        results, total = svc.get_popular_movies()
        assert results == []
        assert total == 0


# ---------------------------------------------------------------------------
# get_search_suggestions（mock Movie/TV/Search）
# ---------------------------------------------------------------------------

class TestSearchSuggestions:
    """搜索建议/补全"""

    def test_movie_suggestions(self):
        svc = TMDBService()
        svc.movie = MagicMock()
        mock_result = MagicMock()
        items = [MagicMock(title="Avatar"), MagicMock(title="Avengers")]
        mock_result.__iter__.return_value = iter(items)
        svc.movie.search.return_value = mock_result

        suggestions = svc.get_search_suggestions("Av", media_type="movie")
        assert len(suggestions) == 2
        assert "Avatar" in suggestions

    def test_tv_suggestions(self):
        svc = TMDBService()
        svc.tv = MagicMock()
        mock_result = MagicMock()
        mock_item = MagicMock()
        mock_item.name = "Stranger Things"
        mock_result.__iter__.return_value = iter([mock_item])
        svc.tv.search.return_value = mock_result

        suggestions = svc.get_search_suggestions("Stranger", media_type="tv")
        assert "Stranger Things" in suggestions

    def test_empty_query(self):
        svc = TMDBService()
        assert svc.get_search_suggestions("") == []
        assert svc.get_search_suggestions("   ") == []

    def test_duplicates_removed(self):
        svc = TMDBService()
        svc.search = MagicMock()
        # multi search 返回重复标题
        r1 = MagicMock(spec=[])
        r1.title = "Test"
        r2 = MagicMock(spec=[])
        r2.title = "Test"
        mock_multi = MagicMock()
        mock_multi.__iter__.return_value = iter([r1, r2])
        svc.search.multi.return_value = mock_multi

        suggestions = svc.get_search_suggestions("Test")
        assert suggestions == ["Test"]

    def test_exception_returns_empty(self):
        svc = TMDBService()
        svc.search = MagicMock()
        svc.search.multi.side_effect = Exception("broken")

        assert svc.get_search_suggestions("test") == []


# ---------------------------------------------------------------------------
# reload_config
# ---------------------------------------------------------------------------

class TestReloadConfig:
    """reload_config：从运行时配置刷新 api_key / language / domain"""

    def test_api_domain_strips_protocol(self):
        svc = TMDBService()
        with patch("app.services.tmdb_service.config") as mock_cfg:
            mock_cfg.get.side_effect = lambda key, default=None: {
                "tmdb.api_key": "test_key",
                "tmdb.language": "zh-CN",
                "tmdb.api_domain": "https://custom.api.org/",
            }.get(key, default)
            svc.reload_config()
            # _base 应被设置
            assert "custom.api.org" in svc.tmdb._base

    def test_default_domain(self):
        svc = TMDBService()
        with patch("app.services.tmdb_service.config") as mock_cfg:
            mock_cfg.get.side_effect = lambda key, default=None: {
                "tmdb.api_key": "",
                "tmdb.language": "zh-CN",
                "tmdb.api_domain": None,
            }.get(key, default)
            svc.reload_config()
            # 默认域名
            assert "api.themoviedb.org" in svc.tmdb._base
