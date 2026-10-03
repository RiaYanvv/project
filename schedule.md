这三天内由我俩提出多个具体议题、用户、痛点组合，进行筛选。可以利用LLM推理进行评分。最后写出一个PRD（包括用户任务、user persona、user journey、workflow、测试计划、最终展现形式等等），并且从最初就上传到github。开始写README
下一周：做一个MVP，这中间应该包括rag、agent搭建、UI设计等等（可使用充值vscode端codex进行vibe coding），目标是走通input-output流程
1、数据层。学习pandas，数据清洗和分析。也应该学习sql
2、RAG。建立知识库
3、LLM workflow
4、agent
5、UI
第三周：进行evaluation、进行优化。包括LLM推理流程优化、rag检索优化、agent性能优化（比如把多性能结合，要不要进行多智能体研发等等）、UI改进（例如可视化效果提高）
这周要解决前端后端等等技术问题
第四周：继续evaluation，迭代以及边界（记录失败案例、指出human in loop）。完成最终部署，比如vercel内置ai
最后：画PPT、整理源代码、上传

最终作品体现：用户需求
 ↓
产品设计(PRD)
 ↓
数据层
 ↓
RAG Pipeline
 ↓
LLM Workflow
 ↓
Agent
 ↓
Backend API
 ↓
Frontend UI
 ↓
Evaluation
 ↓
Deployment
 ↓
Documentation

最终需要留下的东西：参赛作品（无疑）、github展示、demo视频、产品case study（？）
总体有助于简历和面试

简单分工（目前，根据ai建议）：
ywx：Product + AI Engineer
负责：
PRD
Prompt
RAG
Evaluation
Demo

zyy
Research + Data Engineer
负责：
数据收集
数据清洗
专业框架
测试集
同时学：
Pandas
SQL
API

ydq：
Full-stack Engineer
负责：
Backend
Frontend
Deployment
Architecture

我们无法做user research

到星期三为止，我和你两天内应该做的：
挑选议题，主要围绕这三个问题：1、什么地缘政治风险？（一定要具体一点，比如关于出海、管制、去华化等等大问题，再切到小问题）2、用户是什么？（例如公司，哪一类、哪一规模的公司）3、痛点和难点（我们需要解决的问题）。具体的思考角度可以有用户场景、决策任务、地缘政治变量等等。
针对这三个问题，我们要研发什么样的产品？比如是数据搜集、整理，还是风险研判等方向？为做到这一点，我们需要什么样的技术支持？比如数据从哪里找，搭建怎样的agent？都可以简单列举。
进行简单的评估和评分。需要把握的标准比如用户需求、AI所发挥的作用、现有解决方案及其不足、我们能改进的地方、数据可获得性、、MVP在一个月内可实现性、竞品分析、我们在这个过程中能获得的学习价值（毕竟，我们的目标最重要的不是名次而是ai产品相关知识的学习和简历polish）。这个过程也可以用LLM推理帮助评估（第三课应该有讲）。
我们每人提出2-3个初始提案。
从最开始就建立git。

星期三则进行：最终筛选，写成一个完整的PRD0.1version。一起完善git。写初版README。

接下来：PRD撰写。User Journey Map + Agent Architecture Diagram

进一步分工
ywx：
product
PRD
汇报demo
workflow协调

zyy：
数据源
evaluation


ydq：
rag
前后端
部署


9.20-9.27
数据整理：
1、数据源标准化，把现在的 Excel / 表格变成统一的数据结构。
至少有
source_id
title
source_type
publisher
country/region
publication_date
url
authority_level
topic
document_path

e.g.
WTO_001
US Tariff Measure on EV Batteries
WTO
Trade Policy
2026-xx-xx
Authority: S


建议第一版：
10–20份高质量政策/报告
10个左右案例
一小部分贸易数据

2、搭建rag（这部分可能需要你重点学习一下，我也可以一起帮助。rag非常非常重要）
Original documents
↓
Text extraction
↓
Chunking
↓
Embedding
↓
Vector DB
↓
Retrieval

最终目标是要交给ydq一个稳定的 Retrieval Interface


agent搭建
不要等数据了，先搭建起来。现在Company Profile
↓
Retrieve Evidence
↓
Risk Assessment
↓
Scenario Simulation
↓
Initial Assessment这些功能应该都可以尝试做了

重点：把workflow跑通！！！不要求很聪明的agent
最终返回一个固定 JSON！！！


网页制作
Frontend Shell + Mock Data

evaluation
制定评估计划
建立evaluation dataset


Agent Quality Improvement10.1-10.7
Locus Agent Workflow v1
1. Input Understanding
解析用户表单、企业信息、决策问题、目标与约束
2. Company Profile
整合用户输入和公开信息，生成企业结构化画像，标出缺失项
3. Evidence Research
通过 RAG、网络搜索及结构化数据检索政策、贸易、行业报告和案例
4. Risk Assessment
将证据与企业实际情况关联，识别风险、评估影响并说明不确定性
5. Initial Assessment → User Triggered Simulation
先展示企业画像和风险评估；用户点击模拟按钮后，生成并比较三类战略方案
6. Consultation & Report
将已有分析带入对话，处理新增信息、按需更新研究与推演，最终生成决策报告



在每个节点至少需要一个prompt详细说明
Prompt 标准模板
部分
具体要求
Role
模型在该节点扮演什么角色
Objective
本节点唯一的核心目标
Input
可接收的字段和数据
Task
必须完成的具体任务
Rules
业务规则、分析标准、不可做的事情
Evidence Policy
如何引用证据，证据不足时怎么办
Output Schema
必须返回哪些字段、字段类型
Failure Handling
缺失数据、冲突证据、检索失败时如何处理
例如，Risk Assessment 的 Prompt 不能只写：
Analyze geopolitical risks for this company.
而应该明确要求模型：
根据公司生产地、母国、目标市场、产品和供应链依赖识别适用风险。
区分已核实事实、基于事实的推断、假设和未知信息。
每项主要风险必须说明适用原因、潜在业务影响、支持证据 ID 和不确定性。
不得将宏观国家风险直接等同于该企业的实际风险。
缺少关键数据时，明确列出信息缺口，不得臆造数据。
输出符合 Risk Schema 的 JSON。


数据优化
1、evaluation
用于evaluation的Test Set数据库应该包括
（1）historical case benchmark
议最终形成：

> 10–14 个真实企业历史案例

优先覆盖：

* China → Southeast Asia；
* China +1；
* Southeast Asia → China / partial return；
* diversification；
* new manufacturing site；
* tariff / trade-policy driven decisions；
* geopolitical-risk driven decisions。

每个 Case 至少记录：

| Field               | 内容                                   |
| ------------------- | ------------------------------------ |
| case_id             | CASE-xxx                             |
| company             | 企业名称                                 |
| industry            | EV / Battery / related manufacturing |
| original_footprint  | 原生产布局                                |
| decision_trigger    | 为什么需要做决策                             |
| target_market       | 主要市场                                 |
| key_constraints     | 预算、资产、时间、监管等                         |
| major_known_risks   | 历史上可识别的主要风险                          |
| historical_decision | 企业实际采取的行动                            |
| outcome             | 后续结果                                 |
| evidence_ids        | 支撑案例事实的来源                            |
（2）retrieval Evaluation Set
