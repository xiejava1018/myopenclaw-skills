"""kb_upload.py 单元测试。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_http  # noqa: E402
import kb_upload  # noqa: E402


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


def test_upload_sends_file_content(tmp_path):
    _write_env(tmp_path, sources=_SRC)
    f = tmp_path / "scheme.md"
    f.write_text("# Title\n\nhello", encoding="utf-8")
    # 真实端点返回：{"data": {"id": "..."}, "success": true}
    with patch("kb_upload.request_json", return_value={"data": {"id": "d-1"}, "success": True}) as m:
        result = kb_upload.upload("ops", "kb1", str(f), "My Scheme")
    assert result["ok"] is True
    assert result["doc_id"] == "d-1"
    assert result["source"] == "ops"
    assert result["size_bytes"] == f.stat().st_size
    body = m.call_args.kwargs["json_body"]
    assert body["title"] == "My Scheme"
    assert body["content"] == "# Title\n\nhello"
    assert body["status"] == "publish"  # 真实端点用 publish（非 published）
    # 真实端点：POST /knowledge-bases/{id}/knowledge/manual
    assert m.call_args.args[0] == "POST"
    assert m.call_args.args[1].endswith("/knowledge-bases/kb1/knowledge/manual")
    assert m.call_args.kwargs["api_key"] == "sk-test"


def test_upload_with_tags(tmp_path):
    """manual 端点只支持单个 tag_id；多 tag 场景下合并到 title 前缀。"""
    _write_env(tmp_path, sources=_SRC)
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    with patch("kb_upload.request_json", return_value={"data": {"id": "d"}, "success": True}) as m:
        kb_upload.upload("ops", "kb1", str(f), "T", tags=["a", "b"])
    body = m.call_args.kwargs["json_body"]
    # tags 已拼到 title 前缀
    assert "tags" not in body
    assert body["title"] == "[a/b] T"


def test_upload_uses_id_field_fallback(tmp_path):
    """兼容 {id: ...} 旧版响应。"""
    _write_env(tmp_path, sources=_SRC)
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    with patch("kb_upload.request_json", return_value={"id": "legacy-id"}):
        result = kb_upload.upload("ops", "kb1", str(f), "T")
    assert result["doc_id"] == "legacy-id"


def test_upload_missing_file_raises_file_read(tmp_path):
    """文件不存在时抛 file_read 错误。"""
    _write_env(tmp_path, sources=_SRC)
    with pytest.raises(kb_http.KbError) as exc_info:
        kb_upload.upload("ops", "kb1", str(tmp_path / "no-such.md"), "T")
    assert exc_info.value.code == "file_read"
    assert "no-such.md" in exc_info.value.message


def test_upload_propagates_auth_error(tmp_path):
    _write_env(tmp_path, sources=_SRC)
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    with patch("kb_upload.request_json", side_effect=kb_http.KbError("auth", "bad key")):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_upload.upload("ops", "kb1", str(f), "T")
    assert exc_info.value.code == "auth"


def test_upload_main_emits_async_hint(tmp_path, capsys):
    """main() 在成功上传后应向 stderr 输出异步向量化提示。"""
    _write_env(tmp_path, sources=_SRC, aliases={"ops/kb1": "kb1"})
    f = tmp_path / "scheme.md"
    f.write_text("# hello", encoding="utf-8")
    test_args = [
        "kb_upload.py",
        "--kb", "ops/kb1",
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
    out_json = json.loads(captured.out)
    assert out_json["ok"] is True
    assert out_json["doc_id"] == "d-1"


# ---------- 多来源接入解析层 ----------


def test_upload_uses_resolved_source(tmp_path):
    """upload(source, kb_id, ...) 用该源的 url/key，返回带 source 标签。"""
    _write_env(
        tmp_path,
        sources=[{"name": "ops", "url": "http://o/api/v1", "api_key": "sk-o"}],
        aliases={"ops/方案库": "kb-1"},
    )
    f = tmp_path / "doc.md"
    f.write_text("# hi", encoding="utf-8")
    with patch("kb_upload.request_json", return_value={"data": {"id": "doc-1"}}) as m:
        out = kb_upload.upload("ops", "kb-1", str(f), "标题")
    assert out["source"] == "ops"
    assert out["doc_id"] == "doc-1"
    assert out["kb_id"] == "kb-1"
    assert m.call_args.args[1] == "http://o/api/v1/knowledge-bases/kb-1/knowledge/manual"
    assert m.call_args.kwargs["api_key"] == "sk-o"


def _run_upload(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess:
    """以子进程方式跑 kb_upload.py，HOME 指向临时目录避免污染真实配置。"""
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Windows 兼容
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "kb_upload.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
    )


def test_upload_multi_target_rejected(tmp_path):
    """--kb 多目标 → 拒绝（上传不能跨源），退出码 2 + bad_args。"""
    _write_env(
        tmp_path,
        sources=[
            {"name": "ops", "url": "http://o", "api_key": "sk-o"},
            {"name": "sec", "url": "http://s", "api_key": "sk-s"},
        ],
        aliases={"ops/a": "k1", "sec/b": "k2"},
    )
    f = tmp_path / "doc.md"
    f.write_text("# hi", encoding="utf-8")
    proc = _run_upload(
        "--kb", "ops/a,sec/b",
        "--file", str(f),
        "--title", "t",
        cwd=tmp_path,
        home=tmp_path,
    )
    assert proc.returncode == 2
    assert "唯一" in proc.stderr or "单一" in proc.stderr
    # 错误信封是 bad_args
    assert "bad_args" in proc.stderr
