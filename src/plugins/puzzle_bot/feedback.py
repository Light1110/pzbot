import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

CHINA_TZ = timezone(timedelta(hours=8))

SUCCESS_REPLY = "已收到，感谢您的反馈"
FAILURE_REPLY = "反馈发送失败，请稍后再试"


def format_author_message(
    *,
    user_id: int | str,
    content: str,
    group_id: int | str | None = None,
    now: datetime | None = None,
) -> str:
    when = now if now is not None else datetime.now(CHINA_TZ)
    stamp = when.astimezone(CHINA_TZ).strftime("%Y-%m-%d %H:%M")
    if group_id is None:
        source = f"私聊，用户 {user_id}"
    else:
        source = f"群 {group_id}，用户 {user_id}"
    return (
        f"【反馈】\n"
        f"来源：{source}\n"
        f"时间：{stamp}\n"
        f"内容：\n"
        f"{content}"
    )


def parse_author_qq(raw: object | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if value.isdigit():
        return value
    return None


def help_home_line() -> str:
    return "• fb：向作者发送反馈"


def render_fb_help() -> str:
    return "\n".join(
        [
            "向作者发送反馈",
            "用法：fb <内容>",
            "示例：fb 检索结果好像少了一句",
        ]
    )


def configured_author_qq() -> str | None:
    from nonebot import get_driver

    raw = getattr(get_driver().config, "feedback_author_qq", "")
    return parse_author_qq(raw)


def is_enabled() -> bool:
    return configured_author_qq() is not None


async def handle_feedback(
    bot: Any,
    payload: str,
    user_id: int | str,
    group_id: int | str | None = None,
    *,
    now: datetime | None = None,
    author_qq: str | None = None,
) -> str:
    content = payload.strip()
    if not content:
        return render_fb_help()

    qq = parse_author_qq(author_qq) if author_qq is not None else configured_author_qq()
    if qq is None:
        return FAILURE_REPLY

    message = format_author_message(
        user_id=user_id, content=content, group_id=group_id, now=now
    )
    try:
        await bot.send_private_msg(user_id=int(qq), message=message)
    except Exception:
        logger.exception("发送反馈私聊失败")
        return FAILURE_REPLY
    return SUCCESS_REPLY
