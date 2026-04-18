<div align="center">

# Unified Search

**Claude Code 搜索 Skill — 多引擎并行，交叉验证，只给可信结果。**

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

[English](README_EN.md) | 中文

</div>

---

## 这是什么

一个给 [Claude Code](https://claude.ai/code) 用的搜索 Skill。激活后，Claude 不再依赖单一搜索引擎——它同时调 8 个引擎，交叉比对，多个引擎都说有的结果才标为高置信度。

```
"帮我查 Claude Code 最新功能"
        ↓
  ┌─ Exa ─────→ 结果 A
  ├─ Tavily ──→ 结果 A ✓ 交叉验证
  ├─ Metaso ──→ 结果 A ✓
  ├─ Brave ───→ 结果 B
  └─ DuckDuckGo → 结果 A ✓
        ↓
  结果 A: confidence=high（4 个引擎命中）
  结果 B: confidence=low（1 个引擎命中）
```

## 为什么需要它

AI 搜索最大的问题：单一来源不可靠。模型自信满满引用一个来源，点开一看——内容对不上，链接打不开。多个独立来源都说同一件事，才值得相信。

## 安装

```bash
git clone https://github.com/NieAnSHOW/unified-search.git
cd unified-search
cp config.example.json config.json
# 编辑 config.json，填入至少 2 个引擎的 API Key
```

将项目目录放入 Claude Code 的 skills 目录，`SKILL.md` 会自动激活。

## 使用方式

### 作为 Skill 使用（推荐）

Skill 激活后，直接对 Claude Code 说任何需要搜索的问题，它会自动走多引擎管道：

> "帮我查一下 2026 年 AI 编程工具有哪些更新"

> "最近一周有什么科技新闻"

> "事实核查：XXX 这个说法是真的吗"

Claude 会返回带置信度标注的结果，高置信度优先展示，低置信度附提醒。

### CLI 直接调用

```bash
# 基础搜索
python3 dispatcher.py "Claude Code 2026 最新功能"

# 只看最近一周
python3 dispatcher.py "Claude Code 2026 最新功能" --freshness 1w

# 指定引擎
python3 dispatcher.py "Claude Code 2026 最新功能" --engines exa,tavily

# 精简输出
python3 dispatcher.py "Claude Code 2026 最新功能" --compact
```

### 可视化 Dashboard

```bash
python3 dashboard.py --port 9728
```

浏览器打开 `http://localhost:9728`，可以看到引擎健康状态、在线搜索测试、会话统计。

或者在 Claude Code 中直接说「启动可视化页面」。

## 支持的搜索引擎

| 引擎 | 类型 | 需要 API Key | 获取地址 |
|------|------|-------------|---------|
| Exa | AI 搜索 | 是 | [dashboard.exa.ai](https://dashboard.exa.ai) |
| Tavily | AI 搜索 | 是 | [tavily.com](https://tavily.com) |
| Querit | AI 搜索 | 是 | [querit.ai](https://querit.ai) |
| Metaso（秘塔） | 中文搜索 | 是 | [metaso.cn](https://metaso.cn) |
| 博查 | 国内搜索 | 是 | [bocha.io](https://bocha.io) |
| Brave | Web 搜索 | 是 | [brave.com/search/api](https://brave.com/search/api) |
| DuckDuckGo | Web 搜索 | **否** | 开箱即用 |
| 阿里云 IQS（夸克） | 云搜索 | 是 | [aliyun.com/product/iqs](https://www.aliyun.com/product/iqs) |

> **最低要求**：启用 2 个引擎即可获得交叉验证效果。DuckDuckGo 免费，建议先配上。

## 置信度等级

| 等级 | 条件 | 含义 |
|------|------|------|
| `high` | 3+ 引擎返回相同结果 | 多源交叉验证，可信 |
| `medium` | 2 个引擎返回相同结果 | 基本可信 |
| `low` | 仅 1 个引擎返回 | 单一来源，谨慎对待 |

## 扩展引擎

插件式架构，两步添加新引擎：

1. 在 `engines/` 下创建文件，继承 `BaseEngine`，实现 `search()` 和 `_normalize()` 两个方法
2. 在 `config.json` 中添加配置

`dispatcher.py` 会自动发现并加载新引擎，无需注册。

## License

[MIT](LICENSE)
