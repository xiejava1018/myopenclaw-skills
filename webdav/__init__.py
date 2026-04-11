#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV 访问技能包初始化
"""

from .main import (
    handle_webdav_command as handle,
    WebDAVClient,
    test_connection,
    load_config,
    interactive_config,
    normalize_path,
    build_url,
)

__version__ = "1.1.0"
__author__ = "OpenClaw"
__description__ = "WebDAV 文件共享服务访问技能"

__all__ = [
    "handle",
    "WebDAVClient",
    "test_connection",
    "load_config",
    "interactive_config",
    "normalize_path",
    "build_url",
]

SKILL_INFO = {
    "name": "webdav",
    "description": "WebDAV 文件共享服务访问技能，支持上传/下载/删除/列出/目录/测试连接",
    "version": __version__,
    "author": __author__,
    "requires": ["requests"],
    "emoji": "📁",
}
