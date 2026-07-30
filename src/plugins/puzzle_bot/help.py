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
        "nutrimatic",
        "Nutrimatic 中英文查询",
        {
            "en": CommandSpec(
                "english",
                "Nutrimatic 英文表达式查询",
                "nu en <表达式> [-p 页码]",
                "nu en <A>?<B> -p 2",
                "nu_en",
            ),
            "zh": CommandSpec(
                "zhongwen",
                "Nutrimatic-zh 中文正则查询",
                "nu zh <中文正则表达式>",
                "nu zh ....",
                "nu_zh",
            ),
        },
    ),
    "se": GroupSpec(
        "search",
        "本地中文语料检索",
        {
            "wo": CommandSpec(
                "word",
                "中文词语正则查询",
                "se wo <模式>",
                "se wo A.A",
                "search_word",
            ),
            "po": CommandSpec(
                "poem",
                "中文诗词句子正则查询",
                "se po <模式>",
                "se po ..AAA..",
                "search_poem",
            ),
            "ly": CommandSpec(
                "lyrics",
                "歌词句子正则查询",
                "se ly <模式>",
                "se ly 天..",
                "search_lyrics",
            ),
            "sa": CommandSpec(
                "saying",
                "俗语、谚语和成语正则查询",
                "se sa <模式>",
                "se sa ....",
                "search_saying",
            ),
            "co": CommandSpec(
                "contract",
                "合同字查询，寻找满足四个组词条件的汉字",
                "se co <1AB2CD>",
                "se co 1化.2术.",
                "search_contract",
            ),
            "cl": CommandSpec(
                "classic",
                "古文和经典文本正则查询",
                "se cl <模式>",
                "se cl 学而时习之",
                "search_classic",
            ),
        },
        (
            ". 表示任意一个汉字；同一大写字母 A-Z 表示相同汉字。",
            "nz@b(部件...) 表示包含全部指定部件的单个汉字。",
            "查询结果按可能性分数降序排列。",
        ),
    ),
    "ci": GroupSpec(
        "cipher",
        "古典密码转换和破解",
        {
            abbreviation: CommandSpec(
                full_name, summary, usage, example, handler_key
            )
            for abbreviation, full_name, summary, usage, example, handler_key in (
                (
                    "mo",
                    "morse",
                    "摩斯密码",
                    "ci mo <内容>",
                    "ci mo ... --- ...",
                    "cipher_morse",
                ),
                (
                    "a1",
                    "a1z26",
                    "A1Z26",
                    "ci a1 <内容>",
                    "ci a1 1 2 3",
                    "cipher_a1z26",
                ),
                (
                    "bi",
                    "binary",
                    "5 位二进制",
                    "ci bi <内容>",
                    "ci bi 00001",
                    "cipher_binary",
                ),
                (
                    "te",
                    "ternary",
                    "3 位三进制",
                    "ci te <内容>",
                    "ci te 001",
                    "cipher_ternary",
                ),
                (
                    "can",
                    "cantor",
                    "康托展开",
                    "ci can <内容>",
                    "ci can 1234",
                    "cipher_cantor",
                ),
                (
                    "po",
                    "polybius",
                    "棋盘密码",
                    "ci po <内容>",
                    "ci po 11 12",
                    "cipher_polybius",
                ),
                (
                    "br",
                    "braille",
                    "六点盲文",
                    "ci br <内容>",
                    "ci br 100000",
                    "cipher_braille",
                ),
                (
                    "se",
                    "semaphore",
                    "旗语",
                    "ci se <内容>",
                    "ci se 28",
                    "cipher_semaphore",
                ),
                (
                    "dn",
                    "dna",
                    "氨基酸密码子（仅解码）",
                    "ci dn <内容>",
                    "ci dn AUG",
                    "cipher_dna",
                ),
                (
                    "t9",
                    "t9",
                    "九键手机键盘",
                    "ci t9 <内容>",
                    "ci t9 21 31",
                    "cipher_t9",
                ),
                (
                    "wu",
                    "wubi",
                    "五笔 86 查询",
                    "ci wu <汉字或编码>",
                    "ci wu 工",
                    "cipher_wubi",
                ),
                (
                    "mi",
                    "mixed",
                    "混合密码自动识别并拼接解码",
                    "ci mi <段1> <段2> ...",
                    "ci mi .. 00001 1234",
                    "cipher_mixed",
                ),
                (
                    "cae",
                    "caesar",
                    "凯撒密码（省略移位时穷举）",
                    "ci cae <内容> [移位]",
                    "ci cae abc 3",
                    "cipher_caesar",
                ),
                (
                    "vi",
                    "vigenere",
                    "维吉尼亚密码（明文、密文、密钥任选两项）",
                    "ci vi <参数1> <参数2>",
                    "ci vi attack lemon",
                    "cipher_vigenere",
                ),
            )
        },
        ("部分密码支持 ? 通配符，并会自动判断加密或解密方向。",),
    ),
    "hu": GroupSpec(
        "hunt",
        "比赛日程和队伍状态",
        {
            "ca": CommandSpec(
                "calendar",
                "从 Puzzlendar 获取近期或进行中的比赛",
                "hu ca",
                "hu ca",
                "hunt_calendar",
                requires_args=False,
            ),
            "st": CommandSpec(
                "status",
                "Hunt 期间的队伍状态（默认 bph）",
                "hu st [赛事]",
                "hu st bph",
                "hunt_status",
                requires_args=False,
            ),
        },
    ),
}


def render_home() -> str:
    lines = ["可用命令分类："]
    lines.extend(
        f"• {abbreviation}（{group.name}）：{group.summary}"
        for abbreviation, group in COMMAND_GROUPS.items()
    )
    lines.append("使用 help <功能域> 查看分类详情。")
    return "\n".join(lines)


def render_group(group_name: str) -> str:
    group = COMMAND_GROUPS[group_name]
    lines = [f"【{group_name}（{group.name}）】{group.summary}"]
    lines.extend(
        f"• {command.usage}（{group.name} {command.name}）：{command.summary}"
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
        f"全称：{group.name} {command.name}",
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
        return render_group(parts[0])

    command = group.commands.get(parts[1])
    if command is None:
        return (
            f"未知子命令：{parts[0]} {parts[1]}\n\n"
            f"{render_group(parts[0])}"
        )
    return render_command(parts[0], parts[1])


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
        return render_command(group_name, parts[0].lower())
    return DispatchRequest(command, payload)
