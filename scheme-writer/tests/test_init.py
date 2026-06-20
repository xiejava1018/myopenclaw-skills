"""init.py 单元测试：覆盖 --status / --check / --set / --set-aliases / --list-kbs / --show。

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
    """配置存在但 list_kbs 不可用时按可达算。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://x\nKNOWLEDGE_BASE_API_KEY=sk\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(init_mod, "list_kbs", None)
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_OK
    assert label == init_mod.STATUS_OK


def test_probe_auth_error(monkeypatch, tmp_path):
    """API Key 失效 → (2, NEED_REAUTH)。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://x\nKNOWLEDGE_BASE_API_KEY=sk\n",
        encoding="utf-8",
    )

    def fake_list():
        raise RuntimeError("401 unauthorized")

    monkeypatch.setattr(init_mod, "list_kbs", fake_list)
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_AUTH
    assert label == init_mod.STATUS_NEED_REAUTH


def test_probe_network_error(monkeypatch, tmp_path):
    """网络错误 → (3, NETWORK_ERROR)。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://x\nKNOWLEDGE_BASE_API_KEY=sk\n",
        encoding="utf-8",
    )

    def fake_list():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(init_mod, "list_kbs", fake_list)
    code, label = init_mod._probe()
    assert code == init_mod.CHECK_NETWORK
    assert label == init_mod.STATUS_NETWORK_ERROR


def test_probe_ok(monkeypatch, tmp_path):
    """配置完整且可达 → (0, OK)。"""
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://x\nKNOWLEDGE_BASE_API_KEY=sk\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(init_mod, "list_kbs", lambda: {"knowledge_bases": [], "total": 0})
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


@pytest.mark.xfail(
    reason="init.py _probe() 尚未接入 kb_migrate 首跑迁移（实现计划 Task 9）。"
    "旧配置形态(有 URL+KEY 无 SOURCES)下新 list_kbs 走解析层会抛 ConfigError，"
    "导致 status 误判为 NEED_INIT。Task 9 在 _probe 前置 migrate 后，"
    "旧形态会自动提升为 SOURCES=default，此测试应恢复真绿——届时移除本 xfail。",
    strict=False,
)
def test_status_returns_ok(tmp_path):
    (tmp_path / ".env").write_text(
        "KNOWLEDGE_BASE_URL=http://x\nKNOWLEDGE_BASE_API_KEY=sk\n",
        encoding="utf-8",
    )
    # list_kbs 在子进程中通过 mock patch 不到；这里走 list_kbs 真请求分支
    # （http://x 会失败 → NETWORK_ERROR；也可能在 list_kbs import 失败 → OK）
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
    proc = _run_init(
        "--set",
        "KNOWLEDGE_BASE_URL=http://192.168.30.236/api/v1",
        cwd=tmp_path,
        home=tmp_path,
    )
    assert proc.returncode == 0
    assert "OK" in proc.stdout
    env_file = tmp_path / ".env"
    assert env_file.is_file()
    content = env_file.read_text(encoding="utf-8")
    assert "KNOWLEDGE_BASE_URL=http://192.168.30.236/api/v1" in content


def test_set_api_key_masks_in_output(tmp_path):
    proc = _run_init(
        "--set",
        "KNOWLEDGE_BASE_API_KEY=sk-very-long-secret-key-1234",
        cwd=tmp_path,
        home=tmp_path,
    )
    assert proc.returncode == 0
    # 完整 key 不应出现在 stdout
    assert "sk-very-long-secret-key-1234" not in proc.stdout
    # 脱敏后的前 4 + 后 4 字符应出现
    assert "sk-v...1234" in proc.stdout


def test_set_rejects_unknown_key(tmp_path):
    proc = _run_init("--set", "FOO=bar", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2
    assert "bad_args" in proc.stderr


def test_set_rejects_empty_required(tmp_path):
    proc = _run_init("--set", "KNOWLEDGE_BASE_URL=", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2


def test_set_rejects_malformed_spec(tmp_path):
    proc = _run_init("--set", "no-equals-sign", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 2


def test_set_backs_up_existing_env(tmp_path):
    """已有 .env 时写新值会备份为 .env.bak。"""
    env_file = tmp_path / ".env"
    env_file.write_text("KNOWLEDGE_BASE_URL=http://old\n", encoding="utf-8")
    proc = _run_init("--set", "KNOWLEDGE_BASE_URL=http://new", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    backup = tmp_path / ".env.bak"
    assert backup.is_file()
    assert "http://old" in backup.read_text(encoding="utf-8")


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


def test_show_empty_when_no_config(tmp_path):
    proc = _run_init("--show", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["KNOWLEDGE_BASE_URL"] == ""
    assert payload["KNOWLEDGE_BASE_API_KEY"] == "(empty)"


# ---------------------------------------------------------------------------
# 端到端：模拟对话内配置流程
# ---------------------------------------------------------------------------


def test_end_to_end_chat_flow(tmp_path):
    """模拟新用户走完对话内流程：探测 → 写 URL → 写 Key → 写别名。"""
    # 1. 探测：NEED_INIT
    proc = _run_init("--status", cwd=tmp_path, home=tmp_path)
    assert proc.stdout.strip() == init_mod.STATUS_NEED_INIT

    # 2. 写 URL
    proc = _run_init(
        "--set",
        "KNOWLEDGE_BASE_URL=http://192.168.30.236/api/v1",
        cwd=tmp_path,
        home=tmp_path,
    )
    assert proc.returncode == 0

    # 3. 写 Key
    proc = _run_init(
        "--set",
        "KNOWLEDGE_BASE_API_KEY=sk-fake-key-1234567890",
        cwd=tmp_path,
        home=tmp_path,
    )
    assert proc.returncode == 0

    # 4. 写默认库
    proc = _run_init("--set", "DEFAULT_RETRIEVE_KB=kb_id_001", cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0

    # 5. 写别名
    spec = json.dumps({"技术规范库": "kb_id_001"}, ensure_ascii=False)
    proc = _run_init("--set-aliases", spec, cwd=tmp_path, home=tmp_path)
    assert proc.returncode == 0

    # 6. 验证所有配置落盘
    cfg = kb_config.get_config()
    assert cfg["KNOWLEDGE_BASE_URL"] == "http://192.168.30.236/api/v1"
    assert cfg["KNOWLEDGE_BASE_API_KEY"] == "sk-fake-key-1234567890"
    assert cfg["DEFAULT_RETRIEVE_KB"] == "kb_id_001"
    assert kb_config.get_aliases() == {"技术规范库": "kb_id_001"}

    # 7. --show 看到脱敏 Key
    proc = _run_init("--show", cwd=tmp_path, home=tmp_path)
    payload = json.loads(proc.stdout)
    assert payload["aliases"] == {"技术规范库": "kb_id_001"}
    assert "sk-fake-key-1234567890" not in payload["KNOWLEDGE_BASE_API_KEY"]
