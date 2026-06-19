# 错误码与退出码速查

## 退出码总表

| 退出码 | 含义 | 触发场景 |
|:-------|:-----|:---------|
| 0 | 成功 | 调用完成 |
| 1 | 通用错误 | init 写入失败等 |
| 2 | 参数错误 | 缺少 `--kb` / `--query` / `--file` 等；缺配置时也归为 2 |
| 3 | 认证失败 | API Key 无效（HTTP 401/403） |
| 4 | 知识库不存在 | HTTP 404 |
| 5 | 网络/服务端错误 | HTTP 5xx、连接失败 |
| 6 | 请求超时 | `requests.Timeout` |
| 7 | 文件读取失败 | 上传时文件不存在（仅 `kb_upload`） |

`init --check` 使用单独一套退出码：

| 退出码 | 含义 |
|:-------|:-----|
| 0 | 配置完整且可达 |
| 1 | 配置缺失 |
| 2 | 认证失败 |
| 3 | 网络失败 |

## 错误信封（stderr JSON）

所有失败都把以下结构写到 stderr：

```json
{
  "error": "<error_code>",
  "message": "<人类可读描述>",
  "<其他字段>": "..."
}
```

`error` 取值：`bad_args` / `auth` / `kb_not_found` / `timeout` / `file_read` / `server`。

## Claude 端处理建议

- 收到 `auth` → 提示用户在服务端轮换 Key，告诉 Claude "重新配置 scheme-writer"
- 收到 `kb_not_found` → 提示用户调 `kb_list.py` 重新确认 kb_id
- 收到 `timeout` → 提示用户增加 `--timeout`，或检查网络
- 收到 `bad_args` 且 message 含"缺少必需配置" → 让 Claude 自动走 `init.py --status` 引导配置
- 收到 `server` → 提示用户稍后重试，或检查 WeKnora 服务状态

## `init.py` 退出码 → Claude 动作速查

| 退出码 | 标签 | 含义 | Claude 应采取的动作 |
|:-------|:-----|:-----|:-------------------|
| 0 | `OK` | 配置完整且可达 | 静默继续 |
| 1 | `NEED_INIT` | 配置缺失 | 进入对话内配置流程（`AskUserQuestion` + `--set`） |
| 2 | `NEED_REAUTH` | API Key 无效 | 提示用户在服务端轮换 Key 后说"重新配置" |
| 3 | `NETWORK_ERROR` | 网络/服务端故障 | 提示用户检查 URL / 网络 / 服务端状态 |

`--status` 子命令以单行 stdout 标签返回同样信息，退出码恒为 0（便于在对话中解析而不退出）。
