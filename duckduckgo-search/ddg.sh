#!/bin/bash
# DuckDuckGo Search Script for OpenClaw
# Usage: ddg.sh "search query" [limit]

QUERY="$1"
LIMIT="${2:-5}"

if [ -z "$QUERY" ]; then
  echo "Usage: ddg.sh 'search query' [limit]"
  exit 1
fi

# Try Instant Answer API first
RESULT=$(curl -s "https://api.duckduckgo.com/?q=$(echo "$QUERY" | sed 's/ /+/g')&format=json&no_html=1&kl=cn-zh")

# Check if we got a meaningful answer
SUMMARY=$(echo "$RESULT" | jq -r '.AbstractText // empty')

if [ -n "$SUMMARY" ] && [ "$SUMMARY" != "null" ]; then
  echo "📚 **即时答案**"
  echo "$SUMMARY"
  echo ""
  SOURCE=$(echo "$RESULT" | jq -r '.AbstractURL // empty')
  if [ -n "$SOURCE" ] && [ "$SOURCE" != "null" ]; then
    echo "🔗 来源: $SOURCE"
  fi
  echo ""
fi

# Get related topics
RELATED=$(echo "$RESULT" | jq -r ".RelatedTopics[:$LIMIT] | .[] | select(.Text) | \"• \(.Text)\"")

if [ -n "$RELATED" ]; then
  echo "📖 **相关主题**"
  echo "$RELATED"
fi

# If no instant answer, try HTML search
if [ -z "$SUMMARY" ] && [ -z "$RELATED" ]; then
  echo "🔍 搜索结果..."
  curl -s "https://html.duckduckgo.com/html/?q=$(echo "$QUERY" | sed 's/ /+/g')" \
    | grep -oP '(?<=<a class="result__a" href=")[^"]*' \
    | head -"$LIMIT" \
    | nl
fi
