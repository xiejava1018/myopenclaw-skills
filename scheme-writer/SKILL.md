---
name: scheme-writer
description: |
  编写方案技能：调用 WeKnora 知识库 + 网络搜索，按用户主题生成结构化 Markdown 方案，并可将结果显式上传回指定知识库归档。
  当用户需要"写方案"、"编写方案"、"方案咨询"、"知识库方案"、"技术方案"、"调研报告"、"可行性方案"、"方案归档"、"上传方案到知识库"、"看库内有什么"、"列库内文档"、"知识库盘点"、"write a scheme"、"knowledge base RAG"、"archive document to KB"时使用此技能。
  核心功能：知识库语义检索（kb_search，支持多来源合并）、知识库列表（kb_list，支持 --source/--all）、库内文档清单（kb_docs）、文档上传归档（kb_upload，单一来源目标）、首次配置与多来源管理（init 对话内模式）、来源/知识库引用解析（kb_resolve，内部依赖）。
  输出格式：默认 Markdown 文本；用户额外说"附引用/标来源"时开启 inline 引用标注。
  首次使用 Claude 会自动用 `init.py --status` 检测并以对话内方式引导添加来源（URL / API Key / 默认源 / 别名），**无需用户切换到终端**。老用户首跑会自动迁移（旧单实例配置提升为 `default` 来源，别名加 `default/` 前缀），零摩擦。已配置的用户走零打扰路径。
version: 1.3.0
author: xiejava
tags: [knowledge-base, scheme-writing, weknora, document-upload, interactive-setup]
---

# scheme-writer

调用 WeKnora 知识库 + 网络搜索，按用户主题生成结构化 Markdown 方案，支持显式归档到指定知识库。支持配置多个来源（多实例 / 多空间），可跨来源检索并合并结果。

## 快速开始

1. **首次使用**：Claude 在第一次收到方案相关请求时会自动跑 `python scripts/init.py --status` 检测（首跑会自动迁移旧单实例配置为 `default` 来源）：
   - `OK` → 静默继续
   - `NEED_INIT` → 用 `AskUserQuestion` 在对话内引导用户**添加来源**（名字 / URL / API Key），走 `init.py --add-source NAME URL KEY`，**不切到终端**；随后可继续配置默认源 / 默认库 / 别名
   - `NEED_REAUTH` → 提示用户在对应来源服务端轮换 Key 后说"重新配置"
   - `NETWORK_ERROR` → 提示用户检查该来源 URL / 网络
2. **调用方式**：
   - "帮我写一份 X 方案"
   - "从运维空间1的《技术规范库》查一下，写一份 K8s 离线部署方案"
   - "从运维空间1和安全部一起查漏洞信息"（多来源检索）
   - "把这份方案归档到运维空间1的《方案库》"
3. **重新配置 / 加来源**：用户随时说"重新配置 scheme-writer""加一个来源""配置知识库"即可重跑引导或追加来源。

## 能力矩阵

| 能力 | 脚本 | 何时使用 |
|:-----|:-----|:---------|
| 知识库语义检索 | [scripts/kb_search.py](scripts/kb_search.py) | 需要从知识库拉素材写方案时；`--kb` 支持逗号分隔多来源 |
| 知识库列表 | [scripts/kb_list.py](scripts/kb_list.py) | 用户未指定库 / 来源，需反问时；`--source X` 列某源，`--all` 列全部来源 |
| **库内文档清单** | [scripts/kb_docs.py](scripts/kb_docs.py) | **需要看某库内具体有哪些文档、哪些已解析/已向量化时**（**检索为空但 doc_count>0 时优先用**） |
| 文档上传归档 | [scripts/kb_upload.py](scripts/kb_upload.py) | 用户显式说"上传/归档到 X"时；目标必须收敛到**单一来源** |
| 首次配置 + 多来源管理 | [scripts/init.py](scripts/init.py) | `.env` 不存在、重新配置、新增/删除/列举来源时 |
| 来源 / kb 引用解析 | [scripts/kb_resolve.py](scripts/kb_resolve.py)（内部依赖） | 把用户/CLI 传入的 kb 引用解析成 `(来源, kb_id)`；各 kb_*.py 共用，无需直接调用 |
| 别名解析 | `KB_ALIASES`（键为 `来源/库名`） | 解析用户口语化知识库名时 |

## 能力详解

### 能力 1：知识库语义检索（kb_search）

**功能**：在指定知识库中按问题语义检索，返回 top-k 个 chunk。`--kb` 支持逗号分隔的**多来源引用**，多目标时逐源检索后合并（按 `(source, -score)` 排序，不跨源全局重排）。

**触发词**："从 X 查"、"检索 X 知识库"、"基于 X 库"、"从 A 和 B 一起查"。

**使用步骤**：
1. 解析用户输入，确定 kb 引用（见 [知识库参数解析](#知识库参数解析)）——可带 `来源/库名` 限定别名
2. 把问题整理为 1-2 句检索 query
3. 调 `kb_search.py --kb <来源/库名> --query "<query>" --top-k 8 --min-score 0.5`
   - 多源：`--kb 运维空间1/技术规范库,安全部/漏洞库`（每源各返回最多 top-k 条）
4. 解析返回 JSON；score < 阈值的 chunk 一律**视为不可用证据**

**输出**：

单目标（向后兼容老结构）：
```json
{
  "kb_id": "kb_id_001",
  "query": "...",
  "chunks": [{"chunk_id": "...", "content": "...", "score": 0.82, "source_doc": "..."}],
  "total": 6
}
```

多目标（新增 `sources` / `errors` 字段，每条 chunk 带 `source` 标签）：
```json
{
  "sources": ["运维空间1", "安全部"],
  "query": "...",
  "chunks": [{"source": "运维空间1", "kb_id": "kb-001", "source_doc": "...", "content": "...", "score": 0.82}],
  "total": 11,
  "errors": [{"source": "安全部", "error": "auth", "message": "..."}]
}
```

> **部分失败策略**：多源检索时某源挂了（网络抖动 / Key 失效）**不整体失败**——健康源结果照常返回，挂掉的源进 `errors` 数组。退出码：≥1 源成功 → 0；全失败 → 对应错误码。

**协作场景**：
- 与 [能力 2](#能力-2知识库列表kb_list) 协作：retrieve_kb 缺失时先列表（`--all` 跨源）再反问用户
- 与 [能力 4](#能力-4文档上传归档kb_upload) 协作：检索后写方案 → 上传归档

**限制**：
- 单次只检索，不负责生成（生成由 Claude 自身完成）
- `--top-k` 是**每源**各返回最多 N 条（2 源 → 最多 2N 条），无全局预分配
- 不同来源 embedding 模型可能不同，分数**不跨源比较**，仅源内排序

---

### 能力 2：知识库列表（kb_list）

**功能**：列出可见知识库。默认列**默认来源**（或单来源隐式）；`--source X` 列某来源；`--all` 列**全部来源**（结果每条带 `source` 标签，单源失败不致命）。

**触发词**：用户未指定 retrieve_kb 且无默认值时；或用户说"列一下所有来源的库"。

**使用步骤**：
1. 调 `kb_list.py`（默认源）/ `kb_list.py --source 运维空间1`（指定源）/ `kb_list.py --all`（全部源）
2. 把 `knowledge_bases` 数组呈现给用户
3. 用户选定后把 `来源/库名`（或 `来源/kb_id`）代入后续流程

**输出**：
```json
{
  "knowledge_bases": [
    {
      "kb_id": "kb_id_001",
      "name": "技术规范库",
      "doc_count": 142,
      "chunk_count": 1230,
      "description": "...",
      "source": "运维空间1"
    }
  ],
  "total": 1,
  "errors": []
}
```

> `--all` 模式下若某来源失败，该源进 `errors`，健康源照常返回（与 kb_search 一致的部分失败语义）。

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
1. 调 `python scripts/kb_docs.py --kb <来源/库名>` 拿到默认第一页（最多 20 条）
2. 一次性看全：加 `--all` 自动翻页
3. 翻页：`--page 2 --page-size 50`
4. 重点关注 `parse_status` 字段：
   - `"completed"` → 已向量化，可被 `kb_search` 命中
   - `"processing"` / `"pending"` → 还在跑，**等几秒/几分钟重试**
   - `"failed"` → 解析失败，伴随 `error_message` 非空；联系该来源服务端运维

**输出**：
```json
{
  "source": "运维空间1",
  "kb_id": "kb_id_001",
  "total": 12,
  "page": 1,
  "page_size": 20,
  "documents": [
    {
      "doc_id": "doc-uuid-001",
      "title": "示例单位_运维规范〔2024〕29号.pdf",
      "file_name": "示例单位_运维规范〔2024〕29号.pdf",
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

### 能力 3：首次配置 + 多来源管理（init，对话内模式）

**功能**：Claude 在对话内通过 `AskUserQuestion` 逐步收集来源信息（名字 / URL / API Key）并立即落盘到 `~/.claude/scheme-writer/.env`，不要求用户切到终端。支持多来源的增删改查、设默认源、别名发现。

**首跑自动迁移**：脚本启动时会幂等执行迁移——检测到旧单实例 `KNOWLEDGE_BASE_URL + KEY` 但无 `SOURCES` 时，自动合成 `{"name":"default",...}` 写入 `SOURCES`、设 `DEFAULT_SOURCE=default`，并把旧 `KB_ALIASES` 键自动加 `default/` 前缀。老用户零感知（单源即 default，所有行为退化到现状）。迁移日志只打变更键名，**绝不打印明文 Key**。

**触发词**：Claude 调用 `init.py --status` 收到 `NEED_INIT` 时自动进入；用户显式说"重新配置 / 加一个来源 / 配置 scheme-writer"也会触发。

**使用步骤**（Claude 视角，每加一个来源）：

1. 探测：`python scripts/init.py --status`
   - 输出单行标签：`OK` / `NEED_INIT` / `NEED_REAUTH` / `NETWORK_ERROR`
   - `OK` → 静默继续
   - `NEED_INIT` → 进入第 2 步（`NEED_INIT` 现在意味"SOURCES 完全没配"）
2. 询问来源名字（如 `运维空间1`；不能含 `/`，否则破坏 `来源/库名` 解析）
3. 询问 URL：用 `AskUserQuestion` 提供默认值 `http://192.168.30.236/api/v1`
4. 询问 API Key：用 `AskUserQuestion`，**预先告诉用户**：
   > "API Key 会通过 `init.py --add-source` 立即写入本地 .env，不会回显到终端；如担心泄露可事后在服务端轮换一次。"
5. 追加：`init.py --add-source <名字> <URL> <KEY>`（首个来源自动设为 `DEFAULT_SOURCE`）
6. 探测连通：`init.py --list-kbs` 确认该源可达（注意：首个来源已自动设默认，故默认源即新加来源）
7. 别名发现（可选）：
   - `python scripts/kb_list.py --source <名字>` 拿到该源可见库
   - 逐个库用 `AskUserQuestion` 问"为《X》起个口语化别名吗？"
   - 收齐后调 `init.py --set-aliases '{"来源/名称":"kb_id", ...}'`（键必须带 `来源/` 前缀）
8. 可选：询问默认检索库 / 默认上传库（值用限定名 `运维空间1/技术规范库`），走 `init.py --set DEFAULT_RETRIEVE_KB=...`
9. 再次探测：`init.py --status` 应当返回 `OK`
10. 提示用户"配置完成"

**init.py 子命令**：

| 子命令 | 用途 | 退出码 |
|:-------|:-----|:-------|
| `--status` | 输出单行状态标签 | 0（恒） |
| `--check` | 同上但用退出码（0/1/2/3） | 0/1/2/3 |
| `--set KEY=VAL` | 写入单个标量配置项（白名单见下） | 0 |
| `--set-aliases JSON` | 写入别名映射（键为 `来源/库名`） | 0 |
| `--list-kbs` | 列出默认来源可见库（JSON） | 0/2/3/5 |
| `--show` | 打印当前配置（Key 脱敏）+ sources 数组 + default_source | 0 |
| `--add-source NAME URL KEY` | 追加来源（首个自动设默认） | 0/2 |
| `--set-sources JSON` | 整体覆写 SOURCES（JSON 数组） | 0/2 |
| `--remove-source NAME` | 删来源（删默认则清空默认） | 0/2 |
| `--set-default-source NAME` | 设默认来源（校验存在） | 0/2 |
| `--list-sources` | 列所有来源（Key 脱敏）+ 各源连通状态 | 0 |
| （无参） | 终端交互模式，遗留 | 0/1 |

> **`--set` 可写白名单**：`DEFAULT_RETRIEVE_KB` / `DEFAULT_UPLOAD_KB` / `DEFAULT_SOURCE` / `KB_ALIASES`。旧 `KNOWLEDGE_BASE_URL` / `KNOWLEDGE_BASE_API_KEY` **已移出白名单**（仅供迁移识别，不再可 `--set`）。新增来源一律用 `--add-source` / `--set-sources`。

**安全细节**：
- 所有来源的 API Key 仅在用户回复 `AskUserQuestion` 时短暂出现，**立即通过 `--add-source`/`--set-sources` 落盘**，Claude 后续不再回显、不进入任何日志
- `--show` / `--list-sources` 模式下每个 Key 只显示前 4 + 后 4 字符
- 输出里的 `source` 字段是**来源名字不是 Key**，安全可显示
- 已有 .env 自动备份为 `.env.bak`
- 提示用户**切勿在对话中粘贴 API Key 后不轮换**——已粘贴过的应立即在对应来源服务端轮换

---

### 能力 4：文档上传归档（kb_upload）

**功能**：把本地 .md / .txt 上传到指定知识库作为新文档。**上传不跨源**：`--kb` 必须收敛到**唯一的单一来源**（多个目标会被拒绝）。

**触发词**：用户显式说"上传/归档到 X"时。

**使用步骤**：
1. 调 `kb_upload.py` **之前**先输出一行确认：
   > "确认：正在将《<title>》上传到《<来源/库名>》...（取消请说"停"）"
2. 等一拍让用户反应，未取消则执行
3. 调 `kb_upload.py --kb <来源/库名> --file <path> --title "<title>" --tags "..."`
4. 把 `doc_id` 在对话中回显

**限制**：
- **绝不**默认上传——必须用户显式意图
- 上传目标必须单一来源，歧义（裸名跨源撞名 / 逗号多目标）直接报错，不猜
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
用户请求："帮我从运维空间1的《技术规范库》查一下，写一份 K8s 离线部署方案，写完归档到运维空间1的《方案库》"

执行流程：
→ 步骤 1: 解析 retrieve_kb=运维空间1/技术规范库、upload_kb=运维空间1/方案库
→ 步骤 2: kb_search.py --kb 运维空间1/技术规范库 --query "K8s 离线部署" → 6 个 chunk
→ 步骤 3: 写作：先出大纲 → 用户确认 → 完整方案
→ 步骤 4: 上传前确认（"正在将《...》上传到《运维空间1/方案库》..."）
→ 步骤 5: kb_upload.py --kb 运维空间1/方案库 → doc_id 反馈给用户
```

### 场景 1.5：多来源检索合并

**目标**：跨多个来源 / 多个库同时检索，合并素材。

**示例**：
```
用户请求："从运维空间1的《技术规范库》和安全部的《漏洞库》一起查 K8s 相关风险"

执行流程：
→ kb_search.py --kb 运维空间1/技术规范库,安全部/漏洞库 --query "K8s 风险" --top-k 8
→ 输出多源结构：sources=["运维空间1","安全部"]，每条 chunk 带 source 标签
→ 若安全部源 Key 失效：errors=[{source:"安全部",...}]，运维空间1结果照常返回
→ Claude 按 (source, -score) 整理素材，安全部缺口补 WebSearch
```

### 场景 2：用户未指定来源 / 知识库

**目标**：让用户从可见库中选一个。

**执行顺序**：
1. 使用[能力 2 列表](#能力-2知识库列表kb_list)：`kb_list.py --all` 列出全部来源的库（每条带 `source` 标签）
2. 反问用户选哪个（用 `来源/库名` 引用）
3. 接到选择后继续场景 1 的流程

> 若只有单一来源，`kb_list.py` 无参即列该源（隐式默认），行为与旧版一致。

---

## 知识库参数解析

每个 kb 引用必须同时解析出 **`(来源, kb_id)`**——HTTP 调用需要来源的 `(url, key)` + kb_id。解析由 [scripts/kb_resolve.py](scripts/kb_resolve.py) 统一负责，所有 kb_*.py 共用。

按以下优先级解析 `retrieve_kb` 与 `upload_kb`：

1. **显式短语**（最高优先级）
   - "查运维空间1的《技术规范库》"、"从 kb_001 取" → retrieve_kb
   - "归档到《方案库》"、"上传到知识库 B" → upload_kb
2. **别名映射**（见下方别名映射，键为 `来源/库名`）
3. **默认值**（`.env` 中 `DEFAULT_RETRIEVE_KB` / `DEFAULT_UPLOAD_KB`，值用限定名或裸字面）
4. **空值处理**
   - retrieve_kb 为空且无默认 → 调 `kb_list.py --all` 反问用户
   - upload_kb 为空 → 永远不上传，绝不默认归档

### kb 引用的四种形态（`--kb` 接受逗号分隔多个）

| 形态 | 例子 | 解析结果 |
|:-----|:-----|:---------|
| **限定别名**（首选） | `运维空间1/技术规范库` | 命中 `KB_ALIASES` → `(运维空间1, kb-001)`，自带 source |
| **限定字面** | `运维空间1/kb-001` | 含 `/` 且前缀是已知来源但非别名 → `(运维空间1, kb-001)` |
| **裸名** | `技术规范库` | 后缀匹配别名键；唯一命中即解析；**多命中报歧义**（铁律三：不猜）；无命中当字面 kb_id |
| **裸字面** | `kb-001` | source 由 `--source` 或 `DEFAULT_SOURCE` 决定，都无则报错 |

> **裸名歧义**：多个来源有同名库时（如 `运维空间1/技术规范库` 和 `运维空间2/技术规范库`），裸名 `技术规范库` 会报歧义，需用 `来源/库名` 明确。

### source 解析优先级

`--source` 显式 > 限定别名前缀 > `DEFAULT_SOURCE`（无则单来源隐式） > 报错反问（铁律三）。

> 单来源场景（迁移后的 `default`）由 `resolve_default_source()` 隐式选中，所有调用无需带 `--source`，向后兼容。

### 知识库别名映射

> **存放在 `~/.claude/scheme-writer/.env` 的 `KB_ALIASES` 字段**，由 `init.py --set-aliases` 写入与维护。
> 格式：JSON 对象，键为**带来源前缀的限定名** `来源/库名`，值为 `kb_id`。
> Claude 解析用户输入时通过 `kb_config.get_aliases()` 读取（自动从 .env 解析为 dict）。
>
> 示例 .env 内容：
> ```text
> KB_ALIASES={"运维空间1/技术规范库":"kb-001","运维空间1/方案库":"kb-002","安全部/漏洞库":"kb-001"}
> ```
>
> **老用户迁移**：旧裸别名 `{"技术规范库":"kb-001"}` 在首跑迁移后自动重写为 `{"default/技术规范库":"kb-001"}`（加 `default/` 前缀）。这是保持解析模型统一无特例的唯一办法——一旦默认源改名或换默认源，裸别名会静默指向错误库。
>
> 重新配置别名：在对话中说"重新配置 scheme-writer"或"为 X 起别名"即可重跑别名引导。

---

## 必须遵守的规则

- **铁律一**：所有来源的 API Key（N 个来源 = N 个 Key）仅通过 `.env` 的 `SOURCES` 注入，绝不出现在 SKILL.md、对话、提交历史中（不可协商）。输出里的 `source` 字段是名字不是 Key。
- **铁律二**：上传前必须有用户显式意图，绝不默认归档；且上传目标必须收敛到**单一来源**（不跨源）。
- **铁律三**：解析阶段拿不到确定的来源 / retrieve_kb 必须反问用户，不要"猜"一个——裸名跨源歧义、来源无法确定都报错反问。

### 协作规则

- 检索后 score < 阈值的 chunk 一律丢弃，不当证据使用（多源时逐源过滤）
- 多源检索部分失败时，健康源结果照常使用，失败源缺口可用 WebSearch 补位
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
| 探测状态 | `python scripts/init.py --status` |
| 看当前配置（Key 脱敏） | `python scripts/init.py --show` |
| **追加来源**（首个自动设默认） | `python scripts/init.py --add-source NAME URL KEY` |
| 整体覆写来源（批量） | `python scripts/init.py --set-sources '[{"name":...,"url":...,"api_key":...}]'` |
| 删除来源 | `python scripts/init.py --remove-source NAME` |
| 设默认来源 | `python scripts/init.py --set-default-source NAME` |
| 列所有来源 + 连通性 | `python scripts/init.py --list-sources` |
| 写别名（键为 `来源/库名`） | `python scripts/init.py --set-aliases '{"运维空间1/技术规范库":"kb-001"}'` |
| 写标量配置（白名单内） | `python scripts/init.py --set DEFAULT_RETRIEVE_KB=运维空间1/技术规范库` |
| 列可见库（默认源） | `python scripts/init.py --list-kbs` |
| 列某来源可见库 | `python scripts/kb_list.py --source NAME` |
| 检查配置（退出码） | `python scripts/init.py --check` |
| 列知识库（默认源） | `python scripts/kb_list.py` |
| 列某来源知识库 | `python scripts/kb_list.py --source NAME` |
| 列全部来源知识库 | `python scripts/kb_list.py --all` |
| 检索（单源） | `python scripts/kb_search.py --kb 来源/库名 --query "<q>"` |
| 检索（多源，逗号分隔） | `python scripts/kb_search.py --kb 来源/库名,来源/库名 --query "<q>" --top-k 8` |
| 列某库下所有文档 | `python scripts/kb_docs.py --kb 来源/库名 [--all] [--page-size N]` |
| 上传（单一来源目标） | `python scripts/kb_upload.py --kb 来源/库名 --file <path> --title "<t>"` |
| 终端交互模式（遗留） | `python scripts/init.py` |

> **已弃用**：`--set KNOWLEDGE_BASE_URL=...` / `--set KNOWLEDGE_BASE_API_KEY=...` 已移出可写白名单（仅供迁移识别）。新增来源一律用 `--add-source` / `--set-sources`。

### .env 配置示例

```text
# 来源清单（必填）
SOURCES=[{"name":"运维空间1","url":"http://192.168.30.236/api/v1","api_key":"sk-xxx1"},{"name":"安全部","url":"http://10.5.20.8/api/v1","api_key":"sk-xxx2"}]
# 默认来源（可选；单来源时可省略，隐式选中）
DEFAULT_SOURCE=运维空间1
# 别名（键为 来源/库名）
KB_ALIASES={"运维空间1/技术规范库":"kb-001","运维空间1/方案库":"kb-002","安全部/漏洞库":"kb-001"}
# 默认检索/上传库（值用限定名或裸字面）
DEFAULT_RETRIEVE_KB=运维空间1/技术规范库
DEFAULT_UPLOAD_KB=运维空间1/方案库
```

> 旧 `KNOWLEDGE_BASE_URL` / `KNOWLEDGE_BASE_API_KEY` 不再被直接读取，仅供首跑迁移识别；迁移后保留在 .env 作为回滚线索。

### 故障排除

**问题 1**：调 `kb_list.py` 报 `auth` 错误
- **原因**：该来源 API Key 无效或过期
- **解决**：在对应来源服务端轮换 Key，告诉 Claude"重新配置 scheme-writer"或"更新 X 来源的 Key"，Claude 会走对话内流程重新 `--add-source` / `--set-sources`

**问题 2**：`init.py --status` 返回 `NEED_INIT`
- **原因**：`SOURCES` 完全没配（`.env` 缺失或无来源）
- **解决**：Claude 会自动进入对话内配置流程引导添加来源；用户也可手动跑 `python scripts/init.py`（终端模式）

**问题 3**：`init.py --status` 返回 `NEED_REAUTH`
- **原因**：默认来源 API Key 失效
- **解决**：在对应来源服务端轮换 Key，告诉 Claude"重新配置 scheme-writer"

**问题 4**：`init.py --status` 返回 `NETWORK_ERROR`
- **原因**：默认来源 URL 写错、网络不通或 WeKnora 故障
- **解决**：用户核对 `init.py --show` 中该来源 URL；确认网络；确认服务端状态。多源混合健康度用 `init.py --list-sources` 看每源连通状态。

**问题 5**：检索返回空 chunks
- **原因**：该库无相关文档，或 query 表达与库内文档差异过大
- **解决**：调 `kb_list.py --source <来源>` 确认库名正确；用更短 query 重试；或补 WebSearch

**问题 6**：上传返回 `kb_not_found`
- **原因**：`--kb` 解析出的 kb_id 写错，或当前来源 API Key 无该库权限
- **解决**：调 `kb_list.py --source <来源>` 重新确认 kb_id

**问题 7**：`kb_search` 返回 chunks 极少或为空，但 `kb_list` 显示 `doc_count > 0`
- **原因**：文档已上传但**解析或向量化未完成**。最常见信号是 `chunk_count=0`（kb_list 透出的字段）或文档 `parse_status != "completed"`
- **解决**：
  1. 调 `python scripts/kb_docs.py --kb <来源/库名> --all` 看每个文档的 `parse_status`
  2. `parse_status=processing` → 等几秒重试
  3. `parse_status=completed` 但 `chunk_count=0` → 服务端 embedding 索引异常，联系运维
  4. `parse_status=failed` → 看 `error_message` 字段，联系运维

**问题 8**：上传文档后立即 `kb_search` 搜不到
- **原因**：WeKnora `manual` 端点**上传是异步的**——只返回 `doc_id`，不等待解析与向量化完成
- **解决**：调 `python scripts/kb_docs.py --kb <来源/库名>` 看新文档的 `parse_status`；`processing` 等几秒后重试

**问题 9**：`kb_list` 显示某个库的 `doc_count=0` 但实际有内容
- **原因**：`doc_count` 来自服务端 `knowledge_count`，极端情况下数据漂移（理论上不应出现）
- **解决**：调 `python scripts/kb_docs.py --kb <来源/库名>` 二次确认文档数量

**问题 10**：多源检索返回 `errors` 数组里有某个来源失败
- **原因**：该来源网络抖动 / Key 失效 / 服务端故障（部分失败，不致命）
- **解决**：看 `errors` 里该源的 `error` 字段（`auth` / `network` / `server`）；健康源结果已照常返回，可直接使用；针对失败源按问题 1/4 处理后重试

**问题 11**：裸名引用报歧义（`'X' 在多个来源歧义`）
- **原因**：多个来源有同名库，裸名 `X` 无法确定指向哪个
- **解决**：用 `来源/X` 限定别名明确指向，或加 `--source NAME`

**问题 12**：老用户首跑后别名变成 `default/` 前缀
- **原因**：首跑自动迁移把旧裸别名加了 `default/` 前缀（保持解析模型统一）
- **解决**：这是预期行为（原 `技术规范库` → `default/技术规范库`）。若想用更口语的来源名，用 `--remove-source default` 后 `--add-source 新名字 ... --set-default-source 新名字`，并相应更新别名前缀
