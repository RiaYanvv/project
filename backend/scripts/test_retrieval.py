from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings
from app.knowledge import KnowledgeRepository
from app.retrieval import HybridRetrievalProvider, MockRetrievalProvider
from app.schemas import RetrievalQuery



settings = Settings.from_env()


repository = KnowledgeRepository(settings.database_path)

class EmptyFallback:
    def search(self, query):
        return []

    def search(self, query):
        return []


fallback = EmptyFallback()

retriever = HybridRetrievalProvider(
        repository=repository,
        fallback=fallback,
        web_search=None,
        web_search_limit=0,
    )

query = RetrievalQuery(
    industry="battery_ev",
    products=["battery", "electric vehicle"],
    home_country="CN",
    production_countries=["CN"],
    target_markets=["US"],
    decision_question=(
        "What U.S. trade and policy restrictions may affect "
        "Chinese battery and electric vehicle supply chains?"
    ),
    restrictions=[
        "tariff_pressure",
        "export_controls",
        "sanctions_concerns",
    ],
    limit=5,
)

results = retriever.search(query)

print()
print("=" * 70)
print("RETRIEVAL TEST")
print("=" * 70)
print(f"Database: {settings.database_path}")
print(f"Results returned: {len(results)}")

for i, item in enumerate(results, start=1):
        print()
        print("-" * 70)
        print(f"RESULT #{i}")
        print(f"Evidence ID: {item.evidence_id}")
        print(f"Title: {item.title}")
        print(f"Publisher: {item.publisher}")
        print(f"Country/Region: {item.country_region}")
        print(f"Topic: {item.topic}")
        print(f"Authority: {item.authority_level}")
        print(f"Score: {item.relevance_score}")
        print(f"Document path: {item.document_path}")
        print()
        print("Content:")
        print(item.content[:800])


