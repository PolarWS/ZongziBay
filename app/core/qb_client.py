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
        self.authenticated = False

    def login(self) -> bool:
        """登录到 qBittorrent"""
        url = f"{self.host}/api/v2/auth/login"
        data = {'username': self.username, 'password': self.password}
        try:
            headers = {'Referer': self.host}
            response = self.session.post(url, data=data, headers=headers, timeout=10)
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

    def ensure_logged_in(self):
        """确保已登录，未登录则尝试登录"""
        if not self.authenticated:
            if not self.login():
                raise BusinessException(code=ErrorCode.SYSTEM_ERROR, message="无法登录到 qBittorrent")

    def add_torrent(self, urls: str, is_paused: bool = False, save_path: str = None) -> bool:
        """添加种子"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/add"
        data = {
            'urls': urls,
            'paused': 'true' if is_paused else 'false'
        }
        if save_path:
            data['savepath'] = save_path
        response = self.session.post(url, data=data, timeout=30)
        return response.status_code == 200

    def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """获取单个种子信息"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/info"
        params = {'hashes': torrent_hash}
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            return data[0]
        return None

    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """获取种子文件列表"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/files"
        params = {'hash': torrent_hash}
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def delete_torrents(self, hashes: str, delete_files: bool = True) -> bool:
        """删除种子，多个 Hash 用 | 分隔"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/delete"
        data = {
            'hashes': hashes,
            'deleteFiles': 'true' if delete_files else 'false'
        }
        response = self.session.post(url, data=data, timeout=30)
        return response.status_code == 200

    def set_file_priority(self, torrent_hash: str, file_ids: List[int], priority: int) -> bool:
        """设置文件优先级，0=不下载 1=普通 6=高 7=最高"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/filePrio"
        id_str = "|".join(map(str, file_ids))
        data = {
            'hash': torrent_hash,
            'id': id_str,
            'priority': priority
        }
        response = self.session.post(url, data=data, timeout=10)
        return response.status_code == 200

    def resume_torrents(self, hashes: str) -> bool:
        """恢复（开始）种子"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/resume"
        data = {'hashes': hashes}
        response = self.session.post(url, data=data, timeout=10)
        return response.status_code == 200

    def pause_torrents(self, hashes: str) -> bool:
        """暂停种子"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/pause"
        data = {'hashes': hashes}
        response = self.session.post(url, data=data, timeout=10)
        return response.status_code == 200

    def get_version(self) -> str:
        """获取 qBittorrent 版本"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/app/version"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return response.text

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """重命名文件"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/renameFile"
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path
        }
        response = self.session.post(url, data=data, timeout=10)
        return response.status_code == 200

    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """重命名文件夹"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/renameFolder"
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path
        }
        response = self.session.post(url, data=data, timeout=10)
        return response.status_code == 200

    def set_location(self, hashes: str, location: str) -> bool:
        """设置保存位置（移动文件）"""
        self.ensure_logged_in()
        url = f"{self.host}/api/v2/torrents/setLocation"
        data = {
            'hashes': hashes,
            'location': location
        }
        response = self.session.post(url, data=data, timeout=30)
        return response.status_code == 200
