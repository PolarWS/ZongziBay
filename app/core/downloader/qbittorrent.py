"""qBittorrent 下载器适配器

从原 app/core/qb_client.py 重构而来，继承 BaseDownloader 统一接口。
能力：全量 —— 支持暂停拉元数据、文件选择、种子内重命名、移动位置、做种分享率。

认证：Cookie 会话（4.x/5.x）或 API Key Bearer（5.2.0+）。
关键端点：
- 添加: POST /api/v2/torrents/add（支持 urls 或 multipart torrents 文件）
- 文件优先级: POST /api/v2/torrents/filePrio
- 重命名: POST /api/v2/torrents/renameFile / renameFolder
- 移动: POST /api/v2/torrents/setLocation
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from app.core.downloader.base import BaseDownloader, DownloaderCapabilities, TorrentFile
from app.schemas.base import BusinessException, ErrorCode

logger = logging.getLogger(__name__)


class QBittorrentDownloader(BaseDownloader):
    """qBittorrent 下载后端（原 QBittorrentClient）"""

    capabilities = DownloaderCapabilities(
        name="qbittorrent",
        supports_file_selection=True,
        supports_rename=True,
        supports_set_location=True,
        supports_paused_metadata=True,
        supports_magnet=True,
        supports_torrent_file=True,
        supports_seeding_ratio=True,
    )

    def __init__(self, host: str = "", username: str = "", password: str = "", api_key: str = ""):
        self.host = (host or "http://localhost:8080").strip().rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.session = requests.Session()
        # qBittorrent 4.1+ 默认开启 CSRF 保护，要求所有请求包含 Referer 头部
        self.session.headers.update({'Referer': self.host})

        if api_key:
            # API Key 模式：直接设置 Authorization 头，跳过登录流程
            self.session.headers['Authorization'] = f'Bearer {api_key}'
            self.authenticated = True
        else:
            self.authenticated = False

    # ------------------------------------------------------------------
    # 认证
    # ------------------------------------------------------------------

    def login(self) -> bool:
        """登录到 qBittorrent（Cookie 会话模式）

        qBittorrent 版本差异，按优先级依次判断：
        - >= 5.2.0: 成功返回 204，失败返回 401
        - < 5.2.0:  成功返回 200 + "Ok."，失败返回 200 + "Fails."
        """
        if self.api_key:
            return True
        url = f"{self.host}/api/v2/auth/login"
        data = {'username': self.username, 'password': self.password}
        try:
            response = self.session.post(url, data=data, timeout=10)

            if response.status_code == 204:  # v5.2+
                self.authenticated = True
                return True
            if response.status_code == 401:
                logger.error("qBittorrent 登录失败 (401): 用户名或密码错误")
                return False
            if response.status_code == 200:
                if "Fails." in response.text:
                    logger.error("qBittorrent 登录失败: 用户名或密码错误")
                    return False
                if "Ok." in response.text:
                    self.authenticated = True
                    return True
                logger.warning(f"qBittorrent 登录响应未知内容: {response.text}")
                return False
            if response.status_code == 403:
                logger.error(f"qBittorrent 登录被拒绝 (IP 可能被封禁): {response.text}")
                raise BusinessException(code=ErrorCode.SYSTEM_ERROR, message=f"qBittorrent IP被封禁: {response.text}")
            logger.error(f"qBittorrent 登录失败: 状态码 {response.status_code}, 响应: {response.text}")
            return False
        except BusinessException:
            raise
        except Exception as e:
            logger.error(f"qBittorrent 连接异常: {e}")
            return False

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """发送请求，处理 403/401 自动重连（仅 Cookie 会话模式）"""
        self.ensure_logged_in()

        response = self.session.request(method, url, **kwargs)

        # 仅在 Cookie 会话模式下处理 session 过期重连
        if not self.api_key and response.status_code in (401, 403):
            logger.warning(f"qBittorrent 请求返回 {response.status_code}，尝试重新登录后重试")
            self.authenticated = False
            self.ensure_logged_in()
            response = self.session.request(method, url, **kwargs)

        return response

    def ensure_logged_in(self):
        if self.api_key:
            return
        if not self.authenticated:
            if not self.login():
                raise BusinessException(code=ErrorCode.SYSTEM_ERROR, message="无法登录到 qBittorrent")

    # ------------------------------------------------------------------
    # BaseDownloader 实现
    # ------------------------------------------------------------------

    def check_connection(self) -> bool:
        try:
            self.get_version()
            return True
        except Exception as e:
            logger.error(f"qBittorrent 连接检查失败: {e}")
            return False

    def get_version(self) -> str:
        url = f"{self.host}/api/v2/app/version"
        response = self._request("GET", url, timeout=10)
        response.raise_for_status()
        return response.text

    def add_torrent(
        self,
        urls: str,
        is_paused: bool = False,
        save_path: Optional[str] = None,
        content_layout: Optional[str] = None,
        torrent_file: Optional[bytes] = None,
    ) -> bool:
        """添加种子。

        content_layout:
        - "Original": 保持种子原始结构
        - "NoSubfolder": 不创建种子名子目录（本程序用于避免多余“套壳”）
        - "Subfolder": 强制创建子目录
        """
        url = f"{self.host}/api/v2/torrents/add"
        data = {
            'urls': urls or '',
            'paused': 'true' if is_paused else 'false'
        }
        if save_path:
            data['savepath'] = save_path
        if content_layout:
            data['contentLayout'] = content_layout

        files = None
        if torrent_file:
            files = {'torrents': ('torrent.torrent', torrent_file, 'application/x-bittorrent')}

        response = self._request("POST", url, data=data, files=files, timeout=30)
        return response.status_code == 200

    def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        url = f"{self.host}/api/v2/torrents/info"
        params = {'hashes': torrent_hash}
        try:
            response = self._request("GET", url, params=params, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"qBittorrent 获取种子信息失败: {e}")
            return None
        data = response.json()
        if data and len(data) > 0:
            return data[0]
        return None

    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        url = f"{self.host}/api/v2/torrents/files"
        params = {'hash': torrent_hash}
        try:
            response = self._request("GET", url, params=params, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"qBittorrent 获取文件列表失败: {e}")
            return []
        data = response.json()
        # 补 index 字段，保持统一文件结构
        for i, f in enumerate(data):
            f.setdefault("index", i)
        return data

    def delete_torrents(self, hashes: str, delete_files: bool = True) -> bool:
        url = f"{self.host}/api/v2/torrents/delete"
        data = {
            'hashes': hashes,
            'deleteFiles': 'true' if delete_files else 'false'
        }
        try:
            response = self._request("POST", url, data=data, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent 删除种子失败: {e}")
            return False

    def set_file_priority(self, torrent_hash: str, file_ids: List[int], priority: int) -> bool:
        """0=不下载 1=普通 6=高 7=最高"""
        url = f"{self.host}/api/v2/torrents/filePrio"
        id_str = "|".join(map(str, file_ids))
        data = {
            'hash': torrent_hash,
            'id': id_str,
            'priority': priority
        }
        try:
            response = self._request("POST", url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent 设置文件优先级失败: {e}")
            return False

    def resume_torrents(self, hashes: str) -> bool:
        url = f"{self.host}/api/v2/torrents/resume"
        data = {'hashes': hashes}
        try:
            response = self._request("POST", url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent 恢复种子失败: {e}")
            return False

    def pause_torrents(self, hashes: str) -> bool:
        url = f"{self.host}/api/v2/torrents/pause"
        data = {'hashes': hashes}
        try:
            response = self._request("POST", url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent 暂停种子失败: {e}")
            return False

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        url = f"{self.host}/api/v2/torrents/renameFile"
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path
        }
        try:
            response = self._request("POST", url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent 重命名文件失败: {e}")
            return False

    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        url = f"{self.host}/api/v2/torrents/renameFolder"
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path
        }
        try:
            response = self._request("POST", url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent 重命名文件夹失败: {e}")
            return False

    def set_location(self, hashes: str, location: str) -> bool:
        url = f"{self.host}/api/v2/torrents/setLocation"
        data = {
            'hashes': hashes,
            'location': location
        }
        try:
            response = self._request("POST", url, data=data, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent 移动种子失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 磁力解析：qB 暂停添加时也拉元数据（继承默认实现即可）
    # ------------------------------------------------------------------
