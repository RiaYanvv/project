from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings
from app.knowledge import KnowledgeDocument, KnowledgeRepository


def clean(value) -> str:
    """Convert Excel cell values to clean strings."""
    if value is None:
        return ""
    return str(value).strip()


def read_pdf(path: Path) -> str:
    """Extract text from a PDF."""
    reader = PdfReader(str(path))
    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)

    return "\n\n".join(pages)


def read_csv(path: Path) -> str:
    """Convert CSV rows into searchable text."""
    lines = []

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            parts = [
                f"{key}: {value}"
                for key, value in row.items()
                if key and value not in (None, "")
            ]

            if parts:
                lines.append(" | ".join(parts))

    return "\n".join(lines)


def read_xlsx(path: Path) -> str:
    workbook = load_workbook(path, read_only=True, data_only=True)

    lines = []

    for sheet in workbook.worksheets:
        lines.append(f"Sheet: {sheet.title}")

        for row in sheet.iter_rows(values_only=True):
            values = [
                clean(value)
                for value in row
                if value is not None and clean(value)
            ]

            if values:
                lines.append(" | ".join(values))

    workbook.close()

    return "\n".join(lines)


def read_json(path: Path) -> str:
    """Convert JSON into searchable text."""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    return json.dumps(data, ensure_ascii=False, indent=2)


def read_json_gz(path: Path) -> str:
    """Read a gzip JSON dataset and convert records into searchable text."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)

    # Structured dataset with a "results" list
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        lines = []

        for record in data["results"]:
            if not isinstance(record, dict):
                continue

            parts = []

            for key in [
                "name",
                "type",
                "entity_number",
                "alt_names",
                "programs",
                "remarks",
                "source",
                "source_information_url",
                "source_list_url",
                "ids",
            ]:
                value = record.get(key)

                if value not in (None, "", [], {}):
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False)

                    parts.append(f"{key}: {value}")

            if parts:
                lines.append("\n".join(parts))

        return "\n\n--- RECORD ---\n\n".join(lines)

    # Fallback for other JSON structures
    return json.dumps(data, ensure_ascii=False)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_content(path: Path) -> str:
    # .json.gz 必须单独判断
    if path.name.lower().endswith(".json.gz"):
        return read_json_gz(path)

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return read_pdf(path)

    if suffix == ".csv":
        return read_csv(path)
    
    if suffix == ".xlsx":
        return read_xlsx(path)

    if suffix in {".txt", ".md", ".html", ".htm"}:
        return read_text(path)

    raise ValueError(f"Unsupported file type: {path}")


def load_metadata(excel_path: Path) -> list[dict[str, str]]:
    workbook = load_workbook(excel_path, read_only=True, data_only=True)
    sheet = workbook["evidence"] if "evidence" in workbook.sheetnames else workbook.active

    rows = sheet.iter_rows(values_only=True)

    try:
        headers = [clean(value) for value in next(rows)]
    except StopIteration:
        return []

    records = []

    for values in rows:
        record = {
            headers[i]: clean(values[i])
            for i in range(min(len(headers), len(values)))
            if headers[i]
        }

        if record.get("evidence_id"):
            records.append(record)

    return records


def resolve_document_path(data_root: Path, document_path: str) -> Path:
    path = Path(document_path)

    if path.is_absolute():
        return path

    # Excel paths are expected to look like:
    # data/raw/policy/BIS_001.pdf
    if path.parts and path.parts[0] == "data":
        path = Path(*path.parts[1:])

    return data_root / path


def build_document(record: dict[str, str], file_path: Path, content: str) -> KnowledgeDocument:
    country_code = record.get("country_code", "")
    jurisdiction = record.get("jurisdiction", "")

    country_region = " / ".join(
        part for part in [country_code, jurisdiction] if part
    )

    metadata_context = "\n".join(
        line
        for line in [
            f"Evidence ID: {record.get('evidence_id', '')}",
            f"Title: {record.get('source_title', '')}",
            f"Publisher: {record.get('publisher', '')}",
            f"Country/Jurisdiction: {country_region}",
            f"Publication date: {record.get('publication_date', '')}",
            f"Effective date: {record.get('effective_date', '')}",
            f"Status: {record.get('status', '')}",
            f"Topic: {record.get('topic', '')}",
            f"Applicability scope: {record.get('applicability_scope', '')}",
            f"Related industries: {record.get('related_industries', '')}",
            f"Claim: {record.get('claim', '')}",
            f"Key finding: {record.get('key_finding', '')}",
            f"Content summary: {record.get('content_summary', '')}",
            f"Applicability notes: {record.get('applicability_notes', '')}",
            f"Uncertainty: {record.get('uncertainty', '')}",
        ]
        if line.split(": ", 1)[-1].strip()
    )

    combined_content = f"{metadata_context}\n\n{content}".strip()

    return KnowledgeDocument(
        source_id=record["evidence_id"],
        title=record.get("source_title", ""),
        source_type=record.get("source_type", ""),
        publisher=record.get("publisher", ""),
        country_region=country_region,
        publication_date=record.get("publication_date", ""),
        url=record.get("source_url", ""),
        authority_level=record.get("authority_level", ""),
        topic=record.get("topic", ""),
        document_path=str(file_path),
        content=combined_content,
        is_mock=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest the curated EV/battery evidence dataset into the local RAG knowledge base."
    )

    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Path to the data directory containing metadata/ and raw/.",
    )

    parser.add_argument(
        "--excel",
        default="metadata/evidence.xlsx",
        help="Evidence metadata workbook path relative to data-root.",
    )
    parser.add_argument(
        "--evidence-id",
        action="append",
        default=[],
        help="Only ingest the specified evidence_id. Repeat for multiple IDs.",
    )

    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()
    excel_path = data_root / args.excel

    if not excel_path.exists():
        print(f"ERROR: metadata file not found: {excel_path}")
        return 1

    settings = Settings.from_env()
    repository = KnowledgeRepository(settings.database_path)

    records = load_metadata(excel_path)
    if args.evidence_id:
        requested_ids = set(args.evidence_id)
        records = [
            record
            for record in records
            if record.get("evidence_id") in requested_ids
        ]

    print(f"Loaded {len(records)} metadata records.")
    print(f"Knowledge DB: {settings.database_path}")

    success = 0
    skipped = 0
    failed = 0

    for record in records:
        evidence_id = record.get("evidence_id", "UNKNOWN")

        # Do not ingest evidence explicitly marked as no longer current.
        status = record.get("status", "").upper()

        if status in {"EXPIRED", "REPEALED"}:
            print(f"[SKIP] {evidence_id}: status={status}")
            skipped += 1
            continue

        document_path = record.get("document_path", "")

        if not document_path:
            print(f"[SKIP] {evidence_id}: missing document_path")
            skipped += 1
            continue

        file_path = resolve_document_path(data_root, document_path)

        if not file_path.exists():
            print(f"[ERROR] {evidence_id}: file not found: {file_path}")
            failed += 1
            continue

        try:
            content = extract_content(file_path)

            if not content.strip():
                print(f"[SKIP] {evidence_id}: no extractable text")
                skipped += 1
                continue

            document = build_document(record, file_path, content)
            chunk_count = repository.ingest_document(document)

            print(
                f"[OK] {evidence_id}: "
                f"{file_path.name} -> {chunk_count} chunks"
            )

            success += 1

        except Exception as exc:
            print(f"[ERROR] {evidence_id}: {exc}")
            failed += 1

    print()
    print("=== INGESTION COMPLETE ===")
    print(f"Success: {success}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")
    print(f"Repository stats: {repository.stats()}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
