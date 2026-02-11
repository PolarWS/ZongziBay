import logging
import os
import re
import threading
import time
from typing import List

from app.core import db
from app.core.config import config
from app.schemas.notification import NotificationType
from app.services.magnet_service import magnet_service

logger = logging.getLogger(__name__)


class TaskMonitor:
    """定时检查下载任务，同步 qBittorrent 状态并执行后续处理"""

    def __init__(self, interval: int = 10):
        self.interval = interval
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def start(self):
        """启动监控线程"""
        if not self.running:
            if not self._check_connection():
                logger.error("无法连接到 qBittorrent，任务监控服务未启动。请检查配置或服务状态。")
                return
            self.running = True
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info("任务监控服务已启动")

    def stop(self):
        """停止监控线程"""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
            logger.info("任务监控服务已停止")

    def _check_connection(self) -> bool:
        """检查 qBittorrent 连接"""
        try:
            client = magnet_service._get_client()
            if client is None:
                return False
            client.get_version()
            return True
        except Exception as e:
            logger.error(f"qBittorrent 连接检查失败: {e}")
            return False

    def _run_loop(self):
        """循环检查任务状态"""
        while self.running and not self._stop_event.is_set():
            try:
                self._check_tasks()
            except Exception as e:
                logger.error(f"任务监控循环出错: {e}")
            if self._stop_event.wait(self.interval):  # 可被 stop 立即唤醒
                break

    def _check_tasks(self):
        """检查所有活跃任务的状态"""
        active_tasks = db.get_active_tasks()
        if not active_tasks:
            return

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

                torrent_info = client.get_torrent_info(torrent_hash)
                if not torrent_info:
                    if task['taskStatus'] == 'cancelled':  # 取消后 qB 已删除，正常忽略
                        continue
                    logger.warning(f"任务 {task['id']} (Hash: {torrent_hash}) 在 qBittorrent 中未找到")
                    continue

                qb_state = torrent_info.get('state', '')
                progress = torrent_info.get('progress', 0) * 100
                new_status = self._map_status(qb_state)
                current_status = task['taskStatus']

                # error 状态尝试自动恢复
                if new_status == 'error':
                    if current_status != 'error':
                        db.insert_notification(title="任务出错", content=f"任务 {task['taskName']} 状态异常 ({qb_state})，尝试自动恢复", type=NotificationType.WARNING.value)
                    logger.warning(f"任务 {task['id']} 状态异常 ({qb_state})，尝试自动恢复...")
                    try:
                        client.resume_torrents(torrent_hash)
                    except Exception as e:
                        logger.error(f"尝试恢复任务 {task['id']} 失败: {e}")

                # 任务刚完成：执行重命名、移动等后续处理
                if new_status == 'completed' and current_status != 'completed':
                    logger.info(f"任务 {task['id']} 已完成，开始执行后续处理: {torrent_info.get('name')}")
                    db.insert_notification(title="任务下载完成", content=f"任务 {task['taskName']} 下载完成，开始后续处理", type=NotificationType.SUCCESS.value)
                    try:
                        db.update_task_status(task['id'], "moving", progress)
                        self._handle_completed_task(client, task, torrent_hash, torrent_info)
                        db.update_task_status(task['id'], new_status, progress)
                        db.insert_notification(title="任务处理完成", content=f"任务 {task['taskName']} 后续处理完成", type=NotificationType.SUCCESS.value)
                    except Exception as e:
                        logger.error(f"任务 {task['id']} 后续处理失败: {e}")
                        db.insert_notification(title="任务处理失败", content=f"任务 {task['taskName']} 后续处理失败: {e}", type=NotificationType.ERROR.value)
                        db.update_task_status(task['id'], current_status, progress)  # 保留原状态便于重试
                else:
                    db.update_task_status(task['id'], new_status, progress)
            except Exception as e:
                logger.error(f"检查任务 {task.get('id')} 失败: {e}")

    def _extract_torrent_hash(self, task_name: str, source_url: str) -> str | None:
        """从任务名或链接中提取种子 Hash"""
        if re.match(r'^[a-fA-F0-9]{40}$', task_name):
            return task_name.lower()
        if source_url and source_url.startswith("magnet:?"):
            match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', source_url)
            if match:
                return match.group(1).lower()
        return None

    def _map_status(self, qb_state: str) -> str:
        """将 qBittorrent 状态映射为系统状态"""
        # uploading/stalledUP 等 = 已做种/完成
        if qb_state in ['uploading', 'stalledUP', 'queuedUP', 'checkingUP', 'forcedUP', 'pausedUP']:
            return 'completed'
        elif qb_state in ['error', 'missingFiles']:
            return 'error'
        else:
            return 'downloading'  # downloading, stalledDL, metaDL 等

    def _handle_completed_task(self, client, task: dict, torrent_hash: str, torrent_info: dict):
        """处理已完成任务：先重命名，再移动"""
        file_tasks = []
        try:
            file_tasks = db.get_file_tasks(task['id'])
            self._process_file_renames(client, task['id'], torrent_hash, file_tasks)
        except Exception as e:
            logger.error(f"处理文件重命名任务失败: {e}")

        try:
            # 确定最终移动路径：优先用 file_task 的 targetPath，否则用 task 的
            final_target_path = task['targetPath']
            if file_tasks:
                for ft in file_tasks:
                    ft_target = ft.get('targetPath')
                    if ft_target:
                        if os.path.isabs(ft_target):
                            final_target_path = ft_target
                        else:
                            if final_target_path:
                                final_target_path = os.path.join(final_target_path, ft_target)
                            else:
                                # 未指定基础路径，降级使用 file_task 的相对路径
                                final_target_path = ft_target
                                db.insert_notification(
                                    title="路径降级警告",
                                    content=f"任务 {task['taskName']} 未指定基础目标路径，将使用默认路径拼接: {ft_target}",
                                    type=NotificationType.WARNING.value
                                )
                        final_target_path = final_target_path.replace('\\', '/')
                        break

            is_moved, local_path, qb_path = self._maybe_move_location(client, task['id'], torrent_hash, torrent_info, final_target_path)
            if is_moved:
                self._verify_move(client, torrent_hash, local_path, qb_path, file_tasks)
        except Exception as e:
            logger.error(f"处理文件移动任务失败: {e}")

    def _process_file_renames(self, client, task_id: int, torrent_hash: str, file_tasks: list):
        """处理文件重命名，先尝试 rename_file，失败则尝试 rename_folder"""
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
                # 仅改文件名，保留原目录
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
                if norm_old == norm_new:  # 路径相同，无需重命名
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
                    db.insert_notification(title="重命名成功", content=f"{old_path} -> {new_path}", type=NotificationType.SUCCESS.value)
                else:
                    if client.rename_folder(torrent_hash, old_path, new_path):
                        db.update_file_task_status(ft['id'], 'completed')
                        logger.info(f"文件夹重命名成功: {old_path} -> {new_path}")
                        db.insert_notification(title="文件夹重命名成功", content=f"{old_path} -> {new_path}", type=NotificationType.SUCCESS.value)
                    else:
                        logger.error(f"重命名失败: {old_path} -> {new_path}")
                        db.update_file_task_status(ft['id'], 'failed', "QB API returned fail")
                        db.insert_notification(title="重命名失败", content=f"{old_path} -> {new_path}: QB API fail", type=NotificationType.ERROR.value)
            except Exception as e:
                logger.error(f"重命名异常: {e}")
                db.update_file_task_status(ft['id'], 'failed', str(e))
                db.insert_notification(title="重命名异常", content=f"{old_path} -> {new_path}: {e}", type=NotificationType.ERROR.value)

    def _maybe_move_location(self, client, task_id: int, torrent_hash: str, torrent_info: dict, target_path: str) -> tuple:
        """尝试移动任务到目标路径，返回 (is_moved, local_mkdir_path, qb_move_path)"""
        if not target_path:
            logger.info(f"任务 {task_id} 目标路径为空，跳过移动")
            return False, "", ""

        root_path = config.get("paths.root_path", "")
        default_target_path = config.get("paths.default_target_path", "")

        # 构建传给 qB 的路径：绝对路径直接用，相对路径拼接 default_target_path
        if os.path.isabs(target_path):
            qb_move_path = target_path
        else:
            if default_target_path:
                qb_move_path = os.path.join(default_target_path, target_path)
            else:
                qb_move_path = target_path
        qb_move_path = qb_move_path.replace('\\', '/')

        # 本地预创建目录：若配置了 root_path，则 local_mkdir_path 相对于 root_path
        if root_path:
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

        if p1 != p2:  # 当前路径与目标不同，需要移动
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
                db.insert_notification(title="开始移动任务", content=f"任务 {task_id} 正在移动到 {qb_move_path}", type=NotificationType.INFO.value)
                return True, local_mkdir_path, qb_move_path
            else:
                logger.error(f"移动失败: {qb_move_path}")
                db.insert_notification(title="移动任务失败", content=f"任务 {task_id} 移动到 {qb_move_path} 失败", type=NotificationType.ERROR.value)
                return False, local_mkdir_path, qb_move_path

        return False, local_mkdir_path, qb_move_path

    def _verify_move(self, client, torrent_hash: str, local_path: str, qb_path: str, file_tasks: List[dict]):
        """验证移动结果：轮询 qB save_path 是否更新，再检查本地文件是否存在"""
        logger.info(f"开始验证移动结果: {local_path}")

        qb_updated = False
        for _ in range(10):
            try:
                info = client.get_torrent_info(torrent_hash)
                if not info:
                    break
                current_save_path = info.get('save_path', '')
                try:
                    p1 = os.path.normpath(current_save_path)
                    p2 = os.path.normpath(qb_path)
                    if p1 == p2:
                        qb_updated = True
                        break
                except Exception:
                    if current_save_path == qb_path:
                        qb_updated = True
                        break
            except Exception as e:
                logger.warning(f"验证移动时获取种子信息失败: {e}")
            time.sleep(2)

        if not qb_updated:
            logger.warning(f"移动验证超时: qB save_path 未更新 (expect: {qb_path})")
            db.insert_notification(title="移动验证警告", content=f"qBittorrent 状态未及时更新，请稍后检查文件位置", type=NotificationType.WARNING.value)
            return

        files_found = False
        try:
            # 有 file_tasks 时检查重命名后的文件是否存在
            if not os.path.exists(local_path):
                logger.warning(f"移动验证失败: 本地目录不存在 {local_path}")
            else:
                if file_tasks:
                    missing_files = []
                    for ft in file_tasks:
                        fname = ft.get('file_rename')
                        if fname:
                            fpath = os.path.join(local_path, fname)
                            if not os.path.exists(fpath):
                                missing_files.append(fname)
                    if missing_files:
                        logger.warning(f"移动验证: 部分文件未找到 {missing_files}")
                        if len(missing_files) < len(file_tasks):
                            files_found = True
                    else:
                        files_found = True
                else:
                    files_found = True
        except Exception as e:
            logger.error(f"移动验证异常: {e}")

        if files_found:
            logger.info("移动验证成功: 文件已存在")
            db.insert_notification(title="移动完成", content=f"文件已成功移动到: {local_path}", type=NotificationType.SUCCESS.value)
        else:
            db.insert_notification(title="移动验证失败", content=f"目录已创建但文件未找到: {local_path}", type=NotificationType.WARNING.value)


task_monitor = TaskMonitor()
