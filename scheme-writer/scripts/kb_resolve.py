"""scheme-writer: 来源与 kb 引用解析层。

把用户/CLI 传入的 kb 引用解析成 (source_name, kb_id) 对。
所有 kb_*.py 通过本模块确定要访问哪个来源的哪个库。

解析规则（详见 docs/plans/2026-06-20-multi-source-design.md §4.1）：
- 来源/库名（限定别名）：命中 KB_ALIASES → (prefix, alias_kb_id)
- 来源/kb_id（限定字面）：前缀是已知来源但非别名 → (prefix, kb_id)
- 库名（裸名）：后缀唯一命中别名 → 解析；多命中 → 歧义报错（铁律三：不猜）
- kb_id（裸字面）：source 由 --source 或 DEFAULT_SOURCE 决定，都无则报错
"""
from __future__ import annotations

import kb_config
from kb_http import KbError


def _known_source_names() -> set[str]:
    return {s["name"] for s in kb_config.get_sources()}


def resolve_source(explicit: str | None) -> str:
    """确定来源：--source 显式 > DEFAULT_SOURCE/单源隐式 > 报错。

    explicit 非空时必须存在于 SOURCES，否则 KbError。
    """
    if explicit:
        if explicit not in _known_source_names():
            raise KbError("bad_args", f"未知来源: {explicit}")
        return explicit
    name = kb_config.resolve_default_source()
    if not name:
        raise kb_config.ConfigError(
            "无法确定来源：存在多个来源且未配置 DEFAULT_SOURCE，请用 --source 指定。"
        )
    return name


def resolve_kb_ref(ref: str, explicit_source: str | None) -> tuple[str, str]:
    """单个 kb 引用 → (source_name, kb_id)。"""
    aliases = kb_config.get_aliases()
    names = _known_source_names()

    # 形态 1：限定别名（ref 正好是某个别名键）
    if ref in aliases:
        src = ref.split("/", 1)[0]
        return (src, aliases[ref])
    # 形态 2：限定字面 source/kb_id（含 / 且前缀是已知来源）
    if "/" in ref:
        src, _, kb_id = ref.partition("/")
        if src in names:
            return (src, kb_id)
        raise KbError("bad_args", f"未知来源前缀: {src}（引用: {ref}）")
    # 形态 3：裸名（后缀匹配别名键）
    matches = [k for k in aliases if k.endswith("/" + ref)]
    if len(matches) == 1:
        src = matches[0].split("/", 1)[0]
        return (src, aliases[matches[0]])
    if len(matches) > 1:
        raise KbError(
            "bad_args",
            f"裸名 '{ref}' 在多个来源歧义: {matches}；请用 '来源/{ref}' 明确。",
        )
    # 形态 4：裸字面 kb_id
    return (resolve_source(explicit_source), ref)


def resolve_kb_refs(refs_csv: str, explicit_source: str | None) -> list[tuple[str, str]]:
    """逗号分隔的多个 kb 引用 → [(source_name, kb_id), ...]。"""
    out: list[tuple[str, str]] = []
    for raw in refs_csv.split(","):
        ref = raw.strip()
        if not ref:
            continue
        out.append(resolve_kb_ref(ref, explicit_source))
    if not out:
        raise KbError("bad_args", "--kb 不能为空")
    return out
