<div align="center">

# Unified Search

**A Claude Code Skill — parallel multi-engine search with cross-validation for trustworthy results.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

English | [中文](README.md)

</div>

---

## What Is This

A search Skill for [Claude Code](https://claude.ai/code). Once activated, Claude no longer relies on a single search engine — it queries 8 engines in parallel, cross-validates results, and only marks results confirmed by multiple engines as high-confidence.

```
"What's new in Claude Code?"
        ↓
  ┌─ Exa ─────→ Result A
  ├─ Tavily ──→ Result A ✓ cross-validated
  ├─ Metaso ──→ Result A ✓
  ├─ Brave ───→ Result B
  └─ DuckDuckGo → Result A ✓
        ↓
  Result A: confidence=high (4 engines matched)
  Result B: confidence=low  (1 engine matched)
```

## Why You Need It

The biggest problem with AI search: single sources are unreliable. The model confidently cites a source, you click it — wrong content, broken link. Multiple independent sources confirming the same thing? That's worth trusting.

## Installation

```bash
git clone https://github.com/NieAnSHOW/unified-search.git
cd unified-search
cp config.example.json config.json
# Edit config.json with at least 2 engine API keys
```

Place the project directory in your Claude Code skills folder. `SKILL.md` activates automatically.

## Usage

### As a Claude Code Skill (Recommended)

Once activated, just ask Claude Code anything that requires search — it goes through the multi-engine pipeline automatically:

> "What are the latest AI coding tools in 2026?"

> "What tech news happened this week?"

> "Fact-check: is this claim true?"

Claude returns results with confidence labels — high-confidence results first, low-confidence ones flagged.

### CLI

```bash
# Basic search
python3 dispatcher.py "Claude Code 2026 latest features"

# Recent results only
python3 dispatcher.py "Claude Code 2026 latest features" --freshness 1w

# Specify engines
python3 dispatcher.py "Claude Code 2026 latest features" --engines exa,tavily

# Compact output
python3 dispatcher.py "Claude Code 2026 latest features" --compact
```

### Web Dashboard

```bash
python3 dashboard.py --port 9728
```

Open `http://localhost:9728` in your browser for engine health monitoring, live search testing, and session stats.

Or just say "启动可视化页面" in Claude Code.

## Supported Search Engines

| Engine | Type | API Key Required | Get It |
|--------|------|-----------------|--------|
| Exa | AI Search | Yes | [dashboard.exa.ai](https://dashboard.exa.ai) |
| Tavily | AI Search | Yes | [tavily.com](https://tavily.com) |
| Querit | AI Search | Yes | [querit.ai](https://querit.ai) |
| Metaso | Chinese Search | Yes | [metaso.cn](https://metaso.cn) |
| Bocha | China Search | Yes | [bocha.io](https://bocha.io) |
| Brave | Web Search | Yes | [brave.com/search/api](https://brave.com/search/api) |
| DuckDuckGo | Web Search | **No** | Works out of the box |
| Aliyun IQS | Cloud Search | Yes | [aliyun.com/product/iqs](https://www.aliyun.com/product/iqs) |

> **Minimum**: Enable 2+ engines for cross-validation. DuckDuckGo is free — start there.

## Confidence Levels

| Level | Condition | Meaning |
|-------|-----------|---------|
| `high` | 3+ engines return the same result | Cross-validated, trustworthy |
| `medium` | 2 engines agree | Mostly reliable |
| `low` | Only 1 engine | Single source, verify independently |

## Adding New Engines

Plugin architecture — two steps:

1. Create a file in `engines/`, extend `BaseEngine`, implement `search()` and `_normalize()`
2. Add config in `config.json`

The dispatcher auto-discovers new engines — no registration needed.

## License

[MIT](LICENSE)
