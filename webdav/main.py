#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw WebDAV 访问技能 - main.py

支持交互式首次配置、文件上传/下载/删除、目录操作等功能。
配置通过 .env 文件或环境变量管理。
"""

import os
import sys
import re
import logging
from pathlib import Path
from urllib.parse import unquote

import requests
import xml.etree.ElementTree as ET
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 日志配置
logger = logging.getLogger("webdav")

# ===== 配置管理 =====

SKILL_DIR = Path(__file__).parent


def is_config_complete(config):
    """检查配置是否完整"""
    required_fields = ['WEBDAV_SERVER', 'WEBDAV_USERNAME', 'WEBDAV_PASSWORD']
    for field in required_fields:
        value = config.get(field, '').strip()
        if not value or value.startswith('your_'):
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
    """验证配置值，返回 True 表示通过（仅警告，不阻止）"""
    if key == 'WEBDAV_SERVER' and value:
        if not value.startswith(('http://', 'https://')):
            print(f"  ⚠️  服务器地址应以 http:// 或 https:// 开头")
    elif key == 'WEBDAV_USERNAME' and value:
        if len(value) < 1:
            print(f"  ⚠️  用户名不能为空")
    elif key == 'WEBDAV_PASSWORD' and value:
        if len(value) < 1:
            print(f"  ⚠️  密码不能为空")
    return True


def test_connection(server, username, password, verify_ssl):
    """测试 WebDAV 连接是否可用"""
    try:
        response = requests.request(
            "PROPFIND", server,
            headers={"Depth": "0"},
            auth=(username, password),
            timeout=10,
            verify=verify_ssl,
        )
        return response.status_code in (200, 207, 403)
    except Exception as e:
        logger.debug(f"连接测试失败: {e}")
        return False


def interactive_config():
    """交互式配置初始化向导"""
    print()
    print("🔧 首次使用 WebDAV 技能，开始配置初始化")
    print("=" * 60)
    print("请根据提示输入 WebDAV 服务器的配置信息")
    print("按 Enter 可使用方括号中的默认值")
    print("=" * 60)

    config = {}

    print()
    print("-" * 60)
    print("WebDAV 服务器配置")
    print("- 地址格式: https://your-nas-server.com/webdav")
    print("- 可在 NAS 管理界面 -> WebDAV 服务中查看")
    print("-" * 60)
    config['WEBDAV_SERVER'] = get_input("请输入 WebDAV 服务器地址")
    validate_config('WEBDAV_SERVER', config['WEBDAV_SERVER'])

    config['WEBDAV_USERNAME'] = get_input("请输入用户名")
    validate_config('WEBDAV_USERNAME', config['WEBDAV_USERNAME'])

    config['WEBDAV_PASSWORD'] = get_input("请输入密码")
    validate_config('WEBDAV_PASSWORD', config['WEBDAV_PASSWORD'])

    print()
    print("-" * 60)
    print("安全配置")
    print("-" * 60)
    ssl_input = get_input("是否验证 SSL 证书？(true/false)", "true")
    config['WEBDAV_SSL_VERIFY'] = ssl_input.lower() in ('true', 'yes', '1', 'y')

    # 连接测试
    print()
    print("🔍 正在测试连接...")
    connected = test_connection(
        config['WEBDAV_SERVER'],
        config['WEBDAV_USERNAME'],
        config['WEBDAV_PASSWORD'],
        config['WEBDAV_SSL_VERIFY'],
    )
    if connected:
        print("  ✅ 连接成功！")
    else:
        print("  ⚠️  连接测试失败，请检查配置是否正确")

    # 摘要确认
    print()
    print("=" * 60)
    print("配置信息摘要")
    print("=" * 60)
    print(f"  服务器地址:   {config['WEBDAV_SERVER']}")
    print(f"  用户名:       {config['WEBDAV_USERNAME']}")
    print(f"  密码:         {'*' * len(config['WEBDAV_PASSWORD'])}")
    print(f"  SSL 验证:     {'开启' if config['WEBDAV_SSL_VERIFY'] else '关闭'}")
    print(f"  连接状态:     {'成功' if connected else '失败'}")

    print()
    confirm = get_input("配置是否正确？(y/n)", "y").lower()
    if confirm != 'y':
        print("🔄 重新配置...")
        return interactive_config()

    # 保存到 .env 文件
    env_file = SKILL_DIR / ".env"
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("# WebDAV 服务器配置\n")
            f.write(f"WEBDAV_SERVER={config['WEBDAV_SERVER']}\n")
            f.write(f"WEBDAV_USERNAME={config['WEBDAV_USERNAME']}\n")
            f.write(f"WEBDAV_PASSWORD={config['WEBDAV_PASSWORD']}\n")
            f.write(f"WEBDAV_SSL_VERIFY={'true' if config['WEBDAV_SSL_VERIFY'] else 'false'}\n")
        print(f"✅ 配置已保存到 {env_file}")
        return config
    except Exception as e:
        print(f"❌ 配置保存失败: {e}")
        return None


def load_config():
    """加载配置：环境变量 > .env 文件 > 交互式配置"""
    config = {}

    # 加载 .env 文件到环境变量
    env_file = SKILL_DIR / ".env"
    if env_file.exists():
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

    config['WEBDAV_SERVER'] = os.environ.get('WEBDAV_SERVER', '')
    config['WEBDAV_USERNAME'] = os.environ.get('WEBDAV_USERNAME', '')
    config['WEBDAV_PASSWORD'] = os.environ.get('WEBDAV_PASSWORD', '')
    config['WEBDAV_SSL_VERIFY'] = os.environ.get('WEBDAV_SSL_VERIFY', 'true').lower() in ('true', 'yes', '1', 'y')

    return config


# ===== WebDAV 客户端 =====

class WebDAVClient:
    """WebDAV 客户端，支持文件和目录操作"""

    def __init__(self, server=None, username=None, password=None, verify_ssl=None):
        """初始化客户端

        优先使用传入参数，否则从配置加载。配置不完整时触发交互式配置。
        """
        config = load_config()

        self.server = (server or config.get('WEBDAV_SERVER', '')).rstrip('/')
        self.username = username or config.get('WEBDAV_USERNAME', '')
        self.password = password or config.get('WEBDAV_PASSWORD', '')
        self.verify_ssl = verify_ssl if verify_ssl is not None else config.get('WEBDAV_SSL_VERIFY', True)

        # SSL 验证关闭时抑制 InsecureRequestWarning
        if not self.verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 检查配置完整性
        effective_config = {
            'WEBDAV_SERVER': self.server,
            'WEBDAV_USERNAME': self.username,
            'WEBDAV_PASSWORD': self.password,
        }

        if not is_config_complete(effective_config):
            print("⚠️  WebDAV 配置不完整")
            new_config = interactive_config()
            if new_config is None:
                raise RuntimeError("WebDAV 配置失败")
            self.server = new_config['WEBDAV_SERVER'].rstrip('/')
            self.username = new_config['WEBDAV_USERNAME']
            self.password = new_config['WEBDAV_PASSWORD']
            self.verify_ssl = new_config.get('WEBDAV_SSL_VERIFY', True)

        # 构建带重试机制的 session
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _url(self, remote_path=""):
        """构建完整 URL，避免 urljoin 的路径截断问题"""
        path = remote_path.lstrip('/')
        if path:
            return f"{self.server}/{path}"
        return self.server

    def list_contents(self, remote_path=""):
        """列出目录内容"""
        try:
            target_url = self._url(remote_path)
            response = self.session.request(
                "PROPFIND", target_url,
                headers={"Depth": "1"},
                auth=(self.username, self.password),
                timeout=10,
                verify=self.verify_ssl,
            )

            if response.status_code == 207:
                root = ET.fromstring(response.text)
                # 请求的路径前缀，用于计算相对路径
                request_prefix = remote_path.lstrip('/')
                contents = []

                for resp_elem in root.findall("{DAV:}response"):
                    href_elem = resp_elem.find("{DAV:}href")
                    if href_elem is not None and href_elem.text:
                        href = unquote(href_elem.text)
                        # 转为纯路径比较
                        href_path = href.lstrip('/')
                        # 排除自身（请求的目录本身）
                        if href_path == request_prefix or href_path == request_prefix + '/':
                            continue
                        # 提取相对于请求路径的子项
                        if request_prefix and href_path.startswith(request_prefix + '/'):
                            relative = href_path[len(request_prefix) + 1:]
                        elif not request_prefix:
                            # 列根目录时，取 server 路径之后的部分
                            if href.startswith(self.server):
                                relative = href[len(self.server):].lstrip('/')
                            else:
                                relative = href_path
                        else:
                            relative = href_path
                        if relative:
                            contents.append(relative)

                return sorted(set(contents))

            return []

        except Exception as e:
            logger.error(f"列出目录失败: {e}")
            return []

    def get_file_info(self, remote_path):
        """获取文件/目录属性信息"""
        try:
            target_url = self._url(remote_path)
            response = self.session.request(
                "PROPFIND", target_url,
                headers={"Depth": "0"},
                auth=(self.username, self.password),
                timeout=10,
                verify=self.verify_ssl,
            )

            if response.status_code in (200, 207):
                root = ET.fromstring(response.text)
                info = {"path": remote_path}

                for resp_elem in root.findall("{DAV:}response"):
                    propstat = resp_elem.find("{DAV:}propstat")
                    if propstat is not None:
                        prop = propstat.find("{DAV:}prop")
                        if prop is not None:
                            # 提取常见属性
                            for tag in ["{DAV:}getcontentlength", "{DAV:}getlastmodified",
                                        "{DAV:}getcontenttype", "{DAV:}resourcetype"]:
                                elem = prop.find(tag)
                                if elem is not None:
                                    key = tag.split('}')[1]
                                    if key == "resourcetype":
                                        info[key] = "directory" if elem.find("{DAV:}collection") is not None else "file"
                                    else:
                                        info[key] = elem.text

                return info

            return None

        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            return None

    def upload_file(self, local_path, remote_path):
        """上传文件"""
        try:
            if not os.path.exists(local_path):
                return False, f"文件不存在: {local_path}"

            if not os.path.isfile(local_path):
                return False, f"不是有效的文件: {local_path}"

            target_url = self._url(remote_path)

            with open(local_path, 'rb') as f:
                response = self.session.put(
                    target_url, data=f,
                    auth=(self.username, self.password),
                    timeout=30,
                    verify=self.verify_ssl,
                )

            if response.status_code in (201, 204):
                return True, "文件上传成功"
            else:
                return False, f"服务器响应错误: {response.status_code}"

        except Exception as e:
            logger.error(f"上传失败: {e}")
            return False, str(e)

    def download_file(self, remote_path, local_path):
        """下载文件"""
        try:
            target_url = self._url(remote_path)

            response = self.session.get(
                target_url,
                auth=(self.username, self.password),
                timeout=30,
                verify=self.verify_ssl,
            )

            if response.status_code == 200:
                local_dir = os.path.dirname(local_path)
                if local_dir and not os.path.exists(local_dir):
                    os.makedirs(local_dir, exist_ok=True)

                with open(local_path, 'wb') as f:
                    f.write(response.content)

                return True, "文件下载成功"
            else:
                return False, f"服务器响应错误: {response.status_code}"

        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False, str(e)

    def delete_file(self, remote_path):
        """删除文件或目录"""
        try:
            target_url = self._url(remote_path)

            response = self.session.delete(
                target_url,
                auth=(self.username, self.password),
                timeout=10,
                verify=self.verify_ssl,
            )

            if response.status_code in (204, 200):
                return True, "删除成功"
            else:
                return False, f"服务器响应错误: {response.status_code}"

        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False, str(e)

    def create_directory(self, remote_path):
        """创建目录"""
        try:
            target_url = self._url(remote_path)

            response = self.session.request(
                "MKCOL", target_url,
                auth=(self.username, self.password),
                timeout=10,
                verify=self.verify_ssl,
            )

            if response.status_code in (201, 204, 405):
                return True, "目录创建成功"
            else:
                return False, f"服务器响应错误: {response.status_code}"

        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return False, str(e)


# ===== 命令处理 =====

# 全局客户端实例（延迟初始化）
_client = None


def _get_client():
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = WebDAVClient()
    return _client


def handle_webdav_command(command):
    """处理 WebDAV 命令（支持自然语言和结构化调用）"""
    client = _get_client()

    # 结构化参数调用：action + keyword args
    # 例如: handle_webdav_command("list path=test_dir")
    struct_match = re.match(r'^(\w+)(?:\s+(.*))?', command)
    if struct_match:
        action = struct_match.group(1).lower()
        params_str = struct_match.group(2) or ''

        # 解析 key=value 参数
        params = {}
        for pair in params_str.split():
            if '=' in pair:
                k, v = pair.split('=', 1)
                params[k] = v

        handlers = {
            'list': lambda: handle_list(client, params.get('path', '')),
            'upload': lambda: handle_upload(client, params.get('local', ''), params.get('remote', '')),
            'download': lambda: handle_download(client, params.get('remote', ''), params.get('local', '')),
            'delete': lambda: handle_delete(client, params.get('path', '')),
            'mkdir': lambda: handle_create_dir(client, params.get('path', '')),
            'info': lambda: handle_file_info(client, params.get('path', '')),
        }

        if action in handlers:
            return handlers[action]()

    # 自然语言命令（兼容层）
    patterns = {
        r"列出NAS共享目录内容|列出NAS目录内容|列出NAS共享目录|列出共享目录内容":
            lambda cmd, m: handle_list(client, ''),
        r"列出NAS目录\s*([^\s]*)|列出NAS文件夹\s*([^\s]*)":
            lambda cmd, m: handle_list(client, "".join(filter(None, m.groups())).strip()),
        r"上传\s*([^\s]+)\s*到NAS\s*([^\s]+)":
            lambda cmd, m: handle_upload_nlp(client, m),
        r"下载NAS文件\s*([^\s]+)\s*到\s*([^\s]+)":
            lambda cmd, m: handle_download_nlp(client, m),
        r"删除NAS文件\s*([^\s]+)|删除NAS目录\s*([^\s]+)":
            lambda cmd, m: handle_delete(client, "".join(filter(None, m.groups())).strip()),
        r"创建NAS目录\s*([^\s]+)|在NAS上创建\s*([^\s]*)目录|创建NAS文件夹\s*([^\s]+)":
            lambda cmd, m: handle_create_dir(client, "".join(filter(None, m.groups())).strip()),
        r"查看NAS文件\s*([^\s]+)\s*的信息|获取NAS文件\s*([^\s]+)\s*的属性":
            lambda cmd, m: handle_file_info(client, "".join(filter(None, m.groups())).strip()),
    }

    for pattern, handler in patterns.items():
        match = re.search(pattern, command)
        if match:
            return handler(command, match)

    if "NAS" in command or "WebDAV" in command or "webdav" in command.lower():
        return handle_default()

    return "❌ 无法识别的 WebDAV 命令。请使用：list、upload、download、delete、mkdir、info 等操作。"


def handle_list(client, path):
    """处理列出操作"""
    contents = client.list_contents(path)
    label = f"NAS目录 '{path}'" if path else "NAS共享目录"
    if contents:
        result = f"📁 {label} 的内容：\n"
        for item in contents:
            result += f"   - {item}\n"
        return result.rstrip()
    else:
        return f"📂 {label} 为空或无法访问"


def handle_upload_nlp(client, match):
    """处理自然语言上传操作"""
    local_path = match.group(1).strip()
    remote_path = match.group(2).strip()

    if remote_path and not remote_path.endswith("/") and "." in remote_path.split("/")[-1]:
        pass  # remote_path 已是完整文件路径
    else:
        remote_filename = os.path.basename(local_path)
        remote_path = os.path.join(remote_path.rstrip("/"), remote_filename)

    return _do_upload(client, local_path, remote_path)


def handle_upload(client, local_path, remote_path):
    """处理结构化上传操作"""
    if not local_path:
        return "❌ 请指定本地文件路径 (local=...)"
    if not remote_path:
        remote_path = os.path.basename(local_path)
    return _do_upload(client, local_path, remote_path)


def _do_upload(client, local_path, remote_path):
    """执行上传"""
    success, message = client.upload_file(local_path, remote_path)
    if success:
        return f"✅ 文件 '{local_path}' 上传到 '{remote_path}' 成功"
    else:
        return f"❌ 上传失败: {message}"


def handle_download_nlp(client, match):
    """处理自然语言下载操作"""
    remote_path = match.group(1).strip()
    local_path = match.group(2).strip()

    if local_path and os.path.isdir(local_path):
        remote_filename = os.path.basename(remote_path)
        local_path = os.path.join(local_path, remote_filename)

    return _do_download(client, remote_path, local_path)


def handle_download(client, remote_path, local_path):
    """处理结构化下载操作"""
    if not remote_path:
        return "❌ 请指定远程文件路径 (remote=...)"
    if not local_path:
        local_path = os.path.basename(remote_path)
    return _do_download(client, remote_path, local_path)


def _do_download(client, remote_path, local_path):
    """执行下载"""
    success, message = client.download_file(remote_path, local_path)
    if success:
        return f"✅ NAS文件 '{remote_path}' 下载到 '{local_path}' 成功"
    else:
        return f"❌ 下载失败: {message}"


def handle_delete(client, path):
    """处理删除操作"""
    if not path:
        return "❌ 请指定要删除的文件/目录路径"
    success, message = client.delete_file(path)
    if success:
        return f"✅ NAS文件 '{path}' 删除成功"
    else:
        return f"❌ 删除失败: {message}"


def handle_create_dir(client, path):
    """处理创建目录操作"""
    if not path:
        return "❌ 请指定要创建的目录名称"
    success, message = client.create_directory(path)
    if success:
        return f"✅ NAS目录 '{path}' 创建成功"
    else:
        return f"❌ 目录创建失败: {message}"


def handle_file_info(client, path):
    """处理获取文件信息操作"""
    if not path:
        return "❌ 请指定要查看的文件路径"
    info = client.get_file_info(path)
    if info:
        result = f"📄 文件信息：\n"
        for key, value in info.items():
            result += f"   {key}: {value}\n"
        return result.rstrip()
    else:
        return f"❌ 无法获取 '{path}' 的信息"


def handle_default():
    """默认帮助信息"""
    return (
        "📋 WebDAV 访问技能使用说明：\n"
        "\n"
        "🔹 结构化命令（推荐）：\n"
        "   list path=<目录>           列出目录内容\n"
        "   upload local=<本地> remote=<远程>  上传文件\n"
        "   download remote=<远程> local=<本地>  下载文件\n"
        "   delete path=<路径>         删除文件/目录\n"
        "   mkdir path=<目录>          创建目录\n"
        "   info path=<路径>           查看文件信息\n"
        "\n"
        "🔹 自然语言命令（兼容）：\n"
        "   列出NAS共享目录内容\n"
        "   列出NAS目录 test_dir\n"
        "   上传 /local/file.txt 到NAS remote/path/\n"
        "   下载NAS文件 remote/file.txt 到 /local/path\n"
        "   删除NAS文件 remote/file.txt\n"
        "   创建NAS目录 new_dir\n"
        "   查看NAS文件 info.txt 的信息\n"
        "\n"
        "🔹 配置管理：\n"
        "   首次使用会自动引导配置 WebDAV 服务器信息\n"
        "   配置保存在 .env 文件中，删除后可重新配置"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        print(handle_webdav_command(command))
    else:
        print(handle_default())
