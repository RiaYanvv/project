"""Task 4.1 — evidence metadata registry.

Task 1 (``evidence_battery_EV_screened_v0.7.xlsx``) is the single source of
truth for evidence metadata, but it stores several fields in Chinese and does
not carry the optimisation schema verbatim.  This module derives the Task 4
filter schema from the Task 1 file so the retrieval layer can filter on
``industry`` / ``country_region`` / ``topic`` / ``evidence_type`` /
``authority_level`` / ``related_risk`` without touching Task 1 itself.

Derivation rules are deterministic and are re-exported so they can be written
into the deliverable spreadsheet (see ``DERIVATION_RULES``).

Nothing here is a new human judgement: every value is a documented
transformation of a Task 1 cell.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Task 1 -> Task 4 schema mapping tables
# --------------------------------------------------------------------------

# Task 1 `topic` (Chinese) -> Task 4 spec `topic` vocabulary.
TOPIC_EN: dict[str, list[str]] = {
    "出口管制": ["export_control", "regulation"],
    "出口管制/关税": ["export_control", "tariff", "regulation"],
    "关税": ["tariff"],
    "对外投资": ["investment_policy"],
    "原产地与转运": ["trade_policy", "market_access"],
    "反规避": ["trade_policy", "market_access"],
    "供应链布局": ["supply_chain", "supplier_dependency"],
    "宏观风险": ["trade_policy", "supply_chain"],
    "贸易流": ["trade_policy", "supply_chain"],
}

# Task 1 `source_type` -> Task 4 `evidence_type` vocabulary.
EVIDENCE_TYPE: dict[str, str] = {
    "法规政策": "Policy",
    "官方报告": "Policy",
    "研究报告": "Industry Report",
    "调查报告": "Industry Report",
    "新闻报道": "News",
    "案例": "Case Study",
    "贸易数据": "Trade Data",
    "数据库": "Policy",
}

# Task 1 `topic` -> Task 4 `related_risk` vocabulary.
RISK_BY_TOPIC: dict[str, list[str]] = {
    "出口管制": ["Regulatory Risk", "Market Access Risk"],
    "出口管制/关税": ["Regulatory Risk", "Trade Risk", "Market Access Risk"],
    "关税": ["Trade Risk"],
    "对外投资": ["Political Risk", "Regulatory Risk"],
    "原产地与转运": ["Trade Risk", "Market Access Risk"],
    "反规避": ["Trade Risk", "Market Access Risk"],
    "供应链布局": ["Supply Chain Risk", "Operational Risk"],
    "宏观风险": ["Political Risk", "Trade Risk"],
    "贸易流": ["Trade Risk", "Supply Chain Risk"],
}

# Task 1 `verification_status` -> Task 4 `data_status` vocabulary.
VERIFIED = "verified"
REPORTED = "reported"
UNKNOWN = "unknown"

# Task 1 `related_industries` -> Task 4 `industry` + scope.
# scope: core = directly on the EV-battery value chain,
#        general = industry-agnostic policy that still binds EV batteries,
#        off_focus = a different sector kept only as a cross-industry analogue.
INDUSTRY_BY_TAG: dict[str, tuple[str, str]] = {
    "通用": ("EV_Battery", "general"),
    "◆随产业": ("EV_Battery", "general"),
    "金属铸造": ("General_Manufacturing", "off_focus"),
    "光伏": ("Energy_Storage", "off_focus"),
    "◆光伏": ("Energy_Storage", "off_focus"),
    "光模块": ("Electronics_Manufacturing", "off_focus"),
    "光模块/光器件": ("Electronics_Manufacturing", "off_focus"),
    "◆电子/光电": ("Electronics_Manufacturing", "off_focus"),
    # Task 5 case database tags (battery / EV value chain + analogues).
    "动力电池": ("EV_Battery", "core"),
    "动力电池/储能": ("EV_Battery", "core"),
    "动力电池/消费电池": ("EV_Battery", "core"),
    "电池材料": ("Battery_Materials", "core"),
    "整车/汽车": ("Automotive", "core"),
    "电子/半导体": ("Electronics_Manufacturing", "off_focus"),
    "电子制造": ("Electronics_Manufacturing", "off_focus"),
    "通用制造": ("General_Manufacturing", "off_focus"),
}

COUNTRY_CODES: dict[str, str] = {
    "美国": "US",
    "中国": "CN",
    "全球": "Global",
    "柬埔寨": "KH",
    "马来西亚": "MY",
    "泰国": "TH",
    "越南": "VN",
    "印尼": "ID",
    "印度尼西亚": "ID",
    "印度": "IN",
    "墨西哥": "MX",
    "欧盟": "EU",
}

DERIVATION_RULES: list[tuple[str, str, str]] = [
    ("evidence_id", "Task 1 `evidence_id`", "直接沿用，作为与 DB `source_id` 的关联键"),
    ("industry", "Task 1 `related_industries`", "按 INDUSTRY_BY_TAG 映射；语料聚焦 EV battery，通用政策归为 EV_Battery(general)"),
    ("industry_scope", "Task 1 `related_industries`", "core=电池/EV 链；general=通用政策；off_focus=跨行业类比（光伏/光模块/金属铸造）"),
    ("country_region", "Task 1 `country_code`", "按 COUNTRY_CODES 归一化；多国以 / 分隔"),
    ("topic", "Task 1 `topic`", "按 TOPIC_EN 映射到 Task 4 topic 词表（可一对多）"),
    ("evidence_type", "Task 1 `source_type`", "按 EVIDENCE_TYPE 映射"),
    ("authority_level", "Task 1 `authority_level`", "直接沿用（S / A+ / A / B+）"),
    ("data_status", "Task 1 `verification_status`", "已核实→verified；已核实（二手）→reported；待核实/待拉取/待验证→reported/unknown"),
    ("related_risk", "Task 1 `topic`", "按 RISK_BY_TOPIC 映射到六类风险（可一对多），属派生值"),
]


@dataclass(frozen=True)
class EvidenceMeta:
    evidence_id: str
    title: str
    publisher: str
    industry: str
    industry_scope: str
    country_region: str
    countries: tuple[str, ...]
    topics: tuple[str, ...]
    topic_cn: str
    evidence_type: str
    authority_level: str
    data_status: str
    related_risk: tuple[str, ...]


def _norm_countries(raw: str) -> tuple[str, ...]:
    text = str(raw or "").strip()
    if not text:
        return ()
    parts = [p.strip() for p in text.replace("，", "/").replace(",", "/").split("/") if p.strip()]
    out: list[str] = []
    for part in parts:
        code = COUNTRY_CODES.get(part, part)
        if code and code not in out:
            out.append(code)
    return tuple(out)


def _norm_status(raw: str) -> str:
    text = str(raw or "").strip()
    if text == "已核实":
        return VERIFIED
    if text.startswith("已核实"):
        return REPORTED
    if "待核实" in text:
        return REPORTED
    if "待拉取" in text or "待验证" in text:
        return UNKNOWN
    return UNKNOWN


def build_meta(row: dict) -> EvidenceMeta:
    tag = str(row.get("related_industries") or "通用").strip()
    industry, scope = INDUSTRY_BY_TAG.get(tag, ("EV_Battery", "general"))
    topic_cn = str(row.get("topic") or "").strip()
    return EvidenceMeta(
        evidence_id=str(row.get("evidence_id") or "").strip(),
        title=str(row.get("source_title") or "").strip(),
        publisher=str(row.get("publisher") or "").strip(),
        industry=industry,
        industry_scope=scope,
        country_region=str(row.get("country_code") or "").strip(),
        countries=_norm_countries(str(row.get("country_code") or "")),
        topics=tuple(TOPIC_EN.get(topic_cn, [topic_cn] if topic_cn else [])),
        topic_cn=topic_cn,
        evidence_type=EVIDENCE_TYPE.get(str(row.get("source_type") or "").strip(), "Industry Report"),
        authority_level=str(row.get("authority_level") or "B+").strip(),
        data_status=_norm_status(str(row.get("verification_status") or "")),
        related_risk=tuple(RISK_BY_TOPIC.get(topic_cn, [])),
    )


def build_registry(*xlsx_paths: str | Path) -> dict[str, dict]:
    """Merge one or more Task-1-schema workbooks into a single registry.

    Later workbooks win on duplicate ``evidence_id``; in practice the Task 1
    policy corpus and the Task 5 case corpus are disjoint.
    """
    registry: dict[str, dict] = {}
    for path in xlsx_paths:
        registry.update(build_registry_from_task1(path))
    return registry


def build_registry_from_task1(xlsx_path: str | Path) -> dict[str, dict]:
    from openpyxl import load_workbook

    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb["sources"]
    rows = ws.iter_rows(values_only=True)
    header = [str(v).strip() if v is not None else "" for v in next(rows)]
    registry: dict[str, dict] = {}
    for row in rows:
        rec = dict(zip(header, row))
        if not rec.get("evidence_id"):
            continue
        meta = build_meta(rec)
        registry[meta.evidence_id] = asdict(meta)
    wb.close()
    return registry


DEFAULT_METADATA_PATH = Path(
    "/Users/zhengyuanyuan/Desktop/project-data/data/metadata/evidence_metadata_v0.1.json"
)


def _candidate_paths(explicit: str | Path | None) -> list[Path]:
    paths: list[Path] = []
    if explicit:
        paths.append(Path(explicit))
    env = os.getenv("EVIDENCE_METADATA_PATH")
    if env:
        paths.append(Path(env))
    try:
        from .config import Settings

        settings = Settings.from_env()
        paths.append(settings.data_root / "metadata" / "evidence_metadata_v0.1.json")
        paths.append(settings.data_root / "metadata" / "evidence_battery_EV_screened_v0.7.xlsx")
    except Exception:  # pragma: no cover - settings import is best-effort
        pass
    paths.append(DEFAULT_METADATA_PATH)
    paths.append(
        DEFAULT_METADATA_PATH.with_name("evidence_battery_EV_screened_v0.7.xlsx")
    )
    return paths


def load_registry(path: str | Path | None = None) -> dict[str, dict]:
    """Load the metadata registry.

    Resolution order: explicit path -> EVIDENCE_METADATA_PATH -> data root
    JSON -> data root Task 1 xlsx -> repo default JSON -> repo default xlsx.
    Returns an empty dict when nothing is available, in which case metadata
    filtering degrades to a no-op instead of raising.
    """
    for candidate in _candidate_paths(path):
        try:
            if not candidate or not candidate.exists():
                continue
            if candidate.suffix.lower() == ".xlsx":
                return build_registry_from_task1(candidate)
            with candidate.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            continue
    return {}


def write_registry(xlsx_path: str | Path, out_path: str | Path, *extra: str | Path) -> dict[str, dict]:
    registry = build_registry(xlsx_path, *extra)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return registry


if __name__ == "__main__":  # pragma: no cover
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else str(
        DEFAULT_METADATA_PATH.with_name("evidence_battery_EV_screened_v0.7.xlsx")
    )
    dst = sys.argv[2] if len(sys.argv) > 2 else str(DEFAULT_METADATA_PATH)
    reg = write_registry(src, dst)
    print(f"wrote {len(reg)} records to {dst}")
