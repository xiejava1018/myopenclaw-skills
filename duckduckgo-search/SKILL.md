---
name: duckduckgo-search
description: Search the web using DuckDuckGo (free, no API key required). Use when you need to search for current information, documentation, or any web content.
homepage: https://duckduckgo.com/api
metadata: { "openclaw": { "emoji": "🔍", "requires": { "bins": ["curl", "jq"] } } }
---

# DuckDuckGo Search

Free web search using DuckDuckGo Instant Answer API. No API key required!

## Basic Search

```bash
# Search and get instant answers
curl -s "https://api.duckduckgo.com/?q=OpenClaw&format=json&no_html=1" | jq '.AbstractText, .RelatedTopics[].Text'
```

## Search with Complete Results

For more comprehensive results, use the HTML search (works without API):

```bash
# Using DuckDuckGo HTML version
search_term="Python tutorial"
curl -s "https://html.duckduckgo.com/html/?q=$(echo "$search_term" | sed 's/ /+/g')" \
  | grep -oP '(?<=<a rel="nofollow" class="result__a" href=")[^"]*' \
  | head -10
```

## JavaScript-based Search (Recommended)

For better results, use this Node.js one-liner:

```bash
# If you have node installed
node -e "
const https = require('https');
const query = process.argv[2];
const url = \`https://api.duckduckgo.com/?q=\${encodeURIComponent(query)}&format=json&no_html=1\`;
https.get(url, (res) => {
  let data = '';
  res.on('data', (chunk) => data += chunk);
  res.on('end', () => {
    const json = JSON.parse(data);
    console.log('Summary:', json.AbstractText || 'No summary');
    console.log('Source:', json.AbstractURL || 'N/A');
    if (json.RelatedTopics && json.RelatedTopics.length > 0) {
      console.log('\nRelated:');
      json.RelatedTopics.slice(0, 5).forEach(t => {
        if (t.Text) console.log('-', t.Text);
      });
    }
  });
}).on('error', console.error);
" "your search term"
```

## Alternative: Use Searxng (Privacy-focused)

If you want more comprehensive results, consider using Searxng:

```bash
# Public Searxng instance
curl -s "https://searx.be/search?q=test&format=json" | jq '.results[].title'
```

## Quick Search Function

Add this to your shell for quick searches:

```bash
# Add to ~/.bashrc or ~/.zshrc
ddg-search() {
  local query="$1"
  curl -s "https://api.duckduckgo.com/?q=$(echo "$query" | sed 's/ /+/g')&format=json&no_html=1" \
    | jq -r 'if .AbstractText then "📚 \(.AbstractText)\n🔗 \(.AbstractURL // "")" else "No instant answer found" end'
}
```

## Usage in OpenClaw

When user asks to search something:

1. **Try the Instant Answer API first** for quick facts (people, places, concepts)
2. **For general web search**, use the HTML version or combine with web_fetch
3. **For Chinese content**, add `kl=cn-zh` parameter
4. **Parse and present** results in a readable format

### Example Searches

```bash
# Search for a person
curl -s "https://api.duckduckgo.com/?q=Elon+Musk&format=json&no_html=1" | jq '.AbstractText'

# Search for a concept
curl -s "https://api.duckduckgo.com/?q=machine+learning&format=json&no_html=1" | jq '.AbstractText'

# Get related topics
curl -s "https://api.duckduckgo.com/?q=Python+programming&format=json" | jq '.RelatedTopics[].Text' | head -5
```

## Limitations

- Instant Answer API works best for facts, definitions, and popular topics
- For comprehensive web search, consider using Searxng or installing ddgr CLI tool
- Some searches may be rate-limited

## Tips

- Use specific queries for better results
- Combine with other tools (like web_fetch) to get full content from results
- For Chinese content, try: `curl -s "https://api.duckduckgo.com/?q=测试&format=json&kl=cn-zh"`
