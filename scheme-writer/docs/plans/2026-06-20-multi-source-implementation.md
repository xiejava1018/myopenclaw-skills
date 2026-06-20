# scheme-writer 多来源支持 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 scheme-writer 支持配置并检索多个 WeKnora 来源（多实例 / 多空间），解决 kb_id 跨空间撞名，老用户零摩擦迁移。

**Architecture:** 来源 = `(name, url, api_key)` 扁平清单（`SOURCES`）；别名升级为 `来源/库名 → kb_id`（来源作用域）；新增 `kb_resolve.py` 解析层把 kb 引用解析成 `(source, kb_id)` 对；各脚本通过解析层访问对应来源；单来源时行为/输出逐字节退化到现状。

**Tech Stack:** Python 3.10+ / pytest / requests；现有 `kb_config.py` / `kb_http.py` / `init.py` / `kb_*.py`。

**设计依据:** `scheme-writer/docs/plans/2026-06-20-multi-source-design.md`（已评审）。

**仓库优先:** 所有改动落在 `myopenclaw-skills/scheme-writer/`（仓库源），完成后由用户同步到 `~/.claude/skills/scheme-writer/`。

---

## 依赖与并行图

```
Phase 0（顺序，基础层，必须先完成并提交）
  T1 kb_config: SOURCES/DEFAULT_SOURCE 读写
  T2 kb_config: 单来源隐式 + get_source
  T3 kb_resolve.py: 解析层（resolve_source / resolve_kb_ref / resolve_kb_refs）
  T4 迁移逻辑（旧 key → default 源 + 别名加前缀，幂等）
       │
       ▼
Phase 1（并行 ✓ — 4 个子代理各改一个脚本+其测试，互不碰对方文件）
  T5 kb_list   T6 kb_docs   T7 kb_search   T8 kb_upload
       │
       ▼
Phase 2（顺序）
  T9 init.py: --add-source/--set-sources/--remove-source/--set-default-source/--list-sources + --status/--show 适配
       │
       ▼
Phase 3（顺序）
  T10 SKILL.md 更新    T11 全量测试 + 集成回归
```

**并行规则:** Phase 1 的 T5–T8 互独立（各自只动 `scripts/kb_X.py` + `tests/test_kb_X.py`），可派 4 个子代理同时做。前提：Phase 0 已提交、`kb_resolve` 与 `kb_config.get_sources/get_source` 可用。

**TDD 节奏（每个任务内）:** 写失败测试 → 跑确认失败 → 最小实现 → 跑确认通过 → 提交。

**测试运行:** `cd myopenclaw-skills/scheme-writer && python -m pytest tests/ -v`（或单文件 `python -m pytest tests/test_kb_config.py -v`）。

**提交规范:** conventional commits，无 attribution（用户全局已禁用）。每个任务结束提交一次。

---

# Phase 0 — 基础层（顺序）

## Task 1: kb_config 支持 SOURCES / DEFAULT_SOURCE 读写

**Files:**
- Modify: `scripts/kb_config.py`（`_load_merged_env` 白名单 + 新增 `get_sources`/序列化）
- Test: `tests/test_kb_config.py`

### Step 1: 写失败测试（追加到 test_kb_config.py）

```python
# --- SOURCES / DEFAULT_SOURCE（多来源支持）---

def _write_env(tmp_path, text):
    (tmp_path / ".env").write_text(text, encoding="utf-8")


def test_get_sources_empty_when_missing(tmp_path):
    _write_env(tmp_path, "KNOWLEDGE_BASE_URL=http://x\n")
    assert kb_config.get_sources() == []


def test_get_sources_parses_json(tmp_path):
    _write_env(
        tmp_path,
        'SOURCES=['
        '{"name":"a","url":"http://a/api/v1","api_key":"sk-a"},'
        '{"name":"b","url":"http://b/api/v1","api_key":"sk-b"}'
        ']\n',
    )
    srcs = kb_config.get_sources()
    assert len(srcs) == 2
    assert srcs[0] == {"name": "a", "url": "http://a/api/v1", "api_key": "sk-a", "group": None}
    assert srcs[1]["name"] == "b"


def test_get_sources_invalid_json_returns_empty(capsys, tmp_path):
    _write_env(tmp_path, "SOURCES=not-json\n")
    assert kb_config.get_sources() == []
    assert "SOURCES" in capsys.readouterr().err


def test_get_sources_skips_malformed_entries(tmp_path):
    """缺 name/url/api_key 的条目被丢弃并告警。"""
    _write_env(
        tmp_path,
        'SOURCES=[{"name":"a","url":"http://a","api_key":"sk-a"},'
        '{"name":"bad"},{"url":"http://x","api_key":"sk-x"}]\n',
    )
    srcs = kb_config.get_sources()
    assert [s["name"] for s in srcs] == ["a"]


def test_default_source_from_config(tmp_path):
    _write_env(tmp_path, "DEFAULT_SOURCE=ops\n")
    assert kb_config.get_config()["DEFAULT_SOURCE"] == "ops"
```

同时更新 `clean_env` fixture，清掉新键：

```python
    for key in (
        "KNOWLEDGE_BASE_URL",
        "KNOWLEDGE_BASE_API_KEY",
        "DEFAULT_RETRIEVE_KB",
        "DEFAULT_UPLOAD_KB",
        "KB_ALIASES",
        "SOURCES",            # 新增
        "DEFAULT_SOURCE",     # 新增
    ):
        monkeypatch.delenv(key, raising=False)
```

### Step 2: 跑确认失败

Run: `python -m pytest tests/test_kb_config.py -k "sources or default_source" -v`
Expected: FAIL — `AttributeError: module 'kb_config' has no attribute 'get_sources'`

### Step 3: 实现（kb_config.py）

把 `SOURCES` 与 `DEFAULT_SOURCE` 加入 `_load_merged_env` 的环境变量白名单（`kb_config.py:65-71`）：

```python
    for key in (
        "KNOWLEDGE_BASE_URL",
        "KNOWLEDGE_BASE_API_KEY",
        "DEFAULT_RETRIEVE_KB",
        "DEFAULT_UPLOAD_KB",
        KB_ALIASES_KEY,
        "SOURCES",
        "DEFAULT_SOURCE",
    ):
```

新增模块级常量与函数（放在 `get_aliases` 之后）：

```python
SOURCES_KEY = "SOURCES"
DEFAULT_SOURCE_KEY = "DEFAULT_SOURCE"


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
            sys.stderr.write(f"[kb_config] 丢弃不完整来源条目: {entry}\n")
            continue
        result.append(
            {"name": name, "url": url, "api_key": api_key,
             "group": (str(entry["group"]).strip() or None) if entry.get("group") else None}
        )
    return result
```

> 需要 `from typing import Any`（文件顶部已 `from __future__ import annotations`，但 `get_sources` 用了运行时注解 `list[dict[str, Any]]`，需补 `from typing import Any` 导入）。检查文件顶部是否已有，无则加。

### Step 4: 跑确认通过

Run: `python -m pytest tests/test_kb_config.py -v`
Expected: PASS（全部用例）

### Step 5: 提交

```bash
git add scripts/kb_config.py tests/test_kb_config.py
git commit -m "feat(scheme-writer): kb_config 支持 SOURCES/DEFAULT_SOURCE 读写"
```

---

## Task 2: 单来源隐式 + get_source

**Files:**
- Modify: `scripts/kb_config.py`
- Test: `tests/test_kb_config.py`

### Step 1: 写失败测试

```python
def test_get_source_by_name(tmp_path):
    _write_env(
        tmp_path,
        'SOURCES=[{"name":"a","url":"http://a","api_key":"sk-a"}]\n',
    )
    s = kb_config.get_source("a")
    assert s["url"] == "http://a"


def test_get_source_missing_raises(tmp_path):
    _write_env(
        tmp_path,
        'SOURCES=[{"name":"a","url":"http://a","api_key":"sk-a"}]\n',
    )
    with pytest.raises(kb_config.ConfigError):
        kb_config.get_source("nope")


def test_single_source_is_implicit_default(tmp_path):
    """仅一个来源时，resolve 隐式选中它（向后兼容）。"""
    _write_env(
        tmp_path,
        'SOURCES=[{"name":"solo","url":"http://a","api_key":"sk-a"}]\n',
    )
    assert kb_config.resolve_default_source() == "solo"


def test_resolve_default_source_uses_config(tmp_path):
    _write_env(tmp_path, "DEFAULT_SOURCE=picked\n")
    assert kb_config.resolve_default_source() == "picked"


def test_resolve_default_source_none_when_ambiguous(tmp_path):
    _write_env(
        tmp_path,
        'SOURCES=[{"name":"a","url":"http://a","api_key":"sk-a"},'
        '{"name":"b","url":"http://b","api_key":"sk-b"}]\n',
    )
    assert kb_config.resolve_default_source() is None
```

### Step 2: 跑确认失败

Run: `python -m pytest tests/test_kb_config.py -k "get_source or default_source" -v`
Expected: FAIL — `get_source` / `resolve_default_source` 不存在

### Step 3: 实现

```python
def get_source(name: str) -> dict[str, Any]:
    """按 name 取来源；不存在抛 ConfigError。"""
    for src in get_sources():
        if src["name"] == name:
            return src
    raise ConfigError(f"未知来源: {name}")


def resolve_default_source() -> str | None:
    """确定默认来源：DEFAULT_SOURCE > 唯一来源隐式 > None。

    None 表示无法隐式决定，调用方应报错反问（铁律三）。
    """
    cfg = get_config().get(DEFAULT_SOURCE_KEY, "").strip()
    if cfg:
        return cfg
    srcs = get_sources()
    if len(srcs) == 1:
        return srcs[0]["name"]
    return None
```

### Step 4: 跑确认通过

Run: `python -m pytest tests/test_kb_config.py -v`
Expected: PASS

### Step 5: 提交

```bash
git add scripts/kb_config.py tests/test_kb_config.py
git commit -m "feat(scheme-writer): kb_config 提供 get_source 与单来源隐式默认"
```

---

## Task 3: kb_resolve.py 解析层

**Files:**
- Create: `scripts/kb_resolve.py`
- Test: `tests/test_kb_resolve.py`

### Step 1: 写失败测试（新文件 tests/test_kb_resolve.py）

```python
"""kb_resolve.py 单元测试：来源与 kb 引用解析。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_config  # noqa: E402
import kb_resolve  # noqa: E402
from kb_http import KbError  # noqa: E402


def _env(tmp_path, sources, aliases=None, default_source=None):
    lines = [f'SOURCES={sources}']
    if aliases:
        lines.append(f'KB_ALIASES={aliases}')
    if default_source:
        lines.append(f'DEFAULT_SOURCE={default_source}')
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


SRCS = ('[{"name":"ops","url":"http://o","api_key":"sk-o"},'
        '{"name":"sec","url":"http://s","api_key":"sk-s"}]')


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    for k in ("SOURCES", "DEFAULT_SOURCE", "KB_ALIASES",
              "KNOWLEDGE_BASE_URL", "KNOWLEDGE_BASE_API_KEY",
              "DEFAULT_RETRIEVE_KB", "DEFAULT_UPLOAD_KB"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)
    yield


def test_resolve_qualified_alias(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/规范库":"kb-1"}')
    assert kb_resolve.resolve_kb_ref("ops/规范库", None) == ("ops", "kb-1")


def test_resolve_qualified_literal(tmp_path):
    """source/kb_id 形式但非别名 → 字面 kb_id。"""
    _env(tmp_path, SRCS)
    assert kb_resolve.resolve_kb_ref("sec/kb-999", None) == ("sec", "kb-999")


def test_resolve_unknown_prefix_raises(tmp_path):
    _env(tmp_path, SRCS)
    with pytest.raises(KbError):
        kb_resolve.resolve_kb_ref("ghost/x", None)


def test_resolve_bare_unique(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/规范库":"kb-1"}')
    assert kb_resolve.resolve_kb_ref("规范库", None) == ("ops", "kb-1")


def test_resolve_bare_ambiguous_raises(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/库":"kb-1","sec/库":"kb-2"}')
    with pytest.raises(KbError) as exc:
        kb_resolve.resolve_kb_ref("库", None)
    assert "歧义" in str(exc.value)


def test_resolve_bare_literal_uses_default_source(tmp_path):
    _env(tmp_path, SRCS, default_source="ops")
    assert kb_resolve.resolve_kb_ref("kb-1", None) == ("ops", "kb-1")


def test_resolve_bare_literal_no_source_raises(tmp_path):
    _env(tmp_path, SRCS)  # 多源，无默认
    with pytest.raises(kb_config.ConfigError):
        kb_resolve.resolve_kb_ref("kb-1", None)


def test_resolve_explicit_source_overrides(tmp_path):
    _env(tmp_path, SRCS, default_source="ops")
    assert kb_resolve.resolve_kb_ref("kb-1", "sec") == ("sec", "kb-1")


def test_resolve_kb_refs_multi(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/a":"k1","sec/b":"k2"}')
    assert kb_resolve.resolve_kb_refs("ops/a,sec/b", None) == [("ops", "k1"), ("sec", "k2")]


def test_resolve_kb_refs_strips_blanks(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/a":"k1"}')
    assert kb_resolve.resolve_kb_refs(" ops/a , ", None) == [("ops", "k1")]
```

### Step 2: 跑确认失败

Run: `python -m pytest tests/test_kb_resolve.py -v`
Expected: FAIL — `ModuleNotFoundError: kb_resolve`

### Step 3: 实现（scripts/kb_resolve.py，完整）

```python
"""scheme-writer: 来源与 kb 引用解析层。

把用户/CLI 传入的 kb 引用解析成 (source_name, kb_id) 对。
所有 kb_*.py 通过本模块确定要访问哪个来源的哪个库。

解析规则（详见 docs/plans/2026-06-20-multi-source-design.md §4.1）：
- 来源/库名（限定别名）：命中 KB_ALIASES → (prefix, alias_kb_id)
- 来源/kb_id（限定字面）：前缀是已知来源但非别名 → (prefix, kb_id)
- 库名（裸名）：后缀唯一命中别名 → 解析；多命中 → 歧义报错（铁律三）
- kb_id（裸字面）：source 由 --source 或 DEFAULT_SOURCE 决定，都无则报错
"""
from __future__ import annotations

from typing import Any

import kb_config
from kb_http import KbError


def _known_source_names() -> set[str]:
    return {s["name"] for s in kb_config.get_sources()}


def resolve_source(explicit: str | None) -> str:
    """确定来源：--source 显式 > DEFAULT_SOURCE/单源隐式 > 报错。"""
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

    # 限定别名
    if ref in aliases:
        src = ref.split("/", 1)[0]
        return (src, aliases[ref])
    # 限定字面 source/kb_id
    if "/" in ref:
        src, _, kb_id = ref.partition("/")
        if src in names:
            return (src, kb_id)
        raise KbError("bad_args", f"未知来源前缀: {src}（引用: {ref}）")
    # 裸名：后缀匹配别名
    matches = [k for k in aliases if k.endswith("/" + ref)]
    if len(matches) == 1:
        src = matches[0].split("/", 1)[0]
        return (src, aliases[matches[0]])
    if len(matches) > 1:
        raise KbError(
            "bad_args",
            f"裸名 '{ref}' 在多个来源歧义: {matches}；请用 '来源/{ref}' 明确。",
        )
    # 裸字面 kb_id
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
```

### Step 4: 跑确认通过

Run: `python -m pytest tests/test_kb_resolve.py -v`
Expected: PASS（10 用例）

### Step 5: 提交

```bash
git add scripts/kb_resolve.py tests/test_kb_resolve.py
git commit -m "feat(scheme-writer): 新增 kb_resolve 解析层（来源/kb 引用 → source+kb_id）"
```

---

## Task 4: 旧配置自动迁移（幂等）

**Files:**
- Create: `scripts/kb_migrate.py`
- Test: `tests/test_kb_migrate.py`

### Step 1: 写失败测试

```python
"""kb_migrate.py 单元测试：旧单实例配置 → 多来源。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_config  # noqa: E402
import kb_migrate  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    for k in ("SOURCES", "DEFAULT_SOURCE", "KB_ALIASES",
              "KNOWLEDGE_BASE_URL", "KNOWLEDGE_BASE_API_KEY",
              "DEFAULT_RETRIEVE_KB", "DEFAULT_UPLOAD_KB"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)
    yield


def test_needs_migration_when_legacy_only(tmp_path):
    """有旧 URL+KEY、无 SOURCES → 需迁移。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n", encoding="utf-8")
    assert kb_migrate.needs_migration() is True


def test_no_migration_when_sources_present(tmp_path):
    (tmp_path / ".env").write_text(
        'SOURCES=[{"name":"default","url":"http://x","api_key":"sk"}]\n', encoding="utf-8")
    assert kb_migrate.needs_migration() is False


def test_no_migration_when_clean(tmp_path):
    (tmp_path / ".env").write_text("DEFAULT_SOURCE=a\n", encoding="utf-8")
    assert kb_migrate.needs_migration() is False


def test_migrate_synthesizes_default_source(tmp_path):
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n", encoding="utf-8")
    changed = kb_migrate.migrate()
    assert "SOURCES" in changed
    srcs = kb_config.get_sources()
    assert len(srcs) == 1
    assert srcs[0] == {"name": "default", "url": "http://leg/api/v1",
                       "api_key": "sk-leg", "group": None}
    assert kb_config.get_config()["DEFAULT_SOURCE"] == "default"


def test_migrate_prefixes_legacy_aliases(tmp_path):
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n"
        'KB_ALIASES={"技术规范库":"kb-1","方案库":"kb-2"}\n', encoding="utf-8")
    kb_migrate.migrate()
    assert kb_config.get_aliases() == {
        "default/技术规范库": "kb-1", "default/方案库": "kb-2"}


def test_migrate_creates_backup(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n", encoding="utf-8")
    kb_migrate.migrate()
    assert (tmp_path / ".env.bak").is_file()


def test_migrate_idempotent(tmp_path):
    """跑两次不重复迁移、不重复加前缀。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n"
        'KB_ALIASES={"技术规范库":"kb-1"}\n', encoding="utf-8")
    kb_migrate.migrate()
    second = kb_migrate.migrate()
    assert second == []  # 第二次无事可做
    assert kb_config.get_aliases() == {"default/技术规范库": "kb-1"}
    assert len(kb_config.get_sources()) == 1
```

### Step 2: 跑确认失败

Run: `python -m pytest tests/test_kb_migrate.py -v`
Expected: FAIL — `ModuleNotFoundError: kb_migrate`

### Step 3: 实现（scripts/kb_migrate.py，完整）

```python
"""scheme-writer: 旧单实例配置 → 多来源自动迁移。

触发：SOURCES 缺失但存在旧 KNOWLEDGE_BASE_URL + KNOWLEDGE_BASE_API_KEY。
动作：合成 default 来源 + DEFAULT_SOURCE=default + 旧别名加 default/ 前缀。
幂等：已迁移（有 SOURCES）则不动。
"""
from __future__ import annotations

import json
from pathlib import Path

import kb_config

DEFAULT_NAME = "default"


def needs_migration() -> bool:
    cfg = kb_config.get_config()
    if cfg.get(kb_config.SOURCES_KEY, "").strip():
        return False
    return bool(cfg.get("KNOWLEDGE_BASE_URL", "").strip()
                and cfg.get("KNOWLEDGE_BASE_API_KEY", "").strip())


def migrate(path: Path | None = None) -> list[str]:
    """执行迁移，返回变更的键列表；无需迁移返回 []。"""
    if not needs_migration():
        return []

    cfg = kb_config._load_merged_env()
    target = path or (kb_config.config_path() or (Path.cwd() / ".env"))

    # 备份
    if Path(target).is_file():
        (Path(target).with_name(Path(target).name + ".bak")
         .write_bytes(Path(target).read_bytes()))

    flat = dict(cfg)
    src = {
        "name": DEFAULT_NAME,
        "url": cfg["KNOWLEDGE_BASE_URL"].strip(),
        "api_key": cfg["KNOWLEDGE_BASE_API_KEY"].strip(),
        "group": None,
    }
    flat[kb_config.SOURCES_KEY] = json.dumps([src], ensure_ascii=False)
    flat[kb_config.DEFAULT_SOURCE_KEY] = DEFAULT_NAME

    changed = [kb_config.SOURCES_KEY, kb_config.DEFAULT_SOURCE_KEY]

    # 旧别名加 default/ 前缀
    raw_aliases = cfg.get(kb_config.KB_ALIASES_KEY, "").strip()
    if raw_aliases:
        try:
            old = json.loads(raw_aliases)
        except json.JSONDecodeError:
            old = {}
        if isinstance(old, dict):
            new = {}
            for k, v in old.items():
                key = k if "/" in k else f"{DEFAULT_NAME}/{k}"
                new[key] = v
            flat[kb_config.KB_ALIASES_KEY] = json.dumps(new, ensure_ascii=False)
            if new != old:
                changed.append(kb_config.KB_ALIASES_KEY)

    kb_config.write_env(flat, path=Path(target))
    return changed
```

> 注意：`needs_migration` 与 `migrate` 都通过 `kb_config.get_config()`/`_load_merged_env()` 读，路径解析与现有逻辑一致（用户级优先、工作区回退）。迁移目标路径复用 `config_path()`。

### Step 4: 跑确认通过

Run: `python -m pytest tests/test_kb_migrate.py -v`
Expected: PASS（7 用例）

### Step 5: 提交

```bash
git add scripts/kb_migrate.py tests/test_kb_migrate.py
git commit -m "feat(scheme-writer): 新增旧单实例配置自动迁移（合成 default 源 + 别名加前缀，幂等）"
```

---

# Phase 1 — 各脚本接入解析层（并行 ✓）

> **前置:** Phase 0（T1–T4）已提交。本阶段 4 个任务**互独立**（各自只改 `scripts/kb_X.py` + `tests/test_kb_X.py`），可派 4 个子代理并行。
> 共同改动模式：把脚本内 `base = require("KNOWLEDGE_BASE_URL")` / `api_key = require("KNOWLEDGE_BASE_API_KEY")` 替换为「通过 `kb_resolve` 解析得到 `(source_name, kb_id)`，再 `kb_config.get_source(name)` 拿 `(url, api_key)`」。
> 子代理通用指令：遵循仓库优先（改 `myopenclaw-skills/scheme-writer/`）；TDD；不碰本任务外的文件；完成后跑 `python -m pytest tests/test_kb_X.py -v` 全绿再提交。

## Task 5: kb_list.py 接入 `--source` / `--all`

**Files:**
- Modify: `scripts/kb_list.py`（`list_kbs()` 接收 source；`main()` 加 `--source`/`--all`）
- Test: `tests/test_kb_list.py`

**目标行为:**
- `list_kbs(source_name)` → 列该来源的库（输出每条加 `source` 字段）
- `--source X` 列 X；无 `--source` 用 `resolve_source(None)`；`--all` 遍历所有来源、结果带 `source` 标签
- `init.py` 依赖的 `list_kbs()` 无参调用仍可用（默认来源）→ 保持 `list_kbs(source=None)`，内部 `resolve_source` 兜底

### Step 1: 写失败测试（test_kb_list.py 增补，用 monkeypatch mock request_json）

```python
import kb_list
from unittest.mock import patch


def test_list_kbs_single_source(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        'SOURCES=[{"name":"ops","url":"http://o/api/v1","api_key":"sk-o"}]\n', encoding="utf-8")
    fake = {"data": [{"id": "kb-1", "name": "库A", "knowledge_count": 3, "chunk_count": 30}]}
    with patch("kb_list.request_json", return_value=fake):
        out = kb_list.list_kbs()
    assert out["total"] == 1
    assert out["knowledge_bases"][0]["kb_id"] == "kb-1"
    assert out["knowledge_bases"][0]["source"] == "ops"


def test_list_kbs_all_sources(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        'SOURCES=[{"name":"ops","url":"http://o","api_key":"sk-o"},'
        '{"name":"sec","url":"http://s","api_key":"sk-s"}]\n', encoding="utf-8")
    with patch("kb_list.request_json", return_value={"data": [{"id": "kb-x", "name": "n", "knowledge_count": 1, "chunk_count": 1}]}):
        out = kb_list.list_kbs_all()
    names = {kb["source"] for kb in out["knowledge_bases"]}
    assert names == {"ops", "sec"}
```

（`clean_env` fixture 同步加 SOURCES/DEFAULT_SOURCE。）

### Step 2–4: TDD 节奏

实现要点：`list_kbs(source_name=None)` 内 `src = kb_config.get_source(source_name or kb_resolve.resolve_source(None))`，`base = src["url"]`，`api_key = src["api_key"]`；每条 kb 加 `"source": src["name"]`。新增 `list_kbs_all()` 遍历 `get_sources()`，单源失败不致命（收集 errors）。`main()` 加 `--source`/`--all` 分支。

Run: `python -m pytest tests/test_kb_list.py -v` → PASS

### Step 5: 提交

```bash
git add scripts/kb_list.py tests/test_kb_list.py
git commit -m "feat(scheme-writer): kb_list 支持 --source/--all 多来源"
```

---

## Task 6: kb_docs.py 接入多形态 `--kb`

**Files:**
- Modify: `scripts/kb_docs.py`（`list_docs()` 接收 `(source, kb_id)`；`main()` 用 `resolve_kb_ref`）
- Test: `tests/test_kb_docs.py`

**目标行为:**
- `--kb 来源/库名` 或裸名/字面 → 解析为 `(source, kb_id)` → 用该源的 url/key 拉 `/knowledge-bases/{kb_id}/knowledge`
- 输出顶层加 `source` 字段

### Step 1: 写失败测试

```python
import kb_docs
from unittest.mock import patch


def test_list_docs_uses_source(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        'SOURCES=[{"name":"ops","url":"http://o/api/v1","api_key":"sk-o"}]\n'
        'KB_ALIASES={"ops/规范库":"kb-1"}\n', encoding="utf-8")
    fake = {"data": {"items": [{"id": "d1", "title": "doc", "parse_status": "completed"}], "total": 1}}
    with patch("kb_docs.request_json", return_value=fake) as m:
        out = kb_docs.list_docs("ops", "kb-1")
    assert out["source"] == "ops"
    # 确认打到了 ops 的 url
    assert "http://o/api/v1" in m.call_args.args[1]
```

### Step 2–4: TDD 节奏

`list_docs(source_name, kb_id, ...)` 内 `src = kb_config.get_source(source_name)`，`base = src["url"]`，`api_key = src["api_key"]`；返回 dict 加 `"source": source_name`。`main()`：`target = kb_resolve.resolve_kb_ref(args.kb, args.source)` → `(src, kb_id)`；`list_docs(src, kb_id, ...)`。

Run: `python -m pytest tests/test_kb_docs.py -v` → PASS

### Step 5: 提交

```bash
git add scripts/kb_docs.py tests/test_kb_docs.py
git commit -m "feat(scheme-writer): kb_docs 接入解析层，--kb 多形态 + source 标签"
```

---

## Task 7: kb_search.py 多来源检索 + 合并 + 部分失败

**Files:**
- Modify: `scripts/kb_search.py`（拆 `search()` → `search_source(source, kb_id, ...)`；`main()` 多目标循环合并）
- Test: `tests/test_kb_search.py`

> 这是 Phase 1 最复杂的任务，建议由主代理亲自做或指定最强子代理。

**目标行为（详见设计 §5）:**
- `--kb A,B,C` → `resolve_kb_refs` → 多个 `(source, kb_id)`
- 每 `(source,kb_id)` 各自 top_k，逐个 try（部分失败不致命）
- 合并：扁平 chunks，每条打 `source`+`kb_id`，按 `(source, -score)` 排序，**不跨源重排**
- 输出：单目标 → 老结构 `{kb_id, query, chunks, total}`；多目标 → `{sources, query, chunks, total, errors}`
- 退出码：≥1 成功 → 0；全失败 → 对应错误码

### Step 1: 写失败测试

```python
import kb_search
from unittest.mock import patch


def _src_env(tmp_path):
    (tmp_path / ".env").write_text(
        'SOURCES=[{"name":"ops","url":"http://o/api/v1","api_key":"sk-o"},'
        '{"name":"sec","url":"http://s/api/v1","api_key":"sk-s"}]\n'
        'KB_ALIASES={"ops/a":"k1","sec/b":"k2"}\n', encoding="utf-8")


def test_single_target_legacy_shape(tmp_path, monkeypatch):
    _src_env(tmp_path)
    fake = {"chunks": [{"chunk_id": "c1", "content": "x", "score": 0.8}]}
    with patch("kb_search.request_json", return_value=fake):
        out = kb_search.run(["--kb", "ops/a", "--query", "q"])
    assert out["kb_id"] == "k1"
    assert "sources" not in out
    assert out["chunks"][0]["source"] == "ops"


def test_multi_target_merged_shape(tmp_path, monkeypatch):
    _src_env(tmp_path)
    fake = {"chunks": [{"chunk_id": "c1", "content": "x", "score": 0.7}]}
    with patch("kb_search.request_json", return_value=fake):
        out = kb_search.run(["--kb", "ops/a,sec/b", "--query", "q"])
    assert set(out["sources"]) == {"ops", "sec"}
    assert out["total"] == 2
    assert all("source" in c for c in out["chunks"])


def test_partial_failure_returns_healthy(tmp_path, monkeypatch):
    from kb_http import KbError
    _src_env(tmp_path)

    def fake_req(method, url, **kw):
        if "http://s" in url:
            raise KbError("auth", "sec down")
        return {"chunks": [{"chunk_id": "c1", "content": "x", "score": 0.9}]}

    with patch("kb_search.request_json", side_effect=fake_req):
        out = kb_search.run(["--kb", "ops/a,sec/b", "--query", "q"])
    assert out["total"] == 1                      # ops 成功
    assert out["errors"][0]["source"] == "sec"
```

（`run(argv)` 是为测试暴露的入口：解析 argv → 返回 dict；`main()` 调 `run` 后 `emit_ok`/`emit_error`。）

### Step 2–4: TDD 节奏（关键实现）

```python
def search_source(source, kb_id, query, *, top_k=8, min_score=0.5, timeout=30):
    url = f"{source['url'].rstrip('/')}/knowledge-search"
    data = request_json("POST", url, api_key=source["api_key"],
                        json_body={"query": query, "knowledge_base_id": kb_id,
                                   "top_k": top_k, "min_score": min_score}, timeout=timeout)
    raw = data.get("chunks") or data.get("results") or data.get("data") or []
    chunks = []
    for c in raw:
        s = float(c.get("score", 0.0))
        if s < min_score:
            continue
        chunks.append({"chunk_id": c.get("chunk_id") or c.get("id",""),
                       "source_doc": c.get("source_doc") or c.get("knowledge_title") or c.get("document_title",""),
                       "source_doc_id": c.get("source_doc_id") or c.get("knowledge_id") or c.get("document_id",""),
                       "source_file": c.get("knowledge_filename",""),
                       "chunk_index": c.get("chunk_index",0),
                       "content": c.get("content") or c.get("text",""),
                       "score": s, "metadata": c.get("metadata") or {}})
    return chunks


def run(argv):
    args = _parse(argv)
    targets = kb_resolve.resolve_kb_refs(args.kb, args.source)
    all_chunks, errors, ok_sources = [], [], set()
    for src_name, kb_id in targets:
        try:
            src = kb_config.get_source(src_name)
            chunks = search_source(src, kb_id, args.query, top_k=args.top_k,
                                   min_score=args.min_score, timeout=args.timeout)
            for c in chunks:
                c["source"] = src_name; c["kb_id"] = kb_id
            all_chunks.extend(chunks); ok_sources.add(src_name)
        except KbError as e:
            errors.append({"source": src_name, "error": e.code, "message": e.message})

    all_chunks.sort(key=lambda c: (c["source"], -c["score"]))

    if len(targets) == 1:
        return {"kb_id": targets[0][1], "query": args.query,
                "chunks": all_chunks, "total": len(all_chunks)}
    return {"sources": sorted(ok_sources | {e["source"] for e in errors}),
            "query": args.query, "chunks": all_chunks, "total": len(all_chunks),
            "errors": errors}


def main():
    args = _parse(None)  # None → sys.argv[1:]
    targets = kb_resolve.resolve_kb_refs(args.kb, args.source)
    all_chunks, errors, ok_sources = [], [], set()
    for src_name, kb_id in targets:
        try:
            src = kb_config.get_source(src_name)
            chunks = search_source(...)
            ...
        except KbError as e:
            errors.append(...)
    if not ok_sources and errors:        # 全失败
        emit_error(KbError(errors[0]["error"], errors[0]["message"])); return _exit_for(errors[0]["error"])
    emit_ok(run_result); return 0
```

> 实现时把 `run()` 与 `main()` 的公共逻辑抽一个 `_execute(args)` 返回 `(payload, exit_code)`，`run` 测试用、`main` 落地用，避免重复。`_parse(argv)` 用 argparse，`argv is None` 走 `sys.argv[1:]`。

Run: `python -m pytest tests/test_kb_search.py -v` → PASS

### Step 5: 提交

```bash
git add scripts/kb_search.py tests/test_kb_search.py
git commit -m "feat(scheme-writer): kb_search 多来源检索+合并+部分失败，单目标退化老结构"
```

---

## Task 8: kb_upload.py 收敛到单一来源

**Files:**
- Modify: `scripts/kb_upload.py`（`upload()` 接收 `(source, kb_id)`；`main()` 解析且拒绝多目标）
- Test: `tests/test_kb_upload.py`

**目标行为:**
- `--kb` 解析后必须**恰好一个** `(source, kb_id)`；逗号多目标 → 报错（上传不跨源）
- 用该源的 url/key POST `/knowledge-bases/{kb_id}/knowledge/manual`
- 输出加 `source` 字段

### Step 1: 写失败测试

```python
import kb_upload
from unittest.mock import patch


def test_upload_uses_resolved_source(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        'SOURCES=[{"name":"ops","url":"http://o/api/v1","api_key":"sk-o"}]\n'
        'KB_ALIASES={"ops/方案库":"kb-1"}\n', encoding="utf-8")
    f = tmp_path / "doc.md"; f.write_text("# hi")
    with patch("kb_upload.request_json", return_value={"data": {"id": "doc-1"}}) as m:
        out = kb_upload.upload("ops", "kb-1", str(f), "标题")
    assert out["source"] == "ops"
    assert out["doc_id"] == "doc-1"
    assert "http://o/api/v1" in m.call_args.args[1]
```

并加一个 CLI 层测试：`--kb a,b` → 退出码 2 / bad_args。

### Step 2–4: TDD 节奏

`upload(source_name, kb_id, file_path, ...)` 内 `src = kb_config.get_source(source_name)`；`main()`：`targets = kb_resolve.resolve_kb_refs(args.kb, args.source)`；`if len(targets) != 1: emit_error(bad_args "上传目标必须唯一"); return 2`；否则 `upload(targets[0][0], targets[0][1], ...)`。

Run: `python -m pytest tests/test_kb_upload.py -v` → PASS

### Step 5: 提交

```bash
git add scripts/kb_upload.py tests/test_kb_upload.py
git commit -m "feat(scheme-writer): kb_upload 接入解析层并强制单一来源目标"
```

---

# Phase 2 — init.py 来源管理（顺序）

## Task 9: init.py 多来源子命令 + status/show 适配

**Files:**
- Modify: `scripts/init.py`（新子命令、`SETTABLE_KEYS` 调整、`_probe`/`_show` 适配、首跑迁移）
- Test: `tests/test_init.py`

**目标行为:**
- 新子命令：`--add-source NAME URL KEY`、`--set-sources JSON`、`--remove-source NAME`、`--set-default-source NAME`、`--list-sources`
- `SETTABLE_KEYS` 移除 `KNOWLEDGE_BASE_URL/KEY`，保留标量键
- 启动时（`main()` 入口）先调 `kb_migrate.migrate()` 做幂等迁移（老用户首跑零摩擦）
- `--status`：探测 `resolve_default_source()` 对应来源；`NEED_INIT` = 无 SOURCES
- `--show`：列出所有来源（Key 脱敏）+ DEFAULT_SOURCE + 别名
- `--list-sources`：列来源 + 各自连通状态（逐一 list_kbs 探测）

### Step 1: 写失败测试（用现有 `_run_init` 子进程风格）

```python
def test_add_source_appends(tmp_path):
    env = tmp_path / "sw"; env.mkdir()
    r = _run_init("--add-source", "ops", "http://o/api/v1", "sk-o",
                  home=tmp_path, cwd=env)
    # 写到工作区 .env；读回校验
    import json
    text = (env / ".env").read_text()
    assert '"name":"ops"' in text
    assert "DEFAULT_SOURCE=ops" in text  # 首个来源自动设默认


def test_set_sources_bulk(tmp_path):
    env = tmp_path / "sw"; env.mkdir()
    r = _run_init("--set-sources",
                  '[{"name":"a","url":"http://a","api_key":"sk-a"}]',
                  home=tmp_path, cwd=env)
    assert (env / ".env").read_text().count('"name":"a"') == 1


def test_auto_migration_on_first_run(tmp_path):
    """旧 .env 存在时，任意子命令触发自动迁移。"""
    env = tmp_path / "sw"; env.mkdir()
    (env / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\nKNOWLEDGE_BASE_API_KEY=sk-leg\n",
        encoding="utf-8")
    _run_init("--status", home=tmp_path, cwd=env)
    text = (env / ".env").read_text()
    assert '"name":"default"' in text
    assert "DEFAULT_SOURCE=default" in text
```

### Step 2–4: TDD 节奏（关键改动）

- `import kb_migrate, kb_resolve` 顶部加
- `main()` 第一行：`kb_migrate.migrate()`（幂等，无副作用）
- `SETTABLE_KEYS`：删 `KNOWLEDGE_BASE_URL`/`KNOWLEDGE_BASE_API_KEY`，加 `DEFAULT_SOURCE`；保留 `DEFAULT_RETRIEVE_KB/UPLOAD_KB`、`KB_ALIASES`
- `--add-source NAME URL KEY`：读现有 SOURCES（经 `get_sources()`），append，去重（同名报错），写回；若 DEFAULT_SOURCE 空，设为首个来源
- `--set-sources JSON`：校验 JSON 数组 → 直接写 SOURCES
- `--remove-source NAME`：过滤后写回；若删的是 DEFAULT_SOURCE，清空或重置
- `--set-default-source NAME`：校验存在 → 写 DEFAULT_SOURCE
- `--list-sources`：遍历 `get_sources()`，每个调 `list_kbs(source)` 探测连通，输出 `{sources:[{name,url,api_key(masked),reachable,doc_total}], total}`
- `_probe()`：用 `resolve_default_source()` 选源；无源 → `NEED_INIT`
- `_show()`：payload 增加 `sources`（masked）与 `default_source`

> 写回 SOURCES 复用 `kb_config.write_env`（合并现有 flat 配置），与 `set_aliases` 同模式。

Run: `python -m pytest tests/test_init.py -v` → PASS

### Step 5: 提交

```bash
git add scripts/init.py tests/test_init.py
git commit -m "feat(scheme-writer): init.py 多来源管理子命令 + 首跑自动迁移 + status/show 适配"
```

---

# Phase 3 — 文档与回归（顺序）

## Task 10: SKILL.md 更新

**Files:**
- Modify: `SKILL.md`

**改动要点（不写完整 markdown，按现有结构就地更新）:**
- 「快速开始」：配置流程改为「添加来源」（`--add-source`），不再只配单实例
- 「能力矩阵」：新增 `kb_resolve` 行；`kb_list` 注明 `--source/--all`
- 「知识库参数解析」：别名键格式改为 `来源/库名`；source 解析优先级表
- 「协作工作流」场景：补多来源检索示例（`--kb 运维空间1/技术规范库,安全部/漏洞库`）
- 「快速参考」命令表：新增 `--add-source`/`--set-sources`/`--remove-source`/`--set-default-source`/`--list-sources`/`--source`/`--all`
- 「故障排除」：补「多源部分失败如何看 errors」「迁移后旧别名带 default/ 前缀」
- 铁律不变（API Key 仅 .env）

**验证:** 通读 SKILL.md 无遗留「单实例」假设；别名示例全部带 `来源/` 前缀。

**提交:**
```bash
git add SKILL.md
git commit -m "docs(scheme-writer): SKILL.md 适配多来源工作流"
```

---

## Task 11: 全量测试 + 集成回归

**Files:** 无新增，仅运行 + 修复

### Step 1: 全量单测

Run: `cd myopenclaw-skills/scheme-writer && python -m pytest tests/ -v`
Expected: ALL PASS。任一红 → 回到对应任务修复（不改测试迁就实现，除非测试本身错）。

### Step 2: 迁移端到端冒烟（手动构造旧 .env）

```bash
cd /tmp && mkdir sw-smoke && cd sw-smoke
printf 'KNOWLEDGE_BASE_URL=http://leg/api/v1\nKNOWLEDGE_BASE_API_KEY=sk-leg\nKB_ALIASES={"技术规范库":"kb-1"}\n' > .env
python /Users/xiejava/AIproject/myopenclaw-skills/scheme-writer/scripts/init.py --status
cat .env   # 期望：含 SOURCES default + DEFAULT_SOURCE=default + 别名 default/技术规范库 + .env.bak
python .../init.py --status   # 再跑一次：幂等，不再改
```
Expected: 首次迁移生效、第二次无变化、`.env.bak` 存在。

### Step 3: 解析层冒烟

```bash
printf 'SOURCES=[{"name":"ops","url":"http://o/api/v1","api_key":"sk-o"}]\nKB_ALIASES={"ops/规范库":"kb-1"}\n' > .env
python .../kb_list.py --source ops        # 解析限定
python .../kb_list.py                     # 单源隐式默认
```
Expected: 不报「无法确定来源」。

### Step 4: 同步提示

实现全部完成后，**告知用户**：改动已落在仓库 `myopenclaw-skills/scheme-writer/`，需手动同步到 `~/.claude/skills/scheme-writer/`（覆盖 scripts/ + SKILL.md；**不要覆盖 `~/.claude/skills/scheme-writer/.env`**，那是运行态配置）。或提议用软链消除后续手动同步。

### Step 5: 最终提交（如有 smoke 修复）

```bash
git add -A && git commit -m "test(scheme-writer): 全量回归通过 + 迁移/解析冒烟"
```

---

## 风险与回滚

- **迁移破坏性**：`kb_migrate` 生成 `.env.bak`；出问题可 `cp .env.bak .env` 回滚。Phase 0 T4 已测幂等与备份。
- **向后兼容**：单来源（迁移后的 default）所有行为退化到现状；T7 单目标输出 shape 回归测试守卫。
- **解析歧义**：裸名多命中按铁律三报错反问，不静默选一个（T3 守卫）。
- **子代理冲突**：Phase 1 各任务文件域隔离；若并行，确保子代理不改共享文件（kb_config/kb_resolve/init 仅 Phase 0/2 触碰）。
