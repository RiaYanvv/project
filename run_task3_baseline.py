"""Task 3 — RAG baseline evaluation.

Runs the CURRENT (pre-optimisation) retrieval for the 30 benchmark questions at
K=10 and records:
  Precision@5, Recall@10, Entity Accuracy
plus the per-question diagnostics needed for the optimisation backlog.

Outputs (data/evaluation/):
  retrieval_questions.xlsx, retrieval_results.xlsx, entity_accuracy.xlsx, baseline_report.md
"""
from __future__ import annotations

import copy
import math
import re
import shutil
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.app.config import Settings
from backend.app.knowledge import KnowledgeRepository
from backend.app.retrieval import HybridRetrievalProvider
from backend.app.schemas import RetrievalQuery

BENCHMARK = Path("task2_retrieval_evaluation_v0.7.xlsx")
QUESTION_FILE = Path("retrieval_questions.xlsx")
OUT_DIR = Path("/Users/zhengyuanyuan/Desktop/project-data/data/evaluation")
TOP_K = 10
PRECISION_K = 5

TOPIC_MAP = {
    "supply_chain": {"供应链布局", "贸易流", "原产地与转运"},
    "supplier_dependency": {"供应链布局", "贸易流", "原产地与转运"},
    "export_control": {"出口管制", "出口管制/关税", "原产地与转运"},
    "trade_policy": {"原产地与转运", "反规避", "贸易流", "出口管制/关税", "供应链布局"},
    "investment_policy": {"对外投资", "宏观风险"},
    "market_access": {"原产地与转运", "反规避", "贸易流", "出口管制"},
    "regulation": {"出口管制", "出口管制/关税", "原产地与转运"},
}
AUTHORITY_SCORE = {"S": 2, "A+": 2, "A": 2, "B+": 1, "B": 1}

# --- entity lexicon -------------------------------------------------------
ENTITIES = {
    # countries / regions
    "China": ("country", r"中国|大陆|中华人民共和国|\bCHN\b"),
    "United States": ("country", r"美国|美方|对美|\bU\.?S\.?A?\b|United States"),
    "Vietnam": ("country", r"越南|Vietnam"),
    "Thailand": ("country", r"泰国|Thailand"),
    "Malaysia": ("country", r"马来西亚|Malaysia"),
    "India": ("country", r"印度|India"),
    "Indonesia": ("country", r"印尼|印度尼西亚|Indonesia"),
    "Cambodia": ("country", r"柬埔寨|Cambodia"),
    "Mexico": ("country", r"墨西哥|Mexico"),
    "EU": ("country", r"欧盟|\bEU\b"),
    # companies
    "Zhongji Innolight": ("company", r"中际旭创|Innolight"),
    "Eoptolink": ("company", r"新易盛|Eoptolink"),
    "T&S Communications": ("company", r"天孚通信|天孚"),
    "HGTECH": ("company", r"华工科技|华工正源"),
    "Dawang Metals": ("company", r"Dawang|丹东"),
    "CATL": ("company", r"CATL|宁德时代"),
    "JinkoSolar": ("company", r"晶科|Jinko"),
    "Hanwha": ("company", r"韩华|Hanwha"),
    "Boviet": ("company", r"Boviet"),
    "First Solar": ("company", r"First Solar"),
    "LONGi": ("company", r"隆基|LONGi"),
    # policy instruments
    "BIS": ("policy", r"\bBIS\b|工业与安全局"),
    "Entity List": ("policy", r"Entity List|实体清单"),
    "MEU List": ("policy", r"\bMEU\b|军事最终用户"),
    "50% Affiliates Rule": ("policy", r"50%|关联企业|穿透"),
    "EO 14411": ("policy", r"14411"),
    "Federal Register": ("policy", r"Federal Register|联邦公报"),
    "MOFCOM dual-use catalogue": ("policy", r"两用物项|许可证管理目录"),
    "MOFCOM Announcement 72": ("policy", r"第72号|2024年第46号"),
    "Anti-circumvention": ("policy", r"反规避|规避"),
    "AD/CVD": ("policy", r"双反|反倾销|反补贴"),
    "Transshipment": ("policy", r"转运|原产地"),
    "Tariff": ("policy", r"关税|tariff"),
    # technology / sector
    "EV Battery": ("sector", r"电池|\bEV\b|电动车|石墨|镓|锗"),
    "Solar": ("sector", r"光伏|太阳能|组件"),
    "Optical Module": ("sector", r"光模块"),
}
COMPILED = {k: re.compile(v[1]) for k, v in ENTITIES.items()}
TYPE_OF = {k: v[0] for k, v in ENTITIES.items()}


def detect(text: str) -> set[str]:
    return {name for name, rx in COMPILED.items() if rx.search(text or "")}


_ENT_CACHE: dict[str, set[str]] = {}


def ent_cache(evidence_id: str, title: str, content: str) -> set[str]:
    if evidence_id not in _ENT_CACHE:
        _ENT_CACHE[evidence_id] = detect(f"{title}\n{content}")
    return _ENT_CACHE[evidence_id]


def normalize_evidence_id(value: str) -> str:
    value = str(value or "").strip()
    if value.startswith("EVD-"):
        value = value[4:]
    return re.sub(r"-C\d+$", "", value)


def split_expected(value) -> list[str]:
    text = str(value or "").strip()
    return [p.strip() for p in re.split(r"[;,，；]\s*", text) if p.strip()] if text else []


def load_questions(path: Path) -> list[dict]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb["retrieval_questions"]
    rows = ws.iter_rows(values_only=True)
    headers = [str(v).strip() if v is not None else "" for v in next(rows)]
    out = []
    for row in rows:
        rec = dict(zip(headers, row))
        qid = str(rec.get("question_id") or "").strip()
        if not qid:
            continue
        out.append({
            "question_id": qid,
            "question": str(rec.get("question") or "").strip(),
            "scenario_category": str(rec.get("scenario_category") or "").strip(),
            "expected_topic": str(rec.get("expected_topic") or "").strip(),
            "expected_evidence_ids": split_expected(rec.get("expected_evidence_ids")),
            "difficulty": str(rec.get("difficulty") or "").strip(),
        })
    wb.close()
    return out


def style_header(ws, ncol, color="1F3864"):
    fill = PatternFill("solid", fgColor=color)
    for c in ws[1][:ncol]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"


def main(retrieval=None, out_dir=None) -> None:
    settings = Settings.from_env()
    repository = KnowledgeRepository(settings.database_path)
    if retrieval is None:
        retrieval = HybridRetrievalProvider(repository=repository, fallback=None, web_search=None)
    out_dir = Path(out_dir) if out_dir else OUT_DIR
    questions = load_questions(BENCHMARK)

    rows, qrows, ent_rows = [], [], []

    for q in questions:
        query = RetrievalQuery(
            industry="battery_ev",
            products=[q["question"]],
            home_country="CN",
            production_countries=[],
            target_markets=[],
            decision_question=q["question"],
            restrictions=[],
            limit=TOP_K,
        )
        results = retrieval.search(query)
        expected = set(q["expected_evidence_ids"])

        rels = []
        recs = []
        for rank, item in enumerate(results, start=1):
            eid = normalize_evidence_id(item.evidence_id)
            rel = 2 if eid in expected else (1 if item.topic in TOPIC_MAP.get(q["expected_topic"], set()) else 0)
            rels.append(rel)
            recs.append({"rank": rank, "id": eid, "title": item.title, "topic": item.topic,
                         "auth": item.authority_level, "rel": rel, "content": item.content,
                         "publisher": item.publisher, "relevance_score": item.relevance_score,
                         "expected_topic": q["expected_topic"], "question": q["question"],
                         "scenario_category": q["scenario_category"],
                         "expected_evidence_ids": "; ".join(q["expected_evidence_ids"])})

        matched = {r["id"] for r in recs if r["id"] in expected}
        p5 = sum(1 for r in recs[:PRECISION_K] if r["rel"] >= 1) / PRECISION_K
        r10 = len(matched) / len(expected) if expected else 0.0

        # --- entities -------------------------------------------------------
        # Target entities come from the QUESTION TEXT only, so the metric is not
        # circular (it never looks at the gold evidence).
        q_ents = detect(q["question"])
        item_ents = {r["id"]: ent_cache(r["id"], r["title"], r["content"]) for r in recs}
        got = set().union(*item_ents.values()) if item_ents else set()
        covered = q_ents & got
        missing = sorted(q_ents - covered)
        on_entity = [r["id"] for r in recs if item_ents[r["id"]] & q_ents]
        off_target = [r["id"] for r in recs if not (item_ents[r["id"]] & q_ents)]
        ent_recall = (len(covered) / len(q_ents)) if q_ents else None
        ent_prec = (len(on_entity) / len(recs)) if (recs and q_ents) else None
        acc = (ent_recall + ent_prec) / 2 if (ent_recall is not None and ent_prec is not None) else None
        required = q_ents

        for r in recs:
            rows.append({
                "question_id": q["question_id"],
                "retrieved_evidence_id": r["id"],
                "rank": r["rank"],
                "relevance_score": r["rel"],
                "authority_score": AUTHORITY_SCORE.get(r["auth"], 0),
                "scenario_category": q["scenario_category"],
                "expected_topic": q["expected_topic"],
                "expected_evidence_ids": r["expected_evidence_ids"],
                "title": r["title"],
                "publisher": r["publisher"],
                "retrieved_topic": r["topic"],
                "authority_level": r["auth"],
                "system_relevance_score": r["relevance_score"],
                "in_top5": 1 if r["rank"] <= PRECISION_K else 0,
                "in_gold": 1 if r["id"] in expected else 0,
            })

        qrows.append({
            "question_id": q["question_id"],
            "scenario_category": q["scenario_category"],
            "expected_topic": q["expected_topic"],
            "question": q["question"],
            "gold_count": len(expected),
            "retrieved_top10": "; ".join(r["id"] for r in recs),
            "matched_in_top10": "; ".join(sorted(matched)),
            "gold_in_top5": sum(1 for r in recs[:5] if r["id"] in expected),
            "precision_at_5": round(p5, 3),
            "recall_at_10": round(r10, 3),
            "hit_at_5": 1 if any(r["id"] in expected for r in recs[:5]) else 0,
            "hit_at_10": 1 if matched else 0,
            "entity_recall": "" if ent_recall is None else round(ent_recall, 3),
            "entity_precision": "" if ent_prec is None else round(ent_prec, 3),
            "entity_accuracy": "" if acc is None else round(acc, 3),
            "question_entities": "; ".join(sorted(required)),
            "missing_entities": "; ".join(missing),
            "on_entity_count": len(on_entity),
            "off_target_evidence": "; ".join(off_target),
            "mean_authority_top5": round(sum(AUTHORITY_SCORE.get(r["auth"], 0) for r in recs[:5]) / 5, 2),
            "difficulty": q["difficulty"],
        })

        for e in sorted(required):
            hits = [r for r in recs if e in item_ents[r["id"]]]
            ent_rows.append({
                "question_id": q["question_id"],
                "entity": e,
                "entity_type": TYPE_OF[e],
                "covered": 1 if e in covered else 0,
                "first_hit_rank": min([r["rank"] for r in hits], default=None),
                "hit_evidence_ids": "; ".join(r["id"] for r in hits[:6]),
            })

    total_q = len(qrows)
    p5 = sum(r["precision_at_5"] for r in qrows) / total_q
    r10 = sum(r["recall_at_10"] for r in qrows) / total_q
    ent_qs = [r for r in qrows if r["entity_accuracy"] != ""]
    ea = sum(r["entity_accuracy"] for r in ent_qs) / len(ent_qs) if ent_qs else 0.0
    ea_recall = sum(r["entity_recall"] for r in ent_qs) / len(ent_qs) if ent_qs else 0.0
    ea_prec = sum(r["entity_precision"] for r in ent_qs) / len(ent_qs) if ent_qs else 0.0
    hit5 = sum(r["hit_at_5"] for r in qrows) / total_q
    hit10 = sum(r["hit_at_10"] for r in qrows) / total_q
    avg_auth5 = sum(r["mean_authority_top5"] for r in qrows) / total_q

    by_cat: dict[str, list] = {}
    for r in qrows:
        by_cat.setdefault(r["scenario_category"], []).append(r)

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(QUESTION_FILE, out_dir / "retrieval_questions.xlsx")

    # ---------------- retrieval_results.xlsx ----------------
    wb = Workbook()
    ws = wb.active
    ws.title = "retrieval_results"
    cols = ["question_id", "retrieved_evidence_id", "rank", "relevance_score", "authority_score",
            "notes", "scenario_category", "expected_topic", "expected_evidence_ids", "title",
            "publisher", "retrieved_topic", "authority_level", "system_relevance_score",
            "in_top5", "in_gold"]
    ws.append(cols)
    for r in rows:
        ws.append([r.get(c) for c in cols])
    style_header(ws, len(cols))
    for i, w in enumerate([11, 18, 6, 10, 10, 10, 20, 16, 24, 44, 24, 15, 12, 12, 8, 8], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws2 = wb.create_sheet("question_summary")
    qcols = ["question_id", "scenario_category", "expected_topic", "question", "gold_count",
             "retrieved_top10", "matched_in_top10", "gold_in_top5", "precision_at_5", "recall_at_10",
             "hit_at_5", "hit_at_10", "entity_recall", "entity_precision", "entity_accuracy",
             "question_entities", "missing_entities", "on_entity_count", "off_target_evidence",
             "mean_authority_top5", "difficulty"]
    ws2.append(qcols)
    for r in qrows:
        ws2.append([r.get(c) for c in qcols])
    style_header(ws2, len(qcols), "2E5E4E")
    for i, w in enumerate([11, 22, 16, 56, 10, 40, 24, 11, 11, 11, 8, 8, 11, 11, 12, 30, 24, 10, 26, 12, 9], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    ws3 = wb.create_sheet("Summary")
    ws3.append(["Task 3 — Baseline Retrieval Evaluation", "Value", "Note"])
    for c in ws3[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
    ws3.append(["Questions", total_q, "30 benchmark questions"])
    ws3.append(["Top-K", TOP_K, "Recall@10 uses all 10; Precision uses Top-5"])
    ws3.append(["Precision@5", round(p5, 3), "relevant items in Top-5 / 5, mean over questions"])
    ws3.append(["Recall@10", round(r10, 3), "gold retrieved in Top-10 / gold count, mean over questions"])
    ws3.append(["Entity Accuracy", round(ea, 3), "(Entity Recall + Entity Precision) / 2, mean over entity-bearing questions"])
    ws3.append(["  Entity Recall", round(ea_recall, 3), "question entities found in Top-10 / question entities"])
    ws3.append(["  Entity Precision", round(ea_prec, 3), "share of Top-10 items that mention a question entity"])
    ws3.append(["Questions with named entities", len(ent_qs), f"of {total_q}; entity-free questions excluded"])
    ws3.append(["Hit@5", round(hit5, 3), "question has >=1 gold in Top-5"])
    ws3.append(["Hit@10", round(hit10, 3), "question has >=1 gold in Top-10"])
    ws3.append(["Mean Authority (Top-5)", round(avg_auth5, 3), "S/A+/A=2, B+/B=1"])
    ws3.append([])
    ws3.append(["By scenario category", "P@5", "R@10 / Entity Acc / n"])
    for cat, rs in sorted(by_cat.items()):
        ws3.append([cat,
                    round(sum(x["precision_at_5"] for x in rs) / len(rs), 3),
                    f"{round(sum(x['recall_at_10'] for x in rs) / len(rs), 3)} / "
                    f"{'' if not [y for y in rs if y['entity_accuracy'] != ''] else round(sum(y['entity_accuracy'] for y in rs if y['entity_accuracy'] != '') / len([y for y in rs if y['entity_accuracy'] != '']), 3)}"
                    f" / {len(rs)}"])
    ws3.column_dimensions["A"].width = 40
    ws3.column_dimensions["B"].width = 22
    ws3.column_dimensions["C"].width = 52
    for r in ws3.iter_rows(min_row=2):
        for c in r:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(out_dir / "retrieval_results.xlsx")

    # ---------------- entity_accuracy.xlsx ----------------
    wb2 = Workbook()
    e = wb2.active
    e.title = "Entity Accuracy"
    ecols = ["question_id", "scenario_category", "expected_topic", "question",
             "entity_accuracy", "entity_recall", "entity_precision",
             "question_entities", "missing_entities", "covered_count", "required_count",
             "on_entity_items", "off_target_evidence", "retrieved_top10"]
    e.append(ecols)
    for r in qrows:
        req = [x for x in r["question_entities"].split("; ") if x]
        miss = [x for x in r["missing_entities"].split("; ") if x]
        e.append([r["question_id"], r["scenario_category"], r["expected_topic"], r["question"],
                  r["entity_accuracy"], r["entity_recall"], r["entity_precision"],
                  r["question_entities"], r["missing_entities"], len(req) - len(miss), len(req),
                  r["on_entity_count"], r["off_target_evidence"], r["retrieved_top10"]])
    style_header(e, len(ecols))
    for i, w in enumerate([11, 22, 16, 56, 14, 12, 14, 34, 26, 12, 12, 12, 30, 40], 1):
        e.column_dimensions[get_column_letter(i)].width = w
    for row in e.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    d = wb2.create_sheet("Entity Detail")
    dcols = ["question_id", "entity", "entity_type", "covered", "first_hit_rank", "hit_evidence_ids"]
    d.append(dcols)
    for r in ent_rows:
        d.append([r.get(c) for c in dcols])
    style_header(d, len(dcols), "2E5E4E")
    for i, w in enumerate([11, 24, 12, 9, 13, 44], 1):
        d.column_dimensions[get_column_letter(i)].width = w
    d.auto_filter.ref = f"A1:F{d.max_row}"

    s = wb2.create_sheet("Summary")
    s.append(["Task 3 — Entity Accuracy", "Value", "Note"])
    for c in s[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
    s.append(["Entity Accuracy", round(ea, 3), f"mean over {len(ent_qs)} entity-bearing questions"])
    s.append(["  Entity Recall", round(ea_recall, 3), "question entities found in Top-10 / question entities"])
    s.append(["  Entity Precision", round(ea_prec, 3), "share of Top-10 items mentioning a question entity"])
    s.append(["Entity-bearing questions", len(ent_qs), f"of {total_q} (entity-free questions excluded)"])
    s.append(["Entity-free questions", total_q - len(ent_qs), "; ".join(r["question_id"] for r in qrows if r["entity_accuracy"] == "")])
    s.append(["Questions with full entity recall", sum(1 for r in ent_qs if r["entity_recall"] == 1.0), f"of {len(ent_qs)}"])
    s.append(["Questions with entity precision <1.0", sum(1 for r in ent_qs if r["entity_precision"] < 1.0), f"of {len(ent_qs)}"])
    s.append(["Total entities required", len(ent_rows), "across entity-bearing questions"])
    s.append(["Entities not covered", sum(1 for r in ent_rows if r["covered"] == 0), "across all questions"])
    s.append([])
    s.append(["By entity type", "Required", "Covered"])
    for t in ("country", "company", "policy", "sector"):
        sub = [r for r in ent_rows if r["entity_type"] == t]
        if sub:
            s.append([t, len(sub), sum(r["covered"] for r in sub)])
    s.append([])
    s.append(["Definition — Entity Accuracy", "(Entity Recall + Entity Precision) / 2, averaged over questions "
              "that name at least one entity.", ""])
    s.append(["Definition — Entity Recall", "Entities named in the question that appear in the Top-10 retrieved "
              "evidence, divided by the number of entities named in the question.", ""])
    s.append(["Definition — Entity Precision", "Share of the Top-10 retrieved items whose own entities overlap the "
              "entities named in the question.", ""])
    s.append(["Caveat", "Generic entities (China / United States / tariff) appear in most documents and inflate "
              "the score. See the Entity Detail sheet for the per-entity breakdown.", ""])
    s.column_dimensions["A"].width = 42
    s.column_dimensions["B"].width = 30
    s.column_dimensions["C"].width = 60
    for r in s.iter_rows(min_row=2):
        for c in r:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb2.save(out_dir / "entity_accuracy.xlsx")
    print(f"wrote {out_dir}/retrieval_results.xlsx and entity_accuracy.xlsx")
    print(f"P@5={p5:.3f} R@10={r10:.3f} EntityAcc={ea:.3f} (recall={ea_recall:.3f} prec={ea_prec:.3f}, "
          f"n={len(ent_qs)}) Hit@5={hit5:.3f} Hit@10={hit10:.3f}")
    for cat, rs in sorted(by_cat.items()):
        print(f"  {cat}: P@5={sum(x['precision_at_5'] for x in rs)/len(rs):.3f} "
              f"R@10={sum(x['recall_at_10'] for x in rs)/len(rs):.3f} "
              f"EA={sum(x['entity_accuracy'] for x in rs if x['entity_accuracy']!='')/max(1,len([y for y in rs if y['entity_accuracy']!=''])):.3f}")


if __name__ == "__main__":
    main()
