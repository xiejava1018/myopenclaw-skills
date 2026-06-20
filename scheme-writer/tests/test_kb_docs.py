"""kb_docs.py 单元测试：mock HTTP 验证请求参数/响应解析/字段兼容/翻页/错误传播。

覆盖：
- 单来源 list_docs(source, kb_id) 请求/响应/翻页/字段兼容/错误传播
- 多来源：用解析后 source 的 url/key、返回 source 标签
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_docs  # noqa: E402
import kb_http  # noqa: E402


def _write_env(
    tmp_path: Path,
    *,
    sources: list[dict] | None = None,
    aliases: dict[str, str] | None = None,
    default_source: str | None = None,
) -> None:
    """写一个最小 .env，只有多来源配置（SOURCES / KB_ALIASES / DEFAULT_SOURCE）。"""
    lines: list[str] = []
    if sources is not None:
        lines.append(f"SOURCES={json.dumps(sources, ensure_ascii=False)}")
    if aliases is not None:
        lines.append(f"KB_ALIASES={json.dumps(aliases, ensure_ascii=False)}")
    if default_source is not None:
        lines.append(f"DEFAULT_SOURCE={default_source}")
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """每个测试拿到干净的工作区 + 清空相关环境变量。"""
    monkeypatch.chdir(tmp_path)
    for k in (
        "KNOWLEDGE_BASE_URL",
        "KNOWLEDGE_BASE_API_KEY",
        "DEFAULT_RETRIEVE_KB",
        "DEFAULT_UPLOAD_KB",
        "SOURCES",
        "DEFAULT_SOURCE",
        "KB_ALIASES",
    ):
        monkeypatch.delenv(k, raising=False)
    yield


# 单来源 fixture：默认来源 "ops"，供单来源行为测试复用
_SRC = [{"name": "ops", "url": "http://test", "api_key": "sk-test"}]


def test_list_docs_default_params(tmp_path):
    """默认参数：page=1, page_size=20, fetch_all=False。"""
    _write_env(tmp_path, sources=_SRC)
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
        result = kb_docs.list_docs("ops", "kb1")
    assert result["source"] == "ops"
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
    assert call.kwargs["api_key"] == "sk-test"
    assert call.kwargs["params"] == {"page": 1, "page_size": 20}


def test_list_docs_custom_pagination(tmp_path):
    """自定义 page / page_size。"""
    _write_env(tmp_path, sources=_SRC)
    api_response = {"data": {"items": [], "total": 0}}
    with patch("kb_docs.request_json", return_value=api_response) as m:
        result = kb_docs.list_docs("ops", "kb1", page=3, page_size=50)
    assert result["page"] == 3
    assert result["page_size"] == 50
    assert m.call_args.kwargs["params"] == {"page": 3, "page_size": 50}


def test_list_docs_fetch_all_paginates(tmp_path):
    """--all 模式自动翻页直到取完。"""
    _write_env(tmp_path, sources=_SRC)
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
        result = kb_docs.list_docs("ops", "kb1", page_size=20, fetch_all=True)
    assert len(result["documents"]) == 35
    # 翻页调用了 2 次
    assert m.call_count == 2
    # 第 2 次请求 page=2
    assert m.call_args_list[1].kwargs["params"]["page"] == 2


def test_list_docs_field_compat(tmp_path):
    """兼容服务端可能使用 doc_id / document_id / name / filename 等旧字段。"""
    _write_env(tmp_path, sources=_SRC)
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
        result = kb_docs.list_docs("ops", "kb1")
    doc = result["documents"][0]
    assert doc["doc_id"] == "legacy-id"
    assert doc["title"] == "legacy-name.txt"
    assert doc["file_name"] == "legacy-name.txt"
    assert doc["file_size"] == 2048


def test_list_docs_empty_response(tmp_path):
    """空响应返回 total=0, documents=[]。"""
    _write_env(tmp_path, sources=_SRC)
    with patch("kb_docs.request_json", return_value={"data": {"items": [], "total": 0}}):
        result = kb_docs.list_docs("ops", "kb1")
    assert result["total"] == 0
    assert result["documents"] == []


def test_list_docs_propagates_auth_error(tmp_path):
    """底层 KbError 应向上传播。"""
    _write_env(tmp_path, sources=_SRC)
    with patch(
        "kb_docs.request_json",
        side_effect=kb_http.KbError("auth", "bad key"),
    ):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_docs.list_docs("ops", "kb1")
    assert exc_info.value.code == "auth"


# ---------- 多来源接入解析层 ----------


def test_list_docs_uses_resolved_source(tmp_path):
    """list_docs(source, kb_id) 用该源的 url/key，返回带 source 标签。"""
    _write_env(
        tmp_path,
        sources=[
            {"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"},
            {"name": "prod", "url": "http://p/api/v1", "api_key": "sk-p"},
        ],
        aliases={"ops/规范库": "kb-1"},
    )
    fake = {
        "data": {
            "items": [{"id": "d1", "title": "doc", "parse_status": "completed"}],
            "total": 1,
        }
    }
    with patch("kb_docs.request_json", return_value=fake) as m:
        out = kb_docs.list_docs("ops", "kb-1")
    assert out["source"] == "ops"
    assert out["kb_id"] == "kb-1"
    assert out["total"] == 1
    # 确认打到 ops 的 url（带 /api/v1 前缀，rstrip 保留）
    assert m.call_args.args[1] == "http://o/api/v1/knowledge-bases/kb-1/knowledge"
    assert m.call_args.kwargs["api_key"] == "sk-o"


def test_list_docs_unknown_source_raises(tmp_path):
    """未知来源 → ConfigError（get_source 抛出）。"""
    _write_env(tmp_path, sources=_SRC)
    with pytest.raises(kb_docs.ConfigError):
        kb_docs.list_docs("nope", "kb1")
