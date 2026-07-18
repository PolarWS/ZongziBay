import logging
import re
from typing import List, Optional

import requests

from app.core.config import config
from app.schemas.anime_garden import (
    AnimeGardenResponse,
    AnimeGardenResource,
    AnimeGardenTeamsResponse,
)

logger = logging.getLogger(__name__)

# 用于拆分搜索词的季/期/部/集数正则模式
# Anime Garden 服务端对每个 search 参数独立调用 jieba.cut() 分词后，
# 所有词用 & (AND) 连接成 tsquery 做 PG 全文搜索。
# 所以把番剧名和季/集标记拆开传，比混在一起分词准确得多。
_SEARCH_SPLIT_PATTERNS = [
    r'第[一二三四五六七八九十\d]+季',
    r'第[一二三四五六七八九十\d]+期',
    r'第[一二三四五六七八九十\d]+部',
    r'第[一二三四五六七八九十\d]+[集話话]',
    r'Final\s+Season',               # "Final Season" 完结篇（无数字）
    r'Season\s*\d+',                  # "Season 1" / "Season3"
    r'(?<![a-zA-Z])S\d{1,2}(?![a-zA-Z0-9])',  # "S1" / "S03"（不用 \b，Python 会把中文当 \w）
]


def _teams_url() -> str:
    url = config.get("anime_garden.url", "https://animes.garden/api/resources")
    base = url.rstrip("/").replace("/resources", "")
    return config.get("anime_garden.teams_url", f"{base}/teams")


class AnimeGardenService:
    """动漫花园 (Anime Garden) API 搜索服务，支持关键字搜索与字幕组筛选。

    搜索优化策略（基于 Anime Garden 源码分析）：
    ----------------------------------------------------
    Anime Garden 服务端使用 PostgreSQL tsvector + @node-rs/jieba 结巴分词
    实现中文全文搜索。每个 search 参数被独立用 jieba.cut() 分词后，所有 token
    用 & (AND) 连接成 tsquery。

    因此：将输入拆成多个 search 参数传给 API（如 "葬送的芙莉莲" 和 "第三季"
    分开传），比传一个完整的 "葬送的芙莉莲第三季" 分词效果更好。

    回退策略：若拆分搜索返回结果太少，自动回退到仅用核心番剧名做宽泛搜索。
    """

    def __init__(self):
        self.base_url = config.get("anime_garden.url", "https://animes.garden/api/resources")
        try:
            self.page_size = int(config.get("anime_garden.page_size", 20))
        except (ValueError, TypeError):
            self.page_size = 20

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

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

        智能搜索策略：
        1. 将查询词拆分为多个 search 参数（番剧名 + 季/集标记分开），
           利用 Anime Garden 对每个 search 参数独立 Jieba 分词的特性提升匹配精度。
        2. 若拆分后结果太少（< 同页半数），回退到仅用核心番剧名做宽泛搜索。

        返回与 Anime Garden 一致的结构：{ status, complete, resources, pagination }，
        额外增加 query_modified / query_used 字段。
        """
        size = int(page_size) if page_size is not None else self.page_size
        cleaned = q.strip()
        terms = self._parse_search_terms(cleaned)
        query_modified = len(terms) > 1

        # 第一步：用拆分的多个 search 参数搜索
        logger.info(f"搜索词拆分: {cleaned!r} → {terms}")
        result = self._do_search(terms, page, size, fansub)

        # 第二步：若结果不足且拆分过，回退到仅用核心词搜索
        threshold = max(5, size // 2)
        if query_modified and len(result["resources"]) < threshold:
            core = terms[0]  # 核心番剧名
            logger.info(f"拆分搜索词结果不足 ({len(result['resources'])} 条 < {threshold})，回退到核心词: {core!r}")
            try:
                fallback = self._do_search([core], page, size, fansub)
                seen = {r["id"] for r in result["resources"]}
                added = 0
                for r in fallback["resources"]:
                    if r["id"] not in seen:
                        result["resources"].append(r)
                        seen.add(r["id"])
                        added += 1
                if added > 0:
                    logger.info(f"回退搜索合并了 {added} 条额外结果（共 {len(result['resources'])} 条）")
                    # 回退后显示核心词，让用户知道搜了什么
                    result["query_used"] = core
            except Exception:
                logger.warning("回退搜索失败，使用拆分结果", exc_info=True)

        result.setdefault("query_modified", query_modified)
        result.setdefault("query_used", " + ".join(terms) if query_modified else cleaned)
        return result

    # ------------------------------------------------------------------
    # 搜索词拆分
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_search_terms(q: str) -> List[str]:
        """将搜索词按季/期/部/集数标记拆分为多个独立搜索词。

        Anime Garden 对每个 search 参数独立调用 jieba.cut() 分词，全部 token
        用 & 连接。拆分后每个部分独立分词，匹配精度大幅提升。

        示例：
            "葬送的芙莉莲第三季"       → ["葬送的芙莉莲", "第三季"]
            "鬼灭之刃第3季 1080p"      → ["鬼灭之刃", "第3季", "1080p"]
            "进击的巨人Final Season完" → ["进击的巨人", "Final Season", "完"]
            "咒术回战S2"               → ["咒术回战", "S2"]
        """
        q = q.strip()
        if not q:
            return []

        # 组合所有拆分模式
        merged = '|'.join(f'({p})' for p in _SEARCH_SPLIT_PATTERNS)
        regex = re.compile(merged, re.IGNORECASE)

        parts: List[str] = []
        last_end = 0

        for m in regex.finditer(q):
            prefix = q[last_end:m.start()].strip()
            if prefix:
                parts.append(prefix)
            parts.append(m.group().strip())
            last_end = m.end()

        # 最后一个标记之后的剩余文本
        suffix = q[last_end:].strip()
        if suffix:
            parts.append(suffix)

        if not parts:
            return [q]

        # 去重并保持顺序
        seen: set = set()
        result: List[str] = []
        for p in parts:
            if p and p not in seen:
                result.append(p)
                seen.add(p)

        return result if result else [q]

    # ------------------------------------------------------------------
    # 底层 HTTP 请求
    # ------------------------------------------------------------------

    def _do_search(
        self,
        search_terms: List[str],
        page: int,
        page_size: int,
        fansub: Optional[str] = None,
    ) -> dict:
        """执行单次 API 搜索请求。

        参数 search_terms 为列表时，requests 自动生成 ?search=a&search=b，
        对应 Anime Garden API 的多 search 参数（每个独立 Jieba 分词）。
        """
        params: dict = {
            "search": search_terms,
            "page": page,
            "pageSize": page_size,
        }
        if fansub and fansub.strip():
            params["fansub"] = fansub.strip()

        logger.info(f"请求动漫花园 | search={search_terms} page={page} pageSize={page_size} fansub={fansub}")
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            parsed = AnimeGardenResponse(**data)

            pagination = None
            if parsed.pagination is not None:
                pagination = parsed.pagination.model_dump()

            resources_out = [r.model_dump() for r in parsed.resources]

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
