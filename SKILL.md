---
name: unified-search
description: Use when user needs web search, real-time information lookup, fact-checking, or any network-based data retrieval. Triggers unified multi-engine search with cross-validation. Also provides a web Dashboard (`python3 dashboard.py`, port 9728) for visualizing engine health, search stats, and live testing — say "启动可视化页面" to launch, "重启可视化页面" to restart. DO NOT use other search tools when this skill is active.
---

# Unified Search

统一多引擎搜索技能。通过并行调用多个搜索引擎并对结果进行交叉验证、去重合并，提供高置信度的搜索结果。

---

## 1. 触发条件

当用户需要以下任何场景时，激活此技能：

- 网络搜索（查找信息、查询资料）
- 实时信息（新闻、最新动态、当前事件）
- 事实核查（验证信息真实性、交叉比对）
- 网络数据检索（获取任何超出知识截止日期的信息）

---

## 2. 可视化 Dashboard

技能内置 Web Dashboard，提供图形化界面查看引擎健康状态、搜索统计数据和实时搜索测试。

### 启动方式

```bash
python3 /Users/niean/.cc-switch/skills/unified-search/dashboard.py [--port 9728]
```

用户也可以直接说"启动可视化页面"、"打开 Dashboard"、"查看搜索状态"等自然语言来触发启动。说"重启可视化页面"、"重启 Dashboard"可重启服务。

### 功能

| 页面 | 说明 |
|------|------|
| 引擎健康检查 | 实时检测各引擎状态（healthy / slow / error / disabled）和延迟 |
| 搜索测试 | 在页面上直接输入查询，实时查看多引擎结果和置信度 |
| 会话统计 | 累计搜索次数、各引擎调用/失败计数、平均响应时间 |
| 服务重启 | 页面内重启按钮或调用 `/api/restart` 热重启服务 |

### API 端点

| 端点 | 用途 |
|------|------|
| `GET /` | Dashboard 页面 |
| `GET /api/health` | 引擎健康状态 |
| `GET /api/search?q=...` | 执行搜索（可选 `&engines=exa,brave`） |
| `GET /api/stats` | 会话统计数据 |
| `GET /api/restart` | 热重启服务（`os.execv` 替换进程） |

---

## 3. 搜索隔离规则

**当此技能激活时，必须且只能使用 `dispatcher.py` 执行搜索。**

### 禁止使用的工具和方法

以下工具/方法在 unified-search 激活期间**严格禁止**使用：

| 禁止项 | 说明 |
|--------|------|
| `WebSearch` 内置工具 | Claude 内置的网络搜索 |
| MCP 搜索工具 | `mcp__exa__*`、`mcp__web-search-prime__*` 等 |
| `web-search` skill | Playwright 浏览器搜索技能 |
| `web-access` skill | CDP 代理浏览器技能 |
| `metaso-search` skill | 秘塔 AI 搜索技能 |
| `autoglm-websearch` skill | AutoGLM 网络搜索技能 |
| `curl` / `wget` 到搜索引擎 | 直接 HTTP 请求搜索引擎 API |

### 为什么必须隔离

交叉验证机制要求所有搜索结果经过统一的 `dispatcher.py -> merger.py` 管道处理。绕过此管道会导致：

- 结果无法去重和交叉验证
- confidence 评分体系失效
- 引擎优先级权重无法正确应用

---

## 4. Red Flags — 自我检查清单

在执行搜索之前，**必须**逐条检查以下项目。如果任何一项命中，立即停止并改用 `dispatcher.py`：

- [ ] 我正在考虑调用 `WebSearch` 工具 → **停止**
- [ ] 我正在考虑使用 MCP 搜索工具（exa、web-search-prime 等） → **停止**
- [ ] 我正在考虑调用 `metaso-search` 或 `web-search` skill → **停止**
- [ ] 我正在考虑使用 `curl` / `wget` 直接请求搜索引擎 → **停止**
- [ ] 我想"先快速用另一个工具查一下" → **停止**
- [ ] 我觉得某个单独的搜索引擎可能更快 → **停止**

**唯一正确的路径**: `python3 dispatcher.py "query"`

---

## 5. 工作流程

### Step 1: 分析搜索意图

- 识别用户查询的核心主题和目标
- 判断信息类型（事实型、时效型、深度研究型）
- 确定查询语言（中文查询保留中文，英文查询保留英文）

### Step 2: 构建最优查询

- 使用用户原始查询作为主查询
- 对于中文查询，可选择性生成英文变体以覆盖更多国际来源
- 查询应简洁明确，避免过于宽泛

```bash
# 中文查询 — 直接使用
python3 dispatcher.py "2026年人工智能发展趋势"

# 英文变体 — 补充搜索（可选）
python3 dispatcher.py "AI development trends 2026"
```

### Step 3: 执行搜索

```bash
# 基础搜索
python3 dispatcher.py "search query"

# 时效过滤（d=天, w=周, m=月, y=年）
python3 dispatcher.py "search query" --freshness 1w

# 指定引擎（逗号分隔）
python3 dispatcher.py "search query" --engines exa,brave

# 限制结果数量
python3 dispatcher.py "search query" --max-results 5

# 精简输出模式
python3 dispatcher.py "search query" --compact
```

**脚本路径**: 使用绝对路径确保可靠调用：

```bash
python3 /Users/niean/.cc-switch/skills/unified-search/dispatcher.py "query"
```

### Step 4: 分析结果

根据退出码判断搜索状态：

| 退出码 | 含义 | 处理方式 |
|--------|------|---------|
| 0 | 成功（2+ 引擎返回结果） | 正常分析结果 |
| 1 | 部分成功（仅 1 引擎） | 谨慎对待，标注低置信度 |
| 2 | 失败 | 检查网络和 API Key 配置，建议用户排查 |

**结果输出包含以下关键字段**：

- `engines_used`: 成功返回结果的引擎列表
- `engines_failed`: 失败的引擎列表
- `overall_confidence`: 整体置信度（high / medium / low）
- `results`: 合并去重后的结果列表，按 score 降序排列

**Confidence 级别处理**：

- **high**（3+ 引擎交叉验证）: 结果可信度高，可直接引用
- **medium**（2 引擎验证）: 结果基本可信，建议标注来源
- **low**（1 引擎或更少）: 结果需谨慎对待，建议用户自行验证

### Step 5: 综合回复

- 按相关性排序呈现结果
- 每条结果标注来源引擎（`source_engine` 字段）
- 高置信度结果优先展示
- 低置信度结果附加提醒
- 提供原始 URL 供用户深入查阅

回复格式示例：

```
搜索结果（置信度: high | 引擎: exa, brave, duckduckgo）

1. [标题]
   来源: exa, brave | 置信度: high
   摘要: ...
   URL: ...

2. [标题]
   来源: metaso | 置信度: low
   摘要: ...
   URL: ...
   ⚠️ 仅单一引擎返回，建议进一步验证
```

---

## 6. 配置说明

搜索引擎 API Key 配置位于 `config.json`：

```json
{
  "engines": {
    "exa": { "api_key": "", "weight": 100, "enabled": true },
    "querit": { "api_key": "", "weight": 75, "enabled": true },
    "tavily": { "api_key": "", "weight": 70, "enabled": true },
    "metaso": { "api_key": "", "weight": 60, "enabled": true },
    "brave": { "api_key": "", "weight": 30, "enabled": true },
    "duckduckgo": { "weight": 20, "enabled": true },
    "aliyun_iqs": { "api_key": "", "weight": 40, "enabled": true },
    "bocha": { "api_key": "", "weight": 50, "enabled": true }
  }
}
```

**配置路径**: `/Users/niean/.cc-switch/skills/unified-search/config.json`

- `api_key`: 填入对应搜索引擎的 API Key
- `weight`: 引擎权重（1-100），权重越高优先级越高，影响结果评分中的优先级加分
- `enabled`: 设为 `false` 可禁用特定引擎
- `duckduckgo` 无需 API Key，开箱即用
- 至少需要 2 个引擎启用才能获得有效的交叉验证结果

**默认权重排序**（从高到低）: exa(100) > querit(75) > tavily(70) > metaso(60) > bocha(50) > aliyun_iqs(40) > brave(30) > duckduckgo(20)

---

## 7. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 所有引擎失败（退出码 2） | 提示用户检查网络连接和 API Key 配置 |
| 部分引擎失败 | 自动降级，使用成功引擎的结果继续 |
| API Key 缺失 | 引擎自动跳过，提示用户在 config.json 中配置 |
| 超时 | 单引擎超时不影响其他引擎，最终报告失败引擎 |
| 无结果 | 尝试简化查询或更换引擎组合后重试 |
