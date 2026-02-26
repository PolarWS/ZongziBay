import logging
import os
import re
import shutil
import threading
import time
from typing import List

from app.core import db
from app.core.config import config
from app.schemas.notification import NotificationType
from app.services.magnet_service import magnet_service, normalize_info_hash

logger = logging.getLogger(__name__)


class TaskMonitor:
    """定时检查下载任务，同步 qBittorrent 状态并执行后续处理"""

    def __init__(self, interval: int = 10):
        self.interval = interval
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def start(self):
        """启动监控线程（无 qB 时也启动，以便处理字幕等非 qB 任务）"""
        if not self.running:
            if not self._check_connection():
                logger.warning("无法连接到 qBittorrent，种子任务将暂不处理；字幕等 HTTP 下载任务仍会照常处理。")
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

        for task in active_tasks:
            try:
                torrent_hash = self._extract_torrent_hash(task['taskName'], task.get('sourceUrl', ''))
                if not torrent_hash:
                    # 字幕任务：HTTP 下载后由本程序加入队列，此处只做移动/重命名
                    if (task.get('sourceUrl') or '').startswith('subtitle:') and task.get('taskStatus') == 'moving':
                        try:
                            self._handle_subtitle_task(task)
                        except Exception as e:
                            logger.error(f"字幕任务 {task['id']} 处理失败: {e}")
                            db.insert_notification(
                                title="字幕任务处理失败",
                                content=f"任务 {task['taskName']} 移动/重命名失败: {e}",
                                type=NotificationType.ERROR.value,
                            )
                    else:
                        logger.warning(f"无法获取任务 {task['id']} 的 Hash，跳过检查。Name={task['taskName']}")
                    continue
                # qBittorrent API 只认 40 位 hex，若仍是 32 位 Base32 则再规范化一次（兼容旧数据或未规范化的来源）
                if len(torrent_hash) == 32:
                    torrent_hash = normalize_info_hash(torrent_hash)

                if not client:
                    logger.warning("无法连接 qBittorrent，跳过种子任务检查")
                    continue
                torrent_info = client.get_torrent_info(torrent_hash)
                if not torrent_info:
                    if task['taskStatus'] == 'cancelled':  # 取消后 qB 已删除，正常忽略
                        continue
                    # 如果任务在 DB 中是 seeding 状态但 qB 没了，视为 completed
                    if task['taskStatus'] == 'seeding':
                        logger.info(f"任务 {task['id']} 在 qB 中不存在，标记为 completed")
                        db.update_task_status(task['id'], 'completed')
                        continue
                    # 同 Hash 的种子在 qB 中只存在一个，若被取消/删除则其他「下载中」任务会一直卡住，此处同步为已取消
                    if task['taskStatus'] in ('downloading', 'pending', 'moving'):
                        logger.info(f"任务 {task['id']} 在 qBittorrent 中未找到（可能被同 Hash 任务取消），标记为已取消")
                        db.update_task_status(task['id'], 'cancelled')
                        db.insert_notification(
                            title="任务已同步取消",
                            content=f"任务 {task['taskName']} 在 qBittorrent 中已不存在（同一种子可能已被其他任务取消），已标记为已取消",
                            type=NotificationType.WARNING.value
                        )
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
                # 注意：如果 new_status 是 seeding，也视为下载完成，需要触发处理
                is_just_completed = (new_status in ['completed', 'seeding']) and (current_status not in ['completed', 'seeding'])
                
                if is_just_completed:
                    logger.info(f"任务 {task['id']} 已完成 (状态: {new_status})，开始执行后续处理: {torrent_info.get('name')}")
                    db.insert_notification(title="任务下载完成", content=f"任务 {task['taskName']} 下载完成，开始后续处理", type=NotificationType.SUCCESS.value)
                    try:
                        db.update_task_status(task['id'], "moving", progress)
                        # 执行处理，返回最终建议状态
                        final_status = self._handle_completed_task(client, task, torrent_hash, torrent_info)
                        if not final_status:
                            final_status = new_status
                        
                        db.update_task_status(task['id'], final_status, progress)
                        db.insert_notification(title="任务处理完成", content=f"任务 {task['taskName']} 后续处理完成", type=NotificationType.SUCCESS.value)
                        
                        # 如果进入 seeding 状态，立即检查一次
                        if final_status == 'seeding':
                            self._check_seeding_task(client, task['id'], torrent_hash, torrent_info)
                            
                    except Exception as e:
                        logger.error(f"任务 {task['id']} 后续处理失败: {e}")
                        db.insert_notification(title="任务处理失败", content=f"任务 {task['taskName']} 后续处理失败: {e}", type=NotificationType.ERROR.value)
                        db.update_task_status(task['id'], current_status, progress)  # 保留原状态便于重试
                
                elif new_status == 'seeding':
                    # 持续监控做种状态
                    db.update_task_status(task['id'], new_status, progress)
                    self._check_seeding_task(client, task['id'], torrent_hash, torrent_info)
                    
                else:
                    db.update_task_status(task['id'], new_status, progress)
            except Exception as e:
                logger.error(f"检查任务 {task.get('id')} 失败: {e}")

    def _handle_subtitle_task(self, task: dict) -> None:
        """字幕任务：将已下载到 sourcePath 的文件复制到 targetPath 并重命名。"""
        file_tasks = db.get_file_tasks(task["id"])
        if not file_tasks:
            logger.warning(f"字幕任务 {task['id']} 无文件任务，直接标记完成")
            db.update_task_status(task["id"], "completed")
            return
        default_target = config.get("paths.default_target_path", "")
        task_target = (task.get("targetPath") or "").replace("\\", "/").strip()
        if task_target and not (os.path.isabs(task_target) or (len(task_target) > 1 and task_target[1] == ":")):
            base_dir = os.path.join(default_target, task_target) if default_target else task_target
        else:
            base_dir = task_target or default_target
        base_dir = base_dir.replace("\\", "/")
        source_base = (task.get("sourcePath") or "").replace("\\", "/").strip()
        logger.info("字幕任务 targetPath=%s -> base_dir=%s (将解析为本地路径)", task_target or "(空)", base_dir)
        if not source_base or not os.path.exists(source_base):
            logger.error(f"字幕任务 {task['id']} 源目录不存在: {source_base}")
            db.insert_notification(
                title="字幕任务失败",
                content=f"源目录不存在: {source_base}",
                type=NotificationType.ERROR.value,
            )
            return
        for ft in file_tasks:
            src_name = (ft.get("sourcePath") or "").replace("\\", "/").strip()
            dest_name = (ft.get("file_rename") or "").strip() or src_name
            ft_target = (ft.get("targetPath") or "").replace("\\", "/").strip()
            if not src_name:
                continue
            src_full = os.path.normpath(os.path.join(source_base, src_name))
            if not os.path.exists(src_full):
                logger.warning(f"字幕任务 {task['id']} 源文件不存在: {src_full}")
                db.update_file_task_status(ft["id"], "failed", "源文件不存在")
                continue
            dest_dir = os.path.join(base_dir, ft_target) if ft_target else base_dir
            dest_dir = dest_dir.replace("\\", "/")
            dest_dir = self._resolve_path_for_local(dest_dir, for_target=True)
            dest_full = os.path.join(dest_dir, dest_name)
            try:
                os.makedirs(dest_dir, exist_ok=True)
                if os.path.exists(dest_full):
                    logger.warning(f"字幕任务 {task['id']} 目标已存在，跳过: {dest_full}")
                    db.update_file_task_status(ft["id"], "completed")
                    try:
                        os.remove(src_full)
                        logger.info(f"字幕源文件已清理: {src_full}")
                    except OSError as e:
                        logger.warning(f"字幕源文件清理失败 {src_full}: {e}")
                    continue
                shutil.copy2(src_full, dest_full)
                db.update_file_task_status(ft["id"], "completed")
                logger.info(f"字幕已移动: {src_full} -> {dest_full}")
                try:
                    os.remove(src_full)
                    logger.info(f"字幕源文件已清理: {src_full}")
                except OSError as e:
                    logger.warning(f"字幕源文件清理失败 {src_full}: {e}")
            except Exception as e:
                logger.error(f"字幕任务 {task['id']} 复制失败: {e}")
                db.update_file_task_status(ft["id"], "failed", str(e))
                raise
        db.update_task_status(task["id"], "completed")
        db.insert_notification(
            title="字幕任务完成",
            content=f"字幕「{task.get('taskName', '')}」已移动至目标路径",
            type=NotificationType.SUCCESS.value,
        )

    def _extract_torrent_hash(self, task_name: str, source_url: str) -> str | None:
        """从任务名或链接中提取种子 Hash，统一为 40 位小写 hex 以便与 qBittorrent API 一致"""
        if re.match(r'^[a-fA-F0-9]{40}$', (task_name or "").strip()):
            return task_name.strip().lower()
        if source_url and (source_url.startswith("magnet:?") or source_url.startswith("magnet:")):
            match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', source_url)
            if match:
                return normalize_info_hash(match.group(1))
        return None

    def _normalize_path_for_compare(self, path: str) -> str:
        """规范化路径用于比较：统一斜杠、大小写(Windows)，避免同路径被误判为不同"""
        if not path or not path.strip():
            return (path or "").strip()
        try:
            p = os.path.normpath(path.replace("/", os.sep).replace("\\", os.sep))
            if os.name == "nt":
                p = os.path.normcase(p)
            return p.rstrip(os.sep)
        except Exception:
            return (path or "").strip()

    def _map_status(self, qb_state: str) -> str:
        """将 qBittorrent 状态映射为系统状态"""
        # uploading/stalledUP 等 = 已做种/完成
        if qb_state in ['uploading', 'stalledUP', 'queuedUP', 'checkingUP', 'forcedUP', 'pausedUP']:
            # 检查是否开启做种监控
            limit_ratio = float(config.get("qbittorrent.seeding.limit_ratio", -1.0))
            if limit_ratio >= 0:
                return 'seeding'
            return 'completed'
        elif qb_state in ['error', 'missingFiles']:
            return 'error'
        else:
            return 'downloading'  # downloading, stalledDL, metaDL 等

    def _is_single_file_torrent(self, client, torrent_hash: str) -> bool:
        """判断是否为单文件种子（单文件用 qB 移动，多文件用复制时用到）"""
        try:
            files = client.get_torrent_files(torrent_hash)
            return files is not None and len(files) == 1
        except Exception as e:
            logger.warning(f"获取种子文件列表失败，按多文件处理: {e}")
            return False

    def _has_nested_folders(self, client, torrent_hash: str) -> bool:
        """是否存在嵌套文件夹（任意文件路径中含至少 2 个 '/' 则视为有嵌套）"""
        try:
            files = client.get_torrent_files(torrent_hash)
            if not files:
                return False
            for f in files:
                name = (f.get('name') or '').replace('\\', '/')
                if name.count('/') >= 2:
                    return True
            return False
        except Exception as e:
            logger.warning(f"获取种子文件列表失败，按有嵌套处理: {e}")
            return True

    def _has_any_folder(self, client, torrent_hash: str) -> bool:
        """是否带有目录（任意文件路径中含至少 1 个 '/' 即视为带目录；仅根目录单/多文件为 False）"""
        try:
            files = client.get_torrent_files(torrent_hash)
            if not files:
                return False
            for f in files:
                name = (f.get('name') or '').replace('\\', '/')
                if '/' in name:
                    return True
            return False
        except Exception as e:
            logger.warning(f"获取种子文件列表失败，按带目录处理: {e}")
            return True

    def _handle_completed_task(self, client, task: dict, torrent_hash: str, torrent_info: dict) -> str | None:
        """处理已完成任务：先重命名，再移动或复制。返回建议的最终状态(如 'completed')，返回 None 则保持原定状态"""
        file_tasks = []
        try:
            file_tasks = db.get_file_tasks(task['id'])
            self._process_file_renames(client, task['id'], torrent_hash, file_tasks)
        except Exception as e:
            logger.error(f"处理文件重命名任务失败: {e}")

        # 重命名后刷新种子信息，确保获取最新的 content_path
        try:
            updated_info = client.get_torrent_info(torrent_hash)
            if updated_info:
                torrent_info = updated_info
        except Exception:
            pass

        try:
            # 确定最终目标路径：优先用 file_task 的 targetPath，否则用 task 的
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
            
            use_copy = config.get("qbittorrent.file_handling.use_copy", False)
            # 仅当所有文件在根目录（不带目录）时 qB 移动才只移文件；带目录则用复制以便只拷文件到目标
            has_any_folder = self._has_any_folder(client, torrent_hash)
            use_qb_move = (use_copy and not has_any_folder) or (not use_copy)
            if use_qb_move:
                logger.info(f"任务 {task['id']} 使用 qB 移动 (use_copy={use_copy}, 仅根目录文件={not has_any_folder})")
                is_moved, local_path, qb_path = self._maybe_move_location(client, task['id'], torrent_hash, torrent_info, final_target_path)
                if is_moved:
                    self._verify_move(client, torrent_hash, local_path, qb_path, file_tasks)
                return None
            else:
                logger.info(f"任务 {task['id']} 使用本程序复制 (多文件)")
                return self._process_copy(client, task, torrent_hash, torrent_info, final_target_path, file_tasks)

        except Exception as e:
            logger.error(f"处理文件移动/复制任务失败: {e}")
            return None

    def _resolve_path_for_local(self, path: str, for_target: bool = False) -> str:
        """将 qB/容器内路径解析为本机可访问路径。for_target=True 用 target_root_path（归档），否则用 download_root_path（下载）；未配置时回退到 root_path"""
        if not path or not path.strip():
            return path or ""
        paths_cfg = config.get("paths", {}) or {}
        if for_target:
            root = paths_cfg.get("target_root_path") or paths_cfg.get("root_path") or ""
        else:
            root = paths_cfg.get("download_root_path") or paths_cfg.get("root_path") or ""
        if not root:
            return path
        normalized = path.replace("\\", "/").strip()
        if normalized.startswith("/"):
            rel = normalized.lstrip("/")
            if not rel:
                return root
            # 按 / 拆成多段再 join，避免 Windows 下整段被当成单层目录名（如 video/a/xxx 变成一个文件夹名）
            parts = rel.split("/")
            return os.path.normpath(os.path.join(root, *parts))
        return path

    def _process_copy(self, client, task: dict, torrent_hash: str, torrent_info: dict, target_path: str, file_tasks: list = None) -> str | None:
        """执行复制操作。有 file_tasks 时按每条复制为「目标目录 + file_rename」，不保留种子根目录名；否则复制整个 content_path。"""
        if not target_path and not (file_tasks and any(ft.get('targetPath') for ft in (file_tasks or []))):
             logger.warning(f"任务 {task['id']} 目标路径为空，跳过复制")
             return None

        content_path = torrent_info.get('content_path')
        if not content_path:
             save_path = torrent_info.get('save_path', '')
             name = torrent_info.get('name', '')
             if save_path and name:
                 content_path = os.path.join(save_path, name)
        if content_path:
            content_path = self._resolve_path_for_local(content_path, for_target=False)

        default_target_path = config.get("paths.default_target_path", "")

        # 有 file_tasks 时：按每条复制 源文件 -> 目标目录/file_rename，不带上原文件夹名
        if file_tasks:
            if not content_path or not os.path.exists(content_path):
                logger.error(f"无法找到种子根路径: {content_path}")
                db.insert_notification(title="复制失败", content=f"无法访问下载目录: {content_path or '(空)'}", type=NotificationType.ERROR.value)
                return None
            # sourcePath 是相对 save_path 的；content_path = save_path + name，直接 content_path+sourcePath 会多一层根目录名，需用 save_path+sourcePath
            save_path_raw = torrent_info.get('save_path', '')
            save_path_resolved = self._resolve_path_for_local(save_path_raw, for_target=False) if save_path_raw else os.path.dirname(content_path)
            try:
                last_dest_dir = ""
                for ft in file_tasks:
                    src_rel = (ft.get('sourcePath') or '').replace('\\', '/')
                    dest_name = (ft.get('file_rename') or '').strip()
                    ft_target = (ft.get('targetPath') or '').replace('\\', '/')
                    if not dest_name:
                        continue
                    # 重命名后：文件在 content_path（种子根目录）下，名为 file_rename
                    src_full = os.path.normpath(os.path.join(content_path, dest_name))
                    if not os.path.exists(src_full):
                        # 未重命名或失败：源路径为 save_path + sourcePath（不要用 content_path+sourcePath 会重复根目录）
                        src_full = os.path.normpath(os.path.join(save_path_resolved, src_rel))
                    if not os.path.exists(src_full):
                        logger.warning(f"复制跳过（源不存在）: {src_full}")
                        db.insert_notification(title="复制跳过", content=f"源文件不存在，未复制: {dest_name}", type=NotificationType.WARNING.value)
                        continue
                    # 目标目录以任务的 targetPath为基准，再拼 file_task 的 targetPath，避免误用 default_target_path
                    task_base = (task.get('targetPath') or '').replace('\\', '/').strip()
                    if task_base:
                        is_abs = task_base.startswith('/') or (len(task_base) >= 2 and task_base[1] == ':')
                        base = task_base if is_abs else (os.path.join(default_target_path, task_base) if default_target_path else task_base)
                        dest_dir = os.path.normpath(os.path.join(base, *ft_target.split('/'))).replace('\\', '/') if ft_target else base.replace('\\', '/')
                    else:
                        dest_dir = os.path.join(default_target_path, *ft_target.split('/')) if default_target_path and ft_target else (ft_target or default_target_path or '')
                    dest_dir = dest_dir.replace('\\', '/') if isinstance(dest_dir, str) else dest_dir
                    dest_dir = self._resolve_path_for_local(dest_dir, for_target=True)
                    last_dest_dir = dest_dir
                    dest_path = os.path.join(dest_dir, dest_name)
                    if os.path.exists(dest_path):
                        logger.warning(f"复制跳过（目标已存在）: {dest_path}")
                        db.insert_notification(title="复制跳过", content=f"目标已存在，未覆盖: {dest_name}", type=NotificationType.WARNING.value)
                        continue
                    # 复制前再次确认源文件存在，避免复制过程中被删除
                    if not os.path.exists(src_full):
                        logger.warning(f"复制跳过（复制前检查源不存在）: {src_full}")
                        db.insert_notification(title="复制跳过", content=f"复制前检查源文件不存在: {dest_name}", type=NotificationType.WARNING.value)
                        continue
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(src_full, dest_path)
                    logger.info(f"已复制: {src_rel} -> {dest_path}")
                copy_dest_msg = f"任务 {task['id']} 已按重命名复制到: {last_dest_dir}" if last_dest_dir else f"任务 {task['id']} 已按重命名复制到目标目录"
                db.insert_notification(title="复制完成", content=copy_dest_msg, type=NotificationType.SUCCESS.value)
                if config.get("qbittorrent.file_handling.copy_delete_on_complete", False):
                    client.delete_torrents(torrent_hash, delete_files=True)
                    return 'completed'
            except Exception as e:
                logger.error(f"复制失败: {e}")
                db.insert_notification(title="复制失败", content=str(e), type=NotificationType.ERROR.value)
            return None

        # 无 file_tasks：复制整个 content_path 到目标目录（保留根目录名）
        if not content_path or not os.path.exists(content_path):
             logger.error(f"无法找到源文件路径: {content_path}")
             db.insert_notification(title="复制失败", content=f"无法访问源文件路径: {content_path or '(空)'}", type=NotificationType.ERROR.value)
             return None
        if not os.path.isabs(target_path):
             final_dest_dir = os.path.join(default_target_path, target_path) if default_target_path else target_path
        else:
             final_dest_dir = target_path
        final_dest_dir = self._resolve_path_for_local(final_dest_dir, for_target=True)
        is_dir = os.path.isdir(content_path)
        basename = os.path.basename(content_path)
        dest_path = os.path.join(final_dest_dir, basename)
        dest_path = dest_path.replace('\\', '/')
        logger.info(f"开始复制: {content_path} -> {dest_path}")
        db.insert_notification(title="开始复制", content=f"正在复制到: {dest_path}", type=NotificationType.INFO.value)
        try:
            if os.path.exists(dest_path):
                logger.error(f"复制失败: 目标路径已存在: {dest_path}")
                db.insert_notification(title="复制失败", content=f"目标路径已存在，跳过复制: {dest_path}", type=NotificationType.ERROR.value)
                return None
            if not os.path.exists(content_path):
                logger.error(f"复制失败: 复制前检查源不存在: {content_path}")
                db.insert_notification(title="复制失败", content=f"复制前检查源路径不存在: {content_path}", type=NotificationType.ERROR.value)
                return None
            os.makedirs(final_dest_dir, exist_ok=True)
            if is_dir:
                shutil.copytree(content_path, dest_path)
            else:
                shutil.copy2(content_path, dest_path)
            logger.info(f"复制完成: {dest_path}")
            db.insert_notification(title="复制完成", content=f"任务 {task['id']} 已复制到 {dest_path}", type=NotificationType.SUCCESS.value)
            if config.get("qbittorrent.file_handling.copy_delete_on_complete", False):
                client.delete_torrents(torrent_hash, delete_files=True)
                return 'completed'
        except Exception as e:
            logger.error(f"复制失败: {e}")
            db.insert_notification(title="复制失败", content=str(e), type=NotificationType.ERROR.value)
        return None

    def _get_task_qb_target_path(self, task: dict, file_tasks: list = None) -> str | None:
        """计算任务对应的 qB 目标路径（与 _handle_completed_task / _maybe_move_location 一致），用于判断文件是否已移动到目标"""
        final_target_path = task.get('targetPath') or ''
        if file_tasks:
            for ft in file_tasks:
                ft_target = ft.get('targetPath')
                if ft_target:
                    if os.path.isabs(ft_target):
                        final_target_path = ft_target
                    else:
                        final_target_path = os.path.join(final_target_path, ft_target) if final_target_path else ft_target
                    final_target_path = (final_target_path or '').replace('\\', '/')
                    break
        if not final_target_path:
            return None
        default_target_path = config.get("paths.default_target_path", "")
        if os.path.isabs(final_target_path):
            qb_path = final_target_path
        else:
            qb_path = os.path.join(default_target_path, final_target_path) if default_target_path else final_target_path
        return qb_path.replace('\\', '/')

    def _check_seeding_task(self, client, task_id: int, torrent_hash: str, torrent_info: dict):
        """检查做种任务的分享率"""
        limit_ratio = float(config.get("qbittorrent.seeding.limit_ratio", -1.0))
        if limit_ratio < 0:
            return

        current_ratio = torrent_info.get('ratio', 0.0)
        # logger.debug(f"任务 {task_id} 做种中: 当前分享率 {current_ratio:.2f} / 目标 {limit_ratio:.2f}")

        if current_ratio >= limit_ratio:
            if config.get("qbittorrent.seeding.delete_on_ratio_reached", False):
                # 若文件已通过 qB 移动到目标路径，只从 qB 移除任务，不删文件，避免删到已归档的文件
                task = db.get_download_task_by_id(task_id)
                file_tasks = db.get_file_tasks(task_id) if task else []
                qb_target = self._get_task_qb_target_path(task, file_tasks) if task else None
                current_save = torrent_info.get('save_path', '')
                at_target = qb_target and self._normalize_path_for_compare(current_save) == self._normalize_path_for_compare(qb_target)
                delete_files = config.get("qbittorrent.seeding.delete_files", False) and not at_target
                if at_target:
                    logger.info(f"任务 {task_id} 文件已在目标路径，删除任务时不删文件 (save_path={current_save})")
                logger.info(f"任务 {task_id} 分享率达标，执行删除 (delete_files={delete_files})")
                try:
                    client.delete_torrents(torrent_hash, delete_files=delete_files)
                    db.update_task_status(task_id, 'completed')
                    db.insert_notification(title="做种完成", content=f"任务 {task_id} 分享率达标 ({current_ratio:.2f})，已删除任务", type=NotificationType.SUCCESS.value)
                except Exception as e:
                    logger.error(f"删除任务 {task_id} 失败: {e}")
            else:
                # 仅标记为 completed，不再监控
                db.update_task_status(task_id, 'completed')
                db.insert_notification(title="做种完成", content=f"任务 {task_id} 分享率达标 ({current_ratio:.2f})", type=NotificationType.SUCCESS.value)

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

        paths_cfg = config.get("paths", {}) or {}
        target_root = paths_cfg.get("target_root_path") or paths_cfg.get("root_path") or ""
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

        # 本地预创建目录：若配置了 target_root_path，则 local_mkdir_path 相对于该根路径（按段拼接，避免 Windows 下成单层目录名）
        if target_root:
            _, path_without_drive = os.path.splitdrive(qb_move_path)
            rel_path = path_without_drive.replace("\\", "/").lstrip("/")
            local_mkdir_path = os.path.normpath(os.path.join(target_root, *rel_path.split("/"))) if rel_path else target_root
        else:
            local_mkdir_path = qb_move_path

        current_save_path = torrent_info.get('save_path', '')
        p1 = self._normalize_path_for_compare(current_save_path)
        p2 = self._normalize_path_for_compare(qb_move_path)

        if p1 != p2:  # 当前路径与目标不同，需要移动
            # 检查目标路径下是否存在同名文件/文件夹
            try:
                # local_mkdir_path 是目标的父目录，torrent_info['name'] 是种子根目录/文件名
                target_check_path = os.path.join(local_mkdir_path, torrent_info.get('name', ''))
                if os.path.exists(target_check_path):
                    logger.error(f"移动失败: 目标路径已存在同名文件/文件夹: {target_check_path}")
                    db.insert_notification(title="移动失败", content=f"目标路径已存在同名内容，跳过移动: {target_check_path}", type=NotificationType.ERROR.value)
                    return False, local_mkdir_path, qb_move_path
            except Exception as e:
                logger.warning(f"检查目标文件存在性失败: {e}，将继续尝试移动")

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

        logger.info(f"任务 {task_id} 当前已在目标路径 (当前: {current_save_path}, 目标: {qb_move_path})，跳过移动")
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
                if self._normalize_path_for_compare(current_save_path) == self._normalize_path_for_compare(qb_path):
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
