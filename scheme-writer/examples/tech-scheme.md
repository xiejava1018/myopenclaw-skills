# 示例：基于知识库编写 Kubernetes 离线部署方案

> 这是 scheme-writer 的完整使用示例，对应 SKILL.md 中"协作工作流 → 场景 1"。

## 用户输入

> 帮我从《技术规范库》查一下，写一份 K8s 离线部署方案，写完归档到《方案库》。

## Claude 解析结果

- intent = `generate_and_upload`
- retrieve_kb = `kb_id_001`（"技术规范库" → 别名映射）
- upload_kb = `kb_id_002`（"方案库" → 别名映射）
- with_citation = false

## 步骤 1：检索

Claude 执行：

```bash
python scripts/kb_search.py \
  --kb kb_id_001 \
  --query "K8s 离线部署" \
  --top-k 8 \
  --min-score 0.5
```

返回（节选）：

```json
{
  "kb_id": "kb_id_001",
  "query": "K8s 离线部署",
  "chunks": [
    {
      "chunk_id": "c-9f3a",
      "source_doc": "K8s 离线部署手册 v2.3.md",
      "content": "离线环境需先在有网环境预下载镜像、Helm chart、kubectl 插件...",
      "score": 0.84
    },
    {
      "chunk_id": "c-2b81",
      "source_doc": "镜像仓库同步 SOP.md",
      "content": "使用 crane 或 skopeo 把镜像从公网仓库同步到内网 Harbor...",
      "score": 0.78
    }
  ],
  "total": 6
}
```

## 步骤 2：写作

Claude 引用上述 chunk，输出大纲（10 个章节），用户确认后展开为完整方案。  
末段提示："参考了《K8s 离线部署手册 v2.3》《镜像仓库同步 SOP》"。

## 步骤 3：上传前确认

Claude 输出：

> 确认：正在将《Kubernetes 离线部署方案》上传到《方案库》(kb_id_002)...（取消请说"停"）

## 步骤 4：上传

用户未取消，Claude 执行：

```bash
python scripts/kb_upload.py \
  --kb kb_id_002 \
  --file k8s-offline-scheme.md \
  --title "Kubernetes 离线部署方案" \
  --tags "方案,K8s,离线"
```

返回：

```json
{"ok": true, "doc_id": "doc-2026-06-17-k8s-offline-1", "kb_id": "kb_id_002", "title": "Kubernetes 离线部署方案", "size_bytes": 4321}
```

## 步骤 5：反馈

Claude：

> 已归档到《方案库》，doc_id=doc-2026-06-17-k8s-offline-1。

## 注意事项

1. **首次使用**必须先跑 `python scripts/init.py` 配置 `.env`
2. **别名映射表**（SKILL.md 顶部）由 `init.py` 完成后自动填充
3. 上传是**显式行为**，用户没说要上传时**绝不**默认归档
