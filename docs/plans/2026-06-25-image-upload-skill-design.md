# image-upload Skill 设计文档

> 日期：2026-06-25
> 状态：已确认设计，待实现
> 仓库：`myopenclaw-skills`（每个 skill 为顶层目录）

---

## 1. 背景与动机

博客（Hugo，托管于 GitHub Pages + EdgeOne）的图片当前靠 AI 每次手动传图：用七牛云 SDK 上传，配置散落在 PicGo 的 `data.json` 里。痛点：

- 每篇文章的图片上传是重复手工劳动，没有固化成可复用能力；
- PicGo 是正在被淘汰的 GUI，不希望继续依赖它的界面；
- 博客文章里的图片是 Obsidian 本地引用 `![[x.png]]`，发布到 Hugo 前需逐一改成图床 URL，这一步纯靠人/AI 临场处理，易错。

**目标**：把"传图到图床 + 改写博客图片链接"固化成一个 Claude Code skill，一条指令完成，且**不依赖 PicGo 运行时**。

## 2. 目标与非目标

**目标**

- 支持两个图床后端：**七牛云**（主，中国可达）与 **GitHub**（备，免费/可版本回溯）。
- 提供可组合的**上传原语**（文件 → URL）。
- 提供面向博客的**端到端命令**（扫描文章 → 上传 → 原地改写链接）。
- 幂等：重跑不重复上传，可回溯。
- 配置完全自包含，PicGo 仅作首次引导的便利来源。

**非目标（YAGNI）**

- 不做图床管理 UI。
- 不替代 PicGo 做配置编辑（七牛密钥改在哪都行，skill 只读自己的 `.env`）。
- 不做图片压缩/格式转换（保留原文件，如需要可后续加 `--optimize`）。
- 不做多用户/鉴权（本地个人 skill）。

## 3. 架构：Provider 抽象

原语接口固定为"上传本地文件 → 返回图床 URL"，下挂两个后端实现。博客命令对后端无感。

```
image-upload skill
├── upload <图片> [--backend qiniu|github]   # 原语，返回 URL
└── migrate <post.md> [--backend ...]        # 批量上传 + 改写链接
        │
        ├── QiniuUploader   (七牛 SDK)
        └── GithubUploader  (GitHub Contents API)
```

**为什么是这个架构**：用户选择了"C：原语 + 博客命令"——原语可复用于非博客场景，博客命令在其上薄封一层。后端抽象让"加 GitHub"只多一个 provider 文件，博客命令零改动。

## 4. 方案选型（推荐 + 已否决）

| 方案 | 结论 | 理由 |
|------|------|------|
| **Python skill 直接调七牛 SDK + GitHub API** | ✅ 采用 | 复刻本仓 `webdav` skill 形态；七牛官方 Python SDK 几十行；GitHub Contents API 一个 `requests.put` |
| 调 PicGo CLI | ❌ 否决 | 本机未装 `picgo` 命令行（仅 GUI 残留）；用户明确要摆脱 PicGo |
| 嵌 picgo-core（npm） | ❌ 否决 | 比直接调官方 SDK 多一层 Node 运行时，无收益 |

## 5. 命令接口

```bash
# 原语：上传一张或多张，返回 URL
image-upload upload <file...> [--backend qiniu|github] [--json]

# 博客命令：扫描文章里所有本地图片引用，上传 + 原地改写为图床 URL
image-upload migrate <post.md> [--backend qiniu|github] [--dry-run]

# 一次性引导：从 PicGo data.json 导入七牛配置到 .env
image-upload init

# 查看 manifest（本地文件↔图床 URL 账本）
image-upload list
```

**`upload` 行为**：每张图打印 `本地路径 -> URL`；`--json` 输出结构化 JSON（供 AI/脚本组合）；写 manifest。

**`migrate` 行为**：
1. 解析文章里所有**指向本地文件**的图片引用；
2. 跳过已是 URL 的链接（`http…`）；
3. 逐张经所选后端上传；
4. **原地改写**该行为 `![alt](URL)`，保留 alt/title；
5. `--dry-run`：只打印将上传/改写的清单，不传不改。

**默认后端**：读 `.env` 的 `DEFAULT_BACKEND`；`--backend` 覆盖。

**改写安全**：Hugo 仓库有 git，直接改由 git 兜底；非 git 场景写 `.bak`。

## 6. 配置策略（自包含，无 PicGo 运行时依赖）

> **关键决策**：skill 必须自洽。PicGo 仅作首次引导的便利来源，**不是运行时依赖**。

所有参数存在 skill 自己的 `.env`（`.gitignore` 排除，`.env.example` 留键名占位）：

```bash
DEFAULT_BACKEND=qiniu

# —— 七牛（必填）——
QINIU_ACCESS_KEY=
QINIU_SECRET_KEY=
QINIU_BUCKET=
QINIU_DOMAIN=https://image2.ishareread.com
QINIU_AREA=z0                    # z0华东 z1华北 z2华南 na0北美 as0东南亚
QINIU_PATH=blog

# —— GitHub（用 github 后端时必填）——
GH_TOKEN=ghp_xxx                 # classic PAT(repo) 或 fine-grained(contents:write)
GH_OWNER=xiejava1018
GH_REPO=image-bed
GH_BRANCH=main
GH_PATH=blog
GH_DOMAIN=                        # 空=raw.githubusercontent.com；填则用自定义域名
```

**`init` 引导**：检测到 `~/Library/Application Support/picgo/data.json` → 读取 `picBed.qiniu`（字段 `accessKey/secretKey/bucket/url/area/path`）→ 写入 `.env` 七牛段。一次性导入，导入完 PicGo 可卸载。

## 7. GitHub 后端访问域名

推荐 **`raw.githubusercontent.com`（默认）+ 可配置字段**：

- 博客默认后端是七牛（中国可达），GitHub 是"免费/版本回溯/非中国读者"的备用后端，不背中国速度 KPI；
- raw 是 GitHub 源真相，零额外基建，境外永远可达；
- jsDelivr 2021 底国内 ICP 被撤后间歇性挂，不作主力；
- 将来需要 GitHub 图也跑中国流量时，把 `GH_DOMAIN` 指向 Cloudflare Worker/自有域名即可，**零代码改动**。

## 8. 图片 key（图床路径）命名

| 命令 | key 方案 | 示例 |
|------|---------|------|
| `upload`（无文章上下文） | `{前缀}/{YYYYMMDD}/{原文件名}` | `blog/20260625/foo.png` |
| `migrate <post.md>` | `{前缀}/{post-slug}/{原文件名}` | `blog/scheme-writer-guide/architecture.png` |

- `post-slug` = 文章文件名去扩展名，让一篇文章的图聚在一个目录，便于整组管理/删除。
- 保留原文件名（有语义，与 PicGo 一致）。
- 前缀 = 七牛 `QINIU_PATH` / GitHub `GH_PATH`，默认 `blog`。
- URL = `{domain}/{key}`。

## 9. 链接改写规则

| 原文 | 改写为 | 说明 |
|------|--------|------|
| `![[x.png]]` | `![](URL)` | Obsidian 无 alt |
| `![[x.png\|说明]]` | `![说明](URL)` | 保留 alt |
| `![[x.png\|500]]` | `![](URL)` | 纯数字 resize 丢弃（Hugo 不认） |
| `![alt](./p/x.png)` | `![alt](URL)` | 标准 md 相对路径 |
| `![alt](p/x.png "标题")` | `![alt](URL "标题")` | 保留 alt + title |
| `![](http://…)` | **不动** | 已是 URL，跳过 |
| `![[某笔记]]` | **不动** | 无图片扩展名 → 视为笔记双链 |

- 图片扩展名：`.png .jpg .jpeg .gif .webp .svg .bmp .avif`。
- **本地路径解析**：`![[x.png]]` 按文件名查 ①文章同目录 ②`assets/` ③`assets/blog/` ④全 vault glob 兜底；标准 md 相对路径相对文章目录解析。找不到则警告并跳过该链接，不中断整体。

## 10. 幂等 manifest

`manifest.json`，按**文件内容 sha256** 索引，值按后端分桶：

```json
{
  "<sha256>": {
    "local": "/abs/path/architecture.png",
    "qiniu":  { "key": "blog/.../architecture.png", "url": "https://image2.ishareread.com/..." },
    "github": { "key": "blog/.../architecture.png", "url": "https://raw.../..." }
  }
}
```

- **按内容哈希**：同一张图（多处引用）只传一次，省七牛空间；图被编辑（内容变）则视为新文件重传。
- **migrate 流程**：找到本地图 → 算哈希 → manifest 有且含所请求后端 URL → 复用不重传、只改链接；否则上传、写 manifest、改链接。
- **可恢复**：`list` 子命令随时查账本。
- **可续跑**：每次上传成功后才写 manifest，中途失败已传不丢，重跑自动跳过。
- **后端切换友好**：同一文件可同时存七牛和 GitHub 两条 URL，换 `--backend` 不重传。

## 11. 目录结构

```
image-upload/
├── SKILL.md                # name/description 触发词 + 用法
├── README.md
├── main.py                 # CLI 入口：argparse + 派发 upload/migrate/init/list
├── config.py               # 加载 .env + 七牛 area 映射
├── rewriter.py             # 解析+改写图片链接（纯逻辑，可单测）
├── manifest.py             # manifest 哈希查表/持久化（纯逻辑，可单测）
├── providers/
│   ├── __init__.py         # Uploader 抽象基类 + 注册表
│   ├── qiniu.py            # QiniuUploader（qiniu 官方 SDK）
│   └── github.py           # GithubUploader（requests + Contents API）
├── requirements.txt        # qiniu, requests, python-dotenv
├── .env / .env.example / .gitignore
└── tests/
    ├── test_rewriter.py
    ├── test_manifest.py
    └── test_providers.py   # mock SDK，不发真实请求
```

外加：根 `README.md`「技能一览」表 + 「仓库结构」块登记 `image-upload`。

## 12. 测试与验证

**测试（80% + TDD）**

- 纯逻辑单测（无网络，覆盖大头）：`rewriter`（每种链接形态改写、URL/笔记链接跳过、路径解析兜底）、`manifest`（内容哈希去重、多后端分桶复用、持久化）、key 命名（日期桶/post-slug 桶）。
- provider 测试：mock 七牛 `put_file` 与 GitHub `requests.put`，断言 key/token/请求体正确，不发真实流量。
- 门控集成测试：`RUN_INTEGRATION=1` + 真实密钥时才跑一次真上传，正常 CI 跳过。

**端到端验证清单**

1. `init` → `.env` 从 PicGo 自动填好七牛段；
2. `upload assets/blog/foo.png --json` → 真实 URL，浏览器能打开图；
3. `migrate notes/blog/draft.md --dry-run` → 改写 diff 符合预期；
4. `migrate notes/blog/draft.md` → 链接变七牛 URL；**立即再跑** → manifest 命中、零上传、文件不变；
5. `migrate notes/blog/draft.md --backend github` → 同文件加 github 桶，不重传七牛那份。

## 13. 关键决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| skill 范围 | C：原语 + 博客命令 | 原语可复用，博客命令薄封其上 |
| 后端 | 七牛（主）+ GitHub（备） | 七牛中国稳；GitHub 免费可回溯 |
| GitHub 访问域名 | raw（默认）+ 可配置 | 七牛担中国流量；raw 零基建；将来换 CF 域名零代码改 |
| 配置依赖 | 完全自包含 `.env`，PicGo 仅首次引导 | skill 必须自洽，不因 PicGo 缺失而瘫 |
| 幂等键 | 文件内容 sha256 | 真去重 + 编辑自动重传 |
| 放置 | 顶层 `image-upload/` 目录 | 遵循本仓约定（无 `skills/` 父目录） |

## 14. 后续（实现阶段）

- 用 `superpowers:writing-plans` 拆分实现步骤（建议 TDD 顺序：rewriter → manifest → providers → CLI → init）。
- 实现后同步到 `~/.claude/skills/`（与本仓其他 skill 一致）。
- 可选增强（YAGNI，按需）：`--optimize` 图片压缩、Hugo figure shortcode 转换、批量 `migrate` 整个目录。
