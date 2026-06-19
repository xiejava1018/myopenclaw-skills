"""kb_upload.py 单元测试。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_http  # noqa: E402
import kb_upload  # noqa: E402


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


def test_upload_sends_file_content(tmp_path):
    f = tmp_path / "scheme.md"
    f.write_text("# Title\n\nhello", encoding="utf-8")
    # 真实端点返回：{"data": {"id": "..."}, "success": true}
    with patch("kb_upload.request_json", return_value={"data": {"id": "d-1"}, "success": True}) as m:
        result = kb_upload.upload("kb1", str(f), "My Scheme")
    assert result["ok"] is True
    assert result["doc_id"] == "d-1"
    assert result["size_bytes"] == f.stat().st_size
    body = m.call_args.kwargs["json_body"]
    assert body["title"] == "My Scheme"
    assert body["content"] == "# Title\n\nhello"
    assert body["status"] == "publish"  # 真实端点用 publish（非 published）
    # 真实端点：POST /knowledge-bases/{id}/knowledge/manual
    assert m.call_args.args[0] == "POST"
    assert m.call_args.args[1].endswith("/knowledge-bases/kb1/knowledge/manual")


def test_upload_with_tags(tmp_path):
    """manual 端点只支持单个 tag_id；多 tag 场景下合并到 title 前缀。"""
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    with patch("kb_upload.request_json", return_value={"data": {"id": "d"}, "success": True}) as m:
        kb_upload.upload("kb1", str(f), "T", tags=["a", "b"])
    body = m.call_args.kwargs["json_body"]
    # tags 已拼到 title 前缀
    assert "tags" not in body
    assert body["title"] == "[a/b] T"


def test_upload_uses_id_field_fallback(tmp_path):
    """兼容 {id: ...} 旧版响应。"""
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    with patch("kb_upload.request_json", return_value={"id": "legacy-id"}):
        result = kb_upload.upload("kb1", str(f), "T")
    assert result["doc_id"] == "legacy-id"


def test_upload_missing_file_raises_file_read(tmp_path):
    """文件不存在时抛 file_read 错误。"""
    with pytest.raises(kb_http.KbError) as exc_info:
        kb_upload.upload("kb1", str(tmp_path / "no-such.md"), "T")
    assert exc_info.value.code == "file_read"
    assert "no-such.md" in exc_info.value.message


def test_upload_propagates_auth_error(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    with patch("kb_upload.request_json", side_effect=kb_http.KbError("auth", "bad key")):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_upload.upload("kb1", str(f), "T")
    assert exc_info.value.code == "auth"


def test_upload_main_emits_async_hint(tmp_path, capsys):
    """main() 在成功上传后应向 stderr 输出异步向量化提示。"""
    f = tmp_path / "scheme.md"
    f.write_text("# hello", encoding="utf-8")
    test_args = [
        "kb_upload.py",
        "--kb", "kb1",
        "--file", str(f),
        "--title", "T",
    ]
    with patch.object(sys, "argv", test_args), \
         patch("kb_upload.request_json", return_value={"data": {"id": "d-1"}, "success": True}):
        kb_upload.main()
    captured = capsys.readouterr()
    assert "异步" in captured.err
    assert "kb_docs.py" in captured.err
    assert "parse_status" in captured.err
    # stdout 仍为 JSON 化的 ok 响应
    import json
    out_json = json.loads(captured.out)
    assert out_json["ok"] is True
    assert out_json["doc_id"] == "d-1"
