# ishareread-article-writing

爱分享读书公众号文章写作全流程 AI Skill。适用于 Claude Code、Coze 等支持 MCP/Skill 的 AI 智能体。

## 功能概览

从飞书选题库获取选题 → 分析文案库前几期文章 → 搜索资料撰写新文章 → 上传飞书云盘 → 写入文案库 → 更新选题状态。

## 目录结构

```
ishareread-article-writing/
├── SKILL.md                              # Skill 主文件（工作流定义）
├── scripts/
│   ├── article_workflow.py               # Python CLI 工具（所有 API 调用封装）
│   └── .env.example                      # 配置模板
└── references/
    └── feishu_api_reference.md           # 飞书/Coze API 速查表
```

## 快速开始

### 1. 安装依赖

无需安装额外 Python 包，仅依赖系统自带工具：

- Python 3.8+
- curl

### 2. 配置初始化

**方式一：交互式配置向导（推荐）**

```bash
cd scripts/
python3 article_workflow.py init
```

向导会依次引导配置：飞书 App ID → 飞书 App Secret → 多维表格 Token → 云盘文件夹 → Coze Token，并自动测试连接。

**方式二：手动创建配置文件**

```bash
cd scripts/
cp .env.example .env
# 编辑 .env 填入实际值
```

### 3. 验证配置

```bash
python3 article_workflow.py check-config
```

输出示例（敏感信息自动脱敏）：

```
配置文件: /path/to/scripts/.env
文件存在: 是

配置状态:
  FEISHU_APP_ID      = cli_****9cd3
  FEISHU_APP_SECRET  = tsH1****K36m
  TOPIC_APP_TOKEN    = YjN6bWopMaYixSs1ArncqVBLn1c
  ...
  COZE_API_TOKEN     = sat_****5IAu

✅ 必填配置完整
```

## 配置参数说明

| 参数 | 必填 | 默认值 | 说明 | 获取方式 |
|------|------|--------|------|---------|
| `FEISHU_APP_ID` | 是 | - | 飞书应用 App ID | [飞书开放平台](https://open.feishu.cn) → 创建应用 → 凭证与基础信息 |
| `FEISHU_APP_SECRET` | 是 | - | 飞书应用 App Secret | 同上 |
| `TOPIC_APP_TOKEN` | 否 | 已填 | 选题库多维表格 App Token | 多维表格 URL 中获取 |
| `TOPIC_TABLE_ID` | 否 | 已填 | 选题库表格 ID | 同上 |
| `ARTICLE_APP_TOKEN` | 否 | 已填 | 文案库多维表格 App Token | 同上 |
| `ARTICLE_TABLE_ID` | 否 | 已填 | 文案库表格 ID | 同上 |
| `UPLOAD_FOLDER_TOKEN` | 否 | 已填 | 飞书云盘投稿文件夹 Token | 文件夹 URL 中获取 |
| `COZE_API_TOKEN` | 否* | - | Coze 工作流 API Token | [Coze](https://www.coze.cn) → 工作流 → API 发布 |
| `COZE_WORKFLOW_ID` | 否 | 已填 | Coze 工作流 ID | 同上 |

> *`COZE_API_TOKEN` 不配置时，选题查询、文章分析、云盘上传功能仍可正常使用，仅「写入文案库」步骤不可用。

## 飞书应用权限要求

在飞书开放平台创建应用后，需要开通以下权限：

| 权限 | 用途 |
|------|------|
| `bitable:record` | 读写多维表格记录（选题库、文案库） |
| `drive:file` | 上传文件到云盘 |
| 云文档相关权限 | 访问多维表格数据 |

## 命令参考

### 配置管理

```bash
python3 article_workflow.py init              # 交互式配置向导
python3 article_workflow.py check-config      # 检查配置状态
```

### 选题库操作

```bash
# 按关键词搜索选题（模糊匹配所有字段）
python3 article_workflow.py get-topic "国际政治"

# 按状态过滤
python3 article_workflow.py get-topic "国际政治" --status 待写

# 获取完整字段（含备注、推荐书籍等详细信息）
python3 article_workflow.py get-topic "关键词" --detail

# 更新选题状态
python3 article_workflow.py update-topic-status <record_id> "已完成"
```

### 文案库操作

```bash
# 按分类获取文章列表（内容截断到 200 字符预览）
python3 article_workflow.py get-articles --category "国际政治"

# 按关键词搜索文章
python3 article_workflow.py get-articles --keyword "第3期"

# 获取完整 Markdown 正文（用于深度分析）
python3 article_workflow.py get-articles --keyword "第1期" --full
```

### 飞书云盘

```bash
# 上传文件到默认投稿文件夹
python3 article_workflow.py upload-file /tmp/article.md "文章标题.md"

# 上传到指定文件夹
python3 article_workflow.py upload-file /tmp/article.md "文件名.md" --folder-token <TOKEN>
```

### Coze 工作流（写入文案库）

```bash
python3 article_workflow.py call-coze \
  --title "文章标题" \
  --digest "文章摘要（不超过120字）" \
  --type "文章分类" \
  --content-file /tmp/article.md \
  --image-prompt "英文配图提示词"
```

### 调试

```bash
# 获取当前飞书 token（调试用）
python3 article_workflow.py get-token
```

## 完整工作流示例

以下是 AI 智能体执行一次完整写作任务的标准流程：

```
第1步: 获取选题
  python3 article_workflow.py get-topic "关键词" --detail
  → 记录 record_id

第2步: 分析前几期文章
  python3 article_workflow.py get-articles --category "分类" --full
  → 分析优缺点，确定改进方向

第3步: 搜索资料 + 撰写文章
  → AI 搜索书籍核心观点、作者背景等资料
  → 按写作规范撰写文章，保存到 /tmp/article_new.md

第4步: 上传飞书云盘
  python3 article_workflow.py upload-file /tmp/article_new.md "标题.md"

第5步: 写入文案库
  python3 article_workflow.py call-coze \
    --title "标题" --digest "摘要" --type "分类" \
    --content-file /tmp/article_new.md --image-prompt "prompt"

第6步: 更新选题状态
  python3 article_workflow.py update-topic-status <record_id> "已完成"
```

## 写作规范

AI 撰写文章时应遵循以下要求：

1. **开篇钩子**：用认知冲突或悬念开头，衔接上一期内容
2. **理论讲解**：比喻 + 对话感，避免教科书式平铺直叙
3. **现实案例**：具体数据 + 中式案例（中美博弈、供应链等）
4. **认知反转**：每 2-3 段制造一次"你以为是 A，其实是 B"的转折
5. **实战练习**：2-3 个可操作练习，帮读者内化理论
6. **篇幅**：4000-6000 字
7. **格式**：标准 Markdown，`##` 分节，`**加粗**` 强调重点

## 注意事项

- 所有 API 调用使用飞书 `tenant_access_token`，有效期约 2 小时
- `.env` 文件包含敏感信息，不应提交到 Git 或打包分发
- Coze 工作流为流式响应，脚本自动解析完成状态
- 所有 HTTP 请求通过 `curl` 执行，兼容性好，无需额外 Python 依赖

## 相关项目

- [ishareread-publish](../ishareread-publish/) — 文章发布工具（Hugo 构建 → GitHub Pages → 微信公众号）

## 许可

内部使用工具，爱分享读书团队专用。
