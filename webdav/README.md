# WebDAV 访问技能

OpenClaw 技能，用于访问 NAS 等 WebDAV 文件共享服务，支持文件上传、下载、删除和目录操作。

## 功能特点

- 文件上传、下载、删除
- 目录创建、内容列出
- 文件属性查询（大小、修改时间、类型）
- 首次使用自动引导配置，配置保存到 `.env` 文件
- 内置重试机制（HTTP 500/502/503/504 自动重试 3 次）
- 默认启用 SSL 证书验证，自签名环境可关闭
- 同时支持结构化命令和中文自然语言命令

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

首次运行时，技能会自动检测配置并引导你完成设置：

```bash
python3 main.py list
```

你也可以手动创建配置文件：

```bash
cp .env.example .env
# 编辑 .env，填入你的 WebDAV 服务器信息
```

配置项：

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `WEBDAV_SERVER` | 是 | WebDAV 服务器地址 | `https://nas.example.com:5006` |
| `WEBDAV_USERNAME` | 是 | 认证用户名 | `admin` |
| `WEBDAV_PASSWORD` | 是 | 认证密码 | `your_password` |
| `WEBDAV_SSL_VERIFY` | 否 | SSL 证书验证，默认 `true` | `false` |

重新配置：删除 `.env` 文件后再次运行即可触发配置向导。

## 使用方法

### 命令行

```bash
# 列出根目录
python3 main.py list

# 列出子目录
python3 main.py "list path=openclaw_sharedoc"

# 上传文件
python3 main.py "upload local=/tmp/report.pdf remote=openclaw_sharedoc/report.pdf"

# 下载文件
python3 main.py "download remote=openclaw_sharedoc/report.pdf local=/tmp/report.pdf"

# 查看文件信息
python3 main.py "info path=openclaw_sharedoc/report.pdf"

# 创建目录
python3 main.py "mkdir path=openclaw_sharedoc/new_folder"

# 删除文件
python3 main.py "delete path=openclaw_sharedoc/report.pdf"
```

### 自然语言（兼容）

```bash
python3 main.py "列出NAS共享目录内容"
python3 main.py "列出NAS目录 openclaw_sharedoc"
python3 main.py "上传 /tmp/file.txt 到NAS openclaw_sharedoc/"
python3 main.py "下载NAS文件 openclaw_sharedoc/file.txt 到 /tmp/"
python3 main.py "删除NAS文件 openclaw_sharedoc/file.txt"
python3 main.py "创建NAS目录 openclaw_sharedoc/new_folder"
python3 main.py "查看NAS文件 openclaw_sharedoc/file.txt 的信息"
```

### Python 代码调用

```python
from webdav import handle, WebDAVClient

# 方式一：通过命令接口
result = handle("list path=openclaw_sharedoc")
print(result)

# 方式二：直接使用客户端
client = WebDAVClient()

# 列出目录
files = client.list_contents("openclaw_sharedoc")
print(files)

# 上传文件
success, msg = client.upload_file("/tmp/report.pdf", "openclaw_sharedoc/report.pdf")

# 下载文件
success, msg = client.download_file("openclaw_sharedoc/report.pdf", "/tmp/report.pdf")

# 查看文件信息
info = client.get_file_info("openclaw_sharedoc/report.pdf")
print(info)

# 创建目录
success, msg = client.create_directory("openclaw_sharedoc/new_folder")

# 删除文件
success, msg = client.delete_file("openclaw_sharedoc/report.pdf")
```

### 客户端自定义初始化

```python
# 直接传入配置，跳过 .env 文件
client = WebDAVClient(
    server="https://nas.example.com:5006",
    username="admin",
    password="secret",
    verify_ssl=False,
)
```

## 命令参考

| 命令 | 参数 | 说明 |
|------|------|------|
| `list` | `path=<目录>` | 列出目录内容，path 省略则列出根目录 |
| `upload` | `local=<本地路径> remote=<远程路径>` | 上传文件 |
| `download` | `remote=<远程路径> local=<本地路径>` | 下载文件 |
| `delete` | `path=<远程路径>` | 删除文件或目录 |
| `mkdir` | `path=<目录名>` | 创建目录 |
| `info` | `path=<远程路径>` | 查看文件属性 |

## 目录结构

```
webdav/
├── __init__.py       # 包初始化，导出 handle 和 WebDAVClient
├── main.py           # 核心实现：配置管理、WebDAV 客户端、命令解析
├── .env.example      # 配置模板
├── .env              # 实际配置（gitignore，需手动创建）
├── .gitignore        # 排除敏感文件和缓存
├── requirements.txt  # Python 依赖
├── SKILL.md          # OpenClaw 技能描述文件
└── README.md         # 本文件
```

## 技术细节

- **HTTP 方法**：`PROPFIND`（列目录/查属性）、`PUT`（上传）、`GET`（下载）、`DELETE`（删除）、`MKCOL`（创建目录）
- **认证方式**：HTTP Basic Auth
- **重试策略**：urllib3 Retry，3 次重试，退避因子 0.5s，覆盖 500/502/503/504 状态码
- **中文支持**：自动处理 URL 编码的中文路径
- **配置加载优先级**：构造函数参数 > 环境变量 > `.env` 文件 > 交互式向导

## 常见问题

**Q: 连接超时怎么办？**

检查服务器地址是否正确，是否需要在地址末尾加 `/webdav` 路径。如果是 HTTPS 且使用自签名证书，将 `WEBDAV_SSL_VERIFY` 设为 `false`。

**Q: 如何切换到不同的 WebDAV 服务器？**

删除 `.env` 文件重新运行，或直接修改 `.env` 中的配置值。

**Q: 支持哪些 NAS 设备？**

支持所有兼容 WebDAV 协议的设备和服务，包括群晖、威联通、飞牛云（fnOS）、Nextcloud、ownCloud 等。

## License

MIT
