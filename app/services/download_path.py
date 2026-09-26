"""下载落盘目录的公共处理。

本程序与下载器在容器化部署下常以不同用户运行（本程序多为 root，下载器由
PUID/PGID 指定的普通用户，如 linuxserver 镜像的 abc=1000）。把路径交给下载器
之前，如果该目录是本程序预建的（属主 root、权限 755），下载器往里写会
Permission denied：qBittorrent 会把任务直接置为 error，自身的 WebUI 日志里
只有一句 `File error alert ... error: Permission denied`，业务侧只能观察到一个
没有原因的 error 状态，很难反查。task_monitor 对归档目标已有同样的处理
（_ensure_writable_dir），这里补上下载侧。
"""

import logging
import os

from app.core.config import config

logger = logging.getLogger(__name__)


def resolve_download_path_for_local(path: str) -> str:
    """把下载器侧路径解析为本机可访问路径（download_root_path / root_path）。

    与 task_monitor._resolve_path_for_local(for_target=False) 同一套规则：
    未配置 root 时说明本程序与下载器看到的是同一路径，原样返回。
    """
    if not path or not path.strip():
        return path or ""
    paths_cfg = config.get("paths", {}) or {}
    root = paths_cfg.get("download_root_path") or paths_cfg.get("root_path") or ""
    if not root:
        return path
    normalized = path.replace("\\", "/").strip()
    if not normalized.startswith("/"):
        return path
    rel = normalized.lstrip("/")
    if not rel:
        return root
    # 按 / 拆段再 join，避免 Windows 下整段被当成单层目录名
    return os.path.normpath(os.path.join(root, *rel.split("/")))


def ensure_download_dir(path: str) -> bool:
    """确保下载器要写入的目录存在、且下载器进程能写入。

    只处理**叶子目录**，不动调用方配置的上级目录：上级由用户自己创建，
    权限也该由用户掌握。

    失败只记日志并返回 False，绝不抛出——建不出目录时仍按原行为把路径交给
    下载器，由下载器自己尝试创建，不能因为这一步反而让下载失败。
    """
    if not path or not path.strip():
        return False
    local_path = resolve_download_path_for_local(path)
    try:
        os.makedirs(local_path, exist_ok=True)
        # 目录可能是本轮之前由本程序（root）建的，已存在也要放开权限，
        # 否则下载器仍然写不进去
        os.chmod(local_path, 0o777)
        return True
    except OSError as e:
        logger.warning(f"预创建下载目录失败 {local_path}: {e}，将交由下载器自行处理")
        return False
