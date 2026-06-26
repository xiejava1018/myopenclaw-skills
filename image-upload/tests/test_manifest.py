"""test_manifest.py —— manifest 纯逻辑单测（pytest，无网络）。"""
import json
import sys
from pathlib import Path

# 让 tests/ 能 import 到上一层的 manifest 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from manifest import Manifest, sha256_of_file  # noqa: E402

# b"hello" 的 sha256，已知值
HELLO_SHA = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_sha256_known_value(tmp_path):
    # Arrange
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")

    # Act
    digest = sha256_of_file(f)

    # Assert
    assert digest == HELLO_SHA


def test_sha256_same_content_same_hash(tmp_path):
    # Arrange：两份相同内容的文件
    (tmp_path / "x.bin").write_bytes(b"same")
    (tmp_path / "y.bin").write_bytes(b"same")

    # Act & Assert
    assert sha256_of_file(tmp_path / "x.bin") == sha256_of_file(tmp_path / "y.bin")


def test_sha256_different_content_different_hash(tmp_path):
    # Arrange
    (tmp_path / "x.bin").write_bytes(b"foo")
    (tmp_path / "y.bin").write_bytes(b"bar")

    # Act & Assert
    assert sha256_of_file(tmp_path / "x.bin") != sha256_of_file(tmp_path / "y.bin")


def test_sha256_accepts_str_and_path(tmp_path):
    # Arrange
    f = tmp_path / "z.bin"
    f.write_bytes(b"data")

    # Act & Assert：str 与 Path 入参结果一致
    assert sha256_of_file(str(f)) == sha256_of_file(f)


def test_put_get_roundtrip(tmp_path):
    # Arrange
    man = Manifest(tmp_path / "m.json")

    # Act
    man.put("h1", "qiniu", "/abs/a.png", "blog/a.png", "https://cdn/a.png")

    # Assert
    assert man.get("h1", "qiniu") == {"key": "blog/a.png", "url": "https://cdn/a.png"}


def test_multiple_backends_isolated(tmp_path):
    # Arrange
    man = Manifest(tmp_path / "m.json")

    # Act：同一 hash 先写 qiniu 再写 github
    man.put("h1", "qiniu", "/abs/a.png", "blog/q/a.png", "https://q/a.png")
    man.put("h1", "github", "/abs/a.png", "blog/g/a.png", "https://g/a.png")

    # Assert：两个 backend 各自正确，互不覆盖
    assert man.get("h1", "qiniu") == {"key": "blog/q/a.png", "url": "https://q/a.png"}
    assert man.get("h1", "github") == {"key": "blog/g/a.png", "url": "https://g/a.png"}
    # local 字段被记录
    assert man.data["h1"]["local"] == "/abs/a.png"


def test_persistence_across_instances(tmp_path):
    # Arrange
    path = tmp_path / "m.json"
    man = Manifest(path)
    man.put("h1", "qiniu", "/abs/a.png", "blog/a.png", "https://cdn/a.png")

    # Act：保存后用新实例重新加载
    man.save()
    man2 = Manifest(path)

    # Assert：跨实例仍能取到
    assert man2.get("h1", "qiniu") == {"key": "blog/a.png", "url": "https://cdn/a.png"}
    assert man2.data["h1"]["local"] == "/abs/a.png"


def test_load_corrupt_json_is_empty(tmp_path):
    # Arrange：写一份非法 JSON
    path = tmp_path / "m.json"
    path.write_text("{not valid json", encoding="utf-8")

    # Act
    man = Manifest(path)

    # Assert：容错为空，不抛异常
    assert man.data == {}


def test_load_non_dict_top_level_is_empty(tmp_path):
    # Arrange：JSON 合法但顶层是 list（不是 dict）
    path = tmp_path / "m.json"
    path.write_text(json.dumps(["a", "b"]), encoding="utf-8")

    # Act & Assert
    assert Manifest(path).data == {}


def test_get_missing_returns_none(tmp_path):
    # Arrange
    man = Manifest(tmp_path / "m.json")

    # Act & Assert：hash 不存在 → None；hash 存在但 backend 未记 → None
    assert man.get("nope", "qiniu") is None
    man.put("h1", "qiniu", "/a.png", "k", "u")
    assert man.get("h1", "github") is None


def test_save_creates_parent_dir(tmp_path):
    # Arrange：目标在尚不存在的子目录下
    path = tmp_path / "sub" / "deep" / "m.json"
    man = Manifest(path)
    man.put("h1", "qiniu", "/a.png", "blog/a.png", "https://cdn/a.png")

    # Act
    man.save()

    # Assert：父目录被创建，文件可读
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["h1"]["qiniu"]["url"] == "https://cdn/a.png"


def test_init_missing_file_is_empty(tmp_path):
    # Arrange：路径文件不存在
    # Act
    man = Manifest(tmp_path / "absent.json")

    # Assert
    assert man.data == {}
    assert not (tmp_path / "absent.json").exists()
