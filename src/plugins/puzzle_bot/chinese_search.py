import csv
import json
import math
import re
from pathlib import Path
from typing import List, Tuple

from zhconv import convert

from .zi_tools import NZ_B_RE, ZiToolsError, cache_get, normalize_components

# ===================== 本地中文语料正则查询 =====================

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
WORDS_FILE = DATA_DIR / "words.txt"
CLASSICS_DIR = DATA_DIR / "chinese-poetry"
HAND_CLASSICS_FILE = DATA_DIR / "hand_classics.json"
LYRICS_FILE = DATA_DIR / "lyrics.csv"
IDIOMS_FILE = DATA_DIR / "idioms.csv"


def _iter_poem_json_files() -> List[Path]:
    files: List[Path] = []
    tang = CLASSICS_DIR / "全唐诗"
    ci = CLASSICS_DIR / "宋词"
    if tang.exists():
        files.extend(sorted(tang.glob("poet.tang.*.json")))
    if ci.exists():
        files.extend(sorted(ci.glob("ci.song.*.json")))
    return files


# ===================== 汉字部件查询 =====================

def _get_chars_with_components(comps: List[str]) -> List[str]:
    """从字统预取缓存取出含指定部件的汉字。缓存未命中视为实现错误。"""
    key = frozenset(comps)
    chars = cache_get(key)
    if chars is None:
        raise ZiToolsError("部件查询缓存未就绪")
    return chars


def _char_class(chars: List[str]) -> str:
    """构造安全的正则字符类"""
    escaped = []
    for c in chars:
        if c in r"\]-^":
            escaped.append("\\" + c)
        else:
            escaped.append(c)
    return "[" + "".join(escaped) + "]"


def _expand_nz(pattern: str) -> str:
    """把模式中的 nz@b(部件...) 展开为正则字符类

    若单个 nz@b(...) 被一对括号包裹（如 .(nz@b(日口)).....），
    会连同外层括号一起替换为字符类，避免括号被转义为字面量。
    """
    def replace(match: re.Match) -> str:
        comp_str = match.group(1) or match.group(2) or ""
        comps = normalize_components(comp_str)
        chars = _get_chars_with_components(comps)
        if not chars:
            # 没有匹配字符时返回不可能匹配的类
            return "[\u0000]"
        return _char_class(chars)

    return NZ_B_RE.sub(replace, pattern)


async def run_search_with_nz(func, payload: str) -> str:
    from .zi_tools import ZiToolsError, extract_component_groups, prefetch_components
    try:
        if extract_component_groups(payload):
            await prefetch_components(payload)
        return func(payload)
    except ZiToolsError as exc:
        return f"字统部件查询失败：{exc}"


def _pattern_to_regex(pattern: str, full_match: bool = True) -> str:
    """把用户输入模式中的 '.' 视为单个汉字通配符，构造正则表达式

    支持：
    - 嵌套部件查询：nz@b(部件...) 会展开为包含所有满足条件汉字的字符类。
    - 相同字变量：大写字母 A-Z 表示任意一个汉字，同一字母在同一模式中必须相同。
    字符类 [...] 按正则原样保留，其余字符按字面量转义。

    参数:
        full_match: 为 True 时返回 ^...$ 完整匹配；为 False 时仅返回模式主体，
                    便于在长文本中用 search 查找子串。
    """
    # 先展开 nz@b(...)
    pattern = _expand_nz(pattern)
    # 再把 '.' 视为单个汉字通配符；大写字母视为“相同汉字”变量
    regex = ""
    in_class = False
    group_map: dict = {}
    group_count = 0
    hanzi_class = r"[\u4e00-\u9fff]"

    for ch in pattern:
        if ch == "[":
            in_class = True
            regex += ch
        elif ch == "]":
            in_class = False
            regex += ch
        elif in_class:
            # 字符类内部保持原样
            regex += ch
        elif ch == ".":
            regex += hanzi_class
        elif "A" <= ch <= "Z":
            if ch not in group_map:
                group_count += 1
                group_map[ch] = group_count
                regex += f"({hanzi_class})"
            else:
                regex += f"\\{group_map[ch]}"
        else:
            regex += re.escape(ch)
    if full_match:
        return f"^{regex}$"
    return regex


def _normalize_scores(values: List[float]) -> List[float]:
    """把分数线性归一化到 [0.0001, 1.0] 区间，便于像 Nutrimatic 一样展示"""
    if not values:
        return []
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return [1.0] * len(values)
    return [0.0001 + (v - min_v) / (max_v - min_v) * 0.9999 for v in values]


def _load_words() -> List[Tuple[str, float]]:
    """加载本地中文词表，返回 (词语, 频率)"""
    if not WORDS_FILE.exists():
        return []
    words = []
    with WORDS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts:
                word = parts[0].strip()
                # 过滤掉非纯汉字的词（保留含汉字的即可）
                if word and any("\u4e00" <= c <= "\u9fff" for c in word):
                    try:
                        freq = float(parts[2]) if len(parts) > 2 else 1.0
                    except (ValueError, IndexError):
                        freq = 1.0
                    words.append((word, freq))
    return words


def _load_poems() -> List[Tuple[str, str, str]]:
    """加载本地诗词库，返回 (诗句, 作者, 标题) 列表（统一转换为简体）"""
    poems = []
    poem_files = _iter_poem_json_files()
    if not poem_files:
        return poems

    for file_path in poem_files:
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                author = convert(item.get("author", "佚名"), "zh-cn")
                title = convert(item.get("title", "无题"), "zh-cn")
                paragraphs = item.get("paragraphs", [])
                for para in paragraphs:
                    para = convert(para.strip(), "zh-cn")
                    if not para:
                        continue
                    # 同时保留整句（含内部标点，去掉句尾终止符），以便支持含逗号的整句搜索
                    full_line = re.sub(r"[。！？]+$", "", para).strip()
                    if full_line:
                        poems.append((full_line, author, title))
                    # 按句切分，支持常规单句搜索
                    for sent in re.split(r"[，。！？、；]", para):
                        sent = sent.strip()
                        if sent:
                            poems.append((sent, author, title))
        except Exception:
            continue
    return poems


def _flatten_paragraphs(node, author: str, title: str, results: list, is_prose: bool = False):
    """递归遍历 chinese-poetry 的 JSON 结构，提取段落。

    根据 is_prose 决定切分方式：
    - 诗词类：保留整句并按句切分；
    - 古文类：按完整段落保留，并额外按句切分。
    """
    if isinstance(node, str):
        text = convert(node.strip(), "zh-cn")
        if not text:
            return
        if is_prose:
            # 古文保留整段，同时按句切分
            full = re.sub(r"[。！？]+$", "", text).strip()
            if full:
                results.append((full, author, title))
            for sent in re.split(r"[，。！？、；]", text):
                sent = sent.strip()
                if sent:
                    results.append((sent, author, title))
        else:
            full = re.sub(r"[。！？]+$", "", text).strip()
            if full:
                results.append((full, author, title))
            for sent in re.split(r"[，。！？、；]", text):
                sent = sent.strip()
                if sent:
                    results.append((sent, author, title))
    elif isinstance(node, list):
        for child in node:
            _flatten_paragraphs(child, author, title, results, is_prose)
    elif isinstance(node, dict):
        # 尝试从当前节点提取作者/标题
        node_author = author
        node_title = title
        if node.get("author"):
            node_author = convert(str(node.get("author")), "zh-cn")
        if node.get("title"):
            node_title = convert(str(node.get("title")), "zh-cn")
        elif node.get("chapter"):
            node_title = convert(str(node.get("chapter")), "zh-cn")
        elif node.get("rhythmic"):
            node_title = convert(str(node.get("rhythmic")), "zh-cn")

        # 如果节点既有段落又有子内容，先处理段落字段
        for key in ("paragraphs", "content", "abstract"):
            if key in node and isinstance(node[key], list):
                _flatten_paragraphs(node[key], node_author, node_title, results, is_prose)

        # 处理其它字段（避免重复处理已处理的 paragraphs/content）
        for key, value in node.items():
            if key in ("paragraphs", "content", "abstract"):
                continue
            if isinstance(value, (list, dict)):
                _flatten_paragraphs(value, node_author, node_title, results, is_prose)


def _load_classics_poems() -> List[Tuple[str, str, str]]:
    """加载 chinese-poetry 扩展诗词库，返回 (诗句, 作者, 标题)"""
    poems: List[Tuple[str, str, str]] = []
    classics = CLASSICS_DIR
    poem_files = [HAND_CLASSICS_FILE]
    if classics.exists():
        poem_files[0:0] = [
            classics / "诗经" / "shijing.json",
            classics / "楚辞" / "chuci.json",
            classics / "元曲" / "yuanqu.json",
            classics / "幽梦影" / "youmengying.json",
            classics / "曹操诗集" / "caocao.json",
            classics / "纳兰性德" / "纳兰性德诗集.json",
            classics / "蒙学" / "qianjiashi.json",
            classics / "蒙学" / "tangshisanbaishou.json",
            classics / "五代诗词" / "nantang" / "poetrys.json",
        ]

    for file_path in poem_files:
        if not file_path.exists():
            continue
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            _flatten_paragraphs(data, "佚名", "无题", poems, is_prose=False)
        except Exception:
            continue

    # 花间集是多文件
    huajianji_dir = classics / "五代诗词" / "huajianji"
    if huajianji_dir.exists():
        for file_path in huajianji_dir.glob("huajianji-*-juan.json"):
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                _flatten_paragraphs(data, "佚名", "花间集", poems, is_prose=False)
            except Exception:
                continue

    return poems


def _load_novels() -> List[Tuple[str, str, str, str]]:
    """加载四大名著等长篇小说文本，返回 (段落, 作者, 标题, 来源)

    文本预处理：
    - 繁体转简体；
    - 去除字间空格（针对已分词的西游记文本）；
    - 跳过 Project Gutenberg 的英文前言/后记；
    - 按回目切分，每回作为若干段落，便于展示搜索结果上下文。
    """
    novels: List[Tuple[str, str, str, str]] = []
    novels_dir = CLASSICS_DIR / "四大名著"
    if not novels_dir.exists():
        return novels

    novel_files = [
        (novels_dir / "三国演义.txt", "罗贯中", "三国演义"),
        (novels_dir / "西游记.txt", "吴承恩", "西游记"),
        (novels_dir / "水浒传.txt", "施耐庵", "水浒传"),
        (novels_dir / "红楼梦.txt", "曹雪芹", "红楼梦"),
    ]

    hui_regex = re.compile(r"第[一二三四五六七八九十百千零〇0-9\s]+回")

    for file_path, author, title in novel_files:
        if not file_path.exists():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
            # 繁体转简体
            text = convert(text, "zh-cn")
            # 去除中文字符之间的空格（西游记 TXT 中每个字被空格分开）
            text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)

            # 跳过 Project Gutenberg 的英文前言/后记
            if "*** START OF THIS PROJECT GUTENBERG" in text:
                start_marker = "*** START OF THIS PROJECT GUTENBERG"
                idx = text.find(start_marker)
                if idx != -1:
                    rest = text[idx + len(start_marker):]
                    # 找到正文开始处（第一个汉字）
                    for i, ch in enumerate(rest):
                        if "\u4e00" <= ch <= "\u9fff":
                            text = rest[i:]
                            break
            if "*** END OF THIS PROJECT GUTENBERG" in text:
                text = text.split("*** END OF THIS PROJECT GUTENBERG")[0]

            # 按回目切分，每个回目下再按段落拆分
            parts = hui_regex.split(text)
            matches = list(hui_regex.finditer(text))
            for i, part in enumerate(parts):
                if i == 0:
                    # 第一回之前的序言/前言，通常不含正文
                    continue
                hui_title = matches[i - 1].group(0) if i - 1 < len(matches) else ""
                # 去掉回目标题行本身，保留正文
                lines = part.strip().split("\n")
                body_lines = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # 跳过无汉字的行
                    if not any("\u4e00" <= c <= "\u9fff" for c in line):
                        continue
                    body_lines.append(line)
                if not body_lines:
                    continue

                # 合并过短的行，避免一行一段；同时限制单段长度
                current = ""
                for line in body_lines:
                    if current and len(current) + len(line) > 500:
                        novels.append((current.strip(), author, title, "四大名著"))
                        current = line
                    else:
                        current = current + line if current else line
                if current:
                    novels.append((current.strip(), author, title, "四大名著"))
        except Exception:
            continue

    return novels


def _load_classics_prose() -> List[Tuple[str, str, str, str]]:
    """加载古文/经典文本，返回 (段落, 作者, 标题, 来源)"""
    prose: List[Tuple[str, str, str, str]] = []
    classics = CLASSICS_DIR
    if not classics.exists():
        return prose

    prose_files = [
        (classics / "四书五经" / "daxue.json", "四书五经"),
        (classics / "四书五经" / "mengzi.json", "四书五经"),
        (classics / "四书五经" / "zhongyong.json", "四书五经"),
        (classics / "论语" / "lunyu.json", "论语"),
        (classics / "蒙学" / "dizigui.json", "蒙学"),
        (classics / "蒙学" / "qianziwen.json", "蒙学"),
        (classics / "蒙学" / "sanzijing-new.json", "蒙学"),
        (classics / "蒙学" / "sanzijing-traditional.json", "蒙学"),
        (classics / "蒙学" / "shenglvqimeng.json", "蒙学"),
        (classics / "蒙学" / "wenzimengqiu.json", "蒙学"),
        (classics / "蒙学" / "youxueqionglin.json", "蒙学"),
        (classics / "蒙学" / "zengguangxianwen.json", "蒙学"),
        (classics / "蒙学" / "zhuzijiaxun.json", "蒙学"),
        (classics / "蒙学" / "baijiaxing.json", "蒙学"),
        (classics / "蒙学" / "guwenguanzhi.json", "古文观止"),
    ]

    for file_path, source in prose_files:
        if not file_path.exists():
            continue
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # 临时收集到一个普通列表，再附加来源信息
            temp: List[Tuple[str, str, str]] = []
            _flatten_paragraphs(data, "佚名", "无题", temp, is_prose=True)
            for text, author, title in temp:
                prose.append((text, author, title, source))
        except Exception:
            continue

    # 追加四大名著
    novels = _load_novels()
    prose.extend(novels)

    return prose


def _load_lyrics() -> List[Tuple[str, str, str]]:
    """加载本地歌词库，返回 (歌词行, 歌手, 歌名) 列表"""
    lyrics = []
    if not LYRICS_FILE.exists():
        return lyrics

    with LYRICS_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, escapechar="\\")
        for row in reader:
            try:
                title = row.get("title", "未知歌曲").strip()
                author = row.get("author", "未知歌手").strip()
                text = row.get("clean_text", "") or row.get("text", "")
                # 只保留包含中文的歌词
                if not any("\u4e00" <= c <= "\u9fff" for c in text):
                    continue
                # 按行切分
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        lyrics.append((line, author, title))
            except Exception:
                continue
    return lyrics


def _load_idioms() -> List[Tuple[str, str]]:
    """加载本地俗语/谚语/成语库，返回 (条目, 解释) 列表"""
    idioms = []
    if not IDIOMS_FILE.exists():
        return idioms

    with IDIOMS_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                text = row.get("text", "").strip()
                explanation = row.get("explanation", "").strip()
                if not text:
                    continue
                text = convert(text, "zh-cn")
                explanation = convert(explanation, "zh-cn")
                idioms.append((text, explanation))
            except Exception:
                continue
    return idioms


# 名作家与名总集（用于诗词知名程度打分）
_FAMOUS_AUTHORS = {
    '李白', '杜甫', '苏轼', '白居易', '王维', '李清照', '辛弃疾', '陆游',
    '杜牧', '李商隐', '刘禹锡', '孟浩然', '王昌龄', '高适', '岑参',
    '柳永', '欧阳修', '秦观', '周邦彦', '姜夔', '岳飞', '文天祥',
    '陶渊明', '曹操', '曹植', '屈原', '宋玉', '李煜', '纳兰性德',
    '元稹', '韩愈', '柳宗元', '韦应物', '刘长卿', '张九龄', '温庭筠',
    # 补充常见/课标诗人
    '王之涣', '王勃', '贺知章', '骆宾王', '李绅', '贾岛', '张继',
    '崔颢', '王翰', '张若虚', '陈子昂', '卢纶', '王建', '张籍',
    '李贺', '韦庄', '范仲淹', '王安石', '黄庭坚', '杨万里', '范成大',
    '朱熹', '马致远', '龚自珍', '袁枚', '赵翼', '郑燮', '黄景仁',
    '孟郊', '常建', '韩翃', '钱起', '戴叔伦', '杜荀鹤', '罗隐',
    # 经典/民歌/无名氏总集作者
    '汉乐府', '北朝民歌', '古诗十九首', '佚名',
}

_FAMOUS_ANTHOLOGIES = {
    '诗经', '楚辞', '古诗十九首', '唐诗三百首', '宋词三百首',
    '乐府', '全唐诗', '全宋词', '千家诗', '古诗源', '玉台新咏',
    '元曲', '花间集', '幽梦影', '曹操诗集', '纳兰性德', '纳兰词',
    '古文观止', '论语', '四书五经', '蒙学',
}

# 常见/中小学课标名篇标题（子串匹配，便于匹配带前缀的标题）
# 只放具体、不易误匹配的名篇标题；通用词牌/诗题请用下面的 _CURRICULUM_POEMS
_CURRICULUM_TITLES = {
    '登鹳雀楼', '登楼',  # 登鹳雀楼亦作登楼
    '芙蓉楼送辛渐', '送元二使安西',
    '九月九日忆山东兄弟', '静夜思', '望庐山瀑布', '早发白帝城',
    '黄鹤楼送孟浩然之广陵', '赠汪伦', '望天门山', '春晓',
    '过故人庄', '望洞庭湖赠张丞相', '宿建德江', '登科后', '游子吟',
    '江雪', '渔歌子', '望洞庭', '乌衣巷',
    '酬乐天扬州初逢席上见赠', '赋得古原草送别', '钱塘湖春行',
    '暮江吟', '忆江南', '琵琶行', '长恨歌', '清明', '山行',
    '泊秦淮', '赤壁', '江南春', '题都城南庄', '枫桥夜泊',
    '滁州西涧', '送灵澈上人', '逢雪宿芙蓉山主人', '别董大',
    '黄鹤楼', '燕歌行', '白雪歌送武判官归京', '逢入京使',
    '使至塞上', '山居秋暝', '相思', '鹿柴', '鸟鸣涧', '竹里馆',
    '终南别业', '汉江临泛', '积雨辋川庄作', '观猎',
    '梦游天姥吟留别', '月下独酌',
    '宣州谢朓楼饯别校书叔云',
    '茅屋为秋风所破歌', '闻官军收河南河北',
    '旅夜书怀', '阁夜', '咏怀古迹', '夜雨寄北', '锦瑟', '登乐游原',
    '过华清宫', '阿房宫赋', '劝学', '师说', '赤壁赋', '岳阳楼记',
    '醉翁亭记', '小石潭记', '桃花源记', '陋室铭', '爱莲说',
    '木兰诗', '孔雀东南飞', '敕勒歌', '陌上桑', '江南', '长歌行',
    '观沧海', '龟虽寿', '归园田居', '饮酒', '滕王阁序',
    '春江花月夜', '代悲白头翁', '送杜少府之任蜀州',
    '闺怨', '采莲曲', '回乡偶书', '咏鹅', '悯农', '风',
    '所见', '小儿垂钓', '寻隐者不遇', '题诗后',
    '剑客', '题李凝幽居', '石头城', '西塞山怀古',
    '再游玄都观', '南园', '己亥杂诗', '苔',
    '竹石', '游园不值', '题临安邸', '示儿', '秋夜将晓出篱门迎凉有感',
    '小池', '晓出净慈寺送林子方', '观书有感', '题西林壁',
    '饮湖上初晴后雨', '惠崇春江晚景', '赠刘景文',
    # 诗经名篇
    '关雎', '蒹葭', '桃夭', '氓', '采薇', '静女', '子衿', '击鼓',
    '汉广', '鹿鸣', '伐檀', '硕鼠', '无衣', '七月', '黍离', '木瓜',
    '摽有梅', '野有蔓草', '风雨', '君子于役', '溱洧', '柏舟',
    # 楚辞名篇
    '离骚', '九歌', '天问', '九章', '渔父', '卜居', '招魂',
    # 元曲名篇（具体篇目）
    '天净沙·秋思', '山坡羊·潼关怀古',
}

# 通用词牌/诗题需要同时匹配作者且标题为主标题才视为课标名篇，避免大量误 Boost
_CURRICULUM_POEMS = {
    # (作者, 标题关键字)
    ('李商隐', '无题'), ('晏殊', '无题'), ('杜甫', '无题'),
    ('王昌龄', '从军行'), ('李白', '从军行'), ('杨炯', '从军行'),
    ('王之涣', '凉州词'), ('王翰', '凉州词'),
    ('王昌龄', '出塞'),
    ('卢纶', '塞下曲'),
    ('刘禹锡', '浪淘沙'), ('刘禹锡', '竹枝词'),
    ('白居易', '池上'), ('白居易', '村居'),
    ('高鼎', '村居'), ('张舜民', '村居'),
    ('杜甫', '绝句'),
    ('李白', '古风'), ('李白', '静夜思'),
    ('李贺', '马诗'),
    ('刘禹锡', '秋词'),
    ('曹操', '短歌行'), ('李白', '短歌行'),
    ('李白', '行路难'), ('李白', '将进酒'), ('李白', '蜀道难'),
    ('杜甫', '登高'), ('杜甫', '春望'), ('杜甫', '蜀相'),
    ('杜甫', '望岳'), ('杜甫', '客至'),
    ('陆游', '关山月'),
    ('苏轼', '卜算子'), ('陆游', '卜算子'),
    ('苏轼', '水调歌头'), ('辛弃疾', '水调歌头'),
    ('苏轼', '念奴娇'), ('辛弃疾', '念奴娇'),
    ('苏轼', '江城子'), ('柳永', '蝶恋花'), ('晏殊', '蝶恋花'),
    ('柳永', '雨霖铃'), ('辛弃疾', '永遇乐'),
    ('李清照', '声声慢'), ('岳飞', '满江红'),
    ('辛弃疾', '破阵子'), ('辛弃疾', '西江月'),
    ('马致远', '天净沙'), ('张养浩', '山坡羊'),
}


def _is_curriculum_title(title: str) -> bool:
    """判断标题是否匹配课标名篇标题，避免短标题被其他标题子串误匹配。

    匹配规则：
    - 标题完全等于关键字；
    - 标题以关键字开头，且后跟空格或标点；
    - 标题以关键字结尾，且前面是空格或标点；
    - 关键字在标题中间，且前后都是空格或标点。
    """
    for keyword in _CURRICULUM_TITLES:
        if title == keyword:
            return True
        if title.startswith(keyword) and len(title) > len(keyword) and title[len(keyword)] in ' ·，。！？、；：':
            return True
        if title.endswith(keyword) and len(title) > len(keyword) and title[-len(keyword)-1] in ' ·，。！？、；：':
            return True
        idx = title.find(keyword)
        while idx != -1:
            if idx > 0 and title[idx-1] in ' ·，。！？、；：':
                end = idx + len(keyword)
                if end < len(title) and title[end] in ' ·，。！？、；：':
                    return True
            idx = title.find(keyword, idx + 1)
    return False


def _is_curriculum_poem(author: str, title: str) -> bool:
    """判断是否为课标名篇（通用标题需同时匹配作者且为主标题）"""
    for a, keyword in _CURRICULUM_POEMS:
        if author != a:
            continue
        # 主标题匹配：完全相等，或以关键字开头/结尾（后跟分隔符）
        if title == keyword:
            return True
        if title.startswith(keyword + ' ') or title.startswith(keyword + '·'):
            return True
        if title.endswith(' ' + keyword) or title.endswith('·' + keyword):
            return True
    return False

# 缓存，避免每次查询都重新加载
_WORDS_CACHE: List[Tuple[str, float]] = []
_POEMS_CACHE: List[Tuple[str, str, str]] = []
_CLASSICS_PROSE_CACHE: List[Tuple[str, str, str, str]] = []
_LYRICS_CACHE: List[Tuple[str, str, str]] = []
_IDIOMS_CACHE: List[Tuple[str, str]] = []
_AUTHOR_FREQ_CACHE: dict = {}


def _get_words() -> List[Tuple[str, float]]:
    global _WORDS_CACHE
    if not _WORDS_CACHE:
        _WORDS_CACHE = _load_words()
    return _WORDS_CACHE


def _get_poems() -> List[Tuple[str, str, str]]:
    global _POEMS_CACHE
    if not _POEMS_CACHE:
        _POEMS_CACHE = _load_poems() + _load_classics_poems()
    return _POEMS_CACHE


def _get_author_freq() -> dict:
    """统计语料中每位作者的作品数量，作为知名程度的一个代理指标"""
    global _AUTHOR_FREQ_CACHE
    if not _AUTHOR_FREQ_CACHE:
        freq = {}
        for _, author, _ in _get_poems():
            freq[author] = freq.get(author, 0) + 1
        _AUTHOR_FREQ_CACHE = freq
    return _AUTHOR_FREQ_CACHE


def _get_classics_prose() -> List[Tuple[str, str, str, str]]:
    """获取古文/经典文本缓存"""
    global _CLASSICS_PROSE_CACHE
    if not _CLASSICS_PROSE_CACHE:
        _CLASSICS_PROSE_CACHE = _load_classics_prose()
    return _CLASSICS_PROSE_CACHE


def _get_lyrics() -> List[Tuple[str, str, str]]:
    global _LYRICS_CACHE
    if not _LYRICS_CACHE:
        _LYRICS_CACHE = _load_lyrics()
    return _LYRICS_CACHE


def _get_idioms() -> List[Tuple[str, str]]:
    global _IDIOMS_CACHE
    if not _IDIOMS_CACHE:
        _IDIOMS_CACHE = _load_idioms()
    return _IDIOMS_CACHE


def search_words(pattern: str, max_results: int = 30) -> str:
    """按模式查找中文词语，'.' 表示一个任意汉字；结果按可能性分数排序"""
    if not pattern:
        return "用法：dc <模式>（. 表示任意一个汉字）"

    words = _get_words()
    if not words:
        return "本地词表未找到，请检查 data/words.txt 是否存在。"

    regex = re.compile(_pattern_to_regex(pattern))
    matches = [(w, math.log(freq + 1)) for w, freq in words if regex.fullmatch(w)]

    if not matches:
        return f"未找到匹配 '{pattern}' 的词语。"

    raw_scores = [s for _, s in matches]
    norm_scores = _normalize_scores(raw_scores)
    results = sorted(zip(norm_scores, [w for w, _ in matches]), key=lambda x: (-x[0], x[1]))

    total = len(results)
    if total > max_results:
        results = results[:max_results]

    lines = [f"{score:.4f} {word}" for score, word in results]
    return f"词语查询：{pattern}（共 {total} 条，显示前 {len(results)} 条）：\n" + "\n".join(lines)


def search_poems(pattern: str, max_results: int = 30) -> str:
    """按模式查找诗词句子，'.' 表示一个任意汉字；结果按可能性分数排序"""
    if not pattern:
        return "用法：sc <模式>（. 表示任意一个汉字）"

    poems = _get_poems()
    if not poems:
        return "本地诗词库未找到，请检查 data/chinese-poetry/ 目录是否存在。"

    regex = re.compile(_pattern_to_regex(pattern))
    # 按 (诗句, 作者) 去重，保留标题信息量最大的那个
    grouped: dict = {}
    for sent, author, title in poems:
        # 整句匹配：保留内部标点（如逗号），仅去掉句尾终止符
        raw_match = regex.fullmatch(sent)
        # 去全部标点后再匹配，支持常规单句搜索
        clean = re.sub(r"[\s，。！？、；：\"\"''（）【】]", "", sent)
        clean_match = regex.fullmatch(clean)
        if raw_match or clean_match:
            # 去重键使用无标点的诗句；展示文本保留原始标点
            key = (clean, author)
            display = sent if raw_match else clean
            # 标题信息量评分：长度 + 包含 anthology 前缀有加成
            title_score = len(title.replace(" ", ""))
            if any(k in title for k in ("歌辞", "乐府", "杂曲", "相和")):
                title_score += 10
            if key not in grouped or title_score > grouped[key][2]:
                grouped[key] = (display, title, title_score)

    if not grouped:
        return f"未找到匹配 '{pattern}' 的诗词句子。"

    # 计算可能性分数：代表诗词知名程度
    # 作者作品数量（知名作者通常收录更多）+ 名作家/名总集/课标名篇加成
    author_freq = _get_author_freq()
    scored = []
    for (clean, author), (display, title, _) in grouped.items():
        is_curriculum_title = _is_curriculum_title(title)
        is_curriculum_poem = _is_curriculum_poem(author, title)
        is_curriculum = is_curriculum_title or is_curriculum_poem
        if is_curriculum:
            # 课标名篇给予固定高分，确保排在最前；作者频率仅作微调
            # 具体名篇标题的加成高于通用词牌/诗题，使“登鹳雀楼”等名篇更靠前
            if is_curriculum_title:
                score = 60.0 + math.log(author_freq.get(author, 1) + 1) * 0.2
            else:
                score = 50.0 + math.log(author_freq.get(author, 1) + 1) * 0.2
        else:
            score = math.log(author_freq.get(author, 1) + 1)
            if author in _FAMOUS_AUTHORS:
                score += 2.0
            if any(k in title for k in _FAMOUS_ANTHOLOGIES):
                score += 3.0
        scored.append((score, display, author, title))

    norm_scores = _normalize_scores([s for s, _, _, _ in scored])
    results = sorted(
        zip(norm_scores, scored),
        key=lambda x: (-x[0], x[1][1], x[1][2])
    )

    total = len(results)
    if total > max_results:
        results = results[:max_results]

    lines = [f"{score:.4f} {sent} —— {author}《{title}》" for score, (_, sent, author, title) in results]
    return f"诗词查询：{pattern}（共 {total} 条，显示前 {len(results)} 条）：\n" + "\n".join(lines)


def search_lyrics(pattern: str, max_results: int = 30) -> str:
    """按模式查找歌词句子，'.' 表示一个任意字符；结果按可能性分数排序"""
    if not pattern:
        return "用法：gc <模式>（. 表示任意一个字符）"

    lyrics = _get_lyrics()
    if not lyrics:
        return "本地歌词库未找到，请检查 data/lyrics.csv 是否存在。"

    regex = re.compile(_pattern_to_regex(pattern))
    seen = set()
    scored = []
    for line, author, title in lyrics:
        # 歌词的一行可能包含多个短句，先按标点/空白切分
        for sub_line in re.split(r"[\s，。！？、；：]+", line):
            sub_line = sub_line.strip()
            if not sub_line:
                continue
            # 去掉剩余引号括号
            clean = re.sub(r"[\"\"''（）【】]", "", sub_line)
            if regex.fullmatch(clean):
                key = (clean, author, title)
                if key in seen:
                    continue
                seen.add(key)
                score = 1.0 / max(len(clean), 1)
                scored.append((score, sub_line, author, title))

    if not scored:
        return f"未找到匹配 '{pattern}' 的歌词句子。"

    norm_scores = _normalize_scores([s for s, _, _, _ in scored])
    results = sorted(
        zip(norm_scores, scored),
        key=lambda x: (-x[0], x[1][1], x[1][2])
    )

    total = len(results)
    if total > max_results:
        results = results[:max_results]

    lines = [f"{score:.4f} {line} —— {author}《{title}》" for score, (_, line, author, title) in results]
    return f"歌词查询：{pattern}（共 {total} 条，显示前 {len(results)} 条）：\n" + "\n".join(lines)


def search_idioms(pattern: str, max_results: int = 30) -> str:
    """按模式查找俗语/谚语/成语，'.' 表示一个任意汉字；结果按可能性分数排序"""
    if not pattern:
        return "用法：sy/yy <模式>（. 表示任意一个汉字）"

    idioms = _get_idioms()
    if not idioms:
        return "本地俗语/谚语库未找到，请检查 data/idioms.csv 是否存在。"

    regex = re.compile(_pattern_to_regex(pattern))
    seen = set()
    scored = []
    for text, explanation in idioms:
        clean = re.sub(r"[\s，。！？、；：\"\"''（）【】]", "", text)
        if regex.fullmatch(text) or regex.fullmatch(clean):
            if text in seen:
                continue
            seen.add(text)
            score = 1.0 / max(len(text), 1)
            if explanation:
                score += 0.02
            scored.append((score, text, explanation))

    if not scored:
        return f"未找到匹配 '{pattern}' 的俗语/谚语。"

    norm_scores = _normalize_scores([s for s, _, _ in scored])
    results = sorted(
        zip(norm_scores, scored),
        key=lambda x: (-x[0], x[1][1])
    )

    total = len(results)
    if total > max_results:
        results = results[:max_results]

    lines = [f"{score:.4f} {text}" + (f"：{explanation}" if explanation else "") for score, (_, text, explanation) in results]
    return f"俗语/谚语查询：{pattern}（共 {total} 条，显示前 {len(results)} 条）：\n" + "\n".join(lines)


def search_classics(pattern: str, max_results: int = 30) -> str:
    """按模式查找古文/经典文本段落，'.' 表示一个任意汉字；结果按可能性分数排序"""
    if not pattern:
        return "用法：gw <模式>（. 表示任意一个汉字）"

    prose = _get_classics_prose()
    if not prose:
        return "本地古文库未找到，请检查 data/chinese-poetry/ 目录是否存在。"

    # 古文允许在长段落中搜索子串，因此不需要 ^$
    regex = re.compile(_pattern_to_regex(pattern, full_match=False))
    seen = set()
    scored = []
    for text, author, title, source in prose:
        # 去掉标点和非汉字，便于连续子串匹配
        clean_full = re.sub(r"[^\u4e00-\u9fff]", "", text)
        match = regex.search(clean_full)
        if match:
            # 以匹配位置为中心截取一段展示文本
            start, end = match.start(), match.end()
            # 优先从原始 text 中截取对应位置附近的文本
            display = text.strip()
            # 按标点切分后，找到包含匹配子串的分句用于展示
            best_sub = display
            for sub_text in re.split(r"[\s，。！？、；：]", text):
                sub_clean = re.sub(r"[^\u4e00-\u9fff]", "", sub_text)
                if regex.fullmatch(sub_clean):
                    best_sub = sub_text.strip()
                    break
                # 若分句包含匹配内容且比当前展示更短，则选用
                if match.group() in sub_clean and len(sub_clean) < len(best_sub):
                    best_sub = sub_text.strip()

            key = (match.group(), author, title, source)
            if key in seen:
                continue
            seen.add(key)
            # 越短的匹配越可能是用户想要的精确句
            score = 1.0 / max(len(match.group()), 1)
            # 名篇来源额外加成
            if source in ("论语", "四书五经", "古文观止"):
                score += 0.5
            scored.append((score, best_sub, author, title, source))

    if not scored:
        return f"未找到匹配 '{pattern}' 的古文句子。"

    norm_scores = _normalize_scores([s for s, _, _, _, _ in scored])
    results = sorted(
        zip(norm_scores, scored),
        key=lambda x: (-x[0], x[1][1], x[1][2])
    )

    total = len(results)
    if total > max_results:
        results = results[:max_results]

    lines = [f"{score:.4f} {text} —— {author}《{title}》（{source}）" for score, (_, text, author, title, source) in results]
    return f"古文查询：{pattern}（共 {total} 条，显示前 {len(results)} 条）：\n" + "\n".join(lines)


def search_ht(pattern: str, max_results: int = 30) -> str:
    """合同查询：输入 1AB2CD，找出 X 使得 AX、BX、XC、XD 都是词语

    格式说明：
      - 1/2 为分段标记；A、B 为第一节约束，C、D 为第二节约束。
      - 第一节求能跟在 A、B 后面的字；第二节求能排在 C、D 前面的字。
      - 四个约束的交集即为结果。A/B/C/D 可用 '.' 作为通配符。
    """
    if not pattern:
        return "用法：ht 1AB2CD（例如：ht 1化.2术.）"

    pattern = pattern.strip()
    if len(pattern) != 6 or pattern[0] != "1" or pattern[3] != "2":
        return "用法：ht 1AB2CD，例如 ht 1化.2术.，其中 A/B/C/D 可以是汉字或通配符 '.'"

    a, b, c, d = pattern[1], pattern[2], pattern[4], pattern[5]
    for ch in (a, b, c, d):
        if ch != "." and not ("\u4e00" <= ch <= "\u9fff"):
            return "A/B/C/D 必须为汉字或通配符 '.'"

    words = _get_words()
    if not words:
        return "本地词表未找到，请检查 data/words.txt 是否存在。"

    # 只保留两字纯中文词，并建立频率查找表
    cn_words = [w for w, _ in words if len(w) == 2 and all("\u4e00" <= c <= "\u9fff" for c in w)]
    word_freq = {w: f for w, f in words if len(w) == 2 and all("\u4e00" <= c <= "\u9fff" for c in w)}

    def seconds_after(first: str) -> set:
        if first == ".":
            return {w[1] for w in cn_words}
        return {w[1] for w in cn_words if w[0] == first}

    def firsts_before(second: str) -> set:
        if second == ".":
            return {w[0] for w in cn_words}
        return {w[0] for w in cn_words if w[1] == second}

    # 第一节：能跟在 A、B 后面的字；第二节：能排在 C、D 前面的字
    set1 = seconds_after(a) & seconds_after(b)
    set2 = firsts_before(c) & firsts_before(d)
    results = sorted(set1 & set2)

    if not results:
        return f"未找到满足 '{pattern}' 合同约束的字。"

    # 为每个结果字找一个示例词对
    word_index = {(w[0], w[1]): w for w in cn_words}
    scored = []
    for ch in results:
        # 优先取非通配约束的示例
        sec1_example = None
        for first in (a, b):
            if first != "." and (first, ch) in word_index:
                sec1_example = word_index[(first, ch)]
                break
        if not sec1_example:
            sec1_example = word_index.get((a if a != "." else "一", ch), "?")

        sec2_example = None
        for second in (c, d):
            if second != "." and (ch, second) in word_index:
                sec2_example = word_index[(ch, second)]
                break
        if not sec2_example:
            sec2_example = word_index.get((ch, c if c != "." else "一"), "?")

        score = min(word_freq.get(sec1_example, 1.0), word_freq.get(sec2_example, 1.0))
        scored.append((score, ch, sec1_example, sec2_example))

    norm_scores = _normalize_scores([s for s, _, _, _ in scored])
    results = sorted(zip(norm_scores, scored), key=lambda x: (-x[0], x[1][1]))

    total = len(results)
    if total > max_results:
        results = results[:max_results]

    lines = [f"{score:.4f} {ch}（{sec1_example} / {sec2_example}）" for score, (_, ch, sec1_example, sec2_example) in results]
    return f"合同查询：{pattern}（共 {total} 条，显示前 {len(lines)} 条）：\n" + "\n".join(lines)
