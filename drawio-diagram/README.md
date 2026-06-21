# drawio-diagram

一个 Claude Code 技能，把自然语言描述变成**专业、可编辑**的技术图——架构图、流程图、时序图、ER 图、状态机。引擎自动排版并保证节点不重叠、不越界、对齐网格、文字不溢出，所以产出的图永远干净、一致、可直接放进文档或交付客户。同一份输入永远产出同一张图（确定性）。

每次产出两份文件：`.drawio`（可在 draw.io 桌面/网页端继续编辑的源文件，始终生成）+ 一张渲染图片（默认 PNG，也可选 SVG/PDF/JPG）。

## 要求

- **draw.io CLI**（用于渲染图片）— macOS：`brew install --cask drawio`；Windows/Linux：从 https://github.com/jgraph/drawio-desktop/releases 下载。
- **Python 3**（运行引擎）。无其他运行时依赖。
- 验证是否就绪：`python scripts/cli.py check`。

## 快速开始

1. 写一个 `diagram.json`（只描述语义，不写坐标）。最简单的方式是复制 `templates/` 下对应类型的骨架再编辑。
2. 构建：
   ```bash
   python scripts/cli.py build diagram.json -o out
   ```
3. 得到 `out.drawio` + `out.png`。

如果校验失败，修 JSON 重跑——不要手写 `.drawio`。

## 5 种图

| 类型 | 回答的问题 | 必填字段 |
|------|-----------|----------|
| `architecture` | 组件有哪些、按层怎么连？ | `layers`/`nodes`/`edges` |
| `flowchart` | 一步步的流程/分支逻辑？ | `nodes`/`edges` |
| `sequence` | 谁按什么顺序跟谁通信？ | `participants`/`messages` |
| `er` | 有哪些实体、数据怎么关联？ | `entities`/`relationships` |
| `state` | 一个东西有哪些状态、怎么迁移？ | `states`/`transitions`/`initial` |

输入契约详见 [`references/json-schema.md`](references/json-schema.md)，选型与字段速查见 [`references/diagram-types.md`](references/diagram-types.md)。

## 5 种风格

`diagram.style` 驱动调色板、字体、阴影、圆角。默认 `enterprise`。详见 [`references/styles.md`](references/styles.md)。

| 风格 | 观感 | 适合 |
|------|------|------|
| `enterprise` | 中性、可读、柔和分色 | 默认，客户交付物 |
| `flat` | 同 enterprise 调色、更重描边、更扁平 | 幻灯片/海报 |
| `notion` | 单色灰、直角 | Notion/wiki 嵌入 |
| `claude` | 暖米底色、柔和阴影 | 报告、编辑风排版 |
| `openai` | 严格黑底白字 | 打印、高对比/无障碍 |

## 云图标

架构图/流程图节点可加 `provider` + `service` 渲染真实 AWS/Azure/GCP 图标：

```json
{"id": "store", "label": "商品图片", "kind": "database", "provider": "aws", "service": "s3"}
```

完整目录见 [`references/drawio-shapes.md`](references/drawio-shapes.md)。逻辑图用通用 `kind` 形状即可；部署图、云迁移图用云图标更直观。

## 构建后怎么继续编辑

生成的 `.drawio` 是标准 draw.io 源文件。用以下任一方式打开：
- **draw.io 桌面端**（`brew install --cask drawio`）
- **draw.io 网页端**：https://app.diagrams.net （File → Open）

打开后可拖拽、改色、加标注，再导出任意格式。改了语义需求时，建议回到 `diagram.json` 改完重跑，而不是在 `.drawio` 上手改——前者保留确定性。

## 示例

`examples/` 下每种图一个端到端示例，各含 `.json`（输入）+ `.drawio`（源文件）+ `.png`（渲染图）：

| 示例 | 类型 | 演示什么 |
|------|------|----------|
| `rag-architecture` | architecture | RAG 系统多层架构，含 LLM/向量库/缓存；多种 `flow` 触发自动图例 |
| `order-flowchart` | flowchart | 订单处理流程，含决策分支（库存/支付）与多汇合点 |
| `checkout-sequence` | sequence | 结算时序，含参与者生命线 + 返回消息（虚线） |
| `ecommerce-er` | er | 电商数据模型，多实体 + 1:N / N:M 关系 + PK/FK |
| `order-state` | state | 订单状态机，含初始态、终态、自环迁移、守卫条件 |

## 为什么它看起来专业

引擎在每个求解器后自动断言 **5 条不变量**——这是确定性、不靠 LLM 拍脑袋的全部原因：

| 不变量 | 含义 |
|--------|------|
| 不重叠 | 任意两节点之间留有最小间距 |
| 不越界 | 所有节点都在画布内 |
| 对齐网格 | 坐标吸附到 20px 网格 |
| 宽度适配文字 | 节点宽度永远容得下标签 |
| 确定性 | 同一输入永远产出同一张图 |

## 运行测试

```bash
cd drawio-diagram
python -m pytest tests/ -q
```

全绿即表示引擎、校验、渲染、导出、CLI 全链路正常。
