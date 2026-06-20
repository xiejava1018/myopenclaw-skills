"""scheme-writer 配置加载器。

职责：
- 从 $HOME/.claude/scheme-writer/.env 优先加载
- 备选工作区根 .env（便于临时调试）
- 提供 get_config() 与 require(var_name)
- 提供 KB_ALIASES（口语化名 → kb_id）的 JSON 序列化读写
- 不在 import 副作用中读取真实 Key，仅在调用时按需加载
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

KB_ALIASES_KEY = "KB_ALIASES"
SOURCES_KEY = "SOURCES"
DEFAULT_SOURCE_KEY = "DEFAULT_SOURCE"


def _find_env_path() -> Path | None:
    """按优先级返回第一个存在的 .env 路径。"""
    user = Path.home() / ".claude" / "scheme-writer" / ".env"
    workspace = Path.cwd() / ".env"
    for path in (user, workspace):
        if path.is_file():
            return path
    return None


def _load_env_file(path: Path) -> dict[str, str]:
    """极简 .env 解析：KEY=VALUE；忽略空行与 # 注释；不做引号剥离。"""
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


class ConfigError(Exception):
    """配置缺失或解析错误。"""


def get_config() -> dict[str, str]:
    """返回当前生效的配置（合并 .env 文件值与进程环境变量，进程环境优先）。

    不抛异常；若一个 .env 都找不到，返回空字典（调用方按需 require）。

    KB_ALIASES（JSON 字符串）作为原始字符串键返回，不在 get_config 里解析。
    需要 dict 形式请用 get_aliases()。
    """
    return _load_merged_env()


def _load_merged_env() -> dict[str, str]:
    """合并 .env 文件 + 进程环境变量（进程环境优先）。"""
    merged: dict[str, str] = {}
    env_path = _find_env_path()
    if env_path is not None:
        merged.update(_load_env_file(env_path))
    for key in (
        "KNOWLEDGE_BASE_URL",
        "KNOWLEDGE_BASE_API_KEY",
        "DEFAULT_RETRIEVE_KB",
        "DEFAULT_UPLOAD_KB",
        KB_ALIASES_KEY,
        "SOURCES",
        "DEFAULT_SOURCE",
    ):
        val = os.environ.get(key)
        if val is not None:
            merged[key] = val
    return merged


def get_aliases() -> dict[str, str]:
    """返回口语化名 → kb_id 的映射。无配置或解析失败时返回空 dict。

    KB_ALIASES 缺失 → {}
    KB_ALIASES 解析成功 → dict
    KB_ALIASES 不是合法 JSON → {} + stderr 警告
    """
    raw = get_config().get(KB_ALIASES_KEY, "")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"[kb_config] {KB_ALIASES_KEY} 不是合法 JSON，已忽略: {exc}\n"
        )
        return {}
    if not isinstance(parsed, dict):
        sys.stderr.write(
            f"[kb_config] {KB_ALIASES_KEY} 解析结果不是 dict，已忽略\n"
        )
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def get_sources() -> list[dict[str, Any]]:
    """解析 SOURCES JSON 数组为来源 dict 列表。

    每条 {'name','url','api_key','group'}；缺字段的条目丢弃并 stderr 告警。
    非法 JSON → [] + 告警。
    """
    raw = get_config().get(SOURCES_KEY, "")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[kb_config] {SOURCES_KEY} 不是合法 JSON，已忽略: {exc}\n")
        return []
    if not isinstance(parsed, list):
        sys.stderr.write(f"[kb_config] {SOURCES_KEY} 不是 JSON 数组，已忽略\n")
        return []
    result: list[dict[str, Any]] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        url = str(entry.get("url", "")).strip()
        api_key = str(entry.get("api_key", "")).strip()
        if not (name and url and api_key):
            sys.stderr.write(
                f"[kb_config] 丢弃不完整来源条目: name={entry.get('name')!r}"
                f"（缺 name/url/api_key 之一）\n"
            )
            continue
        group_val = entry.get("group")
        group = None
        if group_val is not None:
            group = str(group_val).strip() or None
        result.append(
            {
                "name": name,
                "url": url,
                "api_key": api_key,
                "group": group,
            }
        )
    return result


def set_aliases(mapping: dict[str, str], path: Path | None = None) -> Path:
    """把别名映射序列化后写入 .env 的 KB_ALIASES 字段。

    复用 write_env：先读出当前 .env 中的其他键，合并新值后整文件覆写。
    返回写入的 .env 路径。

    写入目标选择（与 init.py --set 保持一致）：
    - 显式传入 path → 用 path
    - 已有 .env 命中工作区 → 用工作区
    - 其它情况 → 用工作区 .env（不污染用户级 ~/.claude/scheme-writer/.env）
    """
    if path is None:
        workspace = Path.cwd() / ".env"
        existing = config_path()
        path = existing if (existing is not None and existing == workspace) else workspace
    flat = _load_merged_env()
    flat[KB_ALIASES_KEY] = json.dumps(mapping, ensure_ascii=False, sort_keys=True)
    return write_env(flat, path=path)


def require(var_name: str) -> str:
    """取配置项；缺失则抛 ConfigError。

    这是其他脚本调用 WeKnora 前的统一闸口，避免每个脚本都重复判空。
    """
    cfg = get_config()
    val = cfg.get(var_name, "").strip()
    if not val:
        raise ConfigError(
            f"缺少必需配置 {var_name}。请运行 `python scripts/init.py` 完成首次配置，"
            f"或设置环境变量 {var_name}。"
        )
    return val


def config_path() -> Path | None:
    """返回当前生效的 .env 路径（用于 init 提示）。"""
    return _find_env_path()


def write_env(values: dict[str, str], path: Path | None = None) -> Path:
    """把 values 写入 .env（覆盖）。返回写入的路径。

    用于 init.py。已有的 .env 会在 init.py 内部备份，这里只负责写。
    默认路径为 $HOME/.claude/scheme-writer/.env。
    """
    target = path if path is not None else Path.home() / ".claude" / "scheme-writer" / ".env"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# scheme-writer configuration (auto-generated by init.py)",
        "",
    ]
    for key, value in values.items():
        lines.append(f"{key}={value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
