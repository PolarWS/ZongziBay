import logging
from typing import Any, Dict, List, Optional

import requests

from app.schemas.base import BusinessException, ErrorCode

logger = logging.getLogger(__name__)


class QBittorrentClient:
    """qBittorrent Web API 客户端"""

    def __init__(self, host, username, password):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        # qBittorrent 4.1+ 默认开启 CSRF 保护，要求所有请求包含 Referer 头部
        self.session.headers.update({'Referer': self.host})
        self.authenticated = False

    def login(self) -> bool:
        """登录到 qBittorrent"""
        url = f"{self.host}/api/v2/auth/login"
        data = {'username': self.username, 'password': self.password}
        try:
            # Referer 已经在 session.headers 中设置
            response = self.session.post(url, data=data, timeout=10)
            if response.status_code == 200:
                if "Ok." in response.text:
                    self.authenticated = True
                    return True
                elif "Fails." in response.text:
                    logger.error("qBittorrent 登录失败: 用户名或密码错误")
                    return False
                else:
                    logger.warning(f"qBittorrent 登录响应未知内容: {response.text}")
                    return False
            elif response.status_code == 403:
                logger.error(f"qBittorrent 登录被拒绝 (IP 可能被封禁): {response.text}")
                raise BusinessException(code=ErrorCode.SYSTEM_ERROR, message=f"qBittorrent IP被封禁: {response.text}")
            else:
                logger.error(f"qBittorrent 登录失败: 状态码 {response.status_code}, 响应: {response.text}")
                return False
        except BusinessException:
            raise
        except Exception as e:
            logger.error(f"qBittorrent 连接异常: {e}")
            return False

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """发送请求，处理 403/401 自动重连"""
        self.ensure_logged_in()
        
        # 尝试第一次请求
        response = self.session.request(method, url, **kwargs)
        
        # 如果 403 (可能 session 失效或 CSRF 令牌过期)，尝试重新登录后重试一次
        if response.status_code in (401, 403):
            logger.warning(f"qBittorrent 请求返回 {response.status_code}，尝试重新登录后重试")
            self.authenticated = False
            self.ensure_logged_in()
            response = self.session.request(method, url, **kwargs)
            
        return response

    def ensure_logged_in(self):
        """确保已登录，未登录则尝试登录"""
        if not self.authenticated:
            if not self.login():
                raise BusinessException(code=ErrorCode.SYSTEM_ERROR, message="无法登录到 qBittorrent")

    def add_torrent(
        self,
        urls: str,
        is_paused: bool = False,
        save_path: str = None,
        content_layout: Optional[str] = None,
    ) -> bool:
        """添加种子

        content_layout:
        - "Original": 保持种子原始结构
        - "NoSubfolder": 不创建种子名子目录（本程序用于避免多余“套壳”）
        - "Subfolder": 强制创建子目录
        """
        url = f"{self.host}/api/v2/torrents/add"
        data = {
            'urls': urls,
            'paused': 'true' if is_paused else 'false'
        }
        if save_path:
            data['savepath'] = save_path
        if content_layout:
            data['contentLayout'] = content_layout
        
        response = self._request("POST", url, data=data, timeout=30)
        return response.status_code == 200

    def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """获取单个种子信息"""
        url = f"{self.host}/api/v2/torrents/info"
        params = {'hashes': torrent_hash}
        response = self._request("GET", url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            return data[0]
        return None

    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """获取种子文件列表"""
        url = f"{self.host}/api/v2/torrents/files"
        params = {'hash': torrent_hash}
        response = self._request("GET", url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def delete_torrents(self, hashes: str, delete_files: bool = True) -> bool:
        """删除种子，多个 Hash 用 | 分隔"""
        url = f"{self.host}/api/v2/torrents/delete"
        data = {
            'hashes': hashes,
            'deleteFiles': 'true' if delete_files else 'false'
        }
        response = self._request("POST", url, data=data, timeout=30)
        return response.status_code == 200

    def set_file_priority(self, torrent_hash: str, file_ids: List[int], priority: int) -> bool:
        """设置文件优先级，0=不下载 1=普通 6=高 7=最高"""
        url = f"{self.host}/api/v2/torrents/filePrio"
        id_str = "|".join(map(str, file_ids))
        data = {
            'hash': torrent_hash,
            'id': id_str,
            'priority': priority
        }
        response = self._request("POST", url, data=data, timeout=10)
        return response.status_code == 200

    def resume_torrents(self, hashes: str) -> bool:
        """恢复（开始）种子"""
        url = f"{self.host}/api/v2/torrents/resume"
        data = {'hashes': hashes}
        response = self._request("POST", url, data=data, timeout=10)
        return response.status_code == 200

    def pause_torrents(self, hashes: str) -> bool:
        """暂停种子"""
        url = f"{self.host}/api/v2/torrents/pause"
        data = {'hashes': hashes}
        response = self._request("POST", url, data=data, timeout=10)
        return response.status_code == 200

    def get_version(self) -> str:
        """获取 qBittorrent 版本"""
        url = f"{self.host}/api/v2/app/version"
        response = self._request("GET", url, timeout=10)
        response.raise_for_status()
        return response.text

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """重命名文件"""
        url = f"{self.host}/api/v2/torrents/renameFile"
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path
        }
        response = self._request("POST", url, data=data, timeout=10)
        return response.status_code == 200

    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """重命名文件夹"""
        url = f"{self.host}/api/v2/torrents/renameFolder"
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path
        }
        response = self._request("POST", url, data=data, timeout=10)
        return response.status_code == 200

    def set_location(self, hashes: str, location: str) -> bool:
        """设置保存位置（移动文件）"""
        url = f"{self.host}/api/v2/torrents/setLocation"
        data = {
            'hashes': hashes,
            'location': location
        }
        response = self._request("POST", url, data=data, timeout=30)
        return response.status_code == 200
