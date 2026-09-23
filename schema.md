1、字段统一
统一使用：
company_name
home_country
target_markets
production_locations
decision_question
risk_level
evidence_ids

不要混用：
companyName
CompanyName
company-name之类

2、ID命名：
统一使用前缀
company_id: CMP-001
request_id: REQ-001
evidence_id: EVD-001
risk_id: RSK-001
scenario_id: SCN-001
assessment_id: ASM-001
conversation_id: CON-001
report_id: RPT-001

3、日期时间
2026-09-20
2026-09-20T14:30:00+08:00

4、国家地区
CN
VN
US
ID
IN
TH
MY

（注意前段可以显示China，只是说后端保存CN）

5、货币
USD
CNY
EUR
VND
IDR

6、百分比
统一0-100，整数
"production_share": 70
不要用70%

7、布尔值
true / false

8、空值
没有信息统一填null


