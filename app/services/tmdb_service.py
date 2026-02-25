import logging
import os
from typing import Any, List, Optional

import requests
from tmdbv3api import TMDb, Movie, TV, Search, Trending

from app.core.config import config

logger = logging.getLogger(__name__)

# 英文区国家优先级（用于从 alternative_titles 中选取英文标题）
_ENGLISH_COUNTRIES = ("US", "GB", "AU", "CA")


def _attr_or_key(obj: Any, key: str) -> Optional[str]:
    """从 tmdbv3api AsObj 或 dict 中取属性/键值"""
    if obj is None:
        return None
    v = getattr(obj, key, None)
    if v is not None:
        return str(v).strip() if v else None
    if isinstance(obj, dict):
        v = obj.get(key)
        return str(v).strip() if v else None
    return None


class TMDBService:
    """TMDB API 服务，封装电影、剧集搜索及详情"""

    def __init__(self):
        self.tmdb = TMDb()
        self.tmdb.api_key = config.get("tmdb.api_key")
        self.tmdb.language = config.get("tmdb.language", "zh-CN")
        self.movie = Movie()
        self.tv = TV()
        self.search = Search()
        self.trending = Trending()

    @staticmethod
    def _extract_results(raw) -> List[Any]:
        """从 tmdbv3api 返回值中安全提取结果列表。
        
        tmdbv3api 的 AsObj 正常迭代时直接产出每个结果项（AsObj 实例），
        但在某些边界情况下会退化为迭代字典 key（字符串）。
        这里先尝试正常迭代，发现是字符串就回退到取 .results 属性。
        """
        if isinstance(raw, list):
            return raw
        try:
            items = list(raw)
            # 如果迭代产出了字符串，说明遍历的是 dict 的 key 而非结果
            if items and isinstance(items[0], str):
                if hasattr(raw, 'results'):
                    inner = raw.results
                    return list(inner) if not isinstance(inner, list) else inner
                return []
            return items
        except Exception:
            return []

    @staticmethod
    def _extract_total(raw, fallback_obj=None) -> int:
        """从 tmdbv3api 返回值中安全提取总数"""
        total = getattr(raw, 'total_results', None)
        if total is None and fallback_obj is not None:
            total = getattr(fallback_obj, 'total_results', 0)
        try:
            return int(total or 0)
        except Exception:
            return 0

    def search_movies(self, query: str, page: int = 1) -> List[Any]:
        """搜索电影"""
        if not query or not query.strip():
            return []
        raw = self.movie.search(query.strip(), page=page)
        return self._extract_results(raw)

    def search_tv_shows(self, query: str, page: int = 1) -> List[Any]:
        """搜索电视剧/番剧"""
        if not query or not query.strip():
            return []
        raw = self.tv.search(query.strip(), page=page)
        return self._extract_results(raw)

    def search_movies_with_total(self, query: str, page: int = 1) -> tuple:
        """搜索电影并返回总数"""
        if not query or not query.strip():
            return [], 0
        raw = self.movie.search(query.strip(), page=page)
        return self._extract_results(raw), self._extract_total(raw, self.movie)

    def search_tv_shows_with_total(self, query: str, page: int = 1) -> tuple:
        """搜索剧集并返回总数"""
        if not query or not query.strip():
            return [], 0
        raw = self.tv.search(query.strip(), page=page)
        return self._extract_results(raw), self._extract_total(raw, self.tv)

    def search_multi(self, query: str, page: int = 1) -> List[Any]:
        """混合搜索（电影、电视、人物等）"""
        return self.search.multi(query, page=page)

    def get_movie_details(self, movie_id: int) -> Any:
        """获取电影详情"""
        return self.movie.details(movie_id)

    def get_tv_details(self, tv_id: int) -> Any:
        """获取电视剧详情"""
        return self.tv.details(tv_id)

    def get_movie_english_title(self, movie_id: int) -> Optional[str]:
        """获取电影的英文标题（供海盗湾等英文搜索使用）。优先 en-US 详情主标题，再 fallback 到 alternative_titles。"""
        try:
            old_lang = self.tmdb.language
            self.tmdb.language = "en-US"
            try:
                detail = self.movie.details(movie_id)
                title = _attr_or_key(detail, "title")
                if title:
                    return title
            finally:
                self.tmdb.language = old_lang
        except Exception as e:
            logger.debug("获取电影英文主标题失败 movie_id=%s: %s", movie_id, e)
        try:
            raw = self.movie.alternative_titles(movie_id)
            titles = raw if isinstance(raw, list) else list(raw) if raw else []
            for country in _ENGLISH_COUNTRIES:
                for t in titles:
                    if (_attr_or_key(t, "iso_3166_1") or "").upper() == country:
                        title = _attr_or_key(t, "title")
                        if title:
                            return title
            for t in titles:
                title = _attr_or_key(t, "title")
                if title:
                    return title
            return None
        except Exception as e:
            logger.debug("获取电影英文标题 alternative_titles 失败 movie_id=%s: %s", movie_id, e)
            return None

    def get_tv_english_title(self, tv_id: int) -> Optional[str]:
        """获取剧集的英文标题（供海盗湾等英文搜索使用）。优先 en-US 详情主标题（避免取到工作名如 Montauk），再 fallback 到 alternative_titles。"""
        try:
            old_lang = self.tmdb.language
            self.tmdb.language = "en-US"
            try:
                detail = self.tv.details(tv_id)
                name = _attr_or_key(detail, "name")
                if name:
                    return name
            finally:
                self.tmdb.language = old_lang
        except Exception as e:
            logger.debug("获取剧集英文主标题失败 tv_id=%s: %s", tv_id, e)
        try:
            raw = self.tv.alternative_titles(tv_id)
            results = raw if isinstance(raw, list) else list(raw) if raw else []
            for country in _ENGLISH_COUNTRIES:
                for t in results:
                    if (_attr_or_key(t, "iso_3166_1") or "").upper() == country:
                        title = _attr_or_key(t, "title")
                        if title:
                            return title
            for t in results:
                title = _attr_or_key(t, "title")
                if title:
                    return title
            return None
        except Exception as e:
            logger.debug("获取剧集英文标题 alternative_titles 失败 tv_id=%s: %s", tv_id, e)
            return None

    @staticmethod
    def _total_from_raw(raw: Any, fallback: int) -> int:
        """从 TMDB 列表响应或环境变量取 total_results（tmdbv3api 会把 total_results 写入 os.environ）"""
        total = getattr(raw, "total_results", None)
        if total is None:
            try:
                total = os.environ.get("total_results")
            except Exception:
                pass
        try:
            return int(total) if total is not None else fallback
        except (TypeError, ValueError):
            return fallback

    def get_trending_movies(self, page: int = 1, window: str = "week") -> tuple:
        """热播电影，window: day | week，返回 (list, total)"""
        try:
            raw = self.trending.movie_day(page=page) if window == "day" else self.trending.movie_week(page=page)
            results = self._extract_results(raw)
            return results, self._total_from_raw(raw, len(results))
        except requests.RequestException as e:
            logger.warning("TMDB 热播电影请求失败: %s", e)
            return [], 0

    def get_trending_tv(self, page: int = 1, window: str = "week") -> tuple:
        """热播剧集，window: day | week，返回 (list, total)"""
        try:
            raw = self.trending.tv_day(page=page) if window == "day" else self.trending.tv_week(page=page)
            results = self._extract_results(raw)
            return results, self._total_from_raw(raw, len(results))
        except requests.RequestException as e:
            logger.warning("TMDB 热播剧集请求失败: %s", e)
            return [], 0

    def get_popular_movies(self, page: int = 1) -> tuple:
        """热门电影，返回 (list, total)"""
        try:
            raw = self.movie.popular(page=page)
            results = self._extract_results(raw) if not isinstance(raw, list) else raw
            return results, self._total_from_raw(raw, len(results))
        except requests.RequestException as e:
            logger.warning("TMDB 热门电影请求失败: %s", e)
            return [], 0

    def get_popular_tv(self, page: int = 1) -> tuple:
        """热门剧集，返回 (list, total)"""
        try:
            raw = self.tv.popular(page=page)
            results = self._extract_results(raw) if not isinstance(raw, list) else raw
            return results, self._total_from_raw(raw, len(results))
        except requests.RequestException as e:
            logger.warning("TMDB 热门剧集请求失败: %s", e)
            return [], 0

    def get_top_rated_movies(self, page: int = 1) -> tuple:
        """高分电影，返回 (list, total)"""
        try:
            raw = self.movie.top_rated(page=page)
            results = self._extract_results(raw) if not isinstance(raw, list) else raw
            return results, self._total_from_raw(raw, len(results))
        except requests.RequestException as e:
            logger.warning("TMDB 高分电影请求失败: %s", e)
            return [], 0

    def get_top_rated_tv(self, page: int = 1) -> tuple:
        """高分剧集，返回 (list, total)"""
        try:
            raw = self.tv.top_rated(page=page)
            results = self._extract_results(raw) if not isinstance(raw, list) else raw
            return results, self._total_from_raw(raw, len(results))
        except requests.RequestException as e:
            logger.warning("TMDB 高分剧集请求失败: %s", e)
            return [], 0

    def get_search_suggestions(self, query: str, limit: int = 10, media_type: str = "") -> List[str]:
        """获取搜索补全提示，支持按类型过滤"""
        if not query or not query.strip():
            return []
        try:
            suggestions = []
            if media_type == "movie":
                results = self._extract_results(self.movie.search(query.strip()))
                for r in results:
                    title = getattr(r, 'title', None) or (r.get('title') if isinstance(r, dict) else None)
                    if title:
                        suggestions.append(title)
            elif media_type == "tv":
                results = self._extract_results(self.tv.search(query.strip()))
                for r in results:
                    name = getattr(r, 'name', None) or (r.get('name') if isinstance(r, dict) else None)
                    if name:
                        suggestions.append(name)
            else:
                results = self.search.multi(query.strip())
                for result in results:
                    if hasattr(result, 'title'):
                        suggestions.append(result.title)
                    elif hasattr(result, 'name'):
                        suggestions.append(result.name)
            return list(dict.fromkeys(suggestions))[:limit]  # 去重并截取
        except Exception as e:
            logger.error(f"获取建议时出错: {e}")
            return []


tmdb_service = TMDBService()
