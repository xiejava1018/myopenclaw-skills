---
name: ishareread-article-writing
description: |
  爱分享读书公众号文章写作全流程工具。从飞书选题库获取选题→分析文案库前几期文章→搜索资料撰写新文章→上传飞书云盘→调用Coze工作流写入文案库→更新选题状态。
  触发场景：(1) 用户要求写新的公众号文章 (2) 用户提到"选题""写稿""文案库""飞书云盘投稿" (3) 用户要求查看或更新飞书选题库/文案库
  触发词：写文章、新选题、选题库、文案库、飞书投稿、爱分享读书写稿
---

# 爱分享读书 — 文章写作全流程

从飞书选题库选题 → 分析文案库前几期文章优缺点 → 搜索资料撰写新文章 → 上传飞书云盘 → 写入文案库 → 更新选题状态。

## 首次使用：配置初始化

所有 API Key 和配置参数通过 `.env` 文件管理，**不硬编码在脚本中**。

```bash
# 方式一：交互式配置向导（推荐）
python3 scripts/article_workflow.py init

# 方式二：手动创建配置文件
cp scripts/.env.example scripts/.env
# 编辑 .env 填入实际值
```

需要配置的参数：

| 参数 | 必填 | 说明 | 获取方式 |
|------|------|------|---------|
| `FEISHU_APP_ID` | 是 | 飞书应用 App ID | [飞书开放平台](https://open.feishu.cn) → 创建应用 → 凭证 |
| `FEISHU_APP_SECRET` | 是 | 飞书应用 App Secret | 同上 |
| `TOPIC_APP_TOKEN` | 否 | 选题库多维表格 Token | 已有默认值 |
| `ARTICLE_APP_TOKEN` | 否 | 文案库多维表格 Token | 已有默认值 |
| `UPLOAD_FOLDER_TOKEN` | 否 | 投稿文件夹 Token | 已有默认值 |
| `COZE_API_TOKEN` | 否* | Coze API Token | [Coze](https://www.coze.cn) → 工作流 → API |
| `COZE_WORKFLOW_ID` | 否 | Coze 工作流 ID | 已有默认值 |

*注：`COZE_API_TOKEN` 不配置时仍可使用选题、文章、上传功能，仅调用 Coze 写入文案库时需要。

```bash
# 检查当前配置状态（敏感信息自动脱敏）
python3 scripts/article_workflow.py check-config
```

## 工具脚本

`scripts/article_workflow.py` 封装了所有飞书/Coze API 调用。配置通过 `scripts/.env` 文件管理。

详细 API 参数说明见 [references/feishu_api_reference.md](references/feishu_api_reference.md)。

## 完整工作流

### 第1步：获取选题

```bash
# 按关键词搜索选题（模糊匹配所有字段）
python3 scripts/article_workflow.py get-topic "国际政治第5期"

# 按状态过滤
python3 scripts/article_workflow.py get-topic "国际政治" --status 待写

# 获取完整字段（含备注、推荐书籍等）
python3 scripts/article_workflow.py get-topic "关键词" --detail
```

记录返回的 `record_id`，后续更新状态需要。

### 第2步：分析前几期文章

```bash
# 按分类获取文章列表
python3 scripts/article_workflow.py get-articles --category "国际政治"

# 按关键词获取文章列表
python3 scripts/article_workflow.py get-articles --keyword "第3期"

# 获取完整 Markdown 内容（用于深度分析）
python3 scripts/article_workflow.py get-articles --keyword "第1期" --full
```

分析要点：
- **优点**：结构清晰的开篇钩子、生动的比喻、有力的现实案例、互动练习设计
- **不足**：篇幅是否匀称、理论讲解是否过于平铺直叙、案例是否鲜活、有没有"认知反转"的张力
- **改进方向**：新文章必须在分析出的薄弱环节上有明显提升

### 第3步：搜索资料并撰写文章

使用 WebSearch / mcp__web-search-prime__web_search_prime 搜索选题相关书籍的核心观点、作者背景、理论框架等资料。

写作要求：
1. **开篇钩子**：用一个认知冲突或悬念开头，直接衔接上一期内容
2. **理论讲解**：用比喻和对话感讲透核心概念，避免教科书式平铺直叙
3. **现实案例**：用具体数据和中式案例（如：中美博弈、供应链、芯片战等）
4. **认知反转**：每 2-3 段制造一次"你以为是 A，其实是 B"的转折
5. **实战练习**：设计 2-3 个可操作的练习，帮读者内化理论（可选）
6. **篇幅**：4000-6000 字为宜
7. **格式**：标准 Markdown，`##` 分节，`###` 子节，`**加粗**` 强调重点

将文章保存到本地临时文件，如 `/tmp/article_new.md`。

### 第4步：上传飞书云盘

```bash
python3 scripts/article_workflow.py upload-file /tmp/article_new.md "文章标题.md"
```

默认上传到"爱分享读书投稿"文件夹。可指定 `--folder-token` 上传到其他文件夹。

### 第5步：写入文案库

调用 Coze `article2table_api` 工作流，将文章写入飞书文案库多维表格。

```bash
python3 scripts/article_workflow.py call-coze \
  --title "文章标题" \
  --digest "文章摘要（不超过120字）" \
  --type "文章分类" \
  --content-file /tmp/article_new.md \
  --image-prompt "根据文章内容生成的配图提示词（英文）"
```

参数说明：
- `--digest`：不超过 120 字的摘要
- `--image-prompt`：英文描述，用于生成文章配图

### 第6步：更新选题状态

```bash
python3 scripts/article_workflow.py update-topic-status <record_id> "已完成"
```

使用第1步获取的 `record_id`。

## 辅助命令

```bash
# 仅获取飞书 token（调试用）
python3 scripts/article_workflow.py get-token
```

## 注意事项

- 所有 API 调用使用 `tenant_access_token`，有效期约 2 小时
- Coze 工作流为流式响应，脚本自动解析完成状态
- 选题库和文案库的字段定义见 [references/feishu_api_reference.md](references/feishu_api_reference.md)
