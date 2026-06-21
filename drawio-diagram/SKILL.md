---
name: drawio-diagram
description: 生成专业 draw.io 架构图/流程图/时序图/ER图/状态机，输出可编辑 .drawio 源文件 + PNG/SVG/PDF。当用户需要"画图"、"画架构图"、"流程图"、"时序图"、"ER图"、"状态机"、"draw.io"、"出图"、"生成图"、"可视化"、"visualize"、"diagram"、"architecture diagram"或想在文档里插入专业技术图时使用此技能。
version: 1.0.0
---

# drawio-diagram

把一段自然语言描述变成一张**专业、可编辑**的技术图。覆盖 5 种图：架构图、流程图、时序图、ER 图、状态机。引擎自动排版并保证不重叠/不越界/对齐网格/文字不溢出——**你只负责语义，几何交给引擎**。

输出永远是两份：`.drawio`（可在 draw.io 桌面/网页端继续编辑的源文件）+ 渲染图片（默认 PNG）。同一份输入永远产出同一张图（确定性）。

## 6 步工作流

### 1. 首跑自检
```bash
python scripts/cli.py check
```
若 `available: false`，告诉用户安装 draw.io CLI：macOS `brew install --cask drawio`，或从 https://github.com/jgraph/drawio-desktop/releases 下载。Python 3 即可，无其他运行时依赖。

### 2. 分类 + 抽结构
先判断属于哪一种图（见下方"何时用哪种图"），再从用户描述里抽出**语义元素**：节点/边、参与者/消息、实体/属性/关系、状态/迁移。

**这一步由你完成理解。但你绝不计算坐标——所有 x/y/width/height 都由布局引擎拥有。**

### 3. 填 diagram.json
- 对照 [`references/json-schema.md`](references/json-schema.md)（权威输入契约，含逐字段校验表）。
- **复制对应的 `templates/<type>.json` 骨架**，在它上面编辑，而不是从零写。
- 只填语义字段。**严禁** `x/y/width/height/geometry/position`——schema 会直接拒绝。
- 选一个 `style`（默认 `enterprise`，5 种风格见 [`references/styles.md`](references/styles.md)）。
- 用 `kind` 标语义形状（见 [`references/drawio-shapes.md`](references/drawio-shapes.md)）；架构/流程图节点如需真实云图标，加 `provider`+`service`。

### 4. 构建
```bash
python scripts/cli.py build diagram.json -o out
```
产出 `out.drawio`（始终生成，可编辑源文件）+ `out.png`。若 schema 校验失败，**修 JSON 重跑**——绝不手写 `.drawio`。

### 5. 可视自检
把生成的 PNG 读回来，检查是否有重叠/溢出/裁切。若有问题，调整语义 JSON 或布局提示后重跑（确定性，改对了就会变好）。迭代到干净为止。

### 6. 交付
报告 `.drawio`（始终）+ `.png` 路径。告诉用户 `.drawio` 可以在 draw.io 桌面/网页端打开继续编辑。

## 关键纪律（不可违反）

1. **绝不计算坐标**——引擎拥有所有几何。你只描述"是什么/连什么"，不描述"画在哪"。
2. **绝不手写 `.drawio` XML**——永远走 `cli.py build`。它是 schema→布局→渲染→不变量校验的完整管道。
3. **永远用语义 JSON**——`kind` 决定形状，`flow` 决定连线颜色，`style` 决定整体观感。坐标不属于语义。
4. **校验失败就修 JSON 重跑**——不要在 `.drawio` 输出上手贴补丁掩盖 schema 错误。

**5 条不变量保证**（引擎在每个求解器后自动断言）：

| 不变量 | 含义 |
|--------|------|
| 不重叠 | 任意两个节点之间留有最小间距 |
| 不越界 | 所有节点都在画布内 |
| 对齐网格 | 坐标吸附到 20px 网格，观感整齐 |
| 宽度适配文字 | 节点宽度永远容得下标签文字 |
| 确定性 | 同一输入永远产出同一张图 |

这 5 条就是"为什么它看起来专业"的全部原因——它不是 LLM 拍脑袋画出来的。

## 何时用哪种图

按"这张图回答什么问题"来选。详见 [`references/diagram-types.md`](references/diagram-types.md)。

| 问题 | 类型 | 关键字段 |
|------|------|----------|
| 组件有哪些、按层怎么连？ | `architecture` | `layers`/`nodes`/`edges` |
| 一步步的流程/分支逻辑？ | `flowchart` | `nodes`/`edges` |
| 谁按什么顺序跟谁通信？ | `sequence` | `participants`/`messages` |
| 有哪些实体、数据怎么关联？ | `er` | `entities`/`relationships` |
| 一个东西有哪些状态、怎么迁移？ | `state` | `states`/`transitions`/`initial` |

## 云图标

架构图/流程图节点可加 `provider`+`service` 渲染真实云厂商图标（AWS/Azure/GCP）。完整目录见 [`references/drawio-shapes.md`](references/drawio-shapes.md)。

```json
{"id": "store", "label": "商品图片", "kind": "database", "provider": "aws", "service": "s3"}
```

逻辑/概念图用通用 `kind` 形状即可；部署图、云迁移图用云图标更直观。一张图内保持一致。

## 参考文档（按需深入）

- [`references/json-schema.md`](references/json-schema.md) — 权威输入契约 + 逐字段校验表
- [`references/diagram-types.md`](references/diagram-types.md) — 5 种图的选型与字段速查
- [`references/drawio-shapes.md`](references/drawio-shapes.md) — `kind`→形状映射 + 云图标目录
- [`references/styles.md`](references/styles.md) — 5 种风格调色板/观感对照
- [`examples/`](examples/) — 5 个端到端示例（每种图一个）
- [`templates/`](templates/) — 5 个最小骨架，复制即改
