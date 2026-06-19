"""scheme-writer 共享 HTTP 客户端与错误处理。

设计要点：
- 统一错误信封：stderr JSON + 语义化退出码
- 请求超时显式传入，避免长尾阻塞 LLM
- API Key 仅在请求头注入，不进入任何日志
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    import requests
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        '{"error":"import_error","message":"缺少依赖 requests，请先运行: '
        'pip install -r scripts/requirements.txt"}\n'
    )
    raise SystemExit(1) from exc

# 退出码常量（与设计文档 5.6 节保持一致）
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_BAD_ARGS = 2
EXIT_AUTH = 3
EXIT_KB_NOT_FOUND = 4
EXIT_SERVER = 5
EXIT_TIMEOUT = 6
EXIT_FILE_READ = 7

# 错误类型 → 退出码
_ERROR_EXIT = {
    "bad_args": EXIT_BAD_ARGS,
    "auth": EXIT_AUTH,
    "kb_not_found": EXIT_KB_NOT_FOUND,
    "timeout": EXIT_TIMEOUT,
    "file_read": EXIT_FILE_READ,
    "server": EXIT_SERVER,
    "not_found": EXIT_KB_NOT_FOUND,
}


class KbError(Exception):
    """统一的知识库调用错误。包含 error code 与 message。"""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra

    def to_json(self) -> str:
        payload = {"error": self.code, "message": self.message, **self.extra}
        return json.dumps(payload, ensure_ascii=False)


def emit_error(err: KbError) -> None:
    """把错误以 JSON 写到 stderr 并以语义化退出码退出。"""
    sys.stderr.write(err.to_json() + "\n")
    sys.exit(_ERROR_EXIT.get(err.code, EXIT_GENERIC))


def emit_ok(payload: dict[str, Any]) -> None:
    """把成功结果以 JSON 写到 stdout。"""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def request_json(
    method: str,
    url: str,
    *,
    api_key: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """统一的 requests 封装。

    - 把超时、网络错误、HTTP 状态码全部归一化为 KbError
    - 成功时返回解析后的 JSON dict
    """
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            params=params,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise KbError("timeout", f"请求超时（{timeout}s）: {url}", url=url) from exc
    except requests.RequestException as exc:
        raise KbError("server", f"网络错误: {exc}", url=url) from exc

    if resp.status_code == 401 or resp.status_code == 403:
        raise KbError(
            "auth",
            "认证失败：API Key 无效或无权限",
            status=resp.status_code,
        )
    if resp.status_code == 404:
        raise KbError(
            "kb_not_found",
            f"资源不存在: {url}",
            status=resp.status_code,
        )
    if resp.status_code >= 500:
        raise KbError(
            "server",
            f"服务端错误: HTTP {resp.status_code}",
            status=resp.status_code,
            body=resp.text[:500],
        )
    if resp.status_code >= 400:
        # 其它 4xx 视为参数问题
        raise KbError(
            "bad_args",
            f"请求被拒绝: HTTP {resp.status_code} {resp.text[:300]}",
            status=resp.status_code,
        )

    try:
        return resp.json()
    except ValueError as exc:
        raise KbError(
            "server",
            f"响应不是有效 JSON: {resp.text[:300]}",
            status=resp.status_code,
        ) from exc
