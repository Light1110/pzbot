import re
import json
import requests
from nonebot import get_driver
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


# ===================== Puzzlendar 比赛日程查询 =====================

PUZZLENDAR_API = "https://api.scieph.com/calendar/list"
CHINA_TZ = timezone(timedelta(hours=8))


def _fmt_timestamp(ts: int) -> str:
    """将Unix时间戳格式化为北京时间字符串"""
    return datetime.fromtimestamp(ts, CHINA_TZ).strftime("%Y-%m-%d %H:%M")


async def fetch_puzzlendar() -> str:
    """从Puzzlendar抓取近期/进行中比赛信息"""
    try:
        if AIOHTTP_AVAILABLE:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post(PUZZLENDAR_API) as resp:
                    resp.raise_for_status()
                    events = await resp.json()
        else:
            resp = requests.post(PUZZLENDAR_API, timeout=15)
            resp.raise_for_status()
            events = resp.json()

        if not isinstance(events, list):
            return "Puzzlendar 返回数据格式异常。"
    except requests.RequestException as e:
        return f"抓取Puzzlendar失败：{e}"
    except json.JSONDecodeError:
        return "Puzzlendar 返回非JSON数据。"
    except Exception as e:
        return f"抓取Puzzlendar失败：{e}"

    now = datetime.now(CHINA_TZ).timestamp()
    # 只显示未结束的比赛，并过滤掉长期活动（持续时间超过1年）
    upcoming = [
        e for e in events
        if e.get("end_time", 0) > now
        and (e.get("end_time", 0) - e.get("start_time", 0)) <= 365 * 24 * 3600
    ]
    upcoming.sort(key=lambda e: e.get("start_time", 0))

    if not upcoming:
        return "当前没有未结束的Puzzle Hunt比赛。"

    lines = ["Puzzlendar 近期/进行中比赛："]
    for idx, e in enumerate(upcoming, 1):
        title = e.get("title") or e.get("title_en") or "未知比赛"
        start = _fmt_timestamp(e.get("start_time", 0))
        end = _fmt_timestamp(e.get("end_time", 0))
        team = e.get("team_number") or "未知"
        url = e.get("url") or "无"
        lines.append(
            f"\n{idx}. {title}\n"
            f"   比赛时间：{start} — {end}\n"
            f"   比赛人数：{team}\n"
            f"   比赛网站：{url}"
        )
    return "\n".join(lines)


# ===================== Nutrimatic 查询 =====================

NUTRIMATIC_BASE = "https://nutrimatic.org/2024/"
NUTRIMATIC_ZH_BASE = "http://127.0.0.1:8081"


def _get_nutrimatic_zh_base() -> str:
    """从 NoneBot 配置读取 nutrimatic-zh 服务地址。"""
    configured_url = getattr(get_driver().config, "nutrimatic_zh_url", None)
    return str(configured_url or NUTRIMATIC_ZH_BASE).rstrip("/")


def _format_nutrimatic_results(expr: str, html: str, page: int) -> str:
    """解析 Nutrimatic 2024 HTML 并格式化结果"""
    # Nutrimatic 2024 的结果在 <span style='font-size: ...em'>...</span> 中
    # font-size 值越大表示概率越高，把它作为可能性分数输出
    matches = re.findall(r"<span style='font-size: ([\d.]+)em'>(.*?)</span>", html)
    if not matches:
        return "Nutrimatic 查询无结果或解析失败。"

    per_page = 10
    total = len(matches)
    # 最多展示前30条
    max_results = 30
    if total > max_results:
        matches = matches[:max_results]

    start = page * per_page
    end = start + per_page
    page_matches = matches[start:end]
    if not page_matches:
        return f"Nutrimatic 查询页码超出范围（共 {min(total, max_results)} 条）。"

    result_text = '\n'.join(f"{score} {word}" for score, word in page_matches)
    total_display = min(total, max_results)
    return f"Nutrimatic 查询：{expr}\n第 {page+1} 页（最多 {total_display} 条，共找到 {total} 条）：\n{result_text}"


async def query_nutrimatic(expr: str, page: int = 0) -> str:
    """Nutrimatic 2024 查询，返回前30条结果，支持分页（异步）"""
    params = {
        "q": expr,
        "go": "Go",
    }
    try:
        if AIOHTTP_AVAILABLE:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(NUTRIMATIC_BASE, params=params) as resp:
                    resp.raise_for_status()
                    html = await resp.text()
                    return _format_nutrimatic_results(expr, html, page)
        else:
            resp = requests.get(NUTRIMATIC_BASE, params=params, timeout=30)
            resp.raise_for_status()
            return _format_nutrimatic_results(expr, resp.text, page)
    except Exception as e:
        return f"Nutrimatic 查询失败：{e}"


# ===================== Nutrimatic 中文查询 =====================

def _format_zh_results(expr: str, events: List[dict]) -> str:
    """格式化 nutrimatic-zh 的流式结果"""
    if not events:
        return "Nutrimatic-zh 查询无结果。"

    final = events[-1]
    results = final.get("results", [])
    visited = final.get("visited", 0)
    stop_reason = final.get("stop_reason")
    limit = 30

    lines = [f"{item.get('score', 0)} {item.get('text', '')}" for item in results[:limit]]
    tail = ""
    if stop_reason:
        reasons = {
            "node_limit": "达到节点检查上限",
            "state_limit": "达到查询状态上限",
            "memory_limit": "达到程序内存上限",
        }
        tail = f"（搜索因 {reasons.get(stop_reason, stop_reason)} 提前停止）"
    return f"Nutrimatic-zh 查询：{expr}\n找到 {len(results)} 条结果，检查 {visited} 个节点{tail}：\n" + '\n'.join(lines)


async def query_nutrimatic_zh(expr: str) -> str:
    """调用 nutrimatic-zh 服务查询中文正则"""
    if not expr:
        return "用法：zn <中文正则表达式>"

    base_url = f"{_get_nutrimatic_zh_base()}/api/search/stream"
    params = {"q": expr, "limit": 30}

    try:
        if AIOHTTP_AVAILABLE:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.get(base_url, params=params) as resp:
                    resp.raise_for_status()
                    events = []
                    buffer = ""
                    async for chunk in resp.content.iter_chunked(4096):
                        buffer += chunk.decode('utf-8')
                        lines = buffer.split('\n')
                        buffer = lines.pop()
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                event = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if event.get("type") == "error":
                                return f"Nutrimatic-zh 查询失败：{event.get('error', '未知错误')}"
                            if event.get("type") in ("progress", "complete"):
                                events.append(event)
                                if event.get("type") == "complete":
                                    break
                    return _format_zh_results(expr, events)
        else:
            resp = requests.get(base_url, params=params, timeout=60, stream=True)
            resp.raise_for_status()
            events = []
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "error":
                    return f"Nutrimatic-zh 查询失败：{event.get('error', '未知错误')}"
                if event.get("type") in ("progress", "complete"):
                    events.append(event)
                    if event.get("type") == "complete":
                        break
            return _format_zh_results(expr, events)
    except requests.RequestException as e:
        return f"Nutrimatic-zh 连接失败：{e}\n请检查 NUTRIMATIC_ZH_URL 配置及服务状态。"
    except Exception as e:
        if AIOHTTP_AVAILABLE and isinstance(e, (aiohttp.ClientError, TimeoutError)):
            return f"Nutrimatic-zh 连接失败：{e}\n请检查 NUTRIMATIC_ZH_URL 配置及服务状态。"
        return f"Nutrimatic-zh 查询失败：{e}"


