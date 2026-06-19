"""kb_http.py 单元测试：HTTP 错误归一化、退出码语义。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_http  # noqa: E402


def _mock_response(status_code: int, body=None, text: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or ""
    if body is not None:
        resp.json.return_value = body
    else:
        resp.json.side_effect = ValueError("not json")
    return resp


def test_request_json_success():
    with patch("kb_http.requests.request", return_value=_mock_response(200, {"ok": True})) as m:
        result = kb_http.request_json("GET", "http://x", api_key="k")
    assert result == {"ok": True}
    m.assert_called_once()


def test_request_json_401_raises_auth():
    with patch("kb_http.requests.request", return_value=_mock_response(401)):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_http.request_json("GET", "http://x", api_key="bad")
    assert exc_info.value.code == "auth"
    assert exc_info.value.extra["status"] == 401


def test_request_json_404_raises_kb_not_found():
    with patch("kb_http.requests.request", return_value=_mock_response(404)):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_http.request_json("GET", "http://x", api_key="k")
    assert exc_info.value.code == "kb_not_found"


def test_request_json_500_raises_server():
    with patch("kb_http.requests.request", return_value=_mock_response(500, text="boom")):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_http.request_json("GET", "http://x", api_key="k")
    assert exc_info.value.code == "server"
    assert "500" in exc_info.value.message


def test_request_json_400_raises_bad_args():
    with patch("kb_http.requests.request", return_value=_mock_response(400, text="bad req")):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_http.request_json("POST", "http://x", api_key="k", json_body={"q": 1})
    assert exc_info.value.code == "bad_args"


def test_request_json_timeout_raises_timeout():
    with patch("kb_http.requests.request", side_effect=requests.Timeout("slow")):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_http.request_json("GET", "http://x", api_key="k", timeout=1)
    assert exc_info.value.code == "timeout"


def test_request_json_request_exception_raises_server():
    with patch("kb_http.requests.request", side_effect=requests.ConnectionError("refused")):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_http.request_json("GET", "http://x", api_key="k")
    assert exc_info.value.code == "server"


def test_request_json_invalid_json_raises_server():
    resp = _mock_response(200, text="not json {")
    resp.json.side_effect = ValueError("not json")
    with patch("kb_http.requests.request", return_value=resp):
        with pytest.raises(kb_http.KbError) as exc_info:
            kb_http.request_json("GET", "http://x", api_key="k")
    assert exc_info.value.code == "server"


def test_emit_error_writes_stderr_and_exits(capsys):
    with pytest.raises(SystemExit) as exc_info:
        kb_http.emit_error(kb_http.KbError("auth", "bad key"))
    captured = capsys.readouterr()
    payload = json.loads(captured.err.strip())
    assert payload["error"] == "auth"
    assert payload["message"] == "bad key"
    assert exc_info.value.code == kb_http.EXIT_AUTH


def test_emit_error_exit_code_table():
    """错误码 → 退出码映射。"""
    for code, expected in [
        ("bad_args", kb_http.EXIT_BAD_ARGS),
        ("auth", kb_http.EXIT_AUTH),
        ("kb_not_found", kb_http.EXIT_KB_NOT_FOUND),
        ("timeout", kb_http.EXIT_TIMEOUT),
        ("server", kb_http.EXIT_SERVER),
        ("file_read", kb_http.EXIT_FILE_READ),
    ]:
        with pytest.raises(SystemExit) as exc_info:
            kb_http.emit_error(kb_http.KbError(code, "x"))
        assert exc_info.value.code == expected, f"{code} should map to {expected}"


def test_emit_ok_writes_stdout_json(capsys):
    kb_http.emit_ok({"ok": True, "doc_id": "abc"})
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip()) == {"ok": True, "doc_id": "abc"}
