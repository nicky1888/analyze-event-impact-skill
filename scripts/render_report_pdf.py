#!/usr/bin/env python3
"""Render event-impact markdown reports to PDF.

Uses a styled ReportLab renderer when available and falls back to a plain-text
macOS cupsfilter renderer otherwise.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def convert_links(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)


def strip_inline_markdown(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text


def clean_text(text: str) -> str:
    return strip_inline_markdown(convert_links(text)).strip()


def is_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|").strip()
    if not stripped:
        return False
    return all(part.strip().replace("-", "").replace(":", "") == "" for part in stripped.split("|"))


def split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [clean_text(part.strip()) for part in stripped.split("|")]


def normalize_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    in_mermaid = False
    in_code = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```mermaid"):
            in_mermaid = True
            output.append("[Diagram available in the markdown source]")
            output.append("")
            continue

        if stripped.startswith("```"):
            if in_mermaid:
                in_mermaid = False
            else:
                in_code = not in_code
                if in_code:
                    output.append("[Code block]")
                else:
                    output.append("")
            continue

        if in_mermaid:
            continue

        if in_code:
            output.append(line)
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            title = clean_text(heading.group(2))
            prefix = "" if level == 1 else "  " * (level - 2) + "- "
            output.append(f"{prefix}{title}")
            output.append("")
            continue

        cleaned = clean_text(line)
        output.append(cleaned)

    normalized = "\n".join(output)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip() + "\n"
    return normalized


def parse_blocks(markdown: str) -> list[dict[str, object]]:
    lines = markdown.splitlines()
    blocks: list[dict[str, object]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```mermaid"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({"type": "mermaid", "text": "\n".join(code_lines).strip()})
            i += 1
            continue

        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({"type": "code", "text": "\n".join(code_lines).rstrip()})
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            blocks.append(
                {"type": "heading", "level": len(heading.group(1)), "text": clean_text(heading.group(2))}
            )
            i += 1
            continue

        if stripped.startswith("|"):
            table_lines = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1

            rows = [split_table_row(item) for item in table_lines if not is_table_separator(item)]
            if rows:
                blocks.append({"type": "table", "rows": rows})
            continue

        bullet_match = re.match(r"^([-*]|\d+\.)\s+(.*)$", stripped)
        if bullet_match:
            items = [clean_text(bullet_match.group(2))]
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                nxt_match = re.match(r"^([-*]|\d+\.)\s+(.*)$", nxt)
                if nxt_match:
                    items.append(clean_text(nxt_match.group(2)))
                    i += 1
                    continue
                if not nxt:
                    i += 1
                    break
                if lines[i].startswith("  ") or lines[i].startswith("\t"):
                    items[-1] = f"{items[-1]} {clean_text(nxt)}"
                    i += 1
                    continue
                break
            blocks.append({"type": "bullets", "items": items})
            continue

        para_lines = [clean_text(line)]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            nxt_stripped = nxt.strip()
            if not nxt_stripped:
                i += 1
                break
            if (
                re.match(r"^(#{1,6})\s+", nxt_stripped)
                or nxt_stripped.startswith("|")
                or nxt_stripped.startswith("```")
                or re.match(r"^([-*]|\d+\.)\s+", nxt_stripped)
            ):
                break
            para_lines.append(clean_text(nxt))
            i += 1
        blocks.append({"type": "paragraph", "text": " ".join(part for part in para_lines if part).strip()})

    return blocks


def run_command(cmd: list[str], *, stdout_path: Path | None = None) -> None:
    if stdout_path is None:
        subprocess.run(cmd, check=True)
        return
    with stdout_path.open("wb") as handle:
        subprocess.run(cmd, check=True, stdout=handle)


def write_plain_pdf(normalized: str, output_pdf: Path) -> None:
    cupsfilter = shutil.which("cupsfilter")
    if not cupsfilter:
        raise RuntimeError("cupsfilter is not available on this machine.")

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_txt = Path(tmpdir) / "report.txt"
        temp_txt.write_text(normalized, encoding="utf-8")
        run_command([cupsfilter, "-m", "application/pdf", str(temp_txt)], stdout_path=output_pdf)


def reportlab_available() -> bool:
    try:
        import reportlab  # noqa: F401
    except Exception:
        return False
    return True


def write_styled_pdf(markdown: str, output_pdf: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.pdfmetrics import registerFont
    from reportlab.platypus import (
        KeepTogether,
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    registerFont(UnicodeCIDFont("STSong-Light"))

    styles = getSampleStyleSheet()
    font = "STSong-Light"
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName=font,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName=font,
            fontSize=15,
            leading=20,
            textColor=colors.HexColor("#0F172A"),
            borderPadding=0,
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeading",
            parent=styles["Heading3"],
            fontName=font,
            fontSize=12.5,
            leading=17,
            textColor=colors.HexColor("#1D4ED8"),
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyCN",
            parent=styles["BodyText"],
            fontName=font,
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallCN",
            parent=styles["BodyText"],
            fontName=font,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeCN",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8.5,
            leading=11,
            backColor=colors.HexColor("#F8FAFC"),
            borderPadding=6,
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0.5,
            borderRadius=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCellCN",
            parent=styles["BodyText"],
            fontName=font,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1F2937"),
            wordWrap="CJK",
            spaceAfter=0,
            spaceBefore=0,
        )
    )

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title="Event Impact Report",
    )

    blocks = parse_blocks(markdown)
    story: list[object] = []
    page_width = A4[0] - doc.leftMargin - doc.rightMargin

    def header_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.setLineWidth(0.6)
        canvas.line(doc.leftMargin, A4[1] - 12 * mm, A4[0] - doc.rightMargin, A4[1] - 12 * mm)
        canvas.setFont(font, 8.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(doc.leftMargin, 9 * mm, "Generated by analyze-event-impact")
        canvas.drawRightString(A4[0] - doc.rightMargin, 9 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    for block in blocks:
        block_type = block["type"]

        if block_type == "heading":
            level = int(block["level"])
            text = block["text"]
            if level == 1:
                story.append(Paragraph(str(text), styles["ReportTitle"]))
                story.append(Spacer(1, 4))
            elif level == 2:
                story.append(Paragraph(str(text), styles["SectionHeading"]))
            else:
                story.append(Paragraph(str(text), styles["SubHeading"]))
            continue

        if block_type == "paragraph":
            story.append(Paragraph(str(block["text"]), styles["BodyCN"]))
            continue

        if block_type == "bullets":
            for item in block["items"]:
                story.append(Paragraph(f"- {item}", styles["BodyCN"]))
            story.append(Spacer(1, 2))
            continue

        if block_type == "table":
            rows = block["rows"]
            col_count = max(len(row) for row in rows)
            normalized_rows = [row + [""] * (col_count - len(row)) for row in rows]
            col_width = page_width / col_count
            font_size = 8.5 if col_count <= 5 else 8 if col_count <= 7 else 7.2
            leading = 11 if col_count <= 5 else 10 if col_count <= 7 else 9
            cell_style = ParagraphStyle(
                name=f"TableCellCN_{col_count}",
                parent=styles["TableCellCN"],
                fontSize=font_size,
                leading=leading,
            )
            wrapped_rows = [
                [Paragraph(cell or "", cell_style) for cell in row] for row in normalized_rows
            ]
            table = Table(wrapped_rows, colWidths=[col_width] * col_count, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ]
                )
            )
            story.append(KeepTogether([table, Spacer(1, 8)]))
            continue

        if block_type == "code":
            if block["text"]:
                story.append(Preformatted(str(block["text"]), styles["CodeCN"]))
                story.append(Spacer(1, 6))
            continue

        if block_type == "mermaid":
            placeholder = Table(
                [[Paragraph("Diagram available in markdown source. Render graph separately if needed.", styles["BodyCN"])]],
                colWidths=[page_width],
            )
            placeholder.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), font),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#CBD5E1")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(placeholder)
            story.append(Spacer(1, 6))
            continue

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)


def create_preview(output_pdf: Path) -> None:
    qlmanage = shutil.which("qlmanage")
    if qlmanage:
        run_command([qlmanage, "-t", "-s", "1200", "-o", str(output_pdf.parent), str(output_pdf)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an event-impact markdown report to PDF.")
    parser.add_argument("input_path", help="Path to the markdown or text report")
    parser.add_argument("output_pdf", help="Path to write the PDF")
    parser.add_argument(
        "--normalized-text",
        help="Optional path to save the normalized text used for fallback rendering",
    )
    parser.add_argument(
        "--preview-png",
        action="store_true",
        help="Also render a PNG preview next to the PDF using qlmanage",
    )
    parser.add_argument(
        "--renderer",
        choices=["auto", "reportlab", "text"],
        default="auto",
        help="PDF renderer to use. Defaults to auto.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    output_pdf = Path(args.output_pdf).expanduser().resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    raw_text = input_path.read_text(encoding="utf-8")
    normalized = normalize_markdown(raw_text)

    if args.normalized_text:
        normalized_text_path = Path(args.normalized_text).expanduser().resolve()
        normalized_text_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_text_path.write_text(normalized, encoding="utf-8")

    renderer = args.renderer
    if renderer == "auto":
        renderer = "reportlab" if reportlab_available() else "text"

    if renderer == "reportlab":
        try:
            write_styled_pdf(raw_text, output_pdf)
        except Exception as exc:
            print(f"Styled PDF rendering failed, falling back to text renderer: {exc}", file=sys.stderr)
            write_plain_pdf(normalized, output_pdf)
    else:
        write_plain_pdf(normalized, output_pdf)

    if args.preview_png:
        create_preview(output_pdf)

    print(f"PDF written to {output_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
