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
        # 分享率达标但未确认移动时，只警告一次，后续轮询静默跳过
        self._seeding_skip_warned: set = set()
        # 记录已由本程序复制完成归档的任务 id，用于做种完成时的删除策略
        self._copy_completed_tasks: set[int] = set()

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
        processed_hashes = set() # 记录本轮已处理的 Hash
        processed_target_dirs = set() # 记录本轮已占用的目标目录，防止不同任务往同一个地方移动/重命名

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

                if torrent_hash in processed_hashes:
                    logger.debug(f"跳过重复 Hash 任务处理: {task['id']} (Hash={torrent_hash})")
                    continue
                processed_hashes.add(torrent_hash)

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
                    
                    # 正在下载/移动的任务在 qB 中消失，尝试重新推送
                    if task['taskStatus'] in ('downloading', 'pending', 'moving'):
                        logger.info(f"任务 {task['id']} 在 qBittorrent 中未找到，尝试重新推送...")
                        try:
                            from app.services.task_service import task_service
                            file_tasks = db.get_file_tasks(task['id'])
                            success = task_service.push_to_qb(
                                task_id=task['id'],
                                source_url=task.get('sourceUrl', ''),
                                source_path=task.get('sourcePath', ''),
                                torrent_hash=torrent_hash,
                                file_tasks=file_tasks
                            )
                            if success:
                                db.insert_notification(
                                    title="任务已自动重推",
                                    content=f"任务 {task['taskName']} 在 qB 中缺失，已尝试自动重推下载",
                                    type=NotificationType.WARNING.value
                                )
                                continue
                        except Exception as e:
                            logger.error(f"重推任务 {task['id']} 失败: {e}")

                    # 无法重推或重推失败，标记为已取消
                    logger.info(f"任务 {task['id']} 在 qBittorrent 中未找到，且无法恢复，标记为已取消")
                    db.update_task_status(task['id'], 'cancelled')
                    db.insert_notification(
                        title="任务已同步取消",
                        content=f"任务 {task['taskName']} 在 qBittorrent 中已不存在且无法恢复，已标记为已取消",
                        type=NotificationType.WARNING.value
                    )
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
                # 只有进度达到 100% 才触发后续处理
                is_just_completed = (new_status in ['completed', 'seeding']) and (current_status not in ['completed', 'seeding']) and progress >= 100
                
                if is_just_completed:
                    # 检查目标目录冲突：防止不同任务同时往同一个地方移动/重命名
                    try:
                        file_tasks = db.get_file_tasks(task['id'])
                        target_dir = self._get_task_qb_target_path(task, file_tasks)
                        if target_dir:
                            if target_dir in processed_target_dirs:
                                logger.warning(f"目标目录冲突: {target_dir} 已在本轮循环中被处理，跳过任务 {task['id']} (待下一轮重试)")
                                continue
                            processed_target_dirs.add(target_dir)
                    except Exception as e:
                        logger.warning(f"检查目标目录冲突失败: {e}")

                    logger.info(f"任务 {task['id']} 已完成 (状态: {new_status})，开始执行后续处理: {torrent_info.get('name')}")
                    db.insert_notification(title="任务下载完成", content=f"任务 {task['taskName']} 下载完成，开始后续处理", type=NotificationType.SUCCESS.value)
                    try:
                        db.update_task_status(task['id'], "moving", progress)
                        # 执行处理，返回最终建议状态
                        final_status = self._handle_completed_task(client, task, torrent_hash, torrent_info)
                        if not final_status:
                            # 移动/复制未成功（返回 None），保持 moving 便于下次轮询重试，不标为 completed/seeding
                            final_status = "moving"
                        
                        db.update_task_status(task['id'], final_status, progress)
                        if final_status == "moving":
                            db.insert_notification(title="任务待重试", content=f"任务 {task['taskName']} 移动/复制未完成，将稍后自动重试", type=NotificationType.WARNING.value)
                        else:
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
        # 注意：checkingUP 状态可能表示正在校验，此时不应直接视为已完成
        if qb_state in ['uploading', 'stalledUP', 'queuedUP', 'forcedUP', 'pausedUP']:
            # 检查是否开启做种监控
            limit_ratio = float(config.get("qbittorrent.seeding.limit_ratio", -1.0))
            if limit_ratio >= 0:
                return 'seeding'
            return 'completed'
        elif qb_state in ['error', 'missingFiles']:
            return 'error'
        elif qb_state in ['checkingUP', 'checkingDL', 'checkingResumeData']:
            return 'checking'
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
                limit_ratio = float(config.get("qbittorrent.seeding.limit_ratio", -1.0))
                expected_final_status = 'seeding' if limit_ratio >= 0 else 'completed'
                if is_moved:
                    ok = self._verify_move(client, torrent_hash, local_path, qb_path, file_tasks)
                    if not ok:
                        logger.warning(f"任务 {task['id']} 第一次移动验证失败，尝试重试一次移动: {qb_path}")
                        db.insert_notification(
                            title="移动任务重试",
                            content=f"任务 {task['id']} 移动验证失败，正在重试移动到: {qb_path}",
                            type=NotificationType.WARNING.value,
                        )
                        try:
                            if client.set_location(torrent_hash, qb_path):
                                ok = self._verify_move(client, torrent_hash, local_path, qb_path, file_tasks)
                            else:
                                ok = False
                                logger.error(f"任务 {task['id']} 重试移动失败: {qb_path}")
                                db.insert_notification(
                                    title="移动任务重试失败",
                                    content=f"任务 {task['id']} 重试移动到 {qb_path} 失败",
                                    type=NotificationType.ERROR.value,
                                )
                        except Exception as e:
                            ok = False
                            logger.error(f"任务 {task['id']} 重试移动异常: {e}")
                            db.insert_notification(
                                title="移动任务重试异常",
                                content=f"任务 {task['id']} 重试移动异常: {e}",
                                type=NotificationType.ERROR.value,
                            )
                    if not ok:
                        logger.warning(f"任务 {task['id']} 多次移动失败，降级为本程序复制")
                        db.insert_notification(
                            title="移动失败已降级为复制",
                            content=f"任务 {task['id']} 多次移动失败，将改为本程序复制到目标路径",
                            type=NotificationType.WARNING.value,
                        )
                        result = self._process_copy(client, task, torrent_hash, torrent_info, final_target_path, file_tasks)
                        if result in ('seeding', 'completed'):
                            self._copy_completed_tasks.add(task['id'])
                        return result
                    return expected_final_status

                # 未触发移动：若已在目标路径，则视为后续处理完成，直接进入最终状态
                try:
                    current_save_path = torrent_info.get('save_path', '')
                    if self._normalize_path_for_compare(current_save_path) == self._normalize_path_for_compare(qb_path):
                        return expected_final_status
                except Exception:
                    pass

                return None
            else:
                logger.info(f"任务 {task['id']} 使用本程序复制 (多文件)")
                result = self._process_copy(client, task, torrent_hash, torrent_info, final_target_path, file_tasks)
                if result in ('seeding', 'completed'):
                    self._copy_completed_tasks.add(task['id'])
                return result

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

    def _find_source_by_extension(self, save_path_resolved: str, content_path: str, dest_name: str) -> str:
        """当源路径不存在时，在下载目录下按目标文件扩展名找唯一同扩展名文件（兼容源已被重命名的情况）。"""
        ext = os.path.splitext(dest_name)[1].lower()
        if not ext:
            return ""
        search_dir = save_path_resolved
        if content_path and os.path.isdir(content_path):
            search_dir = content_path
        if not search_dir or not os.path.isdir(search_dir):
            return ""
        try:
            candidates = [
                os.path.join(search_dir, f)
                for f in os.listdir(search_dir)
                if os.path.isfile(os.path.join(search_dir, f)) and os.path.splitext(f)[1].lower() == ext
            ]
            if len(candidates) == 1:
                return candidates[0]
        except OSError:
            pass
        return ""

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
                copied_count = 0
                for ft in file_tasks:
                    src_rel = (ft.get('sourcePath') or '').replace('\\', '/')
                    dest_name = (ft.get('file_rename') or '').strip()
                    ft_target = (ft.get('targetPath') or '').replace('\\', '/')
                    if not dest_name:
                        continue
                    # 1) 单文件种子：content_path 即源文件路径，不要再拼 dest_name
                    if os.path.isfile(content_path):
                        src_full = content_path
                    else:
                        # 2) 多文件或目录：先试「重命名后」路径 content_path/dest_name
                        src_full = os.path.normpath(os.path.join(content_path, dest_name))
                    if not os.path.exists(src_full):
                        # 3) 未重命名或失败：源路径为 save_path + sourcePath
                        src_full = os.path.normpath(os.path.join(save_path_resolved, src_rel))
                        # 模糊尝试：处理 NoSubfolder 导致的根目录剥离
                        if not os.path.exists(src_full) and '/' in src_rel:
                            src_rel_no_root = src_rel.split('/', 1)[1]
                            src_full_alt = os.path.normpath(os.path.join(save_path_resolved, src_rel_no_root))
                            if os.path.exists(src_full_alt):
                                src_full = src_full_alt
                    if not os.path.exists(src_full):
                        # 4) 源可能已被重命名：在 save_path 下按扩展名找唯一同扩展名文件
                        src_full = self._find_source_by_extension(save_path_resolved, content_path, dest_name)
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
                    copied_count += 1
                    logger.info(f"已复制: {src_rel} -> {dest_path}")
                if copied_count > 0:
                    copy_dest_msg = f"任务 {task['id']} 已按重命名复制到: {last_dest_dir}" if last_dest_dir else f"任务 {task['id']} 已按重命名复制到目标目录"
                    db.insert_notification(title="复制完成", content=copy_dest_msg, type=NotificationType.SUCCESS.value)
                    delete_on_complete = bool(config.get("qbittorrent.file_handling.copy_delete_on_complete", False))
                    if delete_on_complete:
                        client.delete_torrents(torrent_hash, delete_files=True)
                        return 'completed'
                    # 未配置复制后删种，则保留 qB 做种：是否进入 seeding 由做种分享率配置决定
                    limit_ratio = float(config.get("qbittorrent.seeding.limit_ratio", -1.0))
                    return 'seeding' if limit_ratio >= 0 else 'completed'
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
            delete_on_complete = bool(config.get("qbittorrent.file_handling.copy_delete_on_complete", False))
            if delete_on_complete:
                client.delete_torrents(torrent_hash, delete_files=True)
                return 'completed'
            # 未配置复制后删种，则保留 qB 做种：是否进入 seeding 由做种分享率配置决定
            limit_ratio = float(config.get("qbittorrent.seeding.limit_ratio", -1.0))
            return 'seeding' if limit_ratio >= 0 else 'completed'
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
                # 是否由本程序复制完成归档（包括移动失败降级为复制，以及配置为直接复制的多文件场景）
                copied_by_program = task_id in self._copy_completed_tasks

                # 若不是复制归档场景，仍然要求 qB save_path 已到目标路径才允许删除，防止移动未完成时误删
                task = db.get_download_task_by_id(task_id)
                file_tasks = db.get_file_tasks(task_id) if task else []
                qb_target = self._get_task_qb_target_path(task, file_tasks) if task else None
                current_save = torrent_info.get('save_path', '')
                at_target = qb_target and self._normalize_path_for_compare(current_save) == self._normalize_path_for_compare(qb_target)

                if qb_target and not at_target and not copied_by_program:
                    # 普通“qB 自己移动”场景：移动尚未确认完成，先不删，只更新状态为 completed
                    if task_id not in self._seeding_skip_warned:
                        self._seeding_skip_warned.add(task_id)
                        logger.warning(
                            "任务 %s 分享率已达标，但尚未确认已移动到目标路径，暂不删除（save_path=%s expect=%s）",
                            task_id, current_save, qb_target,
                        )
                        db.insert_notification(
                            title="移动验证警告",
                            content="分享率已达标但 qB 路径未确认更新，已暂缓删除，请稍后检查文件位置",
                            type=NotificationType.WARNING.value,
                        )
                    db.update_task_status(task_id, 'completed')
                    return

                # 复制归档场景：文件已由本程序复制到归档目录，允许按配置删除 qB 任务及临时下载文件
                delete_files = bool(config.get("qbittorrent.seeding.delete_files", False)) and not at_target
                if at_target:
                    logger.info(f"任务 {task_id} 文件已在目标路径，删除任务时不删文件 (save_path={current_save})")
                logger.info(f"任务 {task_id} 分享率达标，执行删除 (delete_files={delete_files})")
                try:
                    client.delete_torrents(torrent_hash, delete_files=delete_files)
                    db.update_task_status(task_id, 'completed')
                    db.insert_notification(title="做种完成", content=f"任务 {task_id} 分享率达标 ({current_ratio:.2f})，已删除任务", type=NotificationType.SUCCESS.value)
                    # 删除成功后可清理标记
                    if copied_by_program and task_id in self._copy_completed_tasks:
                        self._copy_completed_tasks.discard(task_id)
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
        
        # 获取 qB 中的最新文件列表，用于纠正路径（处理 NoSubfolder 布局）
        qb_files = []
        try:
            qb_files = client.get_torrent_files(torrent_hash)
        except Exception as e:
            logger.warning(f"获取种子文件列表失败，重命名将直接使用 DB 路径: {e}")

        def normalize(p):
            return (p or "").replace('\\', '/').strip('/')

        for ft in file_tasks:
            if ft['file_status'] == 'completed':
                continue
            old_path = ft['sourcePath']
            file_rename = ft['file_rename']
            if not file_rename or not old_path:
                continue

            # 纠正 old_path：如果在 qB 中找不到精确匹配，尝试模糊匹配
            real_old_path = old_path.replace('\\', '/')
            norm_old = normalize(old_path)
            
            match_found = False
            if qb_files:
                # 1. 精确匹配
                for f in qb_files:
                    f_name = f.get('name', '')
                    if normalize(f_name) == norm_old:
                        real_old_path = f_name
                        match_found = True
                        break
                
                # 2. 模糊匹配：处理 NoSubfolder 导致的根目录剥离
                if not match_found:
                    for f in qb_files:
                        f_name = f.get('name', '')
                        norm_f = normalize(f_name)
                        if norm_old.endswith('/' + norm_f) or norm_f.endswith('/' + norm_old):
                            logger.info(f"纠正重命名的源文件路径: {old_path} -> {f_name}")
                            real_old_path = f_name
                            match_found = True
                            break

            # 计算 new_path
            file_rename = file_rename.replace('\\', '/')
            if '/' not in file_rename:
                # 仅改文件名，保留原目录
                if '/' in real_old_path:
                    dir_name = os.path.dirname(real_old_path)
                    new_path = f"{dir_name}/{file_rename}"
                else:
                    new_path = file_rename
            else:
                new_path = file_rename

            try:
                norm_old_cmp = os.path.normpath(real_old_path)
                norm_new_cmp = os.path.normpath(new_path)
                if norm_old_cmp == norm_new_cmp:  # 路径相同，无需重命名
                    db.update_file_task_status(ft['id'], 'completed')
                    continue
            except Exception:
                if real_old_path == new_path:
                    db.update_file_task_status(ft['id'], 'completed')
                    continue
            
            logger.info(f"正在重命名文件: {real_old_path} -> {new_path}")
            try:
                if client.rename_file(torrent_hash, real_old_path, new_path):
                    db.update_file_task_status(ft['id'], 'completed')
                    logger.info(f"重命名成功: {real_old_path} -> {new_path}")
                    db.insert_notification(title="重命名成功", content=f"{real_old_path} -> {new_path}", type=NotificationType.SUCCESS.value)
                else:
                    if client.rename_folder(torrent_hash, real_old_path, new_path):
                        db.update_file_task_status(ft['id'], 'completed')
                        logger.info(f"文件夹重命名成功: {real_old_path} -> {new_path}")
                        db.insert_notification(title="文件夹重命名成功", content=f"{real_old_path} -> {new_path}", type=NotificationType.SUCCESS.value)
                    else:
                        logger.error(f"重命名失败: {real_old_path} -> {new_path}")
                        db.update_file_task_status(ft['id'], 'failed', "QB API returned fail")
                        db.insert_notification(title="重命名失败", content=f"{real_old_path} -> {new_path}: QB API fail", type=NotificationType.ERROR.value)
            except Exception as e:
                logger.error(f"重命名异常: {e}")
                db.update_file_task_status(ft['id'], 'failed', str(e))
                db.insert_notification(title="重命名异常", content=f"{real_old_path} -> {new_path}: {e}", type=NotificationType.ERROR.value)

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

    def _verify_move(self, client, torrent_hash: str, local_path: str, qb_path: str, file_tasks: List[dict]) -> bool:
        """验证移动结果：轮询 qB save_path 是否更新，并检查本地文件是否存在。

        说明：qB 的 setLocation 是异步操作，save_path 可能延迟很久才更新；但文件可能已实际移动完成。
        因此验证以“目标目录文件出现”为优先成功条件，save_path 仅作辅助判断。
        """
        logger.info(f"开始验证移动结果: {local_path}")

        verify_timeout = int(config.get("qbittorrent.move_verify_timeout_seconds", 120) or 120)
        poll_interval = float(config.get("qbittorrent.move_verify_poll_seconds", 2) or 2)
        max_rounds = max(1, int(verify_timeout / max(poll_interval, 0.5)))

        qb_updated = False
        files_found = False
        last_save_path = ""

        for _ in range(max_rounds):
            try:
                info = client.get_torrent_info(torrent_hash)
                if not info:
                    break
                current_save_path = info.get('save_path', '')
                last_save_path = current_save_path
                if self._normalize_path_for_compare(current_save_path) == self._normalize_path_for_compare(qb_path):
                    qb_updated = True
            except Exception as e:
                logger.warning(f"验证移动时获取种子信息失败: {e}")

            # 即使 qB 未及时更新 save_path，也检查文件是否已经出现在目标目录
            try:
                if os.path.exists(local_path):
                    if file_tasks:
                        expected = [ft for ft in file_tasks if (ft.get('file_rename') or '').strip()]
                        missing = []
                        for ft in expected:
                            fname = (ft.get('file_rename') or '').strip()
                            fpath = os.path.join(local_path, fname)
                            if not os.path.exists(fpath):
                                missing.append(fname)
                        if not missing:
                            files_found = True
                        elif len(missing) < len(expected):
                            files_found = True
                    else:
                        files_found = True
            except Exception as e:
                logger.warning(f"移动验证检查本地文件异常: {e}")

            if qb_updated or files_found:
                break

            time.sleep(poll_interval)

        if files_found:
            if qb_updated:
                logger.info("移动验证成功: 文件已存在且 qB save_path 已更新")
                db.insert_notification(title="移动完成", content=f"文件已成功移动到: {local_path}", type=NotificationType.SUCCESS.value)
            else:
                logger.warning(
                    "移动验证成功但 qB save_path 未及时更新 (save_path=%s expect=%s)",
                    last_save_path, qb_path,
                )
                db.insert_notification(
                    title="移动完成（状态延迟）",
                    content=f"文件已移动到: {local_path}（qB 状态可能延迟更新）",
                    type=NotificationType.SUCCESS.value,
                )
            return True

        if not qb_updated:
            logger.warning(f"移动验证超时: 未确认文件已到目标且 qB save_path 未更新 (expect: {qb_path})")
            db.insert_notification(
                title="移动验证警告",
                content="qBittorrent 状态未及时更新，且未在目标目录确认到文件，请稍后检查文件位置",
                type=NotificationType.WARNING.value,
            )
            return False

        db.insert_notification(title="移动验证失败", content=f"qB 路径已更新但未在目标目录找到文件: {local_path}", type=NotificationType.WARNING.value)
        return False


task_monitor = TaskMonitor()
