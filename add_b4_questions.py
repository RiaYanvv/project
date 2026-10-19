"""Close B4: give every evidence item a question gold.

- Q044: Vietnam / Malaysia / Thailand country-level political & investment risk
  -> MOFCOM_003 / MOFCOM_004 / MOFCOM_006
- Q045: India tariff/localisation baseline + political/compliance risk
  -> WTO_002 / WTO_003 / MOFCOM_005
- Q046: US Section 301 tariff + IRA/FEOC eligibility
  -> UST_001 / IRS_001
- Q023 already asks what the solar anti-circumvention case teaches; TRD_002 is
  the solar-component trade-flow dataset for that analogue, so it becomes a
  secondary gold rather than a new question.
"""
from __future__ import annotations

from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment

FILES = [Path("retrieval_questions.xlsx"), Path("task2_retrieval_evaluation_v0.7.xlsx")]
NEW = [
    (
        "Q044",
        "我们正在比较越南、马来西亚和泰国作为电池生产基地。除关税和客户要求外，三国在政治稳定性、外资审查、劳工与合规方面分别有哪些国别风险需要提前评估？",
        "Policy / Trade Risk",
        "investment_policy",
        "MOFCOM_003; MOFCOM_004; MOFCOM_006",
        "Medium",
    ),
    (
        "Q045",
        "我们准备在印度本地建厂服务当地市场。印度当前的进口关税与本地化政策基线是什么？同时，中资企业在印度投资还面临哪些政治与合规风险？",
        "Market Access",
        "investment_policy",
        "WTO_002; WTO_003; MOFCOM_005",
        "Medium",
    ),
    (
        "Q046",
        "一家中国电池企业把电芯或电池包出口到美国，并希望进入美国车企供应链。Section 301 关税和 IRA/FEOC 规则分别会带来哪些成本与资格限制？",
        "Policy / Trade Risk",
        "tariff",
        "UST_001; IRS_001",
        "Hard",
    ),
]


def append_rows(path: Path) -> None:
    wb = load_workbook(path)
    ws = wb["retrieval_questions"]
    header = [str(c.value).strip() for c in ws[1]]
    assert header[:6] == ["question_id", "question", "scenario_category",
                          "expected_topic", "expected_evidence_ids", "difficulty"]
    existing = {str(r[0].value).strip() for r in ws.iter_rows(min_row=2) if r[0].value}
    assert not (existing & {q[0] for q in NEW}), f"duplicate question id in {path}"

    template = ws[2]
    for row in NEW:
        r = ws.max_row + 1
        for c, value in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = copy(template[c - 1].font)
            cell.border = copy(template[c - 1].border)
            cell.fill = copy(template[c - 1].fill)
            cell.alignment = Alignment(vertical="top", wrap_text=c in (2,))
        ws.row_dimensions[r].height = 42

    # TRD_002 is the trade-flow half of the Q023 solar analogue.
    for r in ws.iter_rows(min_row=2):
        if str(r[0].value).strip() == "Q023":
            ids = str(r[4].value or "")
            if "TRD_002" not in ids:
                r[4].value = ids.rstrip("; ") + "; TRD_002"
            break
    else:
        raise KeyError("Q023 not found")

    if "evaluation_guide" in wb.sheetnames:
        guide = wb["evaluation_guide"]
        for r in guide.iter_rows(min_row=2):
            if str(r[0].value).strip() == "Question set":
                r[1].value = (
                    "46 realistic enterprise decision questions grounded in Task 1 evidence IDs "
                    "(30 written against v0.7/v0.8; Q031-Q040 added in v0.9; Q041-Q043 added for EU "
                    "evidence; Q044-Q046 added in B4 for MOFCOM_003-006, IRS_001 and UST_001 gold)."
                )
            elif str(r[0].value).strip() == "Category counts":
                r[1].value = ("Company Intelligence 8; Policy / Trade Risk 16; Supply Chain Risk 7; "
                              "Market Access 9; Scenario Simulation Support 6.")

    if "gold_revision_log" in wb.sheetnames:
        log = wb["gold_revision_log"]
        # Insert below the existing table header block.
        start = None
        for i, r in enumerate(log.iter_rows(min_row=1, values_only=True), start=1):
            if r and str(r[0]).strip() == "question_id":
                start = i + 1
                break
        if start is None:
            start = log.max_row + 1
        log.cell(row=start, column=1, value="Q044-Q046 + Q023/TRD_002")
        log.cell(row=start, column=2, value="2026-10-18")
        log.cell(row=start, column=3, value="B4: every evidence item must have a question gold; Q044-Q046 cover the four new MOFCOM guides plus UST_001/IRS_001, and TRD_002 is the solar-component trade-flow dataset used by the Q023 analogue.")
        log.cell(row=start, column=4, value="agent proposal — pending human review")
        log.cell(row=start, column=5, value="")

    wb.save(path)
    print(f"saved {path}: {ws.max_row - 1} questions")


def main() -> None:
    for path in FILES:
        append_rows(path)

    # Verify every evidence item now has at least one gold.
    from openpyxl import load_workbook

    meta_wb = load_workbook(
        "/Users/zhengyuanyuan/Desktop/project-data/data/metadata/evidence_battery_EV_screened_v0.9.xlsx",
        data_only=True,
    )
    meta_ws = meta_wb["sources"]
    mr = list(meta_ws.iter_rows(values_only=True))
    mh = [str(x) for x in mr[0]]
    ei = mh.index("evidence_id")
    ids = {str(r[ei]).strip() for r in mr[1:] if r[ei]}

    qwb = load_workbook("retrieval_questions.xlsx", data_only=True)
    qws = qwb["retrieval_questions"]
    qr = list(qws.iter_rows(values_only=True))
    qh = [str(x) for x in qr[0]]
    gi = qh.index("expected_evidence_ids")
    gold = set()
    for r in qr[1:]:
        for e in str(r[gi] or "").replace(";", ",").split(","):
            if e.strip():
                gold.add(e.strip())
    missing = sorted(ids - gold)
    print(f"evidence={len(ids)}  with-gold={len(ids) - len(missing)}  missing={missing}")


if __name__ == "__main__":
    main()
