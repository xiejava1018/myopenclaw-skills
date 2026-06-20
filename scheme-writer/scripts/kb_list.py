"""scheme-writer: 列出可见知识库（支持多来源）。

按设计文档 5.3 节契约；Phase 1 多来源：接入 kb_resolve 解析层，
新增 --source/--all 两个互斥参数。
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

import kb_config
import kb_resolve
from kb_config import ConfigError
from kb_http import KbError, emit_error, emit_ok, request_json


def _fetch_one(source: dict[str, Any]) -> list[dict[str, Any]]:
    """调单个来源的 /knowledge-bases，返回归一化后的 kb 列表（带 source 标签）。

    保持现有字段归一化逻辑（knowledge_bases/items/data 三选一、id 别名、
    doc_count 兼容 document_count/knowledge_count）。
    """
    base = source["url"].rstrip("/")
    url = f"{base}/knowledge-bases"
    data = request_json("GET", url, api_key=source["api_key"], timeout=15)

    raw = data.get("knowledge_bases") or data.get("items") or data.get("data") or []
    kbs: list[dict[str, Any]] = []
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
                "source": source["name"],
            }
        )
    return kbs


def list_kbs(source_name: str | None = None) -> dict[str, Any]:
    """列出指定来源（或默认来源）的可见知识库。

    source_name 为 None 时用 kb_resolve.resolve_source(None) 决定
    （DEFAULT_SOURCE > 单源隐式 > 报错），保持 list_kbs() 无参向后兼容。
    """
    name = source_name or kb_resolve.resolve_source(None)
    source = kb_config.get_source(name)
    kbs = _fetch_one(source)
    return {"knowledge_bases": kbs, "total": len(kbs)}


def list_kbs_all() -> dict[str, Any]:
    """列出全部来源的知识库；单源失败不致命，收集到 errors。"""
    all_kbs: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source in kb_config.get_sources():
        try:
            all_kbs.extend(_fetch_one(source))
        except KbError as exc:
            errors.append(
                {"source": source["name"], "error": exc.code, "message": exc.message}
            )
    return {"knowledge_bases": all_kbs, "total": len(all_kbs), "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="scheme-writer: 列出可见知识库（多来源）"
    )
    parser.add_argument(
        "--source", default=None, help="指定来源名；省略则用默认来源"
    )
    parser.add_argument(
        "--all", action="store_true", help="列出全部来源的知识库"
    )
    args = parser.parse_args()
    try:
        if args.all:
            result = list_kbs_all()
        else:
            result = list_kbs(args.source)
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
