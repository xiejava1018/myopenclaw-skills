# myopenclaw-skills

> 个人 [Claude Code](https://docs.claude.com/en/docs/claude-code) 技能（Skills）合集 —— 把飞书、Coze、Supabase、WebDAV、WeKnora 知识库等外部服务接入 Claude，让一条指令完成多步骤业务流程。

每个子目录是一个独立技能，自带 `SKILL.md` 定义、脚本实现与 `.env` 配置。Claude 在对话中根据用户意图自动匹配并调用对应技能。

## 技能一览

| 技能 | 说明 | 主要集成 | 触发示例 |
|------|------|----------|----------|
| **[ishareread-article-writing](ishareread-article-writing/)** | 爱分享读书公众号文章写作全流程：选题 → 分析往期文案 → 搜索资料撰写 → 上传飞书云盘 → 写入文案库 → 更新选题状态 | 飞书选题库/文案库、飞书云盘、Coze | "写文章"、"新选题"、"飞书投稿" |
| **[ishareread-publish](ishareread-publish/)** | 爱分享读书一键发布：从飞书多维表格取未发布文章 → 发布到 Hugo 网站（GitHub Pages）→ 同步微信公众号 → 回写发布地址 | 飞书多维表格、Hugo、GitHub Pages、Coze、微信公众平台 | "发布文章"、"微信公众号发布"、"同步飞书" |
| **[scheme-writer](scheme-writer/)** | 编写方案：WeKnora 知识库语义检索 + 网络搜索，按主题生成结构化 Markdown 方案，可显式归档回知识库 | WeKnora 知识库（检索/列表/文档清单/上传）、DuckDuckGo | "写方案"、"知识库方案"、"方案归档" |
| **[webdav](webdav/)** | WebDAV 文件共享服务访问：上传、下载、删除、目录列出与创建、属性查询、连接测试 | WebDAV / NAS | "上传到 NAS"、"WebDAV 下载文件" |
| **[network-scan](network-scan/)** | 内网资产扫描：扫描 192.168.0.0/24 网段，新发现 IP 标记"新发现"，离线主机标记"离线"，双源同步 | Supabase（主数据源）、飞书（展示/备份）、nmap | "资产巡检"、"扫描内网"、"网络安全扫描" |
| **[duckduckgo-search](duckduckgo-search/)** | 免费 Web 搜索，无需 API Key | DuckDuckGo | "搜一下"、"查最新文档" |

## 仓库结构

```
myopenclaw-skills/
├── ishareread-article-writing/   # 各技能一个目录
├── ishareread-publish/
├── scheme-writer/
├── webdav/
├── network-scan/
├── duckduckgo-search/
└── .gitignore                    # 根级忽略 .DS_Store
```

每个技能目录遵循统一约定：

```
<skill>/
├── SKILL.md          # 技能定义：frontmatter(name/description) + 流程说明
├── README.md         # 详细文档（部分技能）
├── scripts/ 或 *.py  # Python 脚本实现
├── references/       # API 文档、错误码参考
├── templates/        # 输出模板
├── examples/         # 示例产物
├── tests/            # pytest 测试
├── requirements.txt  # 依赖
├── .env.example      # 配置模板（已提交，占位符）
├── .env              # 实际配置（被忽略，含真实密钥，不入库）
└── .gitignore        # 忽略 .env / __pycache__ / *.pyc 等
```

## 使用方式

这些是 Claude Code 技能，需放入 Claude 的技能目录后由 Claude 自动加载匹配：

```bash
# 1. 克隆仓库
git clone https://github.com/xiejava1018/myopenclaw-skills.git

# 2. 将技能目录链接/复制到 Claude Code 个人技能目录
ln -s "$PWD/ishareread-publish" ~/.claude/skills/ishareread-publish
# （或按需复制单个技能目录）
```

每个技能也可**独立运行其脚本**（不依赖 Claude），详见各技能的 `README.md`。

## 配置约定

所有技能遵循一致的配置与安全约定：

- **密钥零硬编码** —— API Key、Token 等一律通过 `.env` 文件管理，脚本通过环境变量读取
- **`.env` 不入库** —— 每个技能的 `.gitignore` 均忽略 `.env`，仅提交 `.env.example` 模板
- **首次使用引导** —— 多数技能首次调用时，Claude 会在对话内自动引导填写配置（或运行 `scripts/init.py` 向导），无需切换终端
- **复制模板**：`cp .env.example .env` 后填入实际值

## 开发约定

- 新增技能时创建独立目录，必须包含 `SKILL.md`（frontmatter 的 `description` 决定 Claude 何时匹配该技能）
- 脚本聚焦、单文件 < 800 行；公共服务逻辑抽取到独立模块
- 涉及外部调用的脚本配 `tests/` 单元测试（参考 `scheme-writer/tests`）
- 提交前确认 `.env`、`__pycache__/`、`*.pyc` 未被暂存（各技能 `.gitignore` 已覆盖）

## 相关文档

各技能的详细用法见对应目录下的 `README.md` 与 `SKILL.md`；`scheme-writer` 暂无独立 README，文档集中在 `SKILL.md` + `references/`。
