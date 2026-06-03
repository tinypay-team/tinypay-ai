import base64
import os
import uuid
from datetime import datetime, timedelta

import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_IMAGE_URL = "https://api.openai.com/v1/images/generations"


async def execute_image_generation(
    service_name: str,
    service_type: str,
    original_prompt: str,
    context: str,
    base_url: str
) -> dict:
    if not OPENAI_API_KEY:
        return {
            "success": False,
            "data": None,
            "error": "OPENAI_API_KEY not configured",
        }

    payload = {
        "model": "gpt-image-1",
        "prompt": original_prompt,
        "size": "1024x1024",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            OPENAI_IMAGE_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if resp.status_code >= 400:
            return {
                "success": False,
                "data": None,
                "error": resp.text,
            }

        data = resp.json()

    image_b64 = data["data"][0]["b64_json"]
    image_bytes = base64.b64decode(image_b64)

    file_name = f"generated_{uuid.uuid4().hex[:8]}.png"
    file_path = f"/app/generated_files/{file_name}"

    os.makedirs("/app/generated_files", exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    file_url = f"{base_url.rstrip('/')}/files/{file_name}"
    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"

    file_info = {
        "file_type": "IMAGE",
        "file_name": file_name,
        "file_url": file_url,
        "mime_type": "image/png",
        "expires_at": expires_at,
        "description": f"AI-generated image for: {original_prompt[:80]}",
    }

    return {
        "success": True,
        "data": {
            "image_url": file_url,
        },
        "file_info": file_info,
    }