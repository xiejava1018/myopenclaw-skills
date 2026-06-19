"""kb_search.py 单元测试：mock HTTP 请求验证请求体/响应解析/参数校验。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_search  # noqa: E402


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, tmp_path):
    """每个用例准备有效的 .env 避免 ConfigError。"""
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


def test_search_parses_chunks():
    """WeKnora 旧版响应：chunks 字段。"""
    api_response = {
        "chunks": [
            {
                "chunk_id": "c-1",
                "source_doc": "doc.md",
                "source_doc_id": "d-1",
                "content": "hello",
                "score": 0.9,
                "metadata": {"page": 1},
            }
        ]
    }
    with patch("kb_search.request_json", return_value=api_response) as m:
        result = kb_search.search("kb1", "test query")
    assert result["total"] == 1
    assert result["chunks"][0]["score"] == 0.9
    assert result["chunks"][0]["source_doc"] == "doc.md"
    m.assert_called_once()
    call_args = m.call_args
    # WeKnora 真实端点：单库检索用 knowledge_base_id 字段
    assert call_args.kwargs["json_body"]["query"] == "test query"
    assert call_args.kwargs["json_body"]["knowledge_base_id"] == "kb1"
    assert call_args.kwargs["json_body"]["top_k"] == 8
    assert call_args.kwargs["json_body"]["min_score"] == 0.5
    # 真实端点：POST /knowledge-search（不是 /knowledge-bases/{id}/search）
    assert call_args.args[0] == "POST"
    assert call_args.args[1].endswith("/knowledge-search")


def test_search_parses_results_fallback():
    """WeKnora 新版响应：results 字段。"""
    api_response = {
        "results": [
            {
                "id": "c-2",
                "document_title": "Doc2",
                "document_id": "d-2",
                "text": "world",
                "score": 0.7,
            }
        ]
    }
    with patch("kb_search.request_json", return_value=api_response):
        result = kb_search.search("kb1", "q")
    assert result["chunks"][0]["chunk_id"] == "c-2"
    assert result["chunks"][0]["source_doc"] == "Doc2"
    assert result["chunks"][0]["content"] == "world"


def test_search_filters_below_min_score():
    """min_score 过滤在客户端兜底。"""
    api_response = {
        "chunks": [
            {"chunk_id": "a", "content": "x", "score": 0.9},
            {"chunk_id": "b", "content": "x", "score": 0.3},  # 应被过滤
        ]
    }
    with patch("kb_search.request_json", return_value=api_response):
        result = kb_search.search("kb1", "q", min_score=0.5)
    assert result["total"] == 1
    assert result["chunks"][0]["chunk_id"] == "a"


def test_search_empty_response():
    """空响应返回 total=0。"""
    with patch("kb_search.request_json", return_value={}):
        result = kb_search.search("kb1", "q")
    assert result == {"kb_id": "kb1", "query": "q", "chunks": [], "total": 0}


def test_search_custom_topk_and_min():
    """自定义 top_k / min_score。"""
    with patch("kb_search.request_json", return_value={"chunks": []}) as m:
        kb_search.search("kb1", "q", top_k=3, min_score=0.8)
    body = m.call_args.kwargs["json_body"]
    assert body["top_k"] == 3
    assert body["min_score"] == 0.8
    assert body["knowledge_base_id"] == "kb1"


def test_search_propagates_kb_error():
    """底层 KbError 应向上传播。"""
    import kb_http
    with patch("kb_search.request_json", side_effect=kb_http.KbError("auth", "bad")):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_search.search("kb1", "q")
    assert exc_info.value.code == "auth"
