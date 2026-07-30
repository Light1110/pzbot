import re
import string
import itertools
from math import factorial
from pathlib import Path
from typing import List, Tuple, Optional, Callable

# ===================== 公共工具 =====================

def normalize_letters(text: str) -> str:
    """保留大小写字母与数字，空格也保留（部分密码用）"""
    return text.strip()


def has_wildcard(text: str) -> bool:
    return "?" in text


def expand_wildcard(text: str, alphabet: str = string.ascii_uppercase) -> List[str]:
    """将 ? 展开为字母表所有可能。alphabet 可以是字符串或字符串列表。

    每个 ? 独立替换为 alphabet 中的一个元素；连续的 ? 会分别展开。
    """
    groups = re.split(r"(\?+)", text)
    expanded_groups = []
    for g in groups:
        if g.startswith("?"):
            # 每个 ? 都是独立位置
            for _ in range(len(g)):
                expanded_groups.append(list(alphabet))
        else:
            expanded_groups.append([g])
    return ["".join(p) for p in itertools.product(*expanded_groups)]


def fuzzy_decode_symbols(text: str, alphabet: str, decode_symbol_fn: Callable[[str], str], symbol_size: Optional[int] = None, max_per_symbol: int = 128) -> str:
    """对含 ? 的密文按符号位置展开，输出可直接用于 Nutrimatic 的括号形式。

    每个符号独立展开并解码；若一个符号有多个可能解码结果，则用 [abc] 表示；
    只有一个结果时直接输出该字母。例如 ms ?. → [ia]，ms .. .? → i[ia]。

    参数:
        symbol_size: None 表示变长符号（按空白分隔，如摩斯、a1z26）；
                     int 表示定长符号长度（如 binary5=5, braille=6, cb=2）。
    """
    if symbol_size:
        raw = text.replace(' ', '')
        symbols = [raw[i:i+symbol_size] for i in range(0, len(raw), symbol_size)]
    else:
        symbols = text.split()

    parts = []
    for sym in symbols:
        if not sym:
            continue
        if '?' in sym:
            expanded = expand_wildcard(sym, alphabet)[:max_per_symbol]
            chars = sorted({decode_symbol_fn(s) for s in expanded})
        else:
            chars = [decode_symbol_fn(sym)]

        # 去掉无法解码的占位符 '?'
        real_chars = [c for c in chars if c != '?']
        if real_chars:
            chars = real_chars

        if len(chars) == 1:
            parts.append(chars[0].lower())
        else:
            parts.append('[' + ''.join(chars).lower() + ']')

    return ''.join(parts)


# ===================== 摩斯密码 =====================

MORSE_CODE_DICT = {
    'A': ".-", 'B': "-...", 'C': "-.-.", 'D': "-..", 'E': ".",
    'F': "..-.", 'G': "--.", 'H': "....", 'I': "..", 'J': ".---",
    'K': "-.-", 'L': ".-..", 'M': "--", 'N': "-.", 'O': "---",
    'P': ".--.", 'Q': "--.-", 'R': ".-.", 'S': "...", 'T': "-",
    'U': "..-", 'V': "...-", 'W': ".--", 'X': "-..-", 'Y': "-.--",
    'Z': "--..",
    '0': "-----", '1': ".----", '2': "..---", '3': "...--", '4': "....-",
    '5': ".....", '6': "-....", '7': "--...", '8': "---..", '9': "----.",
}
REVERSE_MORSE = {v: k for k, v in MORSE_CODE_DICT.items()}


def _morse_decode(text: str) -> str:
    parts = text.split()
    return ''.join(REVERSE_MORSE.get(p, '?') for p in parts)


def morse(text: str) -> str:
    text = text.strip().upper()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, ".-", _morse_decode)
    # 判断是编码还是解码：如果全是 .-/空格 则是解码
    if all(c in '.- /' for c in text):
        return _morse_decode(text)
    else:
        return ' '.join(MORSE_CODE_DICT.get(c, c) for c in text if c in MORSE_CODE_DICT or c == ' ')


# ===================== A1Z26 =====================

def _a1z26_decode(text: str) -> str:
    parts = re.split(r"[\s,\-]+", text)
    result = []
    for p in parts:
        if not p:
            continue
        n = int(p)
        if 1 <= n <= 26:
            result.append(chr(ord('A') + n - 1))
        else:
            result.append(str(n))
    return ''.join(result)


def a1z26(text: str) -> str:
    text = text.strip()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, [str(i) for i in range(1, 27)], _a1z26_decode)
    # 判断：若全是数字与分隔符，则解码
    if re.fullmatch(r"[\d\s,\-]+", text):
        return _a1z26_decode(text)
    else:
        return ' '.join(str(ord(c.upper()) - ord('A') + 1) for c in text if c.isalpha())


# ===================== 5位二进制 =====================

def _binary5_decode(text: str) -> str:
    bits = re.findall(r"[01]{5}", text)
    return ''.join(chr(int(b, 2) + ord('A') - 1) if 1 <= int(b, 2) <= 26 else '?' for b in bits)


def binary5(text: str) -> str:
    text = text.strip()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, "01", _binary5_decode, symbol_size=5)
    if re.fullmatch(r"[01\s]+", text.replace(" ", "")):
        return _binary5_decode(text)
    else:
        return ' '.join(format(ord(c.upper()) - ord('A') + 1, '05b') for c in text if c.isalpha())


# ===================== 3位三进制 =====================

def _ternary3_decode(text: str) -> str:
    parts = re.findall(r"[012]{3}", text)
    return ''.join(chr(int(p, 3) + ord('A') - 1) if 1 <= int(p, 3) <= 26 else '?' for p in parts)


def _int_to_ternary(n: int, width: int = 3) -> str:
    """把整数转为指定宽度的三进制字符串"""
    if n == 0:
        return "0" * width
    digits = []
    while n > 0:
        digits.append(str(n % 3))
        n //= 3
    return ("0" * width + "".join(reversed(digits)))[-width:]


def ternary3(text: str) -> str:
    text = text.strip()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, "012", _ternary3_decode, symbol_size=3)
    if re.fullmatch(r"[012\s]+", text.replace(" ", "")):
        return _ternary3_decode(text)
    else:
        return ' '.join(_int_to_ternary(ord(c.upper()) - ord('A') + 1) for c in text if c.isalpha())


# ===================== 康托展开 =====================

def cantor_rank(perm: Tuple[int, ...]) -> int:
    """计算排列的康托展开排名（从0开始）"""
    n = len(perm)
    rank = 0
    for i in range(n):
        count = sum(1 for j in range(i+1, n) if perm[j] < perm[i])
        rank += count * factorial(n - 1 - i)
    return rank


def cantor_unrank(rank: int, n: int) -> Tuple[int, ...]:
    """根据康托展开排名还原排列"""
    available = list(range(1, n+1))
    perm = []
    for i in range(n, 0, -1):
        f = factorial(i-1)
        idx = rank // f
        rank %= f
        perm.append(available.pop(idx))
    return tuple(perm)


def cantor(text: str) -> str:
    text = text.strip()
    # 只接受 4 位 1-4 的不重复数字
    if not re.fullmatch(r"[1-4]{4}", text) or len(set(text)) != 4:
        return "输入格式错误，请输入 4 位 1-4 的不重复数字"

    perm = tuple(int(c) for c in text)
    rank = cantor_rank(perm)        # 0-based，1234=0, 1243=1, ..., 4321=23
    return chr(ord('a') + rank)     # 0->a, 1->b, ..., 23->x


# ===================== 棋盘密码（Polybius Square） =====================

def _polybius_decode(text: str) -> str:
    pairs = re.findall(r"\d{2}", text)
    result = []
    for p in pairs:
        r, c = int(p[0]), int(p[1])
        if 1 <= r <= 5 and 1 <= c <= 5:
            idx = (r - 1) * 5 + (c - 1)
            if idx < 26:
                result.append(chr(ord('A') + idx))
        else:
            result.append('?')
    return ''.join(result)


def polybius(text: str) -> str:
    text = text.strip().upper()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, "12345", _polybius_decode, symbol_size=2)
    # 11~55 数字解码
    if re.fullmatch(r"[\d\s]+", text):
        return _polybius_decode(text)
    else:
        result = []
        for ch in text:
            if ch.isalpha():
                idx = ord(ch) - ord('A')
                if idx >= 26:
                    continue
                r, c = divmod(idx, 5)
                result.append(f"{r+1}{c+1}")
        return ' '.join(result)


# ===================== 盲文 =====================

BRAILLE_DICT = {
    '100000': 'A', '101000': 'B', '110000': 'C', '110100': 'D', '100100': 'E',
    '111000': 'F', '111100': 'G', '101100': 'H', '011000': 'I', '011100': 'J',
    '100010': 'K', '101010': 'L', '110010': 'M', '110110': 'N', '100110': 'O',
    '111010': 'P', '111110': 'Q', '101110': 'R', '011010': 'S', '011110': 'T',
    '100011': 'U', '101011': 'V', '011101': 'W', '110011': 'X', '110111': 'Y',
    '100111': 'Z',
}
REVERSE_BRAILLE = {v: k for k, v in BRAILLE_DICT.items()}


def _braille_decode(text: str) -> str:
    codes = re.findall(r"[01]{6}", text)
    return ''.join(BRAILLE_DICT.get(c, '?') for c in codes)


def braille(text: str) -> str:
    text = text.strip().upper()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, "01", _braille_decode, symbol_size=6)
    if re.fullmatch(r"[01\s]+", text.replace(" ", "")):
        return _braille_decode(text)
    else:
        return ' '.join(REVERSE_BRAILLE.get(c, c) for c in text if c.isalpha())


# ===================== 旗语（小键盘数字） =====================

SEMAPHORE_DICT = {
    '12': 'A', '13': 'B', '14': 'C', '15': 'D', '16': 'E', '17': 'F', '18': 'G',
    '23': 'H', '24': 'I', '25': 'J', '26': 'K', '27': 'L', '28': 'M',
    '34': 'N', '35': 'O', '36': 'P', '37': 'Q', '38': 'R',
    '45': 'S', '46': 'T', '47': 'U', '48': 'V',
    '56': 'W', '57': 'X', '58': 'Y',
    '67': 'Z',
    '68': '空格',  # 部分约定
}
REVERSE_SEMAPHORE = {v: k for k, v in SEMAPHORE_DICT.items()}


def _semaphore_decode(text: str) -> str:
    pairs = re.findall(r"\d{2}", text)
    return ''.join(SEMAPHORE_DICT.get(p, '?') for p in pairs)


def semaphore(text: str) -> str:
    text = text.strip().upper()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, "12345678", _semaphore_decode, symbol_size=2)
    if re.fullmatch(r"[\d\s]+", text):
        return _semaphore_decode(text)
    else:
        return ' '.join(REVERSE_SEMAPHORE.get(c, c) for c in text if c.isalpha())


# ===================== 氨基酸密码子（仅解码） =====================

CODON_TABLE = {
    'UUU': 'F', 'UUC': 'F', 'UUA': 'L', 'UUG': 'L',
    'UCU': 'S', 'UCC': 'S', 'UCA': 'S', 'UCG': 'S',
    'UAU': 'Y', 'UAC': 'Y', 'UAA': '*', 'UAG': '*',
    'UGU': 'C', 'UGC': 'C', 'UGA': '*', 'UGG': 'W',
    'CUU': 'L', 'CUC': 'L', 'CUA': 'L', 'CUG': 'L',
    'CCU': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
    'CAU': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
    'CGU': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
    'AUU': 'I', 'AUC': 'I', 'AUA': 'I', 'AUG': 'M',
    'ACU': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
    'AAU': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
    'AGU': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
    'GUU': 'V', 'GUC': 'V', 'GUA': 'V', 'GUG': 'V',
    'GCU': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
    'GAU': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
    'GGU': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
}


def dna_codon(text: str) -> str:
    text = text.strip().upper().replace('T', 'U')
    codons = [text[i:i+3] for i in range(0, len(text), 3)]
    return ''.join(CODON_TABLE.get(c, '?') for c in codons if len(c) == 3)


# ===================== 九键（手机键盘） =====================

NINE_KEY_DICT = {
    'A': '21', 'B': '22', 'C': '23',
    'D': '31', 'E': '32', 'F': '33',
    'G': '41', 'H': '42', 'I': '43',
    'J': '51', 'K': '52', 'L': '53',
    'M': '61', 'N': '62', 'O': '63',
    'P': '71', 'Q': '72', 'R': '73', 'S': '74',
    'T': '81', 'U': '82', 'V': '83',
    'W': '91', 'X': '92', 'Y': '93', 'Z': '94',
}
REVERSE_NINE_KEY = {v: k for k, v in NINE_KEY_DICT.items()}


def _nine_key_decode(text: str) -> str:
    pairs = re.findall(r"\d{2}", text)
    return ''.join(REVERSE_NINE_KEY.get(p, '?') for p in pairs)


def nine_key(text: str) -> str:
    """九键手机键盘：21=a, 31=d, ... 支持 ? 模糊匹配"""
    text = text.strip().upper()
    if has_wildcard(text):
        return fuzzy_decode_symbols(text, "123456789", _nine_key_decode, symbol_size=2)
    if re.fullmatch(r"[\d\s]+", text):
        return _nine_key_decode(text)
    else:
        return ' '.join(NINE_KEY_DICT.get(c, c) for c in text if c.isalpha())


# ===================== 五笔（86 版） =====================

_WUBI_CACHE: dict = {}
_WUBI_REVERSE_CACHE: dict = {}


def _load_wubi() -> dict:
    """加载 data/wubi_data.js 中的 86 版五笔码表，返回 {汉字: [编码, ...]}"""
    global _WUBI_CACHE
    if _WUBI_CACHE:
        return _WUBI_CACHE

    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    wubi_file = base_dir / "data" / "wubi_data.js"
    if not wubi_file.exists():
        return {}

    content = wubi_file.read_text(encoding="utf-8")
    # 提取 五笔86=Object.freeze({...})
    match = re.search(r"五笔86\s*=\s*Object\.freeze\((\{.*?\})\)", content, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    # 用正则提取 "汉字":"编码" 对
    table = {}
    for char, code in re.findall(r'"([^"]{1,2})":"([a-yA-Y]+)"', raw):
        table.setdefault(char, []).append(code.lower())
    _WUBI_CACHE = table
    return table


def _get_wubi_reverse() -> dict:
    """返回 {编码: [汉字, ...]} 的反向索引"""
    global _WUBI_REVERSE_CACHE
    if _WUBI_REVERSE_CACHE:
        return _WUBI_REVERSE_CACHE

    table = _load_wubi()
    reverse: dict = {}
    for char, codes in table.items():
        for code in codes:
            reverse.setdefault(code, []).append(char)
    _WUBI_REVERSE_CACHE = reverse
    return reverse


def wubi(text: str) -> str:
    """五笔 86：
    - 输入汉字 -> 返回五笔编码
    - 输入编码（a-y）-> 返回对应汉字列表
    """
    text = text.strip()
    if not text:
        return "用法：wb <汉字> 或 wb <编码（a-y）>"

    # 如果包含汉字，按汉字查编码
    if any("\u4e00" <= c <= "\u9fff" for c in text):
        table = _load_wubi()
        if not table:
            return "五笔码表未加载，请检查 data/wubi_data.js 是否存在。"
        results = []
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                codes = table.get(ch, [])
                results.append(f"{ch}: {' '.join(codes) if codes else '（无）'}")
        return "\n".join(results) if results else "未找到对应汉字的五笔编码。"

    # 否则按编码查汉字
    code = re.sub(r"[^a-yA-Y]", "", text).lower()
    if not code:
        return "用法：wb <汉字> 或 wb <编码（a-y）>"

    reverse = _get_wubi_reverse()
    if not reverse:
        return "五笔码表未加载，请检查 data/wubi_data.js 是否存在。"

    chars = reverse.get(code, [])
    if not chars:
        return f"未找到五笔编码 '{code}' 对应的汉字。"
    # 最多显示 30 个
    display = chars[:30]
    tail = f"（共 {len(chars)} 个）" if len(chars) > 30 else ""
    return f"五笔 {code}：{''.join(display)}{tail}"


# ===================== 凯撒 =====================

def caesar_shift(text: str, shift: int) -> str:
    result = []
    for ch in text:
        if ch.isalpha():
            base = ord('A') if ch.isupper() else ord('a')
            result.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            result.append(ch)
    return ''.join(result)


def caesar(text: str, shift: Optional[int] = None) -> str:
    text = text.strip()
    if shift is not None:
        return caesar_shift(text, shift % 26)
    else:
        lines = []
        for s in range(26):
            lines.append(f"+{s}: {caesar_shift(text, s)}")
        return '\n'.join(lines)


# ===================== 维吉尼亚 =====================

def vigenere_encrypt(plain: str, key: str) -> str:
    plain = ''.join(c for c in plain.upper() if c.isalpha())
    key = ''.join(c for c in key.upper() if c.isalpha())
    result = []
    for i, ch in enumerate(plain):
        k = key[i % len(key)]
        result.append(chr((ord(ch) - ord('A') + ord(k) - ord('A')) % 26 + ord('A')))
    return ''.join(result)


def vigenere_decrypt(cipher: str, key: str) -> str:
    cipher = ''.join(c for c in cipher.upper() if c.isalpha())
    key = ''.join(c for c in key.upper() if c.isalpha())
    result = []
    for i, ch in enumerate(cipher):
        k = key[i % len(key)]
        result.append(chr((ord(ch) - ord(k)) % 26 + ord('A')))
    return ''.join(result)


def vigenere(args: List[str]) -> str:
    """参数为两个，自动判定：长度区分明文/密文/密钥，或尝试穷举"""
    if len(args) != 2:
        return "用法：vg <参数1> <参数2>（明文/密文/密钥选2项）"
    a, b = args[0].upper(), args[1].upper()
    # 简单启发：如果一个是纯字母短串且看起来不像单词，可能是密钥
    def looks_like_key(s: str) -> bool:
        return len(s) <= 5 and s.isalpha()

    # 情况1: 密钥已知
    if looks_like_key(a):
        # b 是明文或密文，自动判定：若b像有意义的英文则解密，否则加密
        # 简单判定：若b是纯无空格大写则优先解密
        return f"以 {a} 为密钥加密：{vigenere_encrypt(b, a)}\n以 {a} 为密钥解密：{vigenere_decrypt(b, a)}"
    if looks_like_key(b):
        return f"以 {b} 为密钥加密：{vigenere_encrypt(a, b)}\n以 {b} 为密钥解密：{vigenere_decrypt(a, b)}"

    # 情况2: 两个都是长文本，穷举短者作为密钥
    candidates = []
    key_candidates = []
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    # 简单穷举1-5长度密钥
    for length in range(1, min(6, len(short)+1)):
        # 这里只展示加密/解密结果，key取short的前length位
        key = short[:length]
        enc = vigenere_encrypt(long, key)
        dec = vigenere_decrypt(long, key)
        candidates.append(f"key={key}: enc={enc} | dec={dec}")
    return "可能结果（取短串前缀作为密钥）：\n" + '\n'.join(candidates[:10])


# ===================== 混合密码自动识别 =====================

def _detect_cipher_type(segment: str) -> str:
    """根据段落的字符特征判断最可能的密码类型"""
    seg = segment.strip()
    if not seg:
        return 'az'

    # 摩斯：含 . 或 -
    if any(c in '.-' for c in seg):
        return 'ms'

    # 只保留数字
    digits = re.sub(r"[^0-9]", "", seg)
    if not digits:
        return 'az'

    # 二进制：仅含 0/1（在混合识别中优先于盲文/三进制，避免歧义）
    if re.fullmatch(r"[01]+", digits):
        return 'bi'

    # 三进制：仅含 0/1/2
    if re.fullmatch(r"[012]+", digits):
        return 'tri'

    # 康托展开：4 位 1-4 不重复数字
    if re.fullmatch(r"[1-4]{4}", digits) and len(set(digits)) == 4:
        return 'ct'

    # 棋盘密码：仅含 1-5，长度偶数
    if re.fullmatch(r"[1-5]+", digits) and len(digits) % 2 == 0:
        return 'cb'

    # 旗语：仅含 1-8，长度偶数
    if re.fullmatch(r"[1-8]+", digits) and len(digits) % 2 == 0:
        return 'smph'

    # 默认 A1Z26
    return 'az'


def mixed_cipher(text: str) -> str:
    """自动识别多段混合密码并拼接解码结果。

    用法：hh <段1> <段2> ...
    每段按字符特征自动判断密码类型（ms/az/bi/tri/cb/br/smph）并解码，
    最后把各段结果拼接。例如 hh .. 00001 1234 -> i + a + ...
    """
    segments = text.strip().split()
    if not segments:
        return "用法：hh <段1> <段2> ...（自动识别 ms/az/bi/tri/cb/br/smph）"

    results = []
    for seg in segments:
        cipher = _detect_cipher_type(seg)
        fn = CIPHER_FUNCS.get(cipher)
        if not fn:
            results.append(f"[{seg}:?]")
            continue
        decoded = fn(seg)
        results.append(str(decoded).lower())
    return ''.join(results)


# ===================== 统一入口 =====================

CIPHER_FUNCS = {
    'ms': morse,
    'az': a1z26,
    'bi': binary5,
    'tri': ternary3,
    'ct': cantor,
    'cb': polybius,
    'br': braille,
    'smph': semaphore,
    'dna': dna_codon,
    '9j': nine_key,
    'wb': wubi,
    'cs': caesar,
    'vg': vigenere,
    'hh': mixed_cipher,
}
