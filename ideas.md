如何与日常工作流结合？
China+1企业部署回华？比如，我们可以帮助企业判断是否适合回华？
供应链问题
一些原本为了降低关税和地缘政治风险而把生产从中国转移到印度、越南、印尼的企业，因为当地基础设施、劳动力、电力、供应商生态等问题，又开始重新评估甚至部分回到中国。
帮助已经进行 China+1 布局的企业评估：继续维持东南亚生产、扩大当地布局、迁回中国、或者采用混合供应链，哪一种方案在成本、风险和韧性方面最优。
“面向正在实施 China+1 战略的制造企业，开发 AI Supply Chain Relocation Decision Agent，通过整合贸易数据、政策信息、国家风险指标和供应链结构数据，帮助企业评估不同生产布局方案（维持东南亚、回迁中国、混合布局）的成本、风险和韧性，并生成可解释的战略建议。”
“回华”只是其中一个 action option。
可以采用scenario模拟，必须要做企业画像，而不是宏观国家评分
供应链贸易数据建议：US comtrade
产业链依赖：OECD tiva
贸易政策：WTO、EU Access2Markets、US tariff database
国家风险：WTO、EU Access2Markets、US tariff database
新闻事件：Reuters / FT
接下来需要解决的问题：我们的用户调研从哪里？即问题是怎么发现的？
竞品分析？有什么差异化？
https://www.mckinsey.com/industries/logistics/our-insights/diversifying-global-supply-chains-opportunities-in-southeast-asia?utm_source=chatgpt.com

政策变化研究
风险评判
地缘政治新闻-企业风险预警

Digital Sovereignty：
“我的企业到底在哪些技术环节暴露于外国地缘政治风险？”
暴露给那些国家、具体哪些风险暴露



一、用户分析
调研来源：我们从reuters报告和McKinsey报告中了解到，许多实行china+1战略布局的企业在此前由于关税和政治风险，尤其是美国对华贸易政策升级后，将供应链生产端转向印度、越南、泰国等东南亚地区。
目的：
避免美国对中国商品征收高额关税；
降低中美贸易摩擦风险；
建立“China + 1”供应链。

现实矛盾：中国制造优势并不只是低成本，而是一整套成熟生态。
离开中国后许多企业发现，降低关税不能降低总成本。
现实案例：Dawang Metals（金属铸造企业）
Target
Shein
因此出现企业回流。不是说中国重新成为唯一生产基地，而是企业正在重新平衡供应链。

背景补充：
China+1战略：中国保留核心制造，同时在其他国家建立第二供应链节点。东南亚成为最大受益地区。
东南亚优势：
成本低
地缘政治风险分散
RCEP
劣势：
供应商网络不足
基础设施差异
人才不足

综上，用户画像：正在实施 China+1 战略的制造企业，面临产业链重新布局决策（具体行业待定，越具体越好）
痛点解决：帮助企业评估不同生产布局方案（维持东南亚、回迁中国、混合布局）的成本、风险和韧性，并生成可解释的战略建议。评估回华风险、是否值得回华 。


二、产品画像
产品为AI Supply Chain Relocation Decision Agent
采用网页形式，内置LLM推理和agent
产品功能：帮助已经进行 China+1 布局的企业评估：继续维持东南亚生产、扩大当地布局、迁回中国、或者采用混合供应链，哪一种方案在成本、风险和韧性方面最优。

用户交互：
最主要是一个咨询页面，
用户输入
1、公司名
2、产业（进行选择，例如Electronics、Semiconductor，不要自由输入）
3、product/main business（What products are you producing?

Example answers:
EV battery cells
Lithium-ion battery modules
Solar panels
Consumer electronics）
4、主要产地
Country（选择）
China
Vietnam
Indonesia
India
Mexico
Other


Percentage of production（填空）

China:
40%

Vietnam:
60%
5、其他选填信息
例如，具体生产地址、capacity、成立时间

6、此外可以发送相关excel等文档

7、目标
What decision do you want AI to help with?


○ Should we expand Vietnam production?

○ Should we move production back to China?

○ Should we diversify into multiple countries?

○ Should we build a new factory?

○ Other

8、时间期限
When do you need this decision?

○ Within 6 months
○ 6-18 months
○ 2-5 years

9、priority
排序题
What matters most?


Cost reduction
★★★★★

Supply chain resilience
★★★★★

Market access
★★★★★

Political stability
★★★★★

Compliance
★★★★★

10、生产和受限
Where are your products sold?

USA
EU
China
ASEAN
Other

Do you face:


□ Tariff pressure

□ Export controls

□ Sanctions concerns

□ Local regulation

□ Supplier dependency

□ Labor cost increase

□ Logistics problems

□ None


包括当前信息总结、主要风险识别、各决策scenario推演，并给出一个最终评估建议，最后问用户更多信息提供邀请对话。接下来交给LLM模型，在和用户的对话中继续完善。当用户最后做出决策后，LLM进行一个总结并生成可以给用户用的PDF报告。


内置工作程序：数据搜集，包括
爬虫抓取相关公司目前信息和产业布局
agent信息推理

竞品分析：

三、技术支持
数据来源支持
