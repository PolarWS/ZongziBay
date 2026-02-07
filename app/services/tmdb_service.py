import logging
from typing import List, Dict, Any, Optional
from tmdbv3api import TMDb, Movie, TV, Search
from app.core.config import config

logger = logging.getLogger(__name__)

class TMDBService:
    """
    TMDB 服务类
    封装 tmdbv3api 的功能，提供电影、电视剧搜索及详情获取
    """
    def __init__(self):
        self.tmdb = TMDb()
        # 从配置文件加载 API Key 和语言设置
        self.tmdb.api_key = config.get("tmdb.api_key")
        self.tmdb.language = config.get("tmdb.language", "zh-CN")
        # 初始化各个模块
        self.movie = Movie()
        self.tv = TV()
        self.search = Search()

    def search_movies(self, query: str, page: int = 1) -> List[Any]:
        """
        搜索电影
        :param query: 搜索关键词
        :param page: 页码
        :return: 电影列表
        """
        results = self.movie.search(query, page=page)
        return results

    def search_tv_shows(self, query: str, page: int = 1) -> List[Any]:
        """
        搜索电视剧/番剧
        :param query: 搜索关键词
        :param page: 页码
        :return: 电视剧列表
        """
        results = self.tv.search(query, page=page)
        return results
    
    def search_movies_with_total(self, query: str, page: int = 1) -> (List[Any], int):
        results = self.movie.search(query, page=page)
        total = getattr(self.movie, 'total_results', 0)
        try:
            total = int(total)
        except Exception:
            total = 0
        return results, total
    
    def search_tv_shows_with_total(self, query: str, page: int = 1) -> (List[Any], int):
        results = self.tv.search(query, page=page)
        total = getattr(self.tv, 'total_results', 0)
        try:
            total = int(total)
        except Exception:
            total = 0
        return results, total
        
    def search_multi(self, query: str, page: int = 1) -> List[Any]:
        """
        混合搜索（电影、电视、人物等）
        :param query: 搜索关键词
        :param page: 页码
        :return: 搜索结果列表
        """
        return self.search.multi(query, page=page)

    def get_movie_details(self, movie_id: int) -> Any:
        """
        获取电影详情
        :param movie_id: 电影 ID
        :return: 电影详情对象
        """
        return self.movie.details(movie_id)

    def get_tv_details(self, tv_id: int) -> Any:
        """
        获取电视剧详情
        :param tv_id: 电视剧 ID
        :return: 电视剧详情对象
        """
        return self.tv.details(tv_id)

    def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """
        获取搜索补全提示
        :param query: 搜索关键词
        :param limit: 返回数量限制
        :return: 建议标题列表
        """
        if not query:
            return []
            
        try:
            results = self.search.multi(query)
            suggestions = []
            for result in results:
                # 电影有 title，电视剧有 name
                if hasattr(result, 'title'):
                    suggestions.append(result.title)
                elif hasattr(result, 'name'):
                    suggestions.append(result.name)
            
            # 去重并截取前 limit 个
            # 使用 dict.fromkeys 保持顺序去重
            return list(dict.fromkeys(suggestions))[:limit]
        except Exception as e:
            logger.error(f"获取建议时出错: {e}")
            return []

# 创建全局单例实例
tmdb_service = TMDBService()
