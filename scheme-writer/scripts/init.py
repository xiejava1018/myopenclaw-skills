"""scheme-writer: 首次配置向导（支持对话内调用）。

按设计文档 5.4 节契约 + v1.1 对话内模式扩展。

两种模式：
- 终端模式（默认）：交互式 getpass 流程，遗留行为。
- 对话内模式（--mode=chat）：供 Claude 在对话中逐步引导：
    1. `init.py --status`         → 输出单行状态（OK / NEED_INIT / NEED_REAUTH / NETWORK_ERROR）
    2. `init.py --check`          → 退出码版状态（0/1/2/3）
    3. `init.py --set KEY=VAL`    → 写入单个配置项
    4. `init.py --list-kbs`       → 输出可见库 JSON
    5. `init.py --set-aliases JSON` → 写入别名映射
    6. `init.py --show`           → 输出当前配置（API Key 脱敏）

安全细节：
- API Key 仅在 `--set KNOWLEDGE_BASE_API_KEY=...` 时由调用方传入，脚本不回显。
- 写入前不打印任何包含 Key 的内容；`--show` 模式下 Key 仅显示前后 4 字符。
- 已有 .env 自动备份为 .env.bak。
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Any

import kb_config

try:
    from kb_list import list_kbs
except ImportError:
    list_kbs = None  # type: ignore[assignment]


# 状态常量（对话内模式与 --check 共用）
CHECK_OK = 0
CHECK_MISSING = 1
CHECK_AUTH = 2
CHECK_NETWORK = 3

# 状态标签（仅 --status / --check 的 stdout 行使用）
STATUS_OK = "OK"
STATUS_NEED_INIT = "NEED_INIT"
STATUS_NEED_REAUTH = "NEED_REAUTH"
STATUS_NETWORK_ERROR = "NETWORK_ERROR"

DEFAULT_URL = "http://192.168.30.236/api/v1"

# 允许 `--set` 写入的键白名单
SETTABLE_KEYS = {
    "KNOWLEDGE_BASE_URL",
    "KNOWLEDGE_BASE_API_KEY",
    "DEFAULT_RETRIEVE_KB",
    "DEFAULT_UPLOAD_KB",
    kb_config.KB_ALIASES_KEY,
}


def _prompt(prompt: str, default: str = "") -> str:
    """带默认值的输入。"""
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or default


def _mask_key(key: str) -> str:
    """把 API Key 脱敏为 abcd...wxyz 形式。"""
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def _probe() -> tuple[int, str]:
    """探测当前配置状态。返回 (check_exit_code, status_label)。

    - 0 / OK: 配置完整且可达
    - 1 / NEED_INIT: 配置缺失
    - 2 / NEED_REAUTH: API Key 失效
    - 3 / NETWORK_ERROR: 其它网络/服务端错误
    """
    cfg = kb_config.get_config()
    if not cfg.get("KNOWLEDGE_BASE_URL") or not cfg.get("KNOWLEDGE_BASE_API_KEY"):
        return CHECK_MISSING, STATUS_NEED_INIT
    if list_kbs is None:
        # 脚本目录不完整但配置在，按可达算
        return CHECK_OK, STATUS_OK
    try:
        list_kbs()
    except kb_config.ConfigError:
        return CHECK_MISSING, STATUS_NEED_INIT
    except Exception as exc:
        msg = str(exc)
        if "auth" in msg.lower() or "401" in msg or "403" in msg:
            return CHECK_AUTH, STATUS_NEED_REAUTH
        return CHECK_NETWORK, STATUS_NETWORK_ERROR
    return CHECK_OK, STATUS_OK


def _check_only() -> int:
    """`--check` 模式：探测并以退出码汇报，不打印其它内容。"""
    code, _ = _probe()
    return code


def _status_only() -> int:
    """`--status` 模式：探测并把状态标签打到 stdout，退出码恒为 0。"""
    _, label = _probe()
    sys.stdout.write(label + "\n")
    return 0


def _set_value(spec: str) -> int:
    """`--set KEY=VAL` 模式：写入单个配置项。stdout 报 OK，stderr 报错。"""
    if "=" not in spec:
        sys.stderr.write(
            f'{{"error":"bad_args","message":"--set 期望 KEY=VAL 形式，得到: {spec}"}}\n'
        )
        return 2
    key, _, value = spec.partition("=")
    key = key.strip()
    value = value.strip()
    if key not in SETTABLE_KEYS:
        sys.stderr.write(
            f'{{"error":"bad_args","message":"不允许的键 {key}。允许: '
            f'{sorted(SETTABLE_KEYS)}"}}\n'
        )
        return 2
    if not value and key != "DEFAULT_RETRIEVE_KB" and key != "DEFAULT_UPLOAD_KB":
        # URL / Key / 别名不允许为空
        sys.stderr.write(
            f'{{"error":"bad_args","message":"{key} 不能为空"}}\n'
        )
        return 2

    existing = kb_config.config_path()
    if existing is not None:
        backup = existing.with_name(existing.name + ".bak")
        backup.write_bytes(existing.read_bytes())

    # 合并现有配置（KB_ALIASES 作为字符串保留）
    flat = kb_config._load_merged_env()
    flat[key] = value

    # --set 模式默认写到工作区 .env（不污染用户级 ~/.claude/scheme-writer/.env）
    # 已有 .env 优先于纯默认；想写用户级请用终端交互模式（无参运行）。
    workspace = Path.cwd() / ".env"
    if existing is not None and existing == workspace:
        path = kb_config.write_env(flat, path=existing)
    else:
        path = kb_config.write_env(flat, path=workspace)
    # 回显脱敏信息
    if key == "KNOWLEDGE_BASE_API_KEY":
        sys.stdout.write(f"OK {key}={_mask_key(value)}\n")
    else:
        sys.stdout.write(f"OK {key}={value}\n")
    sys.stdout.write(f"写入 {path}\n")
    return 0


def _set_aliases(spec: str) -> int:
    """`--set-aliases JSON` 模式：写入别名映射。"""
    try:
        mapping = json.loads(spec)
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f'{{"error":"bad_args","message":"别名 JSON 解析失败: {exc}"}}\n'
        )
        return 2
    if not isinstance(mapping, dict):
        sys.stderr.write(
            '{"error":"bad_args","message":"别名必须是 JSON 对象 {名称: kb_id}"}\n'
        )
        return 2
    cleaned = {str(k).strip(): str(v).strip() for k, v in mapping.items()}
    cleaned = {k: v for k, v in cleaned.items() if k and v}
    try:
        path = kb_config.set_aliases(cleaned)
    except Exception as exc:
        sys.stderr.write(
            f'{{"error":"write_failed","message":"{exc}"}}\n'
        )
        return 1
    sys.stdout.write(f"OK aliases={json.dumps(cleaned, ensure_ascii=False, sort_keys=True)}\n")
    sys.stdout.write(f"写入 {path}\n")
    return 0


def _list_kbs() -> int:
    """`--list-kbs` 模式：复用 list_kbs()，输出 JSON 列表。"""
    if list_kbs is None:
        sys.stderr.write('{"error":"import_error","message":"kb_list 不可用"}\n')
        return 1
    try:
        data = list_kbs()
    except kb_config.ConfigError as exc:
        sys.stderr.write(
            f'{{"error":"bad_args","message":"{exc}"}}\n'
        )
        return 2
    except Exception as exc:
        msg = str(exc)
        if "auth" in msg.lower() or "401" in msg or "403" in msg:
            sys.stderr.write(
                f'{{"error":"auth","message":"{msg}"}}\n'
            )
            return 3
        sys.stderr.write(
            f'{{"error":"server","message":"{msg}"}}\n'
        )
        return 5
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    return 0


def _show() -> int:
    """`--show` 模式：输出当前配置（Key 脱敏）。"""
    cfg = kb_config.get_config()
    payload: dict[str, Any] = {
        "config_path": str(kb_config.config_path()) if kb_config.config_path() else None,
        "KNOWLEDGE_BASE_URL": cfg.get("KNOWLEDGE_BASE_URL", ""),
        "KNOWLEDGE_BASE_API_KEY": _mask_key(cfg.get("KNOWLEDGE_BASE_API_KEY", "")),
        "DEFAULT_RETRIEVE_KB": cfg.get("DEFAULT_RETRIEVE_KB", ""),
        "DEFAULT_UPLOAD_KB": cfg.get("DEFAULT_UPLOAD_KB", ""),
        "aliases": kb_config.get_aliases(),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


def _interactive() -> int:
    """终端交互式首次配置。"""
    print("=" * 60)
    print("scheme-writer 首次配置向导（终端模式）")
    print("=" * 60)

    existing = kb_config.config_path()
    if existing is not None:
        print(f"检测到已存在的配置: {existing}")
        if _prompt("是否覆盖？输入 yes 继续", "no").lower() != "yes":
            print("已取消。")
            return 0
        # 备份：直接拼接 .bak 后缀，避免 with_suffix 把 .env 变成 .env.env.bak
        backup = existing.with_name(existing.name + ".bak")
        backup.write_bytes(existing.read_bytes())
        print(f"已备份原配置到 {backup}")
    else:
        print("将创建配置文件 ~/.claude/scheme-writer/.env")

    print()
    url = _prompt("知识库 API 地址", DEFAULT_URL)
    key = getpass.getpass("API Key（不回显，建议先在服务端粘贴后再轮换一次）: ").strip()
    if not key:
        print("API Key 不能为空，已取消。")
        return 1

    retrieve_kb = _prompt("默认检索知识库 ID（可空，回车跳过）", "")
    upload_kb = _prompt("默认上传知识库 ID（可空，回车跳过）", "")

    values = {
        "KNOWLEDGE_BASE_URL": url,
        "KNOWLEDGE_BASE_API_KEY": key,
        "DEFAULT_RETRIEVE_KB": retrieve_kb,
        "DEFAULT_UPLOAD_KB": upload_kb,
    }
    path = kb_config.write_env(values)
    print(f"\n✓ 已写入 {path}")

    # 验证连通性
    if list_kbs is None:
        print("⚠ kb_list.py 不可用，跳过连通性验证。")
    else:
        try:
            data = list_kbs()
            kbs = data.get("knowledge_bases", [])
            print(f"✓ 连通性验证成功，列出 {len(kbs)} 个可见知识库：")
            for kb in kbs[:10]:
                print(f"  - {kb['kb_id']}: {kb['name']} (doc_count={kb['doc_count']})")
        except Exception as exc:
            print(f"⚠ 连通性验证失败: {exc}")
            print("  配置已写入，请检查 URL 与 API Key 后重试。")
            return 1

    print()
    print("下一步：可在 SKILL.md 顶部的'知识库别名映射'表中补充自然语言别名。")
    print("完成。请在 Claude Code 中说'已配置完成'继续使用。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="scheme-writer: 首次配置向导（终端模式 / 对话内模式）"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查配置状态，以退出码汇报（0=OK 1=缺失 2=认证 3=网络）",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="输出单行状态标签（OK / NEED_INIT / NEED_REAUTH / NETWORK_ERROR），退出码恒为 0",
    )
    parser.add_argument(
        "--set",
        dest="set_spec",
        metavar="KEY=VAL",
        help="写入单个配置项（用于对话内模式）",
    )
    parser.add_argument(
        "--set-aliases",
        dest="aliases_spec",
        metavar="JSON",
        help="写入知识库别名映射，参数为 JSON 字符串，例如 '{\"技术规范库\":\"kb_id_001\"}'",
    )
    parser.add_argument(
        "--list-kbs",
        action="store_true",
        help="列出可见知识库（复用 kb_list.py）",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="输出当前配置（Key 脱敏）",
    )
    args = parser.parse_args()

    if args.check:
        return _check_only()
    if args.status:
        return _status_only()
    if args.set_spec is not None:
        return _set_value(args.set_spec)
    if args.aliases_spec is not None:
        return _set_aliases(args.aliases_spec)
    if args.list_kbs:
        return _list_kbs()
    if args.show:
        return _show()
    return _interactive()


if __name__ == "__main__":
    sys.exit(main())
