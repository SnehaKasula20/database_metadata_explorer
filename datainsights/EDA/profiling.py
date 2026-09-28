from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from .semantics import ColumnTypeDetector


class DatasetProfiler:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.total_rows = len(df)

    def profile(self) -> List[Dict[str, Any]]:
        profiles = []
        for column in self.df.columns:
            series = self.df[column]
            category, phys_type = ColumnTypeDetector.detect_category(series, column)

            non_null_s = series.dropna()
            missing_cnt = int(series.isna().sum())
            non_null_cnt = int(len(non_null_s))
            missing_pct = round((missing_cnt / max(1, self.total_rows)) * 100, 2)
            unique_cnt = int(non_null_s.nunique())

            # Infer spark_type string for UI / report compatibility
            if phys_type == "INTEGER":
                spark_type = "LongType"
            elif phys_type == "DECIMAL/CONTINUOUS_NUMERIC":
                spark_type = "DoubleType"
            elif phys_type == "BOOLEAN":
                spark_type = "BooleanType"
            elif phys_type == "DATE":
                spark_type = "DateType"
            elif phys_type == "TIMESTAMP":
                spark_type = "TimestampType"
            else:
                spark_type = "StringType"

            stats: Dict[str, Any] = {}

            if category in {"NUMERICAL_DISCRETE", "NUMERICAL_CONTINUOUS"} or phys_type in {"INTEGER", "DECIMAL/CONTINUOUS_NUMERIC"}:
                num_s = non_null_s if pd.api.types.is_numeric_dtype(non_null_s) else pd.to_numeric(non_null_s, errors="coerce").dropna()
                if len(num_s) > 0:
                    sample_s = num_s.sample(n=min(50000, len(num_s)), random_state=42) if len(num_s) > 50000 else num_s
                    q1 = float(sample_s.quantile(0.25))
                    q3 = float(sample_s.quantile(0.75))
                    mean_val = float(num_s.mean())
                    std_val = float(num_s.std()) if len(num_s) > 1 else 0.0
                    stats = {
                        "min": float(num_s.min()),
                        "max": float(num_s.max()),
                        "mean": round(mean_val, 4),
                        "median": round(float(sample_s.median()), 4),
                        "stddev": round(std_val, 4),
                        "variance": round(float(num_s.var()) if len(num_s) > 1 else 0.0, 4),
                        "q1": round(q1, 4),
                        "q3": round(q3, 4),
                        "iqr": round(q3 - q1, 4),
                        "skewness": round(float(sample_s.skew()) if len(sample_s) > 2 else 0.0, 4),
                        "kurtosis": round(float(sample_s.kurtosis()) if len(sample_s) > 3 else 0.0, 4)
                    }

            if "distribution" not in stats:
                # Calculate value distribution
                val_counts = non_null_s.value_counts().head(10)
                dist = []
                for val, count in val_counts.items():
                    pct = round((count / max(1, self.total_rows)) * 100, 2)
                    val_str = str(val)
                    if len(val_str) > 100:
                        val_str = val_str[:97] + "..."
                    dist.append({
                        "value": val_str,
                        "count": int(count),
                        "percentage": pct
                    })
                stats["distribution"] = dist

            profiles.append({
                "column": column,
                "spark_type": spark_type,
                "physical_datatype": phys_type,
                "category": category,
                "total_rows": self.total_rows,
                "non_null_count": non_null_cnt,
                "missing_count": missing_cnt,
                "missing_percentage": missing_pct,
                "unique_count": unique_cnt,
                "statistics": stats
            })

        return profiles
