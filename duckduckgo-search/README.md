# DuckDuckGo Search Skill

🔍 **免费的网页搜索技能，无需 API key！**

## 功能特点

- ✅ **完全免费**：使用 DuckDuckGo 开放 API
- 🌐 **无需注册**：不需要任何 API key
- 🔒 **隐私友好**：DuckDuckGo 不追踪用户
- 🇨🇳 **支持中文**：完美支持中文搜索
- ⚡ **即时答案**：快速获取百科摘要

## 安装方法

### 方法1：通过 ClawHub 安装（推荐）

```bash
clawhub install duckduckgo-search
```

### 方法2：手动安装

```bash
# 克隆仓库
git clone https://github.com/xiejava1018/myopenclaw-skills.git

# 复制技能到 OpenClaw
cp -r myopenclaw-skills/duckduckgo-search ~/.openclaw/workspace/skills/

# 安装命令行工具（可选）
ln -s ~/.openclaw/workspace/skills/duckduckgo-search/ddg.sh ~/.local/bin/ddg
```

## 使用方法

### 在 OpenClaw 中使用

直接对 AI 说：
- "搜索 Python 教程"
- "查询最新的 JavaScript 框架"
- "搜索 Ubuntu 系统优化方法"

### 命令行使用

```bash
# 基本搜索
ddg "Python 教程"

# 搜索并保存结果
ddg "机器学习入门" > search_result.txt
```

## 技术细节

### DuckDuckGo Instant Answer API

本技能使用 DuckDuckGo 的 Instant Answer API：

```bash
# API 示例
curl "https://api.duckduckgo.com/?q=Python&format=json&no_html=1"
```

### 支持的参数

- `q`: 搜索查询
- `format`: 输出格式（json）
- `no_html`: 移除 HTML 标签
- `kl`: 语言/地区（如 `kl=cn-zh` 用于中文）

## 代理配置（中国大陆用户必看）

⚠️ **如果你在中国大陆，需要配置代理才能访问 DuckDuckGo API。**

### 方法1：配置 OpenClaw Gateway 代理（推荐）

在 `~/.openclaw/openclaw.json` 中添加：

```json
{
  "env": {
    "vars": {
      "HTTP_PROXY": "http://127.0.0.1:10809",
      "HTTPS_PROXY": "http://127.0.0.1:10809",
      "NO_PROXY": "localhost,127.0.0.1,*.feishu.cn,*.larksuite.com,*.bytedance.com"
    }
  }
}
```

重启 Gateway：
```bash
openclaw gateway restart
```

### 方法2：系统环境变量

在 `~/.bashrc` 或 `~/.zshrc` 中添加：

```bash
export HTTP_PROXY="http://127.0.0.1:10809"
export HTTPS_PROXY="http://127.0.0.1:10809"
```

### 方法3：脚本内置代理（已默认启用）

**2026-02-24 更新**：`ddg.sh` 脚本已内置代理配置，默认使用 `http://127.0.0.1:10809`。

如果你的代理端口不同，可以编辑脚本修改 `PROXY` 变量。

## 故障排除

### 问题1：搜索无结果

**原因**：DuckDuckGo Instant Answer API 对教程类关键词支持有限

**解决方案**：
1. 使用**英文关键词**：`Python tutorial` 而非 `Python 教程`
2. 使用**知名实体**：如 `Python`、`Linux`、`Docker`
3. 查看脚本输出中的**主题数量**，确认 API 是否返回数据

### 问题2：连接超时

**原因**：代理未启动或端口错误

**解决方案**：
```bash
# 检查代理是否运行
curl -x http://127.0.0.1:10809 https://duckduckgo.com

# 检查代理端口
env | grep -i proxy
```

### 问题3：jq 解析错误

**原因**：jq 未安装

**解决方案**：
```bash
sudo apt install jq
```

## 替代方案

如果需要更全面的搜索结果，可以考虑：

- **Searxng**：开源的元搜索引擎
- **ddgr**：DuckDuckGo 命令行工具
- **Brave Search**：需要 API key

## 示例

### 搜索编程教程

```bash
curl -s "https://api.duckduckgo.com/?q=Python+tutorial&format=json&no_html=1" \
  | jq '.AbstractText'
```

### 搜索人物

```bash
curl -s "https://api.duckduckgo.com/?q=Linus+Torvalds&format=json" \
  | jq '.AbstractText'
```

### 获取相关主题

```bash
curl -s "https://api.duckduckgo.com/?q=machine+learning&format=json" \
  | jq '.RelatedTopics[].Text' | head -5
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 作者

**小强 (OpenClaw AI Assistant)**

---

**🔗 相关链接**
- [DuckDuckGo 官网](https://duckduckgo.com)
- [DuckDuckGo API 文档](https://duckduckgo.com/api)
- [OpenClaw 文档](https://docs.openclaw.ai)
- [ClawHub 技能市场](https://clawhub.com)
