"""Provider 抽象：上传原语接口固定为 upload(local_path, key) -> UploadResult。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UploadResult:
    backend: str
    key: str          # 图床上的对象路径
    url: str          # 完整访问 URL
    extra: dict = field(default_factory=dict)


class Uploader(ABC):
    """后端上传器基类。子类实现 upload()。"""
    backend_name: str = ""

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def upload(self, local_path: str, key: str) -> UploadResult:
        """上传本地文件到图床 key，返回 UploadResult。"""
        raise NotImplementedError


def get_uploader(backend: str, config) -> Uploader:
    """按 backend 懒加载并实例化上传器（避免未用后端的 SDK 被强制 import）。"""
    if backend == "qiniu":
        from .qiniu import QiniuUploader
        return QiniuUploader(config)
    if backend == "github":
        from .github import GithubUploader
        return GithubUploader(config)
    raise ValueError(f"未知后端: {backend!r}，支持: qiniu, github")


def normalize_domain(domain: str) -> str:
    """去掉尾部斜杠，便于拼接 key。"""
    return (domain or "").rstrip("/")


def join_url(domain: str, key: str) -> str:
    """domain + '/' + key，处理前导斜杠。"""
    return f"{normalize_domain(domain)}/{key.lstrip('/')}"


def supported_backends() -> list[str]:
    return ["qiniu", "github"]
