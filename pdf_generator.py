from datetime import datetime
from typing import Any, Dict, List
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Calibri Font Registration (Fallback to Helvetica if absent)
FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

try:
    windows_fonts = Path("C:/Windows/Fonts")
    if (windows_fonts / "calibri.ttf").exists():
        pdfmetrics.registerFont(TTFont("Calibri", str(windows_fonts / "calibri.ttf")))
        FONT_NORMAL = "Calibri"
    if (windows_fonts / "calibrib.ttf").exists():
        pdfmetrics.registerFont(TTFont("Calibri-Bold", str(windows_fonts / "calibrib.ttf")))
        FONT_BOLD = "Calibri-Bold"
    if (windows_fonts / "calibrii.ttf").exists():
        pdfmetrics.registerFont(TTFont("Calibri-Italic", str(windows_fonts / "calibrii.ttf")))
        FONT_ITALIC = "Calibri-Italic"
    if (windows_fonts / "calibriz.ttf").exists():
        pdfmetrics.registerFont(TTFont("Calibri-BoldItalic", str(windows_fonts / "calibriz.ttf")))

    if FONT_NORMAL == "Calibri":
        pdfmetrics.registerFontFamily(
            "Calibri",
            normal="Calibri",
            bold="Calibri-Bold" if (windows_fonts / "calibrib.ttf").exists() else "Calibri",
            italic="Calibri-Italic" if (windows_fonts / "calibrii.ttf").exists() else "Calibri",
            boldItalic="Calibri-BoldItalic" if (windows_fonts / "calibriz.ttf").exists() else "Calibri",
        )
except Exception:
    pass


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute total pages and add header/footer."""

    def __init__(self, *args, report_title: str = "Database Metadata Insights Report", **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = report_title
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont(FONT_NORMAL, 9)
        self.setFillColor(colors.HexColor("#4B5563"))

        width, height = self._pagesize
        margin = 36.0

        # Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(margin, height - 30, self.report_title)
            self.setStrokeColor(colors.HexColor("#E5E7EB"))
            self.setLineWidth(0.5)
            self.line(margin, height - 36, width - margin, height - 36)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.setLineWidth(0.5)
        self.line(margin, 44, width - margin, 44)

        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(width - margin, 30, page_str)
        self.drawString(margin, 30, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        self.restoreState()


class PDFReportGenerator:
    """Generates structured PDF reports for Database Metadata Insights."""

    def __init__(self, output_dir: str | Path | None = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).resolve().parent / "reports"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        reports: List[Dict[str, Any]],
        database_name: str = "MySQL",
        credentials_info: Dict[str, Any] | None = None,
    ) -> Path:
        """
        Builds a landscape PDF report file containing tables for each insight in `reports`.
        Automatically handles large schemas spanning across multi-page tables seamlessly.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_prefix = database_name.lower().replace(" ", "_")
        filename = f"{db_prefix}_metadata_report_{timestamp}.pdf"
        filepath = self.output_dir / filename

        page_width, page_height = landscape(letter)
        left_margin = 36.0
        right_margin = 36.0
        top_margin = 48.0
        bottom_margin = 54.0

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=(page_width, page_height),
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
        )

        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontName=FONT_BOLD,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1E3A8A"),
            spaceAfter=6,
        )
        
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName=FONT_NORMAL,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=15,
        )

        section_heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True,
        )

        note_style = ParagraphStyle(
            "SectionNote",
            parent=styles["Italic"],
            fontName=FONT_ITALIC,
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=6,
            keepWithNext=True,
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            fontName=FONT_BOLD,
            fontSize=10,
            leading=13,
            textColor=colors.white,
            alignment=0,
        )

        table_cell_style = ParagraphStyle(
            "TableCell",
            fontName=FONT_NORMAL,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#111827"),
            alignment=0,
        )

        story = []

        # Title Banner
        db_type = database_name if database_name else "Database"
        title_text = f"{db_type} Metadata Insights Report" if not db_type.endswith("Report") else db_type
        story.append(Paragraph(title_text, title_style))
        
        host_info = credentials_info.get("host", "localhost") if credentials_info else "localhost"
        raw_db = credentials_info.get("database") if credentials_info else None
        db_info = raw_db if raw_db else "ALL DATABASES"
        
        sub_text = (
            f"<b>Database:</b> {db_info} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Host:</b> {host_info} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        story.append(Paragraph(sub_text, subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceAfter=15))

        total_printable_width = page_width - left_margin - right_margin  # 792 - 72 = 720 pt

        total_reports = len(reports)
        for index, r in enumerate(reports, start=1):
            report_title = r.get("title", f"Report {index}")
            headers = r.get("headers", [])
            rows = r.get("rows", [])
            note = r.get("note")

            import re
            title_text = str(report_title).strip()
            clean_title = re.sub(r"^\d+\.\s*", "", title_text).strip()
            heading_text = f"{index}. {clean_title}"

            MAX_PDF_ROWS = 200
            if len(rows) > MAX_PDF_ROWS:
                display_rows = rows[:MAX_PDF_ROWS]
                rows_note = f"Displaying top {MAX_PDF_ROWS} of {len(rows)} records."
                note = f"{note} | {rows_note}" if note else rows_note
            else:
                display_rows = rows

            story.append(Paragraph(heading_text, section_heading_style))
            
            if note:
                story.append(Paragraph(f"Note: {note}", note_style))

            if not display_rows:
                if r.get("error"):
                    error_style = ParagraphStyle(
                        "ErrorNote",
                        parent=styles["Normal"],
                        fontName=FONT_BOLD,
                        fontSize=9.5,
                        leading=13,
                        textColor=colors.HexColor("#DC2626"),
                        spaceAfter=6,
                    )
                    story.append(Paragraph(f"<b>Query Error:</b> {r['error']}", error_style))
                else:
                    story.append(Paragraph("No records found.", note_style))
            else:
                header_row = [Paragraph(str(h), table_header_style) for h in headers]
                data_matrix = [header_row]

                for row in display_rows:
                    formatted_row = []
                    for i in range(len(headers)):
                        val_str = str(row[i]) if (i < len(row) and row[i] is not None) else "-"
                        if len(val_str) > 500:
                            val_str = val_str[:497] + "..."
                        # Always use Paragraph so text wraps/clips within column width.
                        # Raw strings overflow into adjacent columns when column is narrow.
                        formatted_row.append(Paragraph(val_str, table_cell_style))
                    data_matrix.append(formatted_row)

                # Smart column width calculation:
                # 1. Cap long content at 60 chars (text wraps in cell, doesn't need proportional extra width)
                # 2. Enforce minimum width = max(header_chars * 7pt, 60pt) so headers always fit
                # 3. Cap any single column at 45% of total width to prevent one wide column crushing others
                # 4. Normalize final widths to exactly fill total_printable_width
                num_cols = len(headers)
                if num_cols > 0:
                    CAP_CHARS = 60          # long text wraps — cap its contribution
                    CHAR_WIDTH_PT = 7.0     # approx Calibri 9.5pt character width in points
                    MAX_COL_FRACTION = 0.45 # no single column may claim more than 45% of width

                    col_scores = []
                    col_min_widths = []
                    for i in range(num_cols):
                        h_len = len(str(headers[i]))
                        d_len = max(
                            (len(str(row[i])) for row in display_rows if i < len(row)),
                            default=0,
                        )
                        # Cap the effective content length so long SQL doesn't dominate
                        effective_len = min(max(h_len, d_len, 4), CAP_CHARS)
                        col_scores.append(effective_len)
                        # Minimum width: enough for the header text + padding
                        col_min_widths.append(max(h_len * CHAR_WIDTH_PT + 8, 60.0))

                    max_single = MAX_COL_FRACTION * total_printable_width
                    sum_scores = sum(col_scores)
                    if sum_scores > 0:
                        # Proportional allocation
                        raw_widths = [(s / sum_scores) * total_printable_width for s in col_scores]
                        # Apply per-column caps: enforce minimum and maximum
                        raw_widths = [
                            max(col_min_widths[i], min(raw_widths[i], max_single))
                            for i in range(num_cols)
                        ]
                        # Normalize so columns fill exactly total_printable_width
                        tot_w = sum(raw_widths)
                        col_widths = [(w / tot_w) * total_printable_width for w in raw_widths]
                    else:
                        col_widths = [total_printable_width / num_cols] * num_cols
                else:
                    col_widths = [total_printable_width]

                # Table with header row repeated on multi-page splits
                t = Table(data_matrix, colWidths=col_widths, repeatRows=1)
                
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                    ("FONTNAME", (0, 1), (-1, -1), FONT_NORMAL),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 9.5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ]))
                story.append(t)

        canvas_factory = lambda *args, **kwargs: NumberedCanvas(*args, report_title=f"{database_name} Metadata Insights Report", **kwargs)
        doc.build(story, canvasmaker=canvas_factory)
        return filepath

    def generate_data_insights_report(
        self,
        payload: Dict[str, Any],
        database_name: str = "Database",
        credentials_info: Dict[str, Any] | None = None,
    ) -> Path:
        """
        Builds a landscape PDF report file containing Data Insights profiling, quality metrics,
        column profiles, and imputation recommendations structured matching PySpark EDA Statistics Report.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db = payload.get("database", "DB")
        schema = payload.get("schema", "schema")
        table = payload.get("table", "table")
        filename = f"EDA_Statistics_insights_{db}_{schema}_{table}_{timestamp}.pdf"
        filepath = self.output_dir / filename

        page_width, page_height = landscape(letter)
        left_margin = 36.0
        right_margin = 36.0
        top_margin = 48.0
        bottom_margin = 54.0

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=(page_width, page_height),
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
        )

        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            "DocTitleDataInsights",
            parent=styles["Heading1"],
            fontName=FONT_BOLD,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1E3A8A"),
            spaceAfter=6,
        )
        
        subtitle_style = ParagraphStyle(
            "DocSubTitleDataInsights",
            parent=styles["Normal"],
            fontName=FONT_NORMAL,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=15,
        )

        section_heading_style = ParagraphStyle(
            "SectionHeadingDataInsights",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True,
        )

        note_style = ParagraphStyle(
            "SectionNoteDataInsights",
            parent=styles["Italic"],
            fontName=FONT_ITALIC,
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=6,
            keepWithNext=True,
        )

        table_header_style = ParagraphStyle(
            "TableHeaderDataInsights",
            fontName=FONT_BOLD,
            fontSize=10,
            leading=13,
            textColor=colors.white,
            alignment=0,
        )

        table_cell_style = ParagraphStyle(
            "TableCellDataInsights",
            fontName=FONT_NORMAL,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#111827"),
            alignment=0,
        )

        table_cell_bold = ParagraphStyle(
            "TableCellBoldDataInsights",
            fontName=FONT_BOLD,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#111827"),
            alignment=0,
        )

        story = []

        # Title Banner (Exact Database Insights Header Design)
        story.append(Paragraph(f"Data Insights EDA Profiling Report — {db}.{schema}.{table}", title_style))
        
        host_info = credentials_info.get("host", "localhost") if credentials_info else "localhost"
        sub_text = (
            f"<b>Engine:</b> {database_name} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Database:</b> {db} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Schema:</b> {schema} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Table:</b> {table} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Host:</b> {host_info} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        story.append(Paragraph(sub_text, subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceAfter=15))

        total_printable_width = page_width - left_margin - right_margin

        # Helper: Table generator with light blue header & light grey grid
        def add_report_table(title: str, headers: List[str], rows: List[List[Any]], note: str = None):
            if title:
                story.append(Paragraph(title, section_heading_style))
            if note:
                story.append(Paragraph(note, note_style))
            
            if not rows:
                return

            header_row = [Paragraph(str(h), table_header_style) for h in headers]
            data_matrix = [header_row]

            for row in rows:
                formatted_row = []
                for i in range(len(headers)):
                    val_str = str(row[i]) if (i < len(row) and row[i] is not None) else "-"
                    if len(val_str) > 300:
                        val_str = val_str[:297] + "..."
                    formatted_row.append(Paragraph(val_str, table_cell_style))
                data_matrix.append(formatted_row)

            num_cols = len(headers)
            CAP_CHARS = 60
            CHAR_WIDTH_PT = 7.0
            MAX_COL_FRACTION = 0.45

            col_scores = []
            col_min_widths = []
            for i in range(num_cols):
                h_len = len(str(headers[i]))
                d_len = max((len(str(row[i])) for row in rows if i < len(row)), default=0)
                effective_len = min(max(h_len, d_len, 4), CAP_CHARS)
                col_scores.append(effective_len)
                col_min_widths.append(max(h_len * CHAR_WIDTH_PT + 8, 60.0))

            max_single = MAX_COL_FRACTION * total_printable_width
            sum_scores = sum(col_scores)
            if sum_scores > 0:
                raw_widths = [(s / sum_scores) * total_printable_width for s in col_scores]
                raw_widths = [max(col_min_widths[i], min(raw_widths[i], max_single)) for i in range(num_cols)]
                tot_w = sum(raw_widths)
                col_widths = [(w / tot_w) * total_printable_width for w in raw_widths]
            else:
                col_widths = [total_printable_width / num_cols] * num_cols

            t = Table(data_matrix, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NORMAL),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -1), 9.5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))

        # Helper: Key-Value Summary Table generator with Dark Blue (#1E3A8A) header bar
        def add_key_value_table(title: str, pairs: List[List[str]], headers: List[str] = None):
            if title:
                story.append(Paragraph(title, section_heading_style))
            
            if not pairs:
                return

            if not headers:
                num_cols = len(pairs[0]) if pairs else 2
                headers = ["Metric", "Value"] if num_cols == 2 else ["Metric", "Value", "Metric", "Value"]
            
            header_row = [Paragraph(str(h), table_header_style) for h in headers]
            data_matrix = [header_row]

            for row in pairs:
                formatted_row = []
                for idx, cell in enumerate(row):
                    style = table_cell_bold if idx % 2 == 0 else table_cell_style
                    val_str = str(cell) if cell is not None else "-"
                    if len(val_str) > 300:
                        val_str = val_str[:297] + "..."
                    formatted_row.append(Paragraph(val_str, style))
                data_matrix.append(formatted_row)

            num_cols = len(headers)
            if num_cols == 2:
                col_widths = [200.0, total_printable_width - 200.0]
            else:
                col_widths = [140.0, (total_printable_width / 2) - 140.0, 140.0, (total_printable_width / 2) - 140.0]

            t = Table(data_matrix, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NORMAL),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -1), 9.5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))

        # 1. Source Information
        summary = payload.get("summary", {})
        profiles = payload.get("column_profiles") or payload.get("profiles") or []
        row_cnt = summary.get("total_rows", 0)
        col_cnt = summary.get("total_columns", len(profiles))
        table_full_path = f"{db}.{schema}.{table}"

        source_pairs = [
            ["Source", f"{database_name}: {table_full_path}", "Rows", f"{row_cnt:,}"],
            ["Schema", str(schema), "Columns", str(col_cnt)]
        ]
        add_key_value_table("1. Source Information", source_pairs)

        # 2. Dataset Summary
        inconsistencies = payload.get("inconsistencies", [])
        potential_anomalies = payload.get("potential_anomalies", [])
        missing_cols_cnt = sum(1 for p in profiles if p.get("missing_count", 0) > 0)
        col_names_str = ", ".join(p.get("column", "") for p in profiles)
        inc_cols = list(set(inc.get("column") for inc in inconsistencies if inc.get("column")))
        anom_cols = list(set(a.get("column") for a in potential_anomalies if a.get("column")))

        ds_summary_rows = [
            ["Columns With Missing Values", str(missing_cols_cnt)],
            ["Total Missing Cells", f"{summary.get('missing_cells', 0):,}"],
            ["Columns", col_names_str],
            ["Columns Skipped During Profiling", "NONE"],
            ["Columns With Date/Serialization Warnings", "NONE"],
            ["Columns With Confirmed Inconsistencies", str(len(inconsistencies))],
            ["Confirmed Inconsistency Columns", ", ".join(inc_cols) if inc_cols else "NONE"],
            ["Columns With Potential Anomalies", str(len(potential_anomalies))],
            ["Potential Anomaly Columns", ", ".join(anom_cols) if anom_cols else "NONE"],
        ]
        add_key_value_table("2. Dataset Summary", ds_summary_rows)

        # 3. Pre-Profiling Data Inconsistency Analysis
        story.append(Paragraph("3. Pre-Profiling Data Inconsistency Analysis", section_heading_style))
        if not inconsistencies:
            story.append(Paragraph("No confirmed inconsistencies were detected by the configured pre-profiling rules.", note_style))
            story.append(Spacer(1, 6))
        else:
            inc_headers = ["Type", "Column", "Severity", "Description"]
            inc_rows = [[i.get("issue_type", "Issue"), i.get("column", "N/A"), i.get("severity", "High"), i.get("message") or i.get("description", "")] for i in inconsistencies]
            add_report_table(None, inc_headers, inc_rows)

        # 4. Potential Anomalies - Reference / Business Validation Required
        story.append(Paragraph("4. Potential Anomalies - Reference / Business Validation Required", section_heading_style))
        if not potential_anomalies:
            story.append(Paragraph("No potential anomalies were detected by the configured reference heuristics.", note_style))
            story.append(Spacer(1, 6))
        else:
            anom_headers = ["Type", "Column", "Description"]
            anom_rows = [[a.get("issue_type") or a.get("type", "Anomaly"), a.get("column", "N/A"), a.get("message") or a.get("description", "")] for a in potential_anomalies]
            add_report_table(None, anom_headers, anom_rows)

        # 5. Duplicate Record Summary
        dup_info = payload.get("duplicate_info", {})
        dup_excluded = ", ".join(dup_info.get("excluded_columns", [])) if dup_info.get("excluded_columns") else "created_at"
        dup_logic = dup_info.get("logic", "Exact grouping across all non-audit business columns. SHA-256 is used only as a compact fingerprint for duplicate-group reporting.")

        dup_rows = [
            ["Duplicate Groups", str(summary.get("duplicate_groups", 0))],
            ["Extra Duplicate Rows", str(summary.get("duplicate_extra_records", 0))],
            ["Audit / Technical Columns Excluded", dup_excluded],
            ["Duplicate Check Logic", dup_logic]
        ]
        add_key_value_table("5. Duplicate Record Summary", dup_rows)

        # 6. Imputation Recommendation Summary
        imp_headers = ["Column", "Semantic Category", "Missing", "Missing %", "Recommended Method", "Imputation Value", "Reason"]
        imp_rows = []
        imputations = payload.get("imputation_recommendations", [])
        imp_dict_by_col = {imp.get("column"): imp for imp in imputations}
        for p in profiles:
            col = p.get("column", "")
            cat = p.get("category", "")
            m_cnt = p.get("missing_count", 0)
            m_pct = p.get("missing_percentage", 0.0)
            rec = imp_dict_by_col.get(col, {})
            rec_method = rec.get("recommended_method") or p.get("recommended_method", "NONE")
            imp_val = rec.get("imputation_value", "N/A")
            reason = rec.get("reason") or ("No missing values." if m_cnt == 0 else "Impute with metric.")
            imp_rows.append([col, cat, str(m_cnt), f"{m_pct:.2f}%", rec_method, imp_val, reason])

        add_report_table("6. Imputation Recommendation Summary", imp_headers, imp_rows)

        # 7. Data Distribution (Categorical / Nominal / Ordinal / Boolean columns)
        dist_headers = ["Column", "Category", "Value / Distribution Point", "Count", "Percentage / Value"]
        dist_rows = []
        for p in profiles:
            col = p.get("column", "")
            cat = p.get("category", "")
            if cat in {"CATEGORICAL_NOMINAL", "CATEGORICAL_ORDINAL", "BOOLEAN"}:
                stats = p.get("statistics", {})
                dist_list = stats.get("distribution", [])
                if isinstance(dist_list, list):
                    for d in dist_list:
                        if isinstance(d, dict):
                            val_pt = str(d.get("value", ""))
                            cnt = d.get("count", 0)
                            pct = d.get("percentage", 0.0)
                            dist_rows.append([col, cat, val_pt, f"{cnt:,}", f"{pct:.2f}%"])
        if dist_rows:
            add_report_table("7. Data Distribution", dist_headers, dist_rows)

        # 8. Column Profiling Details
        prof_headers = ["Column", "Physical Type", "Semantic Category", "Null Count", "Missing %", "Distinct Count", "Central / Mode / Range"]
        prof_rows = []
        for p in profiles:
            col = p.get("column", "")
            p_type = p.get("physical_datatype", "")
            cat = p.get("category", "")
            null_cnt = f"{p.get('missing_count', 0):,}"
            missing_pct = f"{p.get('missing_percentage', 0):.2f}%"
            dist_cnt = f"{p.get('unique_count', 0):,}"

            stats = p.get("statistics", {})
            stat_str = "-"
            if cat in {"NUMERICAL_DISCRETE", "NUMERICAL_CONTINUOUS"} or stats.get("mean") is not None:
                mn = stats.get("mean")
                md = stats.get("median")
                stat_str = f"Mean: {mn:.2f}, Med: {md:.2f}" if mn is not None and md is not None else "Numerical"
            elif stats.get("mode") is not None:
                stat_str = f"Mode: {stats.get('mode')}"
            prof_rows.append([col, p_type, cat, null_cnt, missing_pct, dist_cnt, stat_str])

        add_report_table("8. Column Profiling Details Overview", prof_headers, prof_rows)

        story.append(Paragraph("9. Individual Column Profiles", section_heading_style))
        for p in profiles:
            col_name = p.get("column", "")
            cat = p.get("category", "OTHER")
            p_type = p.get("physical_datatype", "StringType()")
            stats = p.get("statistics", {})
            tot = p.get("total_rows", row_cnt)
            m_cnt = p.get("missing_count", 0)
            non_null = max(0, tot - m_cnt)
            m_pct = p.get("missing_percentage", 0.0)
            u_cnt = p.get("unique_count", 0)

            rec = imp_dict_by_col.get(col_name, {})
            rec_method = rec.get("recommended_method") or p.get("recommended_method", "NONE")
            imp_val = rec.get("imputation_value", "N/A")
            rec_reason = rec.get("reason") or ("No missing values." if m_cnt == 0 else "Impute with metric.")

            sem_reason = p.get("semantic_reason", "")
            if not sem_reason:
                if cat == "IDENTIFIER":
                    sem_reason = "Selected as the dataset primary identifier because its populated values are unique and it is the strongest primary-key candidate."
                elif cat == "HIGH_CARDINALITY_TEXT":
                    sem_reason = "Text domain is highly unique and has no detected ordering."
                elif cat == "CATEGORICAL_NOMINAL":
                    sem_reason = "Categorical values have no reliably inferred order."
                elif cat == "NUMERICAL_CONTINUOUS":
                    sem_reason = "Column name indicates a measured/amount/rate quantity that is semantically continuous."
                elif cat == "DATETIME":
                    sem_reason = "Source supplied native date/timestamp values."
                else:
                    sem_reason = "Standard domain column."

            col_detail_pairs = [
                ["Physical Type", str(p_type)],
                ["Semantic Category", str(cat)],
                ["Semantic Reason", str(sem_reason)],
                ["Non-Null", f"{non_null:,}"],
                ["Missing", f"{m_cnt:,}"],
                ["Missing %", f"{m_pct:.2f}%"],
                ["Unique", f"{u_cnt:,}"],
                ["Recommended Imputation", str(rec_method)],
                ["Imputation Value", str(imp_val)],
                ["Recommendation Reason", str(rec_reason)],
            ]

            if cat in {"NUMERICAL_CONTINUOUS", "NUMERICAL_DISCRETE"} or stats.get("mean") is not None:
                mn = stats.get("mean", 0.0)
                md = stats.get("median", 0.0)
                var = stats.get("variance", 0.0)
                sd = stats.get("stddev", 0.0)
                mn_v = stats.get("min", 0.0)
                mx_v = stats.get("max", 0.0)
                skew = stats.get("skewness", 0.0)

                col_detail_pairs.extend([
                    ["Mean", f"{mn:.4f}" if mn is not None else "N/A"],
                    ["Median", f"{md:.4f}" if md is not None else "N/A"],
                    ["Variance", f"{var:.4f}" if var is not None else "N/A"],
                    ["Std Dev", f"{sd:.4f}" if sd is not None else "N/A"],
                    ["Min", f"{mn_v:.4f}" if mn_v is not None else "N/A"],
                    ["Max", f"{mx_v:.4f}" if mx_v is not None else "N/A"],
                    ["Distribution Shape", str(stats.get("shape", "N/A"))],
                    ["Skewness", f"{skew:.4f}" if skew is not None else "0.0000"],
                    ["Skew Direction", str(stats.get("skew_direction", "N/A"))],
                    ["Skew Severity", str(stats.get("skew_severity", "N/A"))],
                    ["Outlier Count", str(stats.get("outliers_count", 0))],
                    ["Outlier Values", str(stats.get("outliers_sample", []))],
                    ["Distribution Note", str(stats.get("note", "N/A"))]
                ])
            elif cat in {"HIGH_CARDINALITY_TEXT", "TEXT", "IDENTIFIER"}:
                mode_v = stats.get("mode", f"{col_name} 1")
                dist_note = stats.get("distribution_note", "Skipped - high-cardinality text contains mostly unique values")
                col_detail_pairs.extend([
                    ["Mode", str(mode_v)],
                    ["Distribution", str(dist_note)]
                ])
            elif cat in {"CATEGORICAL_NOMINAL", "CATEGORICAL_ORDINAL", "BOOLEAN"}:
                mode_v = stats.get("mode", "N/A")
                dist_list = stats.get("distribution", [])
                dist_str = ", ".join(f"{d.get('value')}={d.get('count')} ({d.get('percentage', 0):.2f}%)" for d in dist_list[:5]) if dist_list else "N/A"
                col_detail_pairs.extend([
                    ["Mode", str(mode_v)],
                    ["Distribution", dist_str]
                ])
            elif cat == "DATETIME":
                col_detail_pairs.extend([
                    ["Date Validation", str(stats.get("date_validation", "NATIVE_DATE_TYPE"))],
                    ["Date Format", str(stats.get("date_format", "TimestampType()"))]
                ])

            add_key_value_table(f"Column: {col_name}", col_detail_pairs)

        canvas_factory = lambda *args, **kwargs: NumberedCanvas(*args, report_title=f"PySpark EDA Statistics Report — {db}.{schema}.{table}", **kwargs)
        doc.build(story, canvasmaker=canvas_factory)
        return filepath

