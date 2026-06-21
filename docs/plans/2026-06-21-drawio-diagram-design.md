# drawio-diagram 技能设计文档

> 日期：2026-06-21
> 状态：设计已确认，待实现
> 关联：替换将被卸载的 `~/.claude/skills/draw-diagram`（手搓 SVG，质感不专业）

## 背景与目标

**痛点：** 文档里画架构图时，Claude 出的图不专业、不好看。现有 `draw-diagram` 技能用 LLM 即兴算坐标 + 手搓 SVG，节点重叠/对不齐/间距漂移，质感难以达到企业级。

**目标：** 新建 `drawio-diagram` 技能，调用本机 **draw.io CLI**（与桌面端同一套渲染引擎）出图，拿到 draw.io 的专业质感、阴影、AWS/Azure/GCP 云图标库，并产出**可编辑 `.drawio` 源文件**。v1 支持架构图、流程图、时序图、ER 图、状态机 5 种高频图，默认渲染 PNG，始终保留 `.drawio` 源。

**核心洞察（病灶定位）：** draw-diagram 的"不专业"根因是**布局质量押在 LLM 即兴坐标算术上**。换渲染器（SVG→draw.io）治不了这个病。真正的解法是把布局下沉到**确定性算法 + 可测不变量**层，再叠加 draw.io 渲染质感——专业度变成结构性的，不是运气。

## 已验证的技术前提

- 本机已装 draw.io CLI：`/opt/homebrew/bin/drawio`，v30.0.2，另有 `/Applications/draw.io.app`。
- **无头导出已验证可行**：最小 `.drawio` → `drawio -x -f png -o out.png in.drawio` 成功生成有效 PNG（exit 0），不弹窗、不需要显示器。整条链路命门通过。
- CLI 支持 png/svg/pdf/jpg/html/xml，支持 `--scale`/`--width`/`--border`/`--transparent`/`--crop`/`--svg-theme`。
- Node v24 / npm / npx 在场（备用）。

## 架构与数据流（方案 C：混合布局）

单向流水线，职责严格分层：

```
用户自然语言描述
   │  ① [Claude] 分类图类型 + 提取语义结构 + 给布局提示
   ▼
diagram.json   ← 节点/边/类型/样式，无任何坐标
   │  ② [scripts/layout.py] 确定性布局引擎，按 type 算坐标
   ▼
layout.json    ← 补全 x/y/w/h/路由
   │  ③ [scripts/render_drawio.py] 翻译成 mxGraph XML
   ▼
xxx.drawio     ← 可编辑源文件（始终保留）
   │  ④ [drawio CLI] 无头导出
   ▼
xxx.png（默认）/ .svg / .pdf
```

**职责铁律：**
- Claude 只做"理解 + 结构化"——读描述、定图类型、抽节点/边、给层级/排序提示。**绝不写 x/y。**
- 布局引擎是确定性纯函数：同输入同输出，可单测、可复现、可调参。
- draw.io CLI 只在最后渲染，输入是干净的 `.drawio`，不参与布局。

## 技能目录结构

```
drawio-diagram/
├── SKILL.md                 # frontmatter(触发词) + 工作流
├── README.md
├── scripts/
│   ├── cli.py               # 统一入口：build / check 子命令
│   ├── schema.py            # 校验 diagram.json（fail-fast）
│   ├── layout.py            # ★ 确定性布局引擎（5 个求解器）
│   ├── styles.py            # 5 样式 → draw.io cell style 映射
│   ├── render_drawio.py     # layout.json → .drawio (mxGraph XML)
│   ├── export.py            # 调 drawio CLI 导出 + 依赖检测
│   └── requirements.txt     # 仅 pytest（运行时零依赖）
├── references/
│   ├── json-schema.md       # diagram.json 字段说明（Claude 输入契约）
│   ├── diagram-types.md     # 5 种图语义结构 + 布局提示规范
│   ├── drawio-shapes.md     # 语义 kind → draw.io 形状/云图标映射
│   └── styles.md            # 5 样式预览与适用场景
├── templates/               # 5 种图 JSON 起手骨架
│   ├── architecture.json  flowchart.json  sequence.json
│   ├── er-diagram.json    state-machine.json
├── examples/                # 真实示例产物（.drawio + .png）
├── tests/                   # pytest（见测试策略）
├── .gitignore               # 忽略 output/、__pycache__/、*.pyc
└──（无 .env）               # draw.io 本地工具，无密钥
```

无 `.env`、运行时零第三方依赖，降低安装摩擦。

## JSON 中间契约（按图类型的 schema）

不用通用 nodes/edges，而是每类图一套 schema（时序=参与者+消息、ER=实体+关系+基数、状态机=状态+迁移+守卫）。Claude 照 `references/json-schema.md` 填，`schema.py` fail-fast 校验。JSON 里**永远没有坐标**，只有语义 + 布局提示。

- **架构图** `architecture`：`layers[]`（有序分层，带 label）+ `nodes[]`（`kind` 语义类型）+ `edges[]`（`flow` 流向）。布局提示来源 = layers 顺序。
- **流程图** `flowchart`：`nodes[]`（`kind`: terminal/process/decision/io）+ `edges[]`（`label` 表是/否）。拓扑自动分层。
- **时序图** `sequence`：`participants[]` + `messages[]`（`dashed`=返回/异步）+ 可选 `frames[]`（loop/alt 覆盖区间）。
- **ER 图** `er`：`entities[]`（带 `attributes[]`，`pk`/`fk`）+ `relationships[]`（`card:"1:N"`）。
- **状态机** `state`：`states[]` + `transitions[]`（`label`/`guard`）+ `initial` + `final[]`。

`kind` 是语义类型（database/vectorstore/client/service…），由 `references/drawio-shapes.md` 映射到 draw.io 形状/云图标——Claude 不碰 style 字符串。

## 布局引擎 5 个求解器 + 可测不变量

`layout.py` 暴露 `layout(diagram) -> geometry`，按 `type` 分发：

| 图类型 | 算法 | 布局提示来源 |
|--------|------|------------|
| 架构图 | 分层带状：每层一条带，带内居中均排，边走带间正交通道 | `layers[]` 顺序 |
| 流程图 | rank 分层 + barycenter 交叉最小化；决策"否"侧出 | 拓扑自动 |
| 时序图 | 生命线 + 时间槽：参与者等距列，消息自上而下各占一槽 | `messages[]` 顺序 |
| ER 图 | 实体网格 2~3 列自适应，关系线正交相连 | `entities[]` 顺序 |
| 状态机 | BFS 分层：初态伪节点最左、终态伪节点最右 | `initial`/`transitions` |

**共享间距常量**：`GUTTER_X=80`、`GUTTER_Y=120`、`MARGIN=60`、`NODE_MIN_W=140`、`SNAP=20`。

**可测不变量（`tests/test_layout.py` 强制，把"专业"变成可断言指标）：**
1. 确定性：同输入两次布局坐标完全一致。
2. 无重叠：任意两节点边界间距 ≥ 24px。
3. 不出界：所有节点/容器在 canvas 内，溢出则 canvas 自动扩大。
4. 宽度随文字：`width ≥ max(NODE_MIN_W, len(label)*7 + 32)`。
5. 网格对齐：所有坐标 snap 到 `SNAP` 像素。

## 样式映射 + 形状/云图标库

5 样式沿用 draw-diagram 命名，重新映射到 draw.io cell style：

| 样式 | 画布 | 节点质感 | 阴影 | 适用 |
|------|------|---------|------|------|
| `enterprise`（默认） | 纯白 | 中性灰细描边圆角 | 关 | 商务/打印 |
| `flat` | 白 | 扁平彩色块 | 关 | 博客/文档 |
| `notion` | 白 | 极简灰阶 | 关 | Notion |
| `claude` | 暖米 `#f8f6f3` | 暖色调 | 开 | Anthropic 风 |
| `openai` | 纯白 | 黑白高对比 | 关 | OpenAI 风 |

每个样式 = 色卡 + 渲染开关 + 按 `kind` 的调色板。语义 `kind` → draw.io 形状：`database`/`cache`→`cylinder3`、`service`/`api`→`hexagon`、`decision`→`rhombus`、`terminal`→胶囊、`actor`→`shape=actor`、`cloud`→`shape=cloud` 等。

**专业感杀手锏——云图标库：** 节点可选 `provider`+`service` 字段直接拉 draw.io 内置真实云图标（`shape=mxgraph.aws4.amazon_s3` 等）。v1 收录 AWS/Azure/GCP 高频 ~30 个服务目录供 Claude 选用。

边的 `flow` → draw.io 边样式（继承 draw-diagram 箭头语义）：`data`→蓝粗实线、`control`→橙、`async`→灰虚、`memory_write`→绿虚，统一 `edgeStyle=orthogonalEdgeStyle`。

## SKILL.md 工作流

触发词：`画图/画架构图/流程图/时序图/ER 图/状态机/draw.io/出图/生成图/visualize`。

1. **首跑自检**：`cli.py check` 确认 draw.io CLI；缺失报 `brew install --cask drawio`。
2. **分类 + 抽结构**：定图类型 + 抽语义要素。**Claude 不算坐标。**
3. **填 `diagram.json`**：照 schema + 模板填语义 JSON，可给布局提示，**绝不写 x/y**。
4. **构建**：`python scripts/cli.py build diagram.json -o out` → 校验→布局→`.drawio`→PNG。校验失败 fail-fast 报字段错误，改 JSON 重跑。
5. **可视自检**：Claude 读回 `out.png` 复查（重叠/溢出/遮挡）；有问题回第 3 步调语义输入，确定性重跑。
6. **交付**：报告 `.drawio`（源，始终给）+ `.png` 路径，提示可在 draw.io 应用里继续微调。

**与 draw-diagram 工作流的关键差异（优势）：** 无"Claude 规划坐标"步（病灶根治）；不重建浏览器拖拽编辑器（`.drawio` 本身是行业标准可编辑源，用户直接在 draw.io 应用里拖更稳）；迭代闭环靠确定性。

**与 scheme-writer 衔接：** scheme-writer 需要架构图时按"调用 drawio-diagram 技能"指引触发，v1 保持解耦、不硬编码集成。

## 依赖、错误处理、测试

**依赖：** Python 3 标准库 + `drawio` CLI（v30+，已验证）。无 `.env`、无密钥、运行时零第三方包；开发仅 `pytest`。

**错误处理（fail-fast）：** CLI 缺失→安装指引；schema 失败→指出字段+期望、退出码非 0；layout 不变量破坏→内部 assert，放不下则自动扩 canvas，仍违反则抛异常带详情；drawio 导出失败→捕获 stderr 原样上抛。

**测试（≥80%，纯 Python 不依赖 draw.io）：**
- `test_schema.py`：5 类图合法/非法 fixture。
- `test_layout.py`：5 条不变量在每类 fixture 上全断言。
- `test_render.py`：`.drawio` 合法 XML、可解析。
- `test_styles.py`：5 样式→期望 style 串。
- `test_export.py`：mock `subprocess` 验证命令拼接；CLI 在场时跑一次真实导出集成测试。
- `test_cli.py`：`build` 端到端小 fixture。

## 交付计划（分阶段，每阶段可验证）

0. 脚手架 + `cli.py check` + `schema.py` + `references/json-schema.md`
1. **架构图全链路打通**（flagship）+ 1 个真实示例，验证流水线
2. 补齐流程图/时序图/ER/状态机 4 个求解器
3. 5 样式打磨 + 云图标目录（AWS/Azure/GCP 高频 ~30 个）
4. 测试 + `examples/` + README
5. 软链到 `~/.claude/skills/`、卸载 `draw-diagram`

## 关键决策记录

- **布局策略选 C（混合）**：Claude 给语义结构 + 布局提示，确定性 Python 引擎算坐标。理由：从根上修掉 LLM 坐标漂移。
- **首发范围 5 种图**：架构/流程/时序/ER/状态机（YAGNI，先打磨高频）。
- **默认输出 PNG，始终保留 `.drawio` 源**。
- **无 `.env`、零运行时依赖**：draw.io 是本地工具，省配置层。
- **不重建浏览器编辑器**：`.drawio` 源即行业标准可编辑资产。
