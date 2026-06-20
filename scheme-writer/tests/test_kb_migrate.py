"""kb_migrate.py 单元测试：旧单实例配置 → 多来源自动迁移。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kb_config  # noqa: E402
import kb_migrate  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
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


def test_needs_migration_when_legacy_only(tmp_path):
    """有旧 URL+KEY、无 SOURCES → 需迁移。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n",
        encoding="utf-8",
    )
    assert kb_migrate.needs_migration() is True


def test_no_migration_when_sources_present(tmp_path):
    (tmp_path / ".env").write_text(
        'SOURCES=[{"name":"default","url":"http://x","api_key":"sk"}]\n',
        encoding="utf-8",
    )
    assert kb_migrate.needs_migration() is False


def test_no_migration_when_clean(tmp_path):
    """无旧 key 也无 SOURCES（全新状态）→ 不迁移（避免对空配置误操作）。"""
    (tmp_path / ".env").write_text("DEFAULT_SOURCE=a\n", encoding="utf-8")
    assert kb_migrate.needs_migration() is False


def test_migrate_synthesizes_default_source(tmp_path):
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n",
        encoding="utf-8",
    )
    changed = kb_migrate.migrate()
    assert "SOURCES" in changed
    assert "DEFAULT_SOURCE" in changed
    srcs = kb_config.get_sources()
    assert len(srcs) == 1
    assert srcs[0] == {
        "name": "default",
        "url": "http://leg/api/v1",
        "api_key": "sk-leg",
        "group": None,
    }
    assert kb_config.get_config()["DEFAULT_SOURCE"] == "default"


def test_migrate_prefixes_legacy_aliases(tmp_path):
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n"
        'KB_ALIASES={"技术规范库":"kb-1","方案库":"kb-2"}\n',
        encoding="utf-8",
    )
    kb_migrate.migrate()
    assert kb_config.get_aliases() == {
        "default/技术规范库": "kb-1",
        "default/方案库": "kb-2",
    }


def test_migrate_keeps_already_qualified_aliases(tmp_path):
    """别名键已含 / 则不加前缀。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n"
        'KB_ALIASES={"other/库":"kb-9"}\n',
        encoding="utf-8",
    )
    kb_migrate.migrate()
    assert kb_config.get_aliases() == {"other/库": "kb-9"}


def test_migrate_creates_backup(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n",
        encoding="utf-8",
    )
    kb_migrate.migrate()
    assert (tmp_path / ".env.bak").is_file()
    # 备份内容是迁移前的原始内容
    assert "KNOWLEDGE_BASE_URL=http://leg/api/v1" in (tmp_path / ".env.bak").read_text(encoding="utf-8")


def test_migrate_idempotent(tmp_path):
    """跑两次不重复迁移、不重复加前缀。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n"
        'KB_ALIASES={"技术规范库":"kb-1"}\n',
        encoding="utf-8",
    )
    kb_migrate.migrate()
    second = kb_migrate.migrate()
    assert second == []  # 第二次无事可做
    assert kb_config.get_aliases() == {"default/技术规范库": "kb-1"}
    assert len(kb_config.get_sources()) == 1


def test_migrate_invalid_aliases_skipped(tmp_path, capsys):
    """旧 KB_ALIASES 非法 JSON 时，迁移仍完成（来源合成），别名降级为空且不残留。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg\n"
        "KB_ALIASES=not-json\n",
        encoding="utf-8",
    )
    changed = kb_migrate.migrate()
    assert "SOURCES" in changed  # 来源迁移仍完成
    assert kb_config.get_aliases() == {}  # 非法别名降级为空
    # 迁移产物不再残留非法 KB_ALIASES
    written = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "not-json" not in written
    assert "KB_ALIASES" not in written
    # 再次读取不再喷 stderr 告警
    capsys.readouterr()  # 清掉迁移期间的输出
    assert kb_config.get_aliases() == {}
    assert "不是合法 JSON" not in capsys.readouterr().err
