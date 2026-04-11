---
name: webdav
description: "WebDAV 文件共享服务访问技能。用于访问 NAS 等 WebDAV 服务器，支持文件上传、下载、删除、目录列出与创建、文件属性查询、连接测试。首次使用自动引导配置。"
---

# WebDAV 访问技能 v1.1.0

用于访问 NAS WebDAV 服务器的 Claude Code 系统级技能。

## 功能特点

- 📁 文件上传、下载、删除
- 📂 目录创建、内容列出
- 📊 文件属性查询（大小、修改时间、类型）
- 🔍 **连接测试命令** — 快速验证配置是否正确
- 🔄 内置重试机制（HTTP 500/502/503/504 自动重试 3 次）
- 🛡️ 默认启用 SSL 证书验证，自签名环境可关闭
- 🗂️ 路径自动规范化 — `path` 和 `/path` 行为一致
- 📈 上传/下载进度条 — 大文件传输状态可见
- 🔐 支持 Basic Auth 和 Digest Auth（自动降级）
- 🐛 `--debug` 调试模式 — 详细日志便于排查问题

## 安装

### 1. 安装依赖

```bash
cd ~/.claude/skills/webdav
~/.claude/skills/webdav/.venv/bin/pip install -r requirements.txt
```

### 2. 配置

首次运行时技能会自动检测配置并引导你完成设置：

```bash
python3 ~/.claude/skills/webdav/scripts/main.py test
```

也可手动创建配置文件：

```bash
cp ~/.claude/skills/webdav/.env.example ~/.claude/skills/webdav/.env
# 编辑 .env，填入 WebDAV 服务器信息
```

**配置项：**

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `WEBDAV_SERVER` | 是 | WebDAV 服务器地址（支持 HTTP/HTTPS） | `https://nas.example.com:5006` |
| `WEBDAV_USERNAME` | 是 | 认证用户名 | `admin` |
| `WEBDAV_PASSWORD` | 是 | 认证密码 | `your_password` |
| `WEBDAV_SSL_VERIFY` | 否 | SSL 证书验证，默认 `true` | `false` |

**重新配置：**

```bash
python3 ~/.claude/skills/webdav/scripts/main.py --config
```

## 使用方法

### Claude Code 调用方式

在 Claude Code 中直接使用自然语言或结构化命令：

```
列出NAS根目录
列出NAS目录 openclaw_sharedoc
上传 /tmp/file.txt 到NAS openclaw_sharedoc/
下载NAS文件 openclaw_sharedoc/file.txt 到 /tmp/
删除NAS文件 openclaw_sharedoc/file.txt
创建NAS目录 openclaw_sharedoc/new_folder
查看NAS文件 openclaw_sharedoc/file.txt 的信息
测试NAS连接
```

### 命令行

```bash
# 测试连接
python3 ~/.claude/skills/webdav/scripts/main.py test
python3 ~/.claude/skills/webdav/scripts/main.py ping

# 列出目录
python3 ~/.claude/skills/webdav/scripts/main.py "list path=openclaw_sharedoc"

# 上传文件（含进度条）
python3 ~/.claude/skills/webdav/scripts/main.py "upload local=/tmp/report.pdf remote=openclaw_sharedoc/report.pdf"

# 下载文件（含进度条）
python3 ~/.claude/skills/webdav/scripts/main.py "download remote=openclaw_sharedoc/report.pdf local=/tmp/report.pdf"

# 查看文件信息
python3 ~/.claude/skills/webdav/scripts/main.py "info path=openclaw_sharedoc/report.pdf"

# 创建目录
python3 ~/.claude/skills/webdav/scripts/main.py "mkdir path=openclaw_sharedoc/new_folder"

# 删除文件/目录
python3 ~/.claude/skills/webdav/scripts/main.py "delete path=openclaw_sharedoc/report.pdf"

# 调试模式（查看详细日志）
python3 ~/.claude/skills/webdav/scripts/main.py --debug "list"

# 重新配置
python3 ~/.claude/skills/webdav/scripts/main.py --config
```

### Python 代码调用

```python
import sys
sys.path.insert(0, '~/.claude/skills/webdav/scripts')
from webdav import handle, WebDAVClient, test_connection

# 通过命令接口
result = handle("list path=openclaw_sharedoc")
print(result)

# 测试连接
ok, code, msg = test_connection(
    "https://192.168.0.1:5006",
    "admin", "password",
    verify_ssl=False
)
print(msg)

# 直接使用客户端
client = WebDAVClient()
files = client.list_contents("openclaw_sharedoc")
success, msg = client.upload_file("/tmp/file.pdf", "openclaw_sharedoc/file.pdf")
success, msg = client.download_file("openclaw_sharedoc/file.pdf", "/tmp/file.pdf")
info = client.get_file_info("openclaw_sharedoc/file.pdf")
success, msg = client.create_directory("openclaw_sharedoc/new_folder")
success, msg = client.delete_file("openclaw_sharedoc/file.pdf")
ok, code, msg = client.test_connection()
```

## 命令参考

| 命令 | 参数 | 说明 |
|------|------|------|
| `list` | `path=<目录>` | 列出目录内容，path 省略则列出根目录 |
| `test` / `ping` | — | 测试连接，返回服务器状态和配置信息 |
| `upload` | `local=<本地路径> remote=<远程路径>` | 上传文件（含进度条） |
| `download` | `remote=<远程路径> local=<本地路径>` | 下载文件（含进度条） |
| `delete` | `path=<远程路径>` | 删除文件或目录 |
| `mkdir` | `path=<目录名>` | 创建目录 |
| `info` | `path=<远程路径>` | 查看文件属性 |

## 技术细节

- **依赖模块：** `requests`
- **HTTP 方法：** `PROPFIND`（列目录/查属性）、`PUT`（上传）、`GET`（下载）、`DELETE`（删除）、`MKCOL`（创建目录）
- **认证方式：** HTTP Basic Auth（默认）+ Digest Auth（自动降级）
- **重试策略：** urllib3 Retry，3 次重试，退避因子 0.5s，覆盖 500/502/503/504 状态码
- **中文支持：** 自动处理 URL 编码的中文路径
- **路径规范化：** 自动去除首部 `/`，合并多余斜杠，`path` 与 `/path` 等效
- **进度条：** 文件大于 0 字节时显示，64KB 分块
- **配置加载优先级：** 构造函数参数 > 环境变量 > `.env` 文件 > 交互式向导

## 常见问题

**Q: 连接超时怎么办？**
检查服务器地址是否正确，是否需要在地址末尾加 `/webdav` 路径。如果是 HTTPS 且使用自签名证书，将 `WEBDAV_SSL_VERIFY` 设为 `false`。

**Q: 如何确认配置正确？**
运行 `test` 或 `ping` 命令，会显示连接状态和服务器响应码。

**Q: 上传大文件时没有反应，是卡死了吗？**
不是。v1.1.0 已添加进度条。如果未显示进度条，检查文件是否大于 0 字节，或加 `--debug` 查看详细日志。

**Q: 连接测试成功，但 list 失败？**
可能是服务器路径问题。某些 NAS 需要在地址中包含 `/webdav` 前缀，例如 `https://nas.example.com:5006/webdav`。

**Q: 支持哪些 NAS 设备？**
支持所有兼容 WebDAV 协议的设备和服务，包括群晖、威联通、飞牛云（fnOS）、Nextcloud、ownCloud 等。

**Q: 如何开启调试模式？**
添加 `--debug` 参数，可以看到每个 HTTP 请求的 URL、方法、状态码和响应大小。

**Q: 如何重新配置？**
```bash
python3 ~/.claude/skills/webdav/scripts/main.py --config
```
或删除 `~/.claude/skills/webdav/.env` 后再次运行任意命令。
