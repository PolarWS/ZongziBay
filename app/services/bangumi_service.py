import logging
from datetime import date as date_cls
from typing import Dict, List, Optional, Tuple

import requests

from app.core.config import config

logger = logging.getLogger(__name__)

# Bangumi 要求请求带 User-Agent 以标识客户端
_USER_AGENT = "ZongziBay/1.0 (https://github.com/PolarWS/ZongziBay)"

# 季度 → 三个月；平台过滤更接近新番表
_SEASON_MONTHS: Dict[str, Tuple[int, int, int]] = {
    "winter": (1, 2, 3),
    "spring": (4, 5, 6),
    "summer": (7, 8, 9),
    "autumn": (10, 11, 12),
}
_SEASON_PLATFORMS = frozenset({"TV", "WEB"})

_WEEKDAY_META = (
    {"id": 1, "cn": "星期一", "en": "Mon", "ja": "月曜日"},
    {"id": 2, "cn": "星期二", "en": "Tue", "ja": "火曜日"},
    {"id": 3, "cn": "星期三", "en": "Wed", "ja": "水曜日"},
    {"id": 4, "cn": "星期四", "en": "Thu", "ja": "木曜日"},
    {"id": 5, "cn": "星期五", "en": "Fri", "ja": "金曜日"},
    {"id": 6, "cn": "星期六", "en": "Sat", "ja": "土曜日"},
    {"id": 7, "cn": "星期日", "en": "Sun", "ja": "日曜日"},
)
_UNKNOWN_WEEKDAY = {"id": 0, "cn": "日期未定", "en": "TBD", "ja": "未定"}


def _api_base() -> str:
    base = config.get("bangumi.api_url", "https://api.bgm.tv") or "https://api.bgm.tv"
    return base.rstrip("/")


class BangumiService:
    """Bangumi (bgm.tv) 番剧数据服务：每日放送、历史季度、条目详情。"""

    @staticmethod
    def _pick_image(images: dict, *, prefer: str = "large") -> str:
        """从 Bangumi images 中挑一个可用封面。

        prefer: 列表页用 common/medium（体积小、滚动更顺），详情页用 large。
        """
        if not isinstance(images, dict):
            return ""
        order = {
            "large": ("large", "common", "medium", "small", "grid"),
            "common": ("common", "medium", "large", "small", "grid"),
            "medium": ("medium", "common", "large", "small", "grid"),
        }.get(prefer, ("large", "common", "medium", "small", "grid"))
        for k in order:
            v = images.get(k)
            if v:
                return str(v)
        return ""

    def get_calendar(self) -> List[dict]:
        """获取每日放送，返回按星期分组的列表。

        结构: [{ weekday: {id, cn, en, ja}, items: [{...精简条目}] }, ...]
        """
        url = f"{_api_base()}/calendar"
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"请求 Bangumi 每日放送失败: {e}")
            raise
        except Exception as e:
            logger.error(f"解析 Bangumi 每日放送响应失败: {e}")
            raise

        result: List[dict] = []
        if not isinstance(data, list):
            return result
        for day in data:
            weekday = day.get("weekday") or {}
            items_out = []
            for it in day.get("items") or []:
                rating = it.get("rating") or {}
                collection = it.get("collection") or {}
                items_out.append({
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "name_cn": it.get("name_cn"),
                    "air_date": it.get("air_date"),
                    "air_weekday": it.get("air_weekday"),
                    # 列表用 large：common 在高分屏海报卡上偏糊；滚动卡顿已靠前端其它优化缓解
                    "image": self._pick_image(it.get("images") or {}, prefer="large"),
                    "score": rating.get("score"),
                    "rating_total": rating.get("total"),
                    "rank": it.get("rank"),
                    "doing": collection.get("doing"),
                    "url": it.get("url"),
                    # 简介仅在详情接口返回，日历列表不带以减小 payload / 响应式开销
                })
            result.append({
                "weekday": {
                    "id": weekday.get("id"),
                    "cn": weekday.get("cn"),
                    "en": weekday.get("en"),
                    "ja": weekday.get("ja"),
                },
                "items": items_out,
            })
        return result

    def _fetch_subjects_month(self, year: int, month: int) -> List[dict]:
        """分页拉取某年某月的动画条目（type=2）。"""
        url = f"{_api_base()}/v0/subjects"
        items: List[dict] = []
        offset = 0
        limit = 50
        while True:
            try:
                resp = requests.get(
                    url,
                    params={
                        "type": 2,
                        "year": year,
                        "month": month,
                        "limit": limit,
                        "offset": offset,
                        "sort": "date",
                    },
                    timeout=20,
                    headers={"User-Agent": _USER_AGENT},
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                logger.error(f"请求 Bangumi 季度条目失败 year={year} month={month}: {e}")
                raise
            except Exception as e:
                logger.error(f"解析 Bangumi 季度条目失败 year={year} month={month}: {e}")
                raise

            batch = data.get("data") if isinstance(data, dict) else None
            if not isinstance(batch, list) or not batch:
                break
            items.extend(batch)
            total = int(data.get("total") or 0)
            offset += len(batch)
            if offset >= total or len(batch) < limit:
                break
        return items

    @staticmethod
    def _weekday_from_date(air_date: Optional[str]) -> Optional[int]:
        """YYYY-MM-DD → Bangumi 星期 id（1=周一 … 7=周日）；无效返回 None。"""
        if not air_date or len(air_date) < 10:
            return None
        try:
            y, m, d = (int(x) for x in air_date[:10].split("-"))
            # Python weekday: Mon=0 … Sun=6 → Bangumi: Mon=1 … Sun=7
            return date_cls(y, m, d).weekday() + 1
        except (ValueError, TypeError):
            return None

    def _map_season_item(self, it: dict) -> dict:
        """将 /v0/subjects 条目映射为与 calendar 一致的精简结构。"""
        rating = it.get("rating") or {}
        collection = it.get("collection") or {}
        air_date = it.get("date") or ""
        sid = it.get("id")
        return {
            "id": sid,
            "name": it.get("name"),
            "name_cn": it.get("name_cn"),
            "air_date": air_date or None,
            "air_weekday": self._weekday_from_date(air_date),
            "image": self._pick_image(it.get("images") or {}, prefer="common"),
            "score": rating.get("score"),
            "rating_total": rating.get("total"),
            "rank": rating.get("rank"),
            "doing": collection.get("doing"),
            "url": f"https://bgm.tv/subject/{sid}" if sid else None,
        }

    def get_season(self, year: int, season: str) -> List[dict]:
        """按历史季度拉取 TV/WEB 动画，按首播日归到周一–周日。

        season: winter | spring | summer | autumn
        返回结构与 get_calendar 相同；无首播日的条目归入末尾「日期未定」。
        """
        months = _SEASON_MONTHS.get(season)
        if not months:
            raise ValueError(f"无效季节: {season}")
        if year < 1980 or year > 2100:
            raise ValueError(f"无效年份: {year}")

        raw: List[dict] = []
        seen_ids: set = set()
        for month in months:
            for it in self._fetch_subjects_month(year, month):
                if it.get("platform") not in _SEASON_PLATFORMS:
                    continue
                sid = it.get("id")
                if sid is not None and sid in seen_ids:
                    continue
                if sid is not None:
                    seen_ids.add(sid)
                raw.append(it)

        buckets: Dict[int, List[dict]] = {i: [] for i in range(1, 8)}
        unknown: List[dict] = []
        for it in raw:
            mapped = self._map_season_item(it)
            wd = mapped.get("air_weekday")
            if isinstance(wd, int) and 1 <= wd <= 7:
                buckets[wd].append(mapped)
            else:
                unknown.append(mapped)

        # 同日内按首播日、评分排序
        def _sort_key(x: dict):
            return (x.get("air_date") or "9999", -(x.get("score") or 0))

        result: List[dict] = []
        for meta in _WEEKDAY_META:
            items = sorted(buckets[meta["id"]], key=_sort_key)
            result.append({"weekday": dict(meta), "items": items})
        if unknown:
            result.append({
                "weekday": dict(_UNKNOWN_WEEKDAY),
                "items": sorted(unknown, key=_sort_key),
            })
        return result

    def get_subject(self, subject_id: int) -> dict:
        """获取番剧条目详情，调用 Bangumi /v0/subjects/{id}。"""
        url = f"{_api_base()}/v0/subjects/{subject_id}"
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"请求 Bangumi 条目详情失败: {e}")
            raise
        except Exception as e:
            logger.error(f"解析 Bangumi 条目详情响应失败: {e}")
            raise

        rating = data.get("rating") or {}
        tags = []
        for t in data.get("tags") or []:
            name = t.get("name")
            if name:
                tags.append({"name": name, "count": t.get("count")})

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "name_cn": data.get("name_cn"),
            "summary": data.get("summary"),
            "date": data.get("date"),
            "platform": data.get("platform"),
            "eps": data.get("eps"),
            "total_episodes": data.get("total_episodes"),
            "image": self._pick_image(data.get("images") or {}),
            "score": rating.get("score"),
            "rating_total": rating.get("total"),
            "rank": rating.get("rank"),
            "tags": tags[:12],
            "url": f"https://bgm.tv/subject/{data.get('id')}" if data.get("id") else None,
        }


bangumi_service = BangumiService()
