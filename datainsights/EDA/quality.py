from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np


class DataInconsistencyAnalyzer:

    @classmethod
    def _is_identifier_name(cls, column: str) -> bool:
        c = column.lower()
        if c in {"id", "guid", "uuid", "pk", "fk", "key"}:
            return True
        return bool(re.search(r"(_id|_pk|_fk|_guid|_uuid|_key|id_|key_)$", c))

    @classmethod
    def _issue(
        cls,
        column: str,
        issue_type: str,
        severity: str,
        affected_count: int,
        total_rows: int,
        message: str,
        examples: List[Any],
        recommendation: str
    ) -> Dict[str, Any]:
        pct = round((affected_count / max(1, total_rows)) * 100, 2)
        return {
            "column": column,
            "issue_type": issue_type,
            "severity": severity,
            "affected_count": affected_count,
            "affected_percentage": pct,
            "message": message,
            "examples": [str(e) for e in examples[:5]],
            "recommendation": recommendation
        }

    @classmethod
    def analyze(cls, df: pd.DataFrame) -> Dict[str, Any]:
        total_rows = len(df)
        issues: List[Dict[str, Any]] = []
        potential_anomalies: List[Dict[str, Any]] = []

        if total_rows == 0:
            return {
                "issues": [],
                "potential_anomalies": [],
                "inconsistent_columns": [],
                "potential_anomaly_columns": []
            }

        for column in df.columns:
            series = df[column]
            is_id = cls._is_identifier_name(column)

            # 1. Identifier NULL / blank check
            if is_id:
                null_mask = series.isna()
                if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
                    null_mask |= series.astype(str).str.strip().eq("")

                count = int(null_mask.sum())
                if count > 0:
                    ex = series[null_mask].dropna().head(5).tolist()
                    issues.append(cls._issue(
                        column=column,
                        issue_type="IDENTIFIER_NULL",
                        severity="ERROR",
                        affected_count=count,
                        total_rows=total_rows,
                        message="Identifier-like column contains NULL or blank values.",
                        examples=ex if ex else ["NULL"],
                        recommendation="Identifiers/keys should be fully populated. Reject or repair missing keys."
                    ))

            # 2. Leading / Trailing Spaces
            if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
                str_s = series.dropna().astype(str)
                space_mask = str_s.ne(str_s.str.strip())
                space_count = int(space_mask.sum())
                if space_count > 0:
                    issues.append(cls._issue(
                        column=column,
                        issue_type="LEADING_TRAILING_SPACES",
                        severity="WARNING",
                        affected_count=space_count,
                        total_rows=total_rows,
                        message="String values contain leading or trailing whitespace.",
                        examples=str_s[space_mask].head(5).tolist(),
                        recommendation="Trim leading and trailing whitespace from string column values."
                    ))

            # 3. Numeric string check for mixed types
            if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
                clean_s = series.dropna().astype(str).str.strip()
                if len(clean_s) > 0:
                    sample = clean_s.sample(min(1000, len(clean_s)), random_state=42)
                    sample_num = pd.to_numeric(sample, errors="coerce")
                    sample_valid = int(sample_num.notna().sum())
                    if 0 < sample_valid < len(sample):
                        num_converted = pd.to_numeric(clean_s, errors="coerce")
                        valid_num_count = int(num_converted.notna().sum())
                        if 0 < valid_num_count < len(clean_s):
                            potential_anomalies.append(cls._issue(
                                column=column,
                                issue_type="MIXED_NUMERIC_TEXT",
                                severity="INFO",
                                affected_count=valid_num_count,
                                total_rows=total_rows,
                                message="Column contains a mixture of numeric values and text strings.",
                                examples=clean_s[num_converted.notna()].head(5).tolist(),
                                recommendation="Standardize data format or separate mixed text and numeric entries."
                            ))


        inconsistent_cols = list({i["column"] for i in issues})
        potential_anomaly_cols = list({a["column"] for a in potential_anomalies})

        return {
            "issues": issues,
            "potential_anomalies": potential_anomalies,
            "inconsistent_columns": inconsistent_cols,
            "potential_anomaly_columns": potential_anomaly_cols
        }


class DuplicateRecordAnalyzer:

    AUDIT_COLUMN_NAMES = {
        "id", "created_at", "updated_at", "modified_at", "created_by",
        "updated_by", "row_id", "etl_timestamp", "insert_date"
    }

    @classmethod
    def analyze(cls, df: pd.DataFrame) -> Dict[str, Any]:
        total_rows = len(df)
        if total_rows == 0:
            return {
                "duplicate_group_count": 0,
                "duplicate_extra_record_count": 0,
                "audit_columns": []
            }

        # Identify audit columns to exclude when finding duplicates
        audit_cols = [c for c in df.columns if c.lower() in cls.AUDIT_COLUMN_NAMES]
        subset = [c for c in df.columns if c not in audit_cols] if len(audit_cols) < len(df.columns) else list(df.columns)

        duplicated_mask = df.duplicated(subset=subset, keep=False)
        duplicated_rows = df[duplicated_mask]

        if len(duplicated_rows) == 0:
            return {
                "duplicate_group_count": 0,
                "duplicate_extra_record_count": 0,
                "audit_columns": audit_cols
            }

        # Vectorized drop_duplicates is 100x faster than groupby.ngroups
        group_count = len(duplicated_rows.drop_duplicates(subset=subset))
        extra_count = len(duplicated_rows) - group_count

        return {
            "duplicate_group_count": group_count,
            "duplicate_extra_record_count": max(0, extra_count),
            "audit_columns": audit_cols
        }
