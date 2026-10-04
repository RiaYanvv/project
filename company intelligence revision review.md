# 改动方案审核：Company Intelligence 中枢化

**审核对象**：`origin/backend` @ `8d37168`、`origin/frontend` @ `1207155`
**审核日期**：2026-10-04
**审核方式**：逐函数核对真实代码（含一次真实运行产出的对象实样），不依赖文档推断

需求来源：《Company Intelligence 应成为中枢公司上下文层》——
要求把 Company Intelligence 变成贯穿整条流水线的持久公司上下文，所有下游 agent 必须显式接收它。

---

## 0. 审核结论（TL;DR）

| 项 | 结论 |
|---|---|
| 需求可行性 | **可行，不需要重构框架**。现有单体编排 + Pydantic 对象已能承载 |
| 最大缺口 | Company Intelligence 对象**已存在、已持久化，但下游引用数为 0** |
| 关键前置 | 先做"证据分流 + 画像去风险化"，再接线；否则会把越界判断放大到 4 个阶段 |
| 已有基础（不用重做） | `evidence_scope`（company/policy）字段已存在；`chat_history` 已进 prompt |
| 破坏性变更 | 1 处：`information_gaps` 从 `list[str]` 改类型 |
| 主要风险 | prompt token 膨胀；公司证据过薄（实测 2 条 company vs 9 条 policy） |

---

## 0.1 已确认的决策（2026-10-04）

| 问题 | 决议 |
|---|---|
| `information_gaps` 类型变更 | 采用**联合类型过渡**（`list[str \| InformationGap]`），前端同版本一起兼容 |
| 画像阶段是否给政策证据 | **不给**；改为**加强公司检索**来保证画像不空（见下） |
| 供应链角色词表 | 采用受控词表，**必须**有 `primary_role`，可有多个 `secondary_roles`；无法确认时**不要推断**，用 `OTHER` 或标 unknown |
| `risk_evidence` / `policy_evidence` 语义 | 采用 **One Evidence Store + Multiple Semantic Views**：只维护**一个** evidence 列表，不同 Agent 按任务过滤出各自视图；**不维护两个独立 list** |

供应链角色受控词表（用于步骤 2，目标是为 Risk / Scenario 提供稳定的企业角色标签，不做细分行业分类）：

```markdown
UPSTREAM_RAW_MATERIAL      - Raw material suppliers (lithium, nickel, cobalt, graphite…)
UPSTREAM_COMPONENT         - Battery material/component suppliers (cathode/anode/electrolyte/separator)
BATTERY_MANUFACTURING      - Cell / module / pack manufacturers
DOWNSTREAM_APPLICATION     - EV manufacturer, energy storage system provider, other applications
INTEGRATED_BATTERY_COMPANY - Companies covering multiple stages
OTHER                      - Unknown / Other
```

> 待确认：需求示例中 LG Energy Solution 的 `secondary_roles` 用了
> `ENERGY_STORAGE_SYSTEM_PROVIDER`，该值不在上述枚举内（对应值是
> `DOWNSTREAM_APPLICATION`，其描述即 "Energy storage system provider"）。
> 默认按枚举执行，即储能场景映射到 `DOWNSTREAM_APPLICATION`。

### 步骤 0–1 已完成（backend @ `a423976`）

- **证据分流**：按 `evidence_scope` 过滤，画像阶段只接收公司证据；公司证据为空时回退全量，
  避免一次检索失败就让画像变空白。
- **画像去风险化**：删掉"地缘政治暴露"段落与"必须引用 2 条政策证据"的要求，加入四条禁令。
- **加强公司检索**：改为从官网首页解析真实站内链接（猜路径实测 403/404 不可用），
  并补 Wikidata 失败时按公司名查 Wikipedia 的兜底。CATL 公司证据 **2 → 5 条**。
- **下游接线**：`analyze_risks` / `simulate_scenarios` / `generate_recommendation` /
  `choose_chat_action` / `answer_chat` / 情景重跑全部接收 `company_intelligence`；
  通过 `intelligence_brief()` 精简投影控制 token。
- **实测效果**：CATL 风险输出已变为公司级判断（引用其中国 60%/德国 40% 布局、
  无美国生产基地、2014 德国子公司等），画像四段中不含风险措辞。

**待办（步骤 2）**：角色枚举、设施级制造足迹表、信息缺口优先级 + why + action、
EvidenceReferences、前端渲染与报告章节。

---

## 1. 现状对照（逐条核对代码）

### 1.1 管线

需求管线：
`User Input → Company Research → Company Intelligence → Persistent Company Context → Risk → Scenario → Consultation → Report`

代码实际（`agent.py run()` @220）：

```
ProfileAgent(表单拼装) → EntityAgent(LLM) → ResearchAgent(检索)
  → IntelligenceAgent(LLM) → RiskAgent → ScenarioAgent → AdvisorAgent → VerificationAgent
                                                ↓
                              Assessment.company_intelligence  ← 存下来就结束了

chat() @599 / resimulate() @667 / pdf_report  ← 三个独立入口，各自从头取数据
```

**缺口**：不存在"Persistent Company Context"这一层被消费。它只是 Assessment 里的一个字段。

### 1.2 下游是否收到 Company Intelligence

| 函数 | 位置 | 现在的入参 | 是否含 intelligence |
|---|---|---|---|
| `analyze_risks` | `backend/app/llm.py:341` | `company, evidence, baseline` | ❌ |
| `simulate_scenarios` | `backend/app/llm.py:372` | `company, evidence, risks, baseline` | ❌ |
| `generate_recommendation` | `backend/app/llm.py:402` | `company, evidence, risks, scenarios, baseline` | ❌ |
| `choose_chat_action` | `backend/app/llm.py:433` | `company_profile, user_message, chat_history, current_risks` | ❌ |
| `answer_chat` | `backend/app/llm.py:462` | `company_profile, current_assessment, existing_evidence, supplemental_evidence, chat_history, user_message` | ❌ |
| `build_assessment_pdf` | `backend/app/pdf_report.py` | `assessment`（对象里有，但代码没用） | ❌ |

grep 全仓 `company_intelligence`：**只有 1 处**——`agent.py:585` 把它写进 Assessment。**没有任何读取方。**

### 1.3 payload 现状

需求要求改成 `company, company_intelligence, risk_evidence, policy_evidence`。

现状：所有下游用的是**同一个混合列表** `evidence`（`run()` 里 `_retrieve()` 的结果，company 与 policy 混在一起）。

> **审核意见**：需求里的 `risk_evidence` 与 `policy_evidence` 语义有重叠，需要先定义清楚。建议映射为：
>
> - `company_evidence` = `evidence_scope == "company"`
> - `policy_evidence` = `evidence_scope == "policy"`（即需求里的 risk_evidence）
>
> 即**两个视图、一个底层列表**，不要真的建三条管道。

### 1.4 必需字段对照

| 需求字段 | 代码现状（`backend/app/schemas.py`） | 差距 |
|---|---|---|
| CompanyOverview | `entity`(315) + `overview` + `market_position` | 业务模式 / 价值链角色不是一等字段 |
| ManufacturingFootprint | `production_footprint: list[FactItem]`(335) | 只有散点事实，**没有设施级结构** |
| SupplyChainStructure | `supply_chain: list[FactItem]`(336) | 无 upstream / midstream / downstream 三层 |
| StrategicContext | `strategic_context`(337) | 段落含"地缘政治暴露"，**越界** |
| InformationGaps | `information_gaps: list[str]`(339) | 无优先级、无 why、无 how |
| EvidenceReferences | 无 | 只有散落的 `source_ids`，无聚合引用表 |

### 1.5 一个必须一起处理的现状缺陷

`backend/app/llm.py:274` 的画像 prompt 现在明确写着：

> "strategic_context 必须恰好覆盖四段：公司现状、供应链结构与依赖、**市场与地缘政治暴露**、决策取舍……
> 每段至少引用 2 条公司事实和 **2 条政策证据**"

真实输出（最近一次运行）：

> `Market and geopolitical exposure：需要结合政策证据核验关税、原产地和准入暴露。`

**这正是需求里明确禁止的"画像阶段做风险判断"。** 如果先接线再改 prompt，等于把这个越界结论喂给 4 个下游 agent。

---

## 2. 改动方案

### A. 数据契约（`backend/app/schemas.py`）

```python
class InformationGap:          # 替换 information_gaps: list[str]
    item: str
    priority: Literal["critical", "important", "optional"]
    why_it_matters: str
    recommended_action: str
    source_ids: list[str] = []

class ManufacturingSite:       # 对应需求里的足迹表
    country: str
    facility: str = ""
    role: str = ""
    production_share: int | None = None
    capacity: str = "unknown"
    source_type: Literal["user_input","company_filing","official_website","industry_report","news"] = "user_input"
    status: Literal["verified","reported","estimated","inferred","unknown"] = "unknown"
    source_ids: list[str] = []

class SupplyChainRole:
    primary: str = ""                       # 受控词表
    secondary: list[str] = []
    upstream: list[FactItem] = []
    manufacturing: list[FactItem] = []
    downstream: list[FactItem] = []
    unknown: list[str] = []

class EvidenceReference:       # 对应 EvidenceReferences
    evidence_id: str
    title: str = ""
    publisher: str = ""
    source_type: str = ""
    used_for: list[str] = []
```

`CompanyIntelligence` 采用**只增不删**策略：

```
保留：executive_summary, entity, overview, production_footprint, supply_chain,
      strategic_context, market_position, information_gaps
新增：business_profile, manufacturing_footprint, supply_chain_role,
      decision_context, evidence_references
变更：information_gaps 类型（breaking）
```

- **契约版本**：`contract_version` 从 `1.0` → `1.1`。
- **兼容策略（推荐）**：`information_gaps` 先用 `list[str | InformationGap]` 联合类型过渡一个版本，
  前端同时兼容两种写法；稳定后再收紧。这样存量 8 条 assessment 不会读崩。

### B. 证据分流（小改动，因为基础已有）

`RetrievedEvidence.evidence_scope`（`backend/app/schemas.py:153`）**已经存在**，
实际运行里是 `{company: 2, policy: 9}`。所以分流只是筛选，不需要新建管道：

```python
def _company_evidence(evidence): return [e for e in evidence if e.evidence_scope == "company"]
def _policy_evidence(evidence):  return [e for e in evidence if e.evidence_scope != "company"]
```

各阶段分配：

| 阶段 | company | policy |
|---|---|---|
| IntelligenceAgent（画像） | ✅ 全部 | ⚠️ 不引用（仅作背景，或干脆不给） |
| RiskAgent | 可选 | ✅ 全部 |
| ScenarioAgent | ✅ | ✅ |
| Chat / Report | ✅ | ✅ |

### C. 下游接线（需求列出的 5 个函数）

| 函数 | 建议新签名 | 关键点 |
|---|---|---|
| `analyze_risks` | `(company, company_intelligence, risk_evidence, baseline)` | prompt 里加"必须以该公司事实为前提"，需求给的 LG 正反例可直接用 |
| `simulate_scenarios` | `(company, company_intelligence, risks, evidence, baseline)` | 情景要引用该公司的现有基地与供应链角色 |
| `generate_recommendation` | `(company, company_intelligence, risks, scenarios, evidence, baseline)` | 建议必须落到该公司实际约束 |
| `choose_chat_action` / `answer_chat` | payload 增加 `company_intelligence` | 聊天从"这家公司是谁"开始 |
| `resimulate` | 传 `assessment.company_intelligence` | 咨询重跑情景时也要带 |
| `build_assessment_pdf` | 使用 `company_intelligence` 生成 Company Profile 章节 | 现状完全没用 |

### D. 投递策略（本次审核最重要的设计意见）

**不要**把完整 `company_intelligence` 原样塞进 4 个 prompt。理由：它现在已包含 8 个区块、几十条 fact，
每条还带 6 个元数据字段；再乘 4 个阶段，token 与延迟都会明显上升
（当前一次完整运行已经 140–165 秒）。

建议引入**精简投影** `intelligence_brief()`，只带下游真正需要的部分：

```
identity          : 名称 / 总部 / 业务模式 / 价值链角色
supply_chain_role : primary + secondary
sites[]           : country / facility / role / share / status
markets[]         : 目标市场
decision_context  : 决策目标 + 驱动因素
critical_gaps[]   : 仅 critical 与 important 两档，最多 5 条
```

完整对象只用于：存储、报告、前端。各阶段按需取投影或全量。

### E. Prompt 改动

1. `build_intelligence`（`backend/app/llm.py:274`）：
   - 补上"**不回答**"的四条禁令（风险 / 严重度 / 是否迁移 / 哪个方案更好），并把需求给的正反例写进去；
   - **删掉"必须引用 2 条政策证据"**；
   - 四段改为：公司现状 → 供应链结构 → 市场定位 → 决策情境与待补信息（**去掉"地缘政治暴露"**）；
   - 增加缺口要求：`priority`（三档定义）+ `why_it_matters` + `recommended_action`；
   - 增加供应链角色受控词表；
   - 保留：只返回 JSON、`source_ids` 白名单、目标语言、`fact` 必须是字符串。
2. 下游 prompt：加一句"必须基于 `company_intelligence` 中的公司事实作答；不得泛化为行业级结论"。

### F. 持久化

现状：intelligence 存在 `assessments.payload_json` 里 → **对单个决策生命周期而言已经是持久的**，
chat / resimulate / report 都能从 Assessment 取到。

真正的缺口是"**跨项目复用**"，需求里没有要求，建议**本次不做**，只在 Assessment 内保证单一来源。

### G. 前端（`frontend/app.js`）

现状 `renderIntelligence`（约 1014 行）只渲染 4 个区块，缺口一律显示成 `To be confirmed`：

- `INTELLIGENCE_BLOCKS`（约 1001 行）只含 overview / production_footprint / supply_chain / strategic_context；
- **`executive_summary` 与 `market_position` 已生成但从不显示**（顺带补上）；
- 新增：足迹表格渲染、缺口按 Critical / Important / Optional 分档（红 / 琥珀 / 灰）+ why + action、
  来源类型与状态标签；
- `i18n.js` 补 status / priority 的中文词条。

### H. 报告

`backend/app/pdf_report.py` 的 Company Profile 一节改用 `manufacturing_footprint` 表格 + 缺口表；
`backend/app/main.py` 的 HTML 报告同步。

---

## 3. 测试计划（含需求指定的三个用例）

1. **契约测试**：每个下游函数收到的 payload 必须包含 `company_intelligence`（断言，防止接线回退）。
2. **CATL**：风险输出应体现"中国制造生态 / 海外扩张 / 美欧市场暴露"。
3. **LG Energy Solution**：应体现"韩国总部 / 中国供应链暴露 / 波兰欧盟产能 / 北美本地化"。
4. **通用 EV 电池公司**：必须区分"已知信息"与"行业级假设"，不得把行业通识写成公司事实。
5. **越界测试**：画像区块不得出现风险判断词汇（风险 / severity / 建议迁移）。
6. **缺口测试**：每条 gap 必须有合法 priority。
7. **兼容测试**：旧结构的 assessment 仍能被前端渲染。

---

## 4. 实施顺序

需求建议"先接线 → schema → 检索 → 前端"。**审核不完全同意**，建议加一个步骤 0：

| 顺序 | 内容 | 为什么 |
|---|---|---|
| **0** | **证据分流 + 画像 prompt 去风险化** | 若先接线，会把画像里越界的风险结论放大到 4 个下游；且分流改动很小（按已有 `evidence_scope` 筛选） |
| 1 | 接线：intelligence 传给 Risk / Scenario / Advisor / Chat / Report | 需求的核心目标，改动集中在 payload 与签名 |
| 2 | Schema 升级：足迹表 / 供应链角色 / 缺口优先级 / EvidenceReferences | 结构稳定后下游才能用 |
| 3 | 前端渲染 + 报告章节 | 面向用户可见 |
| 4 | 三个指定用例回归 | 验收 |

---

## 5. 风险与审核意见

| # | 风险 | 审核意见 |
|---|---|---|
| 1 | `information_gaps` 类型变更是破坏性的 | 用联合类型过渡一版，或同版本同步改前端 + 报告 |
| 2 | prompt token 膨胀 | 用 `intelligence_brief()` 投影，别传全量 |
| 3 | 公司证据太薄（实测 2 vs 9） | 画像阶段若移除政策证据，画像会更薄；公司检索能力（Wikidata / 官网）是**同一批工作的前置依赖**，建议一起排期 |
| 4 | 画像与 Risk 职责重叠 | 步骤 0 必须先做 |
| 5 | 已有存量数据（8 条 assessment） | 兼容策略必须覆盖，否则历史记录读不出来 |
| 6 | 不要重复劳动 | `chat_history` 已进 chat prompt；`evidence_scope` 已存在——这两项**不用再做** |

---

## 6. 明确不做

- 不重构 agent 框架、不新增 agent 节点；
- 不改 API 路由契约（`POST /api/v1/assessments` 等）；
- 不删除 `data_status`（前端与存量数据依赖），只做加法；
- 不引入向量库或新依赖；
- 本次不做跨项目 Company Intelligence 复用。

---

## 7. 粗估工作量

| 步骤 | 估时 |
|---|---|
| 0 证据分流 + 去风险化 prompt | 0.5–1 天 |
| 1 下游接线（5 个函数 + 投影） | 1–1.5 天 |
| 2 Schema + coercion + 兜底 | 1.5–2 天 |
| 3 前端渲染 + 报告 | 1–1.5 天 |
| 4 测试与回归（3 用例） | 1 天 |
| **合计** | **约 5–7 人日** |

---

## 8. 补充审核意见

1. 需求写的"所有下游 agent 显式接收 `company_intelligence`"——建议定义为**必填参数**（不是可选），
   并在 intelligence 阶段降级时用兜底对象顶上，保证下游永远不会拿到 `None`。
2. 核对时发现 `chat_history` 已经加进两个 chat prompt，`evidence_scope` 也已存在。
   需求文档可能比代码状态旧一些，这两项可以划掉。
