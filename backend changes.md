# 后端待改动清单（Backend changes needed）

记录前端已经按 UI.md / profile list.md 实现、但需要后端配合才能完全跑通的点。
先记录、暂不修改，后续统一处理。每条都标注了现状、影响和建议方案。

---

## P0 — 阻塞真实流程

### 1. CORS 白名单太窄
**现状**：`main.py` 中 `allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]`。
**影响**：前端从独立端口预览（例如 8123）或部署到域名后，浏览器会直接拦截所有 API 请求。
**建议**：改为可配置列表，例如读取环境变量 `CORS_ORIGINS`（逗号分隔），默认保留本地开发地址。

### 2. 证据原文无法在页面内打开
**现状**：`RetrievedEvidence` 只有 `url` 与 `document_path`，没有对外可访问的文档路由。
**影响**：UI.md 要求"点击证据可以看到数据库或网页原文、PDF 之类的文档"，目前前端只能展示检索到的文本片段 + 外链（没有 URL 时就只能说明不可用）。
**建议**：新增 `GET /api/v1/evidence/{evidence_id}/document`，返回 data 分支 raw 中的 PDF/HTML（或对 web 来源做代理），并在证据对象里补一个可直接使用的 `document_url` 字段。

### 3. `restrictions` 枚举缺三项
**现状**：`CompanyInput.restrictions` 仅支持 `tariff_pressure / export_controls / sanctions_concerns / local_regulation / supplier_dependency / labor_cost_increase / logistics_problems / none`。
**影响**：profile list.md 要求的 `Geopolitical uncertainty`、`Market access`、`Capacity expansion` 三个选项后端没有对应值，前端只能塞进 `notes` 传递，检索层收不到这些信号。
**建议**：枚举补上 `geopolitical_uncertainty`、`market_access`、`capacity_expansion`（并考虑是否加 `other`）。

### 4. `target_markets` 没有 ASEAN
**现状**：`CountryCode` 为 `CN/VN/ID/IN/TH/MY/MX/US/EU`。
**影响**：profile list.md 的目标市场选项里有 ASEAN，前端只能丢弃并写入 notes。
**建议**：`CountryCode` 增加 `ASEAN`，或提供 region → 成员国映射。

### 5. `decision_question` 由必填改为可选
**现状**：`CompanyInput.decision_question: str = Field(min_length=5)`。
**影响**：profile list.md 已注明该自由输入框"不应该必填"。前端目前用所选预设拼出字符串兜底（如 `Relocate production (Vietnam)`），语义上不够干净。
**建议**：允许为空；或新增结构化字段 `decision_type` / `destination_country`，由后端拼装问题文本。

### 6. mock 模式下仍强制 `api_key`
**现状**：`AssessmentRequest.api_key: str = Field(min_length=10)` 为必填。
**影响**：`LLM_PROVIDER=mock` 时其实不需要任何 Key，但前端仍必须传一个 ≥10 字符的占位串。
**建议**：改为 `str | None = None`，仅在 deepseek 模式下校验。

### 7. 生产占比强制等于 100
**现状**：`validate_production_share` 要求 `sum(production_share) == 100`。
**影响**：profile list.md 明确"总和不等于 100% 时提示，但不强制"。前端现在遇到非 100% 只能回退到本地预览，真实 Agent 跑不起来。
**建议**：放宽为 `<= 100` 或接受任意占比，由后端标注/归一化缺失部分。

---

## P1 — 情景页与聊天页需要

### 8. 情景对象字段与 UI.md 约定不一致
**现状**：`ScenarioResult` 用 `cost_score / resilience_score / geopolitical_risk_score / market_access_score / implementation_score / weighted_score`。
**影响**：UI.md 约定 `overall_score` + `confidence` + `scores{cost,resilience,geopolitical_risk,market_access,feasibility}`，且要求每个情景带 Confidence 与依据。目前没有 per-scenario confidence，前端按证据条数与数据模式推导（已实现，但属于前端兜底）。
**建议**：响应里补 `confidence`、`confidence_reasons`，字段名对齐 UI.md（或在 schema 里加别名）。

### 9. 风险分类未标准化
**现状**：`RiskItem.category` 是模型自由文本（可能是中文）。
**影响**：UI.md 的风险雷达固定六类（Trade / Political / Supply chain / Regulation / Market access / Operational），前端只能用关键词匹配归类，跨语言/同义表述时容易归错。
**建议**：`category` 改成固定枚举 + 可读 label 返回。

### 10. 缺少"情景重跑"接口
**现状**：只有创建评估（`POST /api/v1/assessments`）时才会产出 scenarios。
**影响**：UI.md 聊天页的 "Update Scenario Analysis" 需要"带着对话中新信息重跑情景"，目前无法只重跑情景而不重跑整条链路。
**建议**：`POST /api/v1/assessments/{id}/scenarios`，可带 `updated_constraints` / `new_preferences`。

### 11. 聊天接口返回结构太粗
**现状**：`POST /api/v1/assessments/{id}/chat` 只返回更新后的整个 `Assessment`。
**影响**：UI.md 聊天页期望 `message / context_update{new_constraints,new_preferences} / scenario_update_required / updated_analysis`，前端无法据此自动刷新左侧上下文面板、判断是否需要重跑情景。
**建议**：在响应中增加结构化字段（例如 `chat_analysis`）。

### 12. 没有文件上传接口
**现状**：无接收接口；表单和聊天页的上传入口只能在前端列出文件名。
**影响**：UI.md 的 "Supporting Documents"、"Add Information → File Upload" 都无法真正进入知识库参与检索。
**建议**：`POST /api/v1/documents`（multipart）→ 解析、切片、入库，返回 `document_id` 供证据引用。

### 13. 最终报告缺少对话洞见
**现状**：`GET /api/v1/assessments/{id}/report` 只基于 `Assessment` 生成。
**影响**：UI.md 要求最终报告包含 Consultation Insights（对话中形成的新约束、偏好与最终判断）。
**建议**：报告生成时汇总 `chat_history`，或在生成前允许提交最终决策摘要。

---

## P2 — 一致性与可解释性

### 14. `probability` 字段与 UI 规范冲突
**现状**：`RiskItem.probability`（0–100 整数）会随风险一起返回。
**影响**：UI.md 明确"不要出现无依据的数字精确度（0–100 风险分数）"，前端目前选择不展示。
**建议**：保留但标注为内部字段，或改为定性 `level`。

### 15. 返回文案语言不统一
**现状**：`trace`、`limitations` 等字段是中文，前端整体界面是英文。
**影响**：初始评估页的"评估过程/不确定性"区块中英混排。
**建议**：统一为英文，或返回 i18n 结构；也可在 README 里明确"后端文案为中文、前端展示层负责措辞"。

### 16. `recommendation` 在初始评估页暂未展示
**现状**：`recommendation.headline / rationale / next_actions` 已返回。
**影响**：按 UI.md 的页面分工，建议内容放在情景页与最终报告，初始评估页只做风险诊断，因此前端暂存未用。
**建议**：无需改动，仅记录；若产品希望评估页也给一句初步建议，可直接复用该字段。

### 17. industry 固定值
**现状**：前端固定传 `industry="battery_ev"`（产品聚焦 EV/电池赛道），因为 profile list.md 的表单里已无 industry 字段。
**影响**：后端若将来要支持多行业，`industry` 枚举需要放宽或允许 `other`。
**建议**：无需改动，记录约定即可。

### 18. 生成内容不支持语言参数（多语言界面）
**现状**：前端已实现中英文切换（英文/中文两套界面文案），但 Agent 生成的内容没有语言参数：`analyze_risks` / `simulate_scenarios` / `generate_recommendation` / `answer_chat` 的 prompt 未指定输出语言，`trace`、`limitations` 等字段目前是中文，模型回复可能是英文。
**影响**：界面切成中文后，风险名称、风险描述、情景收益/风险、聊天回复、建议文案仍是混合语言，体验割裂。
**建议**：`AssessmentRequest` / `ChatRequest` 增加 `language: "en" | "zh"`，在 prompt 中显式要求按该语言输出；报告 PDF 同样支持（`build_assessment_pdf` 目前混用中英文字体与标题）。

### 19. 决策项目只存在浏览器本地
**现状**：My Decisions 的项目列表存在前端 `localStorage`（最多 20 条），后端没有项目存储接口。
**影响**：换设备或清缓存后项目丢失；无法实现 UI.md 里"Sign in / 跨设备历史同步"的路线图项。
**建议**：`GET/POST /api/v1/projects`（或复用 assessments 列表接口），把 `assessment_id` 与用户关联。

### 20. 情景页的评分口径需与前端约定一致
**现状**：`ScenarioResult.weighted_score` 是后端按优先级加权后的综合分（0–100），前端直接展示为 "Overall score"；五个维度来自五个 `*_score` 字段。
**影响**：UI.md 情景页要求"综合分不是简单平均，要考虑用户优先级"，目前实现一致；但没有任何字段说明加权过程。
**建议**：返回 `weighting` 或 `score_breakdown`（各维度权重与贡献），前端即可展示"为什么是这个分数"，而不是只写一句按优先级加权。

### 21. 报告版本管理
**现状**：`GET /api/v1/assessments/{id}/report` 每次按当时的 Assessment 生成 PDF，没有版本概念；前端现在只在项目上存一个 `report_id` / `report_url`。
**影响**：UI.md §11 明确要求"用户回到咨询改动分析后重新生成报告，不应静默覆盖旧版本，应视为 Report v1 / v2，最新一版标记为当前版本"。
**建议**：报告产物带上 `report_version` 与 `generated_at` 列表（例如 `Assessment.reports[]`），并保留历史版本可下载。

### 22. 最终报告的内容规格（详实度、字数、证据引用）
**来源**：用户明确要求 + UI.md《Final Decision Report Page》§4、§7。
**现状**：`build_assessment_pdf` 只按 `Assessment` 生成一份较短的 PDF，章节偏提纲式，不读 `chat_history`（缺少 Consultation Insights 一节），也没有逐条证据引用、字数下限和版本号。
**要求**：
1. **内容详实丰富，字数不得过少**——不能是条目罗列。建议给每章设最低内容量：执行摘要 ≥ 300 字；公司画像 / 当前供应链情况 / 关键风险评估 / 情景比较 各 ≥ 400 字；咨询洞见 ≥ 300 字；最终决策与建议 ≥ 400 字；证据与不确定性 ≥ 200 字；正文合计 ≥ 3000 字（中文按字数、英文按词数折算）。
2. **必须附证据**——每条重要结论后附证据引用：证据编号、标题、发布方、发布日期、权威等级，且可回溯到 Evidence 库（指向原始文件或网页）。
3. **固定九章**：Executive Summary / Company Profile / Current Supply Chain Situation / Key Risk Assessment / Scenario Comparison / Consultation Insights / Final Decision or Recommendation / Evidence Sources / Uncertainties & Limitations。
4. **必须包含咨询洞见**——把 `chat_history` 中新增的约束、偏好、上传文档，以及它们如何改变结论，写进 Consultation Insights 一节。
5. **首页元数据**——报告标题、决策项目名、生成时间、版本号。
6. **语言**——按 #18 的语言参数输出。
7. **版本**——每次重新生成产生新版本、不覆盖旧版（见 #21）。

---

## 状态更新（2026-10-01，backend 分支 `9aae132` / frontend 分支 `74de556`）

已实现并本地联调通过：

- **#1 CORS 可配置**：`CORS_ORIGINS`（逗号分隔）+ `CORS_ORIGIN_REGEX`，默认放行 localhost / 127.0.0.1 / 私有网段任意端口；实测 `Origin: http://127.0.0.1:8123` 预检通过。
- **#2 证据原文接口**：新增 `GET /api/v1/evidence/{evidence_id}/document`（本地文件直出、仅有网页来源时 307 跳转），`RetrievedEvidence` 增加 `document_url`；前端优先使用该字段。
- **#3 restrictions 枚举**：补 `geopolitical_uncertainty` / `market_access` / `capacity_expansion` / `other`。
- **#4 ASEAN**：`CountryCode` 增加 `ASEAN`（后端与前端同步）。
- **#5 decision_question 选填**：允许空串，profile 摘要自动回退到通用描述。
- **#6 mock 模式不再强制 api_key**：`AssessmentRequest.api_key` 改为可选，仅 deepseek 模式校验。
- **#7 生产占比不再强制 100**：只拒绝 >100；前端同步放宽（不再因为占比不足 100% 退化为预览）。
- **#8 情景置信度**：`ScenarioResult` 增加 `confidence` / `confidence_reasons`，按关联证据的权威等级推导。
- **#9 风险分类标准化**：`RiskItem.category_key` 输出固定六类，前端雷达优先使用它。
- **#10 情景重跑接口**：新增 `POST /api/v1/assessments/{id}/scenarios`，复用画像与证据，只重跑情景与建议，并把咨询新增约束并入公司 notes。
- **#11 聊天结构化返回**：`Assessment.chat_analysis`（new_constraints / new_preferences / scenario_update_required / summary）。
- **#13/#22 报告增强（部分）**：PDF 增加 Company profile、Scenario detail（收益/风险/假设/置信度）、Consultation insights（读取 chat_history）、Evidence sources，章节标题随 `language` 切换中英。
- **#18 语言参数**：`AssessmentRequest.language` / `ChatRequest.language`（en/zh），贯穿各阶段 prompt；`Assessment.language` 回传。
- **#20 权重可解释**：`Assessment.scoring` 返回各维度权重。
- 另：后端在没有 `frontend/` 目录的分支上也能启动（`/` 返回服务信息），避免与前端分支强耦合。

仍待处理：

- **#12 文件上传接口**（前端目前只在会话内列出文件）。
- **#14 probability 表述**、**#15 规则兜底文案仅有中文**（LLM 路径已按语言输出，但 mock/heuristic 文本仍是中文）。
- **#16**、**#17** 仅记录，无需改动。
- **#19 决策项目后端存储**（当前仍在浏览器 localStorage）。
- **#21 报告版本管理**（前端已按版本号展示，后端未留存历史版本）。
- **#22 报告“字数不得过少”**：目前是模板化扩充（约 4 页），要达到每章几百字、全文数千字的详实度，需要让 LLM 生成正文而不是拼接模板。
