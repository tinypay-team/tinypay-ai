import httpx
import re

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

COIN_MAP = {
    "bitcoin": "bitcoin", "비트코인": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "이더리움": "ethereum", "eth": "ethereum",
    "solana": "solana", "솔라나": "solana", "sol": "solana",
    "ripple": "ripple", "리플": "ripple", "xrp": "ripple",
    "dogecoin": "dogecoin", "도지코인": "dogecoin", "doge": "dogecoin",
}


def detect_coins(prompt: str) -> list:
    prompt_lower = prompt.lower()
    coins = []
    for keyword, coin_id in COIN_MAP.items():
        if keyword in prompt_lower and coin_id not in coins:
            coins.append(coin_id)
    return coins if coins else ["bitcoin"]


async def execute_crypto_service(service_name: str, service_type: str,
                                  original_prompt: str, context: str, base_url: str) -> dict:
    coins = detect_coins(original_prompt)
    ids = ",".join(coins)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(COINGECKO_URL, params={
            "ids": ids,
            "vs_currencies": "usd,krw",
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
        })
        resp.raise_for_status()
        data = resp.json()

    results = {}
    for coin_id, info in data.items():
        results[coin_id] = {
            "price_usd": info.get("usd"),
            "price_krw": info.get("krw"),
            "change_24h_pct": round(info.get("usd_24h_change", 0), 2),
            "market_cap_usd": info.get("usd_market_cap"),
            "volume_24h_usd": info.get("usd_24h_vol"),
        }

    return {"success": True, "data": results}
