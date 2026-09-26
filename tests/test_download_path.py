"""
下载落盘目录保障单元测试：resolve_download_path_for_local / ensure_download_dir

对应缺陷：本程序（root）预建的目录属主是自己，下载器（容器内多为 abc=1000）
往里写会 Permission denied，qBittorrent 直接把任务置为 error。
"""
import os
import stat

import pytest
from unittest.mock import patch

from app.services.download_path import (
    ensure_download_dir,
    resolve_download_path_for_local,
)


class TestResolveDownloadPathForLocal:
    """未配置 root 时原样返回；配置了则按 / 拆段拼到 root 下"""

    def _config(self, paths):
        return patch("app.services.download_path.config.get",
                     side_effect=lambda key, default=None: paths if key == "paths" else default)

    def test_no_root_returns_path_as_is(self):
        with self._config({"download_root_path": "", "root_path": ""}):
            assert resolve_download_path_for_local("/downloads/a/b") == "/downloads/a/b"

    def test_download_root_takes_precedence(self):
        with self._config({"download_root_path": "/mnt/dl", "root_path": "/mnt/root"}):
            assert resolve_download_path_for_local("/downloads/a") == os.path.normpath("/mnt/dl/downloads/a")

    def test_root_path_fallback(self):
        with self._config({"root_path": "/mnt/root"}):
            assert resolve_download_path_for_local("/downloads/a") == os.path.normpath("/mnt/root/downloads/a")

    def test_relative_path_untouched(self):
        with self._config({"download_root_path": "/mnt/dl"}):
            assert resolve_download_path_for_local("relative/dir") == "relative/dir"

    def test_empty_path(self):
        with self._config({"download_root_path": "/mnt/dl"}):
            assert resolve_download_path_for_local("") == ""


class TestEnsureDownloadDir:
    """目录不存在则创建，存在则放开权限；任何失败都不抛出"""

    def test_creates_missing_dir(self, tmp_path):
        target = tmp_path / "dl" / "qbittorrent"
        with patch("app.services.download_path.resolve_download_path_for_local",
                   side_effect=lambda p: str(target)):
            assert ensure_download_dir("/downloads/qbittorrent") is True
        assert target.is_dir()

    def test_existing_dir_gets_world_writable(self, tmp_path):
        """已存在但属主是本程序（root）的目录，下载器写不进去——必须放开权限"""
        target = tmp_path / "dl"
        target.mkdir()
        os.chmod(target, 0o755)
        with patch("app.services.download_path.resolve_download_path_for_local",
                   side_effect=lambda p: str(target)):
            assert ensure_download_dir("/downloads/dl") is True
        assert stat.S_IMODE(os.stat(target).st_mode) == 0o777

    def test_empty_path_returns_false(self):
        assert ensure_download_dir("") is False
        assert ensure_download_dir("   ") is False

    def test_oserror_is_swallowed(self, tmp_path):
        """建目录失败不能连累下载：只记日志并返回 False"""
        target = tmp_path / "dl"
        with patch("app.services.download_path.resolve_download_path_for_local",
                   side_effect=lambda p: str(target)), \
             patch("app.services.download_path.os.makedirs",
                   side_effect=OSError("Permission denied")):
            assert ensure_download_dir("/downloads/dl") is False
