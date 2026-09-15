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
workflowxiet

zyy：
数据源
evaluation


ydq：
rag
前后端
部署
