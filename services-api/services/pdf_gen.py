import os
import uuid
import html
import json
from datetime import datetime, timedelta
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUTPUT_DIR = "/app/generated_files"


def _get_styles():
    styles = getSampleStyleSheet()

    try:
        font_paths = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        for fp in font_paths:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont("KoreanFont", fp))

                title = ParagraphStyle(
                    "KTitle",
                    fontName="KoreanFont",
                    fontSize=18,
                    leading=24,
                    spaceAfter=12,
                )

                body = ParagraphStyle(
                    "KBody",
                    fontName="KoreanFont",
                    fontSize=11,
                    leading=17,
                    spaceAfter=8,
                )

                meta = ParagraphStyle(
                    "KMeta",
                    fontName="KoreanFont",
                    fontSize=9,
                    leading=13,
                    textColor="#666666",
                    spaceAfter=8,
                )

                return title, body, meta

    except Exception:
        pass

    return styles["h1"], styles["Normal"], styles["Normal"]


def _to_paragraph_text(text: Any) -> str:
    if not text:
        return ""

    escaped = html.escape(str(text))
    return escaped.replace("\n", "<br/>")


def _extract_pdf_data(original_prompt: Any, context: str = "") -> tuple[str, str]:
    """
    original_prompt가 아래 어떤 형태여도 처리:
    1. 일반 문자열
    2. dict 객체
    3. JSON 문자열
    """

    title = "Generated Document"

    if isinstance(original_prompt, dict):
        title = original_prompt.get("title") or title
        content = (
            original_prompt.get("content")
            or original_prompt.get("description")
            or context
            or json.dumps(original_prompt, ensure_ascii=False, indent=2)
        )
        return title, content

    if isinstance(original_prompt, str):
        stripped = original_prompt.strip()

        # JSON 문자열이면 dict로 파싱 시도
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    title = parsed.get("title") or title
                    content = (
                        parsed.get("content")
                        or parsed.get("description")
                        or context
                        or json.dumps(parsed, ensure_ascii=False, indent=2)
                    )
                    return title, content
            except json.JSONDecodeError:
                pass

        return title, original_prompt or context or "생성할 문서 내용이 없습니다."

    return title, context or "생성할 문서 내용이 없습니다."


async def execute_pdf_generation(
    service_name: str,
    service_type: str,
    original_prompt: Any,
    context: str,
    base_url: str,
) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = f"doc_{uuid.uuid4().hex[:10]}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    title_style, body_style, meta_style = _get_styles()

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    document_title, document_content = _extract_pdf_data(original_prompt, context)

    story = []
    story.append(Paragraph(_to_paragraph_text(document_title), title_style))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(_to_paragraph_text(document_content), body_style))
    story.append(Spacer(1, 6 * mm))

    story.append(
        Paragraph(
            f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            meta_style,
        )
    )

    doc.build(story)

    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
    file_url = f"{base_url.rstrip('/')}/files/{filename}"

    file_info = {
        "file_type": "PDF",
        "file_name": filename,
        "file_url": file_url,
        "mime_type": "application/pdf",
        "expires_at": expires_at,
        "description": f"PDF document generated for: {str(document_content)[:80]}",
    }

    return {
        "success": True,
        "data": {
            "file_url": file_url,
        },
        "file_info": file_info,
    }