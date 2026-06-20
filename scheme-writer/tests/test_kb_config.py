"""kb_config.py 单元测试。

通过修改 sys.path 让测试在仓库根或 CI 环境都能跑。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 把 scripts/ 加进 path，让 from kb_config import ... 能工作
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_config  # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """每个用例前清空相关环境变量并把 cwd 切到 tmp_path（避免真实 ~/.env 干扰）。"""
    for key in (
        "KNOWLEDGE_BASE_URL",
        "KNOWLEDGE_BASE_API_KEY",
        "DEFAULT_RETRIEVE_KB",
        "DEFAULT_UPLOAD_KB",
        "KB_ALIASES",
        "SOURCES",
        "DEFAULT_SOURCE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    yield


def test_get_config_returns_empty_when_no_env(monkeypatch, tmp_path):
    """没有任何 .env 时返回空字典。"""
    result = kb_config.get_config()
    assert result == {}


def test_get_config_reads_user_env(monkeypatch, tmp_path):
    """从 $HOME/.claude/scheme-writer/.env 加载。"""
    user_env = Path.home() / ".claude" / "scheme-writer" / ".env"
    original = user_env.read_bytes() if user_env.exists() else None

    user_env.parent.mkdir(parents=True, exist_ok=True)
    user_env.write_text(
        "KNOWLEDGE_BASE_URL=http://example.com\n"
        "KNOWLEDGE_BASE_API_KEY=sk-test\n",
        encoding="utf-8",
    )
    try:
        result = kb_config.get_config()
        assert result["KNOWLEDGE_BASE_URL"] == "http://example.com"
        assert result["KNOWLEDGE_BASE_API_KEY"] == "sk-test"
    finally:
        # 恢复（避免污染用户家目录）
        if original is None:
            user_env.unlink(missing_ok=True)
        else:
            user_env.write_bytes(original)


def test_get_config_workspace_env_fallback(tmp_path):
    """找不到用户级时回退到工作区 .env。"""
    workspace_env = tmp_path / ".env"
    workspace_env.write_text("KNOWLEDGE_BASE_URL=http://ws.local\n", encoding="utf-8")
    # mock _find_env_path 找用户级时不存在
    cfg = kb_config.get_config()
    assert cfg["KNOWLEDGE_BASE_URL"] == "http://ws.local"


def test_get_config_env_var_overrides_file(monkeypatch, tmp_path):
    """进程环境变量优先于 .env 文件。"""
    workspace_env = tmp_path / ".env"
    workspace_env.write_text("KNOWLEDGE_BASE_URL=http://from-file\n", encoding="utf-8")
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "http://from-env")
    cfg = kb_config.get_config()
    assert cfg["KNOWLEDGE_BASE_URL"] == "http://from-env"


def test_require_raises_when_missing():
    """缺配置时 raise ConfigError。"""
    with pytest.raises(kb_config.ConfigError) as exc_info:
        kb_config.require("KNOWLEDGE_BASE_URL")
    assert "KNOWLEDGE_BASE_URL" in str(exc_info.value)
    assert "init.py" in str(exc_info.value)


def test_require_returns_value_when_present(monkeypatch, tmp_path):
    """配置存在时返回 strip 后的值。"""
    workspace_env = tmp_path / ".env"
    workspace_env.write_text("KNOWLEDGE_BASE_API_KEY=  sk-abc  \n", encoding="utf-8")
    val = kb_config.require("KNOWLEDGE_BASE_API_KEY")
    assert val == "sk-abc"


def test_write_env_creates_file(tmp_path):
    """write_env 写入目标路径并自动 mkdir。"""
    target = tmp_path / "nested" / ".env"
    result = kb_config.write_env({"KNOWLEDGE_BASE_URL": "http://x"}, path=target)
    assert result == target
    assert target.is_file()
    assert "KNOWLEDGE_BASE_URL=http://x" in target.read_text(encoding="utf-8")


def test_load_env_ignores_comments_and_blanks(tmp_path):
    """空行与 # 注释被忽略。"""
    # 让 _USER_CONFIG 指向不存在，强制 _find_env_path 走工作区
    kb_config._USER_CONFIG = tmp_path / "no-such-user-env"  # type: ignore[attr-defined]
    workspace_env = tmp_path / ".env"
    workspace_env.write_text(
        "# this is a comment\n"
        "\n"
        "KNOWLEDGE_BASE_URL=http://x\n"
        "  # indented comment\n"
        "DEFAULT_RETRIEVE_KB=kb_a\n",
        encoding="utf-8",
    )
    result = kb_config.get_config()
    assert result["KNOWLEDGE_BASE_URL"] == "http://x"
    assert result["DEFAULT_RETRIEVE_KB"] == "kb_a"


# ---------------------------------------------------------------------------
# KB_ALIASES 相关用例（v1.1 新增）
# ---------------------------------------------------------------------------


def test_get_aliases_empty_when_missing(tmp_path):
    """KB_ALIASES 缺失时返回空 dict。"""
    workspace_env = tmp_path / ".env"
    workspace_env.write_text("KNOWLEDGE_BASE_URL=http://x\n", encoding="utf-8")
    assert kb_config.get_aliases() == {}


def test_get_aliases_parses_json(tmp_path):
    """KB_ALIASES 为合法 JSON 时解析为 dict。"""
    workspace_env = tmp_path / ".env"
    workspace_env.write_text(
        'KB_ALIASES={"技术规范库":"kb_id_001","方案库":"kb_id_002"}\n',
        encoding="utf-8",
    )
    aliases = kb_config.get_aliases()
    assert aliases == {"技术规范库": "kb_id_001", "方案库": "kb_id_002"}


def test_get_aliases_invalid_json_falls_back(capsys, tmp_path):
    """KB_ALIASES 非法 JSON 时降级为 {} 并 stderr 提示。"""
    workspace_env = tmp_path / ".env"
    workspace_env.write_text("KB_ALIASES=not-json\n", encoding="utf-8")
    aliases = kb_config.get_aliases()
    assert aliases == {}
    captured = capsys.readouterr()
    assert "不是合法 JSON" in captured.err


def test_get_config_keeps_raw_aliases_string(tmp_path):
    """get_config() 返回 KB_ALIASES 原始字符串键；get_aliases() 单独解析。"""
    workspace_env = tmp_path / ".env"
    workspace_env.write_text(
        'KNOWLEDGE_BASE_URL=http://x\nKB_ALIASES={"a":"b"}\n',
        encoding="utf-8",
    )
    cfg = kb_config.get_config()
    assert cfg["KB_ALIASES"] == '{"a":"b"}'
    assert "aliases" not in cfg  # 嵌套字段由 get_aliases() 单独提供
    assert kb_config.get_aliases() == {"a": "b"}


def test_set_aliases_writes_json(tmp_path):
    """set_aliases() 写入 KB_ALIASES 为 JSON 字符串。"""
    target = tmp_path / ".env"
    # 先写一个空 .env 让 config_path() 找到
    target.write_text("KNOWLEDGE_BASE_URL=http://x\n", encoding="utf-8")
    import os
    os.chdir(tmp_path)
    path = kb_config.set_aliases({"技术规范库": "kb_id_001", "方案库": "kb_id_002"})
    assert path == target
    content = target.read_text(encoding="utf-8")
    assert "KB_ALIASES=" in content
    # 解析回看
    assert kb_config.get_aliases() == {"技术规范库": "kb_id_001", "方案库": "kb_id_002"}


def test_set_aliases_merges_with_existing(tmp_path):
    """set_aliases() 不会丢掉已有配置。"""
    target = tmp_path / ".env"
    target.write_text(
        "KNOWLEDGE_BASE_URL=http://x\n"
        "KNOWLEDGE_BASE_API_KEY=sk-test\n"
        "DEFAULT_RETRIEVE_KB=kb_a\n",
        encoding="utf-8",
    )
    import os
    os.chdir(tmp_path)
    kb_config.set_aliases({"a": "1"})
    cfg = kb_config.get_config()
    assert cfg["KNOWLEDGE_BASE_URL"] == "http://x"
    assert cfg["KNOWLEDGE_BASE_API_KEY"] == "sk-test"
    assert cfg["DEFAULT_RETRIEVE_KB"] == "kb_a"
    assert kb_config.get_aliases() == {"a": "1"}


def test_get_aliases_from_env_var(monkeypatch, tmp_path):
    """进程环境变量 KB_ALIASES 也能被识别。"""
    # 工作区 .env 不放 KB_ALIASES，只放 URL 触发 _find_env_path
    (tmp_path / ".env").write_text("KNOWLEDGE_BASE_URL=http://x\n", encoding="utf-8")
    monkeypatch.setenv("KB_ALIASES", '{"env_alias":"kb_env"}')
    assert kb_config.get_aliases() == {"env_alias": "kb_env"}


# ---------------------------------------------------------------------------
# SOURCES / DEFAULT_SOURCE（多来源支持 — Task 1）
# ---------------------------------------------------------------------------


def _write_env(tmp_path, text):
    (tmp_path / ".env").write_text(text, encoding="utf-8")


def test_get_sources_empty_when_missing(tmp_path):
    _write_env(tmp_path, "KNOWLEDGE_BASE_URL=http://x\n")
    assert kb_config.get_sources() == []


def test_get_sources_parses_json(tmp_path):
    _write_env(
        tmp_path,
        'SOURCES=[{"name":"a","url":"http://a/api/v1","api_key":"sk-a"},'
        '{"name":"b","url":"http://b/api/v1","api_key":"sk-b"}]\n',
    )
    srcs = kb_config.get_sources()
    assert len(srcs) == 2
    assert srcs[0] == {"name": "a", "url": "http://a/api/v1", "api_key": "sk-a", "group": None}
    assert srcs[1]["name"] == "b"


def test_get_sources_invalid_json_returns_empty(capsys, tmp_path):
    _write_env(tmp_path, "SOURCES=not-json\n")
    assert kb_config.get_sources() == []
    assert "SOURCES" in capsys.readouterr().err


def test_get_sources_skips_malformed_entries(tmp_path):
    """缺 name/url/api_key 的条目被丢弃并告警。"""
    _write_env(
        tmp_path,
        'SOURCES=[{"name":"a","url":"http://a","api_key":"sk-a"},'
        '{"name":"bad"},{"url":"http://x","api_key":"sk-x"}]\n',
    )
    srcs = kb_config.get_sources()
    assert [s["name"] for s in srcs] == ["a"]


def test_default_source_from_config(tmp_path):
    _write_env(tmp_path, "DEFAULT_SOURCE=ops\n")
    assert kb_config.get_config()["DEFAULT_SOURCE"] == "ops"
