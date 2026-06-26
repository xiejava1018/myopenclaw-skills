"""manifest.py —— 按文件内容 sha256 索引的图床账本，多后端分桶。

数据结构（见设计文档第 10 节）：
    {
        "<sha256>": {
            "local": "/abs/path/architecture.png",
            "qiniu":  {"key": "blog/.../architecture.png", "url": "https://..."},
            "github": {"key": "blog/.../architecture.png", "url": "https://..."},
        }
    }

纯逻辑模块，无网络/无第三方依赖，可直接单测。
"""
import hashlib
import json
import os
from pathlib import Path


def sha256_of_file(path) -> str:
    """读取文件二进制内容，返回 sha256 十六进制摘要。

    接受 str 或 Path；文件不存在时由 open() 自然抛 FileNotFoundError。
    """
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class Manifest:
    """图床 manifest：内容哈希查表 + 多后端分桶持久化。"""

    def __init__(self, path):
        # 存路径并初始化空数据；文件已存在则加载
        self.path = Path(path)
        self.data = {}
        if self.path.exists():
            self.load()

    def load(self) -> None:
        """从 self.path 读 JSON 到 self.data。

        容错：文件缺失 / JSON 解析失败 / 顶层非 dict → self.data = {}，不抛异常。
        """
        try:
            raw = self.path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            self.data = {}
            return
        # 顶层必须是 dict，否则视为损坏
        self.data = parsed if isinstance(parsed, dict) else {}

    def get(self, hash: str, backend: str):
        """返回 {"key":..,"url":..} 或 None。hash 或 backend 未记录 → None。"""
        return self.data.get(hash, {}).get(backend)

    def put(self, hash: str, backend: str, local: str, key: str, url: str) -> None:
        """记录一条上传结果。已存在则覆盖（更新）。"""
        entry = self.data.setdefault(hash, {})
        entry["local"] = local
        entry[backend] = {"key": key, "url": url}

    def save(self) -> None:
        """原子写：先写 .tmp 再 os.replace，避免中途崩溃损坏 manifest。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)
