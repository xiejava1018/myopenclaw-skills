#!/usr/bin/env python3
"""
网络资产扫描脚本 - 自动扫描内网并更新 Supabase + 飞书（双源同步）

正确流程：
1. 扫描网络 -> 获取在线主机列表
2. 更新 Supabase（主数据源）
3. 从 Supabase 同步到飞书（展示/备份）

使用方法:
  python3 network_scan_unified.py
  # 首次运行会自动提示选择模式

环境变量（配置在 .env 文件中）:
  NETWORK - 扫描网段，默认 192.168.0.0/24
  SUPABASE_URL - Supabase 项目 URL
  SUPABASE_KEY - Supabase API Key (anon public)
  FEISHU_APP_TOKEN - 飞书多维表格 App Token
  FEISHU_TABLE_ID - 飞书多维表格 Table ID
  FEISHU_APP_ID - 飞书应用 App ID
  FEISHU_APP_SECRET - 飞书应用 App Secret

更新日志:
2026-03-04: 修复流程 - 添加先更新Supabase再更新飞书的逻辑
2026-03-10: 修复去重 - 飞书同步时检查IP是否已存在，避免重复创建
2026-04-07: 添加交互式配置初始化功能和快速扫描模式
"""
import subprocess
import json
import time
import os
import requests
from datetime import datetime
from pathlib import Path

# ===== 配置区域 =====

def is_config_complete(config):
    """检查配置是否完整"""
    required_fields = [
        'SUPABASE_URL', 'SUPABASE_KEY',
        'FEISHU_APP_TOKEN', 'FEISHU_TABLE_ID',
        'FEISHU_APP_ID', 'FEISHU_APP_SECRET'
    ]

    for field in required_fields:
        if not config.get(field) or config.get(field).strip() == '':
            return False
    return True

def get_input(prompt, default=''):
    """获取用户输入，支持默认值"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    value = input(prompt).strip()
    return value if value else default

def validate_config(key, value):
    """验证配置值"""
    if key in ['SUPABASE_URL'] and value:
        if not (value.startswith('https://') and '.supabase.co' in value):
            print(f"⚠️  {key} 格式可能不正确，应该是类似 https://your-project.supabase.co 的格式")
    elif key in ['SUPABASE_KEY', 'FEISHU_APP_TOKEN', 'FEISHU_TABLE_ID',
                'FEISHU_APP_ID', 'FEISHU_APP_SECRET'] and value:
        if len(value) < 10:
            print(f"⚠️  {key} 长度可能不足，请检查输入是否正确")
    elif key in ['NETWORK'] and value:
        # 简单的网段格式验证
        parts = value.split('/')
        if len(parts) != 2:
            print(f"⚠️  {key} 格式可能不正确，应该是类似 192.168.0.0/24 的格式")

    return True  # 暂时不阻止继续，仅提供警告

def interactive_config():
    """交互式配置初始化"""
    print("🔧 首次运行网络资产扫描，开始配置初始化")
    print("=" * 60)
    print("请根据提示输入配置信息（按 Enter 可使用默认值）")
    print("=" * 60)

    config = {}

    # 网络配置
    config['NETWORK'] = get_input("请输入要扫描的网段", "192.168.0.0/24")
    validate_config('NETWORK', config['NETWORK'])

    print("\n" + "-" * 60)
    print("Supabase 配置（主数据源）")
    print("- 可在 Supabase 控制台 -> 项目设置 -> API 中获取")
    print("- URL 格式: https://your-project.supabase.co")
    print("- 密钥使用 anon public 即可")
    print("-" * 60)
    config['SUPABASE_URL'] = get_input("请输入 Supabase 项目 URL")
    validate_config('SUPABASE_URL', config['SUPABASE_URL'])
    config['SUPABASE_KEY'] = get_input("请输入 Supabase API Key")
    validate_config('SUPABASE_KEY', config['SUPABASE_KEY'])

    print("\n" + "-" * 60)
    print("飞书配置（展示/备份）")
    print("- 应用凭证可在飞书开放平台 -> 你的应用 -> 凭证与基础信息 中获取")
    print("- 表格信息可在多维表格的分享链接中获取")
    print("- App Token 示例: bascnxxxxxxxxxxxxxx")
    print("- Table ID 示例: tblxxxxxxxxxxxxxx")
    print("-" * 60)
    config['FEISHU_APP_TOKEN'] = get_input("请输入飞书多维表格 App Token")
    validate_config('FEISHU_APP_TOKEN', config['FEISHU_APP_TOKEN'])
    config['FEISHU_TABLE_ID'] = get_input("请输入飞书多维表格 Table ID")
    validate_config('FEISHU_TABLE_ID', config['FEISHU_TABLE_ID'])
    config['FEISHU_APP_ID'] = get_input("请输入飞书应用 App ID")
    validate_config('FEISHU_APP_ID', config['FEISHU_APP_ID'])
    config['FEISHU_APP_SECRET'] = get_input("请输入飞书应用 App Secret")
    validate_config('FEISHU_APP_SECRET', config['FEISHU_APP_SECRET'])

    print("\n" + "=" * 60)
    print("配置信息摘要")
    print("=" * 60)
    for key, value in config.items():
        print(f"{key:20} {value}")

    print("\n" + "=" * 60)
    confirm = get_input("配置是否正确？(y/n)", "y").lower()

    if confirm != 'y':
        print("🔄 重新配置...")
        return interactive_config()

    # 保存配置到 .env 文件
    env_file = Path(__file__).parent / ".env"
    try:
        with open(env_file, 'w') as f:
            for key, value in config.items():
                f.write(f"{key}={value}\n")
        print(f"✅ 配置已保存到 {env_file}")
        return config
    except Exception as e:
        print(f"❌ 配置保存失败: {e}")
        return None

# 从环境变量或 .env 文件加载配置
def load_config():
    """加载配置"""
    config = {}

    # 检查 .env 文件
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    config['NETWORK'] = os.environ.get('NETWORK', '192.168.0.0/24')
    config['SUPABASE_URL'] = os.environ.get('SUPABASE_URL', '')
    config['SUPABASE_KEY'] = os.environ.get('SUPABASE_KEY', '')
    config['FEISHU_APP_TOKEN'] = os.environ.get('FEISHU_APP_TOKEN', '')
    config['FEISHU_TABLE_ID'] = os.environ.get('FEISHU_TABLE_ID', '')
    config['FEISHU_APP_ID'] = os.environ.get('FEISHU_APP_ID', '')
    config['FEISHU_APP_SECRET'] = os.environ.get('FEISHU_APP_SECRET', '')

    return config

CONFIG = load_config()
NETWORK = CONFIG['NETWORK']
SUPABASE_URL = CONFIG['SUPABASE_URL']
SUPABASE_KEY = CONFIG['SUPABASE_KEY']
FEISHU_APP_TOKEN = CONFIG['FEISHU_APP_TOKEN']
FEISHU_TABLE_ID = CONFIG['FEISHU_TABLE_ID']
FEISHU_APP_ID = CONFIG['FEISHU_APP_ID']
FEISHU_APP_SECRET = CONFIG['FEISHU_APP_SECRET']

# ===== Supabase 函数 =====

def supabase_request(method, endpoint, data=None):
    """发送请求到 Supabase API"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ 请配置 SUPABASE_URL 和 SUPABASE_KEY")
        return None

    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    try:
        if method == "GET":
            req = requests.Request("GET", url, headers=headers)
        elif method == "POST":
            req = requests.Request("POST", url, headers=headers, data=json.dumps(data))
        elif method == "PATCH":
            req = requests.Request("PATCH", url, headers=headers, data=json.dumps(data))
        elif method == "Delete":
            req = requests.Request("DELETE", url, headers=headers)

        prepped = req.prepare()
        with requests.Session().send(prepped) as response:
            if response.status_code == 204:
                return []
            return json.loads(response.text)
    except Exception as e:
        print(f"❌ Supabase 请求错误: {e}")
        return None

def get_supabase_records():
    """获取 Supabase 所有资产记录"""
    print("📦 获取 Supabase 资产表...")
    records = supabase_request("GET", "soc_assets?select=*")
    if records is None:
        return []
    return records

def create_supabase_record(ip, description, status="新发现"):
    """创建 Supabase 新记录"""
    data = {
        "asset_ip": ip,
        "asset_description": description,
        "asset_status": status,
        "status_updated_at": datetime.utcnow().isoformat() + "Z"
    }
    result = supabase_request("POST", "soc_assets", data)
    return result

def update_supabase_record(id, status):
    """更新 Supabase 记录状态"""
    data = {
        "asset_status": status,
        "status_updated_at": datetime.utcnow().isoformat() + "Z"
    }
    result = supabase_request("PATCH", f"soc_assets?id=eq.{id}", data)
    return result

# ===== 飞书函数 =====

def get_feishu_access_token():
    """获取飞书应用 access_token"""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 请配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return None

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}

    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if result.get("code") == 0:
            return result.get("tenant_access_token")
        else:
            print(f"❌ 获取飞书token失败: {result.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ 飞书认证错误: {e}")
        return None

def get_feishu_records():
    """获取飞书表格所有记录"""
    if not FEISHU_APP_TOKEN or not FEISHU_TABLE_ID:
        print("❌ 请配置 FEISHU_APP_TOKEN 和 FEISHU_TABLE_ID")
        return []

    token = get_feishu_access_token()
    if not token:
        return []

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        all_records = []
        page_token = None

        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            response = requests.get(url, headers=headers, params=params)
            result = response.json()

            if result.get("code") == 0:
                all_records.extend(result.get("data", {}).get("items", []))
                page_token = result.get("data", {}).get("page_token")
                if not page_token:
                    break
            else:
                print(f"❌ 获取飞书记录失败: {result.get('msg')}")
                break

        return all_records
    except Exception as e:
        print(f"❌ 飞书API错误: {e}")
        return []

def create_feishu_record(ip, status, description, timestamp):
    """创建飞书记录"""
    if not FEISHU_APP_TOKEN or not FEISHU_TABLE_ID:
        print("❌ 请配置 FEISHU_APP_TOKEN 和 FEISHU_TABLE_ID")
        return False

    token = get_feishu_access_token()
    if not token:
        return False

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data = {
        "fields": {
            "资产IP": ip,
            "资产状态": status,
            "资产说明": description,
            "状态更新时间": timestamp
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if result.get("code") == 0:
            print(f"   🆕 飞书创建: {ip} -> {status}")
            return True
        else:
            print(f"   ❌ 飞书创建失败: {ip} - {result.get('msg')}")
            return False
    except Exception as e:
        print(f"   ❌ 飞书创建错误: {e}")
        return False

def update_feishu_record(record_id, status, timestamp):
    """更新飞书记录"""
    if not FEISHU_APP_TOKEN or not FEISHU_TABLE_ID:
        print("❌ 请配置 FEISHU_APP_TOKEN 和 FEISHU_TABLE_ID")
        return False

    token = get_feishu_access_token()
    if not token:
        return False

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data = {
        "fields": {
            "资产状态": status,
            "状态更新时间": timestamp
        }
    }

    try:
        response = requests.put(url, headers=headers, json=data)
        result = response.json()
        if result.get("code") == 0:
            print(f"   ✅ 飞书更新: {record_id} -> {status}")
            return True
        else:
            print(f"   ❌ 飞书更新失败: {record_id} - {result.get('msg')}")
            return False
    except Exception as e:
        print(f"   ❌ 飞书更新错误: {e}")
        return False

# ===== 网络扫描 =====

def scan_network(network):
    """扫描指定网段的在线主机"""
    print(f"🔍 正在扫描 {network} 网段...")

    # 检查 nmap 是否可用
    try:
        result = subprocess.run(
            ["nmap", "--version"],
            capture_output=True,
            text=True
        )
        use_nmap = result.returncode == 0
    except:
        use_nmap = False

    if use_nmap:
        print("   使用 nmap 扫描...")
        return scan_with_nmap(network)
    else:
        print("   ⚠️ nmap 未安装，使用 ping 扫描（可能较慢）...")
        return scan_with_ping(network)

def scan_with_nmap(network):
    """使用 nmap 扫描网络"""
    try:
        result = subprocess.run(
            f"nmap -sn {network} -oG -",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )

        online_hosts = []
        for line in result.stdout.split('\n'):
            if 'Up' in line:
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[1]
                    online_hosts.append(ip)

        online_hosts.sort()
        print(f"✅ 发现 {len(online_hosts)} 台在线主机")
        return online_hosts

    except Exception as e:
        print(f"❌ 扫描错误: {e}")
        return []

def scan_with_ping(network):
    """使用 ping 扫描网络（备选方案）"""
    import concurrent.futures
    import ipaddress

    online_hosts = []

    try:
        # 解析网段
        net = ipaddress.ip_network(network, strict=False)
        hosts = list(net.hosts())

        print(f"   开始扫描 {len(hosts)} 个IP地址...")

        def ping_ip(ip):
            try:
                # 使用 ping 命令检测
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", str(ip)],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    return str(ip)
            except:
                pass
            return None

        # 并发 ping
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(ping_ip, hosts))

        # 收集在线主机
        online_hosts = [ip for ip in results if ip is not None]
        online_hosts.sort()

        print(f"✅ 发现 {len(online_hosts)} 台在线主机")
        return online_hosts

    except Exception as e:
        print(f"❌ 扫描错误: {e}")
        return []

def get_current_timestamp():
    """获取当前时间戳（毫秒级）"""
    return int(time.time() * 1000)

# ===== 主流程 =====

def print_help():
    """打印帮助信息"""
    print("=" * 60)
    print("🔌 网络资产扫描工具")
    print("=" * 60)
    print("\n使用方法:")
    print("  python3 network_scan_unified.py [选项]")
    print("\n选项:")
    print("  -h, --help      显示帮助信息")
    print("  --quick         快速扫描模式（不同步到数据源）")
    print("  --scan-only     仅扫描模式（同 --quick）")
    print("\n示例:")
    print("  python3 network_scan_unified.py")
    print("  # 交互式选择模式")
    print("\n  python3 network_scan_unified.py --quick")
    print("  # 快速扫描，不配置数据源")

def get_scan_mode():
    """获取用户选择的扫描模式"""
    print("\n请选择扫描模式:")
    print("  1) 快速扫描 - 仅显示在线主机，不同步到数据源")
    print("  2) 完整同步 - 扫描后同步到 Supabase 和飞书")

    while True:
        choice = input("\n请选择 (1 或 2，默认 1): ").strip()
        if choice == "" or choice == "1":
            return "quick"
        elif choice == "2":
            return "full"
        else:
            print("无效选择，请重新输入")

def main():
    import sys

    # 检查是否需要显示帮助信息
    if '--help' in sys.argv or '-h' in sys.argv:
        print_help()
        return

    # 检查是否是快速扫描模式
    quick_scan = '--quick' in sys.argv or '--scan-only' in sys.argv

    print("=" * 60)
    print("🔌 网络资产扫描 (Supabase + 飞书 双源同步)")
    print("=" * 60)
    print(f"📅 扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查 .env 文件是否存在
    env_file = Path(__file__).parent / ".env"
    has_env = env_file.exists()

    # 如果没有指定模式，且没有 .env 文件，交互式询问
    if not quick_scan and not has_env:
        print("🔍 检测到首次运行！")
        print("=" * 60)
        mode = get_scan_mode()
        if mode == "quick":
            quick_scan = True
            print("\n✅ 已选择快速扫描模式")
        else:
            print("\n✅ 已选择完整同步模式")

    # 如果是完整同步模式，检查/加载配置
    if not quick_scan:
        # 检查配置是否完整，不完整则进入交互式配置
        if not is_config_complete(CONFIG):
            config = interactive_config()
            if config is None:
                print("❌ 配置初始化失败，程序退出")
                exit(1)
            # 重新加载配置
            CONFIG.update(config)
            global SUPABASE_URL, SUPABASE_KEY, FEISHU_APP_TOKEN, FEISHU_TABLE_ID
            global FEISHU_APP_ID, FEISHU_APP_SECRET
            SUPABASE_URL = CONFIG['SUPABASE_URL']
            SUPABASE_KEY = CONFIG['SUPABASE_KEY']
            FEISHU_APP_TOKEN = CONFIG['FEISHU_APP_TOKEN']
            FEISHU_TABLE_ID = CONFIG['FEISHU_TABLE_ID']
            FEISHU_APP_ID = CONFIG['FEISHU_APP_ID']
            FEISHU_APP_SECRET = CONFIG['FEISHU_APP_SECRET']
        print(f"🌐 目标网段: {NETWORK}")
        print("=" * 60)
    else:
        print("🔍 模式: 快速扫描（不同步到数据源）")
        print(f"🌐 目标网段: {NETWORK}")
        print("=" * 60)

    # 1. 扫描网络
    online_hosts = scan_network(NETWORK)
    online_set = set(online_hosts)

    if online_hosts:
        print("\n📋 在线主机列表:")
        for i, ip in enumerate(online_hosts, 1):
            print(f"  {i:2d}. {ip}")
    else:
        print("\n📋 未发现在线主机")

    if quick_scan:
        print("\n✅ 快速扫描完成！")
        return

    # 2. 获取 Supabase 已有记录
    supabase_records = get_supabase_records()
    supabase_ip_map = {r['asset_ip']: r for r in supabase_records}

    print(f"\n📦 Supabase 已有资产: {len(supabase_ip_map)} 条")

    # 3. 更新 Supabase（第一步！）
    print("\n" + "=" * 60)
    print("📊 步骤1: 更新 Supabase（主数据源）")
    print("=" * 60)

    current_time = datetime.utcnow().isoformat() + "Z"
    stats = {'update': 0, 'create': 0, 'offline': 0}

    # 3.1 处理在线主机
    for ip in online_hosts:
        if ip in supabase_ip_map:
            # 已存在，检查状态
            record = supabase_ip_map[ip]
            if record.get('asset_status') != '在线':
                update_supabase_record(record['id'], '在线')
                print(f"   ✅ {ip}: {record.get('asset_status')} -> 在线")
                stats['update'] += 1
            else:
                print(f"   ⏭️  {ip}: 状态已是在线")
        else:
            # 新发现
            create_supabase_record(ip, '新发现设备', '新发现')
            print(f"   🆕 {ip}: 新发现")
            stats['create'] += 1

    # 3.2 处理离线主机
    for ip, record in supabase_ip_map.items():
        if ip not in online_set and record.get('asset_status') == '在线':
            update_supabase_record(record['id'], '离线')
            print(f"   ❌ {ip}: 在线 -> 离线")
            stats['offline'] += 1

    print(f"\n📈 Supabase 更新统计:")
    print(f"   • 在线更新: {stats['update']} 条")
    print(f"   • 新增: {stats['create']} 条")
    print(f"   • 离线标记: {stats['offline']} 条")

    # 4. 同步到飞书（第二步！）- 带去重逻辑
    print("\n" + "=" * 60)
    print("📊 步骤2: 同步到飞书（展示/备份）- 带去重")
    print("=" * 60)

    # 获取飞书已有记录
    feishu_records = get_feishu_records()

    # 构建飞书 IP -> record_id 映射（排除已删除的）
    feishu_ip_map = {}
    for record in feishu_records:
        ip = record.get('fields', {}).get('资产IP', '')
        status = record.get('fields', {}).get('资产状态', '')
        if ip and status != '已删除':
            feishu_ip_map[ip] = {
                'record_id': record.get('record_id', ''),
                'status': status
            }

    print(f"📋 飞书已有资产: {len(feishu_ip_map)} 条")

    # 同步时间戳
    current_timestamp = get_current_timestamp()

    feishu_stats = {'update': 0, 'create': 0, 'offline': 0}

    # 4.1 处理在线主机
    for ip in online_hosts:
        if ip in feishu_ip_map:
            # 已存在，检查状态
            record = feishu_ip_map[ip]
            if record['status'] != '在线':
                update_feishu_record(record['record_id'], '在线', current_timestamp)
                feishu_stats['update'] += 1
            else:
                print(f"   ⏭️  飞书: {ip} 状态已是在线")
        else:
            # 新发现，创建记录
            # 从 Supabase 获取描述
            description = supabase_ip_map.get(ip, {}).get('asset_description', '新发现设备')
            create_feishu_record(ip, '在线', description, current_timestamp)
            feishu_stats['create'] += 1

    # 4.2 处理离线主机
    for ip, info in feishu_ip_map.items():
        if ip not in online_set and info['status'] == '在线':
            update_feishu_record(info['record_id'], '离线', current_timestamp)
            feishu_stats['offline'] += 1

    print(f"\n📈 飞书同步统计:")
    print(f"   • 在线更新: {feishu_stats['update']} 条")
    print(f"   • 新增: {feishu_stats['create']} 条")
    print(f"   • 离线标记: {feishu_stats['offline']} 条")

    # 5. 最终统计
    print("\n" + "=" * 60)
    print("✅ 扫描完成!")
    print("=" * 60)
    print(f"  • 在线主机: {len(online_hosts)} 台")
    print(f"  • Supabase 总资产: {len(supabase_ip_map) + stats['create']} 条")
    print(f"  • 飞书总资产: {len(feishu_ip_map) + feishu_stats['create']} 条")
    print(f"\n  🎯 去重逻辑已生效！")
    print(f"     - 飞书端会检查IP是否已存在")
    print(f"     - 已存在的IP会更新状态，不会重复创建")

    return stats

if __name__ == "__main__":
    main()