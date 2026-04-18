<div align="center">

# Unified Search

**A Claude Code Skill — don't trust one engine, cross-validate them all.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

English | [中文](README.md)

</div>

---

## One Line

8 search engines in parallel, results cross-validated. If multiple engines agree, it's trustworthy. If only one says so, it's flagged low-confidence.

## Why Not Just Use One Engine

The model confidently cites a source — you click it, wrong content, broken link. The model isn't dumb. Single sources are just unreliable by nature.

Unified Search hits 8 engines at once: Exa, Tavily, Querit, Metaso, Bocha, Brave, DuckDuckGo, Aliyun IQS. Same query, sent in parallel, results cross-checked. Only results independently confirmed by multiple engines get marked high-confidence.

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

<img src="imgs/01.png" width="600">

## Install

Zero dependencies. Pure Python standard library. No `pip install` needed.

```bash
git clone https://github.com/NieAnSHOW/unified-search.git
cd unified-search
cp config.example.json config.json
# Edit config.json — fill in at least 2 engine API keys
```

Drop the project into your Claude Code skills folder. `SKILL.md` activates automatically.

## Usage

### As a Skill (Recommended)

Once activated, just talk to Claude Code. It handles the multi-engine pipeline automatically:

> "What are the latest AI coding tools in 2026?"
>
> "What tech news happened this week?"
>
> "Fact-check: is this claim true?"

Results come back with confidence labels. High-confidence first, low-confidence flagged.

### CLI

```bash
# Basic search
python3 dispatcher.py "Claude Code 2026 latest features"

# Recent results only
python3 dispatcher.py "Claude Code 2026 latest features" --freshness 1w

# Specific engines
python3 dispatcher.py "Claude Code 2026 latest features" --engines exa,tavily

# Compact output
python3 dispatcher.py "Claude Code 2026 latest features" --compact
```

### Dashboard

```bash
python3 dashboard.py --port 9728
```

Open `http://localhost:9728` in your browser — engine health, search stats, live testing, all in one page. Or just tell Claude Code "启动可视化页面".

## Supported Engines

| Engine | Type | Needs Key? | Get It |
|--------|------|-----------|--------|
| Exa | AI Search | Yes | [dashboard.exa.ai](https://dashboard.exa.ai) |
| Tavily | AI Search | Yes | [tavily.com](https://tavily.com) |
| Querit | AI Search | Yes | [querit.ai](https://querit.ai) |
| Metaso | Chinese Search | Yes | [metaso.cn](https://metaso.cn) |
| Bocha | China Search | Yes | [bocha.io](https://bocha.io) |
| Brave | Web Search | Yes | [brave.com/search/api](https://brave.com/search/api) |
| DuckDuckGo | Web Search | **No** | Works out of the box |
| Aliyun IQS | Cloud Search | Yes | [aliyun.com/product/iqs](https://www.aliyun.com/product/iqs) |

> Minimum 2 engines to get cross-validation working. DuckDuckGo is free — start with that.

## Confidence Levels

| Level | Condition | Meaning |
|-------|-----------|---------|
| `high` | 3+ engines agree | Trustworthy |
| `medium` | 2 engines agree | Mostly reliable |
| `low` | 1 engine only | Single source, verify yourself |

## Adding Engines

Two steps:

1. Create a file in `engines/`, extend `BaseEngine`, implement `search()` and `_normalize()`
2. Add config in `config.json`

The dispatcher auto-discovers new engines — no manual registration.

## License

[MIT](LICENSE)
