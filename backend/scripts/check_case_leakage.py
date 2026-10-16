"""Task 5 — held-out 案例与 RAG 语料的隔离校验。

Task 5 的 17 个案例是 end-to-end benchmark 的答案键，必须保证：
  1. 案例记录本身不在 RAG 语料里（文档 ID 不撞）；
  2. 案例的外部来源链接不在语料里（同一篇文章不能既当答案又当证据）；
  3. 案例叙述（背景 + 决策 + 结果）与语料没有逐字重合；
  4. 案例绑定的 related_evidence_ids 全部能在 Task 1 证据库里解析。

用法（仓库根目录）：
    .venv/bin/python backend/scripts/check_case_leakage.py
退出码 0 = 全部通过；1 = 有检查项失败。
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from openpyxl import load_workbook

DEFAULT_DB = Path("backend/test_data/app.db")
DEFAULT_CASE_DB = Path("/Users/zhengyuanyuan/Desktop/project-data/data/processed/case_database_v0.1.xlsx")
DEFAULT_REGISTRY = Path("/Users/zhengyuanyuan/Desktop/project-data/data/metadata/evidence_metadata_v0.1.json")
CASE_ID = re.compile(r"^(RELOC|PLUS1|RETURN)_\d{3}$")
SHINGLE = 10
OVERLAP_TOLERANCE = 0.05  # 逐字重合率上限；背景级重合另行登记，不计入失败


def shingles(text: str, n: int = SHINGLE) -> set[str]:
    text = re.sub(r"\s+", "", text or "")
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--case-db", type=Path, default=DEFAULT_CASE_DB)
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    corpus = {
        sid: f"{title or ''} {content or ''}"
        for sid, title, content in con.execute(
            "select source_id, title, coalesce(content,'') from knowledge_documents"
        )
    }
    corpus_urls = {u for (u,) in con.execute("select url from knowledge_documents") if u}
    corpus_text = " \n ".join(corpus.values())

    ws = load_workbook(args.case_db, read_only=True, data_only=True)["Case Database"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(c).strip() for c in rows[0]]
    cases = [dict(zip(hdr, r)) for r in rows[1:] if r and r[0]]

    registry = json.loads(args.registry.read_text(encoding="utf-8"))

    failures: list[str] = []
    print(f"corpus: {len(corpus)} docs / {len(corpus_urls)} urls   cases: {len(cases)}")

    # 1) 案例 ID 不在语料里
    leaked_ids = sorted(cid for cid in corpus if CASE_ID.match(str(cid)))
    print(f"[1] 语料中的案例 ID: {leaked_ids or '无'}")
    if leaked_ids:
        failures.append(f"语料含案例 ID: {leaked_ids}")

    # 2) 案例来源 URL 不在语料里
    dup_urls = [(c["case_id"], c["url"]) for c in cases if str(c.get("url") or "") in corpus_urls]
    print(f"[2] 与语料重合的案例来源 URL: {dup_urls or '无'}")
    if dup_urls:
        failures.append(f"URL 重合: {dup_urls}")

    # 3) 逐字重合
    print(f"[3] 逐字重合（{SHINGLE} 字滑窗，阈值 {OVERLAP_TOLERANCE:.0%}）:")
    worst = 0.0
    for c in cases:
        text = " ".join(str(c.get(k) or "") for k in (
            "initial_problem", "trigger_detail", "actual_decision",
            "outcome_cost_impact", "outcome_production_performance",
            "outcome_market_access", "outcome_supply_chain_impact"))
        sh = shingles(text)
        ratio = sum(1 for x in sh if x in corpus_text) / len(sh) if sh else 0.0
        worst = max(worst, ratio)
        flag = "FAIL" if ratio > OVERLAP_TOLERANCE else "ok"
        print(f"    {c['case_id']:11s} {ratio:6.1%}  {flag}")
        if ratio > OVERLAP_TOLERANCE:
            failures.append(f"{c['case_id']} 逐字重合 {ratio:.1%}")

    # 4) related_evidence_ids 可解析
    dangling: list[tuple[str, list[str]]] = []
    for c in cases:
        ids = [x.strip() for x in str(c.get("related_evidence_ids") or "").split(";") if x.strip()]
        miss = [x for x in ids if x not in registry]
        if miss:
            dangling.append((str(c["case_id"]), miss))
    total_links = sum(len([x for x in str(c.get("related_evidence_ids") or "").split(";") if x.strip()])
                      for c in cases)
    print(f"[4] related_evidence_ids 悬空引用: {dangling or '无'}（共 {total_links} 条绑定）")
    if dangling:
        failures.append(f"悬空引用: {dangling}")

    print()
    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"ALL CHECKS PASSED（逐字重合最高 {worst:.1%}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
