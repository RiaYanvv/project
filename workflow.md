已按你的要求完成——**没有修改任何代码**，下面是纯规划文档。所有结论都基于我刚刚读过并逐条验证过的真实代码路径。

先说两个必须先分清的事实，否则 Phase 1 会白做：

- 项目里有**两层互相独立的 mock**。第一层在前端：`window.LOCUS_API_BASE` 在 `frontend/index.html` 里是注释掉的，且 `app.js` 要求 `LOCUS_API_BASE` 和 `LOCUS_API_KEY` **同时存在**才走 live（`runAnalysis`、`checkAgentConnection`）。第二层在后端：没有 `DEEPSEEK_API_KEY` 时 `main.py` 在模块加载时就选了 `MockLLM`。任何一层没打通，你看到的都是假结果，但表现完全一样。
- 数据库里 8 条 assessment 全部是 `model_mode: "mock"`，而 `model_name` 却写着 `deepseek-flash`，`data_mode` 写着 `hybrid`。**trace 里 RiskAgent / ScenarioAgent / AdvisorAgent 全部显示 "completed"**，只有 IntelligenceAgent 显示 "fallback"。也就是说：规则模板的输出被当成"模型成功输出"记录下来了。这是 Phase 1 必须解决的核心可观测性问题。

---

## Phase 1 — 打通真实 LLM

### 1.1 当前 mock mode 在哪里决定

| 位置 | 逻辑 | 后果 |
|---|---|---|
| `config.py` `Settings.from_env()` | `LLM_PROVIDER` 为空时：有 `DEEPSEEK_API_KEY` → `deepseek`，否则 → `mock` | 默认静默降级到 mock |
| `main.py` 模块级 | `if settings.llm_provider == "deepseek" and settings.deepseek_api_key: DeepSeekLLM(...) else: MockLLM()` | 进程启动时一次性决定；加 key 后必须重启 |
| `agent.py` `run()` | `if self.llm.mode == "deepseek": if not api_key: raise ValueError(...)` | 真实模式必须由请求体带 key |
| `frontend/index.html` | `window.LOCUS_API_BASE` / `LOCUS_API_KEY` 是注释 | 前端默认走本地 preview，根本不请求后端 |

### 1.2 进入真实 LLM 的最小配置

- 后端 `.env`：`LLM_PROVIDER=deepseek`、`DEEPSEEK_API_KEY=sk-...`、`DEEPSEEK_MODEL=deepseek-chat`（注意：请求体会用 `llm_model` 覆盖成 `deepseek-flash`）。
- 前端 `index.html`：放开 `window.LOCUS_API_BASE = "http://127.0.0.1:8000"` 和 `window.LOCUS_API_KEY`。
- **这一步不需要改任何代码**，但目前这么配完，你依然无法证明调用成功——因为第 1.4 节的问题。

### 1.3 需要修改的代码路径（最小集）

| 文件 | 改动 | 为什么需要 |
|---|---|---|
| `llm.py` `_call_json()` | 失败时**不要返回 baseline**，改为返回 `(result, ok, meta)` 或抛 `LLMUnavailable` | 现在重试 3 次失败后静默返回 baseline，调用方无法区分 |
| `agent.py` `run()/chat()/resimulate()` | 各 stage 调用点消费 `ok`，把 `trace.status` 写成 `completed` 或 `fallback` | 现在 mock 的 baseline 是 dict，`_coerce_*` 判定为"合法模型输出"，trace 显示 completed |
| `schemas.py` | `Assessment` 新增 `llm_calls: list[LLMCallRecord]`、`degraded: bool`；`TraceStep.status` 增加 `fallback` 语义 | 让"这次到底调没调模型"变成可查询的事实 |
| `config.py` | 新增 `LLM_REQUIRED`（默认 false）。为 true 时无 key 直接启动失败 | 比赛演示时避免静默降级 |
| `main.py` `/api/v1/meta` | 返回 `llm_provider` / `llm_configured` / `llm_required` | 前端和联调脚本可自检 |

**不需要改**：RetrievalProvider、schemas 的既有字段、前端请求格式。

### 1.4 如何验证"这次真的调用了 LLM"

按可信度从高到低：

1. `Assessment.model_mode == "deepseek"` 且新增的 `llm_calls` 每个 stage 有 `model`、`latency_ms`、`attempts`、`ok=true`；`degraded=false`。
2. **负例测试**（最重要）：故意配一个假 key，跑一次。期望结果是 `degraded=true` + 每个 stage 的 `trace.status="fallback"` + `limitations` 里出现"本阶段使用规则基线"。如果负例看起来和正例一样，就说明可观测性没修好。
3. `trace` 中不允许出现"mock/baseline 内容 + completed 状态"的组合。
4. 加一个 `tests/test_live_llm.py`：没有真 key 时 `skip`，有 key 时断言 `llm_calls` 全绿、且输出与 baseline 不同。

> 两个实测坑要在这一步一起验掉：(a) `_call_json` 在流式路径上同时发 `stream:true` + `response_format:json_object`，DeepSeek 是否接受需要确认；(b) 流式路径会把 `reasoning_content` 作为事件下发，确认不会混进用户可见文本。

### 1.5 API 失败时 fallback 怎么保留

**保留**现有确定性 baseline（它是演示兜底，不能删），但必须改成"**显式降级**"：

- 该 stage 的 `trace.status = "fallback"`，detail 明确写"模型不可用，已降级为规则基线"；
- `Assessment.degraded = true`，`limitations` 追加一条；
- 前端显示"规则基线"标签，而不是现在的 `hybrid` 标签。

原则：**允许降级，禁止伪装**。

### 1.6 前后端改动量

- 前端：**基本不动**。`app.js` 已经在渲染 `trace` 和 `meta.model_name`；只需把 agent 状态 chip 的文案从 `data_mode` 改为读 `degraded`，避免"mock 却显示 hybrid"。
- 后端：上面 5 处，属于小改动。

**解决 P0：1（默认 mock）、并让 2–7 的所有改进可验证。**

---

## Phase 2 — Company Research + Company Intelligence（最高优先级）

### 2.1 目标 workflow

```
User Input
  → Company Entity Understanding   （新增，确定性 + 1 次 LLM 调用）
  → Company Research               （新增工具，公司维度检索/抓取）
  → Evidence Retrieval             （保留现有 HybridRetrieval，改成 stage-specific）
  → Company Intelligence           （重写 prompt + 输出结构）
  → Risk Assessment
```

### 2.2 research query 怎么组

按"每类问题一条 query"，不要把所有字段塞进一条：

| Query | 模板 | 目的 |
|---|---|---|
| Q1 实体 | `"{company_name}" "{home_country}" {industry_terms}` | 确认是不是同一家公司、全称、别名、总部、是否上市 |
| Q2 布局 | `"{company_name}" factory plant manufacturing site {production countries}` | 核实生产基地与所在国 |
| Q3 供应链 | `"{company_name}" supplier cathode anode cell raw material` | 上游依赖 |
| Q4 市场 | `"{company_name}" customer export market {target markets}` | 下游市场 |
| Q5 决策 | `"{company_name}" {decision type} capacity expansion overseas` | 决策背景与扩产/迁移新闻 |

`industry_terms` 由 `industry` 映射（现有 `retrieval.py` 的 `industry_concepts` 可直接复用，不要重写）。

### 2.3 当前 WebSearchTool 能做什么 / 不能做什么

**能**：US Federal Register（法规原文，A/B 级）+ Crossref（学术文献）。返回带 URL、日期、authority 的 `RetrievedEvidence`，有 relevance ≥45 的过滤。

**不能**：不能搜公司官网、年报、新闻、企业登记信息；不能做中文来源；没有通用网页搜索；`_web_query_text()` 完全不含 company_name。

**结论**：它只能支撑"政策/学术证据"，**不能**支撑 company research。

### 2.4 当前 RAG 能做什么 / 不能做什么

**能**：28 篇策展文档、5,931 chunks、FTS5 + BM25 + 元数据（authority/topic/country/date）、可回溯原文（`document_url`）。

**不能**：没有公司实体；"embedding"是 512 维 hashed bag-of-words，不是语义向量；query 无 company 字段；没有 reranker；没有评测集。

**结论**：RAG 目前是"政策风险库"，不是"公司情报库"。

### 2.5 是否需要新增 company-specific retrieval —— 需要，但复用现有组件

新增一个 `CompanyResearchTool`（新文件，与 `web_search.py` 平级），复用**已有依赖**（httpx / bs4 / pypdf，`crawler.py` 已有抽取逻辑，不要重写）：

- 公司官网（About/Products/Press）→ 用 `crawler.py` 的 HTML/PDF 抽取；
- Wikipedia / Wikidata API（免费、无 key）→ 实体消歧、总部、成立年份、上市信息；
- SEC EDGAR（若为美股上市公司）→ 年报/10-K 的事实级来源；
- 可选：公司新闻 RSS。

结果统一转成 `RetrievedEvidence`，但**新增字段区分来源域**：`evidence_scope: "company" | "policy"`、`is_self_reported: bool`、`authority_level` 增加公司语境的档位定义（年报/监管文件 = A+，公司自述 = B，百科 = C）。

### 2.6 如何避免 CATL 被搜成 solar PV / 无关公司

这是**检索质量门**问题，不是 prompt 问题。数据库里 CATL 的 top-1 证据确实是光伏反规避裁决，说明现在的加权（`circumvention`/`customs` + China）压过了行业信号。四道门：

1. **行业硬门**：`battery_ev` 必须至少命中 1 个行业词（battery/cell/cathode/850760/870380…），否则该 chunk **不得**进入"公司事实"证据池（仍可进入"政策风险"池）。
2. **行业负门**：对 battery_ev 明确排除 `photovoltaic / solar cell / silicon wafer / solar panel` 等词。
3. **实体门**：任何被用来支持"公司事实"的证据，chunk 内必须出现公司名或已知别名；否则只能标 `inferred`。
4. **别名表**：Q1 先产出 `aliases[]`（如 CATL / 宁德时代 / Contemporary Amperex Technology），后续查询用别名并集；同时用 HQ + 行业交叉验证，避免同名公司。

### 2.7 如何区分四类事实

| 类别 | 判定规则 | 展示 |
|---|---|---|
| `user_input` | 来自表单；**永不被推断覆盖**；与公开源冲突时保留两者并置 `conflict=true` | 用户提供 |
| `public_source` | 至少 1 条 evidence_id，且该 fact 的关键实体/数字能在 chunk 文本中定位 | 公开已验证 + 可点开原文 |
| `inferred` | 由 ≥1 条已知事实推导；必须记录 `derived_from: [fact_id]` | **AI 推断**（必须显式标注） |
| `to_be_confirmed` | 其余全部 | 待确认 |

关键：目前代码里 `public_source` 只有一条"检索到 N 条资料"这种**伪事实**（`agent.py:_build_intelligence`），必须禁止——`public_source` 只允许承载具体公司事实。

### 2.8 Company Intelligence 输出字段（在现有结构上扩展，保持向后兼容）

```
entity: {legal_name, aliases[], headquarters, listing{exchange,ticker}, founded_year,
         size{revenue_range, employees_range, factories_count}}
overview[]            FactItem
production_footprint[] FactItem
supply_chain[]         FactItem
strategic_context[]    FactItem(paragraph)  ← 新增 cites: fact_ids[]
market_position[]      FactItem  ← 新增
information_gaps[]     str
FactItem: {fact, source_ids[], data_status, confidence, as_of, derived_from[]}
```

前端已经在渲染 `company_intelligence` 的 `fact / data_status / source_ids`，所以新增字段是**加法**，不会破坏现有 UI。

### 2.9 每个 fact 怎么绑 evidence_ids

- 生成阶段：LLM 只能从**本次检索返回的 evidence_id 白名单**里引用（现有 `_coerce_intelligence` 已经在过滤，保留）。
- 校验阶段（新增）：对每条 `public_source` fact，要求其关键 token（公司名/国家/数字/产品词）至少出现在所引 chunk 的正文中；不满足 → 降级为 `inferred` 或 `to_be_confirmed`。
- 禁止：任何"没有 evidence 就默认塞前几条"的逻辑（Phase 3 会统一根除）。

### 2.10 必须标记为 unknown 的信息（禁止猜）

产能、产能利用率、各基地生产份额（除用户填写）、合资/股权结构、客户名单、供应商名单、单位成本、订单积压、具体 HS/ECCN 分类。这些一律进 `information_gaps`，**不允许**出现在 `public_source`。

### 2.11 Strategic Context 怎么写才不是复读机

强制四段式，每段都必须引用前文 fact 或明确写 unknown：

1. **Current position**：基于 entity + footprint 事实，指出公司处于电池价值链的哪个环节、以哪国为制造核心（引 fact_id）。
2. **Supply-chain structure & dependencies**：基于 supply_chain 事实，指出已知的跨国依赖；未知就写"未确认"，并说明为什么重要。
3. **Market & geopolitical exposure**：把 target markets 映射到贸易/原产地/关税暴露，必须引用 policy evidence（这里正是现有 RAG 的强项）。
4. **Decision tension**：把用户决策与前三段结论对照，写出真实取舍（成本 vs 韧性 vs 市场准入），并给出"哪些信息会改变建议"。

验收标准：把 Strategic Context 单独拿出来，必须**无法**只靠表单复述出来——至少引用 2 个 policy evidence + 2 个公司 fact，否则判为不合格。

**解决 P0：2、3（company research + company-specific evidence）。**

---

## Phase 3 — Evidence System：Evidence → Risk → Scenario → Recommendation

### 3.1 引用关系设计

```
Evidence (EVD-xxx)
   ├─ supports / contradicts / context ──> Risk
   ├─ supports / context ───────────────> Scenario dimension
   └─ 间接 ─────────────────────────────> Recommendation（只能引用其采纳的 scenario 的证据）
```

### 3.2 必须删除的逻辑

`agent.py` 中三处 `evidence_ids or [evidence[:2]]`（约 610、644、676 行）。这是 P0-4 的根因：它让每条风险/情景看起来都有证据，实际是随便挂的。**改为：没有合格证据就不写 evidence，并标记风险为证据不足。**

### 3.3 证据选择规则（新增）

对每条 risk，候选证据必须同时满足：

1. `relevance_score >= 阈值`（建议按 topic 校准，而不是全局一个数）；
2. 与 risk 的 `category_key` 有 topical 交集（`restriction_concepts` / `topic`）；
3. 行业门通过（Phase 2.6）。

通过则记为 `supports`；不通过则该 risk 不带 evidence，`insufficient_evidence=true`。

### 3.4 冲突 / 过期处理

对**每条 evidence 本身**（不要给企业级 risk level）做四个独立判断：

| 判断 | 取值 | 来源 |
|---|---|---|
| authority | S/A+/A/B+/B/C/D | 已有字段 |
| relevance | high/medium/low | 检索分 + LLM 复核 |
| freshness | current / aging / stale | 由 `publication_date` 计算年龄档 |
| verification | verified / partial / unverified / **contested** / **outdated** | 新增两个枚举值 |

规则：

- **contested**：两条 A/B 级以上来源给出相反结论 → risk 标 `contested`，`requires_human_review=true`；两条都在证据里，`support` 分别是 supports / contradicts。
- **outdated**：超过该 topic 的新鲜度窗口，或存在"同一 publisher + 同一 topic 的更新文件"（`superseded_by`）；现有 ingest 阶段已经有 `Status: EXPIRED/REPEALED` 的跳过逻辑，建议把 metadata 里的 `status / effective_date` 提升为**可查询列**，不要在正文里搜。

### 3.5 Risk / Scenario / Recommendation 的引用不变量

- 每条 risk：要么 ≥1 条合格 evidence，要么显式 `insufficient_evidence`；
- 每个 scenario 的**每个维度**至少 1 条证据或明确标注为推断；
- recommendation 只能引用它采纳的 scenario 所引用的证据集合（防止"推荐 A 却引 B 的证据"）；
- 校验失败时不允许静默替换，必须降级并记录到 `limitations`。

**解决 P0：4。**

---

## Phase 4 — Risk Assessment Prompt Specification

### 4.1 Risk taxonomy

沿用现有六类 `category_key`（trade / political / supply_chain / regulatory / market_access / operational），`RISK_CATEGORY_KEYWORDS` 已实现，不要新增体系。要求模型**必须先选 category，再写 name**。

### 4.2 risk level 判断规则

| severity | 必要条件 |
|---|---|
| critical | ≥1 条 S/A+ 证据 + 明确的法规或商业机制（如具体条款/清单） |
| high | ≥2 条 A/B+ 证据，且用户 constraints 命中 |
| medium | ≥1 条 B 级证据 |
| low | 其余（含仅有用户输入的情况） |
| —（不给级） | 无证据且无用户输入 → 只输出 `insufficient_evidence` |

禁止在无证据时给 critical/high。

### 4.3 probability 是否还要 0–100

**建议废弃面向用户的 0–100。** 理由：前端从未展示该字段（已验证 grep 无结果），只有 PDF/HTML 报告模板里印了 `severity / probability%`，属于"无依据的数字精确度"，与 UI 规范冲突。

替换为 ordinal `likelihood`：`very_low / low / medium / high / very_high`，并追加 `likelihood_basis`（为什么是这个档）。如需排序，后端可映射成内部数值，但不展示、不落库为"客观概率"。

### 4.4 impact / uncertainty / information gap 如何表达

- **impact**：`impact_channels[]`（cost / lead_time / market_access / compliance / capacity）+ 一句定性说明 + 受影响的具体环节。不要写"影响很大"这种空话。
- **uncertainty**：`uncertainty_reasons[]`（证据不足 / 政策未定 / 公司数据缺失）+ `what_would_change_it[]`（什么信息会改变判断）。
- **information gap**：提升到 **assessment 级** `information_gaps[]`，不要每条风险各编一个。

### 4.5 supporting evidence 如何选

只能引用白名单内的 evidence_id，且遵循 Phase 3.3 的门。引用时给 `support: supports|context|contradicts`。

### 4.6 什么情况下必须拒绝判断

- 无合格证据且用户未提供相关约束 → 输出 `insufficient_evidence=true`，**不给 severity/likelihood**；
- 证据互相冲突 → `contested` + 建议人工复核；
- 问题涉及具体法律结论（是否违规、是否适用某许可证）→ 只描述机制与不确定性，不给结论。

### 4.7 可追溯性

每条 risk 增加 `basis: "evidence" | "user_input" | "inference"`。凡是 `inference`，必须在 UI/报告里显式标注。

**解决 P0：5（风险评分无 rubric）。**

---

## Phase 5 — Scenario Simulation

### 5.1 三个 scenario 的定义

| ID | 名称 | 定义（必须写入 prompt，避免模型自由发挥） |
|---|---|---|
| S1 | Maintain Current Layout | 维持现有国家分布与份额，仅通过库存/供应商管理降低扰动 |
| S2 | Increase China Production | 把部分中高复杂度环节回迁中国，利用成熟供应商生态 |
| S3 | Hybrid Diversification | 按产品/市场拆分产能，形成 2–3 个区域性节点 |

### 5.2 五个维度的定义

| 维度 | 定义 | 主要输入 |
|---|---|---|
| Cost Impact | 变动后总成本相对现状的变化（越低分越高） | 用户预算/时间、单位成本、关税与原产地证据 |
| Supply Chain Resilience | 对单点/单一供应商依赖的降低程度 | supplier_dependency、行业证据、产能分散度 |
| Geopolitical Risk Exposure | 暴露于关税/出口管制/地缘摩擦的程度（越低分越高） | Phase 4 的风险 + policy evidence |
| Market Access | 满足目标市场准入/原产地规则的能力 | target_markets + 原产地/关税证据 |
| Implementation Feasibility | 在期限内落地的可行度 | time_horizon、预算、认证/爬坡约束 |

### 5.3 每个维度怎么从 evidence + profile + risks 推导

每个维度输出必须包含：`band`（档位）+ `reason`（1–2 句）+ `evidence_ids[]` + `source: evidence|inference`。推导链：**用户约束 → 风险 → 证据 → 档位**。禁止只写分数不写依据。

### 5.4 0–100 是否合理

**保留 0–100**（前端已经按 Overall score 展示，改动成本低），但**不允许模型自由给数**。做法：模型只选档位，后端把档位映射为固定数值 → 分数变成 rubric 的产物，而不是直觉。

### 5.5 Score Anchors（每个维度同构）

| 档位 | 分值 | 含义 |
|---|---|---|
| Very favourable | 85 | 证据明确支持，无重大不确定性 |
| Favourable | 70 | 证据支持，存在可控不确定性 |
| Neutral | 55 | 证据不足以区分优劣 |
| Unfavourable | 35 | 证据指向明确成本/风险上升 |
| Very unfavourable | 20 | 证据明确指向不可行或重大暴露 |

无证据时强制落在 Neutral 并标 `inference`，不得给 85 或 20。

### 5.6 weighted_score 怎么结合用户 priorities

沿用 `_weighted_scenario_score()` 的后端计算（**不要**让 LLM 算总分）。建议：

- 权重直接取 `CompanyInput.priorities`（已有 0–5）；
- 缺失维度用中性权重 3；
- `implementation_score` 保持 0.5 折扣（可解释为"是实现难度而非收益"）；
- 新增返回 `score_breakdown: [{dimension, weight, contribution}]`，让前端能展示"为什么是这个分"。这个字段目前缺失，是 `backend changes.md` 里已记录的 #20。

### 5.7 LLM 和后端分别负责什么

| 负责方 | 内容 |
|---|---|
| LLM | 每个维度的档位选择 + 理由 + 引用证据；scenario 的 benefits/risks/applicable_conditions |
| 后端 | 档位→分值映射、加权总分、排序、confidence、`insufficient_evidence` 判定 |

### 5.8 如何避免随意打分

1. 只允许输出档位（枚举），后端映射数值；
2. 每个维度必须带 reason + evidence_ids 或显式 `inference`；
3. `temperature` 保持 0.15（已配置）；
4. 校验不过 → 该 scenario 降级为模板评分并标 `degraded`，不要静默接受。

**解决 P0：5。**

---

## Phase 6 — Consultation Context

### 6.1 为什么 chat history 没进 LLM

`DeepSeekLLM.answer_chat()` 的 payload 只有：`company`、`current_assessment{risks, scenarios, recommendation}`、`existing_evidence`、`supplemental_evidence`、`user_message`。**没有 `chat_history`**。`agent.py:407` 只把历史写进 `Assessment.chat_history` 落库，从未回传给模型；`choose_chat_action()` 同样不含历史。所以每轮对话都是"失忆"的。

### 6.2 consultation context 的组合方式

```
[System]  角色 + 证据纪律 + 语言 + 引用规则
[State]   Company Profile（含 intelligence facts）
          + Evidence（按 relevance 取 top-N）
          + Risks（含 evidence_links）
          + Scenarios（含 breakdown）
          + Recommendation
[History] 最近 N 轮 chat_history（建议 6–10 轮，超出做摘要）
[Turn]    New user information（本轮）
          + supplemental_evidence（若触发检索）
```

要点：状态放前面（稳定），历史放中间（可截断），本轮放最后（权重最高）。历史超长时保留"第一轮 + 最近 N 轮"，中间做一次 compress 摘要。

### 6.3 新增信息如何分流

把现有 `chat_analysis` 扩展为 `ChatImpact`：

| 类别 | 判定 | 动作 |
|---|---|---|
| 更新 Company Profile | 命中 budget / capacity / footprint / product / market 等结构化字段 | 写回 `CompanyInput`（新增一个 draft/patch 存储），重算 profile summary 与 intelligence 的相关 fact |
| 更新 Constraints | 投资预算、时间线、不可迁移项、成本上限 | 写回 `CompanyInput`，标记受影响的风险 |
| 触发 Scenario Re-simulation | 影响成本/韧性/市场准入/实施可行性的信息 | 自动或提示调用 `POST /{id}/scenarios`（接口已存在） |
| 仅用于回答当前问题 | 一般性提问、澄清、寒暄 | 只进 chat_history，不改状态 |

**风险更新**：新增信息命中某条 risk 的机制时，不要就地改写风险等级，而是标记 `risk.stale=true` 并提示重跑；避免"聊天把风险悄悄改了"。

**Scenario 更新**：沿用 `resimulate()`，但目前它是把约束拼进 `company.notes` 的一段文字——建议改为结构化字段追加到 `CompanyInput`，这样 prompt 里是字段而不是自然语言尾巴。

**上传文件**：当前无接口，前端只存文件名（`handleChatFiles`）。这属于 P1，见 Phase A。

**解决 P0：6。**

---

## Phase 7 — Report

### 7.1 目标 flow

```
Assessment data  →  LLM long-form report content  →  citation validation  →  existing PDF renderer
```

不改渲染器架构：`build_assessment_pdf()` 继续负责排版，只是优先消费新字段 `report_content`，缺失时回退到现在的模板。

### 7.2 章节（8 节）

1. Executive Summary
2. Company Profile
3. Current Supply Chain Situation
4. Key Risks
5. Scenario Comparison
6. Recommendation / Decision Considerations
7. Evidence（编号、标题、发布方、日期、权威等级、可回溯链接）
8. Uncertainties and Information Gaps

### 7.3 不允许编造新事实

三条硬规则：

1. 报告 prompt **只**接收已确认的 Assessment 数据，不接入任何新检索；
2. 引用白名单校验：出现的每个 `EVID-xxx` 必须在 `assessment.evidence` 中，否则该段落判不合格；
3. 数字白名单校验：正文中的金额/份额/日期必须能在 assessment 里找到同源，否则改写为定性表述。

这样可以保证"报告是重新组织已有结论"，而不是"重新做一次分析"。

### 7.4 版本

后端新增 `report_versions`（表或 `Assessment.reports[]`），每次生成追加 `version / generated_at / content_hash`，不覆盖旧版。前端 localStorage 里已经有 `report_versions` 概念，后端补上即可对齐。

**解决 P0：7。**

---

## A. 文件级修改清单

**需要修改（既有文件）**

| 文件 | 改动 |
|---|---|
| `backend/app/config.py` | `LLM_REQUIRED`；company research 相关开关与超时 |
| `backend/app/llm.py` | `_call_json` 返回调用元数据、不再静默返回 baseline；重写 4 个分析 prompt；`answer_chat` 加入 history；`choose_chat_action` 去掉硬编码中文 |
| `backend/app/agent.py` | 消费调用元数据写 trace；删除 `evidence[:2]` 兜底；新增 Entity Understanding / research / fact 校验步骤；Strategic Context 校验 |
| `backend/app/schemas.py` | `LLMCallRecord`、`Assessment.llm_calls/degraded`、`FactItem` 扩展、`RiskItem.evidence_links/likelihood/basis`、`ScenarioResult.score_breakdown`、`CompanyIntelligence.entity`、`ReportContent` |
| `backend/app/retrieval.py` | `RetrievalQuery` 增加 `company_name/aliases/evidence_scope`；行业硬门 + 负门；两池分流（company / policy） |
| `backend/app/knowledge.py` | ingest 时把 `status/effective_date` 建成可查询列；`superseded_by` 支持 |
| `backend/app/web_search.py` | 保留不动，仅新增 `evidence_scope="policy"` 标记 |
| `backend/app/main.py` | `/api/v1/meta` 暴露 LLM 状态；上传接口（P1）；报告版本接口（P1） |
| `backend/app/pdf_report.py` | 优先渲染 `report_content`；删掉重复定义的 `_table_style()`（第二个覆盖了第一个） |
| `backend/app/repository.py` | 报告版本 / 项目的读写（P1） |
| `frontend/index.html` | 放开 `LOCUS_API_BASE/KEY` 配置说明（不改逻辑） |
| `frontend/app.js` | 状态 chip 改读 `degraded`；展示 `inference` 标注与 score breakdown（P1） |

**需要新增**

| 文件 | 用途 |
|---|---|
| `backend/app/company_research.py` | CompanyResearchTool（官网 / Wikipedia / Wikidata / EDGAR），复用 `crawler.py` |
| `backend/app/prompts/`（或 `llm_prompts.py`） | 把 6 个 prompt 从 `llm.py` 抽出，便于评审与版本化 |
| `backend/tests/test_live_llm.py` | 有 key 才跑的端到端真实调用测试 |
| `backend/tests/test_evidence_binding.py` | 断言"无证据不得自动挂前两条" |
| `backend/scripts/eval_retrieval.py` | 用 `data/evaluation/` 做小规模相关性评测 |

**保持不动（明确不要碰）**

`repository.py` 的存储形态、`main.py` 的路由契约、`RetrievalProvider` 接口、`pdf_report.py` 的排版骨架、全部 Pydantic 既有字段名、前端页面结构与请求格式。

---

## B. 按优先级排序

**P0（必须完成，直接决定 AI 能力）**

| # | 事项 | 对应 P0 |
|---|---|---|
| P0-1 | 真实 LLM 打通 + 显式降级可观测（Phase 1） | 1 |
| P0-2 | 删除 `evidence[:2]` 默认挂载 + 证据相关性门（Phase 3 前半） | 4 |
| P0-3 | Company Research 工具 + Entity Understanding（Phase 2） | 2、3 |
| P0-4 | Company Intelligence prompt 与 fact 校验 + Strategic Context 四段式（Phase 2） | 2、3 |
| P0-5 | Risk prompt 重写 + 取消 0–100（Phase 4） | 5 |
| P0-6 | Scenario rubric + band 映射 + 后端加权（Phase 5） | 5 |
| P0-7 | Consultation 注入 chat_history + 影响分流（Phase 6） | 6 |

**P1（完成后明显提升）**

- 报告 LLM 长文生成 + 引用/数字白名单（Phase 7）；
- 报告版本落库；
- 决策项目后端持久化（`DP-` 与 `ASM-` 对齐）；
- 文件上传 → 入库 → 参与检索；
- `superseded_by` / contested 的完整实现；
- `score_breakdown` 在前端展示。

**P2（截止前可以不做）**

- 真语义 embedding / reranker；
- 检索评测集自动化；
- 多语言 heuristic 文案统一；
- 前端把 `probability` 彻底移除；
- 报告 HTML 路由的弃用或统一。

---

## C. 最小改造路径（面向比赛 MVP）

原则：**不加框架、不加新依赖、复用 RetrievalProvider / Evidence ID / SQLite / Pydantic。**

| 顺序 | 做什么 | 为什么是现在 | 前端影响 |
|---|---|---|---|
| 1 | Phase 1：打开真实 LLM + `llm_calls`/`degraded`/trace 诚实化 | 不解决这个，后面所有改动都无法验证；而且现在 mock 会伪装成成功 | 仅状态 chip 文案；无功能变化 |
| 2 | Phase 3a：删掉 `evidence[:2]`，加相关性门 | 约几十行，是 Phase 2 fact 绑定的前提 | 无 |
| 3 | Phase 2：Entity Understanding + CompanyResearchTool + Intelligence prompt + fact 校验 + Strategic Context | 最高产品价值，直接解决"复读用户输入" | Company Profile 区块出现真实来源与 AI 推断标注（前端已支持） |
| 4 | Phase 4：Risk prompt 重写（taxonomy / severity 规则 / likelihood / basis / 拒答） | 风险是情景的输入 | 风险列表更少但更实；PDF 不再印百分比 |
| 5 | Phase 5：Scenario rubric + band + score_breakdown | 依赖 4 的风险质量 | 情景页可显示"为什么是这个分" |
| 6 | Phase 6：Consultation context + ChatImpact 分流 | 让咨询真正产生价值 | 聊天页上下文面板会随新信息更新 |
| 7 | Phase 7：Report LLM 长文 + 白名单校验 | 最后一块，且依赖前面全部稳定 | 报告页 PDF 变详实；版本号由后端给出 |
| 8 | P1：报告版本库、项目持久化、文件上传 | 提升完整体验 | My Decisions 可跨设备；上传真正生效 |

验收建议（每一步都要过）：

- 第 1 步后：假 key 测试必须显示 `degraded=true`；
- 第 3 步后：CATL 案例的 Strategic Context 必须引用 ≥2 条 policy evidence + ≥2 条公司 fact，并且不得复述表单；
- 第 4/5 步后：任何一条 risk / 任一 scenario 维度，都必须能点开至少一条证据，或明确写着"AI 推断 / 待确认"；
- 第 7 步后：报告正文里每个 `EVD-` 都能在 evidence 表中找到。

一句话总结优先级逻辑：**先把"到底调没调模型"变成事实（1），再把"证据是不是真的"变成约束（2），然后把"公司是谁"变成真信息（3），最后才是让 prompt 更聪明（4–7）。**