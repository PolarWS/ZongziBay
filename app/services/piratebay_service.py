import re

import requests
import logging
import urllib.parse
from typing import List
from app.core.config import Config
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.piratebay import PirateBayTorrent

logger = logging.getLogger(__name__)

class PirateBayService:
    def __init__(self):
        self.config = Config()
        self.base_url = self.config.get("piratebay.url", "https://apibay.org/q.php")
        # 直接获取 params 字符串，例如 "q=[q]&cat=200"
        self.params_template = self.config.get("piratebay.params", "q=[q]&cat=200")
        # 获取 trackers 列表
        self.trackers = self.config.get("trackers", [])

    def search(self, query: str) -> List[PirateBayTorrent]:
        """
        在海盗湾搜索种子。
        
        Args:
            query: 搜索关键词。
            
        Returns:
            List[PirateBayTorrent]: 种子对象列表。
        """
        
        # 解析 params 模板
        params = {}
        
        if isinstance(self.params_template, str):
            try:
                # 使用 parse_qsl 解析查询字符串为 (key, value) 对的列表
                parsed_items = urllib.parse.parse_qsl(self.params_template)
                
                for key, value in parsed_items:
                    # 替换 [q] 为实际查询内容
                    if "[q]" in value:
                        value = value.replace("[q]", str(query))
                    
                    params[key] = value
            except Exception as e:
                logger.error(f"解析 params 模板失败: {self.params_template}, 错误: {e}")
                # 降级处理
                params = {"q": query, "cat": "200"}
        elif isinstance(self.params_template, dict):
            # 支持字典格式的兼容处理
            for k, v in self.params_template.items():
                if isinstance(v, str):
                    v = v.replace("[q]", str(query))
                    params[k] = v
                else:
                    params[k] = v
        else:
            params = {"q": query, "cat": "200"}
        
        try:
            logger.info(f"正在搜索海盗湾，关键词: {query}, URL: {self.base_url}, 参数: {params}")
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # 海盗湾如果没有找到结果，会返回一个包含 "No results returned" 的单元素列表
            if isinstance(data, list) and len(data) == 1 and data[0].get("name") == "No results returned":
                logger.info("未找到任何结果")
                return []
                
            results = []
            for item in data:
                try:
                    item_name = self._fix_name(item.get("name", ""), item.get("username", ""))
                    item["name"] = item_name
                    torrent = PirateBayTorrent(**item)
                    # 生成磁力链接
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
        """
        生成磁力链接
        
        Args:
            info_hash: 种子的哈希值
            name: 种子名称
            
        Returns:
            str: 磁力链接
        """
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={urllib.parse.quote(name)}"
        for tracker in self.trackers:
            magnet_link += f"&tr={urllib.parse.quote(tracker)}"
        return magnet_link

    def _fix_name(self, name: str, username: str) -> str:
        s = (name or "").strip()
        u = (username or "").strip()
        if not s:
            return s
        if s.endswith("-") and u and u not in s:
            return s + u
        return s
