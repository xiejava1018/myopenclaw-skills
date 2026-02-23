---
name: webdav
description: WebDAV文件共享服务访问技能，支持上传、下载、删除、列出等操作。
homepage: https://fnos.ishareread.com:5006/openclaw_sharedoc
metadata: { "openclaw": { "emoji": "📁", "requires": { "modules": ["requests", "xml.etree.ElementTree"] } } }
---

# WebDAV访问技能

用于访问NAS WebDAV服务器的OpenClaw技能。

## 功能特点

- 🔄 完全可复用的WebDAV访问功能
- 📄 支持文件上传、下载、删除、列出等操作
- 📂 支持目录创建、删除操作
- 📁 支持递归操作
- 📊 完整的错误处理和状态反馈

## 使用方法

### 基础操作

#### 列出目录内容
```
列出NAS共享目录内容
列出NAS目录 test_dir
列出NAS文件夹 remote/path
```

#### 上传文件
```
上传 /local/path/file.txt 到NAS remote/path/file.txt
上传 /data/documents/report.pdf 到NAS reports/2026/
```

#### 下载文件
```
下载NAS文件 remote/path/file.txt 到 /local/path
下载NAS reports/2026/report.pdf 到 /tmp/report.pdf
```

#### 删除文件
```
删除NAS文件 remote/path/file.txt
删除NAS reports/2026/report.pdf
```

#### 创建目录
```
在NAS上创建目录 new_directory
创建NAS文件夹 test/results
```

#### 删除目录
```
删除NAS目录 test_dir
删除NAS文件夹 old/
```

#### 获取文件信息
```
查看NAS文件 info.txt 的信息
获取NAS文件 document.pdf 的属性
```

### 参数说明

- **本地路径**：系统中的文件路径（如 `/data/openclaw/workspace/file.txt`）
- **远程路径**：NAS服务器上的路径（相对路径，从 `openclaw_sharedoc` 开始）

## 配置信息

**当前服务器配置（在技能内部）：**
- **服务器地址**：https://fnos.ishareread.com:5006/openclaw_sharedoc
- **用户名**：xiejava
- **密码**：已加密存储
- **共享根目录**：/openclaw_sharedoc/

## 技术细节

**依赖模块：**
- `requests` - HTTP请求库
- `xml.etree.ElementTree` - XML解析
- `os` - 文件系统操作

**支持的操作：**
- PROPFIND：获取目录内容
- PUT：上传文件
- GET：下载文件
- DELETE：删除文件
- MKCOL：创建目录

## 权限说明

**您的NAS服务器具有以下访问权限：**
- ✅ 读取文件
- ✅ 写入文件
- ✅ 删除文件
- ✅ 创建目录
- ✅ 删除目录

## 注意事项

- 所有操作都会在NAS服务器上执行
- 文件大小限制由NAS服务器配置决定
- 网络连接状态会影响操作速度
- 错误信息会详细显示失败原因
