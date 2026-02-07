/*
 Navicat Premium Data Transfer

 Source Server         : t
 Source Server Type    : SQLite
 Source Server Version : 3035005
 Source Schema         : main

 Target Server Type    : SQLite
 Target Server Version : 3035005
 File Encoding         : 65001

 Date: 07/02/2026 16:56:59
*/

PRAGMA foreign_keys = false;

-- ----------------------------
-- Table structure for download_task
-- ----------------------------
DROP TABLE IF EXISTS "download_task";
CREATE TABLE "download_task" (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "taskName" TEXT NOT NULL,
  "taskInfo" TEXT,
  "sourceUrl" TEXT,
  "sourcePath" TEXT,
  "targetPath" TEXT,
  "taskStatus" TEXT,
  "createTime" DATETIME,
  "updateTime" DATETIME,
  "isDelete" INTEGER NOT NULL DEFAULT 0
);

-- ----------------------------
-- Table structure for file_task
-- ----------------------------
DROP TABLE IF EXISTS "file_task";
CREATE TABLE "file_task" (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "downloadTaskId" INTEGER,
  "sourcePath" TEXT NOT NULL,
  "targetPath" TEXT NOT NULL,
  "file_rename" TEXT NOT NULL,
  "file_status" TEXT NOT NULL DEFAULT 'pending',
  "errorMessage" TEXT,
  "createTime" DATETIME,
  "updateTime" DATETIME,
  FOREIGN KEY ("downloadTaskId") REFERENCES "download_task" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION
);

-- ----------------------------
-- Table structure for notification
-- ----------------------------
DROP TABLE IF EXISTS "notification";
CREATE TABLE "notification" (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "title" TEXT NOT NULL,
  "content" TEXT,
  "type" TEXT NOT NULL DEFAULT 'info',
  "isRead" INTEGER NOT NULL DEFAULT 0,
  "createTime" DATETIME,
  "isDelete" INTEGER NOT NULL DEFAULT 0
);

-- ----------------------------
-- Table structure for sqlite_sequence
-- ----------------------------
DROP TABLE IF EXISTS "sqlite_sequence";
CREATE TABLE "sqlite_sequence" (
  "name",
  "seq"
);

-- ----------------------------
-- Auto increment value for download_task
-- ----------------------------
UPDATE "sqlite_sequence" SET seq = 18 WHERE name = 'download_task';

-- ----------------------------
-- Indexes structure for table download_task
-- ----------------------------
CREATE INDEX "idx_taskName"
ON "download_task" (
  "taskName" ASC
);

-- ----------------------------
-- Auto increment value for file_task
-- ----------------------------
UPDATE "sqlite_sequence" SET seq = 119 WHERE name = 'file_task';

-- ----------------------------
-- Indexes structure for table file_task
-- ----------------------------
CREATE INDEX "idx_fileOpStatus"
ON "file_task" (
  "file_status" ASC
);

-- ----------------------------
-- Auto increment value for notification
-- ----------------------------
UPDATE "sqlite_sequence" SET seq = 7 WHERE name = 'notification';

-- ----------------------------
-- Indexes structure for table notification
-- ----------------------------
CREATE INDEX "idx_notif_isRead"
ON "notification" (
  "isRead" ASC
);

PRAGMA foreign_keys = true;
