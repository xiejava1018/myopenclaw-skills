---
name: scheme-writer
description: |
  编写方案技能：调用 WeKnora 知识库 + 网络搜索，按用户主题生成结构化 Markdown 方案，并可将结果显式上传回指定知识库归档。
  当用户需要"写方案"、"编写方案"、"方案咨询"、"知识库方案"、"技术方案"、"调研报告"、"可行性方案"、"方案归档"、"上传方案到知识库"、"看库内有什么"、"列库内文档"、"知识库盘点"、"write a scheme"、"knowledge base RAG"、"archive document to KB"时使用此技能。
  核心功能：知识库语义检索（kb_search）、知识库列表（kb_list）、库内文档清单（kb_docs）、文档上传归档（kb_upload）、首次配置引导（init 对话内模式）、知识库别名解析。
  输出格式：默认 Markdown 文本；用户额外说"附引用/标来源"时开启 inline 引用标注。
  首次使用 Claude 会自动用 `init.py --status` 检测并以对话内方式引导配置 URL / API Key / 默认库 / 别名，**无需用户切换到终端**。已配置的用户走零打扰路径。
version: 1.2.0
author: xiejava
tags: [knowledge-base, scheme-writing, weknora, document-upload, interactive-setup]
---

# scheme-writer

调用 WeKnora 知识库 + 网络搜索，按用户主题生成结构化 Markdown 方案，支持显式归档到指定知识库。

## 快速开始

1. **首次使用**：Claude 在第一次收到方案相关请求时会自动跑 `python scripts/init.py --status` 检测：
   - `OK` → 静默继续
   - `NEED_INIT` → 用 `AskUserQuestion` 在对话内引导用户填写 URL / API Key / 默认库 / 别名，全部走 `init.py --set KEY=VAL`，**不切到终端**
   - `NEED_REAUTH` → 提示用户在服务端轮换 Key 后说"重新配置"
   - `NETWORK_ERROR` → 提示用户检查 URL / 网络
2. **调用方式**：
   - "帮我写一份 X 方案"
   - "从《技术规范库》查一下，写一份 K8s 离线部署方案"
   - "把这份方案归档到《方案库》"
3. **重新配置**：用户随时说"重新配置 scheme-writer"或"配置知识库"即可重跑引导。

## 能力矩阵

| 能力 | 脚本 | 何时使用 |
|:-----|:-----|:---------|
| 知识库语义检索 | [scripts/kb_search.py](scripts/kb_search.py) | 需要从知识库拉素材写方案时 |
| 知识库列表 | [scripts/kb_list.py](scripts/kb_list.py) | 用户未指定库，需反问时 |
| **库内文档清单** | [scripts/kb_docs.py](scripts/kb_docs.py) | **需要看某库内具体有哪些文档、哪些已解析/已向量化时**（**检索为空但 doc_count>0 时优先用**） |
| 文档上传归档 | [scripts/kb_upload.py](scripts/kb_upload.py) | 用户显式说"上传/归档到 X"时 |
| 首次配置 | [scripts/init.py](scripts/init.py) | `.env` 不存在或重新配置时 |
| 别名解析 | SKILL.md 顶部别名表 | 解析用户口语化知识库名时 |

## 能力详解

### 能力 1：知识库语义检索（kb_search）

**功能**：在指定知识库中按问题语义检索，返回 top-k 个 chunk。

**触发词**："从 X 查"、"检索 X 知识库"、"基于 X 库"。

**使用步骤**：
1. 解析用户输入，确定 `retrieve_kb`（见 [知识库参数解析](#知识库参数解析)）
2. 把问题整理为 1-2 句检索 query
3. 调 `kb_search.py --kb <kb_id> --query "<query>" --top-k 8 --min-score 0.5`
4. 解析返回 JSON；score < 阈值的 chunk 一律**视为不可用证据**

**输出**：
```json
{
  "kb_id": "kb_id_001",
  "query": "...",
  "chunks": [{"chunk_id": "...", "content": "...", "score": 0.82, "source_doc": "..."}],
  "total": 6
}
```

**协作场景**：
- 与 [能力 2](#能力-2知识库列表kb_list) 协作：retrieve_kb 缺失时先列表再反问用户
- 与 [能力 4](#能力-4文档上传归档kb_upload) 协作：检索后写方案 → 上传归档

**限制**：
- 单次只检索，不负责生成（生成由 Claude 自身完成）
- 多个 kb_id 用逗号分隔，结果会合并

---

### 能力 2：知识库列表（kb_list）

**功能**：列出当前 API Key 可见的所有知识库。

**触发词**：用户未指定 retrieve_kb，且 `.env` 无默认值时。

**使用步骤**：
1. 调 `kb_list.py`
2. 把 `knowledge_bases` 数组呈现给用户
3. 用户选定后把 `kb_id` 代入后续流程

**输出**：
```json
{
  "knowledge_bases": [
    {
      "kb_id": "kb_id_001",
      "name": "技术规范库",
      "doc_count": 142,
      "chunk_count": 1230,
      "description": "..."
    }
  ],
  "total": 1
}
```

> **关键诊断字段**：
> - `doc_count`：服务端 `knowledge_count` 字段，反映**元数据文档数**
> - `chunk_count`：反映**已索引 chunk 数**
> - 当 `chunk_count < doc_count`（特别是 `chunk_count=0` 但 `doc_count>0`）时，**说明文档还在解析/向量化中**——`kb_search` 会返回极少或无结果。此时优先调 `kb_docs.py` 看每个文档的 `parse_status` 字段。

**限制**：仅当 retrieve_kb 完全无法确定时调用，避免无谓打扰用户。

---

### 能力 2.5：库内文档清单（kb_docs）

**功能**：列出某知识库下所有文档的真实元数据（doc_id / title / parse_status / file_size / updated_at 等），是诊断"为什么 doc_count>0 但检索为空"的关键工具。

**触发词**：
- "看库内有什么文档"
- "列一下《X》的内容"
- "知识库盘点"
- "为什么 doc_count=12 但搜不到东西"
- "kb_docs" / "列文档"

**使用步骤**：
1. 调 `python scripts/kb_docs.py --kb <kb_id>` 拿到默认第一页（最多 20 条）
2. 一次性看全：加 `--all` 自动翻页
3. 翻页：`--page 2 --page-size 50`
4. 重点关注 `parse_status` 字段：
   - `"completed"` → 已向量化，可被 `kb_search` 命中
   - `"processing"` / `"pending"` → 还在跑，**等几秒/几分钟重试**
   - `"failed"` → 解析失败，伴随 `error_message` 非空；联系服务端运维

**输出**：
```json
{
  "kb_id": "kb_id_001",
  "total": 12,
  "page": 1,
  "page_size": 20,
  "documents": [
    {
      "doc_id": "doc-uuid-001",
      "title": "中国电信云运〔2024〕29号.pdf",
      "file_name": "中国电信云运〔2024〕29号.pdf",
      "file_type": "pdf",
      "file_size": 2048000,
      "parse_status": "completed",
      "enable_status": "enabled",
      "summary_status": "completed",
      "created_at": "2026-05-01T08:00:00Z",
      "updated_at": "2026-05-01T08:05:00Z",
      "processed_at": "2026-05-01T08:05:00Z",
      "error_message": ""
    }
  ]
}
```

**协作场景**：
- **与 [能力 1 检索](#能力-1知识库语义检索kb_search)协作**：检索返回空但 `kb_list` 显示 `doc_count>0` 时，先调 `kb_docs.py` 看 `parse_status`——如果全是 `processing`，等几秒重试；如果 `chunk_count=0` 且文档已是 `completed`，**说明服务端 embedding 索引有问题**，需联系运维
- **与 [能力 4 上传](#能力-4文档上传归档kb_upload)协作**：上传后立即调 `kb_docs.py` 看新文档的 `parse_status`，确认是否已可检索

**限制**：
- 仅返回文档元数据，不返回文档内容
- 文档分页：`page_size` 上限 100（受服务端限制）
- `parse_status` 状态机：`pending → processing → completed | failed`，`failed` 状态需要人工介入

---

### 能力 3：首次配置（init，对话内模式）

**功能**：Claude 在对话内通过 `AskUserQuestion` 逐步收集 URL / API Key / 默认库 / 别名，并立即通过 `init.py --set KEY=VAL` 落盘到 `~/.claude/scheme-writer/.env`，不要求用户切到终端。

**触发词**：Claude 调用 `init.py --status` 收到 `NEED_INIT` 时自动进入；用户显式说"重新配置 / 配置 scheme-writer"也会触发。

**使用步骤**（Claude 视角）：

1. 探测：`python scripts/init.py --status`
   - 输出单行标签：`OK` / `NEED_INIT` / `NEED_REAUTH` / `NETWORK_ERROR`
   - `OK` → 静默继续
   - `NEED_INIT` → 进入第 2 步
2. 询问 URL：用 `AskUserQuestion` 提供默认值 `http://192.168.30.236/api/v1`
3. 询问 API Key：用 `AskUserQuestion`，**预先告诉用户**：
   > "API Key 会通过 `init.py --set` 立即写入本地 .env，不会回显到终端；如担心泄露可事后在服务端轮换一次。"
4. 询问默认检索库 / 默认上传库（可空，可跳过）
5. 写入：每收到一个值就调 `init.py --set KEY=VAL`
6. 再次探测：`init.py --status` 应当返回 `OK`
7. 别名引导：
   - `python scripts/init.py --list-kbs` 拿到可见库
   - 逐个库用 `AskUserQuestion` 问"为《X》起个口语化别名吗？"
   - 收齐后调 `init.py --set-aliases '{"名称":"kb_id", ...}'`
8. 提示用户"配置完成"

**init.py 子命令**：

| 子命令 | 用途 | 退出码 |
|:-------|:-----|:-------|
| `--status` | 输出单行状态标签 | 0（恒） |
| `--check` | 同上但用退出码（0/1/2/3） | 0/1/2/3 |
| `--set KEY=VAL` | 写入单个配置项 | 0 |
| `--set-aliases JSON` | 写入别名映射 | 0 |
| `--list-kbs` | 列出可见库（JSON） | 0/2/3/5 |
| `--show` | 打印当前配置（Key 脱敏） | 0 |
| （无参） | 终端交互模式，遗留 | 0/1 |

**安全细节**：
- API Key 仅在用户回复 `AskUserQuestion` 时短暂出现，**立即通过 `--set` 落盘**，Claude 后续不再回显、不进入任何日志
- `--show` 模式下 Key 只显示前 4 + 后 4 字符
- 已有 .env 自动备份为 `.env.bak`
- 提示用户**切勿在对话中粘贴 API Key 后不轮换**——已粘贴过的应立即在服务端轮换

---

### 能力 4：文档上传归档（kb_upload）

**功能**：把本地 .md / .txt 上传到指定知识库作为新文档。

**触发词**：用户显式说"上传/归档到 X"时。

**使用步骤**：
1. 调 `kb_upload.py` **之前**先输出一行确认：
   > "确认：正在将《<title>》上传到《<kb_name>》(<kb_id>)...（取消请说"停"）"
2. 等一拍让用户反应，未取消则执行
3. 调 `kb_upload.py --kb <kb_id> --file <path> --title "<title>" --tags "..."`
4. 把 `doc_id` 在对话中回显

**限制**：
- **绝不**默认上传——必须用户显式意图
- 上传后默认不删除本地文件

---

## 协作工作流

### 场景 1：完整流程（检索 → 写作 → 上传）

**目标**：从指定知识库拉素材写方案，归档到目标库。

**执行顺序**：
1. 使用[能力 1 检索](#能力-1知识库语义检索kb_search)拉素材
2. Claude 整理为方案大纲 → 用户确认 → 展开为完整方案
3. 使用[能力 4 上传](#能力-4文档上传归档kb_upload)归档

**示例**：
```
用户请求："帮我从《技术规范库》查一下，写一份 K8s 离线部署方案，写完归档到《方案库》"

执行流程：
→ 步骤 1: 解析 retrieve_kb=kb_id_001、upload_kb=kb_id_002
→ 步骤 2: kb_search.py 检索 "K8s 离线部署" → 6 个 chunk
→ 步骤 3: 写作：先出大纲 → 用户确认 → 完整方案
→ 步骤 4: 上传前确认（"正在将《...》上传到《方案库》..."）
→ 步骤 5: kb_upload.py → doc_id 反馈给用户
```

### 场景 2：用户未指定知识库

**目标**：让用户从可见库中选一个。

**执行顺序**：
1. 使用[能力 2 列表](#能力-2知识库列表kb_list)列出可见库
2. 反问用户选哪个
3. 接到 `kb_id` 后继续场景 1 的流程

---

## 知识库参数解析

按以下优先级解析 `retrieve_kb` 与 `upload_kb`：

1. **显式短语**（最高优先级）
   - "查《技术规范库》"、"从 kb_001 取" → retrieve_kb
   - "归档到《方案库》"、"上传到知识库 B" → upload_kb
2. **别名映射**（见下方别名表）
3. **默认值**（`.env` 中 `DEFAULT_RETRIEVE_KB` / `DEFAULT_UPLOAD_KB`）
4. **空值处理**
   - retrieve_kb 为空且无默认 → 调 `kb_list.py` 反问用户
   - upload_kb 为空 → 永远不上传，绝不默认归档

### 知识库别名映射

> **存放在 `~/.claude/scheme-writer/.env` 的 `KB_ALIASES` 字段**，由 `init.py --set-aliases` 写入与维护。  
> 格式：JSON 对象，键为用户口语化名称，值为 `kb_id`。
> Claude 解析用户输入时通过 `kb_config.get_aliases()` 读取（自动从 .env 解析为 dict）。
>
> 示例 .env 内容：
> ```text
> KB_ALIASES={"技术规范库":"kb_id_001","方案库":"kb_id_002"}
> ```
>
> 重新配置别名：在对话中说"重新配置 scheme-writer"即可重跑别名引导。

---

## 必须遵守的规则

- **规则一**：API Key 仅通过 `.env` 注入，绝不出现在 SKILL.md、对话、提交历史中（不可协商）
- **规则二**：上传前必须有用户显式意图，绝不默认归档
- **规则三**：解析阶段拿不到 retrieve_kb 必须反问用户，不要"猜"一个

### 协作规则

- 检索后 score < 阈值的 chunk 一律丢弃，不当证据使用
- 网络搜索仅在知识库结果为空/全低于阈值时补位
- 上传前必须有一拍"确认"消息，给用户反悔机会

### 禁止事项

- ❌ 在对话中明文打印 API Key
- ❌ 默认/自动上传到任何知识库
- ❌ 把 score < 0.5 的 chunk 当作事实写入方案
- ❌ 跳过 init 直接调用任何 kb_*.py

---

## 参考文档

- [WeKnora API 速查](references/weknora-api.md)
- [错误码与退出码速查](references/error-codes.md)

---

## 快速参考

### 工具调用速查

| 动作 | 命令 |
|:-----|:------|
| **对话内模式**：探测状态 | `python scripts/init.py --status` |
| **对话内模式**：写单个配置 | `python scripts/init.py --set KNOWLEDGE_BASE_URL=...` |
| **对话内模式**：写别名 | `python scripts/init.py --set-aliases '{"a":"b"}'` |
| **对话内模式**：列可见库 | `python scripts/init.py --list-kbs` |
| **对话内模式**：看当前配置 | `python scripts/init.py --show` |
| 终端交互模式（遗留） | `python scripts/init.py` |
| 检查配置（退出码） | `python scripts/init.py --check` |
| 列出知识库 | `python scripts/kb_list.py` |
| 检索 | `python scripts/kb_search.py --kb <id> --query "<q>"` |
| 列某库下所有文档 | `python scripts/kb_docs.py --kb <id> [--all] [--page-size N]` |
| 上传 | `python scripts/kb_upload.py --kb <id> --file <path> --title "<t>"` |

### 故障排除

**问题 1**：调 `kb_list.py` 报 `auth` 错误
- **原因**：API Key 无效或过期
- **解决**：在服务端轮换 Key，告诉 Claude"重新配置 scheme-writer"，Claude 会走对话内流程重写

**问题 2**：`init.py --status` 返回 `NEED_INIT`
- **原因**：`.env` 缺失或缺关键字段
- **解决**：Claude 会自动进入对话内配置流程；用户也可手动跑 `python scripts/init.py`（终端模式）

**问题 3**：`init.py --status` 返回 `NEED_REAUTH`
- **原因**：API Key 失效
- **解决**：在服务端轮换 Key，告诉 Claude"重新配置 scheme-writer"

**问题 4**：`init.py --status` 返回 `NETWORK_ERROR`
- **原因**：URL 写错、网络不通或 WeKnora 故障
- **解决**：用户核对 `init.py --show` 中的 URL；确认网络；确认服务端状态

**问题 5**：检索返回空 chunks
- **原因**：知识库无相关文档，或 query 表达与库内文档差异过大
- **解决**：调 `kb_list.py` 确认库名正确；用更短 query 重试；或补 WebSearch

**问题 6**：上传返回 `kb_not_found`
- **原因**：`--kb` 的 ID 写错，或当前 API Key 无该库权限
- **解决**：调 `kb_list.py` 重新确认 kb_id

**问题 7**：`kb_search` 返回 chunks 极少或为空，但 `kb_list` 显示 `doc_count > 0`
- **原因**：文档已上传但**解析或向量化未完成**。最常见信号是 `chunk_count=0`（kb_list 透出的字段）或文档 `parse_status != "completed"`
- **解决**：
  1. 调 `python scripts/kb_docs.py --kb <id> --all` 看每个文档的 `parse_status`
  2. `parse_status=processing` → 等几秒重试
  3. `parse_status=completed` 但 `chunk_count=0` → 服务端 embedding 索引异常，联系运维
  4. `parse_status=failed` → 看 `error_message` 字段，联系运维

**问题 8**：上传文档后立即 `kb_search` 搜不到
- **原因**：WeKnora `manual` 端点**上传是异步的**——只返回 `doc_id`，不等待解析与向量化完成
- **解决**：调 `python scripts/kb_docs.py --kb <id>` 看新文档的 `parse_status`；`processing` 等几秒后重试

**问题 9**：`kb_list` 显示某个库的 `doc_count=0` 但实际有内容
- **原因**：`doc_count` 来自服务端 `knowledge_count`，极端情况下数据漂移（理论上不应出现）
- **解决**：调 `python scripts/kb_docs.py --kb <id>` 二次确认文档数量
