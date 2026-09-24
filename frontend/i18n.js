/* Language switcher: English / 中文.

   Translations are keyed by the English UI string, so the app markup needs no
   extra attributes: any text node (static markup or content rendered later)
   whose trimmed text matches a key is swapped when Chinese is active, and the
   original is restored when switching back.

   Content produced by the Agent (risk names, evidence titles, model replies)
   is intentionally left in its own language — translating that needs the
   backend change recorded in backend changes.md. */

const ZH_TEXT = {
  /* shell */
  "AI Supply Chain Relocation Decision Agent": "AI 供应链迁移决策助手",
  "My Decision": "我的决策",
  "Start New Decision": "开始新决策",
  "Home Page": "主页",
  "News": "资讯",
  "My decisions": "我的决策",
  "Decision projects": "决策项目",
  "Every completed consultation is kept here as a decision project, together with the company profile and risk assessment the Agent produced.": "每次完成的咨询都会作为一个决策项目保留在这里，包含 Agent 生成的企业画像与风险评估。",
  "No decision projects yet. Complete a consultation and the Agent stores the company profile here.": "还没有决策项目。完成一次咨询后，Agent 会在这里保存企业画像。",
  "Start new decision": "开始新决策",
  "Open assessment": "查看评估",
  "Relevant policy signals, soon.": "相关政策信号，敬请期待。",
  "News monitoring is reserved for a future release and does not interrupt your decision workflow.": "资讯监测是后续版本的功能，不会打断你的决策流程。",

  /* home */
  "Evaluate supply chain strategies under geopolitical uncertainty.": "在地缘政治不确定性下评估供应链策略。",
  "Evidence-led": "证据驱动",
  "Scenario-based": "情景推演",
  "Decision-ready": "可决策",
  "Build a company profile": "建立企业画像",
  "Capture your production footprint, markets and decision context in one place.": "在一处记录你的生产布局、目标市场与决策背景。",
  "Assess risks with evidence": "基于证据评估风险",
  "Connect policy, supply-chain and market signals to the decision at hand.": "把政策、供应链与市场信号接到当前决策上。",
  "Compare strategic options": "比较战略选项",
  "See the trade-offs across relocation, expansion and diversified production paths.": "看清迁移、扩产与多元化布局之间的取舍。",
  "Core supply": "核心供应",
  "Production": "生产基地",
  "Market access": "市场准入",
  "Policy signal detected": "检测到政策信号",
  "Review": "查看",
  "Live footprint": "实时布局",
  "03 locations": "3 个生产基地",

  /* form */
  "New decision": "新决策",
  "Tell us about your decision.": "告诉我们你的决策。",
  "Start with what you know. You can refine it with the AI consultant later.": "先填写已知信息，之后可以和 AI 顾问继续完善。",
  "Decision profile completion": "决策画像完成度",
  "Draft saves automatically as you type": "输入时自动保存草稿",
  "Autosave unavailable in this browser": "此浏览器无法自动保存草稿",
  "Decision profile": "决策画像",
  "Company context": "公司情况",
  "Footprint & markets": "产能与市场",
  "Decision context": "决策背景",
  "Review assessment": "查看评估",
  "Information is used only to prepare this decision assessment.": "这些信息仅用于生成本次决策评估。",
  "Quick assessment": "快速评估",
  "Build your decision profile": "建立你的决策画像",
  "5–8 min": "5–8 分钟",
  "Give Locus a clear picture of your business, footprint and decision. Fields marked * are required.": "把企业、生产布局与决策信息告诉 Locus。带 * 的为必填项。",
  "01 / COMPANY CONTEXT": "01 / 公司情况",
  "02 / FOOTPRINT & MARKETS": "02 / 产能与市场",
  "03 / DECISION CONTEXT": "03 / 决策背景",
  "04 / DEEPER ASSESSMENT": "04 / 深入评估",
  "Recommended": "建议填写",
  "Company name": "公司名称",
  "Main product / business": "主要产品 / 业务",
  "Home country": "母国",
  "Be as specific as possible.": "越具体越好。",
  "Automatically detected when possible; please confirm.": "系统会尽量自动识别，请确认。",
  "Current production footprint": "当前生产布局",
  "Select locations and add production share where known. You may select Not sure.": "选择生产基地，已知的填写占比，也可以选择“不确定”。",
  "Main target markets": "主要目标市场",
  "Select markets and add market share where known. You may select Not sure.": "选择目标市场，已知的填写占比，也可以选择“不确定”。",
  "+ Add production location": "+ 添加生产基地",
  "+ Add target market": "+ 添加目标市场",
  "What decision are you trying to make?": "你想解决什么决策？",
  "Potential destination country / region": "可能的目的地国家 / 地区",
  "Preferred candidate countries / regions": "偏好的候选国家 / 地区",
  "Other decision": "其他决策",
  "Optional — describe the decision in your own words": "选填 — 用你自己的话描述这个决策",
  "Not required. Add detail here only if it helps — the option above already defines the decision.": "非必填。只有当补充说明有帮助时才需要填写，上面的选项已经定义了决策类型。",
  "What is driving this decision now?": "现在推动这个决策的因素是什么？",
  "Other current concern": "其他当前顾虑",
  "One-line supplement": "一句话补充",
  "What is the approximate investment budget for this decision?": "这次决策大概的投资预算是多少？",
  "When does this decision need to be implemented?": "这个决策需要什么时候落地？",
  "One-line situation summary": "一句话情况概述",
  "Supporting documents": "支撑文件",
  "Drag files here or browse. Annual reports, supply chain data, supplier lists, factory information, internal risk assessments.": "把文件拖到这里，或点击浏览。年报、供应链数据、供应商清单、工厂信息、内部风险评估都可以。",
  "Browse files": "浏览文件",
  "More context, stronger recommendation.": "信息越充分，建议越具体。",
  "Hide details ↑": "收起详情 ↑",
  "Add more information for a deeper assessment": "补充更多信息以获得更深入的评估",
  "Improve the depth of the recommendation": "提升建议的深度",
  "Your assessment will show evidence and uncertainty clearly.": "评估结果会清楚标注证据与不确定性。",
  "Analyze decision": "开始分析",
  "Pick the closest 10% band.": "选择最接近的 10% 档位。",
  "Start typing a year — the full list is available.": "直接输入年份即可，下拉列表包含完整年份。",
  "Use 10% steps.": "以 10% 为步长。",
  "No length limit here — the more detail you give, the more specific the assessment becomes.": "这里没有字数限制，写得越详细，评估越有针对性。",
  "Rate what matters most to this decision. Drag a row to reorder — the top row counts most in the scoring.": "为这个决策最看重的因素排序。拖动行即可调整顺序，排在最上面的权重最高。",
  "Factory / site country": "工厂 / 基地所在国",
  "City / region": "城市 / 地区",
  "Production capacity": "产能",
  "Production share": "生产占比",
  "Established year": "建厂年份",
  "Production type": "生产类型",
  "Revenue range": "营收区间",
  "Employee count": "员工人数",
  "Number of factories": "工厂数量",
  "Current capacity utilization (%)": "当前产能利用率（%）",
  "Key supplier dependency": "关键供应商依赖",
  "Do you rely heavily on suppliers from a specific country or region?": "你是否高度依赖某个国家或地区的供应商？",
  "Which critical components, materials, or suppliers are difficult to replace?": "哪些关键零部件、材料或供应商难以替代？",
  "How concentrated are your critical suppliers?": "你的关键供应商集中度如何？",
  "What cannot be easily relocated or changed?": "哪些要素难以迁移或改变？",
  "Investment type": "投资类型",
  "Acceptable cost increase": "可接受的成本上升",
  "Target payback period": "目标回收期",
  "Decision priorities": "决策优先级",
  "What does success look like?": "怎样算成功？",
  "What is non-negotiable?": "什么是不可妥协的？",
  "How willing are you to accept additional uncertainty in exchange for potential cost or strategic benefits?": "为了潜在的成本或战略收益，你愿意承受多少额外不确定性？",
  "Describe the decision situation": "描述决策情境",
  "Not specified": "未指定",

  /* options and values */
  "China": "中国",
  "Vietnam": "越南",
  "Indonesia": "印度尼西亚",
  "India": "印度",
  "Thailand": "泰国",
  "Mexico": "墨西哥",
  "Other": "其他",
  "Not sure": "不确定",
  "United States": "美国",
  "Maintain current production structure": "维持现有生产结构",
  "Expand existing production": "扩展现有产能",
  "Relocate production": "迁移生产",
  "Diversify across multiple countries": "多国分散布局",
  "Establish a new production site": "新建生产基地",
  "Tariff / trade policy changes": "关税 / 贸易政策变化",
  "Geopolitical uncertainty": "地缘政治不确定性",
  "Rising production costs": "生产成本上升",
  "Supplier dependency": "供应商依赖",
  "Market access": "市场准入",
  "Regulatory changes": "监管变化",
  "Capacity expansion": "产能扩张",
  "Own factory": "自有工厂",
  "Joint venture": "合资",
  "Contract manufacturing": "代工",
  "Single-source for critical inputs": "关键投入单一来源",
  "2–3 major suppliers": "2–3 家主要供应商",
  "Multiple diversified suppliers": "多家分散供应商",
  "Existing factories": "现有工厂",
  "Core suppliers": "核心供应商",
  "Skilled workforce": "熟练工人",
  "Patents / technology": "专利 / 技术",
  "Customer certifications": "客户认证",
  "Existing contracts": "现有合同",
  "Infrastructure": "基础设施",
  "Cost ceiling": "成本上限",
  "Customer certification": "客户认证",
  "Political risk": "政治风险",
  "Compliance": "合规",
  "Timeline": "时间表",
  "Lower cost": "成本更低",
  "Higher resilience": "韧性更强",
  "Better market access": "市场准入更好",
  "Faster implementation": "落地更快",
  "Supply Chain Resilience": "供应链韧性",
  "Cost": "成本",
  "Political Stability": "政治稳定性",
  "Implementation Speed": "实施速度",
  "Conservative": "保守",
  "Balanced": "平衡",
  "Aggressive": "激进",

  /* analysis */
  "Locus is working": "Locus 正在工作",
  "Analyzing your supply chain.": "正在分析你的供应链。",
  "We're building a decision view around your footprint, priorities and current exposure.": "我们正在围绕你的生产布局、优先级与当前风险构建决策视图。",
  "Understanding company profile": "理解企业画像",
  "Gathering relevant evidence": "收集相关证据",
  "Assessing geopolitical risks": "评估地缘政治风险",
  "Simulating strategic scenarios": "推演战略情景",
  "Waiting": "等待中",
  "In progress": "进行中",
  "Complete": "已完成",

  /* assessment */
  "Initial assessment": "初步评估",
  "Prepared": "已就绪",
  "Live agent": "实时 Agent",
  "Preview": "预览",
  "Your decision, in context.": "你的决策，放在背景下看。",
  "Export briefing": "导出简报",
  "Back to assessment": "返回评估",
  "View full profile": "查看完整画像",
  "Hide full profile": "收起完整画像",
  "01 / YOUR COMPANY": "01 / 你的公司",
  "02 / EXPOSURE MAP": "02 / 风险分布",
  "03 / WHAT NEEDS ATTENTION": "03 / 需要关注的部分",
  "04 / EXPLAINED, NOT OBSCURED": "04 / 解释清楚，而非黑箱",
  "Company profile": "企业画像",
  "Agent summary": "Agent 摘要",
  "Geopolitical & supply chain risk overview": "地缘政治与供应链风险概览",
  "Qualitative levels — select a category to read the detail": "定性分级 —— 点击类别查看详情",
  "Risk details": "风险详情",
  "Linked to the evidence below": "证据见下方",
  "Decision rationale": "决策依据",
  "View the factors behind this assessment": "查看该评估背后的依据",
  "What Locus considered": "Locus 考虑了哪些因素",
  "Evidence used": "使用的证据",
  "Assumptions": "假设",
  "Confidence and uncertainties": "置信度与不确定性",
  "Uncertainty to keep in view": "需要关注的不确定性",
  "High-severity or unverified findings require human review before capital is committed.": "高严重度或未经验证的结论需要人工复核后才能投入资金。",
  "Supporting evidence": "支撑证据",
  "Uncertainty": "不确定性",
  "No linked evidence for this risk.": "该风险暂无关联证据。",
  "In this assessment": "本页内容",
  "Next step": "下一步",
  "For decision support only. High-risk conclusions require human review.": "仅作为决策支持。高风险结论需要人工复核。",
  "Move from diagnosis to choice": "从诊断走向选择",
  "Ready to compare your strategic options?": "准备比较你的战略选项了吗？",
  "Run a scenario simulation to weigh cost, resilience, market access and implementation trade-offs.": "运行情景推演，比较成本、韧性、市场准入与落地难度之间的取舍。",
  "Run scenario simulation": "运行情景推演",
  "Open original source ↗": "打开原始来源 ↗",
  "Original document is not linked in this preview — raw files live in the": "预览模式下未链接原始文档 —— 原始文件存放在",
  "branch and web sources come from the Agent's search.": "分支，网络来源来自 Agent 检索。",
  "No retrieved text is attached to this source.": "该来源没有附带检索到的原文。",
  "partial": "部分校验",
  "unverified": "未验证",
  "verified": "已校验",
  "High": "高",
  "Medium": "中",
  "Low": "低",
  "Not assessed": "未评估",
  "Trade": "贸易",
  "Political": "政治",
  "Supply chain": "供应链",
  "Regulation": "监管",
  "Operational": "运营",

  /* scenario page */
  "Scenario simulation": "情景推演",
  "Strategic Scenario Analysis": "战略情景分析",
  "ON THIS PAGE": "本页内容",
  "01 / OPTION COMPARISON": "01 / 方案比较",
  "02 / PRELIMINARY REPORT": "02 / 初步报告",
  "Scenario comparison": "情景比较",
  "Overall score is weighted by your stated priorities": "综合评分按你填写的优先级加权",
  "AI-generated assessment based on the company profile, evidence database, risk analysis and your constraints.": "基于企业画像、证据库、风险分析与你的约束条件生成的 AI 评估。",
  "View Analysis": "查看分析",
  "Hide analysis": "收起分析",
  "Recommended": "推荐",
  "Cost impact": "成本影响",
  "Supply resilience": "供应链韧性",
  "Geopolitical risk": "地缘政治风险",
  "Feasibility": "落地可行性",
  "Scenario overview": "情景概述",
  "Potential benefits": "潜在收益",
  "Potential risks": "潜在风险",
  "Key assumptions": "关键假设",
  "Evidence support": "证据支撑",
  "Why this assessment?": "为什么给出这个评估？",
  "Scoring drivers.": "评分驱动因素。",
  "Weighting.": "权重。",
  "Confidence.": "置信度。",
  "Not a forecast.": "这不是预测。",
  "Scores are estimates built from the evidence and assumptions listed above.": "分数是基于上述证据与假设的估计值。",
  "No source is linked to this scenario yet.": "该情景暂无关联来源。",
  "Scores are AI-generated estimates based on available evidence and assumptions. They are not predictions of future outcomes.": "分数是基于现有证据与假设的 AI 估计值，不是对未来的预测。",
  "UPDATED SCENARIO RESULT": "更新后的情景结果",
  "Reason:": "原因：",
  "Initial strategic assessment": "初步战略评估",
  "Sections follow the report outline in UI.md": "章节结构遵循 UI.md 的报告大纲",
  "Executive summary": "执行摘要",
  "Current supply chain overview": "当前供应链概览",
  "Key risks identified": "已识别的关键风险",
  "Evidence & assumptions": "证据与假设",
  "Questions for further analysis": "需要进一步分析的问题",
  "From comparison to decision": "从比较到决策",
  "Want to refine these scenarios?": "想进一步细化这些情景吗？",
  "Continue the consultation to add supplier, cost or customer constraints and update the analysis.": "继续咨询，补充供应商、成本或客户约束，并更新分析。",
  "Continue AI Consultation": "继续 AI 咨询",
  "Back to scenarios": "返回情景页",
  "Updating Scenario Analysis…": "正在更新情景分析…",
  "UPDATING SCENARIO ANALYSIS": "正在更新情景分析",
  "New business constraints": "新的业务约束",
  "Updated risk factors": "更新后的风险因素",
  "Additional evidence": "补充证据",
  "User preferences": "用户偏好",

  /* chat */
  "AI consultation": "AI 咨询",
  "Consultation workspace": "咨询工作区",
  "Current risks": "当前风险",
  "Scenario summary": "情景概览",
  "Updated information": "已补充的信息",
  "Nothing added yet": "尚未补充",
  "No risks recorded": "暂无风险记录",
  "No scenarios yet": "暂无情景",
  "Locus consultant": "Locus 顾问",
  "You": "你",
  "Would you like to update the scenario analysis?": "要现在更新情景分析吗？",
  "Review first": "先看看",
  "Update scenario": "更新情景",
  "ADD INFORMATION": "补充信息",
  "Close": "关闭",
  "Upload a document": "上传文档",
  "Or add information directly": "或直接填写信息",
  "Add supplier information": "补充供应商信息",
  "Add factory information": "补充工厂信息",
  "Update production share": "更新生产占比",
  "Add cost information": "补充成本信息",
  "Add customer requirements": "补充客户要求",
  "Add to consultation": "加入咨询",
  "Ask a question, or add context the consultant should consider…": "提问，或补充顾问需要考虑的背景…",
  "+ Add information": "+ 补充信息",
  "Send": "发送",
  "Update scenario analysis": "更新情景分析",
  "Generate final report": "生成最终报告",
  "Final report": "最终报告",
  "The report will include:": "报告将包含：",
  "Generate final decision report?": "要生成最终决策报告吗？",
  "Cancel": "取消",
  "Confirm and generate": "确认并生成",

  /* validation and toasts */
  "Company name is required.": "请填写公司名称。",
  "Main product / business is required.": "请填写主要产品 / 业务。",
  "Select the decision you are trying to make.": "请选择你想解决的决策。",
  "Add at least one production location.": "请至少添加一个生产基地。",
  "Add at least one target market.": "请至少添加一个目标市场。",
  "Select at least one factor driving this decision.": "请至少选择一个推动该决策的因素。",
  "Complete an assessment first — the consultation builds on it.": "请先完成一次评估，咨询会以此为基础。",
  "Type a message first.": "请先输入内容。",
  "Add a short description before submitting.": "提交前请先写一句描述。",
  "Run the assessment first — scenario options come from the Agent run.": "请先运行评估，情景选项来自 Agent 的分析结果。",
  "The report endpoint needs a live Agent assessment.": "报告接口需要一次真实的 Agent 评估。",
  "Live agent unavailable — showing the local preview.": "无法连接实时 Agent —— 改为展示本地预览。",
  "Documents are attached to this browser session. Ingestion into the knowledge base needs the upload endpoint listed in backend changes.md.": "文档已附在本次浏览器会话中。要进入知识库，需要 backend changes.md 里列出的上传接口。",
};

/* Second pass: labels that are uppercased by CSS, profile grid cells, and the
   preview (mock) analysis content so the demo reads fully in Chinese. */
Object.assign(ZH_TEXT, {
  "AI Supply Chain Relocation": "AI 供应链迁移",
  "Decision Agent": "决策助手",
  "Risk overview": "风险总览",
  "IN THIS ASSESSMENT": "本页内容",
  "Company": "公司",
  "Industry": "行业",
  "Main product": "主要产品",
  "Production footprint": "生产布局",
  "Target markets": "目标市场",
  "Decision drivers": "决策驱动",
  "Decision trigger": "决策驱动",
  "Priorities": "优先级",
  "Investment budget": "投资预算",
  "Planning horizon": "规划期限",
  "Timeline": "时间期限",
  "Review these before any capacity commitment.": "在做产能承诺之前请先审视这些风险。",
  "Worth monitoring through the implementation window.": "在实施周期内值得持续跟踪。",
  "Low severity on the current evidence.": "按现有证据属于低严重度。",
  "No risks identified yet": "暂未识别到风险",
  "Adjust the decision profile and run the assessment again.": "调整决策画像后重新运行评估。",
  "Levels show direction based on available evidence — not a prediction or a legal conclusion.": "风险等级反映的是现有证据下的方向，不是预测，也不是法律结论。",
  "Review before any capacity commitment.": "在做产能承诺前请先审视。",
  "No evidence was attached to this assessment.": "本次评估没有附带证据。",
  "No confidence or uncertainty notes were reported.": "没有报告置信度或不确定性说明。",
  "No specific uncertainties were reported for this assessment.": "本次评估没有报告具体的不确定性。",
  "Key assumptions:": "关键假设：",
  "US tariff exposure": "美国关税风险",
  "Trade-policy exposure": "贸易政策风险",
  "Supplier ecosystem dependency": "供应商生态依赖",
  "Export-control and compliance screening": "出口管制与合规审查",
  "Implementation and capacity ramp-up": "实施与产能爬坡",
  "Changes in US trade policy could materially affect the landed-cost position of products serving this market.": "美国贸易政策的变化可能显著影响面向该市场产品的到岸成本。",
  "Changing trade measures may affect cost, lead time and market access across your current footprint.": "贸易措施变化可能影响你现有布局的成本、交期与市场准入。",
  "The current footprint may depend on supplier capacity, engineering support or critical inputs located outside the production market.": "当前布局可能依赖生产地之外的供应商产能、工程支持或关键投入。",
  "Customer screening, product classification and licence requirements can add lead time or restrict access to specific buyers.": "客户筛查、产品分类与许可要求会增加交期，或限制对特定买家的销售。",
  "Any change to production allocation requires time for qualification, workforce ramp-up and customer certification.": "任何生产分配调整都需要资格认证、人员爬坡与客户认证的时间。",
  "Announced measures can change before implementation, and product-level classifications may differ from the headline policy.": "已公布的措施在落地前可能变化，具体产品的分类也可能与政策口径不同。",
  "Supplier concentration is inferred from your inputs rather than verified bill-of-materials data.": "供应商集中度是根据你的输入推断的，并非经过验证的物料清单数据。",
  "Whether your specific products fall under current control lists is not confirmed by public sources.": "公开来源无法确认你的具体产品是否落在现行管制清单内。",
  "Certification lead times are company specific and are not covered by public sources.": "认证周期因企业而异，公开来源不会覆盖。",
  "Hybrid Diversification": "混合多元化布局",
  "Maintain Current Layout": "维持现有布局",
  "Increase China Production": "提高中国产能占比",
  "Preview only — connect the Agent service for a recommendation.": "当前仅为预览 —— 接入 Agent 服务后会给出建议。",
});

/* Counter-style strings that carry live values. */
const ZH_PATTERNS = [
  [/^Total (.+)$/, "合计 $1"],
  [/^(\d+)% complete$/, "已完成 $1%"],
  [/^· (\d+) \/ (\d+) answered$/, "· 已回答 $1 / $2"],
  [/^Draft saved automatically · (\d{2}:\d{2})$/, "草稿已自动保存 · $1"],
  [/^(\d+) \/ 100 words$/, "$1 / 100 词"],
  [/^Scenario ([A-Z])$/, "情景 $1"],
  [/^Overall score · Confidence: (.+)$/, "综合评分 · 置信度：$1"],
  [/^(\d+) high-priority exposures?$/, "$1 项高优先级风险"],
  [/^(\d+) developing exposures?$/, "$1 项上升中风险"],
  [/^(\d+) monitored exposures?$/, "$1 项低风险"],
  [/^(\d+) message[s]? in this session$/, "本次会话 $1 条消息"],
  [/^(\d+) scenario[s]? compared$/, "已比较 $1 个情景"],
  [/^(\d+) evidence items? retrieved$/, "已检索 $1 条证据"],
  [/^Evidence used: (\d+)$/, "使用的证据：$1"],
  [/^Sources used: (\d+)$/, "使用的来源：$1"],
  [/^(\d+) more items? still need input\.$/, "还有 $1 项需要填写。"],
  [/^Assessment (ASM-\S+)$/, "评估编号 $1"],
  [/^(DEC-\S+) · (.+)$/, "$1 · $2"],
  [/^(.+) operates across (.+), with a decision horizon of (.+)\.$/, "$1 的生产布局为 $2，规划期限为 $3。"],
  [/^(\d+) exposures identified, (\d+) of them high priority — concentrated in (.+)\.$/, "识别出 $1 项风险，其中 $2 项为高优先级 —— 集中在 $3。"],
  [/^The assessment draws on (\d+) retrieved evidence items? \(preview placeholders\)\.$/, "本次评估基于 $1 条检索到的证据（预览占位）。"],
  [/^The assessment draws on (\d+) retrieved evidence items? from the project knowledge base\.$/, "本次评估基于项目知识库中检索到的 $1 条证据。"],
  [/^Reported confidence is (.+), and the findings are flagged for human review\.$/, "报告的置信度为 $1，且结论已标记为需要人工复核。"],
  [/^Reported confidence is (.+)\.$/, "报告的置信度为 $1。"],
  [/^I have reviewed the profile for (.+), the evidence set, the risk assessment and (\d+) scenario options?\.$/, "我已查阅 $1 的企业画像、证据集、风险评估与 $2 个情景方案。"],
  [/^The current leading option is (.+) at (\d+)\/100, with (\d+) high-priority exposures? to manage\.$/, "当前领先方案是 $1，综合分 $2/100，另有 $3 项高优先级风险需要应对。"],
  [/^(\d+) options were compared\. (.+) scores highest at (\d+)\/100, ahead of (.+) \((\d+)\/100\)\.$/, "共比较 $1 个方案，$2 得分最高（$3/100），领先 $4（$5/100）。"],
  [/^Strongest dimension: (.+) \((\d+)\); weakest: (.+) \((\d+)\)\.$/, "最强维度：$1（$2）；最弱维度：$3（$4）。"],
  [/^The overall score is weighted by your stated priorities: (.+)\.$/, "综合评分按你填写的优先级加权：$1。"],
  [/^No priority ranking was provided, so the five dimensions are weighted equally\.$/, "未提供优先级排序，因此五个维度等权。"],
  [/^Production footprint: (.+)$/, "生产布局：$1"],
  [/^Target markets: (.+)$/, "目标市场：$1"],
  [/^Decision: (.+)$/, "决策：$1"],
  [/^Main product: (.+)$/, "主要产品：$1"],
];

const ZH_PLACEHOLDERS = {
  "e.g. Aurora Energy Systems": "例如 Aurora Energy Systems",
  "e.g. Lithium-ion battery cells and modules": "例如锂离子电池电芯与模组",
  "Enter country or region": "输入国家或地区",
  "Enter countries or regions": "输入国家或地区",
  "Describe the decision type": "描述决策类型",
  "Optional — describe the decision in your own words": "选填 — 用你自己的话描述这个决策",
  "Add a short explanation if helpful.": "如有帮助可以补充一句解释。",
  "Enter current concern": "输入当前顾虑",
  "Describe the decision situation in 100 words or fewer.": "用 100 词以内描述决策情境。",
  "Share %": "占比 %",
  "Select or enter year": "选择或输入年份",
  "e.g. We rely on China for cathode materials and precision battery components.": "例如：我们在正极材料与精密电池组件上依赖中国。",
  "e.g. Battery-grade lithium, anode materials and two certified module suppliers are difficult to replace.": "例如：电池级锂、负极材料与两家已认证模组供应商难以替代。",
  "Describe the situation in as much detail as you like — supplier specifics, site constraints, internal context, open questions. There is no length limit.": "尽可能详细地描述情况 —— 供应商细节、基地约束、内部背景、待解问题，没有字数限制。",
  "Ask a question, or add context the consultant should consider…": "提问，或补充顾问需要考虑的背景…",
  "Type the detail the consultant should take into account…": "输入希望顾问纳入考虑的信息…",
  "What decision are you trying to make?": "你想解决什么决策？",
};

const I18N_ATTRS = [["placeholder", "i18nPh"], ["aria-label", "i18nAria"], ["title", "i18nTitle"]];

const i18nState = { lang: "en" };
const i18nNodeOriginal = new WeakMap();

function currentLanguage() {
  return i18nState.lang;
}

function translateString(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  if (ZH_TEXT[text]) return ZH_TEXT[text];
  let candidate = null;
  for (const [pattern, replacement] of ZH_PATTERNS) {
    if (pattern.test(text)) { candidate = text.replace(pattern, replacement); break; }
  }
  // Composed lines (meta rows) mix translated and untranslated fragments.
  if (candidate !== null) return applyFragments(candidate);
  const fragments = applyFragments(text);
  return fragments === text ? null : fragments;
}

const ZH_FRAGMENTS = [
  [/(\d+) evidence items? retrieved/g, "已检索 $1 条证据"],
  [/(\d+) scenarios? compared/g, "已比较 $1 个情景"],
  [/(\d+) messages? in this session/g, "本次会话 $1 条消息"],
  [/Preview assessment/g, "预览评估"],
  [/Preview consultation/g, "预览咨询"],
  [/Agent service not connected/g, "未连接 Agent 服务"],
];

function applyFragments(text) {
  let out = text;
  ZH_FRAGMENTS.forEach(([pattern, replacement]) => { out = out.replace(pattern, replacement); });
  return out;
}

function translateTextNode(node) {
  const raw = node.nodeValue || "";
  if (!raw.trim()) return;
  if (!i18nNodeOriginal.has(node)) {
    if (!translateString(raw)) return;
    i18nNodeOriginal.set(node, raw);
  }
  const original = i18nNodeOriginal.get(node);
  const key = original.trim();
  const value = i18nState.lang === "zh" ? (translateString(key) || key) : key;
  const next = original.replace(key, value);
  if (node.nodeValue !== next) node.nodeValue = next;
}

function i18nWalk(root) {
  if (!root) return;
  if (root.nodeType === 3) { translateTextNode(root); return; }
  if (root.nodeType !== 1) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) translateTextNode(walker.currentNode);
  root.querySelectorAll("[placeholder],[aria-label],[title]").forEach(translateElementAttributes);
  if (root.hasAttribute("placeholder") || root.hasAttribute("aria-label") || root.hasAttribute("title")) translateElementAttributes(root);
}

function translateElementAttributes(element) {
  I18N_ATTRS.forEach(([attr, key]) => {
    const current = element.getAttribute(attr);
    if (current === null) return;
    if (!element.dataset[key]) element.dataset[key] = current;
    const original = element.dataset[key];
    const translated = i18nState.lang === "zh" ? (ZH_PLACEHOLDERS[original] || translateString(original) || original) : original;
    if (current !== translated) element.setAttribute(attr, translated);
  });
}

function updateLanguageToggle() {
  const button = document.getElementById("lang-toggle");
  if (!button) return;
  button.textContent = i18nState.lang === "zh" ? "English" : "中文";
  button.setAttribute("aria-label", i18nState.lang === "zh" ? "Switch to English" : "切换为中文");
}

function applyLanguage(lang) {
  i18nState.lang = lang === "zh" ? "zh" : "en";
  document.documentElement.lang = i18nState.lang === "zh" ? "zh-CN" : "en";
  try { localStorage.setItem("locus-lang", i18nState.lang); } catch { /* storage unavailable */ }
  i18nWalk(document.body);
  updateLanguageToggle();
}

function storedLanguage() {
  try { return localStorage.getItem("locus-lang") || "en"; } catch { return "en"; }
}

function toggleLanguage() {
  applyLanguage(i18nState.lang === "zh" ? "en" : "zh");
}

/* Content rendered after a language switch (chat messages, cards) is translated
   as soon as it is inserted. */
const i18nObserver = new MutationObserver(mutations => {
  if (i18nState.lang !== "zh") return;
  mutations.forEach(mutation => mutation.addedNodes.forEach(node => i18nWalk(node)));
});

/* Sentences whose markup splits the English across several text nodes. */
Object.assign(ZH_TEXT, {
  "Give Locus a clear picture of your business, footprint and decision. Fields marked": "把企业、生产布局与决策信息告诉 Locus。标记",
  "are required.": "的为必填项。",
});

/* Meta lines are composed from several values, so they are matched by shape. */
ZH_PATTERNS.push(
  [/^Preview assessment · Agent service not connected · (.+)$/, "预览评估 · 未连接 Agent 服务 · $1"],
  [/^Preview consultation · Agent service not connected · (.+)$/, "预览咨询 · 未连接 Agent 服务 · $1"],
  [/^Preview scenario estimates · Agent service not connected · (.+)$/, "预览情景估算 · 未连接 Agent 服务 · $1"],
  [/^Consultation runs against the retrieved evidence set · (.+)$/, "咨询基于已检索的证据集 · $1"],
);
