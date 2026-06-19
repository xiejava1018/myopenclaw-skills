"""kb_list.py 单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_list  # noqa: E402


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "KNOWLEDGE_BASE_URL=http://test\n"
        "KNOWLEDGE_BASE_API_KEY=sk-test\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    for k in ("KNOWLEDGE_BASE_URL", "KNOWLEDGE_BASE_API_KEY"):
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


def test_list_missing_config_raises():
    """缺配置时由 request_json 抛 KbError。"""
    import kb_http
    # 把 URL 设为空，让 require 抛 ConfigError → 包成 KbError("bad_args")
    with patch("kb_list.require", side_effect=Exception("missing")):
        with pytest.raises(Exception):
            kb_list.list_kbs()
