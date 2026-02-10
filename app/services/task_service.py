import logging
import re
import time
from app.core.db import db
from app.core.qb_client import QBittorrentClient
from app.core.config import Config
from app.schemas.task import AddTaskRequest
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)

class TaskService:
    """
    任务服务类
    负责处理下载任务的创建、状态更新等核心业务逻辑
    """
    def __init__(self):
        # 加载配置
        self.config = Config()
        self.qb_config = self.config.get("qbittorrent", {})
        
        # 从配置中读取 qBittorrent 连接信息
        self.host = self.qb_config.get("host", "http://localhost:8080")
        self.username = self.qb_config.get("username", "admin")
        self.password = self.qb_config.get("password", "adminadmin")
        
        # 初始化 qBittorrent 客户端
        self.qb_client = QBittorrentClient(self.host, self.username, self.password)

    def add_task(self, request: AddTaskRequest) -> int:
        # 1. 确定路径配置
        # 优先使用请求中的路径，如果未提供，则根据 type 选择配置
        if request.type == 'tv':
            default_source = self.config.get("paths.tv_download_path", "/dl/tv")
            default_target = self.config.get("paths.tv_target_path", "/nas/tv")
        elif request.type == 'movie':
            default_source = self.config.get("paths.movie_download_path", "/dl/movies")
            default_target = self.config.get("paths.movie_target_path", "/nas/movies")
        else:
            # default or other
            default_source = self.config.get("paths.default_download_path", "/downloads")
            default_target = self.config.get("paths.default_target_path", "/downloads")

        if request.sourcePath:
            # 如果是绝对路径则直接使用，如果是相对路径则拼接默认路径
            import os
            if os.path.isabs(request.sourcePath):
                source_path = request.sourcePath
            else:
                source_path = os.path.join(default_source, request.sourcePath).replace('\\', '/')
        else:
            source_path = default_source
        
        if request.targetPath:
            import os
            if os.path.isabs(request.targetPath):
                target_path = request.targetPath
            else:
                target_path = os.path.join(default_target, request.targetPath).replace('\\', '/')
        else:
            target_path = default_target
        
        # 获取数据库连接
        conn = db.get_conn()
        
        try:
            # 2. 数据库预插入 (commit=False)
            # 插入主下载任务
            task_id = db.insert_download_task(
                taskName=request.taskName,
                taskInfo=request.taskInfo,
                sourceUrl=request.sourceUrl,
                sourcePath=source_path,
                targetPath=target_path,
                taskStatus="downloading",
                commit=False
            )
            
            # 插入关联的文件操作任务
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
            # 提取 hash (如果是 magnet)
            torrent_hash = None
            if request.sourceUrl.startswith("magnet:?"):
                match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', request.sourceUrl)
                if match:
                    torrent_hash = match.group(1).lower()

            if request.file_tasks and not torrent_hash:
                raise BusinessException(code=ErrorCode.PARAMS_ERROR, message="无法从链接解析Hash，不支持文件选择")

            # 如果有选中的文件，我们需要：
            # 1. 暂停添加任务
            # 2. 等待元数据
            # 3. 设置文件优先级（选中的为 1，其他的为 0）
            # 4. 恢复任务
            
            should_filter_files = bool(request.file_tasks)
            is_paused = should_filter_files # 如果需要过滤文件，则先暂停

            # 注意: qB 的 save_path 应该是 source_path (临时下载目录)
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
                    self._filter_torrent_files(torrent_hash, request.file_tasks)
                    # 过滤完成后，恢复下载
                    self.qb_client.resume_torrents(torrent_hash)
                except Exception as e:
                    logger.error(f"[TaskService] 过滤文件失败: {e}")
                    # 即使过滤失败，也尝试恢复下载（或者抛出异常回滚？）
                    # 这里选择抛出异常，因为用户明确指定了文件
                    raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"过滤文件失败: {e}")

            # 4. 一切顺利，提交数据库事务
            conn.commit()
            logger.info(f"[TaskService] 任务添加成功: task_id={task_id}, 已同步至 DB 和 qBittorrent")
            
            # 5. 添加通知
            db.insert_notification(title="添加任务成功", content=f"任务 {request.taskName} 已开始下载", type=NotificationType.SUCCESS.value)
            
            return task_id

        except Exception as e:
            # 异常处理: 无论发生什么错误，都要回滚数据库，防止产生脏数据
            logger.error(f"[TaskService] 添加任务异常, 执行回滚: {e}")
            conn.rollback() 
            # 重新抛出业务异常
            if isinstance(e, BusinessException):
                raise e
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message=f"添加任务失败: {str(e)}")

    def cancel_task(self, task_id: int) -> bool:
        """
        取消任务
        只有 'downloading' 状态的任务可以取消
        """
        # 1. 获取任务
        task = db.get_download_task_by_id(task_id)
        if not task:
            raise BusinessException(code=ErrorCode.NOT_FOUND, message="任务不存在")
        
        # 2. 检查状态
        if task['taskStatus'] != 'downloading':
            raise BusinessException(code=ErrorCode.OPERATION_ERROR, message="只有下载中的任务可以取消")
            
        # 3. 尝试从 qBittorrent 删除
        # 需要提取 hash
        source_url = task['sourceUrl']
        torrent_hash = None
        if source_url and source_url.startswith("magnet:?"):
             match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', source_url)
             if match:
                 torrent_hash = match.group(1).lower()
        
        if torrent_hash:
            try:
                # 尝试删除并删除文件
                self.qb_client.delete_torrents(torrent_hash, delete_files=True)
                logger.info(f"[TaskService] qBittorrent 任务删除成功 hash={torrent_hash}")
            except Exception as e:
                logger.error(f"[TaskService] 从 qBittorrent 删除任务失败: {e}")
                # 继续更新数据库状态，即使 qB 删除失败 (可能是已经不在 qB 中了)
        
        # 4. 更新数据库状态
        # 更新主任务状态
        db.update_download_task_status(task_id, "cancelled")
        # 同时更新关联的文件任务状态
        db.update_file_tasks_by_download_task_id(task_id, "cancelled")
        
        # 5. 添加通知
        db.insert_notification(title="任务已取消", content=f"任务 {task['taskName']} 已被取消", type=NotificationType.WARNING.value)

        return True

    def _filter_torrent_files(self, torrent_hash: str, file_tasks: list):
        """
        等待元数据并过滤文件
        """
        # 等待元数据 (最多 60 秒)
        timeout = 60
        start_time = time.time()
        metadata_fetched = False
        
        while time.time() - start_time < timeout:
            info = self.qb_client.get_torrent_info(torrent_hash)
            # 检查 total_size > 0 
            if info and info.get('total_size', 0) > 0:
                metadata_fetched = True
                break
            time.sleep(1)
            
        if not metadata_fetched:
            raise Exception("获取种子元数据超时")
            
        # 获取文件列表
        files = self.qb_client.get_torrent_files(torrent_hash)
        if not files:
            raise Exception("种子文件列表为空")
            
        # 构建需要下载的文件路径集合
        target_files = set()
        for ft in file_tasks:
            # 统一使用 /
            p = ft.sourcePath.replace('\\', '/')
            target_files.add(p)
            
        # 确定优先级
        # 0 = do not download, 1 = normal
        ids_to_download = []
        ids_to_skip = []
        
        for idx, f in enumerate(files):
            f_name = f.get('name', '').replace('\\', '/')
            if f_name in target_files:
                ids_to_download.append(idx)
            else:
                ids_to_skip.append(idx)
                
        # 设置优先级
        if ids_to_skip:
            self.qb_client.set_file_priority(torrent_hash, ids_to_skip, 0)
            
        if ids_to_download:
            self.qb_client.set_file_priority(torrent_hash, ids_to_download, 1)
            
        logger.info(f"已设置文件优先级: 下载 {len(ids_to_download)} 个, 跳过 {len(ids_to_skip)} 个")

# 导出
task_service = TaskService()
