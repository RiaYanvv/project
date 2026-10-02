Company Intelligence & Profile
企业信息调查、供应链结构识别与决策情境理解
不只是总结用户填写的信息，而是结合用户输入、上传文件、公开企业资料和相关数据，形成一份有事实依据、结构清晰、包含深度文字分析的企业画像。

agent需要回答的问题：
这是一家什么样的企业？ 主要经营什么产品，处于电池产业链的哪个环节，业务模式是什么？
它的生产布局是什么？ 哪些国家负责研发、原材料、零部件、制造、组装和出口？各地产能与生产份额如何分布？
它的供应链结构是什么？ 关键原材料和零部件来自哪里，哪些环节依赖特定国家或供应商？
它当前的市场和战略处境是什么？ 主要销售市场、海外生产布局、扩张或迁移背景，以及当前正在考虑的决策。
哪些信息已经确认，哪些仍然未知？ 区分用户提供的信息、公开来源、AI 推断和待确认信息。

如果用户提供了详细信息，请以用户信息为准。如果用户没有提供，按照网络检索信息回答，但要注意标注信息来源，并且标为待确认。

agent工作流：
Company Profile Generation Workflow
1. User Input
表单信息、自然语言描述、上传文件
2. Company Research
公司官网、年报、公开公告、行业报告、相关新闻；RAG 与网络搜索
3. Entity & Evidence Verification
核对公司身份、去重、检查日期、标注来源、处理信息冲突
4. Profile Construction
整合生产布局、产品、供应链结构、市场和决策情境
5. Profile Validation & Generation
检查数据完整性、事实来源、未知信息和用户输入冲突；输出结构化画像与文字分析


前端需要展示内容：
Company Profile 页面结构
Section 1
Company Overview — 企业概况
简洁展示公司名称、总部所在地、核心产品、业务模式、产业链位置、主要市场和企业规模（如果有可靠信息）。
Section 2
Global Production Footprint — 全球生产布局
以地图或结构化表格展示各国生产设施、生产环节、产能与供应链角色。对无法确认的信息保留空缺，并注明来源。
Section 3
Supply Chain Structure — 供应链结构
梳理上游原料、关键零部件、制造基地、组装及目标市场之间的关系，并识别已知的跨国依赖。这一部分先描述企业结构，不提前替代后续正式风险评估。
Section 4
Strategic Context — 战略情境分析
用几段有深度的文字解释企业目前的布局逻辑、经营目标、此次决策的触发因素、可能涉及的关键权衡，以及后续分析需要重点调查的事项。

每个关键事实最好还能有自身的 source_ids 和 data_status，而不是只在整个画像末尾放一组来源。否则一个企业画像里可能混合着用户陈述、公开报道和模型推断，后面很难追溯。

案例（非真实）
Company Profile · Illustrative Example
ABC Battery — Company Intelligence
EV Battery Manufacturer · China / Vietnam / US
Headquarters
China
Core product
EV battery cells
Production
China 30% · Vietnam 70%
Main market
United States
Strategic Context
ABC Battery is a China-headquartered EV battery manufacturer with production operations in China and Vietnam. According to the hypothetical company information provided, Vietnam accounts for 70% of its production, while China retains 30%. The company primarily serves the US market and is considering increasing its China-based production capacity while maintaining its Vietnamese operations.
This production structure indicates that the company has established a multi-country manufacturing footprint, but the actual degree of supply-chain diversification remains to be verified. In particular, the geographic distribution of critical raw materials, components, and suppliers is not yet fully established by the available information.
The company's decision involves balancing several potentially competing objectives: maintaining access to its target market, preserving existing overseas manufacturing investments, strengthening supply-chain resilience, and managing the costs and operational complexity of changing production locations.
Given the current information, the next stage of analysis should prioritize verification of supplier origins, production capacity utilization, product-specific trade rules, and the company's investment constraints. These factors will help determine whether maintaining the current layout, increasing China production, or adopting a hybrid configuration is feasible under the company's actual circumstances.
Information Gaps
Actual production capacity and utilization by location
Critical raw material and component supplier origins
Ownership and operational structure of overseas facilities
Product-specific tariff classification and rules of origin