from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .knowledge import KnowledgeDocument, normalize_text


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 GeopoliticalRiskResearchBot/0.2"
)


class PublicSourceCrawler:
    def __init__(self, timeout: float = 35.0):
        self.timeout = timeout

    def fetch_document(self, item: dict[str, str]) -> KnowledgeDocument:
        url = item["url"]
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.6",
        }
        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        is_pdf = "application/pdf" in content_type or url.lower().endswith(".pdf")
        if is_pdf:
            content = self._extract_pdf(response.content)
        else:
            content = self._extract_html(response.text)

        if len(content) < 200:
            raise ValueError(f"extracted content is too short: {len(content)} characters")

        return KnowledgeDocument(
            source_id=item["source_id"],
            title=item["title"],
            source_type=item["source_type"],
            publisher=item["publisher"],
            country_region=item["country_region"],
            publication_date=item["publication_date"],
            url=url,
            authority_level=item["authority_level"],
            topic=item["topic"],
            document_path=None,
            content=content[:250_000],
            is_mock=False,
        )

    @staticmethod
    def _extract_pdf(payload: bytes) -> str:
        reader = PdfReader(io.BytesIO(payload))
        pages = [page.extract_text() or "" for page in reader.pages]
        return normalize_text("\n".join(pages))

    @staticmethod
    def _extract_html(payload: str) -> str:
        soup = BeautifulSoup(payload, "html.parser")
        for element in soup(
            ["script", "style", "noscript", "svg", "nav", "header", "footer", "form"]
        ):
            element.decompose()

        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(attrs={"role": "main"})
            or soup.body
            or soup
        )
        return normalize_text(main.get_text(" ", strip=True))


def load_source_feed(path: Path) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))

