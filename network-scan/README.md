# Network Scan - 内网资产扫描

自动扫描内网资产并同步到 Supabase + 飞书（双源同步）。

## 功能

- 🌐 自动扫描内网在线主机
- 📦 同步到 Supabase（主数据源）
- 📋 同步到飞书多维表格（展示/备份）
- 🔄 状态自动更新（在线/离线/新发现）
- 🛡️ 去重逻辑（避免重复创建）
- 🧭 首次运行自动交互式配置
- ⚡ 快速扫描模式（无需配置，仅显示在线主机）

## 快速开始

### 方式一：快速扫描（无需配置）

```bash
cd skills/network-scan
python3 network_scan_unified.py --quick
```

或直接运行，首次会提示选择模式：

```bash
python3 network_scan_unified.py
```

### 方式二：完整同步（扫描 + 数据同步）

首次运行会自动进入交互式配置：

```bash
cd skills/network-scan
python3 network_scan_unified.py
# 选择 "完整同步" 模式
```

## 使用方法

### 命令行选项

```bash
python3 network_scan_unified.py [选项]
```

| 选项 | 说明 |
|------|------|
| `-h, --help` | 显示帮助信息 |
| `--quick` | 快速扫描模式（不同步到数据源） |
| `--scan-only` | 仅扫描模式（同 --quick） |

### 示例

**快速扫描（不配置数据源）：**
```bash
python3 network_scan_unified.py --quick
```

**交互式选择模式：**
```bash
python3 network_scan_unified.py
# 首次运行会提示选择：
# 1) 快速扫描 - 仅显示在线主机
# 2) 完整同步 - 扫描后同步到 Supabase 和飞书
```

**查看帮助：**
```bash
python3 network_scan_unified.py --help
```

## 安装依赖

```bash
pip3 install requests --break-system-packages
# 需要 nmap（可选）: brew install nmap 或 apt install nmap
```

## 配置说明

### Supabase（主数据源）

1. 创建 Supabase 项目
2. 创建 `soc_assets` 表：
   - `id` (int8, 主键, 自增)
   - `asset_ip` (text, 唯一)
   - `asset_description` (text)
   - `asset_status` (text)
   - `status_updated_at` (timestamp)
3. 获取 API URL 和 anon public key

### 飞书多维表格（展示/备份）

1. 在飞书开放平台创建应用
2. 开通多维表格权限
3. 创建多维表格，设置字段：
   - `资产IP` (文本，唯一)
   - `资产说明` (文本)
   - `资产状态` (文本：在线/离线/新发现/已删除)
   - `状态更新时间` (日期时间)

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| NETWORK | 扫描网段 | 192.168.0.0/24 |
| SUPABASE_URL | Supabase 项目 URL | https://xxx.supabase.co |
| SUPABASE_KEY | Supabase anon public key | eyJxxx |
| FEISHU_APP_TOKEN | 飞书多维表格 App Token | YBxxx |
| FEISHU_TABLE_ID | 飞书多维表格 Table ID | tblxxx |
| FEISHU_APP_ID | 飞书应用 App ID | cli_xxx |
| FEISHU_APP_SECRET | 飞书应用 App Secret | xxx |

## 数据流向

```
nmap/ping 扫描 → Supabase（主数据源）→ 飞书（展示/备份）
```

## 状态说明

- 🆕 新发现：首次扫描到的 IP
- ✅ 在线：本次扫描仍然在线
- ❌ 离线：之前在线，本次未扫描到
- 🗑️ 已删除：手动标记删除

## 重新配置

如果需要重新配置，删除 `.env` 文件后重新运行即可：

```bash
rm .env
python3 network_scan_unified.py
```