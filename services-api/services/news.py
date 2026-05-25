import httpx
import os
import re

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
GNEWS_URL = "https://gnews.io/api/v4/search"

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_URL = "https://newsapi.org/v2/everything"


def extract_query(prompt: str) -> str:
    # Remove common Korean filler words to get the search query
    stopwords = ["조회", "알려줘", "찾아줘", "분석해줘", "보여줘", "관련", "최근", "뉴스"]
    words = prompt.split()
    keywords = [w for w in words if w not in stopwords]
    return " ".join(keywords[:5]) if keywords else prompt[:50]


async def execute_news_service(service_name: str, service_type: str,
                                original_prompt: str, context: str, base_url: str) -> dict:
    query = extract_query(original_prompt)

    # Try GNews first (free tier: 100 req/day)
    if GNEWS_API_KEY:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GNEWS_URL, params={
                "q": query,
                "lang": "ko",
                "max": 5,
                "apikey": GNEWS_API_KEY,
            })
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                return {
                    "success": True,
                    "data": {
                        "query": query,
                        "total_results": data.get("totalArticles", len(articles)),
                        "articles": [
                            {
                                "title": a.get("title"),
                                "description": a.get("description"),
                                "url": a.get("url"),
                                "published_at": a.get("publishedAt"),
                                "source": a.get("source", {}).get("name"),
                            }
                            for a in articles
                        ],
                    }
                }

    # Try NewsAPI
    if NEWSAPI_KEY:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(NEWSAPI_URL, params={
                "q": query,
                "language": "ko",
                "pageSize": 5,
                "apiKey": NEWSAPI_KEY,
            })
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                return {
                    "success": True,
                    "data": {
                        "query": query,
                        "total_results": data.get("totalResults", len(articles)),
                        "articles": [
                            {
                                "title": a.get("title"),
                                "description": a.get("description"),
                                "url": a.get("url"),
                                "published_at": a.get("publishedAt"),
                                "source": a.get("source", {}).get("name"),
                            }
                            for a in articles
                        ],
                    }
                }

    # Fallback: mock response if no API key
    return {
        "success": True,
        "data": {
            "query": query,
            "note": "No news API key configured. Add GNEWS_API_KEY or NEWSAPI_KEY env var.",
            "articles": [
                {
                    "title": f"[Mock] Latest news about {query}",
                    "description": "This is a mock news result. Configure GNEWS_API_KEY for real results.",
                    "url": "https://example.com",
                    "published_at": "2026-05-25T00:00:00Z",
                    "source": "Mock News",
                }
            ],
        }
    }
