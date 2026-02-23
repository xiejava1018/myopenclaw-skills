from skills.webdav.uploader import WebDAVUploader
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw WebDAV访问技能 - main.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

# WebDAV服务器配置
WEBDV_SERVER = "https://your-server.com/webdav"
WEBDV_USER = "xiejava"
WEBDV_PASS = "YOUR_PASSWORD_HERE"

class WebDAVClient:
    """WebDAV客户端类"""
    
    def __init__(self):
        """初始化WebDAV客户端"""
        self.server = WEBDV_SERVER
        self.username = WEBDV_USER
        self.password = WEBDV_PASS
        
    def list_contents(self, remote_path=""):
        """列出目录内容"""
        try:
            target_url = urljoin(self.server, remote_path.lstrip('/'))
            headers = {"Depth": "1"}
            
            response = requests.request("PROPFIND", target_url, 
                                     headers=headers,
                                     auth=(self.username, self.password),
                                     timeout=10,
                                     verify=False)
            
            if response.status_code == 207:
                root = ET.fromstring(response.text)
                contents = []
                
                for response_elem in root.findall("{DAV:}response"):
                    href = response_elem.find("{DAV:}href")
                    if href is not None and href.text:
                        item = href.text
                        if item and item != "/" and item != target_url:
                            relative_path = item.replace(self.server, "").lstrip('/')
                            if relative_path:
                                contents.append(relative_path)
                
                return sorted(contents)
                
            return []
            
        except Exception as e:
            return []
            
    def upload_file(self, local_path, remote_path):
        """上传文件"""
        try:
            if not os.path.exists(local_path):
                return False, "文件不存在"
                
            target_url = urljoin(self.server, remote_path.lstrip('/'))
            
            with open(local_path, 'rb') as f:
                response = requests.put(target_url, data=f,
                                      auth=(self.username, self.password),
                                      timeout=30,
                                      verify=False)
                
                if response.status_code in [201, 204]:
                    return True, "文件上传成功"
                else:
                    return False, f"服务器响应错误: {response.status_code}"
                    
        except Exception as e:
            return False, str(e)
            
    def download_file(self, remote_path, local_path):
        """下载文件"""
        try:
            target_url = urljoin(self.server, remote_path.lstrip('/'))
            
            response = requests.get(target_url,
                                  auth=(self.username, self.password),
                                  timeout=30,
                                  verify=False)
            
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
            return False, str(e)
            
    def delete_file(self, remote_path):
        """删除文件"""
        try:
            target_url = urljoin(self.server, remote_path.lstrip('/'))
            
            response = requests.delete(target_url,
                                     auth=(self.username, self.password),
                                     timeout=10,
                                     verify=False)
            
            if response.status_code in [204, 200]:
                return True, "删除成功"
            else:
                return False, f"服务器响应错误: {response.status_code}"
                
        except Exception as e:
            return False, str(e)
            
    def create_directory(self, remote_path):
        """创建目录"""
        try:
            target_url = urljoin(self.server, remote_path.lstrip('/'))
            
            response = requests.request("MKCOL", target_url,
                                     auth=(self.username, self.password),
                                     timeout=10,
                                     verify=False)
            
            if response.status_code in [201, 204, 405]:
                return True, "目录创建成功"
            else:
                return False, f"服务器响应错误: {response.status_code}"
                
        except Exception as e:
            return False, str(e)

# 全局客户端实例
client = WebDAVClient()

def handle_webdav_command(command):
    """处理WebDAV命令"""
    # 匹配命令模式
    patterns = {
        r"列出NAS共享目录内容|列出NAS目录内容|列出NAS共享目录|列出共享目录内容": lambda cmd, m: handle_list(cmd, None),
        r"列出NAS目录\s*([^\s]*)|列出NAS文件夹\s*([^\s]*)": handle_list,
        r"上传\s*([^\s]*)\s*到NAS\s*([^\s]*)": handle_upload,
        r"下载NAS文件\s*([^\s]*)\s*到\s*([^\s]*)": handle_download,
        r"删除NAS文件\s*([^\s]*)|删除NAS文件\s*([^\s]*)": handle_delete,
        r"创建NAS目录\s*([^\s]*)|在NAS上创建\s*([^\s]*)目录|创建NAS文件夹\s*([^\s]*)": handle_create_dir,
    }
    
    for pattern, handler in patterns.items():
        match = re.search(pattern, command)
        if match:
            return handler(command, match)
    
    # 默认命令
    if "NAS" in command or "WebDAV" in command:
        return handle_default()
        
    return "❌ 无法识别的WebDAV命令。请使用：列出NAS目录、上传文件、下载NAS文件、删除NAS文件、创建NAS目录等操作。"

def handle_list(command, match):
    """处理列出操作"""
    if match:
        remote_path = "".join(filter(None, match.groups())).strip()
        if remote_path and remote_path != "None":
            contents = client.list_contents(remote_path)
            if contents:
                result = f"📁 NAS目录 '{remote_path}' 的内容：\n"
                for item in contents:
                    result += f"   - {item}\n"
                return result.rstrip()
            else:
                return f"📂 NAS目录 '{remote_path}' 为空或无法访问"
    
    contents = client.list_contents()
    if contents:
        result = "📁 NAS共享目录的内容：\n"
        for item in contents:
            result += f"   - {item}\n"
        return result.rstrip()
    else:
        return "📂 NAS共享目录为空"

def handle_upload(command, match):
    """处理上传操作"""
    local_path = match.group(1).strip()
    remote_path = match.group(2).strip()
    
    if remote_path and not remote_path.endswith("/") and "." in remote_path.split("/")[-1]:
        success, message = client.upload_file(local_path, remote_path)
    else:
        remote_filename = os.path.basename(local_path)
        remote_path = os.path.join(remote_path.rstrip("/"), remote_filename)
        success, message = client.upload_file(local_path, remote_path)
        
    if success:
        return f"✅ 文件 '{local_path}' 上传到 '{remote_path}' 成功"
    else:
        return f"❌ 上传失败: {message}"

def handle_download(command, match):
    """处理下载操作"""
    remote_path = match.group(1).strip()
    local_path = match.group(2).strip()
    
    if local_path and os.path.isdir(local_path):
        remote_filename = os.path.basename(remote_path)
        local_path = os.path.join(local_path, remote_filename)
        
    success, message = client.download_file(remote_path, local_path)
    
    if success:
        return f"✅ NAS文件 '{remote_path}' 下载到 '{local_path}' 成功"
    else:
        return f"❌ 下载失败: {message}"

def handle_delete(command, match):
    """处理删除操作"""
    remote_path = match.group(1).strip()
    
    if remote_path.endswith("目录") or remote_path.endswith("文件夹"):
        remote_path = remote_path.rsplit(" ", 1)[0]
        
    success, message = client.delete_file(remote_path)
    
    if success:
        return f"✅ NAS文件 '{remote_path}' 删除成功"
    else:
        return f"❌ 删除失败: {message}"

def handle_create_dir(command, match):
    """处理创建目录操作"""
    directory_name = "".join(filter(None, match.groups())).strip()
    
    if directory_name:
        success, message = client.create_directory(directory_name)
        
        if success:
            return f"✅ NAS目录 '{directory_name}' 创建成功"
        else:
            return f"❌ 目录创建失败: {message}"
    else:
        return "❌ 请指定要创建的目录名称"

def handle_default():
    """处理默认情况"""
    return ("📋 WebDAV访问技能使用说明：\n"
            "🔹 列出NAS目录：列出NAS共享目录内容、列出NAS目录 test_dir\n"
            "🔹 上传文件：上传 /local/path/file.txt 到NAS remote/path/file.txt\n"
            "🔹 下载文件：下载NAS remote/path/file.txt 到 /local/path\n"
            "🔹 删除文件：删除NAS remote/path/file.txt\n"
            "🔹 创建目录：在NAS上创建目录 new_dir、创建NAS文件夹 test")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        print(handle_webdav_command(command))
    else:
        test_commands = [
            "列出NAS共享目录内容",
            "创建NAS测试目录",
            "列出NAS测试目录",
        ]
        
        for cmd in test_commands:
            print(f"\n🔍 测试命令：{cmd}")
            print("-" * 30)
            print(handle_webdav_command(cmd))
