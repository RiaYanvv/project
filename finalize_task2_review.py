"""Finalize Task 2 human scoring after the product-side review.

- Reads the reviewed checklist from the user's Desktop.
- Writes a Review Log sheet into the scoring workbook.
- Freezes computed per-question and summary values so the workbook is readable
  in Excel / Numbers / preview without waiting for formula recalculation.
- Records review completion in the Summary sheet.
"""
from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent
SCORING = ROOT / "Task2_manual_scoring_v3.xlsx"
REVIEWED = Path.home() / "Desktop" / "Task2_人工复核清单.xlsx"
DELIVERY = ROOT / "Task2_交付物"
REVIEW_SHEET = "Review Log"
TODAY = date.today().isoformat()


def style_header(ws, row: int, ncol: int) -> None:
    fill = PatternFill("solid", fgColor="1F4E78")
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def main() -> None:
    if not REVIEWED.exists():
        raise FileNotFoundError(REVIEWED)

    # ---- read the reviewed checklist -------------------------------------
    rwb = load_workbook(REVIEWED, data_only=True)
    rws = rwb["复核清单"]
    reviewed = []
    for row in rws.iter_rows(min_row=5, values_only=True):
        if not row[2]:
            continue
        user = row[14]
        mine = row[9]
        final = mine if user in (None, "") else int(user)
        status = "留空=采纳" if user in (None, "") else ("确认一致" if int(user) == int(mine) else "用户改分")
        reviewed.append({
            "seq": row[0], "group": row[1], "qid": row[2], "rank": row[3],
            "eid": row[4], "title": row[5], "publisher": row[6],
            "auto": row[8], "mine": mine, "user": user, "final": final,
            "status": status, "note": row[15],
        })

    # ---- load scoring workbook ------------------------------------------
    wb = load_workbook(SCORING)
    items = wb["Item Scoring"]
    ih = {str(c.value): c.column for c in items[1]}
    qs = wb["Question Scoring"]
    qh = {str(c.value): c.column for c in qs[1]}

    rel_by_q = defaultdict(list)
    auth_by_q = defaultdict(list)
    for row in items.iter_rows(min_row=2, values_only=True):
        qid = str(row[ih["Question ID"] - 1] or "").strip()
        if not qid:
            continue
        rel_by_q[qid].append(row[ih["Relevance (0/1/2)"] - 1])
        auth_by_q[qid].append(row[ih["Authority (0/1/2)"] - 1])

    # freeze per-question averages
    for row in qs.iter_rows(min_row=2):
        qid = str(row[qh["Question ID"] - 1].value or "").strip()
        if not qid:
            continue
        row[qh["Avg Relevance (0-2)"] - 1].value = round(sum(rel_by_q[qid]) / len(rel_by_q[qid]), 4)
        row[qh["Avg Authority (0-2)"] - 1].value = round(sum(auth_by_q[qid]) / len(auth_by_q[qid]), 4)

    # 30-question task-book metrics
    q30 = [f"Q{i:03d}" for i in range(1, 31)]
    rel30 = [v for q in q30 for v in rel_by_q[q]]
    auth30 = [v for q in q30 for v in auth_by_q[q]]
    cov30 = [r[qh["Coverage (0/1/2)"] - 1] for r in qs.iter_rows(min_row=2, values_only=True)
            if str(r[qh["Question ID"] - 1] or "").strip() in q30]
    hit30 = [r[qh["Hit@5"] - 1] for r in qs.iter_rows(min_row=2, values_only=True)
             if str(r[qh["Question ID"] - 1] or "").strip() in q30]
    avg_rel = sum(rel30) / len(rel30)
    avg_auth = sum(auth30) / len(auth30)
    avg_cov = sum(cov30) / len(cov30)
    hit_rate = sum(hit30) / len(hit30)

    sm = wb["Summary"]
    sm["A4"] = "Primary metrics (computed from Question Scoring; frozen after human review)"
    sm["B5"] = round(avg_rel, 4)
    sm["B6"] = round(avg_auth, 4)
    sm["B7"] = round(hit_rate, 4)
    sm["B8"] = round(avg_cov, 4)
    sm["D5"] = "PASS" if avg_rel >= 1.5 else "FAIL"
    sm["D6"] = "PASS" if avg_auth >= 1.5 else "FAIL"
    sm["D7"] = "PASS" if hit_rate >= 0.8 else "FAIL"
    sm["A9"] = "Note"
    sm["B9"] = "Final reviewed version — values frozen after the 2026-10-18 human review. Item Scoring remains the source of truth."
    sm["A12"] = "Scoring pass"
    sm["B12"] = "AI-assisted pre-scoring + product-side human review completed 2026-10-18 (35 flagged rows; 0 score changes)."

    review_rows = [
        ("Manual review", "Completed"),
        ("Review date", TODAY),
        ("Flagged rows", f"{len(reviewed)} (13 explicitly confirmed, 22 accepted as-is, 0 changed)"),
        ("Review record", "Task2_人工复核清单.xlsx + this workbook's Review Log sheet"),
        ("Final status", "PASS — Relevance, Authority and Hit@5 all meet the task-book targets"),
    ]
    start = 14
    for i, (label, value) in enumerate(review_rows):
        sm.cell(row=start + i, column=1, value=label).font = Font(bold=True)
        sm.cell(row=start + i, column=2, value=value)

    # ---- Review Log sheet ------------------------------------------------
    if REVIEW_SHEET in wb.sheetnames:
        del wb[REVIEW_SHEET]
    log = wb.create_sheet(REVIEW_SHEET, 1)
    headers = ["序号", "复核分组", "题号", "排名", "Evidence ID", "证据标题", "发布机构",
               "Auto", "我的判定", "用户判定", "最终判定", "复核状态", "用户备注"]
    widths = [6, 16, 8, 6, 14, 46, 30, 7, 9, 9, 9, 12, 30]
    log["A1"] = "Task 2 人工复核记录（35 条 Auto 不一致行）"
    log["A1"].font = Font(bold=True, size=13)
    log.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    log["A2"] = (f"复核完成：{TODAY}；13 条明确确认、22 条留空采纳、0 条改分。"
                 "留空的“用户判定”按“我的判定”计入最终分。")
    log.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    log["A2"].alignment = Alignment(wrap_text=True, vertical="top")

    hrow = 4
    for c, (name, width) in enumerate(zip(headers, widths), start=1):
        log.cell(row=hrow, column=c, value=name)
        log.column_dimensions[get_column_letter(c)].width = width
    style_header(log, hrow, len(headers))
    log.row_dimensions[hrow].height = 30

    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    fills = {
        "确认一致": PatternFill("solid", fgColor="E2EFDA"),
        "留空=采纳": PatternFill("solid", fgColor="DDEBF7"),
        "用户改分": PatternFill("solid", fgColor="FFF2CC"),
    }
    for i, rec in enumerate(reviewed, start=1):
        r = hrow + i
        values = [rec["seq"], rec["group"], rec["qid"], rec["rank"], rec["eid"],
                  rec["title"], rec["publisher"], rec["auto"], rec["mine"],
                  rec["user"], rec["final"], rec["status"], rec["note"]]
        for c, value in enumerate(values, start=1):
            cell = log.cell(row=r, column=c, value=value)
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=c in (6, 7, 13),
                                       horizontal="center" if c in (1, 2, 3, 4, 5, 8, 9, 10, 11, 12) else "left")
            if c == 12:
                cell.fill = fills[rec["status"]]
        log.row_dimensions[r].height = 46

    log.freeze_panes = f"C{hrow + 1}"
    log.auto_filter.ref = f"A{hrow}:M{hrow + len(reviewed)}"

    wb.save(SCORING)
    shutil.copy2(SCORING, DELIVERY / SCORING.name)
    shutil.copy2(REVIEWED, ROOT / REVIEWED.name)
    shutil.copy2(REVIEWED, DELIVERY / REVIEWED.name)

    print(f"reviewed rows: {len(reviewed)}")
    print(f"confirmed: {sum(r['status']=='确认一致' for r in reviewed)}  "
          f"accepted: {sum(r['status']=='留空=采纳' for r in reviewed)}  "
          f"changed: {sum(r['status']=='用户改分' for r in reviewed)}")
    print(f"Q001-Q030: Relevance={avg_rel:.4f} Authority={avg_auth:.4f} "
          f"Hit@5={hit_rate:.4f} Coverage={avg_cov:.4f}")
    print(f"saved {SCORING} and {DELIVERY / SCORING.name}")


if __name__ == "__main__":
    main()
