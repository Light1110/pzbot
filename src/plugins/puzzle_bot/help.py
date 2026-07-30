from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandSpec:
    name: str
    summary: str
    usage: str
    example: str
    handler_key: str
    requires_args: bool = True


@dataclass(frozen=True)
class GroupSpec:
    name: str
    summary: str
    commands: dict[str, CommandSpec]
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DispatchRequest:
    command: CommandSpec
    payload: str


COMMAND_GROUPS: dict[str, GroupSpec] = {
    "nu": GroupSpec(
        "nu",
        "Nutrimatic 中英文查询",
        {
            "en": CommandSpec(
                "en",
                "Nutrimatic 英文表达式查询",
                "nu en <表达式> [-p 页码]",
                "nu en <A>?<B> -p 2",
                "nu_en",
            ),
            "zh": CommandSpec(
                "zh",
                "Nutrimatic-zh 中文正则查询",
                "nu zh <中文正则表达式>",
                "nu zh ....",
                "nu_zh",
            ),
        },
    ),
    "search": GroupSpec(
        "search",
        "本地中文语料检索",
        {
            "word": CommandSpec(
                "word",
                "中文词语正则查询",
                "search word <模式>",
                "search word A.A",
                "search_word",
            ),
            "poem": CommandSpec(
                "poem",
                "中文诗词句子正则查询",
                "search poem <模式>",
                "search poem ..AAA..",
                "search_poem",
            ),
            "lyrics": CommandSpec(
                "lyrics",
                "歌词句子正则查询",
                "search lyrics <模式>",
                "search lyrics 天..",
                "search_lyrics",
            ),
            "saying": CommandSpec(
                "saying",
                "俗语、谚语和成语正则查询",
                "search saying <模式>",
                "search saying ....",
                "search_saying",
            ),
            "contract": CommandSpec(
                "contract",
                "合同字查询，寻找满足四个组词条件的汉字",
                "search contract <1AB2CD>",
                "search contract 1化.2术.",
                "search_contract",
            ),
            "classic": CommandSpec(
                "classic",
                "古文和经典文本正则查询",
                "search classic <模式>",
                "search classic 学而时习之",
                "search_classic",
            ),
        },
        (
            ". 表示任意一个汉字；同一大写字母 A-Z 表示相同汉字。",
            "nz@b(部件...) 表示包含全部指定部件的单个汉字。",
            "查询结果按可能性分数降序排列。",
        ),
    ),
    "cipher": GroupSpec(
        "cipher",
        "古典密码转换和破解",
        {
            name: CommandSpec(name, summary, usage, example, handler_key)
            for name, summary, usage, example, handler_key in (
                (
                    "morse",
                    "摩斯密码",
                    "cipher morse <内容>",
                    "cipher morse ... --- ...",
                    "cipher_morse",
                ),
                (
                    "a1z26",
                    "A1Z26",
                    "cipher a1z26 <内容>",
                    "cipher a1z26 1 2 3",
                    "cipher_a1z26",
                ),
                (
                    "binary",
                    "5 位二进制",
                    "cipher binary <内容>",
                    "cipher binary 00001",
                    "cipher_binary",
                ),
                (
                    "ternary",
                    "3 位三进制",
                    "cipher ternary <内容>",
                    "cipher ternary 001",
                    "cipher_ternary",
                ),
                (
                    "cantor",
                    "康托展开",
                    "cipher cantor <内容>",
                    "cipher cantor 1234",
                    "cipher_cantor",
                ),
                (
                    "polybius",
                    "棋盘密码",
                    "cipher polybius <内容>",
                    "cipher polybius 11 12",
                    "cipher_polybius",
                ),
                (
                    "braille",
                    "六点盲文",
                    "cipher braille <内容>",
                    "cipher braille 100000",
                    "cipher_braille",
                ),
                (
                    "semaphore",
                    "旗语",
                    "cipher semaphore <内容>",
                    "cipher semaphore 28",
                    "cipher_semaphore",
                ),
                (
                    "dna",
                    "氨基酸密码子（仅解码）",
                    "cipher dna <内容>",
                    "cipher dna AUG",
                    "cipher_dna",
                ),
                (
                    "t9",
                    "九键手机键盘",
                    "cipher t9 <内容>",
                    "cipher t9 21 31",
                    "cipher_t9",
                ),
                (
                    "wubi",
                    "五笔 86 查询",
                    "cipher wubi <汉字或编码>",
                    "cipher wubi 工",
                    "cipher_wubi",
                ),
                (
                    "mixed",
                    "混合密码自动识别并拼接解码",
                    "cipher mixed <段1> <段2> ...",
                    "cipher mixed .. 00001 1234",
                    "cipher_mixed",
                ),
                (
                    "caesar",
                    "凯撒密码（省略移位时穷举）",
                    "cipher caesar <内容> [移位]",
                    "cipher caesar abc 3",
                    "cipher_caesar",
                ),
                (
                    "vigenere",
                    "维吉尼亚密码（明文、密文、密钥任选两项）",
                    "cipher vigenere <参数1> <参数2>",
                    "cipher vigenere attack lemon",
                    "cipher_vigenere",
                ),
            )
        },
        ("部分密码支持 ? 通配符，并会自动判断加密或解密方向。",),
    ),
    "hunt": GroupSpec(
        "hunt",
        "比赛日程和队伍状态",
        {
            "calendar": CommandSpec(
                "calendar",
                "从 Puzzlendar 获取近期或进行中的比赛",
                "hunt calendar",
                "hunt calendar",
                "hunt_calendar",
                requires_args=False,
            ),
            "status": CommandSpec(
                "status",
                "Hunt 期间的队伍状态（默认 bph）",
                "hunt status [赛事]",
                "hunt status bph",
                "hunt_status",
                requires_args=False,
            ),
        },
    ),
}


def render_home() -> str:
    lines = ["可用命令分类："]
    lines.extend(
        f"• {group.name}：{group.summary}" for group in COMMAND_GROUPS.values()
    )
    lines.append("使用 help <功能域> 查看分类详情。")
    return "\n".join(lines)


def render_group(group_name: str) -> str:
    group = COMMAND_GROUPS[group_name]
    lines = [f"【{group.name}】{group.summary}"]
    lines.extend(
        f"• {command.usage}：{command.summary}"
        for command in group.commands.values()
    )
    if group.notes:
        lines.append("")
        lines.extend(group.notes)
    lines.append(f"使用 help {group_name} <子命令> 查看详细用法。")
    return "\n".join(lines)


def render_command(group_name: str, command_name: str) -> str:
    group = COMMAND_GROUPS[group_name]
    command = group.commands[command_name]
    lines = [
        command.summary,
        f"用法：{command.usage}",
        f"示例：{command.example}",
    ]
    if group.notes:
        lines.append("")
        lines.extend(group.notes)
    return "\n".join(lines)


def render_help(query: str) -> str:
    parts = query.strip().lower().split()
    if not parts:
        return render_home()

    group = COMMAND_GROUPS.get(parts[0])
    if group is None:
        return f"未知功能域：{parts[0]}\n\n{render_home()}"
    if len(parts) == 1:
        return render_group(group.name)

    command = group.commands.get(parts[1])
    if command is None:
        return (
            f"未知子命令：{group.name} {parts[1]}\n\n"
            f"{render_group(group.name)}"
        )
    return render_command(group.name, command.name)


def resolve_group(group_name: str, arg_text: str) -> DispatchRequest | str:
    group = COMMAND_GROUPS[group_name]
    parts = arg_text.strip().split(maxsplit=1)
    if not parts:
        return render_group(group_name)

    command = group.commands.get(parts[0].lower())
    if command is None:
        return (
            f"未知子命令：{group_name} {parts[0]}\n\n"
            f"{render_group(group_name)}"
        )

    payload = parts[1].strip() if len(parts) == 2 else ""
    if command.requires_args and not payload:
        return render_command(group_name, command.name)
    return DispatchRequest(command, payload)
