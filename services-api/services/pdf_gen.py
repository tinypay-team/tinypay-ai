import os
import uuid
import html as html_module
import json
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
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

                h1 = ParagraphStyle(
                    "KH1",
                    fontName="KoreanFont",
                    fontSize=20,
                    leading=28,
                    spaceAfter=10,
                    spaceBefore=6,
                    textColor=colors.HexColor("#111111"),
                )
                h2 = ParagraphStyle(
                    "KH2",
                    fontName="KoreanFont",
                    fontSize=15,
                    leading=22,
                    spaceAfter=8,
                    spaceBefore=10,
                    textColor=colors.HexColor("#222222"),
                )
                h3 = ParagraphStyle(
                    "KH3",
                    fontName="KoreanFont",
                    fontSize=12,
                    leading=18,
                    spaceAfter=6,
                    spaceBefore=8,
                    textColor=colors.HexColor("#444444"),
                )
                body = ParagraphStyle(
                    "KBody",
                    fontName="KoreanFont",
                    fontSize=11,
                    leading=18,
                    spaceAfter=6,
                )
                li = ParagraphStyle(
                    "KLi",
                    fontName="KoreanFont",
                    fontSize=11,
                    leading=18,
                    spaceAfter=4,
                    leftIndent=16,
                    bulletIndent=4,
                )
                meta = ParagraphStyle(
                    "KMeta",
                    fontName="KoreanFont",
                    fontSize=9,
                    leading=13,
                    textColor=colors.HexColor("#888888"),
                    spaceAfter=8,
                )

                return {"h1": h1, "h2": h2, "h3": h3, "body": body, "li": li, "meta": meta}

    except Exception:
        pass

    base = styles["Normal"]
    return {"h1": styles["h1"], "h2": styles["h2"], "h3": styles["h3"],
            "body": base, "li": base, "meta": base}


# ─── HTML → ReportLab flowables 변환기 ───────────────────────────────────────

class _HtmlToFlowables(HTMLParser):
    """HTML을 파싱하여 ReportLab Flowable 목록으로 변환."""

    def __init__(self, styles: dict):
        super().__init__()
        self._styles = styles
        self._flowables: list = []
        self._buf: str = ""          # 현재 태그 내 텍스트 버퍼
        self._tag_stack: list = []   # 열린 블록 태그 스택
        self._inline_stack: list = []  # 열린 인라인 태그 스택
        self._ol_counter: int = 0

    # ── 인라인 태그 매핑 ──────────────────────────────────────────────────────

    _INLINE_OPEN = {
        "strong": "<b>", "b": "<b>",
        "em": "<i>",     "i": "<i>",
        "u": "<u>",
    }
    _INLINE_CLOSE = {
        "strong": "</b>", "b": "</b>",
        "em": "</i>",     "i": "</i>",
        "u": "</u>",
    }

    # ── 블록 태그 ─────────────────────────────────────────────────────────────

    _BLOCK_TAGS = {"h1", "h2", "h3", "p", "li", "div"}
    _VOID_TAGS  = {"br", "hr"}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag in self._VOID_TAGS:
            if tag == "br":
                self._buf += "<br/>"
            elif tag == "hr":
                self._flush_buf()
                self._flowables.append(
                    HRFlowable(width="100%", thickness=0.5,
                               color=colors.HexColor("#cccccc"), spaceAfter=4)
                )
            return

        if tag in ("ul", "ol"):
            self._flush_buf()
            if tag == "ol":
                self._ol_counter = 0
            self._tag_stack.append(tag)
            return

        if tag in self._BLOCK_TAGS:
            self._flush_buf()
            self._tag_stack.append(tag)
            return

        if tag in self._INLINE_OPEN:
            self._buf += self._INLINE_OPEN[tag]
            self._inline_stack.append(tag)
            return

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in self._INLINE_CLOSE:
            self._buf += self._INLINE_CLOSE[tag]
            if tag in self._inline_stack:
                self._inline_stack.remove(tag)
            return

        if tag in self._BLOCK_TAGS:
            self._flush_buf(tag)
            if tag in self._tag_stack:
                idx = len(self._tag_stack) - 1 - self._tag_stack[::-1].index(tag)
                self._tag_stack.pop(idx)
            return

        if tag in ("ul", "ol"):
            self._flush_buf()
            if tag in self._tag_stack:
                idx = len(self._tag_stack) - 1 - self._tag_stack[::-1].index(tag)
                self._tag_stack.pop(idx)
            self._ol_counter = 0
            return

    def handle_data(self, data):
        # <head>/<style>/<script> 내용은 무시
        for skip in ("head", "style", "script"):
            if skip in self._tag_stack:
                return
        self._buf += data

    def _flush_buf(self, closing_tag: str = ""):
        text = self._buf.strip()
        self._buf = ""

        if not text:
            return

        # 현재 블록 컨텍스트 파악
        block = closing_tag or (self._tag_stack[-1] if self._tag_stack else "p")

        if block == "h1":
            self._flowables.append(Paragraph(text, self._styles["h1"]))
            self._flowables.append(
                HRFlowable(width="100%", thickness=1,
                           color=colors.HexColor("#333333"), spaceAfter=6)
            )
        elif block == "h2":
            self._flowables.append(Paragraph(text, self._styles["h2"]))
        elif block == "h3":
            self._flowables.append(Paragraph(text, self._styles["h3"]))
        elif block == "li":
            parent = "ol"
            for t in reversed(self._tag_stack):
                if t in ("ul", "ol"):
                    parent = t
                    break
            if parent == "ol":
                self._ol_counter += 1
                bullet = f"{self._ol_counter}."
            else:
                bullet = "·"
            self._flowables.append(
                Paragraph(f"{bullet}&nbsp;&nbsp;{text}", self._styles["li"])
            )
        else:
            self._flowables.append(Paragraph(text, self._styles["body"]))

    def result(self) -> list:
        self._flush_buf()
        return self._flowables


def _is_html(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("<!doctype") or t.startswith("<html") or t.startswith("<h1") or t.startswith("<p")


def _html_to_flowables(html_text: str, styles: dict) -> list:
    parser = _HtmlToFlowables(styles)
    parser.feed(html_text)
    return parser.result()


def _plain_to_flowables(text: str, styles: dict) -> list:
    """기존 plain text → ReportLab flowable 변환 (마크다운 부분 정리 포함)."""
    flowables = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            flowables.append(Spacer(1, 3 * mm))
            continue
        escaped = html_module.escape(stripped)
        flowables.append(Paragraph(escaped, styles["body"]))
    return flowables


# ─── PDF 생성 함수 ──────────────────────────────────────────────────────────

def _extract_pdf_data(original_prompt: Any, context: str = "") -> tuple[str, str]:
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
        return title, stripped or context or "생성할 문서 내용이 없습니다."

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

    styles = _get_styles()

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    _, document_content = _extract_pdf_data(original_prompt, context)

    story: list = []

    # HTML이면 파싱, 아니면 plain text 처리
    if _is_html(document_content):
        story.extend(_html_to_flowables(document_content, styles))
    else:
        story.extend(_plain_to_flowables(document_content, styles))

    story.append(Spacer(1, 6 * mm))
    story.append(
        HRFlowable(width="100%", thickness=0.5,
                   color=colors.HexColor("#cccccc"), spaceAfter=4)
    )
    story.append(
        Paragraph(
            f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            styles["meta"],
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
        "data": {"file_url": file_url},
        "file_info": file_info,
    }
