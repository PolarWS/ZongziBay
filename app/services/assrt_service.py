# ASSRT 字幕站 API 封装：搜索、详情、相似；字幕为 HTTP 直链，由本程序下载后走任务队列（移动/重命名），不经过 qB
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import config
from app.core.db import db
from app.schemas.assrt import (
    AssrtFileListItem,
    AssrtLang,
    AssrtLangList,
    AssrtProducer,
    AssrtSubDetail,
    AssrtSubItem,
)
from app.schemas.base import BusinessException, ErrorCode
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)


def _resolve_download_path(relative_path: str) -> str:
    """将配置中的相对路径（如 /downloads）解析为本机路径：拼上 download_root_path 或 root_path。"""
    if not relative_path or not str(relative_path).strip():
        return relative_path or ""
    paths_cfg = config.get("paths", {}) or {}
    root = paths_cfg.get("download_root_path") or paths_cfg.get("root_path") or ""
    if not root:
        return os.path.abspath(os.path.expanduser(str(relative_path)))
    normalized = str(relative_path).replace("\\", "/").strip()
    if normalized.startswith("/"):
        rel = normalized.lstrip("/")
        if not rel:
            return os.path.normpath(root)
        return os.path.normpath(os.path.join(root, *rel.split("/")))
    return os.path.abspath(os.path.expanduser(relative_path))


def _get_subtitle_download_dir() -> str:
    """字幕 HTTP 下载的临时目录（paths.subtitle_download_path），会拼上 download_root_path。"""
    raw = config.get("paths.subtitle_download_path") or config.get("paths.default_download_path") or "/temp"
    dir_path = _resolve_download_path(raw)
    try:
        os.makedirs(dir_path, exist_ok=True)
    except OSError as e:
        logger.warning("创建字幕下载目录失败 %s: %s", dir_path, e)
    return dir_path

# ASSRT 错误码与说明（文档）
ASSRT_ERROR_MESSAGES = {
    1: "用户不存在",
    101: "搜索关键词长度必须大于3",
    20000: "请求缺少参数",
    20001: "Token不存在或无效",
    20400: "API终结点不存在",
    20900: "字幕不存在",
    30000: "服务器异常",
    30001: "数据库不可用",
    30002: "搜索引擎不可用",
    30300: "API暂时不可用",
    30900: "请求配额超限",
}


def _raise_if_error(resp: Dict[str, Any]) -> None:
    status = resp.get("status", 0)
    if status == 0:
        return
    msg = ASSRT_ERROR_MESSAGES.get(status) or resp.get("errmsg", f"ASSRT 错误 {status}")
    if 20000 <= status < 30000:
        raise BusinessException(code=ErrorCode.PARAMS_ERROR.code, message=msg)
    if status >= 30000:
        raise BusinessException(code=ErrorCode.SYSTEM_ERROR.code, message=msg)
    raise BusinessException(code=ErrorCode.PARAMS_ERROR.code, message=msg)


def _parse_lang(raw: Any) -> Optional[AssrtLang]:
    if not raw or not isinstance(raw, dict):
        return None
    langlist = raw.get("langlist")
    if isinstance(langlist, dict):
        langlist = AssrtLangList(**{k: v for k, v in langlist.items() if k in AssrtLangList.model_fields})
    else:
        langlist = None
    return AssrtLang(langlist=langlist, desc=raw.get("desc"))


def _sub_item_from_raw(raw: Dict[str, Any]) -> AssrtSubItem:
    lang = _parse_lang(raw.get("lang"))
    return AssrtSubItem(
        id=raw.get("id", 0),
        native_name=raw.get("native_name"),
        revision=raw.get("revision", 0),
        subtype=raw.get("subtype"),
        upload_time=raw.get("upload_time"),
        vote_score=raw.get("vote_score", 0),
        release_site=raw.get("release_site"),
        videoname=raw.get("videoname"),
        lang=lang,
    )


def _sub_detail_from_raw(raw: Dict[str, Any]) -> AssrtSubDetail:
    item = _sub_item_from_raw(raw)
    filelist = raw.get("filelist")
    if isinstance(filelist, list):
        filelist = [
            AssrtFileListItem(url=f.get("url"), f=f.get("f"), s=f.get("s"))
            for f in filelist
            if isinstance(f, dict)
        ]
    else:
        filelist = None
    producer = raw.get("producer")
    if isinstance(producer, dict):
        producer = AssrtProducer(
            uploader=producer.get("uploader"),
            verifier=producer.get("verifier"),
            producer=producer.get("producer"),
            source=producer.get("source"),
        )
    else:
        producer = None
    return AssrtSubDetail(
        **item.model_dump(),
        filename=raw.get("filename"),
        size=raw.get("size"),
        url=raw.get("url"),
        view_count=raw.get("view_count"),
        down_count=raw.get("down_count"),
        title=raw.get("title"),
        filelist=filelist,
        producer=producer,
    )


class AssrtService:
    """ASSRT API 服务"""

    def __init__(self):
        self._token = (config.get("subtitle.assrt.token") or "").strip()
        base = (config.get("subtitle.assrt.base_url") or "https://api.assrt.net").strip()
        self._base_url = base.rstrip("/") if base else "https://api.assrt.net"

    def is_available(self) -> bool:
        return bool(self._token and len(self._token) >= 32)

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_available():
            raise BusinessException(code=ErrorCode.SYSTEM_ERROR.code, message="字幕服务 ASSRT 未配置或未启用")
        url = f"{self._base_url}/v1{path}"
        req_params = {"token": self._token}
        if params:
            req_params.update(params)
        try:
            r = requests.get(url, params=req_params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except requests.HTTPError as e:
            logger.warning("ASSRT 请求失败 %s: %s", url, e)
            code = e.response.status_code if e.response is not None else 0
            if code == 509:
                raise BusinessException(
                    code=ErrorCode.SYSTEM_ERROR.code,
                    message="ASSRT 返回 509：接口限流或配额用尽，请稍后再试或检查ASSRT配额",
                )
            if code == 429:
                raise BusinessException(
                    code=ErrorCode.SYSTEM_ERROR.code,
                    message="ASSRT 请求过于频繁(429)，请稍后再试",
                )
            raise BusinessException(code=ErrorCode.SYSTEM_ERROR.code, message=f"请求字幕服务失败: {e}")
        except requests.RequestException as e:
            logger.warning("ASSRT 请求失败 %s: %s", url, e)
            raise BusinessException(code=ErrorCode.SYSTEM_ERROR.code, message=f"请求字幕服务失败: {e}")
        if not isinstance(data, dict):
            raise BusinessException(code=ErrorCode.SYSTEM_ERROR.code, message="字幕服务返回格式异常")
        _raise_if_error(data)
        return data

    def search_subs(
        self,
        q: str,
        pos: int = 0,
        cnt: int = 15,
        is_file: bool = False,
        no_muxer: bool = False,
    ) -> Tuple[List[AssrtSubItem], int]:
        """搜索字幕。返回 (列表, 总数)。"""
        q = (q or "").strip()
        if len(q) < 3:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR.code, message="搜索关键词长度必须大于3")
        cnt = max(1, min(15, cnt))
        params: Dict[str, Any] = {"q": q, "pos": pos, "cnt": cnt}
        if is_file:
            params["is_file"] = 1
        if no_muxer:
            params["no_muxer"] = 1
        data = self._request("/sub/search", params)
        sub = data.get("sub") or {}
        subs = sub.get("subs") or []
        items = [_sub_item_from_raw(s) for s in subs if isinstance(s, dict) and s.get("id")]
        total = len(items)
        return items, total

    def get_sub_detail(self, sub_id: int) -> AssrtSubDetail:
        """获取字幕详情（含下载链接）。"""
        if not (0 < sub_id < 10**7):
            raise BusinessException(code=ErrorCode.PARAMS_ERROR.code, message="字幕 ID 无效")
        data = self._request("/sub/detail", {"id": sub_id})
        sub = data.get("sub") or {}
        subs = sub.get("subs") or []
        if not subs or not isinstance(subs[0], dict):
            raise BusinessException(code=ErrorCode.NOT_FOUND_ERROR.code, message="字幕不存在")
        return _sub_detail_from_raw(subs[0])

    def get_similar_subs(self, sub_id: int) -> List[AssrtSubItem]:
        """获取与某字幕类似的其他字幕（最多 5 条）。"""
        if not (0 < sub_id < 10**7):
            raise BusinessException(code=ErrorCode.PARAMS_ERROR.code, message="字幕 ID 无效")
        data = self._request("/sub/similar", {"id": sub_id})
        sub = data.get("sub") or {}
        subs = sub.get("subs") or []
        return [_sub_item_from_raw(s) for s in subs if isinstance(s, dict) and s.get("id")]

    def get_quota(self) -> int:
        """获取当前 API 配额（次/分钟）。"""
        data = self._request("/user/quota")
        user = data.get("user") or {}
        return int(user.get("quota", 0))

    def _download_sub_to_path(
        self,
        detail: AssrtSubDetail,
        sub_id: int,
        file_index: Optional[int] = None,
    ) -> Tuple[str, str]:
        """HTTP 下载字幕到 paths.subtitle_download_path，返回 (绝对路径, 文件名)。"""
        download_dir = _get_subtitle_download_dir()
        if file_index is not None and detail.filelist:
            idx = int(file_index)
            if idx < 0 or idx >= len(detail.filelist):
                raise BusinessException(code=ErrorCode.PARAMS_ERROR.code, message="文件索引超出范围")
            entry = detail.filelist[idx]
            file_url = entry.url
            filename = entry.f or f"sub_{sub_id}_{idx}.srt"
        else:
            file_url = detail.url
            filename = detail.filename or f"sub_{sub_id}.rar"
        if not file_url:
            raise BusinessException(code=ErrorCode.OPERATION_ERROR.code, message="无下载链接")
        filename = os.path.basename(filename) or f"sub_{sub_id}"
        safe = re.sub(r"[^\w\-. ]", "_", filename).strip() or f"sub_{sub_id}"
        filename = safe[:200] if len(safe) > 200 else safe
        saved_path = os.path.join(download_dir, filename)
        try:
            r = requests.get(file_url, timeout=30, stream=True)
            r.raise_for_status()
            with open(saved_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except requests.RequestException as e:
            logger.warning("字幕 HTTP 下载失败 %s: %s", file_url, e)
            raise BusinessException(code=ErrorCode.SYSTEM_ERROR.code, message=f"下载失败: {e}")
        except OSError as e:
            logger.warning("字幕写入失败 %s: %s", saved_path, e)
            raise BusinessException(code=ErrorCode.SYSTEM_ERROR.code, message=f"保存失败: {e}")
        return os.path.abspath(saved_path), filename

    def _create_subtitle_download_task_with_detail(
        self,
        detail: AssrtSubDetail,
        sub_id: int,
        file_index: Optional[int],
        target_path: Optional[str],
        file_rename: Optional[str],
    ) -> Tuple[int, str, str, str]:
        """
        使用已拿到的 detail（含下载链接）直接 HTTP 下载并写入任务表，不再请求 ASSRT 详情接口。
        返回 (task_id, task_name, source_path, target_path)。
        """
        saved_path, filename = self._download_sub_to_path(detail, sub_id, file_index)
        source_dir = os.path.dirname(saved_path)
        task_name = (detail.native_name or f"字幕 {sub_id}").strip()
        if len(task_name) > 200:
            task_name = task_name[:200]
        dest_full = ((file_rename or filename) or "").strip() or filename
        dest_full = dest_full.replace("\\", "/")
        dest_dir_relative = os.path.dirname(dest_full)
        if dest_dir_relative and dest_dir_relative != ".":
            dest_filename = os.path.basename(dest_full) or filename
        else:
            dest_dir_relative = ""
            dest_filename = os.path.basename(dest_full) or filename
        final_target = (target_path or "").strip().replace("\\", "/")
        if not final_target:
            final_target = (config.get("paths.default_target_path") or "").replace("\\", "/")
        conn = db.get_conn()
        try:
            task_id = db.insert_download_task(
                taskName=task_name,
                taskInfo=f"ASSRT字幕 #{sub_id}",
                sourceUrl=f"subtitle:{sub_id}",
                sourcePath=source_dir,
                targetPath=final_target,
                taskStatus="moving",
                commit=False,
            )
            db.insert_file_task(
                downloadTaskId=task_id,
                sourcePath=filename,
                targetPath=dest_dir_relative,
                file_rename=dest_filename,
                file_status="pending",
                commit=False,
            )
            conn.commit()
            db.insert_notification(
                title="字幕任务已添加",
                content=f"字幕「{task_name}」已下载并加入任务队列，将由监控移动至目标路径",
                type=NotificationType.SUCCESS.value,
            )
            return task_id, task_name, source_dir, final_target
        except Exception as e:
            conn.rollback()
            logger.error("字幕任务写入失败: %s", e)
            raise BusinessException(
                code=ErrorCode.OPERATION_ERROR.code,
                message=f"添加字幕任务失败: {e}",
            )

    def create_subtitle_download_task(
        self,
        sub_id: int,
        file_index: Optional[int] = None,
        target_path: Optional[str] = None,
        file_rename: Optional[str] = None,
    ) -> Tuple[int, str, str, str]:
        """
        字幕为 HTTP 直链，qB 不支持；由本程序下载后写入任务表，由 task_monitor 移动/重命名。
        返回 (task_id, task_name, source_path, target_path)。
        """
        detail = self.get_sub_detail(sub_id)
        return self._create_subtitle_download_task_with_detail(
            detail, sub_id, file_index, target_path, file_rename
        )

    def create_subtitle_download_task_placeholder(
        self,
        sub_id: int,
        target_path: Optional[str],
        items: List[Tuple[Optional[int], Optional[str]]],
    ) -> int:
        """
        仅创建一条 download_task 与多条 file_task（sourcePath 为空），不请求 ASSRT、不下载。
        任务立即出现在列表；后台再下载并回填 sourcePath、将状态改为 moving。
        返回 task_id。
        """
        if not items:
            raise BusinessException(code=ErrorCode.PARAMS_ERROR.code, message="至少选择一个文件")
        task_name = f"字幕 {sub_id}"
        download_dir = _get_subtitle_download_dir()
        final_target = (target_path or "").strip().replace("\\", "/")
        if not final_target:
            final_target = (config.get("paths.default_target_path") or "").replace("\\", "/")
        conn = db.get_conn()
        try:
            task_id = db.insert_download_task(
                taskName=task_name,
                taskInfo=f"ASSRT字幕 #{sub_id}",
                sourceUrl=f"subtitle:{sub_id}",
                sourcePath=download_dir,
                targetPath=final_target,
                taskStatus="pending_download",
                commit=False,
            )
            for _file_index, file_rename in items:
                dest_full = (file_rename or "").strip().replace("\\", "/") or "sub.srt"
                dest_dir_relative = os.path.dirname(dest_full)
                if dest_dir_relative and dest_dir_relative != ".":
                    dest_filename = os.path.basename(dest_full) or "sub.srt"
                else:
                    dest_dir_relative = ""
                    dest_filename = os.path.basename(dest_full) or "sub.srt"
                db.insert_file_task(
                    downloadTaskId=task_id,
                    sourcePath="",
                    targetPath=dest_dir_relative,
                    file_rename=dest_filename,
                    file_status="pending",
                    commit=False,
                )
            conn.commit()
            return task_id
        except Exception as e:
            conn.rollback()
            logger.error("字幕占位任务写入失败: %s", e)
            raise BusinessException(
                code=ErrorCode.OPERATION_ERROR.code,
                message=f"添加字幕任务失败: {e}",
            )

    def fill_subtitle_downloads_and_start_moving(
        self,
        task_id: int,
        sub_id: int,
        items: List[Tuple[Optional[int], Optional[str]]],
    ) -> None:
        """
        后台：拉取 ASSRT 详情、逐个下载、回填 file_tasks 的 sourcePath，最后将任务状态改为 moving。
        """
        if not items:
            return
        detail = self.get_sub_detail(sub_id)
        task_name = (detail.native_name or f"字幕 {sub_id}").strip()
        if len(task_name) > 200:
            task_name = task_name[:200]
        file_tasks = db.get_file_tasks(task_id)
        file_tasks.sort(key=lambda ft: ft["id"])
        if len(file_tasks) != len(items):
            logger.warning("字幕任务 %s file_tasks 数量与 items 不一致，按最小长度处理", task_id)
        for i, (file_index, _file_rename) in enumerate(items):
            if i >= len(file_tasks):
                break
            try:
                saved_path, filename = self._download_sub_to_path(detail, sub_id, file_index)
                db.update_file_task_source_path(file_tasks[i]["id"], filename)
            except Exception as e:
                logger.exception("字幕任务 %s 第 %s 个文件下载失败: %s", task_id, i, e)
                db.update_file_task_status(file_tasks[i]["id"], "failed", str(e))
        db.update_download_task_name_and_status(task_id, task_name, "moving", task_info=task_name)
        db.insert_notification(
            title="字幕任务已添加",
            content=f"字幕「{task_name}」共 {len(items)} 个文件已下载并加入队列，将由监控移动至目标路径",
            type=NotificationType.SUCCESS.value,
        )

    def create_subtitle_download_tasks_batch(
        self,
        sub_id: int,
        target_path: Optional[str],
        items: List[Tuple[Optional[int], Optional[str]]],
    ) -> List[Tuple[int, str, str, str]]:
        """
        批量创建字幕下载任务：只请求一次 ASSRT 详情，只创建一条 download_task，下多份文件为多条 file_task。
        （若需「先占位再后台下载」请用 create_subtitle_download_task_placeholder + fill_subtitle_downloads_and_start_moving）
        """
        if not items:
            return []
        detail = self.get_sub_detail(sub_id)
        task_name = (detail.native_name or f"字幕 {sub_id}").strip()
        if len(task_name) > 200:
            task_name = task_name[:200]
        download_dir = _get_subtitle_download_dir()
        final_target = (target_path or "").strip().replace("\\", "/")
        if not final_target:
            final_target = (config.get("paths.default_target_path") or "").replace("\\", "/")
        conn = db.get_conn()
        try:
            task_id = db.insert_download_task(
                taskName=task_name,
                taskInfo=f"ASSRT字幕 #{sub_id}",
                sourceUrl=f"subtitle:{sub_id}",
                sourcePath=download_dir,
                targetPath=final_target,
                taskStatus="moving",
                commit=False,
            )
            for file_index, file_rename in items:
                saved_path, filename = self._download_sub_to_path(detail, sub_id, file_index)
                dest_full = ((file_rename or filename) or "").strip() or filename
                dest_full = dest_full.replace("\\", "/")
                dest_dir_relative = os.path.dirname(dest_full)
                if dest_dir_relative and dest_dir_relative != ".":
                    dest_filename = os.path.basename(dest_full) or filename
                else:
                    dest_dir_relative = ""
                    dest_filename = os.path.basename(dest_full) or filename
                db.insert_file_task(
                    downloadTaskId=task_id,
                    sourcePath=filename,
                    targetPath=dest_dir_relative,
                    file_rename=dest_filename,
                    file_status="pending",
                    commit=False,
                )
            conn.commit()
            db.insert_notification(
                title="字幕任务已添加",
                content=f"字幕「{task_name}」共 {len(items)} 个文件已加入任务队列，将由监控移动至目标路径",
                type=NotificationType.SUCCESS.value,
            )
            return [(task_id, task_name, download_dir, final_target)]
        except Exception as e:
            conn.rollback()
            logger.error("字幕批量任务写入失败: %s", e)
            raise BusinessException(
                code=ErrorCode.OPERATION_ERROR.code,
                message=f"添加字幕任务失败: {e}",
            )


assrt_service = AssrtService()
