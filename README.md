# Puzzle Bot

一个用于辅助解谜的 [NoneBot2](https://nonebot.dev/) 插件，提供赛事信息查询、文本检索和常见古典密码转换等功能。

## 功能

- 查询 Puzzlendar 近期赛事及 Hunt 期间的队伍状态
- 使用 Nutrimatic 检索英文表达式
- 检索中文词语、诗词、歌词、俗语、谚语和古文
- 转换或破解摩斯密码、A1Z26、凯撒、维吉尼亚、盲文、旗语等常见古典密码

## 安装

1. 将 `src/plugins/puzzle_bot` 复制到 NoneBot 项目的插件目录。
2. 安装所需依赖：
  ```bash
   pip install -r requirements.txt
  ```
3. 确保 NoneBot 配置中的 `plugin_dirs` 包含该插件所在目录。
4. 如需中文检索或五笔转换，在仓库根目录执行 `python data/prepare.py`，将语料放到 `data/`。细节见 [`data/README.md`](data/README.md)。

## 配置

中文 Nutrimatic 查询需要可访问的 Nutrimatic-zh 服务，并从 `.env` 读取服务根地址。可参考 `.env-template` 配置远程服务：

```env
NUTRIMATIC_ZH_URL=https://nutrimatic-zh.example.com
```

本地部署时，服务根地址可配置为 `http://127.0.0.1:8081`。

不使用该功能时无需额外配置。

## 数据

`se`（本地中文检索）和 `ci wb`（五笔）依赖 `data/` 下的语料。在仓库根目录执行 `python data/prepare.py` 即可下载并整理；文件列表、来源和分步说明见 [`data/README.md`](data/README.md)。未放置对应文件时，相关命令会提示数据缺失。

## 使用

发送 `help` 查看精简的功能分类；发送 `help <功能域缩写>` 查看该分类的全部子命令。

```text
nu en <表达式> [-p 页码]  # nutrimatic english
nu zh <中文正则表达式>    # nutrimatic zhongwen
se po <模式>              # search poem
ci cae <内容> [移位]      # cipher caesar
hu ca                     # hunt calendar
```

例如，发送 `help se` 查看全部中文检索命令，发送 `help ci mo` 查看摩斯密码的详细用法。

实际命令前缀取决于你的 NoneBot 配置。