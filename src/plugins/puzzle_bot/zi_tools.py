"""字统网 lookup 客户端（非官方接口，无稳定性承诺）。"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional
from urllib.parse import quote

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

import requests

# 非官方：https://zi.tools/api/lookup/lookup/{query}
ZI_TOOLS_BASE = "https://zi.tools"
USER_AGENT = "pzbot-nz-b/1.0"
TIMEOUT_SECONDS = 10
NZ_B_RE = re.compile(r"\(nz@b\(([^)]*)\)\)|nz@b\(([^)]*)\)")

_CACHE: Dict[frozenset[str], List[str]] = {}

_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0x2B740, 0x2B81F),
    (0x2B820, 0x2CEAF),
    (0x2CEB0, 0x2EBEF),
    (0x30000, 0x3134F),
    (0x31350, 0x323AF),
    (0x2EBF0, 0x2EE5F),
)


class ZiToolsError(Exception):
    """字统查询失败。str(e) 为原因，由调用方加上「字统部件查询失败：」前缀。"""


def normalize_components(comp_str: str) -> frozenset[str]:
    return frozenset(c for c in comp_str if not c.isspace())


def lookup_query(components: frozenset[str]) -> str:
    return " ".join(sorted(components))


def is_cjk_ideograph(ch: str) -> bool:
    if len(ch) != 1:
        return False
    cp = ord(ch)
    return any(start <= cp <= end for start, end in _CJK_RANGES)


def parse_lookup_chars(payload: object) -> List[str]:
    if not isinstance(payload, dict):
        raise ZiToolsError("响应不是 JSON 对象")
    res = payload.get("res")
    if not isinstance(res, list) or len(res) < 2:
        raise ZiToolsError("响应缺少有效的 res 列表")
    seen: set[str] = set()
    chars: List[str] = []
    for group in res[:2]:
        if not isinstance(group, list):
            raise ZiToolsError("res 分组格式无效")
        for item in group:
            token = item[0] if isinstance(item, (list, tuple)) and item else item
            if not isinstance(token, str) or token in seen or not is_cjk_ideograph(token):
                continue
            seen.add(token)
            chars.append(token)
    return chars


def extract_component_groups(pattern: str) -> List[frozenset[str]]:
    groups: List[frozenset[str]] = []
    seen: set[frozenset[str]] = set()
    for match in NZ_B_RE.finditer(pattern):
        key = normalize_components(match.group(1) or match.group(2) or "")
        if key in seen:
            continue
        seen.add(key)
        groups.append(key)
    return groups


def cache_clear() -> None:
    _CACHE.clear()


def cache_get(components: frozenset[str]) -> Optional[List[str]]:
    chars = _CACHE.get(components)
    return None if chars is None else list(chars)


def cache_put(components: frozenset[str], chars: List[str]) -> None:
    _CACHE[components] = list(chars)


def _get_base_url() -> str:
    try:
        from nonebot import get_driver
        configured = getattr(get_driver().config, "zi_tools_url", None)
    except Exception:
        configured = None
    return str(configured or ZI_TOOLS_BASE).rstrip("/")


def lookup_url(components: frozenset[str], base: Optional[str] = None) -> str:
    root = (base or _get_base_url()).rstrip("/")
    encoded = quote(lookup_query(components), safe="")
    return f"{root}/api/lookup/lookup/{encoded}"


async def http_get_json(url: str) -> object:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        if AIOHTTP_AVAILABLE:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        raise ZiToolsError(f"HTTP {resp.status}")
                    return await resp.json(content_type=None)
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        if resp.status_code != 200:
            raise ZiToolsError(f"HTTP {resp.status_code}")
        return resp.json()
    except ZiToolsError:
        raise
    except json.JSONDecodeError:
        raise ZiToolsError("响应不是合法 JSON") from None
    except Exception as exc:
        raise ZiToolsError(str(exc)) from exc


async def fetch_chars(components: frozenset[str]) -> List[str]:
    cached = cache_get(components)
    if cached is not None:
        return cached
    if not components:
        cache_put(components, [])
        return []
    payload = await http_get_json(lookup_url(components))
    chars = parse_lookup_chars(payload)
    cache_put(components, chars)
    return chars


async def prefetch_components(pattern: str) -> None:
    groups = extract_component_groups(pattern)
    if not groups:
        return
    import asyncio
    await asyncio.gather(*(fetch_chars(group) for group in groups))
