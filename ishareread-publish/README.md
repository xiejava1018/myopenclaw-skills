# 爱分享读书 — 一键发布工具

从飞书多维表格获取未发布文章，自动发布到 Hugo 网站（GitHub Pages）并同步发布到微信公众号。

## 功能特点

- 从飞书多维表格自动读取未发布文章
- 自动创建 Hugo 文章、构建站点、推送 GitHub
- 自动通过 Coze 工作流发布到微信公众号
- 自动回写飞书表格的发布地址
- 首次使用自动引导配置

## 快速开始

### 1. 安装依赖

无需额外安装，使用 Python 3 标准库（`urllib`, `json`, `subprocess`）。

### 2. 首次配置

首次运行时自动进入交互式配置向导：

```bash
python3 publish.py
```

需要配置：
- **飞书多维表格** — App ID、App Secret、App Token、Table ID
- **Coze 发布** — API Token、Workflow ID
- **Hugo 站点** — 站点目录路径、网站域名

或手动创建配置文件：

```bash
cp .env.example .env
# 编辑 .env 填入实际值
```

### 3. 发布文章

```bash
# 交互选择并发布未发布文章
python3 publish.py

# 发布指定标题的文章（模糊匹配）
python3 publish.py --title "文章标题"
```

## 使用方法

### 命令行参数

| 参数       | 缩写 | 说明                           |
|-----------|------|-------------------------------|
| `--title` | `-t` | 指定文章标题（模糊匹配）          |
| `--list`  | `-l` | 仅列出未发布文章                 |
| `--hugo-only` |   | 仅发布到网站（不发微信公众号）    |
| `--wechat-only` | | 仅发布到微信（网站已发布）       |

### 示例

```bash
# 列出所有未发布文章
python3 publish.py --list

# 仅发布到 Hugo 网站
python3 publish.py --hugo-only

# 仅发布到微信公众号
python3 publish.py --wechat-only --title "文章标题"
```

## 配置说明

| 环境变量             | 必填 | 说明                        |
|---------------------|------|----------------------------|
| `FEISHU_APP_ID`     | 是   | 飞书应用 App ID              |
| `FEISHU_APP_SECRET` | 是   | 飞书应用 App Secret           |
| `FEISHU_APP_TOKEN`  | 是   | 飞书多维表格 App Token         |
| `FEISHU_TABLE_ID`   | 是   | 飞书多维表格 Table ID          |
| `COZE_API_TOKEN`    | 是   | Coze API Token               |
| `COZE_WORKFLOW_ID`  | 是   | Coze 工作流 ID                |
| `HUGO_SITE_DIR`     | 是   | Hugo 站点目录绝对路径           |
| `SITE_BASE_URL`     | 是   | 网站域名                      |

## 发布流程

```
飞书多维表格 → 读取未发布文章
    ↓
创建 Hugo 文章 (content/post/YYYY-MM-DD-hash/index.md)
    ↓
Hugo 构建 (hugo --minify)
    ↓
Git commit + push → 触发 GitHub Pages 部署
    ↓
回写飞书表格「文章发布地址」
    ↓
Coze 工作流 → 发布微信公众号（HTML 内容）
```

## 技术细节

- **飞书 API**: 通过 `tenant_access_token` 认证，读写多维表格记录
- **Hugo slug**: 从文章标题自动生成，构建后从 `public/p/` 目录匹配实际 slug
- **微信公众号**: 使用 HTML 格式内容（非 Markdown），通过 Coze 工作流 API 发布
- **Git 部署**: 推送到 `main` 分支自动触发 GitHub Actions 构建部署
- **同日文章排序**: 自动检测同天已有文章的时间，每篇间隔 4 小时（最多 6 篇/天）

## 注意事项

- 配置文件 `.env` 不会被提交到 Git（已在 `.gitignore` 中排除）
- 微信公众号发布使用「文章内容-html」字段，非 Markdown
- 如需重新配置，删除 `.env` 文件后重新运行即可
