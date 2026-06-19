"""scheme-writer: 列出可见知识库。

按设计文档 5.3 节契约。
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from kb_config import ConfigError, require
from kb_http import KbError, emit_error, emit_ok, request_json


def list_kbs() -> dict[str, Any]:
    """调 WeKnora 列出当前用户可见的知识库。"""
    base = require("KNOWLEDGE_BASE_URL").rstrip("/")
    api_key = require("KNOWLEDGE_BASE_API_KEY")

    url = f"{base}/knowledge-bases"
    data = request_json("GET", url, api_key=api_key, timeout=15)

    raw = (
        data.get("knowledge_bases")
        or data.get("items")
        or data.get("data")
        or []
    )
    kbs = []
    for kb in raw:
        kbs.append(
            {
                "kb_id": kb.get("kb_id") or kb.get("id", ""),
                "name": kb.get("name", ""),
                # doc_count 取服务端 knowledge_count 字段，反映元数据文档数。
                # chunk_count 反映已索引 chunk 数；诊断"为什么 doc_count>0 但检索为空"的关键字段。
                "doc_count": int(
                    kb.get("doc_count")
                    or kb.get("document_count")
                    or kb.get("knowledge_count", 0)
                ),
                "chunk_count": int(kb.get("chunk_count") or 0),
                "description": kb.get("description", ""),
            }
        )
    return {"knowledge_bases": kbs, "total": len(kbs)}


def main() -> int:
    parser = argparse.ArgumentParser(description="scheme-writer: 列出可见知识库")
    args = parser.parse_args()
    try:
        result = list_kbs()
    except ConfigError as exc:
        emit_error(KbError("bad_args", str(exc)))
        return 2
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
