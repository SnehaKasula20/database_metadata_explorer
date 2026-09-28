from __future__ import annotations

import json
import math
import os
import sys
import re
import statistics
from html import escape
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, ByteType, DateType, DecimalType, DoubleType, FloatType,
    IntegerType, LongType, ShortType, StringType, StructField, StructType,
    TimestampType,
)
from pyspark.sql.window import Window

@dataclass
class EDAReportEntry:
    source: str
    database: Optional[str]
    schema: Optional[str]
    table: str
    row_count: int
    column_count: int
    profiles: list[dict]
    duplicate_group_count: int = 0
    duplicate_extra_record_count: int = 0
    duplicate_audit_columns: Optional[list[str]] = None
    inconsistencies: Optional[list[dict]] = None
    potential_anomalies: Optional[list[dict]] = None
    inconsistent_columns: Optional[list[str]] = None
    potential_anomaly_columns: Optional[list[str]] = None
    error: Optional[str] = None

class PDFStatisticsReportWriter:
    """
    Create one combined PDF containing EDA statistics for every table
    profiled during the current application session.
    """

    @staticmethod
    def _safe(value: Any) -> str:
        if value is None:
            return "N/A"
        if isinstance(value, float):
            return f"{value:.4f}"
        return str(value)

    @classmethod
    def save(
        cls,
        entries: list[EDAReportEntry],
        output_path: Optional[str] = None,
    ) -> str:
        if not entries:
            raise ValueError(
                "No EDA statistics are available for PDF reporting."
            )

        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import (
            getSampleStyleSheet,
            ParagraphStyle,
        )
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            PageBreak,
            KeepTogether,
        )

        if output_path:
            output = Path(output_path)
            if output.suffix.lower() != ".pdf":
                output = output.with_suffix(".pdf")
        else:
            report_dir = (
                Path(__file__).resolve().parent
                / "EDA_REPORTS"
            )
            report_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            db_name = (
                entries[0].database
                or "local_file"
            )

            safe_db = re.sub(
                r"[^A-Za-z0-9_-]+",
                "_",
                db_name,
            )

            timestamp = (
                datetime.now()
                .strftime(
                    "%Y%m%d_%H%M%S"
                )
            )

            output = (
                report_dir
                / f"EDA_Statistics_{safe_db}_{timestamp}.pdf"
            )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "EDAReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=18,
            leading=22,
            spaceAfter=12,
        )

        h1 = ParagraphStyle(
            "EDAH1",
            parent=styles["Heading1"],
            fontSize=14,
            leading=17,
            spaceBefore=6,
            spaceAfter=8,
        )

        dataset_name_style = ParagraphStyle(
            "EDADatasetName",
            parent=h1,
            backColor=colors.HexColor(
                "#D9EAF7"
            ),
            borderPadding=4,
        )

        h2 = ParagraphStyle(
            "EDAH2",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            spaceBefore=6,
            spaceAfter=6,
        )

        h3 = ParagraphStyle(
            "EDAH3",
            parent=styles["Heading3"],
            fontSize=9.5,
            leading=12,
            spaceBefore=4,
            spaceAfter=4,
        )

        body = ParagraphStyle(
            "EDABody",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11,
            wordWrap="CJK",
        )

        small = ParagraphStyle(
            "EDASmall",
            parent=styles["BodyText"],
            fontSize=7.2,
            leading=9,
            wordWrap="CJK",
        )

        table_label = ParagraphStyle(
            "EDATableLabel",
            parent=small,
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )

        table_value = ParagraphStyle(
            "EDATableValue",
            parent=small,
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )

        tiny = ParagraphStyle(
            "EDATiny",
            parent=styles["BodyText"],
            fontSize=6.4,
            leading=8,
            wordWrap="CJK",
        )

        doc = SimpleDocTemplate(
            str(output),
            pagesize=landscape(A4),
            rightMargin=12 * mm,
            leftMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )

        usable_width = (
            landscape(A4)[0]
            - doc.leftMargin
            - doc.rightMargin
        )

        def p(value: Any, style=table_value):
            if value is None or value == "":
                value = "N/A"

            safe_text = escape(
                str(value)
            ).replace(
                "\n",
                "<br/>",
            )

            return Paragraph(
                safe_text,
                style,
            )

        def label(value: Any):
            return p(
                value,
                table_label,
            )

        def section_table(
            rows,
            col_widths,
            header=False,
            repeat_rows=0,
            font_style=table_value,
        ):
            converted = []

            for row_index, row in enumerate(rows):
                converted_row = []

                for cell in row:
                    if isinstance(
                        cell,
                        Paragraph,
                    ):
                        converted_row.append(cell)
                    else:
                        style = (
                            table_label
                            if header and row_index == 0
                            else font_style
                        )

                        converted_row.append(
                            p(cell, style)
                        )

                converted.append(
                    converted_row
                )

            tbl = Table(
                converted,
                colWidths=col_widths,
                repeatRows=repeat_rows,
                splitByRow=1,
                splitInRow=1,
                hAlign="LEFT",
            )

            commands = [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor(
                        "#B7B7B7"
                    ),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
            ]

            if header:
                commands.extend(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor(
                                "#D9EAF7"
                            ),
                        ),
                        (
                            "FONTNAME",
                            (0, 0),
                            (-1, 0),
                            "Helvetica-Bold",
                        ),
                    ]
                )

            tbl.setStyle(
                TableStyle(
                    commands
                )
            )

            return tbl

        story = [
            Paragraph(
                "PySpark EDA Statistics Report",
                title_style,
            ),
            Paragraph(
                f"Generated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                body,
            ),
            Paragraph(
                f"Tables / datasets profiled: "
                f"{sum(1 for e in entries if not e.error)} "
                f"| Entries with errors: "
                f"{sum(1 for e in entries if e.error)}",
                body,
            ),
            Spacer(
                1,
                8,
            ),
        ]

        for entry_index, entry in enumerate(entries):
            object_name = ".".join(
                part
                for part in [
                    entry.database,
                    entry.schema,
                    entry.table,
                ]
                if part
            )

            if not object_name:
                object_name = (
                    entry.table
                    or entry.source
                    or "Dataset"
                )

            story.append(
                Paragraph(
                    escape(
                        str(object_name)
                    ),
                    dataset_name_style,
                )
            )

            # ----------------------------------------------------
            # SOURCE INFORMATION
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Source Information",
                    h2,
                )
            )

            source_rows = [
                [
                    label("Source"),
                    p(entry.source),
                    label("Rows"),
                    p(entry.row_count),
                ],
                [
                    label("Schema"),
                    p(entry.schema or "N/A"),
                    label("Columns"),
                    p(entry.column_count),
                ],
            ]

            # Balanced 4-column layout that consumes the full landscape width.
            # Every cell is a Paragraph, therefore long headings/values wrap.
            source_table = Table(
                source_rows,
                colWidths=[
                    32 * mm,
                    91 * mm,
                    32 * mm,
                    usable_width
                    - (
                        32 * mm
                        + 91 * mm
                        + 32 * mm
                    ),
                ],
                splitByRow=1,
                splitInRow=1,
                hAlign="LEFT",
            )

            source_table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (0, -1),
                            colors.HexColor(
                                "#E8E8E8"
                            ),
                        ),
                        (
                            "BACKGROUND",
                            (2, 0),
                            (2, -1),
                            colors.HexColor(
                                "#E8E8E8"
                            ),
                        ),
                        (
                            "GRID",
                            (0, 0),
                            (-1, -1),
                            0.3,
                            colors.grey,
                        ),
                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "TOP",
                        ),
                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            4,
                        ),
                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            4,
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            4,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            4,
                        ),
                    ]
                )
            )

            story.append(
                source_table
            )
            story.append(
                Spacer(
                    1,
                    8,
                )
            )

            # If the entire entry failed, show the source information plus
            # the error and continue to the next dataset.
            if entry.error:
                story.append(
                    Paragraph(
                        "<b>Profiling error:</b> "
                        + escape(
                            str(entry.error)
                        ),
                        body,
                    )
                )

                if entry_index < len(entries) - 1:
                    story.append(
                        PageBreak()
                    )

                continue

            # ----------------------------------------------------
            # DATASET SUMMARY
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Dataset Summary",
                    h2,
                )
            )

            total_missing = sum(
                int(
                    profile.get(
                        "missing_count",
                        0,
                    )
                    or 0
                )
                for profile in entry.profiles
            )

            columns_with_missing = sum(
                1
                for profile in entry.profiles
                if (
                    profile.get(
                        "missing_count",
                        0,
                    )
                    or 0
                ) > 0
            )

            skipped_columns = [
                profile["column"]
                for profile in entry.profiles
                if (
                    profile.get(
                        "profiling_skipped",
                        False,
                    )
                    or profile.get(
                        "category"
                    )
                    == "SKIPPED_UNSUPPORTED_DATETIME"
                )
            ]

            warning_columns = [
                profile["column"]
                for profile in entry.profiles
                if profile.get(
                    "source_warning"
                )
            ]

            dataset_rows = [
                [
                    "Metric",
                    "Value",
                ],
                # [
                #     "Total Rows",
                #     entry.row_count,
                # ],
                # [
                #     "Total Columns",
                #     entry.column_count,
                # ],
                [
                    "Columns With Missing Values",
                    columns_with_missing,
                ],
                [
                    "Total Missing Cells",
                    total_missing,
                ],
                [
                    "Columns",
                    ", ".join(
                        profile["column"]
                        for profile
                        in entry.profiles
                    )
                    or "N/A",
                ],
                [
                    "Columns Skipped During Profiling",
                    ", ".join(
                        skipped_columns
                    )
                    or "NONE",
                ],
                [
                    "Columns With Date/Serialization Warnings",
                    ", ".join(
                        warning_columns
                    )
                    or "NONE",
                ],
                [
                    "Columns With Confirmed Inconsistencies",
                    len(
                        entry.inconsistent_columns
                        or []
                    ),
                ],
                [
                    "Confirmed Inconsistency Columns",
                    ", ".join(
                        entry.inconsistent_columns
                        or []
                    )
                    or "NONE",
                ],
                [
                    "Columns With Potential Anomalies",
                    len(
                        entry.potential_anomaly_columns
                        or []
                    ),
                ],
                [
                    "Potential Anomaly Columns",
                    ", ".join(
                        entry.potential_anomaly_columns
                        or []
                    )
                    or "NONE",
                ],
            ]

            story.append(
                section_table(
                    dataset_rows,
                    [
                        62 * mm,
                        usable_width
                        - 62 * mm,
                    ],
                    header=True,
                    repeat_rows=1,
                )
            )

            story.append(
                Spacer(
                    1,
                    8,
                )
            )

            # ----------------------------------------------------
            # PRE-PROFILING DATA INCONSISTENCY ANALYSIS
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Pre-Profiling Data Inconsistency Analysis",
                    h2,
                )
            )

            inconsistencies = (
                entry.inconsistencies
                or []
            )

            inconsistent_columns = (
                entry.inconsistent_columns
                or []
            )

            if inconsistent_columns:
                story.append(
                    Paragraph(
                        "<b>Columns with confirmed inconsistencies:</b> "
                        + escape(
                            ", ".join(
                                inconsistent_columns
                            )
                        ),
                        body,
                    )
                )
                story.append(
                    Spacer(
                        1,
                        4,
                    )
                )

                inconsistency_rows = [
                    [
                        "Column",
                        "Issue Type",
                        "Severity",
                        "Affected",
                        "Affected %",
                        "Examples",
                        "Analysis / Recommendation",
                    ]
                ]

                for issue in inconsistencies:
                    analysis_text = (
                        str(
                            issue.get(
                                "message",
                                "",
                            )
                        )
                        + " "
                        + str(
                            issue.get(
                                "recommendation",
                                "",
                            )
                        )
                    ).strip()

                    inconsistency_rows.append(
                        [
                            issue.get(
                                "column",
                                "",
                            ),
                            issue.get(
                                "issue_type",
                                "",
                            ),
                            issue.get(
                                "severity",
                                "",
                            ),
                            issue.get(
                                "affected_count",
                                0,
                            ),
                            f"{issue.get('affected_percentage', 0):.2f}%",
                            "; ".join(
                                issue.get(
                                    "examples",
                                    [],
                                )
                            )
                            or "N/A",
                            analysis_text
                            or "N/A",
                        ]
                    )

                story.append(
                    section_table(
                        inconsistency_rows,
                        [
                            34 * mm,
                            43 * mm,
                            21 * mm,
                            19 * mm,
                            21 * mm,
                            47 * mm,
                            usable_width
                            - (
                                34 * mm
                                + 43 * mm
                                + 21 * mm
                                + 19 * mm
                                + 21 * mm
                                + 47 * mm
                            ),
                        ],
                        header=True,
                        repeat_rows=1,
                        font_style=tiny,
                    )
                )

            else:
                story.append(
                    Paragraph(
                        "No confirmed inconsistencies were detected by the "
                        "configured pre-profiling rules.",
                        body,
                    )
                )

            story.append(
                Spacer(
                    1,
                    8,
                )
            )

            # ----------------------------------------------------
            # POTENTIAL ANOMALIES - REFERENCE ONLY
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Potential Anomalies - Reference / Business Validation Required",
                    h2,
                )
            )

            potential_anomalies = (
                entry.potential_anomalies
                or []
            )

            potential_columns = (
                entry.potential_anomaly_columns
                or []
            )

            if potential_columns:
                story.append(
                    Paragraph(
                        "<b>Columns with potential anomalies:</b> "
                        + escape(
                            ", ".join(
                                potential_columns
                            )
                        ),
                        body,
                    )
                )
                story.append(
                    Spacer(
                        1,
                        4,
                    )
                )

                anomaly_rows = [
                    [
                        "Column",
                        "Potential Anomaly",
                        "Affected",
                        "Affected %",
                        "Examples",
                        "Reference / Why Review Is Needed",
                    ]
                ]

                for issue in potential_anomalies:
                    reference_text = (
                        str(
                            issue.get(
                                "message",
                                "",
                            )
                        )
                        + " "
                        + str(
                            issue.get(
                                "recommendation",
                                "",
                            )
                        )
                    ).strip()

                    anomaly_rows.append(
                        [
                            issue.get(
                                "column",
                                "",
                            ),
                            issue.get(
                                "issue_type",
                                "",
                            ),
                            issue.get(
                                "affected_count",
                                0,
                            ),
                            f"{issue.get('affected_percentage', 0):.2f}%",
                            "; ".join(
                                issue.get(
                                    "examples",
                                    [],
                                )
                            )
                            or "N/A",
                            reference_text
                            or "N/A",
                        ]
                    )

                story.append(
                    section_table(
                        anomaly_rows,
                        [
                            37 * mm,
                            48 * mm,
                            20 * mm,
                            21 * mm,
                            48 * mm,
                            usable_width
                            - (
                                37 * mm
                                + 48 * mm
                                + 20 * mm
                                + 21 * mm
                                + 48 * mm
                            ),
                        ],
                        header=True,
                        repeat_rows=1,
                        font_style=tiny,
                    )
                )

            else:
                story.append(
                    Paragraph(
                        "No potential anomalies were detected by the configured "
                        "reference heuristics.",
                        body,
                    )
                )

            story.append(
                Spacer(
                    1,
                    8,
                )
            )

            # ----------------------------------------------------
            # DUPLICATE RECORD SUMMARY
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Duplicate Record Summary",
                    h2,
                )
            )

            duplicate_rows = [
                [
                    "Metric",
                    "Value",
                ],
                [
                    "Duplicate Groups",
                    entry.duplicate_group_count,
                ],
                [
                    "Extra Duplicate Rows",
                    entry.duplicate_extra_record_count,
                ],
                [
                    "Audit / Technical Columns Excluded",
                    ", ".join(
                        entry.duplicate_audit_columns
                        or []
                    )
                    or "NONE",
                ],
                [
                    "Duplicate Check Logic",
                    (
                        "Exact grouping across all non-audit business columns. "
                        "SHA-256 is used only as a compact fingerprint for "
                        "duplicate-group reporting."
                    ),
                ],
            ]

            story.append(
                section_table(
                    duplicate_rows,
                    [
                        62 * mm,
                        usable_width
                        - 62 * mm,
                    ],
                    header=True,
                    repeat_rows=1,
                )
            )

            story.append(
                Spacer(
                    1,
                    8,
                )
            )

            # ----------------------------------------------------
            # IMPUTATION RECOMMENDATION SUMMARY
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Imputation Recommendation Summary",
                    h2,
                )
            )

            imputation_rows = [
                [
                    "Column",
                    "Semantic Category",
                    "Missing",
                    "Missing %",
                    "Recommended Method",
                    "Imputation Value",
                    "Reason",
                ]
            ]

            for profile in entry.profiles:
                imputation_rows.append(
                    [
                        profile.get(
                            "column",
                            "",
                        ),
                        profile.get(
                            "category",
                            "",
                        ),
                        profile.get(
                            "missing_count",
                            0,
                        ),
                        f"{profile.get('missing_percentage', 0):.2f}%",
                        profile.get(
                            "recommended_method",
                            "N/A",
                        ),
                        cls._safe(
                            profile.get(
                                "imputation_value"
                            )
                        ),
                        profile.get(
                            "reason",
                            "N/A",
                        ),
                    ]
                )

            story.append(
                section_table(
                    imputation_rows,
                    [
                        35 * mm,
                        42 * mm,
                        18 * mm,
                        20 * mm,
                        38 * mm,
                        32 * mm,
                        usable_width
                        - (
                            35 * mm
                            + 42 * mm
                            + 18 * mm
                            + 20 * mm
                            + 38 * mm
                            + 32 * mm
                        ),
                    ],
                    header=True,
                    repeat_rows=1,
                    font_style=tiny,
                )
            )

            story.append(
                Spacer(
                    1,
                    8,
                )
            )

            # ----------------------------------------------------
            # DATA DISTRIBUTION
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Data Distribution",
                    h2,
                )
            )

            distribution_rows = [
                [
                    "Column",
                    "Category",
                    "Value / Distribution Point",
                    "Count",
                    "Percentage / Value",
                ]
            ]

            has_distribution = False

            for profile in entry.profiles:
                category = profile.get(
                    "category"
                )

                stats = (
                    profile.get(
                        "statistics"
                    )
                    or {}
                )

                if category == "CATEGORICAL_NOMINAL":
                    distribution = (
                        stats.get(
                            "distribution",
                            []
                        )
                        or []
                    )

                    for item in distribution:
                        has_distribution = True

                        distribution_rows.append(
                            [
                                profile[
                                    "column"
                                ],
                                category,
                                item.get(
                                    "value"
                                ),
                                item.get(
                                    "count",
                                    0,
                                ),
                                f"{item.get('percentage', 0):.2f}%",
                            ]
                        )

            if not has_distribution:
                distribution_rows.append(
                    [
                        "N/A",
                        "N/A",
                        "No applicable distribution statistics available.",
                        "",
                        "",
                    ]
                )

            story.append(
                section_table(
                    distribution_rows,
                    [
                        38 * mm,
                        45 * mm,
                        88 * mm,
                        25 * mm,
                        usable_width
                        - (
                            38 * mm
                            + 45 * mm
                            + 88 * mm
                            + 25 * mm
                        ),
                    ],
                    header=True,
                    repeat_rows=1,
                    font_style=tiny,
                )
            )

            story.append(
                Spacer(
                    1,
                    10,
                )
            )

            # ----------------------------------------------------
            # COLUMN PROFILING DETAILS
            # ----------------------------------------------------
            story.append(
                Paragraph(
                    "Column Profiling Details",
                    h2,
                )
            )

            for profile in entry.profiles:
                category = profile.get(
                    "category",
                    "N/A",
                )

                stats = (
                    profile.get(
                        "statistics"
                    )
                    or {}
                )

                details = [
                    # [
                    #     "Physical Type",
                    #     profile.get(
                    #         "physical_datatype",
                    #         "",
                    #     ),
                    # ],
                    # [
                    #     "Spark Type",
                    #     profile.get(
                    #         "spark_type",
                    #         "",
                    #     ),
                    # ],
                    [
                        "Physical Type",
                        profile.get(
                            "spark_type",
                            "",
                        ),
                    ],
                    [
                        "Semantic Category",
                        category,
                    ],
                    [
                        "Semantic Reason",
                        profile.get(
                            "semantic_reason"
                        )
                        or "N/A",
                    ],
                    [
                        "Non-Null",
                        profile.get(
                            "non_null_count",
                            0,
                        ),
                    ],
                    [
                        "Missing",
                        profile.get(
                            "missing_count",
                            0,
                        ),
                    ],
                    [
                        "Missing %",
                        f"{profile.get('missing_percentage', 0):.2f}%",
                    ],
                    [
                        "Unique",
                        profile.get(
                            "unique_count",
                            0,
                        ),
                    ],
                    [
                        "Recommended Imputation",
                        profile.get(
                            "recommended_method",
                            "N/A",
                        ),
                    ],
                    [
                        "Imputation Value",
                        cls._safe(
                            profile.get(
                                "imputation_value"
                            )
                        ),
                    ],
                    [
                        "Recommendation Reason",
                        profile.get(
                            "reason",
                            "N/A",
                        ),
                    ],
                ]

                if profile.get(
                    "source_warning"
                ):
                    details.append(
                        [
                            "Source / Date Conversion Warning",
                            profile[
                                "source_warning"
                            ],
                        ]
                    )

                if profile.get(
                    "mktime_avoided"
                ):
                    details.append(
                        [
                            "mktime Overflow Handling",
                            (
                                "Potential 'mktime argument out of range' "
                                "was detected and avoided by preserving "
                                "the source date/timestamp values as STRING."
                            ),
                        ]
                    )

                if profile.get(
                    "profiling_error"
                ):
                    details.append(
                        [
                            "Profiling Error",
                            profile[
                                "profiling_error"
                            ],
                        ]
                    )

                if profile.get(
                    "profiling_skipped"
                ):
                    details.append(
                        [
                            "Profiling Status",
                            "SKIPPED",
                        ]
                    )

                if profile.get(
                    "ordinal_order"
                ):
                    details.append(
                        [
                            "Ordinal Order",
                            " < ".join(
                                profile[
                                    "ordinal_order"
                                ]
                            ),
                        ]
                    )

                if category in {
                    "NUMERICAL_DISCRETE",
                    "NUMERICAL_CONTINUOUS",
                }:
                    details.extend(
                        [
                            [
                                "Mean",
                                cls._safe(
                                    stats.get(
                                        "mean"
                                    )
                                ),
                            ],
                            [
                                "Median",
                                cls._safe(
                                    stats.get(
                                        "median"
                                    )
                                ),
                            ],
                            [
                                "Variance",
                                cls._safe(
                                    stats.get(
                                        "variance"
                                    )
                                ),
                            ],
                            [
                                "Std Dev",
                                cls._safe(
                                    stats.get(
                                        "stddev"
                                    )
                                ),
                            ],
                            [
                                "Min",
                                cls._safe(
                                    stats.get(
                                        "min"
                                    )
                                ),
                            ],
                            [
                                "Max",
                                cls._safe(
                                    stats.get(
                                        "max"
                                    )
                                ),
                            ],
                            # [
                            #     "Q1",
                            #     cls._safe(
                            #         stats.get(
                            #             "q1"
                            #         )
                            #     ),
                            # ],
                            # [
                            #     "Q3",
                            #     cls._safe(
                            #         stats.get(
                            #             "q3"
                            #         )
                            #     ),
                            # ],
                            # [
                            #     "IQR",
                            #     cls._safe(
                            #         stats.get(
                            #             "iqr"
                            #         )
                            #     ),
                            # ],
                            [
                                "Distribution Shape",
                                stats.get(
                                    "distribution_shape",
                                    "N/A",
                                ),
                            ],
                            [
                                "Skewness",
                                cls._safe(
                                    stats.get(
                                        "skewness"
                                    )
                                ),
                            ],
                            [
                                "Skew Direction",
                                stats.get(
                                    "skew_direction",
                                    "N/A",
                                ),
                            ],
                            [
                                "Skew Severity",
                                stats.get(
                                    "skew_severity",
                                    "N/A",
                                ),
                            ],
                            [
                                "Outlier Count",
                                cls._safe(
                                    stats.get(
                                        "outlier_count"
                                    )
                                ),
                            ],
                            [
                                "Outlier Values",
                                cls._safe(
                                    stats.get(
                                        "outliers",
                                        [],
                                    )
                                ),
                            ],
                            [
                                "Distribution Note",
                                stats.get(
                                    "distribution_note",
                                    "N/A",
                                ),
                            ],
                        ]
                    )

                elif category in {
                    "CATEGORICAL_NOMINAL",
                    "CATEGORICAL_ORDINAL",
                    "BOOLEAN",
                }:
                    details.append(
                        [
                            "Mode",
                            cls._safe(
                                stats.get(
                                    "mode"
                                )
                            ),
                        ]
                    )

                    distribution = (
                        stats.get(
                            "distribution",
                            []
                        )
                        or []
                    )

                    if distribution:
                        dist_text = ", ".join(
                            f"{item['value']}={item['count']} "
                            f"({item['percentage']:.2f}%)"
                            for item
                            in distribution
                        )

                        details.append(
                            [
                                "Distribution",
                                dist_text,
                            ]
                        )

                elif category == "HIGH_CARDINALITY_TEXT":
                    details.extend(
                        [
                            [
                                "Mode",
                                cls._safe(
                                    stats.get(
                                        "mode"
                                    )
                                ),
                            ],
                            [
                                "Distribution",
                                (
                                    "Skipped - high-cardinality text "
                                    "contains mostly unique values"
                                ),
                            ],
                        ]
                    )

                elif category in {
                    "DATETIME",
                    "DATETIME_STRING",
                }:
                    date_info = (
                        profile.get(
                            "date_validation"
                        )
                        or {}
                    )

                    details.extend(
                        [
                            [
                                "Date Validation",
                                date_info.get(
                                    "status",
                                    "N/A",
                                ),
                            ],
                            [
                                "Date Format",
                                date_info.get(
                                    "format",
                                    "N/A",
                                ),
                            ],
                        ]
                    )

                elif (
                    category
                    == "SKIPPED_UNSUPPORTED_DATETIME"
                ):
                    details.extend(
                        [
                            [
                                "Profiling Status",
                                (
                                    "SKIPPED - unsupported/extreme "
                                    "date value"
                                ),
                            ],
                            [
                                "Profiling Error",
                                profile.get(
                                    "profiling_error",
                                    "mktime/date conversion error",
                                ),
                            ],
                        ]
                    )

                metric_rows = [
                    [
                        "Metric",
                        "Value",
                    ]
                ] + details

                detail_table = section_table(
                    metric_rows,
                    [
                        55 * mm,
                        usable_width
                        - 55 * mm,
                    ],
                    header=True,
                    repeat_rows=1,
                    font_style=small,
                )

                story.extend(
                    [
                        Paragraph(
                            "Column: "
                            + escape(
                                str(
                                    profile.get(
                                        "column",
                                        ""
                                    )
                                )
                            ),
                            h3,
                        ),
                        detail_table,
                        Spacer(
                            1,
                            7,
                        ),
                    ]
                )

            if entry_index < len(entries) - 1:
                story.append(
                    PageBreak()
                )

        doc.build(
            story
        )

        return str(
            output.resolve()
        )

