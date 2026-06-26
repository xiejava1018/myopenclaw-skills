"""test_providers_github.py —— GithubUploader 单测（mock requests.put，无网络）。"""
import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

# 让 tests/ 能 import 到上一层的 providers 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers.github import GithubUploader  # noqa: E402


def _make_cfg(**overrides) -> SimpleNamespace:
    """造一份最小 config，默认值可被覆盖。"""
    base = dict(gh_token="tok", gh_owner="owner", gh_repo="repo",
                gh_branch="main", gh_domain="")
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeResp:
    """轻量假 Response：raise_for_status 默认不抛，json() 返回固定 sha。"""

    def __init__(self, *, raise_http_error: bool = False):
        self._raise = raise_http_error

    def raise_for_status(self):
        if self._raise:
            raise requests.HTTPError("403 Forbidden")

    def json(self):
        return {"content": {"sha": "abc123"}}


def test_default_domain_uses_raw(tmp_path, monkeypatch):
    # Arrange：gh_domain 为空 → 走 raw.githubusercontent.com 兜底
    img = tmp_path / "a.png"
    img.write_bytes(b"imgdata")
    monkeypatch.setattr(requests, "put", lambda *a, **k: _FakeResp())
    up = GithubUploader(_make_cfg(gh_domain=""))

    # Act
    res = up.upload(str(img), "blog/a.png")

    # Assert
    assert res.url == "https://raw.githubusercontent.com/owner/repo/main/blog/a.png"
    assert res.backend == "github"
    assert res.extra["commit_sha"] == "abc123"


def test_custom_domain(tmp_path, monkeypatch):
    # Arrange：自定义域名 → url 直接拼接 key
    img = tmp_path / "a.png"
    img.write_bytes(b"imgdata")
    monkeypatch.setattr(requests, "put", lambda *a, **k: _FakeResp())
    up = GithubUploader(_make_cfg(gh_domain="https://cdn.example.com"))

    # Act
    res = up.upload(str(img), "blog/a.png")

    # Assert
    assert res.url == "https://cdn.example.com/blog/a.png"


def test_request_correctness(tmp_path, monkeypatch):
    # Arrange：捕获 requests.put 入参，校验 URL/headers/body
    img = tmp_path / "pic.png"
    raw = b"\x89PNG\r\n\x1a\n pixels"
    img.write_bytes(raw)
    captured = {}
    monkeypatch.setattr(requests, "put", lambda url, headers=None, json=None:
                        captured.update(url=url, headers=headers, json=json) or _FakeResp())
    up = GithubUploader(_make_cfg())

    # Act
    up.upload(str(img), "blog/pic.png")

    # Assert：URL 含 owner/repo/key
    assert "owner" in captured["url"] and "repo" in captured["url"]
    assert captured["url"].endswith("/contents/blog/pic.png")
    # Authorization 头含 token
    assert captured["headers"]["Authorization"] == "token tok"
    # content 是文件内容的 base64，branch 正确
    assert base64.b64decode(captured["json"]["content"]) == raw
    assert captured["json"]["branch"] == "main"
    assert captured["json"]["message"] == "upload blog/pic.png"


def test_http_error_propagates(tmp_path, monkeypatch):
    # Arrange：fake Response 抛 HTTPError
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    monkeypatch.setattr(requests, "put", lambda *a, **k: _FakeResp(raise_http_error=True))
    up = GithubUploader(_make_cfg())
    # Act & Assert：upload 向上抛 HTTPError
    with pytest.raises(requests.HTTPError):
        up.upload(str(img), "blog/a.png")
