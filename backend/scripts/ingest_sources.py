from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import PROJECT_ROOT, Settings
from app.crawler import PublicSourceCrawler, load_source_feed
from app.knowledge import KnowledgeRepository


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch public sources and build the local hybrid RAG index."
    )
    parser.add_argument(
        "--feed",
        type=Path,
        default=PROJECT_ROOT / "backend" / "test_data" / "source_feed.json",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "backend" / "test_data" / "ingestion_report.json",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    repository = KnowledgeRepository(settings.database_path)
    crawler = PublicSourceCrawler()
    feed = load_source_feed(args.feed)
    if args.limit:
        feed = feed[: args.limit]

    report: dict[str, object] = {
        "feed": str(args.feed),
        "attempted": len(feed),
        "succeeded": [],
        "failed": [],
        "chunks": {},
    }
    succeeded: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    chunk_counts: dict[str, int] = {}

    for item in feed:
        source_id = item["source_id"]
        print(f"[{source_id}] fetching {item['url']}", flush=True)
        try:
            document = crawler.fetch_document(item)
            chunk_count = repository.ingest_document(document)
            chunk_counts[source_id] = chunk_count
            succeeded.append(
                {"source_id": source_id, "title": item["title"], "url": item["url"]}
            )
            print(f"[{source_id}] indexed {chunk_count} chunks", flush=True)
        except Exception as exc:  # noqa: BLE001
            failed.append(
                {
                    "source_id": source_id,
                    "title": item["title"],
                    "url": item["url"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"[{source_id}] failed: {type(exc).__name__}: {exc}", flush=True)

    report["succeeded"] = succeeded
    report["failed"] = failed
    report["chunks"] = chunk_counts
    report["stats"] = repository.stats()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["stats"], ensure_ascii=False), flush=True)
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
