import shlex
from collections.abc import Awaitable, Callable

import logging

from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
)
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.adapters import Message

from .help import COMMAND_GROUPS, DispatchRequest, render_help, resolve_group
from .feedback import handle_feedback, is_enabled
from .ciphers import CIPHER_FUNCS, caesar
from .queries import fetch_puzzlendar, query_nutrimatic, query_nutrimatic_zh
from .chinese_search import search_words, search_poems, search_lyrics, search_idioms, search_ht, search_classics, run_search_with_nz

logger = logging.getLogger(__name__)


# ===================== 权限控制 =====================

# 从 .env 读取白名单，逗号分隔；设置为 * 表示允许所有群/所有私聊用户
_config = get_driver().config
ALLOWED_GROUP_IDS = {x.strip() for x in str(getattr(_config, "allowed_group_ids", "")).split(",") if x.strip()}
ALLOWED_PRIVATE_USERS = {x.strip() for x in str(getattr(_config, "allowed_private_users", "")).split(",") if x.strip()}


def _is_group_allowed(group_id: str) -> bool:
    return "*" in ALLOWED_GROUP_IDS or group_id in ALLOWED_GROUP_IDS


def _is_private_allowed(user_id: str) -> bool:
    return "*" in ALLOWED_PRIVATE_USERS or user_id in ALLOWED_PRIVATE_USERS


@event_preprocessor
async def check_message_permission(event: MessageEvent):
    """全局消息权限过滤：只允许指定群或指定私聊用户触发命令"""
    if isinstance(event, GroupMessageEvent):
        if not _is_group_allowed(str(event.group_id)):
            raise IgnoredException(f"群 {event.group_id} 不在白名单")
    elif isinstance(event, PrivateMessageEvent):
        if not _is_private_allowed(str(event.user_id)):
            raise IgnoredException(f"用户 {event.user_id} 不在白名单")
    else:
        raise IgnoredException("非群/私聊消息已忽略")


# ===================== 二级命令执行器 =====================

Executor = Callable[[type[Matcher], str], Awaitable[None]]


def _text_search_executor(func: Callable[[str], str]) -> Executor:
    async def execute(matcher: type[Matcher], payload: str) -> None:
        from .zi_tools import extract_component_groups
        if extract_component_groups(payload):
            await matcher.send("部件查询中，请稍候...")
        await matcher.finish(await run_search_with_nz(func, payload))

    return execute


def _cipher_executor(func: Callable[[str], object], name: str) -> Executor:
    async def execute(matcher: type[Matcher], payload: str) -> None:
        try:
            result = func(payload)
        except Exception:
            logger.exception("命令 %s 处理失败", name)
            await matcher.finish("处理出错，请检查输入格式。")
        await matcher.finish(str(result))

    return execute


async def _execute_nu_en(matcher: type[Matcher], payload: str) -> None:
    page = 0
    parts = payload.split()
    if "-p" in parts:
        index = parts.index("-p")
        try:
            page = int(parts[index + 1]) - 1
        except (IndexError, ValueError):
            await matcher.finish("页码格式错误。\n\n" + render_help("nu en"))
        parts = parts[:index]

    expression = " ".join(parts)
    if not expression:
        await matcher.finish(render_help("nu en"))
    await matcher.send("Nutrimatic 查询中，请稍候...")
    await matcher.finish(await query_nutrimatic(expression, max(0, page)))


async def _execute_nu_zh(matcher: type[Matcher], payload: str) -> None:
    await matcher.send("Nutrimatic-zh 查询中，请稍候...")
    await matcher.finish(await query_nutrimatic_zh(payload))


async def _execute_hunt_calendar(matcher: type[Matcher], payload: str) -> None:
    if payload:
        await matcher.finish(render_help("hu ca"))
    await matcher.finish(await fetch_puzzlendar())


async def _execute_caesar(matcher: type[Matcher], payload: str) -> None:
    parts = payload.split()
    shift = None
    if parts[-1].lstrip("-").isdigit():
        shift = int(parts[-1])
        content = " ".join(parts[:-1])
    else:
        content = payload

    if not content:
        await matcher.finish(render_help("ci cae"))
    await matcher.finish(caesar(content, shift))


async def _execute_vigenere(matcher: type[Matcher], payload: str) -> None:
    try:
        parts = shlex.split(payload)
    except ValueError:
        parts = payload.split()

    if len(parts) != 2:
        await matcher.finish(render_help("ci vi"))
    await matcher.finish(CIPHER_FUNCS["vg"](parts))


EXECUTORS: dict[str, Executor] = {
    "nu_en": _execute_nu_en,
    "nu_zh": _execute_nu_zh,
    "search_word": _text_search_executor(search_words),
    "search_poem": _text_search_executor(search_poems),
    "search_lyrics": _text_search_executor(search_lyrics),
    "search_saying": _text_search_executor(search_idioms),
    "search_contract": _text_search_executor(search_ht),
    "search_classic": _text_search_executor(search_classics),
    "cipher_morse": _cipher_executor(CIPHER_FUNCS["ms"], "cipher morse"),
    "cipher_a1z26": _cipher_executor(CIPHER_FUNCS["az"], "cipher a1z26"),
    "cipher_binary": _cipher_executor(CIPHER_FUNCS["bi"], "cipher binary"),
    "cipher_ternary": _cipher_executor(CIPHER_FUNCS["tri"], "cipher ternary"),
    "cipher_cantor": _cipher_executor(CIPHER_FUNCS["ct"], "cipher cantor"),
    "cipher_polybius": _cipher_executor(CIPHER_FUNCS["cb"], "cipher polybius"),
    "cipher_braille": _cipher_executor(CIPHER_FUNCS["br"], "cipher braille"),
    "cipher_semaphore": _cipher_executor(CIPHER_FUNCS["smph"], "cipher semaphore"),
    "cipher_dna": _cipher_executor(CIPHER_FUNCS["dna"], "cipher dna"),
    "cipher_t9": _cipher_executor(CIPHER_FUNCS["9j"], "cipher t9"),
    "cipher_wubi": _cipher_executor(CIPHER_FUNCS["wb"], "cipher wubi"),
    "cipher_mixed": _cipher_executor(CIPHER_FUNCS["hh"], "cipher mixed"),
    "cipher_caesar": _execute_caesar,
    "cipher_vigenere": _execute_vigenere,
    "hunt_calendar": _execute_hunt_calendar,
}


# ===================== 一级命令分发 =====================

async def _dispatch_group(
    matcher: type[Matcher], group_name: str, arg_text: str
) -> None:
    resolution = resolve_group(group_name, arg_text)
    if isinstance(resolution, str):
        await matcher.finish(resolution)
    request: DispatchRequest = resolution
    await EXECUTORS[request.command.handler_key](matcher, request.payload)


ROOT_MATCHERS = {
    group_name: on_command(
        group_name, priority=5, block=True, force_whitespace=True
    )
    for group_name in COMMAND_GROUPS
}


def _make_group_handler(
    matcher: type[Matcher], group_name: str
) -> Callable[[Message], Awaitable[None]]:
    async def handle(args: Message = CommandArg()) -> None:
        await _dispatch_group(matcher, group_name, args.extract_plain_text())

    return handle


for _group_name, _matcher in ROOT_MATCHERS.items():
    _matcher.handle()(_make_group_handler(_matcher, _group_name))


help_cmd = on_command("help", priority=5, block=True, force_whitespace=True)


@help_cmd.handle()
async def handle_help(args: Message = CommandArg()) -> None:
    await help_cmd.finish(render_help(args.extract_plain_text()))


if is_enabled():
    fb_cmd = on_command("fb", priority=5, block=True, force_whitespace=True)

    @fb_cmd.handle()
    async def handle_fb(
        bot: Bot, event: MessageEvent, args: Message = CommandArg()
    ) -> None:
        group_id = (
            event.group_id if isinstance(event, GroupMessageEvent) else None
        )
        reply = await handle_feedback(
            bot,
            args.extract_plain_text(),
            event.user_id,
            group_id,
        )
        await fb_cmd.finish(reply)
