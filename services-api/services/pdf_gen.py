import os
import uuid
import html
from datetime import datetime, timedelta

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


def _to_paragraph_text(text: str) -> str:
    """
    일반 텍스트를 ReportLab Paragraph에서 안전하게 표시할 수 있게 변환.
    - HTML escape 처리
    - 줄바꿈을 <br/>로 변환
    """
    if not text:
        return ""

    escaped = html.escape(str(text))
    return escaped.replace("\n", "<br/>")


async def execute_pdf_generation(
    service_name: str,
    service_type: str,
    original_prompt: str,
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

    # 핵심:
    # original_prompt에는 "PDF로 만들어줘" 같은 요청문이 아니라
    # Dify의 '파일 내용 구조화 LLM' 결과, 즉 실제 문서 본문을 넣어야 함.
    document_content = original_prompt or context or "생성할 문서 내용이 없습니다."

    story = []
    story.append(Paragraph("Generated Document", title_style))
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
        "description": f"PDF document generated for: {document_content[:80]}",
    }

    return {
        "success": True,
        "data": {
            "file_url": file_url,
        },
        "file_info": file_info,
    }