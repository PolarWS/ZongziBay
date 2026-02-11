import logging
import os
import re
import time
from typing import List

from app.core.config import config
from app.core.db import db
from app.core.qb_client import QBittorrentClient
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.notification import NotificationType
from app.schemas.task import AddTaskRequest

logger = logging.getLogger(__name__)


class TaskService:
    """下载任务创建、取消等核心业务"""

    def __init__(self):
        qb_config = config.get("qbittorrent", {})
        self.host = qb_config.get("host", "http://localhost:8080")
        self.username = qb_config.get("username", "admin")
        self.password = qb_config.get("password", "adminadmin")
        self.qb_client = QBittorrentClient(self.host, self.username, self.password)

    def add_task(self, request: AddTaskRequest) -> int:
        # 1. 确定路径：优先使用请求中的路径，否则按 type 选择配置
        if request.type == 'tv':
            default_source = config.get("paths.tv_download_path", "/dl/tv")
            default_target = config.get("paths.tv_target_path", "/nas/tv")
        elif request.type == 'movie':
            default_source = config.get("paths.movie_download_path", "/dl/movies")
            default_target = config.get("paths.movie_target_path", "/nas/movies")
        else:
            default_source = config.get("paths.default_download_path", "/downloads")
            default_target = config.get("paths.default_target_path", "/downloads")

        # 绝对路径直接用，相对路径拼接默认路径
        if request.sourcePath:
            if os.path.isabs(request.sourcePath):
                source_path = request.sourcePath
            else:
                source_path = os.path.join(default_source, request.sourcePath).replace('\\', '/')
        else:
            source_path = default_source

        if request.targetPath:
            if os.path.isabs(request.targetPath):
                target_path = request.targetPath
            else:
                target_path = os.path.join(default_target, request.targetPath).replace('\\', '/')
        else:
            target_path = default_target

        # 2. 数据库预插入（commit=False），失败时回滚
        conn = db.get_conn()
        try:
            task_id = db.insert_download_task(
                taskName=request.taskName,
                taskInfo=request.taskInfo,
                sourceUrl=request.sourceUrl,
                sourcePath=source_path,
                targetPath=target_path,
                taskStatus="downloading",
                commit=False
            )
            if request.file_tasks:
                for file_task in request.file_tasks:
                    db.insert_file_task(
                        downloadTaskId=task_id,
                        sourcePath=file_task.sourcePath,
                        targetPath=file_task.targetPath,
                        file_rename=file_task.file_rename,
                        file_status="pending",
                        commit=False
                    )
            logger.info(f"[TaskService] DB预插入成功 task_id={task_id}, 等待调用 qBittorrent...")

            # 3. 调用 qBittorrent API
            torrent_hash = None
            if request.sourceUrl.startswith("magnet:?"):
                match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', request.sourceUrl)
                if match:
                    torrent_hash = match.group(1).lower()

            if request.file_tasks and not torrent_hash:
                raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无法从链接解析Hash，不支持文件选择")

            # 有文件选择时先暂停添加，等元数据后设置优先级再恢复
            should_filter_files = bool(request.file_tasks)
            is_paused = should_filter_files
            success = self.qb_client.add_torrent(
                urls=request.sourceUrl,
                save_path=source_path,
                is_paused=is_paused
            )
            if not success:
                logger.error(f"[TaskService] qBittorrent 添加任务失败: url={request.sourceUrl}")
                raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="无法添加到 qBittorrent")

            if should_filter_files:
                try:
                    self._filter_torrent_files(torrent_hash, request.file_tasks)  # 设置选中 1，未选 0
                    self.qb_client.resume_torrents(torrent_hash)
                except Exception as e:
                    logger.error(f"[TaskService] 过滤文件失败: {e}")
                    raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"过滤文件失败: {e}")

            # 4. 提交事务，添加通知
            conn.commit()
            logger.info(f"[TaskService] 任务添加成功: task_id={task_id}, 已同步至 DB 和 qBittorrent")
            db.insert_notification(title="添加任务成功", content=f"任务 {request.taskName} 已开始下载", type=NotificationType.SUCCESS.value)
            return task_id

        except Exception as e:
            logger.error(f"[TaskService] 添加任务异常, 执行回滚: {e}")
            conn.rollback()  # 防止脏数据
            if isinstance(e, BusinessException):
                raise e
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"添加任务失败: {str(e)}")

    def cancel_task(self, task_id: int) -> bool:
        """取消任务，仅限 downloading 状态"""
        task = db.get_download_task_by_id(task_id)
        if not task:
            raise BusinessException(code=ErrorCode.NOT_FOUND_ERROR, message="任务不存在")
        if task['taskStatus'] != 'downloading':
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="只有下载中的任务可以取消")

        source_url = task['sourceUrl']
        torrent_hash = None
        if source_url and source_url.startswith("magnet:?"):
            match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', source_url)
            if match:
                torrent_hash = match.group(1).lower()

        if torrent_hash:
            try:
                self.qb_client.delete_torrents(torrent_hash, delete_files=True)
                logger.info(f"[TaskService] qBittorrent 任务删除成功 hash={torrent_hash}")
            except Exception as e:
                logger.error(f"[TaskService] 从 qBittorrent 删除任务失败: {e}")

        db.update_download_task_status(task_id, "cancelled")
        db.update_file_tasks_by_download_task_id(task_id, "cancelled")
        db.insert_notification(title="任务已取消", content=f"任务 {task['taskName']} 已被取消", type=NotificationType.WARNING.value)
        return True

    def _filter_torrent_files(self, torrent_hash: str, file_tasks: list):
        """等待元数据并设置文件优先级（0=不下载，1=正常）"""
        timeout = 60
        start_time = time.time()
        metadata_fetched = False

        while time.time() - start_time < timeout:
            info = self.qb_client.get_torrent_info(torrent_hash)
            if info and info.get('total_size', 0) > 0:  # total_size > 0 表示元数据已获取
                metadata_fetched = True
                break
            time.sleep(1)

        if not metadata_fetched:
            raise Exception("获取种子元数据超时")

        files = self.qb_client.get_torrent_files(torrent_hash)
        if not files:
            raise Exception("种子文件列表为空")

        target_files = set()
        for ft in file_tasks:  # 构建需下载的文件路径集合
            p = ft.sourcePath.replace('\\', '/')
            target_files.add(p)

        ids_to_download = []
        ids_to_skip = []
        for idx, f in enumerate(files):  # 按路径匹配分配优先级
            f_name = f.get('name', '').replace('\\', '/')
            if f_name in target_files:
                ids_to_download.append(idx)
            else:
                ids_to_skip.append(idx)

        if ids_to_skip:
            self.qb_client.set_file_priority(torrent_hash, ids_to_skip, 0)
        if ids_to_download:
            self.qb_client.set_file_priority(torrent_hash, ids_to_download, 1)
        logger.info(f"已设置文件优先级: 下载 {len(ids_to_download)} 个, 跳过 {len(ids_to_skip)} 个")


task_service = TaskService()
