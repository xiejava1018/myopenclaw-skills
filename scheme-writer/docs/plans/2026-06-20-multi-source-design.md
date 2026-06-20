# scheme-writer 多来源（多实例 / 多空间）支持设计

- **日期**：2026-06-20
- **状态**：设计已评审通过，待实现
- **作者**：brainstorming 会话产出

## 1. 背景与问题

当前 scheme-writer 只能连接**一个 WeKnora 实例**：`.env` 里只有一组 `KNOWLEDGE_BASE_URL` + `KNOWLEDGE_BASE_API_KEY`，全局单例。`kb_config.py:65-71` 枚举的 5 个全局键即是全部连接信息。

两个真实需求无法满足：

1. **多实例**：多个部门各自部署 WeKnora，需要连接多个部门的实例（不同 URL + 不同 API Key）。
2. **多空间**：同一个 WeKnora 实例下有多个**空间**，需要同时访问多个空间。

### 关键澄清：空间 = 独立租户/权限域

经确认，WeKnora 的「空间」是**独立租户/权限域**，靠 **API Key** 区分——每个空间一个 Key，Key 决定可见的空间与库。因此两种需求**坍缩成同一种结构**：

| 情况 | URL | API Key | 本质 |
|:-----|:-----|:-----|:-----|
| 同实例多空间 | 相同 | 不同（每空间一个 Key） | 两条来源，URL 一样、Key 不同 |
| 多实例多空间 | 不同 | 不同 | 两条来源，URL 和 Key 都不同 |

→ **连接的基本单位 = `(URL + API Key)`**，记为一个「来源」（source）。「实例」和「空间」都只是来源的属性，不再各自成层。

### 推论：kb_id 不再全局唯一

不同空间里 `kb-001` 可能指向完全不同的库。因此**现有的全局 `KB_ALIASES={"技术规范库":"kb-001"}` 设计在多来源下失效**——别名必须升级为「名字 → (来源, kb_id)」。

## 2. 目标与非目标

**目标**
- 支持配置多个来源（多组 URL + API Key），覆盖同实例多空间与多实例两种拓扑。
- 支持跨多来源同时检索并合并结果。
- 解决 kb_id 跨空间撞名（来源作用域别名）。
- 老用户零摩擦迁移：现有单实例自动转成单来源。

**非目标（YAGNI，本期不做）**
- 不做「部门 → 来源 → 库」三层分组体系（预留 `group` 字段，现在忽略）。
- 不引入 `--max-total`、跨来源全局重排、分数归一化。
- 不做多用户/多权限角色管理。

**规模假设**：先小后大（2-3 个来源起步，未来长到 10+）。结构设计成扁平清单，但预留分组扩展位，从 2 个长到 10+ 不用重构。

## 3. 配置 Schema

`.env` 从「单组 key」升级为「**来源清单 + 来源作用域别名**」。

### 3.1 `SOURCES`（JSON 数组，必填）

每条一个来源：

```jsonc
SOURCES=[
  {"name":"运维空间1", "url":"http://192.168.30.236/api/v1", "api_key":"sk-运维空间1"},
  {"name":"运维空间2", "url":"http://192.168.30.236/api/v1", "api_key":"sk-运维空间2"},
  {"name":"安全部",    "url":"http://10.5.20.8/api/v1",       "api_key":"sk-安全部"}
]
```

字段：
- `name`（必填、唯一）：口语化名，用户引用与别名前缀都用它。
- `url`（必填）：WeKnora API base，含 `/api/v1`。
- `api_key`（必填）：仅存 `.env`，绝不进对话/日志/SKILL.md（铁律一不变）。
- `group`（可选、**现在忽略**）：YAGNI 预留位，将来按部门分组时启用。

### 3.2 `KB_ALIASES`（JSON 对象）

键升级为**带来源前缀的限定名** `来源/库名`，值是 kb_id：

```jsonc
KB_ALIASES={
  "运维空间1/技术规范库": "kb-001",
  "安全部/漏洞库":       "kb-001"
}
```

- 键格式 `<source_name>/<friendly_name>`，`source_name` 必须存在于 SOURCES。
- kb_id 跨空间撞名被前缀天然解决。

### 3.3 默认值键

- `DEFAULT_SOURCE`（可选）：用户不指定来源时的默认源。
- `DEFAULT_RETRIEVE_KB` / `DEFAULT_UPLOAD_KB`（可选）：值改成限定名 `运维空间1/技术规范库` 或裸 `source/kb_id`。

旧 `KNOWLEDGE_BASE_URL` / `KNOWLEDGE_BASE_API_KEY` **不再直接读取**，仅供自动迁移识别。

## 4. 来源解析 & CLI 接口

所有 kb_*.py 的核心变化：**每个 kb 引用必须同时解析出 `(source, kb_id)`**——HTTP 调用需要 source 的 `(url, key)` + kb_id。新增 `--source`；`--kb` 升级为多形态引用。

### 4.1 kb 引用解析规则（`--kb` 接受逗号分隔多个）

- `来源/库名`（限定别名，首选）→ 自带 source，查 KB_ALIASES 拿 kb_id。例 `运维空间1/技术规范库`。
- `库名`（裸名）→ 在所有别名后缀里匹配；唯一命中即解析，**多个命中报歧义**（铁律三：不猜），无命中则当字面 kb_id。
- `kb_id`（字面）→ source 由 `--source` 或 `DEFAULT_SOURCE` 决定，都没有则报错。

### 4.2 source 解析优先级

`--source` 显式 > 限定别名前缀 > `DEFAULT_SOURCE` > 报错反问。

### 4.3 各脚本改动

| 脚本 | 变化 |
|:-----|:-----|
| `kb_search.py` | `--kb` 多来源逗号分隔 → 逐 `(source,kb_id)` 检索后合并（见 §5） |
| `kb_list.py` | 新增 `--source X` 列某源；`--all` 列全部源（结果带 source 标签） |
| `kb_docs.py` | `--kb` 同样多形态；按 `(source,kb_id)` 拉文档清单 |
| `kb_upload.py` | 目标必须收敛到**单一** `(source,kb_id)`——上传不跨源；歧义则报错 |

### 4.4 对话侧零负担

用户说「从运维空间1的《技术规范库》查」，Claude 直接拼 `--kb 运维空间1/技术规范库`，限定别名自带 source，无需额外 `--source`。

### 4.5 向后兼容形态

所有引用收敛到单一 source 时，输出退化为现在的单源 JSON `{kb_id, query, chunks, total}`；多源时才输出合并结构——老的单源调用方不受影响。

## 5. 跨来源检索合并语义

`--kb 运维空间1/技术规范库,安全部/漏洞库` 触发多源检索：同一 query 打到每个 `(source, kb_id)`，各自拿自己的 top_k，再合并。

- **top_k 语义**：`--top-k 8` 是**每源**各返回最多 8 条（2 源 → 最多 16 条）。不做全局预分配（不同源文档量未知）。不引入 `--max-total`（YAGNI）。
- **合并 & 排序**：每源 chunks 已按自己 score 降序；合并成扁平数组，**按 `(source, -score)` 排序**——**不跨源全局重排**，因为不同实例/空间 embedding 模型可能不同，分数不可直接比较。每条 chunk 打 `source` 标签，保留来源溯源。
- **去重**：跨源文档天然不同（不同空间），无需跨源去重；源内去重服务端已做。
- **铁律不变**：score < min_score 的 chunk 仍逐源客户端过滤丢弃，不当证据。

### 输出形态（多源时）

```jsonc
{
  "sources": ["运维空间1","安全部"],
  "query": "...",
  "chunks": [{"source":"运维空间1","kb_id":"kb-001","source_doc":"...","content":"...","score":0.82}, "..."],
  "total": 11,
  "errors": [{"source":"安全部","error":"auth","message":"..."}]
}
```

单源时退化成老结构 `{kb_id, query, chunks, total}`（无 `sources`/`errors` 字段）。

### 部分失败策略（关键决策）

3 个源里 1 个挂了（网络抖动/Key 失效），**不整体失败**——健康源结果照常返回，挂掉的源进 `errors` 数组。退出码：≥1 源成功 → 0；全失败 → 对应错误码。多源检索不因一个部门服务抖动而全军覆没。

## 6. 配置流程 & 自动迁移

init.py 从「单实例向导」升级为「**来源管理器**」。

### 6.1 新增子命令（对话内模式）

| 子命令 | 用途 |
|:-----|:-----|
| `--add-source NAME URL KEY` | 追加一个来源到 SOURCES（增量，主用） |
| `--set-sources JSON` | 整体覆写 SOURCES（批量/迁移用，类比 `--set-aliases`） |
| `--remove-source NAME` | 删一个来源 |
| `--set-default-source NAME` | 设 DEFAULT_SOURCE |
| `--list-sources` | 列所有来源（Key 脱敏）+ 各自连通状态 |
| `--set-aliases` | 别名键升级为 `来源/库名` 形态 |

旧 `--set KEY=VAL` 保留给标量键（DEFAULT_SOURCE、DEFAULT_RETRIEVE_KB 等），但 `KNOWLEDGE_BASE_URL/KEY` 移出可写白名单（仅供迁移识别）。

### 6.2 自动迁移（零摩擦承诺）

首次跑新代码时，若 `SOURCES` 缺失但检测到旧 `KNOWLEDGE_BASE_URL + KEY`：

1. 合成一条 `{"name":"default","url":<旧url>,"api_key":<旧key>}`，写入 SOURCES。
2. 设 `DEFAULT_SOURCE=default`。
3. 旧 `KB_ALIASES={"技术规范库":"kb-001"}` → **自动加前缀**重写成 `{"default/技术规范库":"kb-001"}`，迁移日志透明打印。
4. 旧 key 保留在 .env 但不再被读取（留作回滚线索）。

迁移决策：
- 第一个源命名 `default`、**不问用户**——迁移时只有单源、无歧义，名字意义要到第 2 源出现才浮现；零摩擦优先，名字以后可改。
- 别名键自动加 `default/` 前缀——这是保持解析模型**统一无特例**的唯一办法；保留裸别名靠 DEFAULT_SOURCE 兜底会埋雷（一旦 default 改名或换默认源，裸别名静默指向错误库）。重写一次性、init.py 现有 `.env.bak` 备份逻辑（`init.py:140-142`）提供安全网。

迁移后老用户零感知：单源即 default，所有行为退化到现状。

### 6.3 `--status` 语义

探测 `DEFAULT_SOURCE`（无则首个源）返回单标签 OK/NEED_INIT/...；`NEED_INIT` 现在意味「SOURCES 完全没配」。多源混合健康度用 `--list-sources` 看每源连通状态。

### 6.4 对话内配源流程（每加一个源）

问名字 → 问 URL → 问 Key（带安全前缀）→ 探测连通（`list-kbs --source X`）→ 追加 → 对该源做别名发现（列库 → 问口语化库名）。

## 7. 向后兼容

单源场景下一切退化到现状：
- `--source` 全程可选。
- 单源 kb_search 输出与今天逐字节一致。
- 迁移把老用户落在合法单源态。

老的单源调用方（SKILL.md 工作流）零改动。

## 8. 安全边界（三条铁律在多源下的延续）

- **铁律一**：N 个 Key 仍是 N 个只在 `.env` 的秘密。`--add-source`/`--show`/`--list-sources` 对每个 Key 脱敏（复用现有 `_mask_key`）；SOURCES 整体在 `.env`，`.gitignore` 已忽略；输出里的 `source` 字段是**名字不是 Key**，安全可显示。
- **铁律二**：上传仍需显式意图，且必须收敛到单一源。
- **铁律三**：裸名/源歧义一律反问，不猜。

## 9. YAGNI 扩展位

- `group` 字段已留、现在忽略。
- 不引入 `--max-total`、跨源全局重排、分数归一化——等真有需求再加（届时 SOURCES 扁平结构也能向上加一层分组，不破坏现有消费者）。

## 10. 测试策略

扩展现有 `tests/` pytest 套件，沿用 monkeypatch + 子进程风格。

- `clean_env` fixture 增删 `SOURCES`/`DEFAULT_SOURCE` 两个键。
- 新增解析用例：限定别名 / 裸名（唯一·歧义）/ 字面 kb_id / 多源逗号。
- 回归：单源输出 JSON shape == 现状（防退化）。
- 多源合并：每源 top_k、source 打标、部分失败（1/3 down → 健康源返回 + errors + exit 0）。
- 迁移：旧 `.env` → SOURCES + default + 别名加前缀 + `.env.bak` 生成；**幂等**（跑两次不重复迁移）。
- 安全断言：`--show`/`--list-sources` stdout 不含任何明文 Key。

## 11. 落地步骤（实现阶段参考）

1. `kb_config.py`：新增 SOURCES / DEFAULT_SOURCE 读写与解析；保留旧 key 仅供迁移读取。
2. 迁移逻辑：在 `kb_config` 或 `init.py` 实现「检测旧 key → 合成 default 源 + 别名加前缀」，幂等。
3. 解析层：实现 kb 引用与 source 解析（§4.1/4.2），抽成共享函数供各脚本复用。
4. 各脚本改造：`kb_search`（多源合并 + 部分失败）、`kb_list`（`--source`/`--all`）、`kb_docs`、`kb_upload`（单源收敛）。
5. init.py 新子命令（§6.1）+ `--status`/`--show` 适配。
6. SKILL.md 更新（多来源工作流、别名表形态、新 CLI 速查）。
7. 测试套件补齐（§10）。

> 实现遵循仓库优先原则：改动落在 `myopenclaw-skills/scheme-writer/` 仓库源，完成后再同步到 `~/.claude/skills/scheme-writer/`。
