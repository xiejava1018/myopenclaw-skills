"""配置加载：所有参数从 .env 读取，完全自包含，无 PicGo 运行时依赖。"""
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 未装时退化为不加载 .env（依赖系统环境变量）
    load_dotenv = None

SKILL_DIR = Path(__file__).resolve().parent
ENV_FILE = SKILL_DIR / ".env"

# 七牛区域代号（与 PicGo / qiniu SDK 一致）
QINIU_AREAS = {"z0": "华东", "z1": "华北", "z2": "华南", "na0": "北美", "as0": "东南亚"}


@dataclass
class Config:
    default_backend: str = "qiniu"
    # 七牛
    qiniu_access_key: str = ""
    qiniu_secret_key: str = ""
    qiniu_bucket: str = ""
    qiniu_domain: str = ""
    qiniu_area: str = "z0"
    qiniu_path: str = "blog"
    # GitHub
    gh_token: str = ""
    gh_owner: str = ""
    gh_repo: str = ""
    gh_branch: str = "main"
    gh_path: str = "blog"
    gh_domain: str = ""

    def prefix_for(self, backend: str) -> str:
        return self.qiniu_path if backend == "qiniu" else self.gh_path

    def validate(self, backend: str) -> list[str]:
        """返回缺失必填项的列表（空列表=配置齐全）。"""
        missing = []
        if backend == "qiniu":
            for k, label in [
                ("qiniu_access_key", "QINIU_ACCESS_KEY"),
                ("qiniu_secret_key", "QINIU_SECRET_KEY"),
                ("qiniu_bucket", "QINIU_BUCKET"),
                ("qiniu_domain", "QINIU_DOMAIN"),
            ]:
                if not getattr(self, k):
                    missing.append(label)
        elif backend == "github":
            for k, label in [
                ("gh_token", "GH_TOKEN"),
                ("gh_owner", "GH_OWNER"),
                ("gh_repo", "GH_REPO"),
            ]:
                if not getattr(self, k):
                    missing.append(label)
        return missing


def load_config(env_file: Path = ENV_FILE) -> Config:
    if load_dotenv is not None and Path(env_file).exists():
        load_dotenv(env_file)

    def g(key: str, default: str = "") -> str:
        return os.environ.get(key, default)

    return Config(
        default_backend=g("DEFAULT_BACKEND", "qiniu"),
        qiniu_access_key=g("QINIU_ACCESS_KEY"),
        qiniu_secret_key=g("QINIU_SECRET_KEY"),
        qiniu_bucket=g("QINIU_BUCKET"),
        qiniu_domain=g("QINIU_DOMAIN"),
        qiniu_area=g("QINIU_AREA", "z0"),
        qiniu_path=g("QINIU_PATH", "blog"),
        gh_token=g("GH_TOKEN"),
        gh_owner=g("GH_OWNER"),
        gh_repo=g("GH_REPO"),
        gh_branch=g("GH_BRANCH", "main"),
        gh_path=g("GH_PATH", "blog"),
        gh_domain=g("GH_DOMAIN"),
    )
