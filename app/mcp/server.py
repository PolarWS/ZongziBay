"""ZongziBay MCP Server

通过 Model Context Protocol 对外暴露 ZongziBay 的核心功能。
使用 mcp Python SDK，通过 SSE 端点对外提供服务。

启动方式（FastAPI 集成）:
    from app.mcp.server import create_mcp_app
    mcp_app = create_mcp_app()
    app.mount("/mcp", mcp_app)
"""

import asyncio
import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

from app.mcp.auth import require_scope
from app.services.piratebay_service import PirateBayService
from app.services.anime_garden_service import AnimeGardenService
from app.services.magnet_service import magnet_service
from app.services.task_service import task_service
from app.services.tmdb_service import tmdb_service
from app.services.bangumi_service import bangumi_service
from app.services.assrt_service import assrt_service
from app.core.db import get_download_tasks, get_download_task_by_id
from app.core.config import config

logger = logging.getLogger("zongzibay.mcp")

# 创建 MCP Server 实例
mcp = FastMCP(
    name="ZongziBay",
    instructions="ZongziBay 媒体下载与管理助手 — 搜索种子、管理下载、获取媒体元数据、浏览番剧日历",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

piratebay_service = PirateBayService()
anime_garden_service = AnimeGardenService()


# ================================================================
# Tool 1: search_torrents — 搜索种子资源
# ================================================================
@mcp.tool()
async def search_torrents(
    query: str,
    source: str = "all",
    page: int = 1,
) -> str:
    """搜索种子资源，支持海盗湾和动漫花园。

    Args:
        query: 搜索关键词
        source: 搜索来源，可选值: piratebay（海盗湾，适合电影/剧集）, anime（动漫花园，适合番剧）, all（全部）
        page: 页码，从1开始
    """
    require_scope("search")
    results = []

    if source in ("piratebay", "all"):
        try:
            pirate_results = await asyncio.to_thread(piratebay_service.search, query)
            for r in pirate_results[:10]:
                item = r.__dict__ if hasattr(r, "__dict__") else r
                results.append({
                    "source": "piratebay",
                    "title": str(item.get("name", item.get("title", ""))),
                    "magnet": str(item.get("magnet", "")),
                    "size": str(item.get("size", "")),
                    "seeders": int(item.get("seeders", 0)),
                    "leechers": int(item.get("leechers", 0)),
                })
        except Exception as e:
            logger.warning(f"PirateBay 搜索失败: {e}")

    if source in ("anime", "all"):
        try:
            anime_results = await asyncio.to_thread(anime_garden_service.search, query, page, 10)
            for r in anime_results[:10]:
                item = r.__dict__ if hasattr(r, "__dict__") else r
                results.append({
                    "source": "anime_garden",
                    "title": str(item.get("name", item.get("title", ""))),
                    "magnet": str(item.get("magnet", "")),
                    "size": str(item.get("size", "")),
                    "team": str(item.get("team", "")),
                })
        except Exception as e:
            logger.warning(f"Anime Garden 搜索失败: {e}")

    if not results:
        return "未找到相关种子资源。"

    lines = [f"搜索「{query}」共找到 {len(results)} 条结果："]
    for i, r in enumerate(results, 1):
        source_label = "🏴‍☠️" if r["source"] == "piratebay" else "🌸"
        magnet_preview = r.get("magnet", "")[:60] + "..." if len(r.get("magnet", "")) > 60 else r.get("magnet", "")
        lines.append(f"{i}. {source_label} {r['title']}")
        lines.append(f"   大小: {r.get('size', 'N/A')} | 种子: {r.get('seeders', 'N/A')} | Magnet: {magnet_preview}")
    return "\n".join(lines)


# ================================================================
# Tool 2: parse_magnet — 解析磁力链接
# ================================================================
@mcp.tool()
async def parse_magnet(magnet_link: str) -> str:
    """解析磁力链接，查看包含的文件列表。

    Args:
        magnet_link: 磁力链接（magnet:?xt=urn:btih:...）
    """
    require_scope("search")
    try:
        files = await asyncio.to_thread(magnet_service.parse_magnet, magnet_link)
        if not files:
            return "未能解析该磁力链接，或链接中没有文件。"
        lines = [f"磁力链接包含 {len(files)} 个文件："]
        for i, f in enumerate(files, 1):
            name = f.get("name", f) if isinstance(f, dict) else str(f)
            size = f.get("size", "") if isinstance(f, dict) else ""
            size_str = f" ({size})" if size else ""
            lines.append(f"  {i}. {name}{size_str}")
        return "\n".join(lines)
    except ValueError:
        return "无效的磁力链接格式。"
    except Exception as e:
        return f"解析失败: {str(e)}"


# ================================================================
# Tool 3: add_download — 提交下载任务
# ================================================================
@mcp.tool()
async def add_download(
    magnet_link: str,
    save_path: str = "",
    task_name: str = "",
) -> str:
    """提交磁力链接到 qBittorrent 下载。

    Args:
        magnet_link: 磁力链接
        save_path: 保存路径（可选，不填则使用默认下载路径）
        task_name: 任务名称（可选，用于标识）
    """
    require_scope("download")
    try:
        result = await asyncio.to_thread(
            magnet_service.add_magnet_download,
            magnet_link,
            save_path if save_path else None,
        )
        return f"✅ 下载任务已提交。\n详情: {result}"
    except Exception as e:
        return f"❌ 提交下载失败: {str(e)}"


# ================================================================
# Tool 4: list_downloads — 查看下载任务列表
# ================================================================
@mcp.tool()
async def list_downloads(
    page: int = 1,
    page_size: int = 10,
    status: str = "",
) -> str:
    """查看下载任务列表和进度。

    Args:
        page: 页码，从1开始
        page_size: 每页数量，默认10
        status: 按状态过滤（可选），如: downloading, seeding, completed, error
    """
    require_scope("read")
    try:
        tasks, total = await asyncio.to_thread(get_download_tasks, page, page_size)
        if not tasks:
            return "当前没有下载任务。"

        filtered = tasks
        if status:
            filtered = [t for t in tasks if t.get("taskStatus", "") == status]

        lines = [f"下载任务列表（共 {total} 个，当前页 {len(filtered)} 个）："]
        for t in filtered:
            status_emoji = {
                "downloading": "⬇️",
                "seeding": "🌱",
                "completed": "✅",
                "error": "❌",
                "cancelled": "🚫",
                "moving": "📦",
                "pending_download": "⏳",
            }.get(t.get("taskStatus", ""), "📌")
            lines.append(
                f"  {t['id']}. {status_emoji} {t.get('taskName', 'N/A')} "
                f"[{t.get('taskStatus', 'N/A')}] "
                f"进度: {t.get('taskInfo', 'N/A')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"获取任务列表失败: {str(e)}"


# ================================================================
# Tool 5: cancel_download — 取消下载任务
# ================================================================
@mcp.tool()
async def cancel_download(task_id: int) -> str:
    """取消指定的下载任务。

    Args:
        task_id: 任务ID（可从 list_downloads 获取）
    """
    require_scope("download")
    try:
        await asyncio.to_thread(task_service.cancel_task, task_id)
        return f"✅ 任务 #{task_id} 已取消。"
    except Exception as e:
        return f"❌ 取消任务失败: {str(e)}"


# ================================================================
# Tool 6: search_movie — 搜索 TMDB 电影
# ================================================================
@mcp.tool()
async def search_movie(
    query: str,
    page: int = 1,
) -> str:
    """在 TMDB 中搜索电影信息。

    Args:
        query: 电影名称关键词
        page: 页码，从1开始
    """
    require_scope("read")
    try:
        results, total = await asyncio.to_thread(tmdb_service.search_movies_with_total, query, page)
        if not results:
            return f"未找到与「{query}」相关的电影。"

        lines = [f"搜索「{query}」共 {total} 部电影（显示前 {len(results)} 部）："]
        for i, r in enumerate(results, 1):
            item = r.__dict__ if hasattr(r, "__dict__") else r
            title = item.get("title", item.get("name", "N/A"))
            year = item.get("release_date", "")[:4] if item.get("release_date") else ""
            overview = (item.get("overview", "") or "")[:100]
            rating = item.get("vote_average", "")
            year_str = f" ({year})" if year else ""
            rating_str = f" ⭐{rating}" if rating else ""
            lines.append(f"  {i}. {title}{year_str}{rating_str} [ID: {item.get('id', 'N/A')}]")
            if overview:
                lines.append(f"     {overview}...")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索电影失败: {str(e)}"


# ================================================================
# Tool 7: search_tv — 搜索 TMDB 剧集/番剧
# ================================================================
@mcp.tool()
async def search_tv(
    query: str,
    page: int = 1,
) -> str:
    """在 TMDB 中搜索电视剧或番剧。

    Args:
        query: 剧集名称关键词
        page: 页码，从1开始
    """
    require_scope("read")
    try:
        results, total = await asyncio.to_thread(tmdb_service.search_tv_shows_with_total, query, page)
        if not results:
            return f"未找到与「{query}」相关的剧集。"

        lines = [f"搜索「{query}」共 {total} 部剧集（显示前 {len(results)} 部）："]
        for i, r in enumerate(results, 1):
            item = r.__dict__ if hasattr(r, "__dict__") else r
            title = item.get("name", item.get("title", "N/A"))
            year = item.get("first_air_date", "")[:4] if item.get("first_air_date") else ""
            overview = (item.get("overview", "") or "")[:100]
            rating = item.get("vote_average", "")
            year_str = f" ({year})" if year else ""
            rating_str = f" ⭐{rating}" if rating else ""
            lines.append(f"  {i}. {title}{year_str}{rating_str} [ID: {item.get('id', 'N/A')}]")
            if overview:
                lines.append(f"     {overview}...")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索剧集失败: {str(e)}"


# ================================================================
# Tool 8: get_trending — 获取热播内容
# ================================================================
@mcp.tool()
async def get_trending(
    media_type: str = "movie",
    window: str = "week",
) -> str:
    """获取 TMDB 热播电影或剧集。

    Args:
        media_type: 媒体类型，movie（电影）或 tv（剧集）
        window: 时间窗口，day（今日）或 week（本周）
    """
    require_scope("read")
    try:
        if media_type == "movie":
            results, _ = await asyncio.to_thread(tmdb_service.get_trending_movies, 1, window)
            label = "热播电影"
        else:
            results, _ = await asyncio.to_thread(tmdb_service.get_trending_tv, 1, window)
            label = "热播剧集"

        if not results:
            return f"暂无{label}数据。"

        time_label = "今日" if window == "day" else "本周"
        lines = [f"{time_label}{label} TOP {len(results)}："]
        for i, r in enumerate(results[:20], 1):
            item = r.__dict__ if hasattr(r, "__dict__") else r
            title = item.get("title") or item.get("name", "N/A")
            rating = item.get("vote_average", "")
            rating_str = f" ⭐{rating}" if rating else ""
            lines.append(f"  {i}. {title}{rating_str} [ID: {item.get('id', 'N/A')}]")
        return "\n".join(lines)
    except Exception as e:
        return f"获取热播列表失败: {str(e)}"


# ================================================================
# Tool 9: get_media_detail — 获取媒体详情
# ================================================================
@mcp.tool()
async def get_media_detail(
    media_type: str,
    tmdb_id: int,
) -> str:
    """获取电影或剧集的详细信息（含简介、评分、类型等）。

    Args:
        media_type: 媒体类型，movie（电影）或 tv（剧集）
        tmdb_id: TMDB ID
    """
    require_scope("read")
    try:
        if media_type == "movie":
            result = await asyncio.to_thread(tmdb_service.get_movie_details, tmdb_id)
        else:
            result = await asyncio.to_thread(tmdb_service.get_tv_details, tmdb_id)

        raw = getattr(result, "_json", None)
        if isinstance(raw, dict):
            data = raw
        elif hasattr(result, "__dict__"):
            data = {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
        else:
            data = result

        title = data.get("title") or data.get("name", "N/A")
        overview = data.get("overview", "无简介")
        rating = data.get("vote_average", "N/A")
        genres = [g.get("name", "") for g in data.get("genres", [])]
        release_date = data.get("release_date") or data.get("first_air_date", "")
        runtime = data.get("runtime") or data.get("episode_run_time", [])
        if isinstance(runtime, list) and runtime:
            runtime = runtime[0]

        lines = [
            f"🎬 {title}",
            f"ID: {tmdb_id}",
            f"评分: ⭐{rating}/10",
            f"类型: {', '.join(genres) if genres else 'N/A'}",
            f"上映日期: {release_date or 'N/A'}",
        ]
        if runtime:
            lines.append(f"时长: {runtime}分钟" if media_type == "movie" else f"单集时长: {runtime}分钟")
        if media_type == "tv":
            seasons = data.get("number_of_seasons", "N/A")
            episodes = data.get("number_of_episodes", "N/A")
            lines.append(f"季数: {seasons} | 总集数: {episodes}")
        lines.append(f"简介: {overview}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取详情失败: {str(e)}"


# ================================================================
# Tool 10: get_bangumi_calendar — 获取番剧周历
# ================================================================
@mcp.tool()
async def get_bangumi_calendar() -> str:
    """获取 Bangumi 本周新番放送日历，按周一到周日排列。"""
    require_scope("read")
    try:
        data = await asyncio.to_thread(bangumi_service.get_calendar)
        if not data:
            return "暂无本周番剧数据。"

        lines = ["📺 本周新番放送日历："]
        for day_data in data:
            if isinstance(day_data, dict):
                weekday = day_data.get("weekday", day_data.get("day", ""))
                items = day_data.get("items", [])
            else:
                weekday = getattr(day_data, "weekday", getattr(day_data, "day", ""))
                items = getattr(day_data, "items", [])

            # weekday 是 {id, cn, en, ja} 结构（BangumiWeekday），不能直接当字典键用，
            # 否则 TypeError: unhashable type: 'dict'。
            if isinstance(weekday, dict):
                label = weekday.get("cn") or weekday.get("en") or "未知"
            else:
                label = getattr(weekday, "cn", None) or str(weekday) or "未知"

            lines.append(f"\n  {label}：")
            for item in items[:10]:
                if isinstance(item, dict):
                    name = item.get("name_cn") or item.get("name", "N/A")
                    score = item.get("score", "")
                    item_id = item.get("id", "N/A")
                else:
                    name = getattr(item, "name_cn", None) or getattr(item, "name", "N/A")
                    score = getattr(item, "score", "")
                    item_id = getattr(item, "id", "N/A")
                score_str = f" ⭐{score}" if score else ""
                lines.append(f"    - {name}{score_str} [ID: {item_id}]")
        return "\n".join(lines)
    except Exception as e:
        return f"获取番剧日历失败: {str(e)}"


# ================================================================
# Tool 11: search_subtitles — 搜索字幕
# ================================================================
@mcp.tool()
async def search_subtitles(
    keyword: str,
    page: int = 1,
) -> str:
    """在 ASSRT 搜索字幕。

    Args:
        keyword: 搜索关键词（剧名/文件名）
        page: 页码，从1开始
    """
    require_scope("search")
    try:
        # 服务层方法名是 search_subs（REST 端 assrt.py 也这么调），且返回 (items, total)
        # 元组而非列表——此处原先调用不存在的 search_subtitles，该工具必然报错。
        page = max(1, page)
        items, total = await asyncio.to_thread(
            assrt_service.search_subs, keyword, (page - 1) * 15, 15
        )
        if not items:
            return f"未找到与「{keyword}」相关的字幕。"

        lines = [f"搜索「{keyword}」的字幕结果（第{page}页，{total} 条）："]
        for i, r in enumerate(items[:15], 1):
            name = getattr(r, "native_name", None) or getattr(r, "videoname", None) or f"字幕 #{r.id}"
            lang = getattr(getattr(r, "lang", None), "desc", "") or ""
            lang_str = f" [{lang}]" if lang else ""
            lines.append(f"  {i}. {name}{lang_str} [ID: {r.id}]")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索字幕失败: {str(e)}"


# ================================================================
# Tool 12: get_system_status — 获取系统状态
# ================================================================
@mcp.tool()
async def get_system_status() -> str:
    """获取 ZongziBay 系统状态，包括 qBittorrent 连接、任务统计等。"""
    require_scope("read")
    lines = ["📊 ZongziBay 系统状态："]
    try:
        tasks, total = get_download_tasks(1, 100)
        status_counts = {}
        for t in tasks:
            s = t.get("taskStatus", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        lines.append(f"总任务数: {total}")
        for status, count in sorted(status_counts.items()):
            emoji = {
                "downloading": "⬇️",
                "seeding": "🌱",
                "completed": "✅",
                "error": "❌",
            }.get(status, "📌")
            lines.append(f"  {emoji} {status}: {count}")
    except Exception as e:
        lines.append(f"任务统计获取失败: {e}")

    try:
        qb_ok = magnet_service.check_connection()
        lines.append(f"qBittorrent: {'✅ 连接正常' if qb_ok else '❌ 连接失败'}")
    except Exception:
        lines.append("qBittorrent: ❌ 无法检测")

    try:
        movie_results, _ = await asyncio.to_thread(tmdb_service.search_movies_with_total, "test", 1)
        lines.append(f"TMDB API: {'✅ 正常' if movie_results is not None else '❌ 异常'}")
    except Exception:
        lines.append("TMDB API: ❌ 无法检测")

    try:
        cfg = config.get_file_config() or {}
        initialized = bool((cfg.get("security") or {}).get("secret_key"))
        lines.append(f"系统已初始化: {'✅' if initialized else '❌ 未初始化'}")
    except Exception:
        pass

    return "\n".join(lines)


def create_mcp_app():
    """创建 MCP SSE 应用，可挂载到 FastAPI"""
    return mcp.sse_app()
