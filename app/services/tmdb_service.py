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

    def search_movies(self, query: str, page: int = 1) -> List[Any]:
        """搜索电影"""
        return self.movie.search(query, page=page)

    def search_tv_shows(self, query: str, page: int = 1) -> List[Any]:
        """搜索电视剧/番剧"""
        return self.tv.search(query, page=page)

    def search_movies_with_total(self, query: str, page: int = 1) -> tuple:
        """搜索电影并返回总数"""
        results = self.movie.search(query, page=page)
        total = getattr(self.movie, 'total_results', 0)
        try:
            total = int(total)
        except Exception:
            total = 0
        return results, total

    def search_tv_shows_with_total(self, query: str, page: int = 1) -> tuple:
        """搜索剧集并返回总数"""
        results = self.tv.search(query, page=page)
        total = getattr(self.tv, 'total_results', 0)
        try:
            total = int(total)
        except Exception:
            total = 0
        return results, total

    def search_multi(self, query: str, page: int = 1) -> List[Any]:
        """混合搜索（电影、电视、人物等）"""
        return self.search.multi(query, page=page)

    def get_movie_details(self, movie_id: int) -> Any:
        """获取电影详情"""
        return self.movie.details(movie_id)

    def get_tv_details(self, tv_id: int) -> Any:
        """获取电视剧详情"""
        return self.tv.details(tv_id)

    def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """获取搜索补全提示"""
        if not query:
            return []
        try:
            results = self.search.multi(query)
            suggestions = []
            for result in results:
                if hasattr(result, 'title'):  # 电影有 title
                    suggestions.append(result.title)
                elif hasattr(result, 'name'):  # 剧集有 name
                    suggestions.append(result.name)
            return list(dict.fromkeys(suggestions))[:limit]  # 去重并截取
        except Exception as e:
            logger.error(f"获取建议时出错: {e}")
            return []


tmdb_service = TMDBService()
