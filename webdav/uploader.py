#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV文件上传器 - 使用curl命令实现
"""

import subprocess
import tempfile
import os

class WebDAVUploader:
    """使用curl命令实现的WebDAV文件上传器"""
    
    def __init__(self, url=None, username=None, password=None):
        """初始化上传器"""
        # 从环境变量或配置文件读取
        import json
        
        if not all([url, username, password]):
            # 优先从环境变量读取
            url = url or os.environ.get('WEBDAV_SERVER')
            username = username or os.environ.get('WEBDAV_USERNAME')
            password = password or os.environ.get('WEBDAV_PASSWORD')
            
            # 如果环境变量不存在，从config.json读取
            if not all([url, username, password]):
                config_path = os.path.join(os.path.dirname(__file__), 'config.json')
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        webdav_config = config_data.get('config', {})
                        url = url or webdav_config.get('server')
                        username = username or webdav_config.get('username')
                        password = password or webdav_config.get('password')
        
        self.url = url.rstrip("/") if url else ""
        self.username = username
        self.password = password
        
    def upload(self, local_path, remote_path):
        """
        上传文件
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程路径
            
        Returns:
            (成功, 消息)
        """
        try:
            if not os.path.exists(local_path):
                return False, f"本地文件不存在: {local_path}"
                
            if not os.path.isfile(local_path):
                return False, f"{local_path}不是有效的文件"
                
            # 构建远程URL
            remote_url = f"{self.url}/{remote_path.lstrip('/')}"
            
            # 使用curl命令上传
            command = [
                "curl",
                "-T", local_path,
                "-u", f"{self.username}:{self.password}",
                "--insecure",
                "-v",
                remote_url
            ]
            
            result = subprocess.run(command, 
                                  capture_output=True, 
                                  text=True,
                                  timeout=30)
            
            if result.returncode == 0 and "201" in result.stderr:
                return True, f"文件上传成功: {remote_path}"
            else:
                error_msg = f"服务器返回代码: {result.returncode}"
                if result.stderr:
                    error_msg += f"\n错误信息: {result.stderr}"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "上传超时"
        except Exception as e:
            return False, f"上传失败: {e}"
            
    def test_connection(self):
        """测试连接是否正常"""
        try:
            test_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
            test_file.write(b"Connection test file")
            test_file.close()
            
            test_path = "test_connection.txt"
            
            success, message = self.upload(test_file.name, test_path)
            
            if success:
                # 上传成功，删除测试文件
                delete_command = [
                    "curl",
                    "-X", "DELETE",
                    "-u", f"{self.username}:{self.password}",
                    "--insecure",
                    f"{self.url}/{test_path}"
                ]
                subprocess.run(delete_command, 
                             capture_output=True, 
                             text=True,
                             timeout=10)
                
                os.unlink(test_file.name)
                return True, "连接成功"
                
            else:
                os.unlink(test_file.name)
                return False, message
                
        except Exception as e:
            if 'test_file' in locals() and os.path.exists(test_file.name):
                os.unlink(test_file.name)
            return False, f"连接失败: {e}"

if __name__ == "__main__":
    print("🚀 测试WebDAV上传器")
    print("=" * 50)
    
    uploader = WebDAVUploader()
    
    # 测试连接
    print("🔍 测试连接...")
    success, message = uploader.test_connection()
    print(f"📡 连接状态: {'✅' if success else '❌'}")
    print(f"📄 消息: {message}")
    
    if success:
        # 测试文件上传
        print("\n🔍 测试文件上传...")
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        temp_file.write(b"WebDAV uploader test file")
        temp_file.close()
        
        remote_path = "test_directory/test_uploader_file.txt"
        success, message = uploader.upload(temp_file.name, remote_path)
        
        print(f"📄 上传状态: {'✅' if success else '❌'}")
        print(f"📄 消息: {message}")
        
        os.unlink(temp_file.name)
        
        if success:
            print("\n✅ 文件上传成功！")
            
            # 列出目录内容确认
            print("\n📁 test_directory目录内容:")
            from skills.webdav.main import WebDAVClient
            import urllib.parse
            client = WebDAVClient()
            contents = client.list_contents("openclaw_sharedoc/test_directory")
            for item in contents:
                decoded_item = urllib.parse.unquote(item)
                print(f"   - {decoded_item}")
                
    print("\n" + "=" * 50)
    print("✅ WebDAV上传器测试完成！")
