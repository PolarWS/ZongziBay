CREATE TABLE IF NOT EXISTS download_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 主键ID
    taskName TEXT NOT NULL,                 -- 任务名称 (例如: 电影标题)
    taskInfo TEXT,                          -- 任务详细信息 (例如: 进度百分比, 文件大小)
    sourceUrl TEXT,                         -- 来源URL (例如: 磁力链接, 种子地址)
    sourcePath TEXT,                        -- 源文件下载路径 (qBittorrent 下载目录)
    targetPath TEXT,                        -- 目标存储路径 (最终归档目录)
    taskStatus TEXT,                        -- 任务状态 (downloading:下载中, moving:移动中, completed:已完成,cancelled:已取消, error:错误)
    createTime DATETIME,                    -- 创建时间
    updateTime DATETIME,                    -- 更新时间
    isDelete INTEGER NOT NULL DEFAULT 0     -- 逻辑删除标记 (0:未删除, 1:已删除)
);

-- 文件操作任务表
CREATE TABLE IF NOT EXISTS file_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 主键ID
    downloadTaskId INTEGER,                 -- 关联的下载任务ID
    sourcePath TEXT NOT NULL,               -- 源文件/目录路径
    targetPath TEXT NOT NULL,               -- 目标文件/目录路径
    file_rename TEXT NOT NULL,              -- 重命名名称
    file_status TEXT NOT NULL DEFAULT 'pending', -- 任务状态 (pending:等待中, processing:处理中, completed:已完成, failed:失败, cancelled:已取消)
    errorMessage TEXT,                      -- 错误信息 (如果失败)
    createTime DATETIME,                    -- 创建时间
    updateTime DATETIME,                    -- 更新时间
    FOREIGN KEY (downloadTaskId) REFERENCES download_task(id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_taskName ON download_task(taskName);
CREATE INDEX IF NOT EXISTS idx_fileOpStatus ON file_task(file_status);

-- 通知表
CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,                    -- 通知标题
    content TEXT,                           -- 通知内容
    type TEXT NOT NULL DEFAULT 'info',      -- 通知类型 (info, success, warning, error)
    isRead INTEGER NOT NULL DEFAULT 0,      -- 是否已读 (0:未读, 1:已读)
    createTime DATETIME,                    -- 创建时间
    isDelete INTEGER NOT NULL DEFAULT 0     -- 逻辑删除 (0:未删除, 1:已删除)
);

CREATE INDEX IF NOT EXISTS idx_notif_isRead ON notification(isRead);
