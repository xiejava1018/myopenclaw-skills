#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw WebDAV 访问技能 - main.py

支持：文件上传/下载/删除/目录操作/属性查询/test连接
配置通过 .env 文件或环境变量管理。
"""

import os
import sys
import re
import logging
import argparse
import hashlib
import time
from pathlib import Path
from urllib.parse import unquote, quote

import requests
import xml.etree.ElementTree as ET
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# ===== 日志配置 =====

logger = logging.getLogger("webdav")
_DEBUG = False


def _setup_logging(debug=False):
    global _DEBUG
    _DEBUG = debug
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    if not debug:
        # 抑制 requests/urllib3 的乏余 INFO 日志
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


# ===== 配置管理 =====

SKILL_DIR = Path(__file__).parent.parent


def is_config_complete(config):
    """检查配置是否完整"""
    required_fields = ["WEBDAV_SERVER", "WEBDAV_USERNAME", "WEBDAV_PASSWORD"]
    for field in required_fields:
        value = config.get(field, "").strip()
        if not value or value.startswith("your_"):
            return False
    return True


def get_input(prompt, default=""):
    """获取用户输入，支持默认值"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    try:
        value = input(prompt).strip()
    except (EOFError, UnicodeDecodeError):
        value = ""
    return value if value else default


def validate_config(key, value):
    """验证配置值"""
    if key == "WEBDAV_SERVER" and value:
        if not value.startswith(("http://", "https://")):
            print("  ⚠️  服务器地址应以 http:// 或 https:// 开头")
    return True


def test_connection(server, username, password, verify_ssl, method="PROPFIND"):
    """测试 WebDAV 连接是否可用，返回 (success, status_code, message)"""
    try:
        response = requests.request(
            method, server,
            headers={"Depth": "0"},
            auth=requests.auth.HTTPBasicAuth(username, password),
            timeout=10,
            verify=verify_ssl,
        )
        if response.status_code in (200, 207, 403):
            return True, response.status_code, "连接成功"
        return False, response.status_code, f"服务器返回 {response.status_code}"
    except requests.exceptions.SSLError:
        return False, 0, "SSL 证书验证失败，请确认服务器地址是否使用 HTTPS，或将 WEBDAV_SSL_VERIFY 设为 false"
    except requests.exceptions.ConnectTimeout:
        return False, 0, "连接超时，请检查服务器地址是否正确"
    except requests.exceptions.ConnectionError as e:
        return False, 0, f"连接失败: {e}"
    except Exception as e:
        return False, 0, f"未知错误: {e}"


def interactive_config(existing_config=None):
    """交互式配置初始化向导"""
    print()
    print("🔧 首次使用 WebDAV 技能，开始配置初始化")
    print("=" * 60)
    print("请根据提示输入 WebDAV 服务器的配置信息")
    print("按 Enter 可使用方括号中的默认值")
    print("=" * 60)

    config = existing_config.copy() if existing_config else {}

    print()
    print("-" * 60)
    print("WebDAV 服务器配置")
    print("- 地址格式: https://your-nas-server.com:5006")
    print("- 可在 NAS 管理界面 -> WebDAV 服务中查看")
    print("-" * 60)
    config["WEBDAV_SERVER"] = get_input(
        "请输入 WebDAV 服务器地址",
        config.get("WEBDAV_SERVER", "https://192.168.0.1:5006"),
    )
    validate_config("WEBDAV_SERVER", config["WEBDAV_SERVER"])

    config["WEBDAV_USERNAME"] = get_input(
        "请输入用户名",
        config.get("WEBDAV_USERNAME", ""),
    )
    validate_config("WEBDAV_USERNAME", config["WEBDAV_USERNAME"])

    config["WEBDAV_PASSWORD"] = get_input(
        "请输入密码",
        config.get("WEBDAV_PASSWORD", ""),
    )
    validate_config("WEBDAV_PASSWORD", config["WEBDAV_PASSWORD"])

    print()
    print("-" * 60)
    print("安全配置")
    print("-" * 60)
    default_ssl = "true" if config.get("WEBDAV_SSL_VERIFY", True) else "false"
    ssl_input = get_input("是否验证 SSL 证书？(true/false)", default_ssl)
    config["WEBDAV_SSL_VERIFY"] = ssl_input.lower() in ("true", "yes", "1", "y")

    # 连接测试
    print()
    print("🔍 正在测试连接...")
    connected, code, msg = test_connection(
        config["WEBDAV_SERVER"],
        config["WEBDAV_USERNAME"],
        config["WEBDAV_PASSWORD"],
        config["WEBDAV_SSL_VERIFY"],
    )
    status_icon = "✅" if connected else "⚠️"
    print(f"  {status_icon} {msg} (HTTP {code})")

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
    try:
        confirm = get_input("配置是否正确？(y/n)", "y").lower()
    except EOFError:
        confirm = "y"
    if confirm != "y":
        print("🔄 重新配置...")
        return interactive_config(config)

    # 保存到 .env 文件
    env_file = SKILL_DIR / ".env"
    try:
        with open(env_file, "w", encoding="utf-8") as f:
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
    """加载配置：环境变量 > .env 文件"""
    config = {}

    env_file = SKILL_DIR / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    config["WEBDAV_SERVER"] = os.environ.get("WEBDAV_SERVER", "")
    config["WEBDAV_USERNAME"] = os.environ.get("WEBDAV_USERNAME", "")
    config["WEBDAV_PASSWORD"] = os.environ.get("WEBDAV_PASSWORD", "")
    config["WEBDAV_SSL_VERIFY"] = os.environ.get(
        "WEBDAV_SSL_VERIFY", "true"
    ).lower() in ("true", "yes", "1", "y")

    return config


# ===== 路径规范化 =====

def normalize_path(path):
    """规范化路径：去除首尾空白和多余斜杠，首部斜杠不保留（相对路径风格）"""
    if not path:
        return ""
    # 去除空白
    path = path.strip()
    # 去除首部 /
    path = path.lstrip("/")
    # 合并多余斜杠
    while "//" in path:
        path = path.replace("//", "/")
    return path


def build_url(server, remote_path):
    """构建完整 URL，自动处理路径规范化"""
    path = normalize_path(remote_path)
    server = server.rstrip("/")
    if path:
        return f"{server}/{quote(path, safe='/')}"
    return server


# ===== 认证 =====

class DigestAuth(requests.auth.HTTPDigestAuth):
    """Digest Auth，支持 qop=auth 模式"""

    def __init__(self, username, password):
        super().__init__(username, password)

    def handler(self, response, request):
        # Digest Auth 降级到 Basic Auth
        return requests.auth.HTTPBasicAuth(self.username, self.password).handler(
            response, request
        )


def try_auth(method, url, auth, **kwargs):
    """尝试用 Digest Auth 请求，失败后降级为 Basic Auth"""
    for auth_cls, label in [
        (requests.auth.HTTPBasicAuth, "Basic"),
        (requests.auth.HTTPDigestAuth, "Digest"),
    ]:
        auth_instance = auth_cls(auth.username, auth.password)
        try:
            resp = requests.request(method, url, auth=auth_instance, timeout=kwargs.get("timeout", 30), **kwargs)
            logger.debug(f"[{label}] {method} {url} -> {resp.status_code}")
            return resp
        except requests.exceptions.RequestException:
            continue
    # 全都失败，尝试 Basic
    return requests.request(method, url, auth=requests.auth.HTTPBasicAuth(auth.username, auth.password), timeout=kwargs.get("timeout", 30), **kwargs)


# ===== WebDAV 客户端 =====

class WebDAVClient:
    """WebDAV 客户端，支持文件上传/下载/删除/目录操作"""

    def __init__(self, server=None, username=None, password=None, verify_ssl=None):
        config = load_config()

        self.server = (server or config.get("WEBDAV_SERVER", "")).rstrip("/")
        self.username = username or config.get("WEBDAV_USERNAME", "")
        self.password = password or config.get("WEBDAV_PASSWORD", "")
        self.verify_ssl = (
            verify_ssl if verify_ssl is not None else config.get("WEBDAV_SSL_VERIFY", True)
        )

        if not self.verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        effective_config = {
            "WEBDAV_SERVER": self.server,
            "WEBDAV_USERNAME": self.username,
            "WEBDAV_PASSWORD": self.password,
        }

        if not is_config_complete(effective_config):
            print("⚠️  WebDAV 配置不完整")
            new_config = interactive_config()
            if new_config is None:
                raise RuntimeError("WebDAV 配置失败")
            self.server = new_config["WEBDAV_SERVER"].rstrip("/")
            self.username = new_config["WEBDAV_USERNAME"]
            self.password = new_config["WEBDAV_PASSWORD"]
            self.verify_ssl = new_config.get("WEBDAV_SSL_VERIFY", True)

        # 构建带重试的 session
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._auth = requests.auth.HTTPBasicAuth(self.username, self.password)

    def _request(self, method, remote_path, headers=None, data=None, timeout=10):
        """统一请求方法，自动处理路径和认证"""
        url = build_url(self.server, remote_path)
        headers = headers or {}
        logger.debug(f"[_request] {method} {url}")
        resp = self.session.request(
            method, url,
            headers=headers,
            data=data,
            auth=self._auth,
            timeout=timeout,
            verify=self.verify_ssl,
        )
        logger.debug(f"[response] {resp.status_code} | {len(resp.content)} bytes")
        return resp

    def test_connection(self):
        """测试连接，返回 (success, status_code, message)"""
        return test_connection(
            self.server,
            self.username,
            self.password,
            self.verify_ssl,
        )

    def list_contents(self, remote_path=""):
        """列出目录内容"""
        try:
            response = self._request(
                "PROPFIND", remote_path,
                headers={"Depth": "1"},
                timeout=10,
            )

            if response.status_code == 207:
                root = ET.fromstring(response.text)
                req_prefix = normalize_path(remote_path)
                contents = []

                for resp_elem in root.findall("{DAV:}response"):
                    href_elem = resp_elem.find("{DAV:}href")
                    if href_elem is None or not href_elem.text:
                        continue
                    href = unquote(href_elem.text).lstrip("/")
                    # 跳过请求路径本身
                    if href == req_prefix or href == req_prefix + "/":
                        continue
                    # 提取相对路径
                    if req_prefix:
                        prefix_with_slash = req_prefix + "/"
                        if href.startswith(prefix_with_slash):
                            relative = href[len(prefix_with_slash):]
                        else:
                            continue
                    else:
                        if href.startswith(normalize_path(self.server).lstrip("/")):
                            relative = href[len(normalize_path(self.server).lstrip("/")):].lstrip("/")
                        else:
                            relative = href
                    if relative:
                        contents.append(relative)

                return sorted(set(contents))

            logger.warning(f"列出目录返回意外状态: {response.status_code}")
            return []

        except Exception as e:
            logger.error(f"列出目录失败: {e}")
            return []

    def get_file_info(self, remote_path):
        """获取文件/目录属性"""
        try:
            response = self._request(
                "PROPFIND", remote_path,
                headers={"Depth": "0"},
                timeout=10,
            )

            if response.status_code in (200, 207):
                root = ET.fromstring(response.text)
                info = {"path": remote_path}

                for resp_elem in root.findall("{DAV:}response"):
                    propstat = resp_elem.find("{DAV:}propstat")
                    if propstat is None:
                        continue
                    prop = propstat.find("{DAV:}prop")
                    if prop is None:
                        continue
                    for tag in [
                        "{DAV:}getcontentlength",
                        "{DAV:}getlastmodified",
                        "{DAV:}getcontenttype",
                        "{DAV:}resourcetype",
                    ]:
                        elem = prop.find(tag)
                        if elem is not None:
                            key = tag.split("}")[1]
                            if key == "resourcetype":
                                info[key] = (
                                    "directory"
                                    if elem.find("{DAV:}collection") is not None
                                    else "file"
                                )
                            else:
                                info[key] = elem.text
                return info

            return None

        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            return None

    def upload_file(self, local_path, remote_path, progress=True):
        """上传文件，支持进度显示"""
        try:
            if not os.path.exists(local_path):
                return False, f"文件不存在: {local_path}"
            if not os.path.isfile(local_path):
                return False, f"不是有效的文件: {local_path}"

            file_size = os.path.getsize(local_path)
            filename = os.path.basename(local_path)
            url = build_url(self.server, remote_path)

            def gen():
                with open(local_path, "rb") as f:
                    uploaded = 0
                    chunk_size = 64 * 1024  # 64KB
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        uploaded += len(chunk)
                        yield chunk
                        if progress and file_size > 0:
                            pct = min(uploaded / file_size * 100, 100)
                            bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
                            sys.stdout.write(f"\r  上传 {filename}: [{bar}] {pct:.1f}%")
                            sys.stdout.flush()
                if progress and file_size > 0:
                    sys.stdout.write("\n")
                    sys.stdout.flush()

            response = self.session.put(
                url,
                data=gen(),
                auth=self._auth,
                timeout=max(30, file_size // (256 * 1024) + 30),
                verify=self.verify_ssl,
            )

            if response.status_code in (201, 204):
                return True, f"文件上传成功 ({_format_size(file_size)})"
            return False, f"服务器响应错误: {response.status_code}"

        except Exception as e:
            logger.error(f"上传失败: {e}")
            return False, str(e)

    def download_file(self, remote_path, local_path, progress=True):
        """下载文件，支持进度显示"""
        try:
            url = build_url(self.server, remote_path)

            # 先获取文件大小
            head_resp = self.session.head(url, auth=self._auth, timeout=10, verify=self.verify_ssl)
            file_size = int(head_resp.headers.get("Content-Length", 0)) if head_resp.status_code == 200 else 0

            response = self.session.get(
                url,
                auth=self._auth,
                timeout=30,
                verify=self.verify_ssl,
                stream=True,
            )

            if response.status_code == 200:
                local_dir = os.path.dirname(local_path)
                if local_dir and not os.path.exists(local_dir):
                    os.makedirs(local_dir, exist_ok=True)

                downloaded = 0
                chunk_size = 64 * 1024
                filename = os.path.basename(remote_path)
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress and file_size > 0:
                                pct = min(downloaded / file_size * 100, 100)
                                bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
                                sys.stdout.write(f"\r  下载 {filename}: [{bar}] {pct:.1f}%")
                                sys.stdout.flush()
                if progress and file_size > 0:
                    sys.stdout.write("\n")
                    sys.stdout.flush()

                return True, f"文件下载成功 ({_format_size(downloaded)})"
            return False, f"服务器响应错误: {response.status_code}"

        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False, str(e)

    def delete_file(self, remote_path):
        """删除文件或目录"""
        try:
            response = self._request("DELETE", remote_path, timeout=10)
            if response.status_code in (204, 200, 404):
                return True, "删除成功"
            return False, f"服务器响应错误: {response.status_code}"
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False, str(e)

    def create_directory(self, remote_path):
        """创建目录"""
        try:
            response = self._request("MKCOL", remote_path, timeout=10)
            if response.status_code in (201, 204, 405):
                return True, "目录创建成功"
            return False, f"服务器响应错误: {response.status_code}"
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return False, str(e)


# ===== 工具函数 =====

def _format_size(size):
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    else:
        return f"{size / 1024 / 1024 / 1024:.2f} GB"


# ===== 命令处理 =====

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = WebDAVClient()
    return _client


def _clear_client():
    """清除客户端缓存，强制重新初始化"""
    global _client
    _client = None


def handle_webdav_command(command):
    """处理 WebDAV 命令"""
    client = _get_client()

    # 结构化命令
    struct_match = re.match(r"^(\w+)(?:\s+(.*))?", command)
    if struct_match:
        action = struct_match.group(1).lower()
        params_str = struct_match.group(2) or ""
        params = {}
        for pair in params_str.split():
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v

        handlers = {
            "list": lambda: handle_list(client, params.get("path", "")),
            "test": lambda: handle_test(client),
            "ping": lambda: handle_test(client),
            "upload": lambda: handle_upload(client, params.get("local", ""), params.get("remote", "")),
            "download": lambda: handle_download(client, params.get("remote", ""), params.get("local", "")),
            "delete": lambda: handle_delete(client, params.get("path", "")),
            "mkdir": lambda: handle_create_dir(client, params.get("path", "")),
            "info": lambda: handle_file_info(client, params.get("path", "")),
        }

        if action in handlers:
            return handlers[action]()

    # 自然语言命令
    patterns = [
        (r"^(列出NAS共享目录内容|列出共享目录内容|列出NAS目录内容|列出NAS共享目录)$",
         lambda cmd, m: handle_list(client, "")),
        (r"^(列出|查看)NAS[目录文件夹]*\s*(.+)$",
         lambda cmd, m: handle_list(client, m.group(2).strip())),
        (r"^上传\s+([^\s]+)\s+到NAS\s+(.+)$",
         lambda cmd, m: handle_upload_nlp(client, m.group(1).strip(), m.group(2).strip())),
        (r"^上传\s+([^\s]+)\s+(.+)$",
         lambda cmd, m: handle_upload_nlp(client, m.group(1).strip(), m.group(2).strip())),
        (r"^(下载|获取)NAS文件\s+(.+?)\s+到\s+(.+)$",
         lambda cmd, m: handle_download_nlp(client, m.group(2).strip(), m.group(3).strip())),
        (r"^删除NAS[文件目录]*\s+(.+)$",
         lambda cmd, m: handle_delete(client, m.group(1).strip())),
        (r"^创建NAS[目录文件夹]+\s+(.+)$",
         lambda cmd, m: handle_create_dir(client, m.group(1).strip())),
        (r"^查看NAS文件\s+(.+?)\s*(?:的信息|信息)$",
         lambda cmd, m: handle_file_info(client, m.group(1).strip())),
        (r"^(test|ping|测试|检测|连接)$",
         lambda cmd, m: handle_test(client)),
    ]

    for pattern, handler in patterns:
        match = re.search(pattern, command)
        if match:
            return handler(command, match)

    return _handle_default()


# ===== 命令处理函数 =====

def handle_list(client, path):
    contents = client.list_contents(normalize_path(path))
    label = f"NAS目录 '{path}'" if path else "NAS共享目录"
    if contents:
        result = f"📁 {label} 的内容：\n"
        for item in contents:
            result += f"   - {item}\n"
        return result.rstrip()
    return f"📂 {label} 为空或无法访问"


def handle_test(client):
    """测试连接"""
    success, code, msg = client.test_connection()
    if success:
        return f"✅ WebDAV 连接正常\n   服务器: {client.server}\n   用户名: {client.username}\n   HTTP 状态: {code}\n   SSL 验证: {'开启' if client.verify_ssl else '关闭'}"
    return f"❌ WebDAV 连接失败\n   {msg}\n   请检查配置或重新运行交互式配置"


def handle_upload(client, local_path, remote_path):
    if not local_path:
        return "❌ 请指定本地文件路径 (local=...)\n   例如: upload local=/tmp/file.txt remote=folder/file.txt"
    if not remote_path:
        remote_path = os.path.basename(local_path)
    return _do_upload(client, local_path, remote_path)


def handle_upload_nlp(client, local_path, remote_path):
    # remote_path 可能是 "openclaw_sharedoc/xxx.pdf" 或 "openclaw_sharedoc/"
    # 如果 remote_path 末尾是 /，则拼接文件名
    if remote_path.endswith("/"):
        remote_path = os.path.join(remote_path.rstrip("/"), os.path.basename(local_path))
    return _do_upload(client, local_path, remote_path)


def _do_upload(client, local_path, remote_path):
    """执行上传（local_path 保持原样，remote_path 需规范化）"""
    success, message = client.upload_file(
        local_path,
        normalize_path(remote_path),
    )
    if success:
        return f"✅ {message}"
    return f"❌ 上传失败: {message}"


def handle_download(client, remote_path, local_path):
    if not remote_path:
        return "❌ 请指定远程文件路径 (remote=...)\n   例如: download remote=folder/file.txt local=/tmp/file.txt"
    if not local_path:
        local_path = os.path.basename(remote_path)
    return _do_download(client, remote_path, local_path)


def handle_download_nlp(client, remote_path, local_path):
    if os.path.isdir(local_path):
        local_path = os.path.join(local_path, os.path.basename(remote_path))
    return _do_download(client, remote_path, local_path)


def _do_download(client, remote_path, local_path):
    """执行下载（remote_path 需规范化，local_path 保持原样）"""
    success, message = client.download_file(
        normalize_path(remote_path),
        local_path,
    )
    if success:
        return f"✅ {message}"
    return f"❌ 下载失败: {message}"


def handle_delete(client, path):
    if not path:
        return "❌ 请指定要删除的文件/目录路径"
    success, message = client.delete_file(normalize_path(path))
    if success:
        return f"✅ {message}"
    return f"❌ 删除失败: {message}"


def handle_create_dir(client, path):
    if not path:
        return "❌ 请指定要创建的目录名称"
    success, message = client.create_directory(normalize_path(path))
    if success:
        return f"✅ {message}"
    return f"❌ 目录创建失败: {message}"


def handle_file_info(client, path):
    if not path:
        return "❌ 请指定要查看的文件路径"
    info = client.get_file_info(normalize_path(path))
    if info:
        result = f"📄 文件信息：\n"
        for key, value in info.items():
            if key == "getcontentlength" and value:
                value = f"{value} 字节 ({_format_size(int(value))})"
            result += f"   {key}: {value}\n"
        return result.rstrip()
    return f"❌ 无法获取 '{path}' 的信息"


def _handle_default():
    return (
        "📋 WebDAV 访问技能使用说明：\n"
        "\n"
        "🔹 结构化命令（推荐）：\n"
        "   list path=<目录>           列出目录内容\n"
        "   test / ping                测试连接\n"
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
        "   配置文件: ~/.claude/skills/webdav/.env\n"
        "   删除 .env 后重新运行即可触发配置向导\n"
        "   使用 --debug 参数可查看详细日志"
    )


# ===== CLI 入口 =====

def main():
    parser = argparse.ArgumentParser(
        description="WebDAV 访问技能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug", action="store_true", help="启用调试日志"
    )
    parser.add_argument(
        "--config", action="store_true", help="重新运行交互式配置向导"
    )
    parser.add_argument(
        "command", nargs="*", help="WebDAV 命令，空白参数启动交互模式"
    )

    args = parser.parse_args()
    _setup_logging(args.debug)

    if args.config:
        _clear_client()
        config = load_config()
        interactive_config(config)
        return

    if not args.command:
        print(_handle_default())
        return

    command = " ".join(args.command)
    result = handle_webdav_command(command)
    print(result)


if __name__ == "__main__":
    main()
