import logging
from typing import List, Optional

import requests

from app.core.config import config
from app.schemas.anime_garden import (
    AnimeGardenResponse,
    AnimeGardenResource,
    AnimeGardenTeamsResponse,
)

logger = logging.getLogger(__name__)


def _teams_url() -> str:
    url = config.get("anime_garden.url", "https://animes.garden/api/resources")
    base = url.rstrip("/").replace("/resources", "")
    return config.get("anime_garden.teams_url", f"{base}/teams")


class AnimeGardenService:
    """动漫花园 (Anime Garden) API 搜索服务，支持关键字搜索与字幕组筛选。"""

    def __init__(self):
        self.base_url = config.get("anime_garden.url", "https://animes.garden/api/resources")
        self.page_size = config.get("anime_garden.page_size", 20)

    def get_teams(self) -> List[dict]:
        """获取所有字幕组列表。返回 [{ id, provider, providerId, name, avatar }, ...]"""
        try:
            response = requests.get(_teams_url(), timeout=10)
            response.raise_for_status()
            data = response.json()
            parsed = AnimeGardenTeamsResponse(**data)
            return [t.model_dump() for t in parsed.teams]
        except requests.RequestException as e:
            logger.error(f"请求动漫花园字幕组列表失败: {e}")
            raise
        except Exception as e:
            logger.error(f"解析动漫花园字幕组响应失败: {e}")
            raise

    def search(
        self,
        q: str,
        page: int = 1,
        page_size: Optional[int] = None,
        fansub: Optional[str] = None,
    ) -> dict:
        """
        按关键字搜索资源。支持中文/繁体。可选按字幕组筛选。
        返回与 Anime Garden 一致的结构：{ status, complete, resources, pagination }。
        """
        size = page_size if page_size is not None else self.page_size
        params: dict = {
            "search": q.strip(),
            "page": page,
            "pageSize": size,
        }
        if fansub and fansub.strip():
            params["fansub"] = fansub.strip()
        try:
            logger.info(f"正在请求动漫花园，关键词: {q}, page: {page}, pageSize: {size}, fansub: {fansub}")
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            parsed = AnimeGardenResponse(**data)
            pagination = None
            if parsed.pagination is not None:
                pagination = parsed.pagination.model_dump()
            resources_out = []
            for r in parsed.resources:
                d = r.model_dump()
                resources_out.append(d)
            return {
                "status": parsed.status,
                "complete": parsed.complete,
                "resources": resources_out,
                "pagination": pagination,
                "filter": parsed.filter,
                "timestamp": parsed.timestamp,
            }
        except requests.RequestException as e:
            logger.error(f"请求动漫花园失败: {e}")
            raise
        except Exception as e:
            logger.error(f"解析动漫花园响应失败: {e}")
            raise
