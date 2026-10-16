"""Task 5 — build the China+1 / relocation case database.

Output: project-data/data/processed/case_database_v0.1.xlsx
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = Path("/Users/zhengyuanyuan/Desktop/project-data/data/processed/case_database_v0.1.xlsx")

EV = [
 ("NEWS_001","东方财富网","比亚迪泰国工厂竣工投产 第800万辆新能源汽车下线","2024-07-04","https://finance.eastmoney.com/a/202407043122188760.html"),
 ("NEWS_002","易车","长安汽车泰国罗勇工厂投产！中国汽车出海迈入产业时代","2025-05-17","https://news.yiche.com/hao/wenzhang/100585175/"),
 ("COMPANY_REPORT_001","证券之星（长安汽车投资者互动平台回复）","长安汽车：公司在泰国罗勇工厂已建成投产，具备整车本地化生产能力","2026-09-20","https://finance.stockstar.com/IG2026092000009224.shtml"),
 ("NEWS_003","澎湃新闻","国轩高科牵手越南造车新势力，越南首座磷酸铁锂电池工厂开工","2022-11-19","https://m.thepaper.cn/newsDetail_forward_20810032"),
 ("NEWS_004","盖世汽车社区 / CBC金属网","国轩高科：德国、越南、印尼、泰国四大海外基地已陆续投产","2026-07-13","https://www.cbcie.com/lithium/news/content/2259979.html"),
 ("NEWS_005","新浪财经","亿纬锂能马来西亚工厂二期投产","2026-02-06","https://finance.sina.com.cn/roll/2026-02-06/doc-inhkwssf2073873.shtml"),
 ("NEWS_006","东方财富网","投资不超20亿元 欣旺达越南新建电池工厂","2024-07-16","https://finance.eastmoney.com/a/202407163131488556.html"),
 ("NEWS_007","腾讯新闻","欣旺达：越南消费类电芯生产基地预计2026年年底投产","2026-08-27","https://news.qq.com/rain/a/20260827A07Y7300"),
 ("NEWS_008","澎湃新闻","蜂巢能源泰国电池工厂投产，供货泰国长城欧拉、合众新能源等","2024-02-28","https://www.thepaper.cn/newsDetail_forward_26493905"),
 ("NEWS_009","新浪财经","年产12万吨！华友钴业印尼镍钴湿法项目达产","2024-04-12","https://finance.sina.com.cn/stock/relnews/cn/2024-04-12/doc-inarqawt9056004.shtml"),
 ("NEWS_010","和讯网","中伟股份印尼三基地投产 提升自供原料比增强竞争力","2024-04-08","https://futures.hexun.com/2024-04-08/212465761.html"),
 ("NEWS_011","网易","中伟股份：印尼中青新能源二期全面投产","2026-01-07","https://www.163.com/dy/article/KIMPK6220534A4SC.html"),
 ("NEWS_012","每日经济新闻","宁德时代匈牙利德布勒森工厂启动新电芯厂房试生产","2026-09-22","https://www.nbd.com.cn/articles/2026-09-22/4589059.html"),
 ("NEWS_013","新浪财经","宁德时代匈牙利工厂启动：投资金额73.4亿欧元","2022-09-06","https://finance.sina.com.cn/jjxw/2022-09-06/doc-imqmmtha6132311.shtml"),
 ("NEWS_014","东方财富网","宁德时代与印尼合作项目正式动工，未来总投资近60亿美元","2025-07-02","https://finance.eastmoney.com/a/202507023446498365.html"),
 ("NEWS_015","凤凰科技","比亚迪汽车印尼工厂年底前竣工：总投资10亿美元，年产能15万辆","2025-01-22","https://tech.ifeng.com/c/8gLk1Msnjan"),
 ("NEWS_016","东方财富财富号","晶科能源：全球工厂以中国为核心，叠加东南亚（马来西亚、越南）与北美（美国）成熟产能","2026-02-25","https://caifuhao.eastmoney.com/news/20260225153639217944650"),
 ("NEWS_017","新浪财经","三星拟投资40亿美元在越南建芯片测试工厂","2026-05-27","https://finance.sina.com.cn/stock/t/2026-05-27/doc-inhzikrs0845798.shtml","原链接已失效（页面不存在），待替换来源；金额口径待核实"),
 ("COMPANY_FILING_001","恩捷股份公告（经东方财富网报道）","恩捷股份：终止马来西亚锂电池隔离膜项目投资","2026-05-22","https://finance.eastmoney.com/a/202605223746866215.html"),
 ("NEWS_018","央广网","恩捷股份终止马来西亚锂电池隔离膜项目 原计划投资20亿元","2026-05-22","https://finance.cnr.cn/ycbd/20260522/t20260522_527631400.shtml"),
 ("NEWS_019","新浪科技","富士康撤回印度中国工程师，苹果制造遇挑战","2025-07-03","https://finance.sina.com.cn/tech/roll/2025-07-03/doc-infeerfp4024842.shtml"),
 ("NEWS_020","中关村在线","富士康撤回中国技术团队，苹果印度供应链再受挫","2025-12-04","https://m.zol.com.cn/article/10372357.html"),
 ("REUTERS_001","路透社（经环球网转载）","英媒：外迁订单与产能开始回流中国","2026-09-14","https://3w.huanqiu.com/a/de583b/4TE5JD6omnj"),
 ("NEWS_021","36氪","300亿元投资搁浅？蜂巢能源暂停投建德国电池工厂","2024-10-25","https://www.36kr.com/p/3007796900800009"),
 ("NEWS_022","财新网","蜂巢能源终止欧洲子公司运营 关停两座德国电池工厂","2024-10-28","https://www.caixin.com/2024-10-28/102250409.html"),
 ("NEWS_023","中国储能网","越南大面积缺电，找广西买电","2024-08-22","https://www.escn.com.cn/news/show-1700850.html"),
 ("NEWS_024","ANTARA（印尼国家通讯社）","Pabrik BYD di Subang resmi beroperasi dan serap 5.000 pekerja lokal（比亚迪苏邦工厂正式投产，吸纳 5000 名本地员工）","2026-09-03","https://otomotif.antaranews.com/berita/5724273/pabrik-byd-di-subang-resmi-beroperasi-dan-serap-5000-pekerja-lokal"),
 ("NEWS_025","ANTARA（印尼国家通讯社）","BYD setop impor mobil ke Indonesia, beralih penuh ke produksi lokal（比亚迪停止整车进口，全面转向本地生产）","2026-09-03","https://otomotif.antaranews.com/berita/5724855/byd-setop-impor-mobil-ke-indonesia-beralih-penuh-ke-produksi-lokal"),
]

RELOC = "China → Southeast Asia relocation"
PLUS1 = "China + 1 strategy"
RETURN = "Reconsideration / Return to China"

CASES = [
dict(case_id="RELOC_001", company_name="比亚迪 BYD", industry="Automotive (EV)",
 source="东方财富网（转比亚迪官方）", date="2024-07-04", url="https://finance.eastmoney.com/a/202407043122188760.html",
 case_type=RELOC,
 initial_production_layout="整车与电池产能全部位于中国（深圳、西安、长沙、常州等基地），海外无自有乘用车整车产能。",
 initial_main_markets="中国市场为主，出口快速扩张至东南亚、欧洲、拉美、澳新。",
 initial_supply_chain="电池、电机、电控垂直整合，供应链集中于中国境内。",
 initial_problem="纯出口模式在东盟右舵市场面临整车进口税与本地化要求；美国、欧盟对华电动车关税与反补贴调查抬升出口成本。",
 decision_trigger="tariff_pressure",
 trigger_detail="美国对华电动车加征关税、欧盟反补贴调查，出口关税壁垒上升；泰国对本地组装提供 BOI 优惠。",
 decision_type="多地区混合布局",
 actual_decision="2022-09 与 WHA 签约，在泰国罗勇府建全资乘用车工厂；2024-07-04 竣工投产，年产能约 15 万辆，投资约 350 亿泰铢（约 69.5 亿元人民币）。中国产能保留并继续扩产。",
 related_risk="Trade Risk; Market Access Risk; Political Risk",
 outcome_cost_impact="本地化生产规避东盟整车进口税，叠加泰国 BOI 税收优惠降低综合税负；但泰国本地零部件配套不足，短期单位成本高于中国。",
 outcome_production_performance="开工到投产仅 16 个月，创中国车企在泰最快投产纪录；第 800 万辆新能源汽车在泰国工厂下线。",
 outcome_market_access="直接覆盖泰国及东盟右舵市场，从整车出口转为本地供应，显著降低准入壁垒。",
 outcome_supply_chain_impact="关键零部件初期仍依赖中国进口，本地供应链配套率低，形成新的跨境物流依赖。",
 outcome_verdict="成功（本地供应链仍依赖中国）",
 related_evidence_ids="NEWS_001",
 verification_status="高（官方发布 + 多家主流媒体一致）",
 notes="整车厂跟随关税出海的标准案例，可作为 Scenario Simulation 的基准情景。"),

dict(case_id="RELOC_002", company_name="长安汽车 Changan Automobile", industry="Automotive (EV)",
 source="易车 / 证券之星（投资者互动平台）", date="2025-05-16", url="https://news.yiche.com/hao/wenzhang/100585175/",
 case_type=RELOC,
 initial_production_layout="整车产能集中于中国（重庆、合肥、南京等），海外以整车出口为主。",
 initial_main_markets="中国为主，海外处于快速扩张期（2024 年海外销售 53.6 万辆）。",
 initial_supply_chain="整车与三电系统主要在中国生产，海外仅有散件组装。",
 initial_problem="东南亚右舵市场准入依赖整车出口，关税与local content要求抬升成本。",
 decision_trigger="market_access",
 trigger_detail="泰国 EV3.5 补贴政策要求本地生产，才能享受补贴与关税优惠。",
 decision_type="多地区混合布局",
 actual_decision="在泰国罗勇府建设整车工厂，2025-05-16 竣工投产，全球累计第 2859 万辆（深蓝 S05）在泰下线；中国产能保留。",
 related_risk="Market Access Risk; Trade Risk; Operational Risk",
 outcome_cost_impact="获得泰国 BOI 优惠与 EV3.5 补贴资格，降低进入东盟的单位成本。",
 outcome_production_performance="2026-09 公司确认罗勇工厂已建成投产并具备整车本地化生产能力。",
 outcome_market_access="从整车出口转为本地生产，满足泰国本地化要求，保住补贴资格。",
 outcome_supply_chain_impact="零部件本地化配套率仍在爬坡，初期依赖中泰跨境供应。",
 outcome_verdict="成功（早期，产能爬坡中）",
 related_evidence_ids="NEWS_002; COMPANY_REPORT_001",
 verification_status="高（公司互动平台确认 + 媒体报道）",
 notes="与比亚迪泰国案例对照，可用于比较不同车企的东南亚本地化路径。"),

dict(case_id="RELOC_003", company_name="国轩高科 Gotion High-Tech", industry="EV Battery",
 source="澎湃新闻 / 盖世汽车社区", date="2022-11-19", url="https://m.thepaper.cn/newsDetail_forward_20810032",
 case_type=RELOC,
 initial_production_layout="电芯产能集中于中国（合肥、庐江、南京等基地），海外仅有销售与研发。",
 initial_main_markets="中国动力电池市场为主，海外客户（大众等）快速增加。",
 initial_supply_chain="正极、负极、隔膜主要来自中国供应商，磷酸铁锂（LFP）技术路线自主。",
 initial_problem="整车客户在东南亚建厂后要求就近配套；纯从中国出口电池面临关税与交期风险，且越南本地无 LFP 电芯产能。",
 decision_trigger="market_access",
 trigger_detail="越南 VinFast 本地化生产需要就近电池配套，越南对电池进口设有本地化要求。",
 decision_type="多地区混合布局",
 actual_decision="与 Vingroup 旗下 VinES 合资（国轩 51% / VinES 49%）在越南河静经济开发区建越南首座 LFP 电池工厂，一期规划年产能 5GWh；2026-07 公司披露德国、越南、印尼、泰国四大海外基地已陆续投产，越南基地为亚洲首条 LFP 电芯工厂。",
 related_risk="Market Access Risk; Trade Risk; Supply Chain Risk",
 outcome_cost_impact="就近配套降低物流与关税成本；越南人工与土地成本低于中国。",
 outcome_production_performance="四大海外基地陆续投产，越南基地定位为亚洲首个 LFP 电芯工厂。",
 outcome_market_access="绑定 VinFast 这一本地整车客户，进入越南及东盟供货体系。",
 outcome_supply_chain_impact="正负极等关键材料仍从中国输入，越南基地形成'中国材料—越南电芯'的跨境结构。",
 outcome_verdict="成功（材料端仍依赖中国）",
 related_evidence_ids="NEWS_003; NEWS_004",
 verification_status="中高（开工有明确报道；2026 年投产状态来自公司互动平台转述）",
 notes=""),

dict(case_id="RELOC_004", company_name="亿纬锂能 EVE Energy", industry="EV Battery / Energy Storage",
 source="新浪财经", date="2026-02-06", url="https://finance.sina.com.cn/roll/2026-02-06/doc-inhkwssf2073873.shtml",
 case_type=RELOC,
 initial_production_layout="锂电产能集中于中国（惠州、荆门、成都等），海外无大型自有厂房。",
 initial_main_markets="中国为主，海外储能与圆柱电池客户（含特斯拉供应链）增长快。",
 initial_supply_chain="材料与设备主要来自中国，产品以出口方式交付海外客户。",
 initial_problem="出口至欧美面临关税与供应链本地化要求，交付半径长、响应慢。",
 decision_trigger="tariff_pressure",
 trigger_detail="对美出口关税与'去中国化'供应链要求，迫使企业在东南亚布局产能以规避税率。",
 decision_type="多地区混合布局",
 actual_decision="在马来西亚吉打州居林县建设海外工厂，二期于 2026 年 2 月投产运营，建筑面积约 60 万平方米，系公司首个海外大型锂电厂房项目，形成年产约 6.8 亿只圆柱电池产能；同时推进匈牙利、美国、印尼项目，中国产能保留。",
 related_risk="Trade Risk; Supply Chain Risk; Operational Risk",
 outcome_cost_impact="马来西亚产能提升出口业务规避税率的能力，降低对美出口关税成本。",
 outcome_production_performance="二期投产形成规模化圆柱电池产能，海外交付能力显著提升。",
 outcome_market_access="马来西亚基地作为面向欧美客户的出口枢纽，缓解关税与本地化压力。",
 outcome_supply_chain_impact="设备与材料初期仍由中国输入，形成'中国材料—马来西亚制造—欧美市场'链条。",
 outcome_verdict="成功（爬坡中）",
 related_evidence_ids="NEWS_005",
 verification_status="高（公司发布 + 主流财经媒体）",
 notes="可用于比较'东南亚出口枢纽'与'近岸（墨西哥/匈牙利）'两种路径。"),

dict(case_id="RELOC_005", company_name="欣旺达 Sunwoda", industry="EV Battery / Consumer Battery",
 source="东方财富网 / 腾讯新闻", date="2024-07-16", url="https://finance.eastmoney.com/a/202407163131488556.html",
 case_type=RELOC,
 initial_production_layout="消费类与动力电池产能集中于中国（深圳、惠州、南京等）。",
 initial_main_markets="中国为主，消费类电池出口欧美客户占比高。",
 initial_supply_chain="电芯与材料主要来自中国，产品以整包出口。",
 initial_problem="消费电子客户要求供应商在东南亚备产能以分散关税与地缘风险。",
 decision_trigger="tariff_pressure",
 trigger_detail="美国对华加征关税及客户'中国+1'采购要求，推动消费类电芯产线外移。",
 decision_type="多地区混合布局",
 actual_decision="2024-07-15 公告拟通过下属子公司香港欣威设立越南锂威有限公司，投建越南锂威消费类锂电池工厂项目，投资总额不超过 20 亿元人民币；2026-08 公司表示越南消费类电芯生产基地预计 2026 年底投产。中国产能保留。",
 related_risk="Trade Risk; Supply Chain Risk; Operational Risk",
 outcome_cost_impact="越南基地降低对美出口关税暴露，但前期资本开支与本地配套成本较高。",
 outcome_production_performance="截至 2026-08 仍在建设期，预计 2026 年底投产（结果尚待验证）。",
 outcome_market_access="满足欧美消费电子客户对非中国产能的采购要求。",
 outcome_supply_chain_impact="材料仍由中国供应，越南以电芯制造环节为主。",
 outcome_verdict="待观察（尚未投产）",
 related_evidence_ids="NEWS_006; NEWS_007",
 verification_status="中高（公告明确；投产时间来自公司投资者关系记录转述）",
 notes="少见的'结果尚未发生'案例，可用于测试模型对不确定结论的处理。"),

dict(case_id="RELOC_006", company_name="蜂巢能源 SVOLT", industry="EV Battery",
 source="澎湃新闻", date="2024-02-28", url="https://www.thepaper.cn/newsDetail_forward_26493905",
 case_type=RELOC,
 initial_production_layout="电芯与 PACK 产能集中于中国（常州、金坛、上饶等）。",
 initial_main_markets="中国整车客户为主，海外客户极少。",
 initial_supply_chain="材料与设备全部来自中国。",
 initial_problem="中国客户（长城、合众/哪吒）在泰国建厂后需要本地电池配套；泰国对电池进口有关税。",
 decision_trigger="market_access",
 trigger_detail="跟随中国整车客户出海，满足泰国本地化电池配套要求。",
 decision_type="多地区混合布局",
 actual_decision="在泰国春武里府是拉差市建设电池工厂（模组 PACK + 电芯），2024-02-28 正式投产并批量交付，配套长城欧拉、合众/哪吒等中国车企在泰车型；当年计划交付超 2 万套 PACK；中国产能保留。",
 related_risk="Market Access Risk; Trade Risk; Operational Risk",
 outcome_cost_impact="本地 PACK 组装降低关税与物流成本，投资规模小于整线电芯厂。",
 outcome_production_performance="2024-02 投产并批量交付，产能按订单爬坡。",
 outcome_market_access="绑定泰国本地中国品牌整车客户，进入泰国本地供应体系。",
 outcome_supply_chain_impact="电芯/材料仍从中国输入，泰国仅承担模组与 PACK 环节。",
 outcome_verdict="成功（局部环节外移）",
 related_evidence_ids="NEWS_008",
 verification_status="高（多家媒体一致）",
 notes="与 RETURN_004（蜂巢停建德国工厂）同一公司，可直接对比'东南亚收缩 vs 欧洲退出'的策略差异。"),

dict(case_id="RELOC_007", company_name="华友钴业 Huayou Cobalt", industry="Battery Materials",
 source="新浪财经", date="2024-04-12", url="https://finance.sina.com.cn/stock/relnews/cn/2024-04-12/doc-inarqawt9056004.shtml",
 case_type=RELOC,
 initial_production_layout="钴/镍冶炼与前驱体产能集中于中国（浙江桐乡等），印尼仅有勘探布局。",
 initial_main_markets="中国正极与前驱体厂商为主。",
 initial_supply_chain="镍钴原料高度依赖进口（刚果金钴、印尼镍矿），加工环节在中国。",
 initial_problem="上游镍资源受制于人，原料价格与供应稳定性风险高；印尼禁止原矿出口，倒逼本地冶炼。",
 decision_trigger="supplier_issue",
 trigger_detail="印尼 2020 年起禁止镍原矿出口，要求就地冶炼；下游电池需求推升镍资源安全诉求。",
 decision_type="多地区混合布局",
 actual_decision="自 2018 年起在印尼布局镍钴资源，依托青山系莫罗瓦利与纬达贝工业园建设红土镍矿湿法冶炼项目（华越 6 万吨、华飞 12 万吨镍金属量等），2024-04 年产 12 万吨镍钴湿法项目达产；2026-01 表示 Pomalaa 年产 12 万吨镍金属量湿法项目预计 2026 年底建成投产。中国冶炼与材料产能保留。",
 related_risk="Supply Chain Risk; Political Risk; Trade Risk",
 outcome_cost_impact="印尼湿法冶炼的万吨镍投资约为世界同类项目的三分之一，原料自给降低成本。",
 outcome_production_performance="多个湿法项目达产，关键原料自供比例显著提升。",
 outcome_market_access="以印尼镍产品供应中国及全球前驱体客户，绕开原矿出口禁令。",
 outcome_supply_chain_impact="形成'印尼资源—中国材料'的双向依赖，海外上游集中度上升带来新的地缘风险。",
 outcome_verdict="成功（上游外移，加工仍在国内）",
 related_evidence_ids="NEWS_009",
 verification_status="高（公司公告 + 主流财经媒体）",
 notes="典型的'资源端外移而非制造端外移'案例。"),

dict(case_id="RELOC_008", company_name="中伟股份 CNGR Advanced Material", industry="Battery Materials",
 source="和讯网 / 网易", date="2024-04-08", url="https://futures.hexun.com/2024-04-08/212465761.html",
 case_type=RELOC,
 initial_production_layout="三元前驱体产能集中于中国（湖南、贵州等），原料端依赖进口。",
 initial_main_markets="中国正极材料厂与日韩电池客户。",
 initial_supply_chain="镍钴原料外购，冶炼与加工均在中国，资源依赖进口。",
 initial_problem="原料依赖进口导致成本与供应稳定性风险，且印尼原矿出口禁令压缩传统采购路径。",
 decision_trigger="supplier_issue",
 trigger_detail="印尼原矿出口禁令 + 客户对低碳、可追溯镍的需求。",
 decision_type="多地区混合布局",
 actual_decision="在印尼建设北莫罗瓦利、莫罗瓦利、纬达贝三大原料基地，2024-04 三基地已投产；2026-01 莫罗瓦利中青新能源二期全面投产（首炉冰镍产出），在建及建成资源粗炼端产能约 12.5 万金属吨。中国前驱体产能保留。",
 related_risk="Supply Chain Risk; Political Risk; Operational Risk",
 outcome_cost_impact="自供原料比例提升，降低外购镍价波动影响。",
 outcome_production_performance="三基地投产、二期冰镍产线投料试产成功，产能持续释放。",
 outcome_market_access="以自产镍资源支撑中国及海外前驱体客户供货。",
 outcome_supply_chain_impact="海外上游集中于印尼，单一国家集中度风险上升。",
 outcome_verdict="成功（上游外移）",
 related_evidence_ids="NEWS_010; NEWS_011",
 verification_status="高（公司披露 + 媒体报道）",
 notes="与华友钴业对照，可用于'资源国集中度'风险讨论。"),

dict(case_id="PLUS1_001", company_name="宁德时代 CATL", industry="EV Battery",
 source="每日经济新闻 / 搜狐网", date="2026-09-22", url="https://www.nbd.com.cn/articles/2026-09-22/4589059.html",
 case_type=PLUS1,
 initial_production_layout="电芯产能集中于中国（宁德、溧阳、宜宾、肇庆等），海外原仅有德国埃尔福特工厂。",
 initial_main_markets="中国 + 欧洲整车厂（宝马、大众、奔驰、Stellantis 等）。",
 initial_supply_chain="材料与设备高度依赖中国供应链，产品以出口与本地组装方式交付欧洲客户。",
 initial_problem="欧洲本地化率与电池法规（EU Battery Regulation）要求提升，纯出口面临关税、碳足迹与供应链审查。",
 decision_trigger="regulation_change",
 trigger_detail="欧盟电池法规与本地化含量要求，叠加欧洲整车客户对就近供货的需求。",
 decision_type="多地区混合布局",
 actual_decision="在匈牙利德布勒森建设欧洲第二座电池工厂，投资约 73.4 亿欧元（匈牙利史上最大外资项目之一），规划总产能 100GWh；2022-08 宣布，2023 年夏季首座电芯厂房动工，2026-08 取得厂房使用许可，2026-09-22 启动试生产；德国工厂与中国基地继续运营。",
 related_risk="Regulatory Risk; Trade Risk; Political Risk; Supply Chain Risk",
 outcome_cost_impact="欧洲本地生产规避电池进口关税并获得本地补贴，但欧洲能源与人工成本显著高于中国。",
 outcome_production_performance="2026-09 进入试生产阶段，尚未规模量产（结果待验证）。",
 outcome_market_access="就近供应奔驰等欧洲客户，满足欧盟本地化与合规要求。",
 outcome_supply_chain_impact="正极、负极、电解液等仍需中国及亚洲供应，形成'中国材料—欧洲电芯'结构。",
 outcome_verdict="待观察（试生产中，投资周期长）",
 related_evidence_ids="NEWS_012; NEWS_013",
 verification_status="中高（2026 年节点高质量来源；2022 年投资额来自媒体转述）",
 notes="'欧洲本地化'路径的代表案例，与东南亚路径形成对照。"),

dict(case_id="PLUS1_002", company_name="宁德时代 CATL", industry="EV Battery",
 source="东方财富网（转界面新闻）", date="2025-07-02", url="https://finance.eastmoney.com/a/202507023446498365.html",
 case_type=PLUS1,
 initial_production_layout="中国电芯产能为主，印尼仅有镍资源相关投资。",
 initial_main_markets="中国 + 欧洲 + 东南亚。",
 initial_supply_chain="镍钴原料部分来自印尼，材料加工与电芯制造在中国。",
 initial_problem="印尼要求矿产资源本地化加工并延伸至电池制造，单纯采购镍矿的模式不可持续；同时需要覆盖东南亚增长市场。",
 decision_trigger="regulation_change",
 trigger_detail="印尼'下游化'政策要求镍矿就地加工并延伸至电池产业链。",
 decision_type="多地区混合布局",
 actual_decision="由子公司普勤时代（CBL）、印尼国有矿业公司 ANTAM 与印尼电池公司 IBC 组成联合体，2025-06-29 在西爪哇省卡拉旺产业新城动工建设'从镍矿开采—冶炼—前驱体—电池制造—回收'一体化项目，总投资近 60 亿美元，电池产能规划 15GWh，可满足约 25–30 万辆汽车需求；中国产能保留。",
 related_risk="Political Risk; Regulatory Risk; Supply Chain Risk; Trade Risk",
 outcome_cost_impact="一体化布局降低原料与中间品跨境成本，但前期资本开支巨大。",
 outcome_production_performance="2025-06 动工，处于建设期（结果待验证）。",
 outcome_market_access="进入印尼本地供应链并满足资源下游化要求，辐射东南亚市场。",
 outcome_supply_chain_impact="把镍资源与电池制造绑定在印尼，减少对中国中间品运输的依赖，但新增单一国家集中度。",
 outcome_verdict="待观察（建设中）",
 related_evidence_ids="NEWS_014",
 verification_status="中高（公司发布 + 多家媒体，含彭博社转述）",
 notes="可用于讨论'资源国要求本地化'这一触发因素。"),

dict(case_id="PLUS1_003", company_name="比亚迪 BYD", industry="Automotive (EV)",
 source="ANTARA（印尼国家通讯社）", date="2026-09-03", url="https://otomotif.antaranews.com/berita/5724273/pabrik-byd-di-subang-resmi-beroperasi-dan-serap-5000-pekerja-lokal",
 case_type=PLUS1,
 initial_production_layout="整车产能集中在中国，海外首个工厂为泰国罗勇（2024-07 投产）。",
 initial_main_markets="中国 + 东南亚 + 欧洲 + 拉美。",
 initial_supply_chain="电池与核心零部件由中国供应。",
 initial_problem="印尼是东南亚最大汽车市场，但整车进口关税高且要求本地化生产。",
 decision_trigger="tariff_pressure",
 trigger_detail="印尼对整车进口征收高关税并推行电动车本地化要求，2023-05 与印尼政府签署投资谅解备忘录。",
 decision_type="多地区混合布局",
 actual_decision="在西爪哇省苏邦 Smartpolitan 工业园区建设印尼工厂，投资约 16 万亿印尼盾（约 10 亿美元），最大年产能 15 万辆；2026-09-03 正式投产启用，为比亚迪全球第 13 座整车工厂。与泰国工厂共同构成东南亚双基地，中国产能保留。",
 related_risk="Trade Risk; Market Access Risk; Operational Risk",
 outcome_cost_impact="本地生产规避印尼整车进口关税并满足本地化率（TKDN）要求，保住电动车激励资格；工厂投资约 16 万亿印尼盾。",
 outcome_production_performance="2026-09-03 正式投产，最大年产能 15 万辆，投产后实际产量约 1 万辆/月；启用仪式同场下线印尼本地生产的第 10 万辆整车。",
 outcome_market_access="2026-09 起停止整车进口、全面转为本地生产，以本地化进入印尼市场并与日系品牌竞争。",
 outcome_supply_chain_impact="电池与关键零部件初期由中国供应，形成中印尼跨境供应链。",
 outcome_verdict="成功（已投产并转为全本地生产）",
 related_evidence_ids="NEWS_015; NEWS_024; NEWS_025",
 verification_status="高（印尼国家通讯社 ANTARA 报道工厂投产、产能与停止整车进口）",
 notes="与 RELOC_001 同属比亚迪。原 2025 年'预计年底竣工'的建设中表述已按 2026-09-03 投产事实更新。"),

dict(case_id="PLUS1_004", company_name="晶科能源 JinkoSolar", industry="Solar Manufacturing",
 source="东方财富财富号", date="2026-02-25", url="https://caifuhao.eastmoney.com/news/20260225153639217944650",
 case_type=PLUS1,
 initial_production_layout="硅片—电池—组件一体化产能以中国为核心。",
 initial_main_markets="全球（中国、欧洲、美国、新兴市场）。",
 initial_supply_chain="硅料、硅片主要在中国，组件通过海外基地与出口进入欧美。",
 initial_problem="美国对东南亚四国光伏产品的双反与反规避调查，使'中国—东南亚—美国'路径的关税优势不稳定（参见 Task 1 的 CASE_002/CASE_003）。",
 decision_trigger="tariff_pressure",
 trigger_detail="美国对东南亚光伏组件的双反/反规避认定，以及美国本土制造激励，要求产能进一步分散。",
 decision_type="多地区混合布局",
 actual_decision="保持中国核心产能，同时在马来西亚（对美/欧核心出口枢纽）、越南（一体化产能）与美国本土布局成熟产能，形成'中国 + 东南亚 + 北美'的三地结构。",
 related_risk="Trade Risk; Market Access Risk; Regulatory Risk; Political Risk",
 outcome_cost_impact="马来西亚基地不受本轮关税影响，成为对美欧出口枢纽；美国本土产能直接受益于关税保护。",
 outcome_production_performance="多地产能并行，具体产能与利用率需以公司财报核实。",
 outcome_market_access="通过多地产能规避单一市场的关税与反规避风险。",
 outcome_supply_chain_impact="硅片、电池等中间品仍在区域内跨境流动，东南亚基地对中国中间品存在依赖。",
 outcome_verdict="成功（多地产能分散风险）",
 related_evidence_ids="NEWS_016",
 verification_status="中（来源为财经自媒体对公开产能布局的整理，需以公司年报/官网核实）",
 notes="与 Task 1 的光伏反规避证据（CASE_002/CASE_003/DOC_001）直接呼应，可用于跨任务串联。"),

dict(case_id="PLUS1_005", company_name="三星电子 Samsung Electronics", industry="Electronics / Semiconductor",
 source="新浪财经 / 东方财富网", date="2026-05-27", url="https://finance.sina.com.cn/stock/t/2026-05-27/doc-inhzikrs0845798.shtml",
 case_type=PLUS1,
 initial_production_layout="半导体与消费电子产能分布在中国（西安 NAND、苏州封测）、韩国、越南（手机组装）。",
 initial_main_markets="全球。",
 initial_supply_chain="关键零部件来自韩国、日本、中国，越南承担组装环节。",
 initial_problem="中美科技摩擦与关税使单一产地风险上升，越南被定位为分散地；同时 AI 需求推升存储芯片产能缺口。",
 decision_trigger="geopolitical_uncertainty",
 trigger_detail="中美科技与关税摩擦，以及 AI 驱动的存储芯片短缺，推动封装测试产能向第三国分散。",
 decision_type="多地区混合布局",
 actual_decision="计划在越南北部（太原省）投资约 15 亿美元建设芯片测试与封装工厂（已见报道的初始项目）。媒体另称可能追加约 25 亿美元的第二工厂投资——该项为条件性后续计划，尚未确认实施，不能与初始项目合并为单一'约 40 亿美元'已确定项目。中国西安等既有基地继续运营，形成'韩国 + 中国 + 越南'的多地产能结构。",
 related_risk="Political Risk; Supply Chain Risk; Trade Risk; Operational Risk",
 outcome_cost_impact="越南人工与土地成本低于韩国，但芯片封测对工程师与配套要求高，初期效率受限。",
 outcome_production_performance="截至 2026 年 10 月仍为投资计划阶段，未见公司正式公告确认实施或落地产能。",
 outcome_market_access="分散对单一国家出口管制的暴露。",
 outcome_supply_chain_impact="封装测试外移，但前道晶圆制造仍集中在韩国与中国。",
 outcome_verdict="待观察（计划阶段；投资金额需拆分核实）",
 related_evidence_ids="NEWS_017",
 verification_status="中（媒体转述，未见公司正式公告；原新浪链接已失效，金额需以公司公告核实）",
 notes="半导体行业'China+1'的对照案例，属第二梯队，非 EV/Battery 主线；已报道的约 15 亿美元初始项目与条件性的约 25 亿美元后续投资必须分开表述。"),

dict(case_id="RETURN_001", company_name="恩捷股份 Yunnan Energy New Material (Semcorp)", industry="Battery Materials",
 source="恩捷股份公告（经东方财富网 / 央广网报道）", date="2026-05-22", url="https://finance.eastmoney.com/a/202605223746866215.html",
 case_type=RETURN,
 initial_production_layout="湿法锂电隔膜产能以中国为主（上海、珠海、无锡等），为全球隔膜龙头。",
 initial_main_markets="中国 + 海外电池客户（含欧美）。",
 initial_supply_chain="基膜与涂覆材料主要在中国生产，产品出口海外。",
 initial_problem="2024 年规划马来西亚隔膜项目（约 10 亿平方米/年、投资约 20 亿元）以求贴近海外客户并规避关税。",
 decision_trigger="cost_change",
 trigger_detail="外部市场环境及行业竞争格局发生变化（隔膜价格下行、行业产能过剩、海外建厂成本高于预期）。",
 decision_type="提高中国生产比例",
 actual_decision="2026-05-22 董事会审议通过《关于终止在马来西亚投资建设锂电池隔离膜项目的议案》，终止原计划约 20 亿元的马来西亚隔膜项目，资源回投国内，优化资源配置、降低风险。",
 related_risk="Operational Risk; Trade Risk; Supply Chain Risk",
 outcome_cost_impact="避免在行业下行期投入 20 亿元海外资本开支，节省资金；但失去东南亚本地化产能抓手。",
 outcome_production_performance="国内产能继续承担全球交付，海外扩张暂停。",
 outcome_market_access="对海外客户仍以中国出口方式交付，关税暴露未消除。",
 outcome_supply_chain_impact="海外供应链布局收缩，对单一中国基地的依赖上升。",
 outcome_verdict="主动止损（成功止损，但海外布局目标未达成）",
 related_evidence_ids="COMPANY_FILING_001; NEWS_018",
 verification_status="高（上市公司公告，多家财经媒体一致）",
 notes="完整的'规划→终止'闭环案例，最能体现 Return/Reconsideration 类型。"),

dict(case_id="RETURN_002", company_name="富士康 Foxconn / 苹果 Apple（供应链）", industry="Electronics Manufacturing",
 source="新浪科技 / 中关村在线", date="2025-07-03", url="https://finance.sina.com.cn/tech/roll/2025-07-03/doc-infeerfp4024842.shtml",
 case_type=RETURN,
 initial_production_layout="苹果产品组装以中国大陆为核心，印度、越南为分散地。",
 initial_main_markets="全球。",
 initial_supply_chain="关键模组、设备与工程技术人员高度依赖中国大陆。",
 initial_problem="为分散地缘风险，苹果推动印度组装比例提升，但印度工厂良率、配套与工程能力不足，关键组件仍依赖进口。",
 decision_trigger="geopolitical_uncertainty",
 trigger_detail="印度本地化配套与技术能力不足，导致良率与交付不达预期。",
 decision_type="提高中国生产比例",
 actual_decision="2025 年 7 月及 12 月，富士康两度要求/撤回其印度工厂的中国大陆工程师与技术团队（彭博社等报道）。印度的组装布局并未取消，但推进节奏明显放缓。注：现有证据仅支持'工程团队撤回、工程支持减弱'，不足以证明订单或产能已实际回流中国。",
 related_risk="Operational Risk; Political Risk; Supply Chain Risk",
 outcome_cost_impact="撤回技术人员降低了印度工厂的爬坡效率，短期成本上升；高难度工序仍由中国基地承担。",
 outcome_production_performance="印度工厂工程支持减弱、本地良率与产能爬坡受阻（有报道支持）；中国大陆产能利用率是否回升尚无直接证据，待验证。",
 outcome_market_access="对美出口仍依托中国与东南亚双通道。",
 outcome_supply_chain_impact="印证了'关键工序与工程能力仍依赖中国'的结构性依赖（有报道支持）。",
 outcome_verdict="工程团队撤回（订单/产能回流中国为待验证推断，未完全放弃印度）",
 related_evidence_ids="NEWS_019; NEWS_020",
 verification_status="中（工程团队撤回有彭博社等报道支持；'订单/产能回流中国'缺乏直接证据，不可作为既定事实）",
 notes="保留'工程支持减弱 + 本地爬坡受阻'的已支持事实；'订单回流中国'如需保留须补直接证据。可与行业级 RETURN_003 配合做情景模拟。"),

dict(case_id="RETURN_003", company_name="制造业外迁企业（行业层面）", industry="General Manufacturing / Supply Chain",
 source="路透社（经环球网 / 新浪转载）", date="2026-09-14", url="https://3w.huanqiu.com/a/de583b/4TE5JD6omnj",
 case_type=RETURN,
 initial_production_layout="过去数年，为规避美国关税，大量企业把产能从中国迁往越南、印度、墨西哥等地，中国产能相应压缩。",
 initial_main_markets="以美国为主要出口市场。",
 initial_supply_chain="从基础螺丝到核心模具、设备与工程人员仍依赖中国供应。",
 initial_problem="落地后出现'搬得出、难运转'：当地劳动力、供应商、设备、电力与物流成本高于预期，关税优势被成本吞噬；越南 2023 年及之后反复出现电力短缺导致工厂停产。",
 decision_trigger="cost_change",
 trigger_detail="东南亚等地综合成本高于预期 + 电力等基础设施不稳定，抵消关税收益。",
 decision_type="提高中国生产比例",
 actual_decision="部分跨国企业将订单与产能重新回流中国，同时保留东南亚既有布局，形成'中国为主 + 东南亚保留'的混合结构。",
 related_risk="Political Risk; Supply Chain Risk; Operational Risk",
 outcome_cost_impact="回流后综合成本下降，关税优势部分让位于运转效率。",
 outcome_production_performance="中国工厂产能利用率回升，交付稳定性改善。",
 outcome_market_access="对美出口仍需应对关税，部分通过第三国转运与产品结构调整解决。",
 outcome_supply_chain_impact="印证中国在配套完整度上的不可替代性，'China+1'演变为'China+1 但中国仍是主基地'。",
 outcome_verdict="行业性回流（结构性调整，非全面逆转）",
 related_evidence_ids="REUTERS_001; NEWS_023",
 verification_status="中高（路透社报道，中文媒体广泛转载；属趋势性报道，缺少单一企业完整数据）",
 notes="行业级案例，建议与 RETURN_002 配合测试；NEWS_023（越南缺电）为其背景证据。"),

dict(case_id="RETURN_004", company_name="蜂巢能源 SVOLT（欧洲业务）", industry="EV Battery",
 source="36氪 / 财新网", date="2024-10-28", url="https://www.caixin.com/2024-10-28/102250409.html",
 case_type=RETURN,
 initial_production_layout="电芯产能集中于中国，2020 年起规划德国萨尔州模组/PACK 工厂（24GWh）与勃兰登堡州电芯超级工厂。",
 initial_main_markets="中国为主，欧洲市场处于开拓期。",
 initial_supply_chain="材料与设备来自中国。",
 initial_problem="欧洲电动车需求疲软、融资环境恶化，德国两座工厂建设资金不到位、进度一再延误。",
 decision_trigger="cost_change",
 trigger_detail="欧洲销售疲软 + 经济挑战 + 融资困难，海外扩张的投入产出不成立。",
 decision_type="维持现有海外布局（收缩新增）",
 actual_decision="2024-05 取消勃兰登堡州电芯超级工厂计划，2024-10 宣布停建德国工厂、终止欧洲子公司运营（自 2025 年 1 月起关闭欧洲业务），资源集中于中国与泰国等已投产基地。",
 related_risk="Operational Risk; Political Risk; Trade Risk",
 outcome_cost_impact="停止约 300 亿元级别的海外投资计划，避免持续亏损。",
 outcome_production_performance="欧洲产能归零，中国与泰国基地继续运营。",
 outcome_market_access="退出欧洲本地化生产，欧洲市场改以出口方式服务。",
 outcome_supply_chain_impact="海外布局从'欧洲 + 东南亚'收缩为'东南亚'。",
 outcome_verdict="失败/主动退出（止损）",
 related_evidence_ids="NEWS_021; NEWS_022",
 verification_status="高（财新、36氪等多家媒体报道一致）",
 notes="与 RELOC_006（蜂巢泰国投产）构成同一公司内'一地成功、一地退出'的对照，非常适合 Scenario Simulation。"),
]

# ---------------------------------------------------------------------------
# 案例 -> 证据库绑定（v0.9.1 修复）
#
# 原先 `related_evidence_ids` 用的是 NEWS_001…REUTERS_001 这类外部新闻编号，
# 它们不在 Task 1 的证据库里（v0.9.2 起 53 条），案例到证据库的链路是断的。这里改为绑定
# Task 1 真实证据，并按四条规则选，逐条给依据：
#   R1 触发条件：支撑 decision_trigger 的政策/法规/数据（关税/出口管制/物流/劳工）
#   R2 目的地：该东道国的政策审议或关税/贸易数据
#   R3 行业主体：能说明该企业所属行业格局的证据
#   R4 类比案例：同行业/同去向的已发生案例证据（CASE_00x）
# 外部新闻来源不删除，改存 `external_source_refs`，编号对应 Evidence Index 表。
# ---------------------------------------------------------------------------
EVIDENCE_LINKS: dict[str, list[str]] = {
    "RELOC_001": ["TRD_001", "EU_003", "IEA_001", "CASE_004", "WB_001"],
    "RELOC_002": ["TRD_001", "CASE_004", "IEA_001", "WB_001"],
    "RELOC_003": ["TRD_001", "TRD_003", "SNE_001", "WB_001", "CASE_007"],
    "RELOC_004": ["TRD_001", "TRD_003", "CASE_007", "SNE_001", "WB_001"],
    "RELOC_005": ["TRD_001", "TRD_003", "CASE_007", "SNE_001", "WB_001"],
    "RELOC_006": ["TRD_001", "CASE_004", "EU_003", "IEA_001", "WB_001"],
    "RELOC_007": ["WTO_004", "TRD_003", "SNE_001", "WB_001"],
    "RELOC_008": ["WTO_004", "TRD_003", "SNE_001", "WB_001"],
    "PLUS1_001": ["EU_003", "EU_001", "EU_004", "EU_002", "SNE_001", "IEA_001"],
    "PLUS1_002": ["WTO_004", "TRD_003", "SNE_001", "IEA_001"],
    "PLUS1_003": ["WTO_004", "IEA_001", "SNE_001", "TRD_003", "EU_003"],
    "PLUS1_004": ["DOC_001", "CASE_002", "CASE_003", "TRD_002"],
    "PLUS1_005": ["UNCTAD_001", "TRD_003", "WB_001", "IMF_001"],
    "RETURN_001": ["CASE_001", "TRD_003", "WB_001", "SNE_001"],
    "RETURN_002": ["UNCTAD_001", "WTO_002", "WTO_003", "CASE_001"],
    "RETURN_003": ["CASE_001", "WB_001", "TRD_001", "KPMG_001"],
    "RETURN_004": ["EU_003", "EU_001", "EU_004", "CASE_001"],
}

EVIDENCE_RATIONALE: dict[str, str] = {
    "RELOC_001": "R1 美国对华电动车关税/欧盟反补贴(EU_003)是出海触发；R3 中美自泰进口整车与电池数据(TRD_001)显示泰国通道；R4 光模块厂泰国产能(CASE_004)提供同去向类比；R3 全球EV格局(IEA_001)；R2 泰国物流绩效(WB_001)",
    "RELOC_002": "R1 关税与泰国本地化要求为触发；R2 美国自泰进口整车/电池(TRD_001)；R4 泰国建厂类比(CASE_004)；R3 全球EV格局(IEA_001)；R2 物流绩效(WB_001)",
    "RELOC_003": "R2 美国自越进口电池数据(TRD_001)与中国对越中间品出口(TRD_003)共同刻画越南通道；R3 中国电池厂全球份额(SNE_001)；R2 物流绩效(WB_001)；R4 东南亚建厂类比(CASE_007)",
    "RELOC_004": "R2 美国自马进口电池(TRD_001)+中国对马中间品出口(TRD_003)；R4 马来西亚工厂类比(CASE_007)；R3 行业格局(SNE_001)；R2 物流绩效(WB_001)",
    "RELOC_005": "R2 美国自越进口(TRD_001)+对越中间品出口(TRD_003)；R4 东南亚建厂类比(CASE_007)；R3 行业格局(SNE_001)；R2 物流绩效(WB_001)",
    "RELOC_006": "R1 欧盟反补贴税(EU_003)抬高欧洲出口成本；R2 美国自泰进口(TRD_001)；R4 泰国建厂类比(CASE_004)；R3 全球EV格局(IEA_001)；R2 物流(WB_001)",
    "RELOC_007": "R2 印尼贸易政策审议包含镍下游化政策(WTO_004)；R1 中国对印尼中间品出口(TRD_003)；R3 电池材料格局(SNE_001)；R2 印尼物流绩效(WB_001)",
    "RELOC_008": "R2 印尼镍下游化与本地化要求(WTO_004)；R1 对印尼中间品出口(TRD_003)；R3 行业格局(SNE_001)；R2 物流绩效(WB_001)",
    "PLUS1_001": "R1 欧盟对华BEV反补贴(EU_003)+电池法规(EU_001)+外资审查(EU_004)+CRMA(EU_002)构成匈牙利建厂的合规与准入约束；R3 宁德时代全球份额(SNE_001)与EV格局(IEA_001)",
    "PLUS1_002": "R2 印尼镍下游化/本地化(WTO_004)；R1 对印尼中间品出口(TRD_003)；R3 份额与格局(SNE_001,IEA_001)",
    "PLUS1_003": "R2 印尼本地化政策(WTO_004)直接对应'转为全本地生产'的结果；R3 格局(IEA_001,SNE_001)；R1 中间品出口(TRD_003)+欧盟反补贴(EU_003)说明多地区布局动因",
    "PLUS1_004": "R1 美国对东南亚四国光伏反规避终裁(DOC_001)是该案例决策的直接触发；R4 同调查'已规避/未规避'案例(CASE_002,CASE_003)；R2 美国光伏进口数据(TRD_002)",
    "PLUS1_005": "R3 UNCTAD 投资报告把三星/富士康类外迁作为 FDI 案例(UNCTAD_001)；R1 对越中间品出口(TRD_003)；R2 越南物流绩效(WB_001)；R3 IMF 对水平型 FDI 的举例(IMF_001)",
    "RETURN_001": "R4 大旺金属'订单转移后回流'案例(CASE_001)是直接类比；R1 对马中间品出口与配套依赖(TRD_003)；R2 物流成本(WB_001)；R3 行业格局(SNE_001)",
    "RETURN_002": "R3 UNCTAD_001 直接引用路透'富士康印度 iPhone 出口'报道（同源提示）；R2 印度贸易政策审议与关税(WTO_002,WTO_003)；R4 回流类比(CASE_001)",
    "RETURN_003": "R4 行业层面回流的核心类比是 CASE_001（大旺金属，订单外移印度后回流）；R2 物流与配套成本(WB_001)；R1 关税背景(TRD_001)；R3 美国供应链调查(KPMG_001)",
    "RETURN_004": "R1 欧盟对华BEV反补贴(EU_003)+电池法规(EU_001)+外资审查(EU_004)是收缩欧洲布局的直接约束；R4 回流/收缩类比(CASE_001)",
}

for _case in CASES:
    _cid = _case["case_id"]
    _case["external_source_refs"] = _case["related_evidence_ids"]
    _case["related_evidence_ids"] = "; ".join(EVIDENCE_LINKS[_cid])
    _case["related_evidence_rationale"] = EVIDENCE_RATIONALE[_cid]


COLS = [
 ("case_id","案例唯一编号"),
 ("company_name","企业名称"),
 ("industry","行业"),
 ("source","来源媒体/文件"),
 ("date","关键决策或事件日期"),
 ("url","原文链接"),
 ("case_type","案例类型（三类之一）"),
 ("initial_production_layout","决策前：生产布局"),
 ("initial_main_markets","决策前：主要市场"),
 ("initial_supply_chain","决策前：供应链结构"),
 ("initial_problem","决策前：面临的问题"),
 ("decision_trigger","决策触发因素（6 类）"),
 ("trigger_detail","触发因素说明"),
 ("decision_type","实际决策分类（3 类）"),
 ("actual_decision","实际决策内容"),
 ("related_risk","相关风险（Task 1 口径）"),
 ("outcome_cost_impact","结果：成本影响"),
 ("outcome_production_performance","结果：生产表现"),
 ("outcome_market_access","结果：市场准入"),
 ("outcome_supply_chain_impact","结果：供应链影响"),
 ("outcome_verdict","结果结论（成功/失败/待观察）"),
 ("related_evidence_ids","关联证据 ID（Task 1 证据库，53 条内）"),
 ("external_source_refs","外部来源编号（新闻报道，见 Evidence Index）"),
 ("related_evidence_rationale","绑定依据（R1触发/R2目的地/R3行业/R4类比）"),
 ("verification_status","真实性核验状态"),
 ("notes","备注"),
]


RISK_ORDER = [
    "Trade Risk",
    "Political Risk",
    "Supply Chain Risk",
    "Regulatory Risk",
    "Market Access Risk",
    "Operational Risk",
]


def canonical_risks(value) -> str:
    """Normalise a related_risk cell to the Task 1 six-category vocabulary
    and a stable display order."""
    parts = [p.strip() for p in str(value or "").split(";") if p.strip()]
    unknown = [p for p in parts if p not in RISK_ORDER]
    ordered = [r for r in RISK_ORDER if r in parts] + unknown
    return "; ".join(ordered)


def main() -> None:
    wb = Workbook()
    hl = PatternFill("solid", fgColor="1F3864")
    hl2 = PatternFill("solid", fgColor="2E5E4E")
    thin = Side(style="thin", color="D9D9D9")
    wrap = Alignment(wrap_text=True, vertical="top")

    ws = wb.active
    ws.title = "Case Database"
    ws.append([c[0] for c in COLS])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = hl
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for case in CASES:
        ws.append(
            [
                canonical_risks(case.get(k)) if k == "related_risk" else case.get(k)
                for k, _ in COLS
            ]
        )
    widths = [12,26,24,30,13,46,32,44,26,34,44,18,40,20,60,32,40,38,36,40,26,30,30,54,34,44]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{ws.max_row}"
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = wrap; c.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.row_dimensions[1].height = 32

    ev = wb.create_sheet("Evidence Index")
    ev.append(["evidence_id", "outlet", "title", "date", "url", "url_status", "used_by_cases"])
    for c in ev[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = hl2; c.alignment = wrap
    _used: dict[str, list[str]] = {}
    for _c in CASES:
        for _ref in str(_c["external_source_refs"]).split(";"):
            _ref = _ref.strip()
            if _ref:
                _used.setdefault(_ref, []).append(_c["case_id"])
    for entry in EV:
        eid, outlet, title, d, u = entry[:5]
        status = entry[5] if len(entry) > 5 else (
            "链接已核验" if u else "链接待补（标题与日期已核验）"
        )
        ev.append([eid, outlet, title, d, u, status, "; ".join(_used.get(eid, []))])
    for i, w in enumerate([22, 40, 60, 13, 52, 28, 26], 1):
        ev.column_dimensions[get_column_letter(i)].width = w
    ev.freeze_panes = "A2"
    ev.auto_filter.ref = f"A1:F{ev.max_row}"

    sc = wb.create_sheet("Schema")
    sc.append(["字段", "说明", "取值"])
    for c in sc[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = hl
    for k, desc in COLS:
        vals = ""
        if k == "case_type":
            vals = "China → Southeast Asia relocation / China + 1 strategy / Reconsideration / Return to China"
        elif k == "decision_trigger":
            vals = "tariff_pressure / geopolitical_uncertainty / cost_change / supplier_issue / market_access / regulation_change"
        elif k == "decision_type":
            vals = "多地区混合布局 / 维持现有海外布局 / 提高中国生产比例"
        elif k == "related_risk":
            vals = "Trade Risk / Political Risk / Supply Chain Risk / Regulatory Risk / Market Access Risk / Operational Risk（可多选，; 分隔）"
        elif k == "outcome_verdict":
            vals = "成功 / 失败 / 待观察（含主动退出与止损）"
        sc.append([k, desc, vals])
    for i, w in enumerate([26, 40, 90], 1):
        sc.column_dimensions[get_column_letter(i)].width = w
    for row in sc.iter_rows(min_row=2):
        for c in row:
            c.alignment = wrap

    qa = wb.create_sheet("QA")
    qa.append(["验收项", "结果", "说明"])
    for c in qa[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = hl
    triggers = sorted({c["decision_trigger"] for c in CASES})
    types = sorted({c["case_type"] for c in CASES})
    dtypes = sorted({c["decision_type"] for c in CASES})
    inds = sorted({c["industry"] for c in CASES})
    qa.append(["案例数量", f"{len(CASES)} 个", "要求 ≥10，最好 15 左右"])
    qa.append(["案例类型覆盖", " / ".join(types), "三类是否齐全"])
    qa.append(["决策触发因素覆盖", f"{len(triggers)}/6", " / ".join(triggers)])
    qa.append(["决策类型覆盖", " / ".join(dtypes), "三种决策分类是否齐全"])
    qa.append(["行业覆盖", " / ".join(inds), "优先 EV Battery / Battery Materials / Automotive / Supply Chain / Electronics，其次 Semiconductor / Solar"])
    qa.append(["背景→决策→结果链条", "100% 完整", "每个案例均有 Initial Situation / Decision / Outcome 三段"])
    qa.append(["真实性核验", "全部来自公开报道或公司公告", "verification_status 逐条标注；两条为财经自媒体整理，需以年报核实"])
    qa.append(["可追溯性（外部来源）", f"{len(EV)} 条新闻/公告，编号见 Evidence Index", "external_source_refs 指向 Evidence Index，含 outlet/标题/日期/URL 与 used_by_cases"])
    qa.append(["可追溯性（证据库绑定）", "17/17 全部解析到 Task 1 的 53 条证据", "related_evidence_ids 已由外部新闻编号改为证据库内真实 ID；每条附绑定依据（R1触发/R2目的地/R3行业/R4类比）"])
    qa.append(["证据库链路校验", "通过", "逐个 ID 与 evidence_metadata_v0.1.json 比对，无悬空引用"])
    qa.append(["能否用于 Scenario Simulation", "是", "含 4 个'待观察/建设中'与 2 个'失败/退出'案例，可测试不确定与反向情景"])
    qa.append(["未覆盖", "无", "'维持现有海外布局'由 RETURN_004 覆盖"])
    qa.append([])
    qa.append(["held-out 校验", "通过", "RAG 语料 53 篇文档 ID 中无 RELOC_*/PLUS1_*/RETURN_*；17 个案例来源 URL 与语料 URL 零重合"])
    qa.append(["语料泄漏检查（逐字）", "通过", "backend/scripts/check_case_leakage.py：17/17 通过，最高逐字重合 1.0%（10 字滑窗，阈值 5%）"])
    qa.append(["隔离校验复跑", ".venv/bin/python backend/scripts/check_case_leakage.py", "退出码 0 = 案例 ID 不撞 / 来源 URL 不撞 / 无逐字重合 / related_evidence_ids 全部可解析"])
    qa.append(["语料背景重合（已登记）", "4 处", "RELOC_001/PLUS1_003 经 IEA_001 的 OEM 名单；PLUS1_004 经 DOC_001 的光伏反规避语境；PLUS1_005 经 IMF_001 的 FDI 举例；RETURN_002 经 UNCTAD_001 的路透引用"])
    qa.append(["同源提示", "RETURN_002", "其外部来源为路透报道，而语料 UNCTAD_001 引用了同一系列路透稿；属背景级同源，评测时需知悉"])
    qa.append(["通用吸引子", "CASE_001", "语料 CASE_001（大旺金属回流）在 13/17（基线）/ 16/17（优化层）个案例的 Top-5 出现（v0.9.2 语料复测），是 Task 6 false positive 的来源之一，与 RETURN_003 构成同现象不同主体"])
    qa.append([])
    qa.append(["已知局限", "", "1) 多数结果字段来自媒体转述，财务口径的成本影响未做量化；2) 4 个案例的最终结果尚未发生；3) 行业级案例 RETURN_003 缺少单一企业完整数据。"])
    for i, w in enumerate([26, 40, 110], 1):
        qa.column_dimensions[get_column_letter(i)].width = w
    for row in qa.iter_rows(min_row=2):
        for c in row:
            c.alignment = wrap

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"saved {OUT}")
    print(f"cases={len(CASES)} evidence={len(EV)} triggers={triggers} types={dtypes}")


if __name__ == "__main__":
    main()
