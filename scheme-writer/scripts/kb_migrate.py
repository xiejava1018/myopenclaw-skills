"""scheme-writer: 旧单实例配置 → 多来源自动迁移。

触发：SOURCES 缺失但存在旧 KNOWLEDGE_BASE_URL + KNOWLEDGE_BASE_API_KEY。
动作：合成 default 来源 + DEFAULT_SOURCE=default + 旧别名加 default/ 前缀 + .env.bak 备份。
幂等：已迁移（有 SOURCES）则不动。

安全：备份写 .env.bak；旧 key 保留在 .env（不再被读取，留作回滚线索）。
本模块不向 stdout/stderr 打印 api_key——合成来源时直接序列化进 SOURCES JSON 落盘。
"""
from __future__ import annotations

import json
from pathlib import Path

import kb_config

DEFAULT_NAME = "default"


def needs_migration() -> bool:
    """是否需要迁移：SOURCES 缺/空 且 旧 URL+KEY 都在。"""
    cfg = kb_config.get_config()
    if cfg.get(kb_config.SOURCES_KEY, "").strip():
        return False
    return bool(
        cfg.get("KNOWLEDGE_BASE_URL", "").strip()
        and cfg.get("KNOWLEDGE_BASE_API_KEY", "").strip()
    )


def migrate(path: Path | None = None) -> list[str]:
    """执行迁移，返回变更的键列表；无需迁移返回 []。

    path 显式指定写入目标；否则用 config_path()（用户级优先，工作区回退）。
    返回值只含键名（如 ["SOURCES","DEFAULT_SOURCE","KB_ALIASES"]），不含任何明文 key。
    """
    if not needs_migration():
        return []

    cfg = kb_config._load_merged_env()
    target = Path(path) if path else (kb_config.config_path() or (Path.cwd() / ".env"))

    # 备份（迁移前原始内容，字节级拷贝）
    if Path(target).is_file():
        bak = Path(target).with_name(Path(target).name + ".bak")
        bak.write_bytes(Path(target).read_bytes())

    flat: dict[str, str] = dict(cfg)
    src = {
        "name": DEFAULT_NAME,
        "url": cfg["KNOWLEDGE_BASE_URL"].strip(),
        "api_key": cfg["KNOWLEDGE_BASE_API_KEY"].strip(),
        "group": None,
    }
    flat[kb_config.SOURCES_KEY] = json.dumps([src], ensure_ascii=False)
    flat[kb_config.DEFAULT_SOURCE_KEY] = DEFAULT_NAME
    changed = [kb_config.SOURCES_KEY, kb_config.DEFAULT_SOURCE_KEY]

    # 旧别名加 default/ 前缀（已含 / 的不动）。
    # 非法 JSON → 不写 KB_ALIASES 键。write_env 是整文件覆写（只写 flat 里的键），
    # 故 flat 缺 KB_ALIASES_KEY 等效于别名清空——符合"降级为空"。
    raw_aliases = cfg.get(kb_config.KB_ALIASES_KEY, "").strip()
    if raw_aliases:
        try:
            old = json.loads(raw_aliases)
        except json.JSONDecodeError:
            old = None
        if isinstance(old, dict):
            new: dict[str, str] = {}
            for k, v in old.items():
                key = k if "/" in k else f"{DEFAULT_NAME}/{k}"
                new[key] = v
            flat[kb_config.KB_ALIASES_KEY] = json.dumps(new, ensure_ascii=False)
            if new != old:
                changed.append(kb_config.KB_ALIASES_KEY)

    kb_config.write_env(flat, path=Path(target))
    return changed
