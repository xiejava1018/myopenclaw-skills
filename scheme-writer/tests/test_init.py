"""init.py 单元测试：覆盖 --status / --check / --set / --set-aliases / --list-kbs / --show
+ 多来源子命令 --add-source / --set-sources / --remove-source / --set-default-source / --list-sources
+ 首跑迁移（main() 前置 kb_migrate.migrate()）。

通过修改 sys.path 让测试在仓库根或 CI 环境都能跑。
"""
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

import init as init_mod  # noqa: E402
import kb_config  # noqa: E402


def _run_init(*args: str, cwd: Path | None = None, home: Path | None = None) -> subprocess.CompletedProcess:
    """以子进程方式跑 init.py，拿到 stdout/stderr/returncode。

    `home` 参数会把子进程的 $HOME 指过去，避免污染真实 ~/.claude/scheme-writer/.env。
    """
    env = os.environ.copy()
    if home is not None:
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)  # Windows 兼容
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "init.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        env=env,
    )


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """每个用例清空相关环境变量并把 cwd 切到 tmp_path。

    同时把 $HOME 重定向到 tmp_path，避免子进程测试污染真实 ~/.claude/scheme-writer/.env。
    """
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
    # 进程内测试：把 cwd 切到 tmp_path，让 _find_env_path 走工作区 .env
    monkeypatch.chdir(tmp_path)
    yield


# ---------------------------------------------------------------------------
# _probe / _check / _status 内部函数
# ---------------------------------------------------------------------------


def test_probe_missing_config():
    """无 .env → (1, NEED_INIT)。"""
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_MISSING
    assert label == init_mod.STATUS_NEED_INIT


def test_probe_present_config_no_list_kbs(monkeypatch, tmp_path):
    """配置存在（SOURCES）但 list_kbs 不可用时按可达算。"""
    src = json.dumps(
        [{"name": "default", "url": "http://x", "api_key": "sk", "group": None}]
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=default\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(init_mod, "list_kbs", None)
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_OK
    assert label == init_mod.STATUS_OK


def test_probe_auth_error(monkeypatch, tmp_path):
    """API Key 失效 → (2, NEED_REAUTH)。"""
    src = json.dumps(
        [{"name": "default", "url": "http://x", "api_key": "sk", "group": None}]
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=default\n",
        encoding="utf-8",
    )

    def fake_list(source_name=None):
        raise RuntimeError("401 unauthorized")

    monkeypatch.setattr(init_mod, "list_kbs", fake_list)
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_AUTH
    assert label == init_mod.STATUS_NEED_REAUTH


def test_probe_network_error(monkeypatch, tmp_path):
    """网络错误 → (3, NETWORK_ERROR)。"""
    src = json.dumps(
        [{"name": "default", "url": "http://x", "api_key": "sk", "group": None}]
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=default\n",
        encoding="utf-8",
    )

    def fake_list(source_name=None):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(init_mod, "list_kbs", fake_list)
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_NETWORK
    assert label == init_mod.STATUS_NETWORK_ERROR


def test_probe_ok(monkeypatch, tmp_path):
    """配置完整且可达 → (0, OK)。"""
    src = json.dumps(
        [{"name": "default", "url": "http://x", "api_key": "sk", "group": None}]
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=default\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        init_mod, "list_kbs", lambda source_name=None: {"knowledge_bases": [], "total": 0}
    )
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_OK
    assert label == init_mod.STATUS_OK


# ---------------------------------------------------------------------------
# --status / --check（子进程跑）
# ---------------------------------------------------------------------------


def test_status_returns_need_init(tmp_path):
    proc = _run_init("--status", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    assert proc.stdout.strip() == init_mod.STATUS_NEED_INIT


def test_status_returns_ok(tmp_path):
    """旧配置形态（有 URL+KEY 无 SOURCES）跑 --status：
    main() 首跑迁移把旧形态提升为 SOURCES=default，_probe 用 list_kbs(default) 探测
    http://x → NETWORK_ERROR（也可能 list_kbs import 失败 → OK）。
    接受 {OK, NETWORK_ERROR}，不再 xfail。
    """
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://x\nKNOWLEDGE_BASE_API_KEY=sk\n",
        encoding="utf-8",
    )
    proc = _run_init("--status", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    assert proc.stdout.strip() in {
        init_mod.STATUS_OK,
        init_mod.STATUS_NETWORK_ERROR,
    }


def test_check_returns_exit_code_missing(tmp_path):
    proc = _run_init("--check", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == init_mod.CHECK_MISSING


# ---------------------------------------------------------------------------
# --set KEY=VAL
# ---------------------------------------------------------------------------


def test_set_url_writes_env(tmp_path):
    """旧 KNOWLEDGE_BASE_URL 不再可 --set（刻意行为变更）→ bad_args exit 2。

    旧 URL/KEY 已从 SETTABLE_KEYS 移除，仅供迁移识别；新增来源请用 --add-source。
    """
    proc = _run_init(
        "--set",
        "KNOWLEDGE_BASE_URL=http://192.168.30.236/api/v1",
        cwd=tmp_path,
        home=tmp_path,
    )
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


def test_set_api_key_rejected(tmp_path):
    """旧 KNOWLEDGE_BASE_API_KEY 也不再可 --set（刻意行为变更）→ bad_args exit 2。"""
    proc = _run_init(
        "--set",
        "KNOWLEDGE_BASE_API_KEY=sk-very-long-secret-key-1234",
        cwd=tmp_path,
        home=tmp_path,
    )
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


def test_set_rejects_unknown_key(tmp_path):
    proc = _run_init("--set", "FOO=bar", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


def test_set_default_retrieve_kb_ok(tmp_path):
    """DEFAULT_RETRIEVE_KB 仍可 --set（仍在 SETTABLE_KEYS）。"""
    proc = _run_init(
        "--set", "DEFAULT_RETRIEVE_KB=kb_id_001", cwd=tmp_path, home=tmp_path
    )
    assert proc.returncode == 0
    assert "OK" in proc.stdout
    assert kb_config.get_config().get("DEFAULT_RETRIEVE_KB") == "kb_id_001"


def test_set_rejects_malformed_spec(tmp_path):
    proc = _run_init("--set", "no-equals-sign", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2


def test_set_default_source_writes_env(tmp_path):
    """DEFAULT_SOURCE 在 SETTABLE_KEYS 中可 --set；这里不校验存在性（写入闸口，
    存在性校验由 --set-default-source 子命令负责）。"""
    proc = _run_init(
        "--set", "DEFAULT_SOURCE=foo", cwd=tmp_path, home=tmp_path
    )
    assert proc.returncode == 0
    assert "OK" in proc.stdout


def test_set_backs_up_existing_env(tmp_path):
    """已有 .env 时写新值会备份为 .env.bak（用仍在白名单的 DEFAULT_UPLOAD_KB）。"""
    env_file = tmp_path / ".env"
    env_file.write_text("DEFAULT_UPLOAD_KB=old_kb\n", encoding="utf-8")
    proc = _run_init("--set", "DEFAULT_UPLOAD_KB=new_kb", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    backup = tmp_path / ".env.bak"
    assert backup.is_file()
    assert "old_kb" in backup.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# --set-aliases JSON
# ---------------------------------------------------------------------------


def test_set_aliases_writes_json(tmp_path):
    spec = json.dumps({"技术规范库": "kb_id_001", "方案库": "kb_id_002"}, ensure_ascii=False)
    proc = _run_init("--set-aliases", spec, cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    env_file = tmp_path / ".env"
    content = env_file.read_text(encoding="utf-8")
    assert "KB_ALIASES=" in content
    # 重新读出来能解析
    assert kb_config.get_aliases() == {"技术规范库": "kb_id_001", "方案库": "kb_id_002"}


def test_set_aliases_rejects_invalid_json(tmp_path):
    proc = _run_init("--set-aliases", "not-json", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


def test_set_aliases_rejects_non_object(tmp_path):
    proc = _run_init("--set-aliases", "[]", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# --show
# ---------------------------------------------------------------------------


def test_show_masks_key(tmp_path):
    """旧 .env（URL+KEY）跑 --show：main 首跑迁移成 SOURCES=default，
    KNOWLEDGE_BASE_URL/KEY 保留显示（key masked）+ 新增 sources 数组。"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KNOWLEDGE_BASE_URL=http://x\nKNOWLEDGE_BASE_API_KEY=sk-very-long-secret-1234\n",
        encoding="utf-8",
    )
    proc = _run_init("--show", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["KNOWLEDGE_BASE_URL"] == "http://x"
    assert "sk-very-long-secret-1234" not in payload["KNOWLEDGE_BASE_API_KEY"]
    assert payload["KNOWLEDGE_BASE_API_KEY"].startswith("sk-v")
    assert payload["KNOWLEDGE_BASE_API_KEY"].endswith("1234")
    # 多来源：sources 数组 + default_source
    assert isinstance(payload.get("sources"), list)
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["name"] == "default"
    # sources 内 key 也必须脱敏
    assert "sk-very-long-secret-1234" not in payload["sources"][0]["api_key"]
    assert payload.get("default_source") == "default"


def test_show_empty_when_no_config(tmp_path):
    proc = _run_init("--show", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["KNOWLEDGE_BASE_API_KEY"] == "(empty)"
    assert payload.get("sources") == []
    assert payload.get("default_source") in (None, "")


def test_show_includes_sources(tmp_path):
    """多来源 .env 跑 --show：sources 数组含所有来源（masked key）+ default_source。"""
    src = json.dumps(
        [
            {"name": "prod", "url": "http://prod/api/v1", "api_key": "sk-prodsecret1234", "group": None},
            {"name": "test", "url": "http://test/api/v1", "api_key": "sk-testsecret1234", "group": None},
        ],
        ensure_ascii=False,
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=prod\n",
        encoding="utf-8",
    )
    proc = _run_init("--show", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert isinstance(payload["sources"], list)
    assert len(payload["sources"]) == 2
    names = [s["name"] for s in payload["sources"]]
    assert names == ["prod", "test"]
    # 明文 key 不得出现在输出
    assert "sk-prodsecret1234" not in proc.stdout
    assert "sk-testsecret1234" not in proc.stdout
    # 脱敏形态出现
    assert payload["sources"][0]["api_key"].startswith("sk-p")
    assert payload["sources"][0]["api_key"].endswith("1234")
    assert payload["default_source"] == "prod"


# ---------------------------------------------------------------------------
# --add-source NAME URL KEY
# ---------------------------------------------------------------------------


def test_add_source_appends(tmp_path):
    """首个来源自动设 DEFAULT_SOURCE。"""
    proc = _run_init(
        "--add-source", "default", "http://x/api/v1", "sk-secretkey-1234",
        cwd=tmp_path, home=tmp_path,
    )
    assert proc.returncode == 0
    assert "OK" in proc.stdout
    srcs = kb_config.get_sources()
    assert len(srcs) == 1
    assert srcs[0]["name"] == "default"
    assert srcs[0]["url"] == "http://x/api/v1"
    assert srcs[0]["api_key"] == "sk-secretkey-1234"
    # 首个来源自动设默认
    assert kb_config.resolve_default_source() == "default"
    # 明文 key 不出现在 stdout
    assert "sk-secretkey-1234" not in proc.stdout


def test_add_source_does_not_overwrite_default(tmp_path):
    """已有 DEFAULT_SOURCE 时，追加新来源不改默认。"""
    src = json.dumps(
        [{"name": "first", "url": "http://a/api/v1", "api_key": "sk-firstsecret12", "group": None}],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=first\n", encoding="utf-8"
    )
    proc = _run_init(
        "--add-source", "second", "http://b/api/v1", "sk-secondsecret12",
        cwd=tmp_path, home=tmp_path,
    )
    assert proc.returncode == 0
    assert kb_config.resolve_default_source() == "first"
    assert len(kb_config.get_sources()) == 2


def test_add_source_rejects_slash_in_name(tmp_path):
    """来源名含 '/' → bad_args（破坏 来源/库名 解析）。"""
    proc = _run_init(
        "--add-source", "evil/name", "http://x/api/v1", "sk-secretkey-1234",
        cwd=tmp_path, home=tmp_path,
    )
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


def test_add_source_duplicate_rejects(tmp_path):
    src = json.dumps(
        [{"name": "default", "url": "http://a/api/v1", "api_key": "sk-firstsecret12", "group": None}],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(f"SOURCES={src}\n", encoding="utf-8")
    proc = _run_init(
        "--add-source", "default", "http://b/api/v1", "sk-secondsecret12",
        cwd=tmp_path, home=tmp_path,
    )
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


# ---------------------------------------------------------------------------
# --set-sources JSON（整体覆写）
# ---------------------------------------------------------------------------


def test_set_sources_bulk(tmp_path):
    spec = json.dumps(
        [
            {"name": "a", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None},
            {"name": "b", "url": "http://b/api/v1", "api_key": "sk-bbbbkey-1234", "group": None},
        ],
        ensure_ascii=False,
    )
    proc = _run_init("--set-sources", spec, cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    srcs = kb_config.get_sources()
    assert [s["name"] for s in srcs] == ["a", "b"]


def test_set_sources_rejects_slash_in_name(tmp_path):
    spec = json.dumps(
        [{"name": "evil/name", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None}],
        ensure_ascii=False,
    )
    proc = _run_init("--set-sources", spec, cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr
    # 校验失败不写
    assert not (tmp_path / ".env").exists() or kb_config.get_sources() == []


def test_set_sources_rejects_invalid_json(tmp_path):
    proc = _run_init("--set-sources", "not-json", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


# ---------------------------------------------------------------------------
# --remove-source NAME
# ---------------------------------------------------------------------------


def test_remove_source(tmp_path):
    src = json.dumps(
        [
            {"name": "a", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None},
            {"name": "b", "url": "http://b/api/v1", "api_key": "sk-bbbbkey-1234", "group": None},
        ],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=a\n", encoding="utf-8"
    )
    proc = _run_init("--remove-source", "b", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    assert [s["name"] for s in kb_config.get_sources()] == ["a"]
    # 默认不动
    assert kb_config.resolve_default_source() == "a"


def test_remove_source_clears_default(tmp_path):
    """删除当前默认来源 → DEFAULT_SOURCE 清空。"""
    src = json.dumps(
        [{"name": "a", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None}],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=a\n", encoding="utf-8"
    )
    proc = _run_init("--remove-source", "a", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    assert kb_config.get_sources() == []
    # DEFAULT_SOURCE 清空（get_config 取不到值）
    assert kb_config.get_config().get("DEFAULT_SOURCE", "") == ""


def test_remove_source_unknown(tmp_path):
    """删除不存在的来源 → bad_args。"""
    src = json.dumps(
        [{"name": "a", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None}],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(f"SOURCES={src}\n", encoding="utf-8")
    proc = _run_init("--remove-source", "nope", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


# ---------------------------------------------------------------------------
# --set-default-source NAME
# ---------------------------------------------------------------------------


def test_set_default_source_ok(tmp_path):
    src = json.dumps(
        [
            {"name": "a", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None},
            {"name": "b", "url": "http://b/api/v1", "api_key": "sk-bbbbkey-1234", "group": None},
        ],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(f"SOURCES={src}\n", encoding="utf-8")
    proc = _run_init("--set-default-source", "b", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    assert kb_config.resolve_default_source() == "b"


def test_set_default_source_validates_existence(tmp_path):
    """--set-default-source 指向不存在的来源 → bad_args（T2 遗留校验）。"""
    src = json.dumps(
        [{"name": "a", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None}],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(f"SOURCES={src}\n", encoding="utf-8")
    proc = _run_init("--set-default-source", "ghost", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


# ---------------------------------------------------------------------------
# --list-sources
# ---------------------------------------------------------------------------


def test_list_sources(tmp_path):
    src = json.dumps(
        [{"name": "a", "url": "http://a/api/v1", "api_key": "sk-aaaakey-1234", "group": None}],
        ensure_ascii=False,
    )
    (tmp_path / ".env").write_text(f"SOURCES={src}\n", encoding="utf-8")
    proc = _run_init("--list-sources", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["total"] == 1
    assert isinstance(payload["sources"], list)
    entry = payload["sources"][0]
    assert entry["name"] == "a"
    assert entry["url"] == "http://a/api/v1"
    assert "reachable" in entry
    assert "kb_total" in entry
    # 明文 key 不出现
    assert "sk-aaaakey-1234" not in proc.stdout
    # 脱敏形态出现
    assert entry["api_key"].startswith("sk-a")
    assert entry["api_key"].endswith("1234")


def test_list_sources_empty(tmp_path):
    proc = _run_init("--list-sources", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["total"] == 0
    assert payload["sources"] == []


# ---------------------------------------------------------------------------
# 首跑迁移（main() 前置 kb_migrate.migrate()）
# ---------------------------------------------------------------------------


def test_auto_migration_on_status(tmp_path):
    """旧 .env（URL+KEY 无 SOURCES）跑 --status：main 自动迁移成 default 来源。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://leg/api/v1\n"
        "KNOWLEDGE_BASE_API_KEY=sk-leg-secret-1234\n",
        encoding="utf-8",
    )
    proc = _run_init("--status", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    # 迁移后 .env 应含 SOURCES + DEFAULT_SOURCE
    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SOURCES=" in content
    assert "DEFAULT_SOURCE=default" in content
    # 迁移提示打 stderr，只含变更键名，不含 key
    assert "迁移" in proc.stderr or "migrate" in proc.stderr.lower()
    assert "sk-leg-secret-1234" not in proc.stderr
    # 备份
    assert (tmp_path / ".env.bak").is_file()


def test_auto_migration_idempotent_no_stderr(tmp_path):
    """已是 SOURCES 形态时 main 迁移幂等返回 []，不喷迁移提示。"""
    src = json.dumps(
        [{"name": "default", "url": "http://x", "api_key": "sk", "group": None}]
    )
    (tmp_path / ".env").write_text(
        f"SOURCES={src}\nDEFAULT_SOURCE=default\n", encoding="utf-8"
    )
    proc = _run_init("--status", cwd=tmp_path, home=tmp_path)
    assert "迁移" not in proc.stderr


# ---------------------------------------------------------------------------
# 端到端：模拟对话内配置流程（多来源版）
# ---------------------------------------------------------------------------


def test_end_to_end_chat_flow(tmp_path):
    """模拟新用户走完对话内流程（多来源版）：
    探测 → --add-source 写来源 → 写默认库 → 写别名 → --show。
    """
    # 1. 探测：NEED_INIT
    proc = _run_init("--status", cwd=tmp_path, home=tmp_path)
    assert proc.stdout.strip() == init_mod.STATUS_NEED_INIT

    # 2. 用 --add-source 写入首个来源（自动设默认）
    proc = _run_init(
        "--add-source",
        "default", "http://192.168.30.236/api/v1", "sk-fake-key-1234567890",
        cwd=tmp_path, home=tmp_path,
    )
    assert proc.returncode == 0

    # 3. 写默认库
    proc = _run_init("--set", "DEFAULT_RETRIEVE_KB=kb_id_001", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0

    # 4. 写别名
    spec = json.dumps({"技术规范库": "kb_id_001"}, ensure_ascii=False)
    proc = _run_init("--set-aliases", spec, cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0

    # 5. 验证配置落盘
    srcs = kb_config.get_sources()
    assert len(srcs) == 1
    assert srcs[0]["api_key"] == "sk-fake-key-1234567890"
    assert kb_config.resolve_default_source() == "default"
    assert kb_config.get_config().get("DEFAULT_RETRIEVE_KB") == "kb_id_001"
    assert kb_config.get_aliases() == {"技术规范库": "kb_id_001"}

    # 6. --show 看到脱敏 Key + sources
    proc = _run_init("--show", cwd=tmp_path, home=tmp_path)
    payload = json.loads(proc.stdout)
    assert payload["aliases"] == {"技术规范库": "kb_id_001"}
    assert "sk-fake-key-1234567890" not in proc.stdout
    assert payload["sources"][0]["name"] == "default"
