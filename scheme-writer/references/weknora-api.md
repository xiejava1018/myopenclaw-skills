# WeKnora API 速查

> scheme-writer 调用的 WeKnora 端点。本文档**按真实服务端 API 整理**，与历史速查表（2025 年初版）相比已全面修正。
>
> 完整文档见 [WeKnora docs](https://github.com/Tencent/WeKnora/blob/main/docs/api/README.md)。本文仅描述 scheme-writer 用到的端点。

## 端点

| 端点 | 方法 | 用途 | scheme-writer 入口 |
|:-----|:-----|:-----|:-------------------|
| `/knowledge-bases` | GET | 列出可见知识库 | `kb_list.py` |
| `/knowledge-search` | POST | 语义检索（跨库） | `kb_search.py` |
| `/knowledge-bases/{kb_id}/knowledge/manual` | POST | 上传 Markdown/纯文本文档 | `kb_upload.py` |
| `/knowledge-bases/{kb_id}/knowledge?page=&page_size=` | GET | 列出某库下所有文档（含 parse_status） | `kb_docs.py` |

> ⚠️ **历史版本勘误**（早期速查表写错的部分）：
> - 检索端点是 `POST /knowledge-search`（**不是** `/knowledge-bases/{kb_id}/search`）
> - 上传端点是 `POST /knowledge-bases/{kb_id}/knowledge/manual`（**不是** `/knowledge-bases/{kb_id}/documents`）
> - 认证头是 `X-API-Key`（**不是** `Authorization: Bearer`）

## 认证

所有请求带 `X-API-Key: <API_KEY>` 头（`kb_http.py:86` 已统一处理）。

```text
X-API-Key: sk-xxxxxxxxxxxxx
Content-Type: application/json
```

## 1. 列出知识库

**端点**：`GET /knowledge-bases`

**响应**（真实服务端结构，`{data: [...]}`）：

```json
{
  "data": [
    {
      "id": "kb-uuid-001",
      "name": "安全运营管理知识库",
      "description": "（服务端 description 可能为空字符串）",
      "knowledge_count": 12,
      "chunk_count": 0,
      "type": "document",
      "is_pinned": false,
      "is_processing": false,
      "vector_store_status": "available",
      "created_at": "2026-01-15T08:00:00Z",
      "updated_at": "2026-06-17T03:00:00Z"
    }
  ],
  "success": true
}
```

**`kb_list.py` 归一化输出**（兼容服务端可能使用 `knowledge_bases` / `items` / `doc_count` 等不同字段名）：

```json
{
  "knowledge_bases": [
    {
      "kb_id": "kb-uuid-001",
      "name": "安全运营管理知识库",
      "doc_count": 12,
      "chunk_count": 0,
      "description": ""
    }
  ],
  "total": 1
}
```

**关键诊断字段**：
- `doc_count`（来自服务端 `knowledge_count`）：**元数据文档数**
- `chunk_count`：**已索引 chunk 数**
- 当 `chunk_count < doc_count` 时，**检索结果会很稀疏**——这是因为文档还在解析或向量化中

## 2. 语义检索

**端点**：`POST /knowledge-search`

**请求体**：

```json
{
  "query": "漏洞管理修复流程",
  "knowledge_base_id": "kb-uuid-001",
  "top_k": 8,
  "min_score": 0.5
}
```

**响应**（服务端实际返回 `{chunks: [...]}`，kb_search.py 兼容 `{results}` / `{data}`）：

```json
{
  "chunks": [
    {
      "chunk_id": "chunk-uuid-001",
      "source_doc": "中国电信云运〔2024〕29号.pdf",
      "source_doc_id": "doc-uuid-001",
      "knowledge_filename": "中国电信云运〔2024〕29号.pdf",
      "chunk_index": 119,
      "content": "（chunk 文本内容）",
      "score": 0.72,
      "metadata": {}
    }
  ],
  "total": 1
}
```

**`kb_search.py` 归一化输出**：

```json
{
  "kb_id": "kb-uuid-001",
  "query": "漏洞管理修复流程",
  "chunks": [
    {
      "chunk_id": "chunk-uuid-001",
      "source_doc": "中国电信云运〔2024〕29号.pdf",
      "source_doc_id": "doc-uuid-001",
      "source_file": "中国电信云运〔2024〕29号.pdf",
      "chunk_index": 119,
      "content": "（chunk 文本内容）",
      "score": 0.72,
      "metadata": {}
    }
  ],
  "total": 1
}
```

## 3. 上传文档

**端点**：`POST /knowledge-bases/{kb_id}/knowledge/manual`

**请求体**：

```json
{
  "title": "湖南电信_网络安全漏洞管理制度",
  "content": "# 文档 Markdown 内容...",
  "status": "publish"
}
```

> **多标签处理**：`manual` 端点只接受单个 `tag_id`。当 `--tags` 传入多个标签时，`kb_upload.py` 会**把标签拼到 title 前缀** `[tag1/tag2] <title>`，不传 `tags` 字段。

**响应**（真实结构 `{data: {id: ...}}`）：

```json
{
  "data": {
    "id": "doc-uuid-001"
  },
  "success": true
}
```

**`kb_upload.py` 归一化输出**：

```json
{
  "ok": true,
  "doc_id": "doc-uuid-001",
  "kb_id": "kb-uuid-001",
  "title": "湖南电信_网络安全漏洞管理制度",
  "size_bytes": 51801
}
```

**⚠️ 异步行为**：manual 端点**只返回 doc_id**，不等待解析与向量化完成。立即调 `kb_search` 大概率搜不到——用 `kb_docs.py` 轮询 `parse_status` 直至 `"completed"`。

## 4. 列出某库下所有文档

**端点**：`GET /knowledge-bases/{kb_id}/knowledge?page=1&page_size=20`

**请求参数**：
- `page`：页码（从 1 开始）
- `page_size`：每页文档数（默认 20）

**响应**（真实结构 `{data: {items, total, page, page_size}, success}`）：

```json
{
  "data": {
    "items": [
      {
        "id": "doc-uuid-001",
        "knowledge_base_id": "kb-uuid-001",
        "title": "中国电信云运〔2024〕29号.pdf",
        "file_name": "中国电信云运〔2024〕29号.pdf",
        "file_type": "pdf",
        "file_size": 2048000,
        "parse_status": "completed",
        "enable_status": "enabled",
        "summary_status": "completed",
        "created_at": "2026-05-01T08:00:00Z",
        "updated_at": "2026-05-01T08:05:00Z",
        "processed_at": "2026-05-01T08:05:00Z",
        "error_message": ""
      },
      {
        "id": "doc-uuid-002",
        "title": "湖南电信_网络安全漏洞管理制度.md",
        "file_name": "湖南电信_网络安全漏洞管理制度.md",
        "file_type": "md",
        "file_size": 51801,
        "parse_status": "processing",
        "enable_status": "enabled",
        "created_at": "2026-06-17T08:00:00Z",
        "updated_at": "2026-06-17T08:00:00Z",
        "processed_at": "",
        "error_message": ""
      }
    ],
    "total": 12,
    "page": 1,
    "page_size": 20
  },
  "success": true
}
```

**`kb_docs.py` 归一化输出**：

```json
{
  "kb_id": "kb-uuid-001",
  "total": 12,
  "page": 1,
  "page_size": 20,
  "documents": [
    {
      "doc_id": "doc-uuid-001",
      "title": "中国电信云运〔2024〕29号.pdf",
      "file_name": "中国电信云运〔2024〕29号.pdf",
      "file_type": "pdf",
      "file_size": 2048000,
      "parse_status": "completed",
      "enable_status": "enabled",
      "summary_status": "completed",
      "created_at": "2026-05-01T08:00:00Z",
      "updated_at": "2026-05-01T08:05:00Z",
      "processed_at": "2026-05-01T08:05:00Z",
      "error_message": ""
    }
  ]
}
```

**关键字段**：
- `parse_status`：`"completed"` 表示已解析+向量化完成，可被 `kb_search` 命中；`"processing"` / `"pending"` 表示还在跑；`"failed"` 通常伴随 `error_message` 非空
- `enable_status`：`"enabled"` 表示文档被纳入检索；`"disabled"` 表示已停用（仍在库中但搜不到）
- `processed_at`：完成解析的时间戳（处理中时为空字符串）

## 服务端字段 vs 兼容字段对照表

| 服务端真实字段 | kb_*.py 兼容字段 | 出现位置 |
|:--------------|:----------------|:---------|
| `id` | `kb_id` / `doc_id` | 库 ID 与文档 ID |
| `knowledge_count` | `doc_count` / `document_count` | KB 文档数 |
| `chunk_count` | （新增）`chunk_count` | KB 已索引 chunk 数 |
| `title` | `name` | 库名/文档名 |
| `filename` / `file_name` | `title` | 文档标题（兼容旧字段） |
| `file_size` | `size` / `size_bytes` | 文档大小 |
| `parse_status` | （无兼容） | 文档解析状态 |

> 修改 `kb_*.py` 字段映射前请确认服务端字段名；**不要**仅依据本文档——以 `requests` 实际响应为准。

## 错误响应（统一信封）

所有 4xx/5xx 响应体由 `kb_http.py` 归一化为：

```json
{
  "error": "auth",
  "message": "认证失败：API Key 无效或无权限",
  "status": 401
}
```

`error` 取值见 `error-codes.md`。
