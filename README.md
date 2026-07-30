# Puzzle Bot

一个用于辅助解谜的 [NoneBot2](https://nonebot.dev/) 插件，提供文本检索、赛事信息查询和常见古典密码转换等功能。

## 功能

- 查询 Puzzlendar 近期赛事及 Hunt 期间的队伍状态
- 使用 Nutrimatic 检索英文表达式
- 检索中文词语、诗词、歌词、俗语、谚语和古文
- 支持汉字部件、相同字变量和正则模式查询
- 转换或破解摩斯密码、A1Z26、凯撒、维吉尼亚、盲文、旗语等常见古典密码

## 安装

1. 将 `src/plugins/puzzle_bot` 复制到 NoneBot 项目的插件目录。
2. 安装所需依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. 确保 NoneBot 配置中的 `plugin_dirs` 包含该插件所在目录。

## 配置

中文 Nutrimatic 查询需要单独部署 Nutrimatic-zh 服务。可参考 `.env-template` 在 `.env` 中设置服务地址：

```env
NUTRIMATIC_ZH_URL=http://127.0.0.1:8081
```

不使用该功能时无需额外配置。

## 使用

发送 `hlp`、`help` 或 `帮助` 查看完整命令列表。

```text
nu <表达式>       # Nutrimatic 英文查询
dc <模式>         # 中文词语查询
sc <模式>         # 中文诗词查询
cs <内容> [移位]  # 凯撒密码转换或穷举
```

实际命令前缀取决于你的 NoneBot 配置。
