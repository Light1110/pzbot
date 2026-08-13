#!/usr/bin/env python3
"""下载并整理 Puzzle Bot 所需的 data/ 语料。"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from http.client import IncompleteRead
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

DATA_DIR = Path(__file__).resolve().parent
USER_AGENT = "Mozilla/5.0 (compatible; pzbot-data-prepare/1.0)"

WORDS_URL = (
    "https://raw.githubusercontent.com/liangqi/chinese-frequency-word-list"
    "/master/xiandaihaiyuchangyongcibiao.txt"
)
IDIOM_JSON_URL = "https://raw.githubusercontent.com/pwxcoo/chinese-xinhua/master/data/idiom.json"
LYRICS_ZIP_URL = (
    "https://github.com/gaussic/Chinese-Lyric-Corpus/raw/master/Chinese_Lyrics.zip"
)
WUBI_URLS = [
    "https://cdn.jsdelivr.net/npm/wubi-code-data@1.0.2/五笔码表数据.js",
    "https://raw.githubusercontent.com/program-in-chinese/npm-wubi-code-data/master/五笔码表数据.js",
]
POETRY_REPO = "https://github.com/chinese-poetry/chinese-poetry.git"

POETRY_SPARSE_PATTERNS = [
    "全唐诗/poet.tang.*",
    "宋词/ci.song.*",
    "诗经/",
    "楚辞/",
    "元曲/",
    "幽梦影/",
    "曹操诗集/",
    "纳兰性德/",
    "蒙学/",
    "五代诗词/",
    "四书五经/",
    "论语/",
]

def gutenberg_urls(ebook_id: int) -> List[str]:
    return [
        f"https://www.gutenberg.org/files/{ebook_id}/{ebook_id}-0.txt",
        f"https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.txt",
        f"https://www.gutenberg.org/ebooks/{ebook_id}.txt.utf-8",
    ]


NOVEL_URLS = {
    "三国演义.txt": gutenberg_urls(23950),
    "西游记.txt": gutenberg_urls(23962),
    "水浒传.txt": gutenberg_urls(23863),
    "红楼梦.txt": gutenberg_urls(24264),
}

_ID_SUFFIX = re.compile(r"_\d+$")
_LRC_TAG = re.compile(r"\[\d+:\d+(?:\.\d+)?\]")


def normalize_word_list(raw: str) -> str:
    lines: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            lines.append("\t".join(parts[:3]))
        elif parts:
            lines.append("\t".join(parts))
    return "".join(f"{line}\n" for line in lines)


def idioms_from_json(payload: Sequence[dict]) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for item in payload:
        word = str(item.get("word") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        if word:
            rows.append((word, explanation))
    return rows


def parse_lyric_path(path: str) -> Tuple[str, str]:
    parts = Path(path.replace("\\", "/")).parts
    artist_dir = parts[-2] if len(parts) >= 2 else ""
    song_stem = Path(parts[-1]).stem if parts else ""
    return _ID_SUFFIX.sub("", artist_dir), _ID_SUFFIX.sub("", song_stem)


def clean_lyric_text(text: str) -> str:
    lines: List[str] = []
    for line in text.splitlines():
        line = _LRC_TAG.sub("", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def decode_zip_name(name: str) -> str:
    if any("\u4e00" <= ch <= "\u9fff" for ch in name):
        return name
    for encoding in ("utf-8", "gbk"):
        try:
            return name.encode("cp437").decode(encoding)
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return name


def lyrics_from_zip(data: bytes) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            name = decode_zip_name(info.filename)
            if info.is_dir() or not name.lower().endswith(".txt"):
                continue
            author, title = parse_lyric_path(name)
            raw = zf.read(info).decode("utf-8", errors="replace")
            rows.append(
                {
                    "title": title or "未知歌曲",
                    "author": author or "未知歌手",
                    "text": raw.strip().replace("\0", ""),
                    "clean_text": clean_lyric_text(raw).replace("\0", ""),
                }
            )
    return rows


def iter_poem_files(poetry_root: Path) -> Iterable[Path]:
    tang = poetry_root / "全唐诗"
    ci = poetry_root / "宋词"
    if tang.exists():
        yield from sorted(tang.glob("poet.tang.*.json"))
    if ci.exists():
        yield from sorted(ci.glob("ci.song.*.json"))


def quote_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, quote(parts.path, safe="/@"), parts.query, parts.fragment)
    )


def log(message: str) -> None:
    print(message, flush=True)


def download(url: str, retries: int = 5, delay: float = 1.5) -> bytes:
    last_error: Exception | None = None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Connection": "close",
    }
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(quote_url(url), headers=headers)
            with urllib.request.urlopen(request, timeout=180) as response:
                chunks: List[bytes] = []
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks)
        except (IncompleteRead, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                wait = delay * attempt
                log(f"download retry {attempt}/{retries} ({url}): {exc}; wait {wait:.1f}s")
                if wait:
                    time.sleep(wait)
    raise last_error or RuntimeError(f"download failed: {url}")


def download_first(urls: Sequence[str]) -> bytes:
    last_error: Exception | None = None
    for url in urls:
        try:
            return download(url)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log(f"download failed ({url}): {exc}")
    raise last_error or RuntimeError("no download urls")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    log(f"wrote {path.relative_to(DATA_DIR)} ({path.stat().st_size} bytes)")


def prepare_words(dest: Path) -> None:
    log("fetching words.txt")
    raw = download(WORDS_URL).decode("utf-8", errors="replace")
    write_text(dest, normalize_word_list(raw))


def prepare_idioms(dest: Path) -> None:
    log("fetching idiom.json")
    payload = json.loads(download(IDIOM_JSON_URL).decode("utf-8"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["text", "explanation"])
        writer.writerows(idioms_from_json(payload))
    log(f"wrote {dest.relative_to(DATA_DIR)} ({dest.stat().st_size} bytes)")


def prepare_lyrics(dest: Path) -> None:
    log("fetching Chinese_Lyrics.zip (约 31MB)")
    rows = lyrics_from_zip(download(LYRICS_ZIP_URL))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["title", "author", "text", "clean_text"],
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
            escapechar="\\",
        )
        writer.writeheader()
        writer.writerows(rows)
    log(f"wrote {dest.relative_to(DATA_DIR)} ({len(rows)} songs, {dest.stat().st_size} bytes)")


def prepare_wubi(dest: Path) -> None:
    log("fetching wubi_data.js")
    write_text(dest, download_first(WUBI_URLS).decode("utf-8"))


def prepare_poetry(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    git_dir = dest / ".git"
    if git_dir.exists():
        log(f"updating {dest.name}")
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=True)
        return

    log(f"cloning chinese-poetry into {dest.name} (sparse)")
    if dest.exists():
        # 残留空目录时允许继续 clone
        try:
            dest.rmdir()
        except OSError:
            pass
    subprocess.run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--sparse",
            "--depth",
            "1",
            POETRY_REPO,
            str(dest),
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(dest), "sparse-checkout", "init", "--no-cone"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone", *POETRY_SPARSE_PATTERNS],
        check=True,
    )


def prepare_novels(poetry_root: Path) -> None:
    novels_dir = poetry_root / "四大名著"
    novels_dir.mkdir(parents=True, exist_ok=True)
    errors: List[str] = []
    for filename, urls in NOVEL_URLS.items():
        dest = novels_dir / filename
        if dest.exists() and dest.stat().st_size > 50_000:
            log(f"skip existing {filename} ({dest.stat().st_size} bytes)")
            continue
        log(f"fetching {filename}")
        try:
            text = download_first(urls).decode("utf-8", errors="replace")
            write_text(dest, text)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{filename}: {exc}")
            log(f"failed {filename}: {exc}")
    if errors:
        raise RuntimeError("novels failed: " + "; ".join(errors))


def parse_only(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="下载并整理 data/ 语料")
    parser.add_argument(
        "--only",
        default="",
        help="只准备指定部分，逗号分隔：words,poetry,novels,idioms,lyrics,wubi",
    )
    args = parser.parse_args(argv)

    selected = set(parse_only(args.only)) if args.only else {
        "words",
        "poetry",
        "novels",
        "idioms",
        "lyrics",
        "wubi",
    }
    poetry_dir = DATA_DIR / "chinese-poetry"

    try:
        if "words" in selected:
            prepare_words(DATA_DIR / "words.txt")
        if "poetry" in selected:
            prepare_poetry(poetry_dir)
        if "novels" in selected:
            if "poetry" not in selected and not poetry_dir.exists():
                prepare_poetry(poetry_dir)
            prepare_novels(poetry_dir)
        if "idioms" in selected:
            prepare_idioms(DATA_DIR / "idioms.csv")
        if "lyrics" in selected:
            prepare_lyrics(DATA_DIR / "lyrics.csv")
        if "wubi" in selected:
            prepare_wubi(DATA_DIR / "wubi_data.js")
    except subprocess.CalledProcessError as exc:
        log(f"命令失败: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        log(f"失败: {exc}")
        return 1

    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
