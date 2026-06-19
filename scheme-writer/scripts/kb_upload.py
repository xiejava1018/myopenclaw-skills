"""scheme-writer: 文档上传归档。

按设计文档 5.2 节契约。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from kb_config import ConfigError, require
from kb_http import (
    EXIT_FILE_READ,
    KbError,
    emit_error,
    emit_ok,
    request_json,
)


def upload(
    kb_id: str,
    file_path: str,
    title: str,
    *,
    tags: list[str] | None = None,
    mode: str = "reuse_vectors",
    timeout: int = 60,
) -> dict[str, Any]:
    """上传文档到指定知识库，返回 dict 结果。"""
    base = require("KNOWLEDGE_BASE_URL").rstrip("/")
    api_key = require("KNOWLEDGE_BASE_API_KEY")

    path = Path(file_path)
    if not path.is_file():
        raise KbError(
            "file_read",
            f"文件不存在或不可读: {file_path}",
            path=file_path,
        )

    content = path.read_text(encoding="utf-8")
    url = f"{base}/knowledge-bases/{kb_id}/knowledge/manual"
    body: dict[str, Any] = {
        "title": title,
        "content": content,
        "status": "publish",
    }
    if tags:
        # manual 端点仅接受单个 tag_id；多标签场景下退化为逗号串追加到标题前缀
        body["title"] = f"[{'/'.join(tags)}] {title}"
    else:
        body["title"] = title

    data = request_json(
        "POST",
        url,
        api_key=api_key,
        json_body=body,
        timeout=timeout,
    )
    return {
        "ok": True,
        "doc_id": (
            (data.get("data") or {}).get("id")
            or data.get("doc_id")
            or data.get("id", "")
        ),
        "kb_id": kb_id,
        "title": title,
        "size_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="scheme-writer: 上传文档到知识库归档")
    parser.add_argument("--kb", required=True, help="目标知识库 ID")
    parser.add_argument("--file", required=True, help="待上传的本地文件路径（.md / .txt）")
    parser.add_argument("--title", required=True, help="方案名（作为知识库中的文档标题）")
    parser.add_argument("--tags", default="", help="逗号分隔的标签，如 '方案,K8s,离线'")
    parser.add_argument("--mode", default="reuse_vectors", help="上传模式，默认 reuse_vectors")
    parser.add_argument("--timeout", type=int, default=60, help="请求超时（秒）")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    try:
        result = upload(
            args.kb,
            args.file,
            args.title,
            tags=tags,
            mode=args.mode,
            timeout=args.timeout,
        )
    except ConfigError as exc:
        emit_error(KbError("bad_args", str(exc)))
        return 2
    except KbError as exc:
        if exc.code == "file_read":
            sys.stderr.write(exc.to_json() + "\n")
            return EXIT_FILE_READ
        emit_error(exc)
        return 0  # unreachable
    else:
        # 异步提示：manual 端点只返回 doc_id，解析与向量化是异步进行的。
        # Claude 拿到 doc_id 后立刻调 kb_search 大概率搜不到，应提示用 kb_docs.py 看 parse_status。
        sys.stderr.write(
            f"[kb_upload] 提示：文档解析与向量化是异步进行的，立即检索可能为空。"
            f"可用 `python scripts/kb_docs.py --kb {args.kb}` 轮询 parse_status 直至 completed。\n"
        )
        emit_ok(result)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KbError as exc:
        emit_error(exc)
    except ConfigError as exc:
        emit_error(KbError("bad_args", str(exc)))
    except KeyboardInterrupt:
        sys.exit(130)
