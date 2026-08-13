# data

本目录存放 Puzzle Bot 本地中文检索（`se`）和五笔转换（`ci wb`）所需的语料。

有公开来源的语料需要单独下载。未放置对应文件时，相关命令会提示数据缺失，不影响其它功能。

## 一键复现

需要 Git，以及能访问 GitHub、jsDelivr 和 Project Gutenberg 的网络。在仓库根目录执行：

```bash
python data/prepare.py
```

脚本会下载、裁剪并转换成运行时需要的文件。歌词包约 31MB，准备可能需要几分钟。

只准备一部分时：

```bash
python data/prepare.py --only words,wubi
python data/prepare.py --only poetry,novels,idioms,lyrics
```

可选值：`words`、`poetry`、`novels`、`idioms`、`lyrics`、`wubi`。`novels` 会写入 `chinese-poetry/四大名著/`，若该目录还不存在会先拉取诗词库。

## 准备完成后的目录

```text
data/
  README.md              # 本说明
  prepare.py             # 复现脚本
  hand_classics.json     # 乐府/古诗十九首补遗
  words.txt              # 词表
  lyrics.csv             # 歌词
  idioms.csv             # 成语
  wubi_data.js           # 五笔码表
  chinese-poetry/        # 稀疏克隆的古诗词库 + 四大名著
    全唐诗/poet.tang.*.json
    宋词/ci.song.*.json
    诗经/ 楚辞/ 论语/ ...
    四大名著/*.txt
```

## 运行时文件与命令

| 路径 | 命令 | 由脚本生成 |
|------|------|------------|
| `words.txt` | `se wo`、`se co` | `--only words` |
| `chinese-poetry/全唐诗`、`宋词` | `se po` | `--only poetry` |
| `chinese-poetry/` 其它子集 | `se po`、`se cl` | `--only poetry` |
| `chinese-poetry/四大名著/` | `se cl` | `--only novels` |
| `hand_classics.json` | `se po` | 否 |
| `lyrics.csv` | `se ly` | `--only lyrics` |
| `idioms.csv` | `se sa` | `--only idioms` |
| `wubi_data.js` | `ci wb` | `--only wubi` |

## 来源

- `words.txt`：[liangqi/chinese-frequency-word-list](https://github.com/liangqi/chinese-frequency-word-list) 中的《现代汉语常用词表》电子版。
- `chinese-poetry/`：[chinese-poetry/chinese-poetry](https://github.com/chinese-poetry/chinese-poetry)，稀疏检出诗经、楚辞、论语、四书五经、蒙学、元曲、五代诗词、曹操诗集、纳兰性德、幽梦影，以及唐诗 `poet.tang.*`、宋词 `ci.song.*`。
- `四大名著/`：Project Gutenberg 文本，[三国演义 #23950](https://www.gutenberg.org/ebooks/23950)、[西游记 #23962](https://www.gutenberg.org/ebooks/23962)、[水浒传 #23863](https://www.gutenberg.org/ebooks/23863)、[红楼梦 #24264](https://www.gutenberg.org/ebooks/24264)。
- `idioms.csv`：由 [pwxcoo/chinese-xinhua](https://github.com/pwxcoo/chinese-xinhua) 的 `idiom.json` 抽出 `text,explanation`。
- `lyrics.csv`：由 [gaussic/Chinese-Lyric-Corpus](https://github.com/gaussic/Chinese-Lyric-Corpus) 的 `Chinese_Lyrics.zip` 转换。
- `wubi_data.js`：npm [`wubi-code-data@1.0.2`](https://www.npmjs.com/package/wubi-code-data)。
- `hand_classics.json`：本项目自行整理的乐府与古诗十九首补遗。
