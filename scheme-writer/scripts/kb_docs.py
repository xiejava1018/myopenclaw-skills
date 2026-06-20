"""scheme-writer: 列出某知识库下的所有文档。

按设计文档 5.4 节契约（新增能力）。

为什么需要这个脚本：
- kb_list.py 输出的 doc_count 是服务端 knowledge_count 字段，**只是文档元数据计数**，
  反映不出"哪些已向量化、哪些还在 processing"。
- kb_search.py 用语义检索，对索引未完成的文档根本搜不到。
- 当用户问"这个库到底有什么"时，Claude 之前只能用 search 反复试探，被 min_score
  过滤后看不到未索引的文档。
- 本脚本直接调 GET /knowledge-bases/{kb_id}/knowledge 拿到所有文档的真实元数据
  （含 parse_status / file_size / updated_at），是诊断"为什么 doc_count>0 但检索为空"
  的关键工具。
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

import kb_config
import kb_resolve
from kb_config import ConfigError
from kb_http import KbError, emit_error, emit_ok, request_json


def _normalize_doc(raw: dict[str, Any]) -> dict[str, Any]:
    """把服务端返回的单条文档归一化为统一字段。

    兼容多种字段名：
    - id  ← id / doc_id / document_id
    - title ← title / name / filename
    - file_size ← file_size / size / size_bytes
    - 其他字段（parse_status / enable_status / processed_at / error_message 等）原样透出
    """
    return {
        "doc_id": raw.get("id") or raw.get("doc_id") or raw.get("document_id", ""),
        "title": raw.get("title") or raw.get("name") or raw.get("filename", ""),
        "file_name": raw.get("file_name") or raw.get("filename", ""),
        "file_type": raw.get("file_type", ""),
        "file_size": int(raw.get("file_size") or raw.get("size") or raw.get("size_bytes") or 0),
        "parse_status": raw.get("parse_status", ""),
        "enable_status": raw.get("enable_status", ""),
        "summary_status": raw.get("summary_status", ""),
        "created_at": raw.get("created_at", ""),
        "updated_at": raw.get("updated_at", ""),
        "processed_at": raw.get("processed_at", ""),
        "error_message": raw.get("error_message", ""),
    }


def list_docs(
    source_name: str,
    kb_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
    fetch_all: bool = False,
    timeout: int = 30,
) -> dict[str, Any]:
    """调 WeKnora 列出某 KB 下所有文档。

    参数：
        source_name: 来源名（由 kb_resolve 解析得到）
        kb_id: 知识库 ID
        page: 起始页码（从 1 开始）
        page_size: 每页文档数
        fetch_all: True 时自动翻页直到 total 用尽；False 时只取当前页
        timeout: HTTP 超时秒数

    返回 dict 含 source / kb_id / total / page / page_size / documents 列表。
    """
    src = kb_config.get_source(source_name)
    base = src["url"].rstrip("/")
    api_key = src["api_key"]

    url = f"{base}/knowledge-bases/{kb_id}/knowledge"
    all_docs: list[dict[str, Any]] = []
    total = 0
    current_page = page

    while True:
        data = request_json(
            "GET",
            url,
            api_key=api_key,
            params={"page": current_page, "page_size": page_size},
            timeout=timeout,
        )
        # 兼容三种响应结构：data.items / data.data / data
        payload = data.get("data") or {}
        if isinstance(payload, dict):
            items = payload.get("items") or payload.get("data") or []
            total = int(payload.get("total", len(items)))
        elif isinstance(payload, list):
            items = payload
            total = int(data.get("total", len(items)))
        else:
            items = []
            total = 0

        all_docs.extend(_normalize_doc(it) for it in items if isinstance(it, dict))

        # 非 --all 模式只取一页
        if not fetch_all:
            break
        # 已取完：current_page * page_size >= total
        if current_page * page_size >= total:
            break
        current_page += 1

    return {
        "source": source_name,
        "kb_id": kb_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "documents": all_docs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="scheme-writer: 列出某知识库下所有文档（含 parse_status）"
    )
    parser.add_argument("--kb", required=True, help="知识库引用：限定别名 / 裸名 / 字面 kb_id")
    parser.add_argument(
        "--source",
        default=None,
        help="指定来源名（--kb 为限定别名/带前缀时可省略）",
    )
    parser.add_argument("--page", type=int, default=1, help="起始页码，默认 1")
    parser.add_argument(
        "--page-size", type=int, default=20, help="每页文档数，默认 20"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="自动翻页直到取完所有文档（默认只取一页）",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="请求超时（秒），默认 30"
    )
    args = parser.parse_args()

    try:
        source_name, kb_id = kb_resolve.resolve_kb_ref(args.kb, args.source)
        result = list_docs(
            source_name,
            kb_id,
            page=args.page,
            page_size=args.page_size,
            fetch_all=args.all,
            timeout=args.timeout,
        )
    except ConfigError as exc:
        emit_error(KbError("bad_args", str(exc)))
        return 2
    except KbError:
        raise

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
