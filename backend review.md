# 后端 Review 清单（Backend review checklist）

**审查对象**：`origin/backend` @ `cb684fd`（含 `2d30586`）
**审查日期**：2026-10-03
**审查方式**：本地真实运行一次完整评估，不用 mock、不猜代码

测试环境：

| 项目 | 值 |
|---|---|
| LLM | 真实 DeepSeek（`LLM_PROVIDER=deepseek`，`LLM_REQUIRED=true`） |
| 知识库 | 本地 RAG，28 篇文档 / 5931 chunks |
| 测试用例 | CATL，电池 EV，生产布局 CN 80% + EU 20%，目标市场 CN/US/EU |
| 结果 | HTTP 200，耗时 125 秒，`degraded=false`，5 个 LLM 阶段全部 `ok=true` |

**总体结论**：Phase 1（打通真实 LLM 与可观测性）确实完成了，这是本次最大的进步。
新增的 `EntityAgent` + `CompanyResearchTool` 方向完全正确，但目前**联网研究实际没生效**，
证据仍然 100% 来自本地 RAG，且证据绑定存在硬伤。下面 4 条 S0 建议优先修。

---

## 实测到的正向变化（先记录，避免误删）

- `model_mode=deepseek`、`degraded=false`，`llm_calls` 每个阶段都有 `ok / attempts / latency_ms`，
  失败会被显式标记为 `fallback` 并写入 `degraded_stages`——"静默伪装成成功"的问题已解决。
- `/health` 返回 `llm_provider` 和 `model`；`/api/v1/meta` 增加 `llm_configured` / `llm_required`；
  `api_key_required` 已改为"服务端有 Key 时不需要浏览器传 Key"。
- 配置改为 fail-fast：`LLM_PROVIDER=deepseek` 但缺 Key 会直接启动失败，不再静默降级。
- 移动端结构扩展到位：`CompanyEntity`、`FactItem`（`fact_id/confidence/as_of/derived_from/conflict`）、
  `market_position`、`executive_summary`、`LLMCallRecord`。
- Intelligence prompt 已要求四段式 Strategic Context、禁止"检索到 N 条资料"这类伪事实、
  并列出禁止猜测的信息类型。

---

## 🔴 S0-1　安全：真实 API Key 已提交到公开仓库

**位置**：仓库根目录 `.env`（commit `2d30586`）

**现象**：`.env` 被跟踪提交，内容包含真实可用的 DeepSeek Key（此处已打码）：

```
LLM_PROVIDER=deepseek
LLM_REQUIRED=true
DEEPSEEK_API_KEY=sk-****（真实值，已泄露）
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
WEB_SEARCH_ENABLED=false
```

根目录 `.gitignore` 虽然写了 `.env`，但该文件**已经被 Git 跟踪**，ignore 规则对已跟踪文件无效。

**影响**：任何能访问该仓库的人都可以取走这把 Key 并盗刷额度。

**修复**：

1. **立刻去 DeepSeek 控制台吊销并重新生成 Key**（最优先，改代码救不回已泄露的 Key）；
2. `git rm --cached .env` 停止跟踪；
3. 用 `git filter-repo`（或 BFG）清理历史——只做第 2 步的话，旧 commit 里仍能翻出 Key；
4. 提交一份 `.env.example` 放占位值，真实 `.env` 只保留在本地。

---

## 🔴 S0-2　公司研究被 403 拦死，联网研究返回 0 条

**位置**：`backend/app/company_research.py` 第 **77、119、219、257、302** 行

**现象**：5 处都写死同一个 User-Agent：

```python
headers={"User-Agent": "LocusCompanyResearch/1.0"}
```

Wikimedia 的机器人策略要求 UA 中带可联系的网址或邮箱，否则直接 403。实测对照：

| User-Agent | 结果 |
|---|---|
| `LocusCompanyResearch/1.0`（当前代码） | **403** `Please respect our robot policy` |
| 浏览器 UA | **403** |
| `LocusBot/1.0 (https://example.org; contact@example.org)` | **200** ✅ |

**实测证据**：直接调用 `CompanyResearchTool().search(company, aliases=['CATL','宁德时代'])`
→ `elapsed 3.7s  items=0`。网络本身正常（`example.com` 200、DeepSeek 正常），因此不是网络问题。

**影响**（本条最严重）：

- `EntityAgent` 拿不到任何实体信息：`entity.legal_name` 回显、`aliases` 只有 `["CATL"]`、
  `headquarters` / `listing` / `founded_year` / `size` 全空、`source_ids` 为空；
- Wikipedia 与官网抓取依赖 Wikidata 返回的实体 → Wikidata 挂了，后两步一起不执行；
- 最终 7 条证据的 `evidence_scope` **全是 `policy`，没有一条 `company`**。

**修复**：把 5 处 UA 抽成一个模块级常量，统一改成带联系方式的规范格式（如
`LocusBot/1.0 (https://<项目地址>; <联系邮箱>)`），避免散落 5 处各自维护。

---

## 🔴 S0-3　行业过滤形同虚设：光伏证据仍在污染电池企业

**位置**：`backend/app/retrieval.py` 第 **317–340** 行

**现象**：新增的电池/光伏过滤逻辑：

```python
battery_terms = (..., "cell", ..., "ev", ...)
solar_terms   = ("photovoltaic", "solar cell", "solar panel", "silicon wafer")
if any(term in text for term in solar_terms) and not any(term in text for term in battery_terms):
    continue
```

问题在于 `"cell"` 和 `"ev"` 用的是**裸子串匹配**。以本次被错误选中的
`EVD-DOC_001-C0070`（晶硅光伏反规避裁决）为例，其正文实测统计：

| 词 | 出现次数 | 实际语境 |
|---|---|---|
| `solar` | 2 | ✅ 确属光伏 |
| `photovoltaic` | 1 | ✅ 确属光伏 |
| `cell` | 2 | ❌ 是 `solar cells`，不是电池电芯 |
| `battery` | 0 | — |

因为 `"cell" in "solar cells"` 成立，`battery_terms` 命中，于是该光伏文档**不满足跳过条件**，
被当作电池行业的证据放行。同理 `"ev"` 会命中 `every / level / development / revenue / several`，
等于没有过滤。

**影响**：CATL 的 `supply_chain` / `market_position` 事实中出现"美国对东南亚四国光伏产品反规避认定"，
用户会直接看到与自身业务无关的证据。

**修复**：

1. 用词边界匹配替代子串匹配：`\bcell(s)?\b`、`\bev\b`；
2. 更彻底：把 `cell`、`ev` 这类高歧义词移出 `battery_terms`，改用组合词
   （`battery cell` / `lithium-ion cell` / `electric vehicle` / `EV battery`）；
3. 建议加硬规则：命中 `solar` / `photovoltaic` 且**未**命中 `battery` / `lithium` 组合词 → 直接剔除。

---

## 🔴 S0-4　"缺证据就挂前两条"的兜底仍在，导致证据绑定不可靠

**位置**：`backend/app/agent.py` 第 **778、813、845、882** 行

**现象**：这几处仍然是：

```python
if not evidence_ids:
    evidence_ids = [item.evidence_id for item in evidence[:2]]
```

**影响**：模型未给出 `evidence_ids` 时，系统会把检索结果的**前两条无条件挂上去**，
于是每条风险/情景看起来都"有证据支撑"，实际是随机挂的。本次 CATL 的 7 条风险
全部标记为 `verification_status=verified`，但其中相当一部分引用的正是上面那条光伏裁决。

**修复**：

1. 删除这 4 处兜底；
2. 改为：无合格证据 → `evidence_ids=[]` + `verification_status="unverified"`
   + 新增 `insufficient_evidence=true`，并在前端与报告中如实标注"证据不足"；
3. 挂证据前做一次相关性校验（topic / `category_key` 与证据 topic 有交集，且 `relevance_score` 过阈值）。

> S0-3 与 S0-4 必须一起修，"每条风险都有支撑"这句话才成立。

---

## 🟠 P1-5　`data_mode` 标签失真，无法用来判断是否联网

**位置**：`backend/app/agent.py` 第 **213** 行

```python
data_mode = "mock" if all(item.is_mock for item in evidence) else "hybrid"
```

**现象**：只要不是 mock 就写 `hybrid`。本次 7 条证据**全部来自本地 RAG、零条联网**，
但 `data_mode` 报的是 `hybrid`，前端因此显示成"联网分析"。
另外当 `evidence` 为空时 `all([])` 为 True，会误报为 `mock`。

**修复**：按 `evidence_scope` / `source_type` 真实统计，例如
`rag_only` / `company_research` / `web` / `mixed`，或直接返回各类来源的条数。

---

## 🟠 P1-6　嵌套对象被塞进字符串字段，前端显示原始字典

**位置**：`backend/app/agent.py` `_coerce_intelligence`（第 **1358** 行起）

**现象**：模型把 `strategic_context` 输出为对象 `{"narrative": "..."}`、
把 `information_gaps` 输出为对象 `{"fact_id": "IG-001", "fact": "..."}`，
而 schema 中 `FactItem.fact` 与 `information_gaps` 均为字符串，于是被 `str()` 转成 Python 字典文本：

```
strategic_context[0].fact = "Current Position: {'narrative': 'CATL is a China-headquartered..."
information_gaps[0]       = "{'fact_id': 'IG-001', 'fact': 'Production capacity and capacity utilization..."
```

**影响**：Company Profile 页面会把 `{'narrative': ...}` 原样显示给用户，观感很差。

**修复**：在 coercion 中解包（优先取 `narrative` / `fact` / `text` 等已知键），
同时在 prompt 中明确这两个字段必须是纯字符串，并补一个单测锁住输出形状。

---

## 🟠 P1-7　Consultation 仍然没有对话记忆

**位置**：`backend/app/llm.py` `answer_chat()`（第 **450** 行）；`choose_chat_action()`

**现象**：payload 只有 `company_profile`、`current_assessment{risks,scenarios,recommendation}`、
`existing_evidence`、`supplemental_evidence`、`user_message`。
在 `llm.py` 中 grep `chat_history` **无任何结果**。

**影响**：每轮追问都是"失忆"的，第二轮提到的信息模型看不到第一轮说过什么。

**修复**：把最近 6–10 轮 `chat_history` 拼入 payload（超长时保留首轮 + 最近 N 轮并摘要中间部分），
`choose_chat_action()` 同步。

---

## 🟠 P1-8　Risk / Scenario 缺 rubric，评分仍自由发挥

**位置**：`backend/app/llm.py`（`analyze_risks` / `simulate_scenarios`）、
`backend/app/schemas.py`（`RiskItem.probability` 第 **162** 行）

**现象**：全代码 grep 不到 `band` / `rubric` / `score_breakdown` / `likelihood`。
风险仍返回 `probability: int (0–100)`；情景五个维度仍由模型直接给 0–100 整数，
没有档位、没有锚点、没有"为什么是这个分"的说明。

**影响**：风险等级与概率不可比、不可复核；情景分数无法解释，用户看不到"凭什么是 73 分"。

**修复**：

1. 风险：把面向用户的 `probability` 换成 ordinal `likelihood`（very_low…very_high）+ `basis`；
   增加 severity 判级规则（例如 critical 需至少 1 条 S/A+ 证据）；
2. 情景：模型只输出**档位 + 理由 + 证据**，由后端映射为 0–100 并计算加权分，
   同时返回 `score_breakdown`（各维度权重与贡献）。

---

## 🟠 P1-9　后端已不需要浏览器 Key，但前端仍卡在这个门上

**位置**：`backend/app/main.py` 第 **154** 行；`frontend/app.js` 第 **588、1204** 行；
`frontend/index.html` 第 **410–412** 行

**现象**：后端已改为服务端持 Key（`api_key_required` 在服务端有 Key 时为 `false`），
但前端仍是：

```js
const configured = Boolean(window.LOCUS_API_BASE && window.LOCUS_API_KEY);
```

`runAnalysis` 与 `checkAgentConnection` 都要求两者**同时为真**；
而 `index.html` 中这两个全局变量仍在 HTML 注释内，本次只是把占位符改成了空串，
结果是页面永远停在 preview 模式。

**修复**：前端改为只判断 `LOCUS_API_BASE`，`LOCUS_API_KEY` 变为可选；
并把全局变量从注释中移出（或单独提供 `config.js`）。

---

## 🟡 P2-10　报告仍是模板拼装，且没有版本

**位置**：`backend/app/pdf_report.py`

**现象**：报告完全由 Python 表格/段落拼装，没有任何 LLM 生成环节，章节偏提纲式；
后端没有报告版本概念（前端的 `report_versions` 只是浏览器本地记录）。

**修复**：Assessment → LLM 生成长文正文（章节化、带 `EVID-` 引用）→
引用与数字白名单校验 → 交给现有 renderer 排版；后端增加 `report_versions`。

---

## 🟡 P2-11　决策项目与文件上传仍未落地

- 决策项目里的 `DP-xxx` 完全由浏览器 localStorage 生成，后端没有对应资源，换设备即丢失；
  且前端存在 `DP-` 与后端 `ASM-` 两套 ID 并存的问题。
- 表单与聊天中的 "Supporting Documents" 只在前端列出文件名，没有上传接口，
  文件从未进入知识库参与检索。

---

## 建议修复顺序

| 顺序 | 事项 | 理由 |
|---|---|---|
| 1 | S0-1 吊销 Key | 唯一有时效性的一条 |
| 2 | S0-2 修 UA | 成本最低、收益最直观，立刻能看到公司研究生效 |
| 3 | S0-3 + S0-4 行业过滤 + 删除证据兜底 | 决定证据是否可信 |
| 4 | P1-6 字典解包 | 前端观感立刻恢复正常 |
| 5 | P1-5 `data_mode`、P1-9 前端门控 | 联调体验 |
| 6 | P1-7 对话记忆 | 咨询能力 |
| 7 | P1-8 rubric | 评分可解释 |
| 8 | P2-10 / P2-11 | 报告与持久化 |

---

## 复跑验收清单

修完后重新跑一次完整评估，逐条确认：

- [ ] `evidence_scope` 中出现 `company`，不再全是 `policy`
- [ ] `entity.aliases` 含多个别名（中英文），`headquarters` / `listing` 等有值
- [ ] 证据中不再出现 `solar` / `photovoltaic`（电池行业场景下）
- [ ] 不再出现由 `evidence[:2]` 兜底产生的引用；无证据的风险标为 `insufficient_evidence`
- [ ] `strategic_context[].fact` 与 `information_gaps[]` 是纯文本，不是字典字面量
- [ ] `data_mode` 能真实反映来源构成
- [ ] 连续两轮对话，第二轮能正确引用第一轮提供的信息
- [ ] 情景返回 `score_breakdown`，风险不再输出 0–100 概率

---

## 附：一条经验

本次两个最严重的功能问题（S0-2 的 403、S0-3 的 `"cell"` 子串误匹配）都属于
**"代码看起来实现了，实际没生效"**。建议为这类外部依赖与过滤逻辑补上最小回归测试：

- 一条真实调用 `CompanyResearchTool` 的测试（无网络时 skip）；
- 一条"光伏文本不得通过电池行业过滤"的单元测试。

这样下次改动可以直接被测试拦住，而不用靠人工复跑 125 秒的完整评估。
