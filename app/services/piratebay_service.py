import logging
import re
import urllib.parse
from typing import List

import requests

from app.core.config import config
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.piratebay import PirateBayTorrent

logger = logging.getLogger(__name__)


class PirateBayService:
    """海盗湾 API 搜索服务"""

    def __init__(self):
        self.base_url = config.get("piratebay.url", "https://apibay.org/q.php")
        self.params_template = config.get("piratebay.params", "q=[q]&cat=200")
        self.trackers = config.get("trackers", [])

    def search(self, query: str) -> List[PirateBayTorrent]:
        """在海盗湾搜索种子"""
        params = {}
        # 解析 params 模板，将 [q] 替换为实际关键词
        if isinstance(self.params_template, str):
            try:
                parsed_items = urllib.parse.parse_qsl(self.params_template)
                for key, value in parsed_items:
                    if "[q]" in value:
                        value = value.replace("[q]", str(query))
                    params[key] = value
            except Exception as e:
                logger.error(f"解析 params 模板失败: {self.params_template}, 错误: {e}")
                params = {"q": query, "cat": "200"}  # 降级为默认参数
        elif isinstance(self.params_template, dict):
            for k, v in self.params_template.items():
                if isinstance(v, str):
                    v = v.replace("[q]", str(query))
                params[k] = v
        else:
            params = {"q": query, "cat": "200"}

        try:
            logger.info(f"正在搜索海盗湾，关键词: {query}, URL: {self.base_url}, 参数: {params}")
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            # 海盗湾无结果时返回单元素列表 "No results returned"
            if isinstance(data, list) and len(data) == 1 and data[0].get("name") == "No results returned":
                logger.info("未找到任何结果")
                return []

            results = []
            for item in data:
                try:
                    item_name = self._fix_name(item.get("name", ""), item.get("username", ""))
                    item["name"] = item_name
                    torrent = PirateBayTorrent(**item)
                    # API 不返回 magnet，需根据 info_hash 和 trackers 生成
                    torrent.magnet = self._generate_magnet_link(torrent.info_hash, torrent.name)
                    results.append(torrent)
                except Exception as e:
                    logger.warning(f"解析项目失败: {item}. 错误: {e}")
                    continue
            logger.info(f"搜索完成，找到 {len(results)} 个结果")
            return results
        except requests.RequestException as e:
            logger.error(f"搜索海盗湾时发生错误: {e}")
            raise e

    def _generate_magnet_link(self, info_hash: str, name: str) -> str:
        """生成磁力链接"""
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={urllib.parse.quote(name)}"
        for tracker in self.trackers:
            magnet_link += f"&tr={urllib.parse.quote(tracker)}"
        return magnet_link

    def _fix_name(self, name: str, username: str) -> str:
        """修正种子名称"""
        s = (name or "").strip()
        u = (username or "").strip()
        if not s:
            return s
        # 部分种子名称以 "-" 结尾，需拼接发布者名
        if s.endswith("-") and u and u not in s:
            return s + u
        return s
