import logging
import os
import re
import time
import urllib.parse
from typing import List

from app.core.config import config
from app.core.db import db
from app.core.qb_client import QBittorrentClient
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.notification import NotificationType
from app.schemas.task import AddTaskRequest
from app.services.magnet_service import normalize_info_hash

logger = logging.getLogger(__name__)


class TaskService:
    """下载任务创建、取消等核心业务"""

    def __init__(self):
        qb_config = config.get("qbittorrent", {})
        self.host = qb_config.get("host", "http://localhost:8080")
        self.username = qb_config.get("username", "admin")
        self.password = qb_config.get("password", "adminadmin")
        self.qb_client = QBittorrentClient(self.host, self.username, self.password)
        self.trackers: List[str] = config.get("trackers", [])

    @staticmethod
    def _append_trackers(magnet_link: str, trackers: List[str]) -> str:
        """在磁力链接后追加 tracker 列表"""
        if not magnet_link or not trackers:
            return magnet_link or ""
        result = magnet_link.rstrip("&")
        for tr in trackers:
            if tr:
                result += f"&tr={urllib.parse.quote(tr, safe='')}"
        return result

    def add_task(self, request: AddTaskRequest) -> int:
        # 0. 提取 Hash 并检查 qBittorrent 中是否已存在该任务
        torrent_hash = None
        if request.sourceUrl.startswith("magnet:?"):
            match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', request.sourceUrl)
            if match:
                torrent_hash = normalize_info_hash(match.group(1))

        if torrent_hash:
            existing_info = self.qb_client.get_torrent_info(torrent_hash)
            if existing_info:
                # 任务已存在，复用现有任务
                logger.info(f"[TaskService] 检测到任务已存在于 qBittorrent: {torrent_hash}，状态: {existing_info.get('state')}")
                # 根据当前状态判断后续操作
                # 无论是已完成还是下载中，都视为添加成功，并插入 DB 记录以便监控接管
                # 注意：如果任务已经在 DB 中存在，可能需要避免重复插入或更新
                # 这里暂且允许插入新记录（可能用户想重新走一遍流程），Monitor 会接管
                
                # 如果是已完成任务，可能需要直接触发后续处理（Monitor 会负责）
                # 这里我们只负责记录日志，并不直接执行复制/移动，交给 Monitor 的循环去发现
                pass

        # 1. 确定路径：优先使用请求中的路径，否则按 type 选择配置
        if request.type == 'tv':
            default_source = config.get("paths.tv_download_path", "/dl/tv")
            default_target = config.get("paths.tv_target_path", "/nas/tv")
        elif request.type == 'anime':
            default_source = config.get("paths.anime_download_path", "/dl/anime")
            default_target = config.get("paths.anime_target_path", "/nas/anime")
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
            # 如果之前已经检测到任务存在，则跳过 add_torrent
            is_new_task = True
            if torrent_hash:
                 existing_info = self.qb_client.get_torrent_info(torrent_hash)
                 if existing_info:
                     logger.info(f"[TaskService] 任务已存在于 qB，跳过添加: {torrent_hash}")
                     is_new_task = False
                     
                     # 如果需要过滤文件，即使是旧任务也尝试重新设置优先级
                     if request.file_tasks:
                         try:
                             self._filter_torrent_files(torrent_hash, request.file_tasks)
                         except Exception as e:
                             logger.warning(f"为已存在的任务设置文件过滤失败: {e}")

            if is_new_task:
                if request.sourceUrl.startswith("magnet:?") and not torrent_hash:
                    match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', request.sourceUrl)
                    if match:
                        torrent_hash = normalize_info_hash(match.group(1))

                if request.file_tasks and not torrent_hash:
                    raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无法从链接解析Hash，不支持文件选择")

                # 下载时追加 trackers 到磁力链接
                download_url = self._append_trackers(request.sourceUrl, self.trackers)

                # 有文件选择时先暂停添加，等元数据后设置优先级再恢复
                should_filter_files = bool(request.file_tasks)
                is_paused = should_filter_files
                success = self.qb_client.add_torrent(
                    urls=download_url,
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
            else:
                 logger.info(f"[TaskService] 复用现有任务，未执行 add_torrent")

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
        """取消任务：下载中/等待中可取消并删文件；做种中可取消并从 qB 移除（不删文件，适合复制完成的任务）"""
        task = db.get_download_task_by_id(task_id)
        if not task:
            raise BusinessException(code=ErrorCode.NOT_FOUND_ERROR, message="任务不存在")
        status = task.get('taskStatus') or ''
        if status not in ('downloading', 'pending', 'seeding'):
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="只有下载中、等待中或做种中的任务可以取消")

        source_url = task['sourceUrl']
        torrent_hash = None
        if source_url and (source_url.startswith("magnet:?") or source_url.startswith("magnet:")):
            match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', source_url)
            if match:
                torrent_hash = normalize_info_hash(match.group(1))

        if torrent_hash:
            try:
                # 做种中取消：若文件已在目标目录（qb 移动过）则不删文件；若仍在临时下载目录则删文件
                if status == 'seeding':
                    delete_files = self._seeding_files_in_temp_folder(torrent_hash, task)
                else:
                    delete_files = True
                self.qb_client.delete_torrents(torrent_hash, delete_files=delete_files)
                # 确认 qB 已移除后再更新 DB 和发通知（做种时轮询几次）
                if status == 'seeding':
                    for _ in range(5):
                        time.sleep(0.5)
                        if not self.qb_client.get_torrent_info(torrent_hash):
                            break
                    else:
                        if self.qb_client.get_torrent_info(torrent_hash):
                            raise BusinessException(
                                code=ErrorCode.OPERATION_ERROR,
                                message="qBittorrent 中仍存在该任务，取消失败，请稍后重试"
                            )
                logger.info(f"[TaskService] qBittorrent 任务删除成功 hash={torrent_hash} delete_files={delete_files}")
            except BusinessException:
                raise
            except Exception as e:
                logger.error(f"[TaskService] 从 qBittorrent 删除任务失败: {e}")
                raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"从 qBittorrent 取消失败: {e}")

        db.update_download_task_status(task_id, "cancelled")
        db.update_file_tasks_by_download_task_id(task_id, "cancelled")
        msg = "任务已取消（已从 qB 移除做种）" if status == 'seeding' else "任务已取消"
        db.insert_notification(title="任务已取消", content=f"任务 {task['taskName']} {msg}", type=NotificationType.WARNING.value)
        return True

    def _norm_path(self, p: str) -> str:
        """路径规范化便于比较"""
        if not p or not str(p).strip():
            return (p or "").strip()
        p = str(p).replace("\\", os.sep).replace("/", os.sep)
        p = os.path.normpath(p).rstrip(os.sep)
        if os.name == "nt":
            p = os.path.normcase(p)
        return p

    def _seeding_files_in_temp_folder(self, torrent_hash: str, task: dict) -> bool:
        """做种时文件是否仍在临时下载目录（True=在临时目录要删文件，False=已在目标目录不删）"""
        try:
            info = self.qb_client.get_torrent_info(torrent_hash)
            if not info:
                return True  # 拿不到信息时默认删文件
            current_save = (info.get("save_path") or "").replace("\\", "/")
            # 任务目标路径（与 task_monitor._get_task_qb_target_path 一致）
            final_target = (task.get("targetPath") or "").replace("\\", "/")
            file_tasks = db.get_file_tasks(task.get("id") or 0)
            if file_tasks:
                for ft in file_tasks:
                    ft_target = (ft.get("targetPath") or "").replace("\\", "/")
                    if ft_target:
                        final_target = (final_target.rstrip("/") + "/" + ft_target) if final_target else ft_target
                        break
            default_target = config.get("paths.default_target_path", "")
            if final_target and not (final_target.startswith("/") or (len(final_target) > 1 and final_target[1] == ":")):
                final_target = (default_target.rstrip("/") + "/" + final_target) if default_target else final_target
            final_target = final_target.replace("\\", "/")
            if not final_target:
                return True
            if self._norm_path(current_save) == self._norm_path(final_target):
                return False  # 已在目标目录，不删文件
            return True  # 仍在临时目录，删文件
        except Exception as e:
            logger.warning(f"[TaskService] 判断做种文件位置失败: {e}，默认删除临时文件")
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
