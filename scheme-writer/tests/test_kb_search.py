"""kb_search.py 单元测试：mock HTTP 请求验证多来源检索/合并/部分失败。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_search  # noqa: E402
from kb_http import KbError  # noqa: E402


def _src_env(tmp_path, sources, aliases=None, default_source=None):
    lines = [f"SOURCES={sources}"]
    if aliases:
        lines.append(f"KB_ALIASES={aliases}")
    if default_source:
        lines.append(f"DEFAULT_SOURCE={default_source}")
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


SRCS = (
    '[{"name":"ops","url":"http://o/api/v1","api_key":"sk-o"},'
    '{"name":"sec","url":"http://s/api/v1","api_key":"sk-s"}]'
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """每个用例隔离环境：清旧 key + 旧单源配置 + chdir 到临时 .env。"""
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


# ---------------------------------------------------------------------------
# search_source：单实例检索（传 source dict，验证请求体/响应解析/客户端过滤）
# ---------------------------------------------------------------------------
def test_search_source_parses_chunks():
    """WeKnora 旧版响应：chunks 字段。"""
    source = {"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"}
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
        chunks = kb_search.search_source(source, "kb1", "test query")
    assert len(chunks) == 1
    assert chunks[0]["score"] == 0.9
    assert chunks[0]["source_doc"] == "doc.md"
    m.assert_called_once()
    call_args = m.call_args
    assert call_args.args[0] == "POST"
    assert call_args.args[1].endswith("/knowledge-search")
    body = call_args.kwargs["json_body"]
    assert body["query"] == "test query"
    assert body["knowledge_base_id"] == "kb1"
    assert body["top_k"] == 8
    assert body["min_score"] == 0.5
    # search_source 不打 source 标签（标签由合并层打）
    assert "source" not in chunks[0]
    assert "kb_id" not in chunks[0]


def test_search_source_parses_results_fallback():
    """WeKnora 新版响应：results 字段。"""
    source = {"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"}
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
        chunks = kb_search.search_source(source, "kb1", "q")
    assert chunks[0]["chunk_id"] == "c-2"
    assert chunks[0]["source_doc"] == "Doc2"
    assert chunks[0]["content"] == "world"


def test_search_source_custom_topk_and_min():
    """自定义 top_k / min_score 透传到请求体。"""
    source = {"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"}
    with patch("kb_search.request_json", return_value={"chunks": []}) as m:
        kb_search.search_source(source, "kb1", "q", top_k=3, min_score=0.8)
    body = m.call_args.kwargs["json_body"]
    assert body["top_k"] == 3
    assert body["min_score"] == 0.8
    assert body["knowledge_base_id"] == "kb1"


def test_search_source_client_min_score_filter():
    """score < min_score 的 chunk 客户端过滤丢弃（即便服务端忽略）。"""
    source = {"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"}
    api_response = {
        "chunks": [
            {"chunk_id": "a", "content": "x", "score": 0.9},
            {"chunk_id": "b", "content": "x", "score": 0.3},
        ]
    }
    with patch("kb_search.request_json", return_value=api_response):
        chunks = kb_search.search_source(source, "kb1", "q", min_score=0.5)
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "a"


def test_search_source_empty_response():
    """空响应返回空 chunks。"""
    source = {"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"}
    with patch("kb_search.request_json", return_value={}):
        chunks = kb_search.search_source(source, "kb1", "q")
    assert chunks == []


def test_search_source_propagates_kb_error():
    """底层 KbError 向上传播（单个来源失败由调用方捕获）。"""
    source = {"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"}
    with patch("kb_search.request_json", side_effect=KbError("auth", "bad")):
        with pytest.raises(KbError) as exc_info:
            kb_search.search_source(source, "kb1", "q")
    assert exc_info.value.code == "auth"


# ---------------------------------------------------------------------------
# run()：端到端多来源检索（解析 argv → 返回 payload dict）
# ---------------------------------------------------------------------------
def test_single_target_legacy_shape(tmp_path, monkeypatch):
    """单目标 → 老结构（无 sources/errors 字段），chunk 带 source 标签。"""
    _src_env(tmp_path, SRCS, aliases='{"ops/a":"k1"}')
    fake = {"chunks": [{"chunk_id": "c1", "content": "x", "score": 0.8}]}
    with patch("kb_search.request_json", return_value=fake):
        out = kb_search.run(["--kb", "ops/a", "--query", "q"])
    assert out["kb_id"] == "k1"
    assert "sources" not in out
    assert "errors" not in out
    assert out["chunks"][0]["source"] == "ops"
    assert out["chunks"][0]["kb_id"] == "k1"
    assert out["total"] == 1


def test_multi_target_merged_shape(tmp_path, monkeypatch):
    """多目标 → 新结构（sources + errors），每条 chunk 带 source。"""
    _src_env(tmp_path, SRCS, aliases='{"ops/a":"k1","sec/b":"k2"}')
    fake = {"chunks": [{"chunk_id": "c1", "content": "x", "score": 0.7}]}
    with patch("kb_search.request_json", return_value=fake):
        out = kb_search.run(["--kb", "ops/a,sec/b", "--query", "q"])
    assert set(out["sources"]) == {"ops", "sec"}
    assert out["total"] == 2
    assert all("source" in c for c in out["chunks"])
    assert "errors" in out
    assert out["errors"] == []


def test_partial_failure_returns_healthy(tmp_path, monkeypatch):
    """部分失败：健康源照常返回，失败的进 errors。"""
    _src_env(tmp_path, SRCS, aliases='{"ops/a":"k1","sec/b":"k2"}')

    def fake_req(method, url, **kw):
        if "http://s" in url:
            raise KbError("auth", "sec down")
        return {"chunks": [{"chunk_id": "c1", "content": "x", "score": 0.9}]}

    with patch("kb_search.request_json", side_effect=fake_req):
        out = kb_search.run(["--kb", "ops/a,sec/b", "--query", "q"])
    assert out["total"] == 1                      # ops 成功
    assert {c["source"] for c in out["chunks"]} == {"ops"}
    assert out["errors"][0]["source"] == "sec"
    assert out["errors"][0]["error"] == "auth"


def test_sort_no_cross_source_rerank(tmp_path, monkeypatch):
    """合并后按 (source, -score) 排序，不跨源全局重排。"""
    _src_env(tmp_path, SRCS, aliases='{"ops/a":"k1","sec/b":"k2"}')
    # ops 两条低分，sec 一条高分——跨源重排会把 sec 放第一，本设计不应
    calls = iter([
        {"chunks": [{"chunk_id": "c1", "content": "o1", "score": 0.6},
                    {"chunk_id": "c2", "content": "o2", "score": 0.55}]},  # ops
        {"chunks": [{"chunk_id": "c3", "content": "s1", "score": 0.95}]},  # sec 高分
    ])

    def fake_req(method, url, **kw):
        return next(calls)

    with patch("kb_search.request_json", side_effect=fake_req):
        out = kb_search.run(["--kb", "ops/a,sec/b", "--query", "q"])
    sources_order = [c["source"] for c in out["chunks"]]
    # ops 的两条在前（按 score 降序 0.6,0.55），sec 在后——不是全局 0.95,0.6,0.55
    assert sources_order == ["ops", "ops", "sec"]


def test_min_score_client_filter(tmp_path, monkeypatch):
    """score < min_score 的 chunk 客户端过滤丢弃。"""
    _src_env(tmp_path, SRCS, aliases='{"ops/a":"k1"}')
    fake = {"chunks": [
        {"chunk_id": "c1", "content": "hi", "score": 0.8},
        {"chunk_id": "c2", "content": "lo", "score": 0.3},  # 低于默认 0.5
    ]}
    with patch("kb_search.request_json", return_value=fake):
        out = kb_search.run(["--kb", "ops/a", "--query", "q"])
    assert out["total"] == 1
    assert out["chunks"][0]["chunk_id"] == "c1"


def test_all_fail_raises_kb_error(tmp_path, monkeypatch):
    """全失败（无健康源）→ run() 抛 KbError。"""
    _src_env(tmp_path, SRCS, aliases='{"ops/a":"k1","sec/b":"k2"}')

    def fake_req(method, url, **kw):
        raise KbError("server", "down")

    with patch("kb_search.request_json", side_effect=fake_req):
        with pytest.raises(KbError):
            kb_search.run(["--kb", "ops/a,sec/b", "--query", "q"])
