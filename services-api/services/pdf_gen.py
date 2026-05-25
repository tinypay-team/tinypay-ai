import os
import uuid
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT

OUTPUT_DIR = "/app/generated_files"


def _get_styles():
    styles = getSampleStyleSheet()
    try:
        # Try to register a Korean-compatible font if available
        font_paths = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont("KoreanFont", fp))
                normal = ParagraphStyle("KNormal", fontName="KoreanFont", fontSize=11, leading=16)
                title = ParagraphStyle("KTitle", fontName="KoreanFont", fontSize=16, leading=22, spaceAfter=10)
                return title, normal
    except Exception:
        pass
    return styles["h1"], styles["Normal"]


async def execute_pdf_generation(service_name: str, service_type: str,
                                  original_prompt: str, context: str, base_url: str) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"doc_{uuid.uuid4().hex[:10]}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    title_style, body_style = _get_styles()

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    story = []
    story.append(Paragraph("Generated Document", title_style))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(f"Request: {original_prompt}", body_style))
    story.append(Spacer(1, 4*mm))
    if context:
        story.append(Paragraph(f"Context: {context}", body_style))
        story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", body_style))

    doc.build(story)

    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
    file_url = f"{base_url}/files/{filename}"

    file_info = {
        "file_type": "PDF",
        "file_name": filename,
        "file_url": file_url,
        "mime_type": "application/pdf",
        "expires_at": expires_at,
        "description": f"PDF document generated for: {original_prompt[:80]}",
    }

    return {"success": True, "data": None, "file_info": file_info}
