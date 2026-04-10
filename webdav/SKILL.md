---
name: webdav
description: WebDAV 文件共享服务访问技能，支持上传、下载、删除、列出、目录操作。首次使用自动引导配置。
homepage: https://github.com/xiejava1018/myopenclaw-skills
metadata: { "openclaw": { "emoji": "📁", "requires": { "modules": ["requests"] } } }
---

# WebDAV 访问技能

用于访问 NAS WebDAV 服务器的 OpenClaw 技能。

## 功能特点

- 📁 支持文件上传、下载、删除
- 📂 支持目录创建、列出内容
- 📊 文件属性查询
- 🔒 配置通过 `.env` 文件管理，首次使用自动引导配置
- 🔄 内置重试机制，网络波动自动重连
- 🛡️ 默认启用 SSL 证书验证

## 首次配置

首次使用时，技能会自动检测配置是否完整，并引导你完成以下配置：

1. **WebDAV 服务器地址** — NAS 的 WebDAV 服务地址
2. **用户名 / 密码** — WebDAV 认证信息
3. **SSL 证书验证** — 是否验证 HTTPS 证书

配置保存在 `webdav/.env` 文件中。也可手动创建：

```bash
cp .env.example .env
# 编辑 .env 填入实际值
```

## 使用方法

### 结构化命令（推荐）

```
list path=<目录>                          列出目录内容
upload local=<本地路径> remote=<远程路径>   上传文件
download remote=<远程路径> local=<本地路径>  下载文件
delete path=<远程路径>                     删除文件/目录
mkdir path=<目录名>                        创建目录
info path=<远程路径>                       查看文件信息
```

### 自然语言命令（兼容）

```
列出NAS共享目录内容
列出NAS目录 test_dir
上传 /local/file.txt 到NAS remote/path/
下载NAS文件 remote/file.txt 到 /local/path
删除NAS文件 remote/file.txt
创建NAS目录 new_dir
查看NAS文件 info.txt 的信息
```

### 代码调用

```python
from webdav import handle, WebDAVClient

# 通过命令接口
result = handle("list path=test_dir")

# 直接使用客户端
client = WebDAVClient()
files = client.list_contents("some/path")
success, msg = client.upload_file("/local/file.txt", "remote/file.txt")
```

## 配置说明

| 环境变量 | 必填 | 说明 |
|---------|------|------|
| `WEBDAV_SERVER` | 是 | WebDAV 服务器地址 |
| `WEBDAV_USERNAME` | 是 | 认证用户名 |
| `WEBDAV_PASSWORD` | 是 | 认证密码 |
| `WEBDAV_SSL_VERIFY` | 否 | SSL 验证，默认 true |

## 技术细节

**依赖模块：** `requests`

**支持的 WebDAV 操作：**
- `PROPFIND` — 获取目录内容和文件属性
- `PUT` — 上传文件
- `GET` — 下载文件
- `DELETE` — 删除文件/目录
- `MKCOL` — 创建目录

**重试机制：** 自动重试 3 次（500/502/503/504 错误），间隔 0.5s 递增。

## 权限说明

- ✅ 读取文件
- ✅ 写入文件
- ✅ 删除文件
- ✅ 创建目录

## 注意事项

- 配置文件 `.env` 不会被提交到 Git（已在 `.gitignore` 中排除）
- 如需重新配置，删除 `.env` 文件后再次运行即可
- 自签名证书环境可将 `WEBDAV_SSL_VERIFY` 设为 `false`
