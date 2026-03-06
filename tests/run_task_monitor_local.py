"""
本地试跑：用临时文件夹 + mock qB 客户端调用 TaskMonitor 的「单文件/无嵌套」判断与移动/复制决策。
不连真实 qBittorrent，不改生产数据。在项目根目录执行：
  python -m tests.run_task_monitor_local
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# 必须在 import app 前设置，避免使用生产数据库
if "ZONGZI_DATABASE_PATH" not in os.environ:
    _fd, _path = tempfile.mkstemp(suffix=".db")
    os.close(_fd)
    os.environ["ZONGZI_DATABASE_PATH"] = _path

# 保证能 import app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.task_monitor import TaskMonitor


def make_mock_client(file_names):
    """构造返回 get_torrent_files 的 mock 客户端"""
    client = MagicMock()
    client.get_torrent_files.return_value = [{"name": n} for n in file_names]
    return client


def use_qb_move(use_copy: bool, has_any_folder: bool) -> bool:
    """与 _handle_completed_task 中一致：仅根目录文件时移动，带目录且 use_copy 时复制"""
    return (use_copy and not has_any_folder) or (not use_copy)


def main():
    monitor = TaskMonitor()
    hash_dummy = "abc123"

    cases = [
        ("仅根目录单文件 video.mkv", ["video.mkv"]),
        ("带一层目录 Folder/a.mkv", ["Folder/a.mkv"]),
        ("带多文件夹 FolderA/a.mkv, FolderB/b.mkv", ["FolderA/a.mkv", "FolderB/b.mkv"]),
        ("带嵌套目录 Folder/Sub/file.mkv", ["Folder/Sub/file.mkv"]),
    ]

    print("=" * 70)
    print("TaskMonitor 本地测试：仅根目录=移动，带目录=复制（use_copy 时）")
    print("=" * 70)

    for label, file_names in cases:
        client = make_mock_client(file_names)
        is_single = monitor._is_single_file_torrent(client, hash_dummy)
        has_any_folder = monitor._has_any_folder(client, hash_dummy)
        move_when_copy_off = use_qb_move(False, has_any_folder)
        move_when_copy_on = use_qb_move(True, has_any_folder)
        print(f"\n【{label}】")
        print(f"  文件列表: {file_names}")
        print(f"  单文件: {is_single}, 带目录: {has_any_folder}")
        print(f"  use_copy=False -> {'移动' if move_when_copy_off else '复制'}")
        print(f"  use_copy=True  -> {'移动' if move_when_copy_on else '复制'}")

    # 可选：在临时目录里建真实文件夹结构，仅用于观察路径，不参与逻辑
    print("\n" + "=" * 70)
    print("临时目录结构（仅用于对照，逻辑仍用 mock 文件列表）")
    print("=" * 70)
    with tempfile.TemporaryDirectory(prefix="zongzi_test_") as tmp:
        (Path(tmp) / "video.mkv").write_text("")
        (Path(tmp) / "Folder").mkdir()
        (Path(tmp) / "Folder" / "a.mkv").write_text("")
        (Path(tmp) / "Folder" / "Sub").mkdir()
        (Path(tmp) / "Folder" / "Sub" / "file.mkv").write_text("")
        for root, dirs, files in os.walk(tmp):
            level = root.replace(tmp, "").count(os.sep)
            indent = "  " * level
            print(f"{indent}{os.path.basename(root) or '(根)'}/")
            for f in files:
                print(f"{indent}  {f}")
    print("\n完成。运行 pytest 可执行: pytest tests/test_task_monitor.py -v")


if __name__ == "__main__":
    main()
