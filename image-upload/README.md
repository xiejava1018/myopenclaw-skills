# image-upload

博客图片上传到图床（七牛云 / GitHub）并改写文章图片链接的 Claude Code 技能。

## 解决什么问题

博客（Hugo）发布前，文章里的 Obsidian 本地图片引用 `![[x.png]]` 需要变成图床 URL。本技能把它固化成一条命令：扫描文章 → 上传到图床 → 原地改写链接。也提供可复用的单张上传原语。

## 快速开始

```bash
# 1. 安装
cd image-upload
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# 2. 配置（二选一）
cp .env.example .env && $EDITOR .env        # 手填
# 或
python3 main.py init                         # 从 PicGo 导入七牛配置

# 3. 用
.venv/bin/python main.py upload assets/blog/foo.png --json
.venv/bin/python main.py migrate notes/blog/draft.md --dry-run
.venv/bin/python main.py migrate notes/blog/draft.md
```

## 命令

| 命令 | 作用 |
|------|------|
| `upload <file...> [--backend] [--json]` | 上传图片，返回 URL（原语） |
| `migrate <post.md> [--backend] [--dry-run] [--vault-root]` | 扫描文章图片，上传 + 改写链接 |
| `init` | 从 PicGo `data.json` 导入七牛配置到 `.env` |
| `list` | 查看 manifest |

## 后端

- **七牛云**（默认，中国可达）：`qiniu` 官方 SDK。
- **GitHub**（备，免费/可回溯）：Contents API，默认 `raw.githubusercontent.com`，`GH_DOMAIN` 可换自定义域名（如 Cloudflare Worker 反代）。

## 幂等

`manifest.json` 按文件内容 sha256 索引、按后端分桶：重跑不重复传，切换后端不重传，`list` 可回溯。

## 测试

```bash
.venv/bin/pytest -q
```

详见 `SKILL.md` 与 `docs/plans/2026-06-25-image-upload-skill-design.md`。
