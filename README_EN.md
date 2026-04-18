<div align="center">

[English](#README_EN.md) | [中文](#中文)

</div>

---
## Why This Project?

If you've used LLMs, you've probably seen this: the model confidently cites a source, but when you click the link, the content doesn't match or the URL is broken. A single search engine is like having only one witness — you can't verify if it's telling the truth.

**Unified Search takes a simple approach: query multiple search engines in parallel, cross-validate results, and only mark results confirmed by multiple engines as high-confidence.**

## Quick Start

```bash
git clone https://github.com/NieAnSHOW/unified-search.git
cd unified-search
cp config.example.json config.json
# Edit config.json with your API keys (2+ engines needed for cross-validation)
python3 dispatcher.py "your search query"
```

## Features

- **8 search engines** — Exa, Tavily, Querit, Metaso, Bocha, Brave, DuckDuckGo, Aliyun IQS
- **Cross-validation** — Results confirmed by 3+ engines get `high` confidence, single-source gets `low`
- **Zero dependencies** — Pure Python stdlib, no `pip install` needed
- **Plugin architecture** — Add a new engine with one file, two methods
- **Web Dashboard** — Engine health monitoring, live search testing, session stats
- **Freshness filter** — Filter results by day/week/month/year

## Adding a New Engine

```python
# engines/my_engine.py
from engines.base import BaseEngine, SearchResult

class MyEngine(BaseEngine):
    name = "my_engine"
    display_name = "My Engine"
    priority = 100
    requires_key = True

    def search(self, query, max_results=10, freshness=None, config=None):
        raw = self._call_api(query, config)
        return self._normalize(raw)

    def _normalize(self, raw_results):
        return [SearchResult(title=r["title"], url=r["url"],
                snippet=r["snippet"], source_engine=[self.name])
                for r in raw_results]
```

The dispatcher auto-discovers engines — no registration needed.

## Tests

```bash
python3 -m pytest tests/ -v
```

All tests use mocks — no real API keys required.

## License

[MIT](LICENSE)
