# B4 — Gold Coverage Audit

- 自动评测题：**46**
- Task 1 证据：**53**
- 至少有 1 道题 gold 指向的证据：**53 / 53**
- gold 引用但不存在于语料的 ID：**0**

## B4 新增题

| question_id | scenario | expected_topic | gold |
|---|---|---|---|
| Q044 | Policy / Trade Risk | investment_policy | MOFCOM_003; MOFCOM_004; MOFCOM_006 |
| Q045 | Market Access | investment_policy | WTO_002; WTO_003; MOFCOM_005 |
| Q046 | Policy / Trade Risk | tariff | UST_001; IRS_001 |

Q023 另追加 `TRD_002`（光伏组件贸易流，作为反规避类比的贸易数据）。Q044–Q046 已在 `Task2_manual_scoring_v4.xlsx` 中完成人工评分，但作为 B4 补充集单独报告，不混入 Q001–Q030 验收均值。

来源：`retrieval_questions.xlsx`、`task2_retrieval_evaluation_v0.7.xlsx`、`evidence_battery_EV_screened_v0.9.xlsx`。
