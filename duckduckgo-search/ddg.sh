#!/bin/bash
# DuckDuckGo Search Script for OpenClaw (带代理支持)
# Usage: ddg.sh "search query" [limit]

QUERY="$1"
LIMIT="${2:-5}"

if [ -z "$QUERY" ]; then
  echo "Usage: ddg.sh 'search query' [limit]"
  exit 1
fi

# 代理配置
PROXY="http://127.0.0.1:10809"

# URL 编码查询
ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))" 2>/dev/null || echo "$QUERY" | sed 's/ /+/g')

echo "🔍 正在搜索: $QUERY"
echo ""

# 调用 API（带代理）
RESULT=$(curl -s -x "$PROXY" --connect-timeout 15 "https://api.duckduckgo.com/?q=$ENCODED_QUERY&format=json&no_html=1&kl=cn-zh")

if [ -z "$RESULT" ]; then
  echo "❌ 搜索失败：无法连接到 DuckDuckGo"
  exit 1
fi

# 提取标题
HEADING=$(echo "$RESULT" | jq -r '.Heading // empty' 2>/dev/null)
if [ -n "$HEADING" ] && [ "$HEADING" != "null" ] && [ "$HEADING" != "" ]; then
  echo "📌 **主题**: $HEADING"
  echo ""
fi

# 提取摘要
SUMMARY=$(echo "$RESULT" | jq -r '.AbstractText // empty' 2>/dev/null)

if [ -n "$SUMMARY" ] && [ "$SUMMARY" != "null" ] && [ "$SUMMARY" != "" ]; then
  echo "📚 **即时答案**"
  echo "$SUMMARY"
  echo ""
  
  SOURCE=$(echo "$RESULT" | jq -r '.AbstractURL // empty' 2>/dev/null)
  if [ -n "$SOURCE" ] && [ "$SOURCE" != "null" ]; then
    echo "🔗 来源: $SOURCE"
    echo ""
  fi
fi

# 提取相关主题（修复 jq 查询）
TOPICS_COUNT=$(echo "$RESULT" | jq '.RelatedTopics | length' 2>/dev/null)

if [ "$TOPICS_COUNT" -gt 0 ] 2>/dev/null; then
  echo "📖 **相关主题** ($TOPICS_COUNT 个结果)"
  echo ""
  
  echo "$RESULT" | jq -r ".RelatedTopics[:$LIMIT][] | select(.Text != null and .Text != \"\") | \"• \" + .Text" 2>/dev/null
  
  # 检查是否有带 FirstURL 但没有 Text 的主题
  echo "$RESULT" | jq -r ".RelatedTopics[:$LIMIT][] | select(.Text == null or .Text == \"\") | select(.FirstURL != null) | \"• <\" + .FirstURL + \">\"" 2>/dev/null
else
  echo "📖 **相关主题**: 无结果"
fi

# 如果没有结果，尝试 HTML 搜索
if [ "$TOPICS_COUNT" -eq 0 ] 2>/dev/null && [ -z "$SUMMARY" ]; then
  echo ""
  echo "🔍 **尝试网页搜索...**"
  HTML_RESULT=$(curl -s -x "$PROXY" --connect-timeout 15 "https://html.duckduckgo.com/html/?q=$ENCODED_QUERY")
  
  # 提取搜索结果链接
  echo "$HTML_RESULT" | grep -oP '(?<=<a class="result__a" href=")[^"]*' | head -"$LIMIT" | while read -r url; do
    echo "• $url"
  done
fi
