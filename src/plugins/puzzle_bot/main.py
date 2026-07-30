import shlex
from typing import List

import logging

from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, PrivateMessageEvent
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.params import CommandArg
from nonebot.adapters import Message

from .help import HELP_TEXT
from .ciphers import CIPHER_FUNCS, caesar
from .queries import fetch_puzzlendar, query_nutrimatic, query_nutrimatic_zh, fetch_hunt_status
from .chinese_search import search_words, search_poems, search_lyrics, search_idioms, search_ht, search_classics

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


# ===================== 帮助命令 =====================

hlp_cmd = on_command("hlp", aliases={"help", "帮助"}, priority=5, block=True)

@hlp_cmd.handle()
async def handle_hlp(event: MessageEvent):
    await hlp_cmd.finish(HELP_TEXT)


# ===================== Puzzlendar 比赛日程查询 =====================

pc_cmd = on_command("pc", priority=5, block=True)

@pc_cmd.handle()
async def handle_pc(event: MessageEvent):
    result = await fetch_puzzlendar()
    await pc_cmd.finish(result)


# ===================== Nutrimatic 查询 =====================

nu_cmd = on_command("nu", priority=5, block=True)

@nu_cmd.handle()
async def handle_nu(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await nu_cmd.finish("用法：nu <表达式> [-p 页码]")

    # 解析 -p 页码
    page = 0
    parts = arg_text.split()
    if "-p" in parts:
        idx = parts.index("-p")
        try:
            page = int(parts[idx + 1]) - 1  # 用户输入1-based
            parts = parts[:idx]
        except (IndexError, ValueError):
            await nu_cmd.finish("页码格式错误，用法：nu <表达式> [-p 页码]")

    expr = " ".join(parts)
    await nu_cmd.send("Nutrimatic 查询中，请稍候...")
    result = await query_nutrimatic(expr, max(0, page))
    await nu_cmd.finish(result)


# ===================== Nutrimatic 中文查询 =====================

zn_cmd = on_command("zn", priority=5, block=True)

@zn_cmd.handle()
async def handle_zn(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await zn_cmd.finish("用法：zn <中文正则表达式>")
    await zn_cmd.send("Nutrimatic-zh 查询中，请稍候...")
    result = await query_nutrimatic_zh(arg_text)
    await zn_cmd.finish(result)


# ===================== 比赛状态查询 =====================

now_cmd = on_command("now", priority=5, block=True)

@now_cmd.handle()
async def handle_now(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    hunt = arg_text.lower() if arg_text else "bph"  # 默认bph
    result = fetch_hunt_status(hunt)
    await now_cmd.finish(result)


# ===================== 中文词语正则查询 =====================

dc_cmd = on_command("dc", priority=5, block=True)

@dc_cmd.handle()
async def handle_dc(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await dc_cmd.finish("用法：dc <模式>（. 表示任意一个汉字）")
    result = search_words(arg_text)
    await dc_cmd.finish(result)


# ===================== 中文诗词句子正则查询 =====================

sc_cmd = on_command("sc", priority=5, block=True)

@sc_cmd.handle()
async def handle_sc(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await sc_cmd.finish("用法：sc <模式>（. 表示任意一个汉字）")
    result = search_poems(arg_text)
    await sc_cmd.finish(result)


# ===================== 歌词句子正则查询 =====================

gc_cmd = on_command("gc", priority=5, block=True)

@gc_cmd.handle()
async def handle_gc(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await gc_cmd.finish("用法：gc <模式>（. 表示任意一个字符）")
    result = search_lyrics(arg_text)
    await gc_cmd.finish(result)


# ===================== 俗语/谚语正则查询 =====================

sy_cmd = on_command("sy", priority=5, block=True)

@sy_cmd.handle()
async def handle_sy(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await sy_cmd.finish("用法：sy <模式>（. 表示任意一个汉字）")
    result = search_idioms(arg_text)
    await sy_cmd.finish(result)


yy_cmd = on_command("yy", priority=5, block=True)

@yy_cmd.handle()
async def handle_yy(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await yy_cmd.finish("用法：yy <模式>（. 表示任意一个汉字）")
    result = search_idioms(arg_text)
    await yy_cmd.finish(result)


# ===================== 合同查询 =====================

ht_cmd = on_command("ht", priority=5, block=True)

@ht_cmd.handle()
async def handle_ht(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await ht_cmd.finish("用法：ht <两字>（例如：ht 明亮）")
    result = search_ht(arg_text)
    await ht_cmd.finish(result)


# ===================== 古文/经典查询 =====================

gw_cmd = on_command("gw", priority=5, block=True)

@gw_cmd.handle()
async def handle_gw(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await gw_cmd.finish("用法：gw <模式>（. 表示任意一个汉字）")
    result = search_classics(arg_text)
    await gw_cmd.finish(result)


# ===================== 古典密码转换命令 =====================

for _cmd_name, _func in CIPHER_FUNCS.items():
    if _cmd_name in ("cs", "vg"):
        continue  # 特殊处理
    _cipher_cmd = on_command(_cmd_name, priority=5, block=True)

    def _make_cipher_handler(fn, cmd, name):
        async def handler(event: MessageEvent, args: Message = CommandArg()):
            arg_text = args.extract_plain_text().strip()
            if not arg_text:
                await cmd.finish(f"用法：{name} <内容>")
                return
            try:
                result = fn(arg_text)
            except Exception:
                logger.exception("命令 %s 处理失败", name)
                await cmd.finish("处理出错，请检查输入格式。")
                return
            await cmd.finish(str(result))
        return handler

    _cipher_cmd.handle()(_make_cipher_handler(_func, _cipher_cmd, _cmd_name))


# ===================== 凯撒特殊处理（支持可选移位） =====================

cs_cmd = on_command("cs", priority=5, block=True)

@cs_cmd.handle()
async def handle_cs(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await cs_cmd.finish("用法：cs <内容> [移位]")

    parts = arg_text.split()
    shift = None
    # 如果最后一部分是整数，则视为移位量
    if parts[-1].lstrip('-').isdigit():
        shift = int(parts[-1])
        content = " ".join(parts[:-1])
    else:
        content = arg_text

    if not content:
        await cs_cmd.finish("用法：cs <内容> [移位]")

    result = caesar(content, shift)
    await cs_cmd.finish(result)


# ===================== 维吉尼亚特殊处理 =====================

vg_cmd = on_command("vg", priority=5, block=True)

@vg_cmd.handle()
async def handle_vg(event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await vg_cmd.finish("用法：vg <参数1> <参数2>（明文/密文/密钥选2项）")

    try:
        parts = shlex.split(arg_text)
    except ValueError:
        parts = arg_text.split()

    if len(parts) != 2:
        await vg_cmd.finish("用法：vg <参数1> <参数2>（明文/密文/密钥选2项）")

    result = CIPHER_FUNCS["vg"](parts)
    await vg_cmd.finish(result)
