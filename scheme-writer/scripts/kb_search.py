"""scheme-writer: 语义检索。

按设计文档 5.1 节契约。
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from kb_config import ConfigError, require
from kb_http import KbError, emit_error, emit_ok, request_json


def search(
    kb_id: str,
    query: str,
    *,
    top_k: int = 8,
    min_score: float = 0.5,
    timeout: int = 30,
) -> dict[str, Any]:
    """调 WeKnora 检索接口，返回 dict 结果（与 CLI 输出一致）。"""
    base = require("KNOWLEDGE_BASE_URL").rstrip("/")
    api_key = require("KNOWLEDGE_BASE_API_KEY")

    url = f"{base}/knowledge-search"
    body = {
        "query": query,
        "knowledge_base_id": kb_id,
        "top_k": top_k,
        "min_score": min_score,
    }
    data = request_json(
        "POST",
        url,
        api_key=api_key,
        json_body=body,
        timeout=timeout,
    )

    # 兼容不同 WeKnora 版本的响应结构
    raw_chunks = (
        data.get("chunks")
        or data.get("results")
        or data.get("data")
        or []
    )
    chunks = []
    for c in raw_chunks:
        chunks.append(
            {
                "chunk_id": c.get("chunk_id") or c.get("id", ""),
                "source_doc": (
                    c.get("source_doc")
                    or c.get("knowledge_title")
                    or c.get("document_title", "")
                ),
                "source_doc_id": (
                    c.get("source_doc_id")
                    or c.get("knowledge_id")
                    or c.get("document_id", "")
                ),
                "source_file": c.get("knowledge_filename", ""),
                "chunk_index": c.get("chunk_index", 0),
                "content": c.get("content") or c.get("text", ""),
                "score": float(c.get("score", 0.0)),
                "metadata": c.get("metadata") or {},
            }
        )
    # 客户端兜底过滤（即便服务端忽略了 min_score）
    chunks = [c for c in chunks if c["score"] >= min_score]

    return {
        "kb_id": kb_id,
        "query": query,
        "chunks": chunks,
        "total": len(chunks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="scheme-writer: 知识库语义检索")
    parser.add_argument("--kb", required=True, help="知识库 ID（可多个，逗号分隔）")
    parser.add_argument("--query", required=True, help="检索问题文本")
    parser.add_argument("--top-k", type=int, default=8, help="返回 top-k，默认 8")
    parser.add_argument("--min-score", type=float, default=0.5, help="相似度阈值，默认 0.5")
    parser.add_argument("--timeout", type=int, default=30, help="请求超时（秒）")
    args = parser.parse_args()

    kb_ids = [k.strip() for k in args.kb.split(",") if k.strip()]
    if not kb_ids:
        sys.stderr.write('{"error":"bad_args","message":"--kb 不能为空"}\n')
        return 2

    results: list[dict[str, Any]] = []
    for kb_id in kb_ids:
        try:
            results.append(
                search(
                    kb_id,
                    args.query,
                    top_k=args.top_k,
                    min_score=args.min_score,
                    timeout=args.timeout,
                )
            )
        except ConfigError as exc:
            emit_error(KbError("bad_args", str(exc)))
            return 2
        except KbError:
            raise

    # 多库时合并到一个数组
    if len(results) == 1:
        emit_ok(results[0])
    else:
        merged = {
            "kb_ids": kb_ids,
            "query": args.query,
            "results": results,
            "total": sum(r["total"] for r in results),
        }
        emit_ok(merged)
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
