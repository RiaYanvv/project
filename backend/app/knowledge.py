from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


EMBEDDING_DIMENSIONS = 512


@dataclass(frozen=True)
class KnowledgeDocument:
    source_id: str
    title: str
    source_type: str
    publisher: str
    country_region: str
    publication_date: str
    url: str
    authority_level: str
    topic: str
    document_path: str | None
    content: str
    is_mock: bool = False


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source_id: str
    chunk_index: int
    content: str
    embedding: list[float]
    title: str
    source_type: str
    publisher: str
    country_region: str
    publication_date: str
    url: str
    authority_level: str
    topic: str
    document_path: str | None
    is_mock: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u0000", " ")).strip()


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text).lower()
    tokens: list[str] = []
    latin = re.findall(r"[a-z0-9][a-z0-9_.-]{1,}", normalized)
    tokens.extend(token for token in latin if len(token) >= 2)

    for sequence in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(sequence) == 1:
            tokens.append(sequence)
            continue
        tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return tokens


def hashed_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    counts = Counter(tokenize(text))
    if not counts:
        return vector

    for token, count in counts.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % dimensions
        sign = -1.0 if value & 1 else 1.0
        vector[index] += sign * (1.0 + math.log(count))

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def chunk_text(text: str, target_size: int = 950, overlap: int = 140) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    sentences = re.split(r"(?<=[。！？.!?])\s+", normalized)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= target_size:
            current = f"{current} {sentence}".strip()
            continue

        if current:
            chunks.append(current)
        if len(sentence) <= target_size:
            current = sentence
            continue

        start = 0
        while start < len(sentence):
            end = min(start + target_size, len(sentence))
            chunks.append(sentence[start:end])
            if end == len(sentence):
                current = ""
                break
            start = max(end - overlap, start + 1)

    if current:
        chunks.append(current)
    return chunks


class KnowledgeRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    source_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    country_region TEXT NOT NULL,
                    publication_date TEXT NOT NULL,
                    url TEXT NOT NULL,
                    authority_level TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    document_path TEXT,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    is_mock INTEGER NOT NULL DEFAULT 0,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES knowledge_documents(source_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_source
                ON knowledge_chunks(source_id);

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts
                USING fts5(
                    chunk_id UNINDEXED,
                    tokens,
                    title_tokens,
                    topic_tokens
                );
                """
            )
            chunk_count = connection.execute(
                "SELECT COUNT(*) FROM knowledge_chunks"
            ).fetchone()[0]
            fts_count = connection.execute(
                "SELECT COUNT(*) FROM knowledge_chunks_fts"
            ).fetchone()[0]
            if chunk_count != fts_count:
                connection.execute("DELETE FROM knowledge_chunks_fts")
                rows = connection.execute(
                    """
                    SELECT c.chunk_id, c.content, d.title, d.topic
                    FROM knowledge_chunks c
                    JOIN knowledge_documents d ON d.source_id = c.source_id
                    """
                ).fetchall()
                connection.executemany(
                    """
                    INSERT INTO knowledge_chunks_fts (
                        chunk_id, tokens, title_tokens, topic_tokens
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            row["chunk_id"],
                            " ".join(tokenize(row["content"])),
                            " ".join(tokenize(row["title"])),
                            " ".join(tokenize(row["topic"])),
                        )
                        for row in rows
                    ],
                )

    def ingest_document(self, document: KnowledgeDocument) -> int:
        content = normalize_text(document.content)
        chunks = chunk_text(content)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        fetched_at = utc_now()

        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO knowledge_documents (
                    source_id, title, source_type, publisher, country_region,
                    publication_date, url, authority_level, topic, document_path,
                    content, content_hash, is_mock, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    title = excluded.title,
                    source_type = excluded.source_type,
                    publisher = excluded.publisher,
                    country_region = excluded.country_region,
                    publication_date = excluded.publication_date,
                    url = excluded.url,
                    authority_level = excluded.authority_level,
                    topic = excluded.topic,
                    document_path = excluded.document_path,
                    content = excluded.content,
                    content_hash = excluded.content_hash,
                    is_mock = excluded.is_mock,
                    fetched_at = excluded.fetched_at
                """,
                (
                    document.source_id,
                    document.title,
                    document.source_type,
                    document.publisher,
                    document.country_region,
                    document.publication_date,
                    document.url,
                    document.authority_level,
                    document.topic,
                    document.document_path,
                    content,
                    content_hash,
                    int(document.is_mock),
                    fetched_at,
                ),
            )
            connection.execute(
                """
                DELETE FROM knowledge_chunks_fts
                WHERE chunk_id IN (
                    SELECT chunk_id FROM knowledge_chunks WHERE source_id = ?
                )
                """,
                (document.source_id,),
            )
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE source_id = ?",
                (document.source_id,),
            )
            for index, content_chunk in enumerate(chunks):
                chunk_id = f"{document.source_id}-C{index:04d}"
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id, source_id, chunk_index, content, embedding_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        document.source_id,
                        index,
                        content_chunk,
                        json.dumps(hashed_embedding(content_chunk)),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks_fts (
                        chunk_id, tokens, title_tokens, topic_tokens
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        " ".join(tokenize(content_chunk)),
                        " ".join(tokenize(document.title)),
                        " ".join(tokenize(document.topic)),
                    ),
                )
        return len(chunks)

    def stats(self) -> dict[str, int | bool]:
        with closing(self._connect()) as connection, connection:
            document_count = connection.execute(
                "SELECT COUNT(*) FROM knowledge_documents"
            ).fetchone()[0]
            chunk_count = connection.execute(
                "SELECT COUNT(*) FROM knowledge_chunks"
            ).fetchone()[0]
        return {
            "document_count": document_count,
            "chunk_count": chunk_count,
            "ready": chunk_count > 0,
        }

    def document_source(self, source_id: str) -> dict[str, str | None] | None:
        """Source metadata for one document, used to serve original evidence."""
        if not source_id:
            return None
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                """
                SELECT source_id, title, publisher, url, document_path, is_mock
                FROM knowledge_documents WHERE source_id = ?
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "source_id": row["source_id"],
            "title": row["title"],
            "publisher": row["publisher"],
            "url": row["url"] or None,
            "document_path": row["document_path"] or None,
            "is_mock": "1" if row["is_mock"] else "",
        }

    def all_chunks(self) -> Iterable[KnowledgeChunk]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                """
                SELECT
                    c.chunk_id, c.source_id, c.chunk_index, c.content,
                    c.embedding_json, d.title, d.source_type, d.publisher,
                    d.country_region, d.publication_date, d.url,
                    d.authority_level, d.topic, d.document_path, d.is_mock
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.source_id = c.source_id
                ORDER BY c.source_id, c.chunk_index
                """
            ).fetchall()
        for row in rows:
            yield self._row_to_chunk(row)

    def search_candidates(
        self,
        terms: list[str],
        limit: int = 800,
    ) -> list[KnowledgeChunk]:
        """Use SQLite to shortlist relevant chunks before BM25/vector ranking."""
        cleaned = []
        for term in terms:
            normalized = term.strip().lower()
            if len(normalized) < 2 or normalized in cleaned:
                continue
            cleaned.append(normalized)
            if len(cleaned) >= 14:
                break
        if not cleaned:
            return []

        match_query = " OR ".join(
            f'"{term.replace(chr(34), chr(34) * 2)}"' for term in cleaned
        )
        try:
            with closing(self._connect()) as connection, connection:
                fts_rows = connection.execute(
                    """
                    SELECT
                        c.chunk_id, c.source_id, c.chunk_index, c.content,
                        c.embedding_json, d.title, d.source_type, d.publisher,
                        d.country_region, d.publication_date, d.url,
                        d.authority_level, d.topic, d.document_path, d.is_mock
                    FROM knowledge_chunks_fts f
                    JOIN knowledge_chunks c ON c.chunk_id = f.chunk_id
                    JOIN knowledge_documents d ON d.source_id = c.source_id
                    WHERE knowledge_chunks_fts MATCH ?
                    ORDER BY bm25(
                        knowledge_chunks_fts, 1.0, 3.0, 2.0
                    )
                    LIMIT ?
                    """,
                    (match_query, limit),
                ).fetchall()
            if fts_rows:
                return [self._row_to_chunk(row) for row in fts_rows]
        except sqlite3.OperationalError:
            # Older SQLite builds can lack FTS5. The LIKE fallback below keeps
            # the application functional, only slower.
            pass

        score_parts: list[str] = []
        params: list[str] = []
        for term in cleaned:
            escaped = (
                term.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            score_parts.append(
                "(CASE WHEN lower(c.content) LIKE ? ESCAPE '\\' THEN 1 ELSE 0 END"
                " + CASE WHEN lower(d.title) LIKE ? ESCAPE '\\' THEN 3 ELSE 0 END"
                " + CASE WHEN lower(d.topic) LIKE ? ESCAPE '\\' THEN 2 ELSE 0 END)"
            )
            params.extend([pattern, pattern, pattern])

        score_sql = " + ".join(score_parts)
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT
                    c.chunk_id, c.source_id, c.chunk_index, c.content,
                    c.embedding_json, d.title, d.source_type, d.publisher,
                    d.country_region, d.publication_date, d.url,
                    d.authority_level, d.topic, d.document_path, d.is_mock,
                    ({score_sql}) AS match_score
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.source_id = c.source_id
                WHERE ({score_sql}) > 0
                ORDER BY match_score DESC, d.authority_level ASC
                LIMIT ?
                """,
                [*params, *params, limit],
            ).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> KnowledgeChunk:
        return KnowledgeChunk(
            chunk_id=row["chunk_id"],
            source_id=row["source_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            embedding=json.loads(row["embedding_json"]),
            title=row["title"],
            source_type=row["source_type"],
            publisher=row["publisher"],
            country_region=row["country_region"],
            publication_date=row["publication_date"],
            url=row["url"],
            authority_level=row["authority_level"],
            topic=row["topic"],
            document_path=row["document_path"],
            is_mock=bool(row["is_mock"]),
        )
