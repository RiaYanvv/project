task 1
你负责标注
1、基础信息，例如
| 字段          | 作用   | 示例                             |
| ----------- | ---- | ------------------------------ |
| evidence_id | 唯一编号 | BIS_001                        |
| title       | 资料标题 | Expansion of End-User Controls |
| source      | 来源   | BIS                            |
| date        | 发布时间 | 2025-09-30                     |
| url         | 原文链接 | xxx                            |
country/region
原则：每条evidence可以被追溯

2、此外增加来源可信度，分级标准大致如下
S级（最高）
用于支持关键决策：
Government regulation
Official company filing
WTO
UN
World Bank
A级
权威研究：
McKinsey
IMF
CSIS
Industry association
B级
行业信息：
Consulting reports
Market research
C级
辅助信息：
News
Media articles

有标准不明问题随时协商；

3、evidence内容需要分类，我们只聚焦了EV battery领域，所以可能常见类型：EV_Battery
Battery_Materials
Energy_Storage
Automotive
General_Manufacturing


4、topic
每项信息和什么相关，有助于后续risk assessment
可能常见类别：
tariff

export_control

trade_policy

investment_policy

market_access

supply_chain

supplier_dependency

labor

logistics

regulation

localization_policy

5、evidence本身类型
Policy

Company Disclosure

Industry Report

Trade Data

Case Study

News

Academic Research

6、状态（已确定/未知等等）
verified

reported

estimated

inferred

unknown

7、related_risk
我们一共有贸易、政治、供应链、监管、市场准入、运营几类风险，这条证据和什么相关？
Trade Risk
贸易风险：
tariff
trade restriction
Political Risk
政治风险：
geopolitical tension
policy uncertainty
Supply Chain Risk
供应链风险：
supplier dependency
geographic concentration
logistics dependency
Regulatory Risk
监管风险：
export control
compliance
local regulation
Market Access Risk
市场准入风险：
customer access
regional requirement
Operational Risk
运营风险：
labor
infrastructure
production capability
一条Evidence可以对应多个risk。


Final Output
最终每条Evidence应类似：
{
"evidence_id":"BIS_001",

"title":"Expansion of End-User Controls",

"source":"BIS",

"date":"2025-09-30",

"country_region":"USA",

"industry":"EV_Battery",

"topic":"export_control",

"evidence_type":"Policy",

"authority_level":"S",

"data_status":"verified",

"related_risk":[
"Regulatory Risk",
"Market Access Risk"
]
}

每一条evidence应该有以上几条信息。你先标注20条左右之后我来再检验一遍，确认无误后再全部标注，以免返工。


task2
注意：
测试问题不要设计成普通知识问答，而应该模拟真实企业用户决策场景。
例如：
❌ 不推荐：
What is IRA?
因为这只是知识检索。
✅ 推荐：
A Chinese EV battery manufacturer exporting products to the US is considering expanding production in China. What US policies may affect its market access?
你的任务：
写30个测试问题在retrieval_questions.xlsx。每个需要包含
| 字段                    | 说明             | Example                                       |
| --------------------- | -------------- | --------------------------------------------- |
| question_id           | 问题编号           | RQ_001                                        |
| question              | 测试问题           | What policies affect CATL's US market access? |
| scenario_category     | 所属场景           | Policy Risk                                   |
| expected_topic        | 应该检索到的topic    | export_control                                |
| expected_evidence_ids | 正确答案对应Evidence | BIS_001                                       |
| difficulty            | 难度             | Medium                                        |
Question Categories


至少覆盖以下场景：
1. Company Intelligence
测试企业信息理解能力。
Example:
问题：
What are CATL's major overseas manufacturing locations?
Expected evidence:
CATL annual report
company announcement
测试：
是否能够找到企业生产布局资料。
数量：
5 questions
2. Policy / Trade Risk
测试政策检索。
Example:
What US policies may affect Chinese EV battery manufacturers exporting to the US?
Expected:
tariff policy
IRA
export controls
数量：
10 questions
3. Supply Chain Risk
Example:
What factors make battery supply chains dependent on China?
Expected:
supplier network
raw material processing
manufacturing ecosystem
数量：
5 questions
4. Market Access
Example:
What requirements may affect EV battery companies entering the EU market?
Expected:
EU Battery Regulation
compliance requirements
数量：
5 questions
5. Scenario Simulation Support
测试是否能支持战略比较。
Example:
What evidence supports maintaining production in China instead of relocating?
Expected:
China's manufacturing ecosystem
supplier concentration
cost advantages
数量：
5 questions


问题写好之后，发给我看看。接着运行rag：
| 字段                    | 说明           |
| --------------------- | ------------ |
| question_id           | 对应问题         |
| retrieved_evidence_id | AI返回Evidence |
| rank                  | 排名           |
| relevance_score       | 相关性评分        |
| authority_score       | 来源质量评分       |
| notes                 | 人工评价         |

接着需要人工评分，这部分如果有压力我可以一起帮忙。
1. Relevance（相关性）
0-2分：
2分
Evidence直接回答问题。
Example:
问题：
US tariff impact on Chinese EV batteries
返回：
US tariff regulation
1分
部分相关。
0分
无关。
2. Authority（权威性）
0-2分：
2
S/A级来源
政府、公司公告、国际组织。
1
B级来源。
0
低质量来源。
3. Coverage（覆盖度）
0-2分：
是否找到足够信息支持分析。

目标：
Top-5 Retrieval Quality
随机抽取30个问题：
平均：
Relevance score >=1.5/2

Authority score >=1.5/2
并且：
80%以上问题至少包含一个正确Evidence

记录测试结果在retrieval_results.xlsx

完成后提交：
retrieval_questions.xlsx
retrieval_results.xlsx
然后我会进行产品侧review：
检查：
是否符合真实用户决策场景；
是否覆盖核心Risk categories；
是否能有效评价RAG能力。


task3
总目标
测试当前RAG在优化前的基础检索能力，记录baseline结果。
输出：
当前RAG检索质量
主要问题类型
后续优化方向

大部份测试和task重合，只需要再计算并提交  entity_accuracy.xlsx

    baseline_report.md

baseline_report.md：
总结：
Current RAG Performance

Precision@5:
72%

Recall@10:
65%

Entity Accuracy:
90%


Main Problems:

1.
Company retrieval weak

2.
Policy documents ranked low

3.
Case documents missing
便于以后再优化。
最终evaluation分支结构
data/
└── evaluation/

    retrieval_questions.xlsx

    retrieval_results.xlsx

    entity_accuracy.xlsx

    baseline_report.md


task4
task4相对来说是后续的优化任务，不算最紧急，建议先做5
你的任务：
4.1 Metadata Filtering
1. 接入schema字段
使用Task 1中的：
industry

country_region

topic

evidence_type

authority_level

related_risk
2. 建立filter逻辑
例如：
用户输入：
CATL Vietnam factory risk
自动识别：
industry:
EV_Battery

country:
Vietnam

topic:
supply_chain

risk:
Operational Risk
然后过滤。
提交：
代码修改：
retrieval/filter.py
或者对应backend文件。
以及：
metadata_filter_test.xlsx
测试：
优化前 vs 优化后。

4.2 Query Enhancement
建立query enhancement prompt / rule
例如：
输入：
Company:
CATL

Question:
Should we expand China production?
生成：
CATL production footprint

CATL overseas factories

China EV battery supply chain

US tariff risk

EU battery regulation

China+1 strategy
然后用于RAG。
提交：
例如：
query_expansion_prompt.md
以及测试：
query_before_after.xlsx
字段：
Original Query	Expanded Query
CATL risk	CATL + EV battery + tariff + supply chain

4.3 Authority Ranking
使用：
Task 1:
authority_level
字段。
增加ranking score。
例如：
S = 1.0

A = 0.8

B = 0.6

C = 0.4
最终：
retrieval score:
similarity score
+
authority score
A提交：
authority_ranking_test.xlsx
展示：
优化前：
Reuters
News
BIS
优化后：
BIS
WTO
Reuters

注意：权威性不是永远最优先，有时候相关性大于权威性，这需要你制定准则
最终产品侧验收：
优化后重新跑 Task 3：
比较：
Before：
Precision@5 = 65%
Recall@10 = 70%
Entity Accuracy = 85%
After：
Precision@5 >=80%
Recall@10 >=80%
Entity Accuracy >=95%
并记录：
Baseline vs Improved Retrieval



task5
优先选择：
与产品高度相关：
Industry
优先：
EV Battery
Battery Materials
Automotive Supply Chain
Electronics Manufacturing
其次：
Semiconductor
Solar Manufacturing

Case类型：
需要覆盖：
1. China → Southeast Asia relocation
例如：
企业因为：
tariff pressure
geopolitical risk
转移到：
Vietnam / Thailand / Indonesia
2. China + 1 strategy
例如：
企业保持中国，同时增加：
Vietnam
India
Mexico
3. Reconsideration / Return to China
例如：
企业发现海外布局存在：
supplier ecosystem不足
cost higher than expected
operational difficulty
重新增加中国生产。

数量至少10个，最好15左右

Case Database Schema
1、基础信息
| 字段           | 说明   |
| ------------ | ---- |
| case_id      | 唯一编号 |
| company_name | 企业名称 |
| industry     | 行业   |
| source       | 来源   |
| date         | 时间   |
| url          | 原始链接 |
2. Initial Situation（决策前状态）
描述：
企业当时：
生产布局
主要市场
供应链结构
面临的问题
Example:
Company had major production in China
and considered Southeast Asia expansion
due to tariff uncertainty.
3. Decision Trigger（为什么需要决策）
分类参考profile list.md上用户表单那几类trigger，方便追溯
tariff_pressure

geopolitical_uncertainty

cost_change

supplier_issue

market_access

regulation_change
4、Actual Decision（真实决策）
必须记录：
企业最终选择：
Example:
Built Vietnam factory while
maintaining China production.
简单分类有多地区混合布局、维持现有海外布局、提高中国生产比例这三种

5、related_risk
参加task1 中related_risk

6. Outcome（后续结果）
成功和失败案例都要收集
尽量包括：
cost impact
production performance
market access
supply chain impact
Example:
Vietnam reduced tariff exposure,
but supplier ecosystem remained dependent on China.

7、Evidence
每个案例必须绑定来源：
字段：
related_evidence_ids
Example:
CASE_001

Evidence:

REUTERS_001
MCK_002
COMPANY_REPORT_001

我需要最终验收：
检查：
案例是否真实；
是否和EV battery / supply chain relocation相关；
是否有完整“背景→决策→结果”链条；
是否可以用于测试Scenario Simulation。

案例会用来做evaluation，这个下一步再谈

