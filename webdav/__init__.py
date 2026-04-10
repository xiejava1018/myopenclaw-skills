#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV 访问技能包初始化
"""

from .main import handle_webdav_command as handle, WebDAVClient

__version__ = "1.0.0"
__author__ = "OpenClaw"
__description__ = "WebDAV 文件共享服务访问技能"

# 导出主要功能
__all__ = ['handle', 'WebDAVClient']

# 技能注册信息
SKILL_INFO = {
    "name": "webdav",
    "description": "WebDAV 文件共享服务访问技能",
    "version": __version__,
    "author": __author__,
    "requires": ["requests"],
    "emoji": "📁"
}
