"""QiniuUploader 单元测试：用 sys.modules 注入 fake qiniu，不发真实请求、不装 SDK。"""
import sys
import types
from unittest.mock import MagicMock

import pytest

from providers.qiniu import QiniuUploader


class _FakeInfo:
    """模拟 qiniu 的 resp_info，ok() 控制成功标志。"""
    def __init__(self, ok: bool, status_code: int = 200):
        self._ok = ok
        self.status_code = status_code

    def ok(self) -> bool:
        return self._ok

    def __str__(self) -> str:
        return f"_FakeInfo(ok={self._ok}, status_code={self.status_code})"


class _FakeAuth:
    """模拟 qiniu.Auth，返回带 upload_token 的对象。"""
    def __init__(self, ak, sk):
        self.ak, self.sk = ak, sk

    def upload_token(self, bucket, key):
        return f"fake-token:{bucket}:{key}"


def _install_fake_qiniu(monkeypatch, put_file_ret=None):
    """注入 fake qiniu 模块到 sys.modules；put_file_ret=(ret, info)。"""
    mod = types.ModuleType("qiniu")
    mod.Auth = _FakeAuth
    put_file = MagicMock(return_value=put_file_ret)
    mod.put_file = put_file
    monkeypatch.setitem(sys.modules, "qiniu", mod)
    return put_file


def _make_cfg(domain="https://image2.ishareread.com"):
    return types.SimpleNamespace(
        qiniu_access_key="ak",
        qiniu_secret_key="sk",
        qiniu_bucket="bkt",
        qiniu_domain=domain,
        qiniu_area="z0",
        qiniu_path="blog",
    )


def test_upload_success(tmp_path, monkeypatch):
    # Arrange：造一个本地图片 + 成功的 fake put_file
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n")
    key = "blog/slug/x.png"
    put_file = _install_fake_qiniu(
        monkeypatch,
        put_file_ret=({"key": key}, _FakeInfo(ok=True, status_code=200)),
    )

    # Act
    res = QiniuUploader(_make_cfg()).upload(str(p), key)

    # Assert：put_file 入参正确，返回结果字段正确
    put_file.assert_called_once()
    args, _ = put_file.call_args
    assert key in args and str(p) in args
    assert res.backend == "qiniu"
    assert res.key == key
    assert res.url == "https://image2.ishareread.com/blog/slug/x.png"


def test_upload_domain_trailing_slash(tmp_path, monkeypatch):
    # Arrange：domain 带尾斜杠，join_url 应只保留一个
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n")
    key = "blog/y.png"
    _install_fake_qiniu(
        monkeypatch,
        put_file_ret=({"key": key}, _FakeInfo(ok=True, status_code=200)),
    )

    # Act
    res = QiniuUploader(_make_cfg(domain="https://image2.ishareread.com/")).upload(str(p), key)

    # Assert
    assert res.url == "https://image2.ishareread.com/blog/y.png"


def test_upload_failure_raises(tmp_path, monkeypatch):
    # Arrange：put_file 返回失败 info
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n")
    key = "blog/z.png"
    _install_fake_qiniu(
        monkeypatch,
        put_file_ret=({}, _FakeInfo(ok=False, status_code=400)),
    )

    # Act / Assert：失败路径抛 RuntimeError
    with pytest.raises(RuntimeError, match="七牛上传失败"):
        QiniuUploader(_make_cfg()).upload(str(p), key)
