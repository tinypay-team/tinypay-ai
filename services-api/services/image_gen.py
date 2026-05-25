import httpx
import os
import uuid
from datetime import datetime, timedelta

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_IMAGE_URL = "https://api.openai.com/v1/images/generations"


async def execute_image_generation(service_name: str, service_type: str,
                                    original_prompt: str, context: str, base_url: str) -> dict:
    if not OPENAI_API_KEY:
        return {
            "success": False,
            "data": None,
            "error": "OPENAI_API_KEY not configured",
        }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            OPENAI_IMAGE_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "dall-e-3",
                "prompt": original_prompt,
                "n": 1,
                "size": "1024x1024",
                "response_format": "url",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    image_url = data["data"][0]["url"]
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"

    file_info = {
        "file_type": "IMAGE",
        "file_name": f"generated_{uuid.uuid4().hex[:8]}.png",
        "file_url": image_url,
        "mime_type": "image/png",
        "expires_at": expires_at,
        "description": f"AI-generated image for: {original_prompt[:80]}",
    }

    return {"success": True, "data": {"image_url": image_url}, "file_info": file_info}
