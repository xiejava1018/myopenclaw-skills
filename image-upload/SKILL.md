---
name: image-upload
description: "博客图片上传到图床（七牛云 / GitHub）并改写文章图片链接。支持单张上传原语（文件→URL）和扫描整篇文章批量迁移改写（Obsidian ![[图]] → 图床 URL），内容哈希去重、多后端可切换、可回溯。当用户需要'上传图片'、'传图'、'图床'、'七牛上传'、'上传到图床'、'博客图片迁移'、'改写图片链接'、'图片传到GitHub'、'发布博客前传图'时使用。"
---

# 图床上传技能 image-upload

把博客图片上传到图床（七牛云主、GitHub 备），并自动把文章里的 Obsidian 本地图片引用改写为图床 URL。配置完全自包含（`.env`），不依赖 PicGo 运行时。

## 两个核心命令

```bash
# 原语：上传一张或多张图，返回 URL
python3 main.py upload <图片...> [--backend qiniu|github] [--json]

# 博客命令：扫描文章里所有本地图片引用，上传 + 原地改写为图床 URL
python3 main.py migrate <文章.md> [--backend qiniu|github] [--dry-run] [--vault-root <vault>]
```

辅助：

```bash
python3 main.py init     # 从 PicGo data.json 一次性导入七牛配置到 .env
python3 main.py list     # 查看 manifest（本地文件↔图床 URL 账本）
```

## 安装

```bash
cd image-upload
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # 含测试
# 或只装运行时：.venv/bin/pip install -r requirements.txt
cp .env.example .env       # 填七牛/GitHub 配置；或 python3 main.py init 从 PicGo 导入七牛段
```

## 配置

全部在 `.env`（见 `.env.example`）：

- **七牛**：`QINIU_ACCESS_KEY/SECRET_KEY/BUCKET/DOMAIN/AREA/PATH`
- **GitHub**：`GH_TOKEN/OWNER/REPO/BRANCH/PATH/DOMAIN`（`GH_DOMAIN` 留空=raw.githubusercontent.com，填则用自定义域名）
- `DEFAULT_BACKEND=qiniu|github`

`init` 会读 `~/Library/Application Support/picgo/data.json` 的 `picBed.qiniu` 写入 `.env`，导入后 PicGo 可卸载。

## 行为要点

- **幂等**：按文件内容 sha256 去重，重跑不重复上传；同一文件可同时记七牛与 GitHub 两条 URL。
- **改写规则**：`![[x.png]]`/`![[x.png|alt]]`/`![alt](./x.png)` → `![alt](URL)`；已是 URL 或无图片扩展名的笔记双链**跳过**。
- **key 命名**：`upload` 用 `{前缀}/{日期}/{文件名}`；`migrate` 用 `{前缀}/{post-slug}/{文件名}`。
- **路径解析**：`![[]]` 依次查文章同目录 → vault 的 `assets/` → `assets/blog/` → 全 vault 兜底 glob。

设计文档：`docs/plans/2026-06-25-image-upload-skill-design.md`。
