# 飞书 API 速查

## 选题库

- **App Token**: `YjN6bWopMaYixSs1ArncqVBLn1c`
- **Table ID**: `tblspru4cgIMd5M3`

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 选题标题 | text | 选题名称 |
| 主题分类 | select | 分类（国际政治、AI时代等） |
| 状态 | select | 待写/已完成/已发布 |
| 推荐书籍 | text | 推荐的书目 |
| 热点结合 | text | 结合的热点话题 |
| 备注 | text | 补充说明 |
| 文章发布地址 | text | 发布后的 URL |
| 创建日期 | date | 创建时间 |

## 文案库

- **App Token**: `XsBnb6AOTafA8usGoIGc2faunUh`
- **Table ID**: `tblwHGCK9VwzORYR`

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 文章标题 | text | 文章标题 |
| 文章分类 | text | 分类 |
| 文章摘要 | text | 摘要（不超过120字） |
| 文章内容-markdown | text | Markdown 正文 |
| 文章内容-html | text | HTML 正文（微信公众号用） |
| 文章配图 | text | 配图 |
| 文章发布地址 | text | 发布 URL |
| 日期 | date | 发布日期 |

## 飞书云盘

- **投稿文件夹 Token**: `YPMwfcqfilMkxgd2MsTcOAumn6g`
- **上传 API**: `POST /open-apis/drive/v1/files/upload_all`
- 必填参数: `parent_type=explorer`, `parent_node`, `file_name`, `size`, `file`

## Coze 工作流

- **API**: `POST https://api.coze.cn/v1/workflow/stream_run`
- **Workflow ID**: `7629233812262879273`
- **参数**: `article_content`, `article_digest`(≤120字), `article_imageprompt`, `article_title`, `article_type`
