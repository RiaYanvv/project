PRD

1. Product Overview
   1.1 Background
    我们从reuters报告和McKinsey报告中了解到，许多实行china+1战略布局的企业在此前由于关税和政治风险，尤其是美国对华贸易政策升级后，将供应链生产端转向印度、越南、泰国等东南亚地区。
    目的：
    避免美国对中国商品征收高额关税；
    降低中美贸易摩擦风险；
    建立“China + 1”供应链。
    然而很多企业逐渐意识到，离开中国没有那么容易。中国制造优势并不只是低成本，而是一整套成熟生态，包括：完整供应商网络；熟练产业工人；高效物流；稳定能源供应；大规模生产经验等等。离开中国仅降低关税，却不一定降低生产成本。
    由此，部分企业部分企业开始重新评估此前的供应链迁移决策，并根据成本、供应链韧性、政策环境等因素调整生产布局。，例如Dawang Metals、Target、Shein。而更多企业面临评估回华风险、需要进行供应链布局调整，但信息分散，分析成本高。

   1.2 Product Vision
   一个帮助制造企业在地缘政治不确定环境下进行供应链迁移和布局决策的 AI 咨询助手。
   1.3 Goals
   帮助企业
   ·提供企业自身信息分析
   ·了解当前地缘风险
   ·评估不同生产布局方案（维持东南亚、回迁中国、混合布局）的成本、风险和韧性，并生成可解释的战略建议。
   ·提供相似案例支持
   ·生成PDF报告


2. User Analysis
   2.1 Target Users
   idustries
      Battery / EV Supply Chain
    These industries are selected because they have significant global supply chain exposure, strong China+1 trends, and abundant public data availability.
   Primary User:
     供应链/战略经理
     企业：
     制造业公司
     跨国公司
     考虑重新布局的企业
    Secondary User:
     咨询分析人员
     投资分析人员

   2.2 User Persona
  
| ------------ | -------- |
| Name         | / |
| Role         |  Global Supply Chain Manager    |
| Company Type | Medium-to-large manufacturing company with overseas operations     |
| Background   | 负责公司的全球生产布局和供应链战略。由于关税变化、地缘政治不稳定等原因，公司正在重新评估是否继续扩大海外生产，还是调整生产布局。      |
| Goals        | Understand geopolitical risks affecting supply chain
Compare different relocation strategies
Make evidence-based decisions for management       |
| Pain Points  | 信息碎片化，需要同时查看政府报告、 贸易数据 、新闻等等，高度分散；决策受多种因素影响，困难；咨询报告大多为静态，缺乏真实情景推演    |
| Needs        |   需要一个工具：自动收集相关信息、总结风险、比较不同方案、提供决策支持     |

   2.3 User Scenario
   一家新能源电池企业目前在中国拥有部分生产能力，越南拥有主要海外工厂，产品主要出口美国。近年来由于关税变化、地缘政治不稳定等原因，公司管理层要求供应链部门重新评估生产布局。CEO提出问题：“如果未来美国进一步提高相关产品贸易限制，我们是否应该增加中国生产比例，或者转向其他国家？”
   Alex作为供应链/战略经理通常需要收集政策信息、阅读大量行业报告、咨询专家、制作分析报告。耗时长，信息更新慢。

   Using Our Product
step 1
Alex输入：
Company name
Industry
Current production locations
Target markets
Decision question
......
Step 2
AI自动：
构建Company Profile
检索企业相关资料
收集政策、贸易、新闻证据
Step 3
AI输出：
Initial Assessment:
包括：
current supply chain summary
key risks
relevent cases
possible scenarios
例如：
Scenario A:
Maintain Vietnam production
Scenario B:
Increase China production
Scenario C:
Diversify to other countries
Step 4
Alex继续和AI对话：
补充：
supplier dependency
cost constraints
investment limitation
AI更新分析。
Step 5
最终：
生成：
Executive Decision Report PDF
供管理层讨论。

最终，Alex可以减少调查时间、理解风险、比较选择、形成有逻辑的战略决策。产品功能可以合理嵌入工作流程。

3. Problem Definition
痛点1:Fragmented information。政策、新闻、贸易数据分散。企业需要大量人工研究。
痛点2:Complex trade-off analysis。没有单一最优答案。需要综合成本、风险大量因素进行复杂决策。
痛点3:Lack of scenario simulation。传统报告无法动态回答。

4. Product Solution
    User Journey
    Input Company Information
        ↓
Build Company Profile
        ↓
Collect Evidence & Analyze Risks
        ↓
Generate Initial Assessment & Scenarios
        ↓
Interactive AI Consultation & Refinement
        ↓
Generate Final Decision Report
   

5. Functional Requirements
   5.1 Company Profile Generation
   Purpose
建立企业基础画像，为后续分析提供context。
User Input
初始描述：一句话描述 + 基础信息。（需要提示词,提醒用户输入产业、生产链、销售地、痛点）
e.g.我们是一家新能源汽车电池企业，目前70%的生产在越南，主要出口美国。由于美国政策变化以及越南供应链不足，我们考虑是否扩大中国生产比例。

用户输入表单（示例）：
Required Information

Company
Industry
Production location
Market
Decision question


Optional Information

Capacity
Documents
Supplier information

AI Output
Company Profile:
business overview
supply chain footprint
market exposure
Priority:
P0
   5.2 Evidence-based Research
   Purpose
收集可靠信息。
Input:
Company Profile
Sources:
uploaded documents
reports
news
trade data
Output:
Evidence Database
包含：
source
date
authority level
relevance
Priority:
P0
   
   5.3 Evidence system
   Purpose
建立统一的证据管理与可信度机制，为风险分析、情景推演和最终建议提供可追溯的事实依据。
Function
系统对 Research 阶段获取的信息进行整理、筛选与分级，并根据来源权威性、时效性和与企业场景的相关性评估证据可信度。关键分析结论均关联对应证据，同时标注信息存在的不确定性。
Output
结构化 Evidence Library，包括：
Evidence content
Source
Publication date
Authority level
Relevance
Related conclusion
   5.4 Risk Assessment
   Purpose
基于企业画像和已验证的证据信息，识别与当前供应链布局及决策相关的主要风险。
Function
Agent 从贸易、政策、地缘政治、供应链依赖、市场准入等维度分析信息，并判断这些风险对该企业当前业务和供应链布局的具体影响。
Output
形成企业专属的 Risk Assessment，包括：
Major risks
Risk severity
Potential business impact
Supporting evidence
Key uncertainties
   5.5 Scenario Simulation
   Purpose
模拟不同供应链布局方案下可能产生的影响，帮助用户比较不同决策路径及其权衡关系。
Function
根据企业当前情况、识别出的风险以及用户设定的决策约束，生成若干可行 Scenario，并从成本、供应链韧性、地缘政治风险、市场准入和实施难度等维度进行比较。
典型 Scenario 包括：
Maintain current layout
Increase production in China
Relocate production
Adopt a hybrid strategy
Output
Scenario Comparison，展示各方案的：
Potential benefits
Potential risks
Key trade-offs
Applicable conditions
并形成基于当前信息的 preliminary assessment。
   5.6 AI Consultation
   Purpose
通过与用户的持续对话补充关键信息、澄清决策偏好，并在新的信息和条件下不断完善分析。
Function
用户可以在初步分析后继续提供：
Additional information
Business constraints
New concerns
Decision preferences
LLM 根据对话内容重新审视已有分析，必要时调用 Research / Analysis 能力获取或验证新的信息，并动态更新 Scenario 与 assessment。
Output
经过多轮互动后形成更加完整的：
Updated risk assessment
Refined scenario comparison
Decision considerations
Final decision
The system supports human decision-making rather than replacing human judgment.
   5.7 Report Generation
   Purpose
将完整的咨询过程和最终决策结果整理为可直接用于企业内部沟通与决策的正式报告。
Function
在用户完成决策后，系统整合企业信息、研究证据、风险分析、Scenario 比较以及对话中形成的最终判断，生成结构化报告。
Output
PDF Decision Report，包括：
Executive Summary
Company Profile
Current Supply Chain Situation
Risk Assessment
Scenario Comparison
Final Decision / Recommendation
Evidence Sources
Uncertainties & Limitations

6. AI System Workflow
User Input
                    |
                    ↓
          Decision Understanding
                    |
                    ↓
          Company Profile Builder
                    |
                    ↓
        Knowledge Acquisition Layer
     ┌──────────┼───────────┐
     ↓          ↓           ↓
 Documents   Web Search   Data Sources
                    |
                    ↓
            Evidence Database
                    |
                    ↓
          Risk Analysis Module
                    |
                    ↓
        Scenario Simulation Module
                    |
                    ↓
          AI Consultant Chat Loop
                    |
                    ↓
           Final Decision Report
                    |
                    ↓
                  PDF

7. Output Design
1、Initial Assessment Report
包括：
Company Overview
Current Situation
Key Risks
Scenario Comparison
Preliminary Recommendation
Evidence
Uncertainty

Final Decision Report
PDF：
结构：
Executive Summary
Company Profile
Risk Assessment
Scenario Comparison
Recommendation
Evidence

8. Non-functional Requirements
1、Accuracy
重要结论必须附来源。
2、Explainability。展示：evidence和uncertainty

9. Evaluation Plan
1、 Information Retrieval Evaluation
测试AI是否找到正确的答案，指标包括证据相关性、来源权威性等等。
2. Risk Identification Evaluation
建立 Expert Checklist。
3. Scenario Analysis Evaluation
找到相关案例及决策、后续发展，一部分在evidence dataset里面作为数据集，一部分更高质量的作为测试集，以此判断决策质量。或者人工专家打分。
4、User Experience Evaluation
采访模拟。分为产品满意度和节约时间两项指标

评分机制：同意采取整数0-10离散评分、连续评分，评分的同时给出rationale分析；多次采样增加稳定度
10. Future Roadmap
后续可能加入功能：
1、相关新闻报告推荐页面，方便企业查询和辅助决策。
2、“售后”：用户完成决策咨询后，订阅政策变更通知，当与用户决策相关的关税政策发生变化时，提供通知，并再次简要分析决策建议。
3、增加：Sign in / Create account实现跨设备历史同步