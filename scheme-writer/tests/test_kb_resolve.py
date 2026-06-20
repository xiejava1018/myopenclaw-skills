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
    lines = [f"SOURCES={sources}"]
    if aliases:
        lines.append(f"KB_ALIASES={aliases}")
    if default_source:
        lines.append(f"DEFAULT_SOURCE={default_source}")
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


SRCS = (
    '[{"name":"ops","url":"http://o","api_key":"sk-o"},'
    '{"name":"sec","url":"http://s","api_key":"sk-s"}]'
)


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    for k in (
        "SOURCES",
        "DEFAULT_SOURCE",
        "KB_ALIASES",
        "KNOWLEDGE_BASE_URL",
        "KNOWLEDGE_BASE_API_KEY",
        "DEFAULT_RETRIEVE_KB",
        "DEFAULT_UPLOAD_KB",
    ):
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
    """斜杠前缀不是已知来源 → KbError。"""
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
    """多源无默认 + 裸字面 → ConfigError（无法决定来源）。"""
    _env(tmp_path, SRCS)  # 多源，无 DEFAULT_SOURCE
    with pytest.raises(kb_config.ConfigError):
        kb_resolve.resolve_kb_ref("kb-1", None)


def test_resolve_explicit_source_overrides(tmp_path):
    """--source 显式覆盖默认源。"""
    _env(tmp_path, SRCS, default_source="ops")
    assert kb_resolve.resolve_kb_ref("kb-1", "sec") == ("sec", "kb-1")


def test_resolve_explicit_unknown_source_raises(tmp_path):
    _env(tmp_path, SRCS)
    with pytest.raises(KbError):
        kb_resolve.resolve_source("ghost")


def test_resolve_kb_refs_multi(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/a":"k1","sec/b":"k2"}')
    assert kb_resolve.resolve_kb_refs("ops/a,sec/b", None) == [("ops", "k1"), ("sec", "k2")]


def test_resolve_kb_refs_strips_blanks(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/a":"k1"}')
    assert kb_resolve.resolve_kb_refs(" ops/a , ", None) == [("ops", "k1")]


def test_resolve_kb_refs_empty_raises(tmp_path):
    _env(tmp_path, SRCS, aliases='{"ops/a":"k1"}')
    with pytest.raises(KbError):
        kb_resolve.resolve_kb_refs(" , ", None)
