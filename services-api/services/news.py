import httpx
import os
import xml.etree.ElementTree as ET
from urllib.parse import quote

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
GNEWS_URL     = "https://gnews.io/api/v4/search"

NEWSAPI_KEY   = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_URL   = "https://newsapi.org/v2/everything"

# Google News RSS (API 키 불필요)
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


def extract_query(prompt: str) -> str:
    stopwords = ["조회", "알려줘", "찾아줘", "분석해줘", "보여줘", "관련", "최근", "뉴스", "해줘", "주세요"]
    words = prompt.split()
    keywords = [w for w in words if w not in stopwords]
    return " ".join(keywords[:5]) if keywords else prompt[:50]


async def fetch_google_news_rss(query: str) -> dict | None:
    url = GOOGLE_NEWS_RSS.format(query=quote(query))
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return None

        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        if channel is None:
            return None

        items = channel.findall("item")[:5]
        articles = []
        for item in items:
            articles.append({
                "title":        item.findtext("title", ""),
                "description":  item.findtext("description", ""),
                "url":          item.findtext("link", ""),
                "published_at": item.findtext("pubDate", ""),
                "source":       (item.find("source").text if item.find("source") is not None else "Google News"),
            })

        return {
            "success": True,
            "data": {
                "query":         query,
                "total_results": len(articles),
                "articles":      articles,
            }
        }
    except Exception as e:
        return None


async def execute_news_service(service_name: str, service_type: str,
                                original_prompt: str, context: str, base_url: str) -> dict:
    query = extract_query(original_prompt)

    # 1) GNews API
    if GNEWS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(GNEWS_URL, params={
                    "q": query, "lang": "ko", "max": 5, "apikey": GNEWS_API_KEY,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    articles = data.get("articles", [])
                    return {
                        "success": True,
                        "data": {
                            "query":         query,
                            "total_results": data.get("totalArticles", len(articles)),
                            "articles": [
                                {
                                    "title":        a.get("title"),
                                    "description":  a.get("description"),
                                    "url":          a.get("url"),
                                    "published_at": a.get("publishedAt"),
                                    "source":       a.get("source", {}).get("name"),
                                }
                                for a in articles
                            ],
                        }
                    }
        except Exception:
            pass

    # 2) NewsAPI
    if NEWSAPI_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(NEWSAPI_URL, params={
                    "q": query, "language": "ko", "pageSize": 5, "apiKey": NEWSAPI_KEY,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    articles = data.get("articles", [])
                    return {
                        "success": True,
                        "data": {
                            "query":         query,
                            "total_results": data.get("totalResults", len(articles)),
                            "articles": [
                                {
                                    "title":        a.get("title"),
                                    "description":  a.get("description"),
                                    "url":          a.get("url"),
                                    "published_at": a.get("publishedAt"),
                                    "source":       a.get("source", {}).get("name"),
                                }
                                for a in articles
                            ],
                        }
                    }
        except Exception:
            pass

    # 3) Google News RSS (API 키 불필요)
    result = await fetch_google_news_rss(query)
    if result:
        return result

    # 4) 전부 실패 시
    return {
        "success": False,
        "data":  None,
        "error": f"뉴스 데이터를 가져오는 데 실패했습니다. (query: {query})",
    }
