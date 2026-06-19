"""kb_docs.py 单元测试：mock HTTP 验证请求参数/响应解析/字段兼容/翻页/错误传播。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_docs  # noqa: E402
import kb_http  # noqa: E402


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


def test_list_docs_default_params():
    """默认参数：page=1, page_size=20, fetch_all=False。"""
    api_response = {
        "data": {
            "items": [
                {
                    "id": "d-1",
                    "title": "doc1.pdf",
                    "file_name": "doc1.pdf",
                    "file_type": "pdf",
                    "file_size": 1024,
                    "parse_status": "completed",
                    "enable_status": "enabled",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "processed_at": "2026-01-01T00:00:00Z",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
        },
        "success": True,
    }
    with patch("kb_docs.request_json", return_value=api_response) as m:
        result = kb_docs.list_docs("kb1")
    assert result["kb_id"] == "kb1"
    assert result["total"] == 1
    assert result["page"] == 1
    assert result["page_size"] == 20
    assert len(result["documents"]) == 1
    assert result["documents"][0]["doc_id"] == "d-1"
    assert result["documents"][0]["parse_status"] == "completed"
    # 验证请求参数
    call = m.call_args
    assert call.args[0] == "GET"
    assert call.args[1].endswith("/knowledge-bases/kb1/knowledge")
    assert call.kwargs["params"] == {"page": 1, "page_size": 20}


def test_list_docs_custom_pagination():
    """自定义 page / page_size。"""
    api_response = {"data": {"items": [], "total": 0}}
    with patch("kb_docs.request_json", return_value=api_response) as m:
        result = kb_docs.list_docs("kb1", page=3, page_size=50)
    assert result["page"] == 3
    assert result["page_size"] == 50
    assert m.call_args.kwargs["params"] == {"page": 3, "page_size": 50}


def test_list_docs_fetch_all_paginates():
    """--all 模式自动翻页直到取完。"""
    page1 = {
        "data": {
            "items": [{"id": f"d-{i}", "title": f"d{i}"} for i in range(20)],
            "total": 35,
        }
    }
    page2 = {
        "data": {
            "items": [{"id": f"d-{i}", "title": f"d{i}"} for i in range(20, 35)],
            "total": 35,
        }
    }
    with patch("kb_docs.request_json", side_effect=[page1, page2]) as m:
        result = kb_docs.list_docs("kb1", page_size=20, fetch_all=True)
    assert len(result["documents"]) == 35
    # 翻页调用了 2 次
    assert m.call_count == 2
    # 第 2 次请求 page=2
    assert m.call_args_list[1].kwargs["params"]["page"] == 2


def test_list_docs_field_compat():
    """兼容服务端可能使用 doc_id / document_id / name / filename 等旧字段。"""
    api_response = {
        "data": {
            "items": [
                {
                    "doc_id": "legacy-id",
                    "name": "legacy-name.txt",
                    "filename": "legacy-name.txt",
                    "size": 2048,
                }
            ],
            "total": 1,
        }
    }
    with patch("kb_docs.request_json", return_value=api_response):
        result = kb_docs.list_docs("kb1")
    doc = result["documents"][0]
    assert doc["doc_id"] == "legacy-id"
    assert doc["title"] == "legacy-name.txt"
    assert doc["file_name"] == "legacy-name.txt"
    assert doc["file_size"] == 2048


def test_list_docs_empty_response():
    """空响应返回 total=0, documents=[]。"""
    with patch("kb_docs.request_json", return_value={"data": {"items": [], "total": 0}}):
        result = kb_docs.list_docs("kb1")
    assert result["total"] == 0
    assert result["documents"] == []


def test_list_docs_propagates_auth_error():
    """底层 KbError 应向上传播。"""
    with patch(
        "kb_docs.request_json",
        side_effect=kb_http.KbError("auth", "bad key"),
    ):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_docs.list_docs("kb1")
    assert exc_info.value.code == "auth"
