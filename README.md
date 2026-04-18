<div align="center">

# Unified Search

**大模型搜索不够靠谱？让多个搜索引擎交叉验证，只给你可信的结果。**

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

[English](#english) | [中文](#中文)

</div>

---

<a id="中文"></a>

## 为什么需要这个项目？

用过大模型的人大概都遇到过这种情况——模型自信满满地引用了一个来源，结果点开一看，要么内容对不上，要么链接根本打不开。单一搜索引擎的结果就像只有一个证人——你没办法判断它说的是不是真的。

**Unified Search 的做法很简单：同时问多个搜索引擎，交叉比对，只有多个引擎都给出的结果，才标记为高置信度。**

```
你的查询 → [Exa] [Tavily] [Metaso] [Brave] [DuckDuckGo] ...
                  ↓           ↓          ↓
              结果A        结果A       结果B
                  ↓           ↓
              去重合并 + 交叉验证评分
                  ↓
         结果A: confidence=high (3个引擎命中)
         结果B: confidence=low  (1个引擎命中)
```

## 核心特性

- **8 个搜索引擎并行** — Exa、Tavily、Querit、Metaso（秘塔）、博查、Brave、DuckDuckGo、阿里云 IQS（夸克），覆盖中英文搜索
- **交叉验证 + 置信度评分** — 多引擎命中的结果标记为 `high`，单一来源标记为 `low`，每条结果都有明确的可信度等级
- **零外部依赖** — 纯 Python 标准库实现（`urllib`、`json`、`concurrent.futures`），`pip install` 都不需要
- **插件式引擎架构** — 添加新引擎只需创建一个文件，继承 `BaseEngine`，实现两个方法
- **Web Dashboard** — 内置可视化面板，实时查看引擎健康状态、搜索统计、在线搜索测试
- **时效过滤** — 支持按天/周/月/年过滤结果，适合查新闻和时效性内容

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/unified-search.git
cd unified-search
```

### 2. 配置 API Key

复制示例配置文件，填入你的 API Key：

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "default_engines": ["tavily", "exa", "metaso", "bocha"],
  "min_engines": 2,
  "timeout_seconds": 10,
  "engines": {
    "tavily": {
      "api_key": "your-tavily-api-key",
      "enabled": true
    },
    "exa": {
      "api_key": "your-exa-api-key",
      "enabled": true
    },
    "metaso": {
      "api_key": "your-metaso-api-key",
      "enabled": true
    },
    "bocha": {
      "api_key": "your-bocha-api-key",
      "enabled": true
    },
    "duckduckgo": {
      "enabled": true
    }
  }
}
```

> **最低要求**：配置 2 个引擎即可获得交叉验证效果。DuckDuckGo 无需 API Key，开箱即用。

**API Key 获取方式：**

| 引擎 | 获取地址 | 说明 |
|------|---------|------|
| Tavily | [tavily.com](https://tavily.com) | AI 搜索，免费额度 |
| Exa | [dashboard.exa.ai](https://dashboard.exa.ai) | AI 搜索，支持语义/关键词模式 |
| Metaso（秘塔） | [metaso.cn](https://metaso.cn) | 中文搜索优秀 |
| 博查 | [bocha.io](https://bocha.io) | 国内搜索 |
| Querit | [querit.ai](https://querit.ai) | AI 搜索 |
| Brave | [brave.com/search/api](https://brave.com/search/api) | 传统 Web 搜索 |
| DuckDuckGo | 无需 API Key | 传统 Web 搜索，开箱即用 |
| 阿里云 IQS | [aliyun.com/product/iqs](https://www.aliyun.com/product/iqs) | 云搜索 |

### 3. 运行搜索

```bash
# 基础搜索
python3 dispatcher.py "Claude Code 2026 最新功能"

# 只看最近一周的结果
python3 dispatcher.py "Claude Code 2026 最新功能" --freshness 1w

# 只用指定引擎
python3 dispatcher.py "Claude Code 2026 最新功能" --engines exa,tavily

# 精简输出（省略摘要）
python3 dispatcher.py "Claude Code 2026 最新功能" --compact

# 限制结果数量
python3 dispatcher.py "Claude Code 2026 最新功能" --max-results 5
```

**输出示例：**

```json
{
  "query": "Claude Code 2026 最新功能",
  "timestamp": "2026-04-17T12:00:00Z",
  "engines_used": ["exa", "metaso", "tavily"],
  "engines_failed": [],
  "total_results": 8,
  "overall_confidence": "high",
  "results": [
    {
      "title": "Claude Code April 2026 Update",
      "url": "https://...",
      "snippet": "...",
      "source_engine": ["exa", "metaso", "tavily"],
      "published_date": "2026-04-15",
      "score": 0.97
    }
  ]
}
```

## 交叉验证机制

这是 Unified Search 的核心——不只是聚合搜索结果，而是验证它们。

### 置信度等级

| 等级 | 条件 | 含义 |
|------|------|------|
| `high` | 3+ 个引擎返回相同结果 | 多个独立来源交叉验证，可信度高 |
| `medium` | 2 个引擎返回相同结果 | 有一定可信度 |
| `low` | 仅 1 个引擎返回 | 单一来源，需谨慎对待 |

整体置信度（`overall_confidence`）取 Top 5 结果中的最低等级——保守估计，宁可信其不可靠。

### 评分算法

```
score = base_score + priority_bonus + recency_bonus
```

- **base_score** = 来源引擎数 × 0.3（3 个引擎 = 0.9）
- **priority_bonus** = 来源引擎中最高优先级的权重（Exa 最高 0.20，DuckDuckGo 最低 0.05）
- **recency_bonus** = 时效窗口内的结果额外 +0.1

### 去重规则

URL 归一化后合并相同结果：统一小写、去除 `www.`、移除 `utm_*` 追踪参数、按参数名排序。字段保留策略：最长的标题、最长的摘要、最近的发布日期、最高的评分。

## Web Dashboard

内置可视化面板，方便监控引擎状态和调试搜索效果。

```bash
python3 dashboard.py --port 9728
```

浏览器打开 `http://localhost:9728`，可以看到：

- **引擎健康检查** — 实时检测各引擎状态和响应延迟
- **在线搜索测试** — 直接在页面上输入查询，实时查看多引擎结果和置信度
- **会话统计** — 累计搜索次数、各引擎调用/失败计数、平均响应时间

## 添加新引擎

插件式架构，添加新搜索引擎只需两步：

**Step 1** — 在 `engines/` 下创建一个文件，继承 `BaseEngine`：

```python
# engines/my_engine.py
from engines.base import BaseEngine, SearchResult

class MyEngine(BaseEngine):
    name = "my_engine"
    display_name = "My Engine"
    priority = 100
    requires_key = True

    def search(self, query, max_results=10, freshness=None, config=None):
        # 调用你的搜索 API
        raw = self._call_api(query, config)
        return self._normalize(raw)

    def _normalize(self, raw_results):
        # 将 API 响应转换为统一的 SearchResult 列表
        return [
            SearchResult(
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"],
                source_engine=[self.name],
            )
            for item in raw_results
        ]
```

**Step 2** — 在 `config.json` 中添加配置：

```json
{
  "engines": {
    "my_engine": { "api_key": "your-key", "enabled": true }
  }
}
```

完成。`dispatcher.py` 会自动发现并加载新引擎。

## 作为 Claude Code Skill 使用

Unified Search 可以作为 [Claude Code](https://claude.ai/code) 的 Skill 使用，替代内置搜索，让 AI 编程助手也能用上交叉验证搜索。

将项目目录放入 Claude Code 的 skills 目录，SKILL.md 中的指令会自动激活。激活后，Claude Code 执行搜索时会走 unified-search 的管道，而不是内置的 `WebSearch`。

## 项目结构

```
unified-search/
├── dispatcher.py          # CLI 入口 + 并行调度引擎
├── merger.py              # 结果合并器：去重、评分、置信度计算
├── config_loader.py       # 配置加载与验证
├── dashboard.py           # Web Dashboard 服务
├── dashboard.html         # Dashboard 前端页面
├── config.json            # 引擎配置（已加入 .gitignore）
├── SKILL.md               # Claude Code Skill 描述
├── engines/
│   ├── base.py            # BaseEngine 抽象基类 (60 行)
│   ├── exa.py             # Exa AI 搜索
│   ├── tavily.py          # Tavily 搜索
│   ├── querit.py          # Querit 搜索
│   ├── metaso.py          # 秘塔 AI 搜索
│   ├── bocha.py           # 博查搜索
│   ├── brave.py           # Brave Search
│   ├── duckduckgo.py      # DuckDuckGo
│   └── aliyun_iqs.py      # 阿里云 IQS
├── tests/                 # pytest 测试套件
│   ├── test_merger.py
│   ├── test_dispatcher.py
│   ├── test_integration.py
│   └── ...                # 每个引擎都有独立测试
└── docs/
```

### 代码量

| 模块 | 行数 | 说明 |
|------|------|------|
| 核心调度与合并 | ~1,200 | dispatcher + merger + base + config_loader |
| Dashboard | ~350 | Web 服务 + 统计 |
| 引擎实现 | ~1,400 | 8 个搜索引擎适配器 |
| 测试 | ~5,700 | 完整的 pytest 测试套件 |

## 运行测试

```bash
# 全部测试
python3 -m pytest tests/ -v

# 单个模块
python3 -m pytest tests/test_merger.py -v
python3 -m pytest tests/test_exa.py -v
```

所有测试通过 mock 隔离外部依赖，无需真实 API Key。

## CLI 参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `query` | 搜索关键词（必填） | `"AI trends 2026"` |
| `--freshness` | 时效过滤 | `1w`（一周）、`3d`（三天）、`1m`（一月） |
| `--engines` | 指定引擎 | `exa,tavily,metaso` |
| `--max-results` | 每引擎最大结果数 | `5` |
| `--compact` | 精简输出 | 省略 snippet 和 published_date |

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 — 2+ 引擎返回结果，交叉验证有效 |
| 1 | 部分成功 — 仅 1 个引擎返回结果 |
| 2 | 失败 — 无引擎返回结果 |

## License

[MIT](LICENSE)

---

<a id="english"></a>

## Why This Project?

If you've used LLMs, you've probably seen this: the model confidently cites a source, but when you click the link, the content doesn't match or the URL is broken. A single search engine is like having only one witness — you can't verify if it's telling the truth.

**Unified Search takes a simple approach: query multiple search engines in parallel, cross-validate results, and only mark results confirmed by multiple engines as high-confidence.**

## Quick Start

```bash
git clone https://github.com/your-username/unified-search.git
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
