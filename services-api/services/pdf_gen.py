import os
import uuid
import html as html_module
import json
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, XPreformatted,
    Table, TableStyle,
)
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
                quote = ParagraphStyle(
                    "KQuote",
                    parent=body,
                    leftIndent=12,
                    borderPadding=6,
                    backColor=colors.HexColor("#f8f8f8"),
                    textColor=colors.HexColor("#555555"),
                )
                code = ParagraphStyle(
                    "KCode",
                    parent=body,
                    fontSize=9,
                    leading=14,
                    leftIndent=8,
                    rightIndent=8,
                    borderPadding=6,
                    backColor=colors.HexColor("#f5f5f5"),
                )
                table_header = ParagraphStyle(
                    "KTableHeader",
                    parent=body,
                    fontSize=9,
                    leading=13,
                    textColor=colors.white,
                    alignment=1,
                )
                table_body = ParagraphStyle(
                    "KTableBody",
                    parent=body,
                    fontSize=9,
                    leading=13,
                    spaceAfter=0,
                )

                return {
                    "h1": h1, "h2": h2, "h3": h3, "body": body,
                    "li": li, "meta": meta, "quote": quote, "code": code,
                    "table_header": table_header, "table_body": table_body,
                }

    except Exception:
        pass

    base = styles["Normal"]
    quote = ParagraphStyle("Quote", parent=base, leftIndent=12)
    code = ParagraphStyle("Code", parent=base, fontName="Courier", fontSize=9, leading=12)
    table_header = ParagraphStyle("TableHeader", parent=base, fontSize=9, textColor=colors.white)
    table_body = ParagraphStyle("TableBody", parent=base, fontSize=9)
    return {
        "h1": styles["h1"], "h2": styles["h2"], "h3": styles["h3"],
        "body": base, "li": base, "meta": base, "quote": quote, "code": code,
        "table_header": table_header, "table_body": table_body,
    }


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

    # 내용을 무시할 태그 (CSS, JS, 메타 등)
    _SKIP_CONTENT_TAGS = {"head", "style", "script"}
    # 투명하게 통과시킬 태그 (html, body는 컨테이너만)
    _PASS_TAGS = {"html", "body", "meta", "link", "title"}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        # 내용 스킵 태그: 스택에 올려서 handle_data에서 무시
        if tag in self._SKIP_CONTENT_TAGS:
            self._tag_stack.append(tag)
            return

        # 투명 컨테이너 태그: 무시
        if tag in self._PASS_TAGS:
            return

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

        # 스킵 태그 닫기
        if tag in self._SKIP_CONTENT_TAGS:
            if tag in self._tag_stack:
                idx = len(self._tag_stack) - 1 - self._tag_stack[::-1].index(tag)
                self._tag_stack.pop(idx)
            return

        if tag in self._PASS_TAGS:
            return

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
        # head/style/script 내부 내용은 무시
        for skip in self._SKIP_CONTENT_TAGS:
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


def _markdown_inline(text: str) -> str:
    """일반적인 Markdown 인라인 문법을 ReportLab Paragraph 마크업으로 변환."""
    code_tokens: list[str] = []

    def stash_code(match: re.Match) -> str:
        code_tokens.append(
            f'<font color="#555555">{html_module.escape(match.group(1))}</font>'
        )
        return f"\x00CODE{len(code_tokens) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", stash_code, text)
    text = html_module.escape(text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: f'<link href="{m.group(2)}" color="#2563eb">{m.group(1)}</link>',
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<b>{m.group(1) or m.group(2)}</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)",
                  lambda m: f"<i>{m.group(1) or m.group(2)}</i>", text)

    for index, code in enumerate(code_tokens):
        text = text.replace(f"\x00CODE{index}\x00", code)
    return text


def _split_table_row(line: str) -> list[str]:
    """Markdown table 행을 셀 목록으로 분리."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _markdown_table(rows: list[list[str]], styles: dict) -> Table:
    column_count = max(len(row) for row in rows)
    normalized = [row + [""] * (column_count - len(row)) for row in rows]
    data = [
        [
            Paragraph(_markdown_inline(cell), styles["table_header" if row_index == 0 else "table_body"])
            for cell in row
        ]
        for row_index, row in enumerate(normalized)
    ]
    table = Table(data, colWidths=[170 * mm / column_count] * column_count, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
    ]))
    return table


def _markdown_to_flowables(text: str, styles: dict) -> list:
    """Markdown 문서를 ReportLab flowable 목록으로 변환."""
    flowables = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code_block = False

    def flush_paragraph():
        if paragraph_lines:
            content = " ".join(line.strip() for line in paragraph_lines)
            flowables.append(Paragraph(_markdown_inline(content), styles["body"]))
            paragraph_lines.clear()

    def flush_code():
        if code_lines:
            flowables.append(XPreformatted(html_module.escape("\n".join(code_lines)), styles["code"]))
            code_lines.clear()

    lines = text.splitlines()
    index = 0
    content_started = False

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush_paragraph()
            if in_code_block:
                flush_code()
            in_code_block = not in_code_block
            index += 1
            continue

        if in_code_block:
            code_lines.append(line)
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if (
            "|" in stripped
            and index + 1 < len(lines)
            and _is_table_separator(lines[index + 1].strip())
        ):
            flush_paragraph()
            table_rows = [_split_table_row(stripped)]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                table_rows.append(_split_table_row(lines[index]))
                index += 1
            flowables.append(_markdown_table(table_rows, styles))
            flowables.append(Spacer(1, 3 * mm))
            content_started = True
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            flowables.append(
                Paragraph(_markdown_inline(heading.group(2)), styles[f"h{min(level, 3)}"])
            )
            if level == 1:
                flowables.append(
                    HRFlowable(width="100%", thickness=1,
                               color=colors.HexColor("#333333"), spaceAfter=6)
                )
            content_started = True
            index += 1
            continue

        bold_title = re.fullmatch(r"\*\*(.+)\*\*|__(.+)__", stripped)
        if bold_title and not content_started:
            flush_paragraph()
            title = bold_title.group(1) or bold_title.group(2)
            flowables.append(Paragraph(_markdown_inline(title), styles["h1"]))
            flowables.append(
                HRFlowable(width="100%", thickness=1,
                           color=colors.HexColor("#333333"), spaceAfter=6)
            )
            content_started = True
            index += 1
            continue

        if re.match(r"^[^\w\s]\s*\S", stripped) and len(stripped) <= 40:
            flush_paragraph()
            flowables.append(Paragraph(_markdown_inline(stripped), styles["h2"]))
            content_started = True
            index += 1
            continue

        if re.match(r"^([-*_])(?:\s*\1){2,}\s*$", stripped):
            flush_paragraph()
            flowables.append(
                HRFlowable(width="100%", thickness=0.5,
                           color=colors.HexColor("#cccccc"), spaceAfter=4)
            )
            index += 1
            continue

        unordered = re.match(r"^[-+*]\s+(.+)$", stripped)
        ordered = re.match(r"^(\d+)[.)]\s+(.+)$", stripped)
        if unordered or ordered:
            flush_paragraph()
            bullet = "·" if unordered else f"{ordered.group(1)}."
            content = unordered.group(1) if unordered else ordered.group(2)
            flowables.append(
                Paragraph(f"{bullet}&nbsp;&nbsp;{_markdown_inline(content)}", styles["li"])
            )
            content_started = True
            index += 1
            continue

        quote = re.match(r"^>\s?(.*)$", stripped)
        if quote:
            flush_paragraph()
            flowables.append(Paragraph(_markdown_inline(quote.group(1)), styles["quote"]))
            content_started = True
            index += 1
            continue

        paragraph_lines.append(stripped)
        content_started = True
        index += 1

    flush_paragraph()
    flush_code()
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

    # HTML이면 파싱, 아니면 Markdown(일반 텍스트 포함) 처리
    if _is_html(document_content):
        story.extend(_html_to_flowables(document_content, styles))
    else:
        story.extend(_markdown_to_flowables(document_content, styles))

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
