"""scheme-writer: 语义检索（支持多来源合并 + 部分失败）。

按设计文档 §5 契约：
- search_source：对单个 (source, kb_id) 检索，返回归一化 chunks（不打 source 标签）
- run()：测试入口，解析 argv → 返回 payload dict（全失败时抛 KbError）
- main()：emit JSON + 语义化退出码；run 与 main 共用 _execute
- 单目标 → 老结构（无 sources/errors）；多目标 → 新结构（sources + errors）
- 部分失败不致命：健康源照常返回，失败源进 errors 收集
- 合并排序按 (source, -score)，不跨源全局重排
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

import kb_config
import kb_resolve
from kb_config import ConfigError
from kb_http import KbError, emit_error, emit_ok, request_json


def search_source(
    source: dict[str, Any],
    kb_id: str,
    query: str,
    *,
    top_k: int = 8,
    min_score: float = 0.5,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """对单个 (source, kb_id) 检索，返回归一化后的 chunks（未打 source 标签）。

    标签（source / kb_id）由调用方在合并层打上，本函数只负责检索与归一化。
    """
    url = f"{source['url'].rstrip('/')}/knowledge-search"
    body = {
        "query": query,
        "knowledge_base_id": kb_id,
        "top_k": top_k,
        "min_score": min_score,
    }
    data = request_json(
        "POST",
        url,
        api_key=source["api_key"],
        json_body=body,
        timeout=timeout,
    )

    # 兼容不同 WeKnora 版本的响应结构
    raw_chunks = data.get("chunks") or data.get("results") or data.get("data") or []
    chunks: list[dict[str, Any]] = []
    for c in raw_chunks:
        score = float(c.get("score", 0.0))
        if score < min_score:  # 客户端兜底过滤（即便服务端忽略 min_score）
            continue
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
                "score": score,
                "metadata": c.get("metadata") or {},
            }
        )
    return chunks


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="scheme-writer: 知识库语义检索（多来源）")
    parser.add_argument(
        "--kb",
        required=True,
        help="知识库引用（多目标逗号分隔，支持 来源/库名 限定别名）",
    )
    parser.add_argument("--query", required=True, help="检索问题文本")
    parser.add_argument(
        "--source",
        default=None,
        help="指定来源名（--kb 为限定形态时可省略）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="每个来源返回 top-k，默认 8",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.5,
        help="相似度阈值，默认 0.5",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="请求超时（秒）",
    )
    return parser.parse_args(argv)


def _exit_code_for(code: str) -> int:
    """错误 code → 退出码，复用 kb_http 的语义化映射。"""
    from kb_http import _ERROR_EXIT

    return _ERROR_EXIT.get(code, 1)


def _execute(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """公共逻辑：返回 (payload, exit_code)。run() 与 main() 共用。

    - ≥1 目标成功 → exit_code=0，payload 为成功信封
    - 全失败 → exit_code=对应错误码，payload 为错误信封（含聚合 errors）
    """
    targets = kb_resolve.resolve_kb_refs(args.kb, args.source)

    all_chunks: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    ok_sources: set[str] = set()
    involved: set[str] = set()

    for src_name, kb_id in targets:
        involved.add(src_name)
        try:
            source = kb_config.get_source(src_name)
            chunks = search_source(
                source,
                kb_id,
                args.query,
                top_k=args.top_k,
                min_score=args.min_score,
                timeout=args.timeout,
            )
            for c in chunks:
                c["source"] = src_name
                c["kb_id"] = kb_id
            all_chunks.extend(chunks)
            ok_sources.add(src_name)
        except KbError as exc:
            # 单源失败不致命：记录到 errors，继续下一个目标
            errors.append(
                {"source": src_name, "error": exc.code, "message": exc.message}
            )

    # 按 (source, -score) 排序——同源内 score 降序，不跨源全局重排
    all_chunks.sort(key=lambda c: (c["source"], -c["score"]))

    if not ok_sources and errors:
        # 全失败：返回错误信封，exit_code 取第一个失败的语义码
        first = errors[0]
        return (
            {
                "error": first["error"],
                "message": first["message"],
                "errors": errors,
            },
            _exit_code_for(first["error"]),
        )

    if len(targets) == 1:
        # 单目标 → 老结构（向后兼容，无 sources/errors 字段）
        payload: dict[str, Any] = {
            "kb_id": targets[0][1],
            "query": args.query,
            "chunks": all_chunks,
            "total": len(all_chunks),
        }
    else:
        # 多目标 → 新结构（含 sources 与 errors 聚合）
        payload = {
            "sources": sorted(involved),
            "query": args.query,
            "chunks": all_chunks,
            "total": len(all_chunks),
            "errors": errors,
        }
    return (payload, 0)


def run(argv: list[str] | None) -> dict[str, Any]:
    """测试入口：解析 argv → 返回 payload dict（成功/部分失败）。

    全失败时抛 KbError（由测试用 pytest.raises 捕获）。
    不 emit、不调用 sys.exit。
    """
    args = _parse(argv)
    payload, exit_code = _execute(args)
    if exit_code != 0:
        # 全失败：抛出，便于测试断言
        raise KbError(payload["error"], payload["message"])
    return payload


def main() -> int:
    try:
        args = _parse(None)
        payload, exit_code = _execute(args)
    except ConfigError as exc:
        emit_error(KbError("bad_args", str(exc)))
        return 2
    if exit_code != 0:
        emit_error(KbError(payload["error"], payload["message"]))
        return exit_code
    emit_ok(payload)
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
