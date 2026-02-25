import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import config
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)


class Database:
    """
    数据库管理类 (SQLite)
    负责数据库连接、初始化以及所有的数据 CRUD 操作。
    使用线程本地连接，避免多请求共用同一连接导致的串行等待，API 之间互不阻塞。
    """

    def __init__(self):
        db_cfg = config.get("database", {})
        path_cfg = db_cfg.get("path", "Zongzibay.db")
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = path_cfg if os.path.isabs(path_cfg) else os.path.join(root_dir, path_cfg)
        self.schema_path = os.path.join(root_dir, "sql", "main.sql")
        if not os.path.exists(self.schema_path):
            self.schema_path = os.path.join(root_dir, "sql", "create_table.sql")
        self._local = threading.local()

    def get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（每线程一个，避免多请求互相阻塞）"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def init_db(self) -> None:
        """
        初始化数据库
        如果表不存在，则从 create_table.sql 创建
        """
        conn = self.get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM download_task LIMIT 1")
            return
        except sqlite3.OperationalError:
            pass

        if os.path.exists(self.schema_path):
            try:
                with open(self.schema_path, "r", encoding="utf-8") as f:
                    sql = f.read()
                conn.executescript(sql)
                conn.commit()
                logger.info("数据库初始化成功")
            except Exception as e:
                logger.error(f"数据库初始化失败: {e}")
        else:
            logger.error(f"未找到数据库初始化脚本: {self.schema_path}")

    def insert_download_task(
        self, 
        taskName: str, 
        taskInfo: str, 
        sourceUrl: str, 
        sourcePath: str, 
        targetPath: str, 
        taskStatus: str, 
        commit: bool = True
    ) -> int:
        """
        插入新的下载任务
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO download_task (taskName, taskInfo, sourceUrl, sourcePath, targetPath, taskStatus, createTime, updateTime, isDelete) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (taskName, taskInfo, sourceUrl, sourcePath, targetPath, taskStatus, now, now),
        )
        if commit:
            conn.commit()
        return cur.lastrowid

    def get_download_tasks(self, page: int = 1, page_size: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        """
        分页获取下载任务列表
        Returns: (tasks, total_count)
        """
        offset = (page - 1) * page_size
        conn = self.get_conn()
        cur = conn.cursor()
        
        # Count total
        cur.execute("SELECT COUNT(*) FROM download_task WHERE isDelete = 0")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT * FROM download_task WHERE isDelete = 0 ORDER BY createTime DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        rows = cur.fetchall()
        tasks = [dict(row) for row in rows]
        for task in tasks:
            cur.execute("SELECT * FROM file_task WHERE downloadTaskId = ?", (task['id'],))
            ft_rows = cur.fetchall()
            task['file_tasks'] = [dict(r) for r in ft_rows]

        return tasks, total

    def get_download_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取下载任务"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM download_task WHERE id = ? AND isDelete = 0", (task_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None

    def update_download_task_status(self, task_id: int, status: str) -> bool:
        """更新下载任务状态"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE download_task SET taskStatus = ?, updateTime = ? WHERE id = ?",
            (status, now, task_id)
        )
        conn.commit()
        return cur.rowcount > 0
        
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """获取所有未完成的任务 (downloading, moving, seeding 等)"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM download_task WHERE isDelete = 0 AND taskStatus NOT IN ('completed', 'error', 'paused')"
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def update_task_status(self, task_id: int, status: str, progress: float = None) -> None:
        """更新任务状态和进度"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        cur = conn.cursor()
        
        if progress is not None:
             cur.execute(
                "UPDATE download_task SET taskStatus = ?, taskInfo = ?, updateTime = ? WHERE id = ?",
                (status, f"{progress:.1f}%", now, task_id),
            )
        else:
            cur.execute(
                "UPDATE download_task SET taskStatus = ?, updateTime = ? WHERE id = ?",
                (status, now, task_id),
            )
        conn.commit()

    def insert_file_task(
        self, 
        downloadTaskId: int, 
        sourcePath: str, 
        targetPath: str, 
        file_rename: str, 
        file_status: str = 'pending', 
        commit: bool = True
    ) -> int:
        """
        插入文件操作任务
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO file_task (downloadTaskId, sourcePath, targetPath, file_rename, file_status, createTime, updateTime) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (downloadTaskId, sourcePath, targetPath, file_rename, file_status, now, now)
        )
        if commit:
            conn.commit()
        return cur.lastrowid

    def get_file_tasks(self, download_task_id: int) -> List[Dict[str, Any]]:
        """获取指定下载任务关联的文件任务"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM file_task WHERE downloadTaskId = ?",
            (download_task_id,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def update_file_task_status(self, task_id: int, status: str, error_message: str = None) -> None:
        """更新文件任务状态"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        cur = conn.cursor()
        if error_message:
            cur.execute(
                "UPDATE file_task SET file_status = ?, errorMessage = ?, updateTime = ? WHERE id = ?",
                (status, error_message, now, task_id),
            )
        else:
            cur.execute(
                "UPDATE file_task SET file_status = ?, updateTime = ? WHERE id = ?",
                (status, now, task_id),
            )
        conn.commit()

    def update_file_tasks_by_download_task_id(self, download_task_id: int, status: str) -> None:
        """批量更新指定下载任务关联的所有文件任务状态"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE file_task SET file_status = ?, updateTime = ? WHERE downloadTaskId = ?",
            (status, now, download_task_id)
        )
        conn.commit()

    def insert_notification(
        self,
        title: str,
        content: str = None,
        type: str = NotificationType.INFO.value
    ) -> int:
        """插入新通知"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notification (title, content, type, isRead, createTime, isDelete) VALUES (?, ?, ?, 0, ?, 0)",
            (title, content, type, now)
        )
        conn.commit()
        return cur.lastrowid

    def get_notifications(self, page: int = 1, page_size: int = 20, is_read: bool = None) -> Tuple[List[Dict[str, Any]], int]:
        """分页获取通知"""
        offset = (page - 1) * page_size
        conn = self.get_conn()
        cur = conn.cursor()
        
        where_clause = "isDelete = 0"
        params = []
        if is_read is not None:
            where_clause += " AND isRead = ?"
            params.append(1 if is_read else 0)
        cur.execute(f"SELECT COUNT(*) FROM notification WHERE {where_clause}", params)
        total = cur.fetchone()[0]
        cur.execute(
            f"SELECT * FROM notification WHERE {where_clause} ORDER BY createTime DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows], total

    def mark_notification_read(self, notification_id: int) -> bool:
        """标记单个通知为已读"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE notification SET isRead = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        return cur.rowcount > 0

    def mark_all_notifications_read(self) -> int:
        """标记所有通知为已读"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE notification SET isRead = 1 WHERE isRead = 0 AND isDelete = 0")
        conn.commit()
        return cur.rowcount

    def get_unread_count(self) -> int:
        """获取未读通知数量"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM notification WHERE isRead = 0 AND isDelete = 0")
        return cur.fetchone()[0]

    def delete_notification(self, notification_id: int) -> bool:
        """逻辑删除通知"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE notification SET isDelete = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        return cur.rowcount > 0


db = Database()

init_db = db.init_db
insert_download_task = db.insert_download_task
insert_file_task = db.insert_file_task
get_download_tasks = db.get_download_tasks
get_active_tasks = db.get_active_tasks
update_task_status = db.update_task_status
get_file_tasks = db.get_file_tasks
update_file_task_status = db.update_file_task_status
update_file_tasks_by_download_task_id = db.update_file_tasks_by_download_task_id

insert_notification = db.insert_notification
get_notifications = db.get_notifications
mark_notification_read = db.mark_notification_read
mark_all_notifications_read = db.mark_all_notifications_read
get_unread_count = db.get_unread_count
delete_notification = db.delete_notification
