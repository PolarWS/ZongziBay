import logging
from typing import Any, List

from tmdbv3api import TMDb, Movie, TV, Search

from app.core.config import config

logger = logging.getLogger(__name__)


class TMDBService:
    """TMDB API 服务，封装电影、剧集搜索及详情"""

    def __init__(self):
        self.tmdb = TMDb()
        self.tmdb.api_key = config.get("tmdb.api_key")
        self.tmdb.language = config.get("tmdb.language", "zh-CN")
        self.movie = Movie()
        self.tv = TV()
        self.search = Search()

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
