from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, List, Dict, Optional, Tuple

import numpy as np
import pandas as pd


class MissingValueNormalizer:
    MISSING_TOKENS = {"", "null", "NULL", "none", "NONE", "na", "NA", "n/a", "N/A", "nan", "NaN", "nil", "missing"}

    @classmethod
    def normalize(cls, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                mask = df[col].isin(cls.MISSING_TOKENS)
                if mask.any():
                    df.loc[mask, col] = None
        return df



class ColumnTypeDetector:
    DATE_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}/\d{2}/\d{2}$",
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{2}-\d{2}-\d{4}$",
    ]
    DATETIME_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",
        r"^\d{4}/\d{2}/\d{2}[ T]\d{2}:\d{2}:\d{2}",
    ]

    ORDINAL_VOCABULARIES = {
        "education": ["no schooling", "primary", "middle school", "secondary", "high school", "diploma", "associate", "bachelor", "undergraduate", "master", "postgraduate", "phd", "doctorate"],
        "membership_tier": ["basic", "bronze", "silver", "gold", "platinum", "diamond"],
        "agreement": ["strongly disagree", "disagree", "neutral", "agree", "strongly agree"],
        "quality": ["very poor", "poor", "fair", "average", "good", "very good", "excellent"],
        "priority": ["low", "medium", "high", "critical", "urgent"],
        "size": ["xs", "s", "m", "l", "xl", "xxl"],
    }

    @classmethod
    def is_identifier_name(cls, column: str) -> bool:
        c = column.lower()
        if c in {"id", "guid", "uuid", "pk", "fk", "key"}:
            return True
        return bool(re.search(r"(_id|_pk|_fk|_guid|_uuid|_key|id_|key_)$", c))

    @classmethod
    def detect_category(cls, series: pd.Series, column_name: str) -> Tuple[str, str]:
        """Returns (category, physical_type)"""
        non_null = series.dropna()
        total_non_null = len(non_null)

        # Infer physical type
        dtype = series.dtype
        if pd.api.types.is_bool_dtype(dtype):
            phys_type = "BOOLEAN"
        elif pd.api.types.is_integer_dtype(dtype):
            phys_type = "INTEGER"
        elif pd.api.types.is_float_dtype(dtype):
            # Check sample of float values
            test_sample = non_null.head(100)
            if len(test_sample) > 0 and (test_sample % 1 == 0).all():
                phys_type = "INTEGER"
            else:
                phys_type = "DECIMAL/CONTINUOUS_NUMERIC"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            phys_type = "TIMESTAMP"
        else:
            phys_type = "STRING"

        # Check Identifier
        if cls.is_identifier_name(column_name):
            return "IDENTIFIER", phys_type

        # Check Boolean
        if phys_type == "BOOLEAN":
            return "BOOLEAN", phys_type
        elif total_non_null > 0:
            sample_unique = set(non_null.head(100).unique())
            if sample_unique.issubset({0, 1, "0", "1", "true", "false", "True", "False", "Y", "N", "y", "n"}):
                return "BOOLEAN", phys_type

        # Check Datetime/Date
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return "TIMESTAMP", phys_type

        if phys_type == "STRING" and total_non_null > 0:
            test_sample = non_null.head(100).astype(str).str.strip()
            # Test Date/Datetime pattern on 100 sample rows for speed
            is_date = test_sample.apply(lambda v: any(re.match(p, v) for p in cls.DATE_PATTERNS)).all()
            if is_date:
                return "DATE", phys_type
            is_datetime = test_sample.apply(lambda v: any(re.match(p, v) for p in cls.DATETIME_PATTERNS)).all()
            if is_datetime:
                return "TIMESTAMP", phys_type

        # Check Numeric
        if pd.api.types.is_numeric_dtype(dtype) or phys_type in {"INTEGER", "DECIMAL/CONTINUOUS_NUMERIC"}:
            unique_cnt = non_null.head(1000).nunique()
            if unique_cnt <= 10 or phys_type == "INTEGER":
                return "NUMERICAL_DISCRETE", phys_type
            return "NUMERICAL_CONTINUOUS", phys_type

        # Text / String check for numeric strings
        if phys_type == "STRING" and total_non_null > 0:
            test_sample = non_null.head(100)
            num_test = pd.to_numeric(test_sample, errors="coerce")
            if num_test.notna().sum() == len(test_sample):
                num_converted = pd.to_numeric(non_null, errors="coerce")
                unique_cnt = num_converted.nunique()
                if (num_converted % 1 == 0).all():
                    if unique_cnt <= 10:
                        return "NUMERICAL_DISCRETE", "INTEGER"
                    return "NUMERICAL_CONTINUOUS", "INTEGER"
                return "NUMERICAL_CONTINUOUS", "DECIMAL/CONTINUOUS_NUMERIC"

        # Check Categorical Ordinal
        if phys_type == "STRING" and total_non_null > 0:
            lower_vals = set(non_null.head(500).astype(str).str.lower().unique())
            for vocab in cls.ORDINAL_VOCABULARIES.values():
                if lower_vals.issubset(set(vocab)):
                    return "CATEGORICAL_ORDINAL", phys_type

        return "CATEGORICAL_NOMINAL", phys_type


class SemanticSchemaRefiner:
    @classmethod
    def refine(cls, df: pd.DataFrame) -> pd.DataFrame:
        # Returns df as is (normalization already done)
        return df
