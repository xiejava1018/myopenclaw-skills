"""kb_list.py 单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_list  # noqa: E402


def _src_env(path: Path, sources: str, default_source: str | None = None) -> None:
    """在工作区写一份多来源 .env。"""
    lines = [f"SOURCES={sources}"]
    if default_source:
        lines.append(f"DEFAULT_SOURCE={default_source}")
    (path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """单源隐式默认环境，保证 list_kbs() 无参仍可用（向后兼容）。

    同时清掉残留的环境变量，避免污染本机 ~/.claude/scheme-writer/.env。
    """
    _src_env(
        tmp_path,
        '[{"name":"default","url":"http://test","api_key":"sk-test"}]',
    )
    monkeypatch.chdir(tmp_path)
    for k in (
        "KNOWLEDGE_BASE_URL",
        "KNOWLEDGE_BASE_API_KEY",
        "SOURCES",
        "DEFAULT_SOURCE",
    ):
        monkeypatch.delenv(k, raising=False)
    yield


def test_list_parses_knowledge_bases():
    api_response = {
        "knowledge_bases": [
            {"kb_id": "kb-1", "name": "技术规范库", "doc_count": 100, "description": "tech docs"},
            {"kb_id": "kb-2", "name": "方案库", "doc_count": 20, "description": ""},
        ]
    }
    with patch("kb_list.request_json", return_value=api_response) as m:
        result = kb_list.list_kbs()
    assert result["total"] == 2
    assert result["knowledge_bases"][0]["name"] == "技术规范库"
    assert m.call_args.args[0] == "GET"
    assert "/knowledge-bases" in m.call_args.args[1]


def test_list_passes_through_chunk_count():
    """服务端 chunk_count 字段透出，便于诊断『doc_count>0 但检索为空』场景。"""
    api_response = {
        "data": [
            {
                "id": "kb-1",
                "name": "安全运营库",
                "knowledge_count": 12,
                "chunk_count": 0,
            }
        ]
    }
    with patch("kb_list.request_json", return_value=api_response):
        result = kb_list.list_kbs()
    assert result["knowledge_bases"][0]["doc_count"] == 12
    assert result["knowledge_bases"][0]["chunk_count"] == 0


def test_list_parses_items_fallback():
    """兼容 items 字段。"""
    api_response = {
        "items": [
            {"id": "kb-9", "name": "旧版", "document_count": 5},
        ]
    }
    with patch("kb_list.request_json", return_value=api_response):
        result = kb_list.list_kbs()
    assert result["knowledge_bases"][0]["kb_id"] == "kb-9"
    assert result["knowledge_bases"][0]["doc_count"] == 5


def test_list_empty_response():
    with patch("kb_list.request_json", return_value={}):
        result = kb_list.list_kbs()
    assert result == {"knowledge_bases": [], "total": 0}


def test_list_kbs_single_source_implicit():
    """单来源 → 隐式默认，list_kbs() 无参可用（向后兼容）。"""
    _src_env(
        Path.cwd(),
        '[{"name":"ops","url":"http://o/api/v1","api_key":"sk-o"}]',
    )
    fake = {"data": [{"id": "kb-1", "name": "库A", "knowledge_count": 3, "chunk_count": 30}]}
    with patch("kb_list.request_json", return_value=fake) as m:
        out = kb_list.list_kbs()
    assert out["total"] == 1
    assert out["knowledge_bases"][0]["kb_id"] == "kb-1"
    assert out["knowledge_bases"][0]["source"] == "ops"
    call = m.call_args
    assert call.args[1] == "http://o/api/v1/knowledge-bases"
    assert call.kwargs["api_key"] == "sk-o"


def test_list_kbs_explicit_source():
    _src_env(
        Path.cwd(),
        '[{"name":"ops","url":"http://o","api_key":"sk-o"},'
        '{"name":"sec","url":"http://s","api_key":"sk-s"}]',
    )
    fake = {"data": [{"id": "kb-x", "name": "n", "knowledge_count": 1, "chunk_count": 1}]}
    with patch("kb_list.request_json", return_value=fake) as m:
        kb_list.list_kbs("sec")
    assert m.call_args.args[1] == "http://s/knowledge-bases"
    assert m.call_args.kwargs["api_key"] == "sk-s"


def test_list_kbs_all_sources():
    _src_env(
        Path.cwd(),
        '[{"name":"ops","url":"http://o","api_key":"sk-o"},'
        '{"name":"sec","url":"http://s","api_key":"sk-s"}]',
    )
    with patch(
        "kb_list.request_json",
        return_value={"data": [{"id": "kb-x", "name": "n", "knowledge_count": 1, "chunk_count": 1}]},
    ):
        out = kb_list.list_kbs_all()
    names = {kb["source"] for kb in out["knowledge_bases"]}
    assert names == {"ops", "sec"}
    assert "errors" in out


def test_list_kbs_all_partial_failure():
    """--all 时某源失败不致命，进 errors。"""
    from kb_http import KbError

    _src_env(
        Path.cwd(),
        '[{"name":"ops","url":"http://o","api_key":"sk-o"},'
        '{"name":"sec","url":"http://s","api_key":"sk-s"}]',
    )

    def fake_req(method, url, **kw):
        if "http://s" in url:
            raise KbError("auth", "sec down")
        return {"data": [{"id": "kb-1", "name": "n", "knowledge_count": 1, "chunk_count": 1}]}

    with patch("kb_list.request_json", side_effect=fake_req):
        out = kb_list.list_kbs_all()
    assert {kb["source"] for kb in out["knowledge_bases"]} == {"ops"}
    assert out["errors"][0]["source"] == "sec"
