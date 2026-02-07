import threading
import time
import logging
import re
import os
from app.core import db
from app.services.magnet_service import magnet_service

logger = logging.getLogger(__name__)

class TaskMonitor:
    """
    任务监控类
    定时检查数据库中的下载任务，同步 qBittorrent 的状态
    """
    def __init__(self, interval: int = 10):
        self.interval = interval
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def start(self):
        """启动监控线程"""
        if not self.running:
            # 启动前检查连接
            if not self._check_connection():
                logger.error("无法连接到 qBittorrent，任务监控服务未启动。请检查配置或服务状态。")
                return

            self.running = True
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info("任务监控服务已启动")

    def _check_connection(self) -> bool:
        """检查 qBittorrent 连接"""
        try:
            client = magnet_service._get_client()
            if client is None:
                return False
            # 尝试调用一个轻量级接口验证是否真正连接成功
            client.get_version()
            return True
        except Exception as e:
            logger.error(f"qBittorrent 连接检查失败: {e}")
            return False

    def stop(self):
        """停止监控线程"""
        self.running = False
        self._stop_event.set()
        if self.thread:
            # 如果线程正在 sleep，设置 event 会立即唤醒它
            # join 设置超时，防止死锁
            self.thread.join(timeout=2)
            logger.info("任务监控服务已停止")

    def _run_loop(self):
        """循环检查任务状态"""
        while self.running and not self._stop_event.is_set():
            try:
                self._check_tasks()
            except Exception as e:
                logger.error(f"任务监控循环出错: {e}")
            
            # 使用 event.wait 代替 time.sleep，这样可以被立即中断
            if self._stop_event.wait(self.interval):
                # 如果 wait 返回 True，说明 event 被 set 了（要求停止）
                break

    def _extract_torrent_hash(self, task_name: str, source_url: str) -> str | None:
        if re.match(r'^[a-fA-F0-9]{40}$', task_name):
            return task_name.lower()
        if source_url and source_url.startswith("magnet:?"):
            match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', source_url)
            if match:
                return match.group(1).lower()
        return None

    def _process_file_renames(self, client, task_id: int, torrent_hash: str, file_tasks: list):
        if not file_tasks:
            return
        logger.info(f"开始处理任务 {task_id} 的文件重命名 ({len(file_tasks)} 个文件)...")
        for ft in file_tasks:
            if ft['file_status'] == 'completed':
                continue
            old_path = ft['sourcePath']
            file_rename = ft['file_rename']
            if not file_rename or not old_path:
                continue
            old_path = old_path.replace('\\', '/')
            file_rename = file_rename.replace('\\', '/')
            if '/' not in file_rename:
                if '/' in old_path:
                    dir_name = os.path.dirname(old_path)
                    new_path = f"{dir_name}/{file_rename}"
                else:
                    new_path = file_rename
            else:
                new_path = file_rename
            try:
                norm_old = os.path.normpath(old_path)
                norm_new = os.path.normpath(new_path)
                if norm_old == norm_new:
                    db.update_file_task_status(ft['id'], 'completed')
                    continue
            except Exception:
                if old_path == new_path:
                    db.update_file_task_status(ft['id'], 'completed')
                    continue
            logger.info(f"正在重命名文件: {old_path} -> {new_path}")
            try:
                if client.rename_file(torrent_hash, old_path, new_path):
                    db.update_file_task_status(ft['id'], 'completed')
                    logger.info(f"重命名成功: {old_path} -> {new_path}")
                    db.insert_notification(title="重命名成功", content=f"{old_path} -> {new_path}", type="success")
                else:
                    if client.rename_folder(torrent_hash, old_path, new_path):
                        db.update_file_task_status(ft['id'], 'completed')
                        logger.info(f"文件夹重命名成功: {old_path} -> {new_path}")
                        db.insert_notification(title="文件夹重命名成功", content=f"{old_path} -> {new_path}", type="success")
                    else:
                        logger.error(f"重命名失败: {old_path} -> {new_path}")
                        db.update_file_task_status(ft['id'], 'failed', "QB API returned fail")
                        db.insert_notification(title="重命名失败", content=f"{old_path} -> {new_path}: QB API fail", type="error")
            except Exception as e:
                logger.error(f"重命名异常: {e}")
                db.update_file_task_status(ft['id'], 'failed', str(e))
                db.insert_notification(title="重命名异常", content=f"{old_path} -> {new_path}: {e}", type="error")

    def _maybe_move_location(self, client, task_id: int, torrent_hash: str, torrent_info: dict, target_path: str):
        if not target_path:
            logger.info(f"任务 {task_id} 目标路径为空，跳过移动")
            return

        from app.core.config import Config
        config = Config()
        root_path = config.get("paths.root_path", "")
        default_target_path = config.get("paths.default_target_path", "")

        # 1. 构建传给 qBittorrent 的路径 (qb_move_path)
        # 如果 target_path 是绝对路径，则直接使用
        # 如果是相对路径，则拼接到 default_target_path 后面
        if os.path.isabs(target_path):
            qb_move_path = target_path
        else:
            if default_target_path:
                qb_move_path = os.path.join(default_target_path, target_path)
            else:
                qb_move_path = target_path
        
        # 规范化路径分隔符为 / (qb 通常使用 /)
        qb_move_path = qb_move_path.replace('\\', '/')

        # 2. 构建本地用于创建文件夹的路径 (local_mkdir_path)
        # 如果配置了 root_path，则将 qb_move_path 视为相对 root_path 的路径
        if root_path:
            # 去掉 qb_move_path 开头的 / 或 \ 以及盘符，防止 os.path.join 将其视为绝对路径
            # Windows 下 splitdrive 可以分离盘符
            _, path_without_drive = os.path.splitdrive(qb_move_path)
            rel_path = path_without_drive.lstrip('/\\')
            local_mkdir_path = os.path.join(root_path, rel_path)
        else:
            local_mkdir_path = qb_move_path

        current_save_path = torrent_info.get('save_path', '')
        try:
            p1 = os.path.normpath(current_save_path)
            p2 = os.path.normpath(qb_move_path)
        except Exception:
            p1 = current_save_path
            p2 = qb_move_path
        
        # logger.debug(f"Task {task_id} path check: current='{p1}', target='{p2}', local_mkdir='{local_mkdir_path}'")

        if p1 != p2:
            # 3. 尝试预创建目标文件夹
            if local_mkdir_path:
                try:
                    local_mkdir_path = os.path.normpath(local_mkdir_path)
                    if not os.path.exists(local_mkdir_path):
                        logger.info(f"目标文件夹不存在，尝试本地预创建: {local_mkdir_path}")
                        os.makedirs(local_mkdir_path, exist_ok=True)
                except Exception as e:
                    logger.warning(f"本地创建文件夹失败 {local_mkdir_path}: {e}，将尝试让 qBittorrent 自动处理")

            logger.info(f"正在移动任务 {task_id} 到 {qb_move_path}")
            if client.set_location(torrent_hash, qb_move_path):
                logger.info(f"移动指令已发送: {qb_move_path}")
                db.insert_notification(title="开始移动任务", content=f"任务 {task_id} 正在移动到 {qb_move_path}", type="info")
            else:
                logger.error(f"移动失败: {qb_move_path}")
                db.insert_notification(title="移动任务失败", content=f"任务 {task_id} 移动到 {qb_move_path} 失败", type="error")

    def _handle_completed_task(self, client, task: dict, torrent_hash: str, torrent_info: dict):
        file_tasks = []
        try:
            file_tasks = db.get_file_tasks(task['id'])
            self._process_file_renames(client, task['id'], torrent_hash, file_tasks)
        except Exception as e:
            logger.error(f"处理文件重命名任务失败: {e}")
        
        try:
            # 确定最终移动的目标路径
            # 优先使用 file_task 中的 targetPath (如果有)
            # 假设一个种子里的文件都去同一个目标目录 (通常是这样)
            final_target_path = task['targetPath']
            
            if file_tasks:
                # 寻找第一个非空的 targetPath
                for ft in file_tasks:
                    if ft.get('targetPath'):
                        final_target_path = ft['targetPath']
                        break
            
            self._maybe_move_location(client, task['id'], torrent_hash, torrent_info, final_target_path)
        except Exception as e:
            logger.error(f"处理文件移动任务失败: {e}")

    def _check_tasks(self):
        """检查所有活跃任务的状态"""
        # 1. 从数据库获取活跃任务
        active_tasks = db.get_active_tasks()
        if not active_tasks:
            return

        # 2. 获取 qBittorrent 客户端
        client = magnet_service._get_client()
        if not client:
            logger.warning("无法连接 qBittorrent，跳过本次检查")
            return

        for task in active_tasks:
            try:
                torrent_hash = self._extract_torrent_hash(task['taskName'], task.get('sourceUrl', ''))
                if not torrent_hash:
                    logger.warning(f"无法获取任务 {task['id']} 的 Hash，跳过检查。Name={task['taskName']}")
                    continue
                
                # 3. 获取种子信息
                torrent_info = client.get_torrent_info(torrent_hash)
                
                if not torrent_info:
                    # 种子在 qbt 中不存在，可能是被手动删除了，或者是磁力解析还没开始下载
                    
                    # 如果当前是 'cancelled' 状态，直接忽略（这是正常的，因为取消任务会删除 qbt 任务）
                    if task['taskStatus'] == 'cancelled':
                        continue

                    # 这里可以标记为 error 或者 waiting
                    logger.warning(f"任务 {task['id']} (Hash: {torrent_hash}) 在 qBittorrent 中未找到")
                        
                    # 如果不是 cancelled，可能是异常消失，或者是磁力链接还没添加进去
                    # 暂时不更新状态，以免误判
                    continue

                # 4. 解析状态
                qb_state = torrent_info.get('state', '')
                progress = torrent_info.get('progress', 0) * 100  # 0.0 - 1.0 -> 0 - 100
                
                new_status = self._map_status(qb_state)
                
                # 5. 更新数据库
                # 只有状态改变或进度有显著变化才更新，减少 DB 写入
                current_status = task['taskStatus']
                
                # 如果是 error 状态，尝试自动恢复 (用户要求：看见错误尝试启动运行)
                if new_status == 'error':
                    if current_status != 'error':
                        db.insert_notification(title="任务出错", content=f"任务 {task['taskName']} 状态异常 ({qb_state})，尝试自动恢复", type="warning")

                    logger.warning(f"任务 {task['id']} 状态异常 ({qb_state})，尝试自动恢复...")
                    try:
                        client.resume_torrents(torrent_hash)
                    except Exception as e:
                        logger.error(f"尝试恢复任务 {task['id']} 失败: {e}")

                # 6. 处理已完成任务 (例如后续处理)
                if new_status == 'completed' and current_status != 'completed':
                    logger.info(f"任务 {task['id']} 已完成，开始执行后续处理: {torrent_info.get('name')}")
                    db.insert_notification(title="任务下载完成", content=f"任务 {task['taskName']} 下载完成，开始后续处理", type="success")
                    try:
                        # 先设置为 moving 状态，让前端感知到正在处理
                        db.update_task_status(task['id'], "moving", progress)
                        
                        self._handle_completed_task(client, task, torrent_hash, torrent_info)
                        
                        # 后续处理成功后，才更新状态为 completed
                        db.update_task_status(task['id'], new_status, progress)
                        db.insert_notification(title="任务处理完成", content=f"任务 {task['taskName']} 后续处理完成", type="success")
                    except Exception as e:
                        logger.error(f"任务 {task['id']} 后续处理失败: {e}")
                        db.insert_notification(title="任务处理失败", content=f"任务 {task['taskName']} 后续处理失败: {e}", type="error")
                        # 处理失败，不更新为 completed，仅更新进度，保留原状态以便下次重试
                        # 或者设置为 error 状态？ 暂时保留原状态
                        db.update_task_status(task['id'], current_status, progress)
                else:
                    # 其他情况，直接更新状态和进度
                    db.update_task_status(task['id'], new_status, progress)
                    
            except Exception as e:
                logger.error(f"检查任务 {task.get('id')} 失败: {e}")

    def _map_status(self, qb_state: str) -> str:
        """
        将 qBittorrent 状态映射为系统状态
        downloading:下载中, moving:移动中, completed:已完成, cancelled:已取消, error:错误
        """
        # qBittorrent states: 
        # downloading, stalledDL, metaDL, pausedDL, queuedDL, checkingDL
        # uploading, stalledUP, queuedUP, checkingUP, forcedUP
        # error, missingFiles
        
        if qb_state in ['uploading', 'stalledUP', 'queuedUP', 'checkingUP', 'forcedUP', 'pausedUP']:
            return 'completed'
        elif qb_state in ['error', 'missingFiles']:
            return 'error'
        else:
            # downloading, stalledDL, metaDL, pausedDL, queuedDL, checkingDL
            # and any unknown states
            return 'downloading'

# 全局单例
task_monitor = TaskMonitor()
