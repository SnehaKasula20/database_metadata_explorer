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

class LocalOutputWriter:
    @staticmethod
    def save(df: DataFrame, source_base: str, requested_output: Optional[str] = None) -> str:
        if requested_output:
            output = Path(requested_output)
        else:
            source = Path(source_base)
            ext = source.suffix.lower()
            if ext not in {".csv", ".xlsx", ".parquet", ".json"}:
                ext = ".csv"
            output = source.parent / f"{source.stem}_imputed{ext}"

        output.parent.mkdir(parents=True, exist_ok=True)
        pdf = df.toPandas()

        ext = output.suffix.lower()
        if ext == ".xlsx":
            pdf.to_excel(output, index=False, engine="openpyxl")
        elif ext == ".parquet":
            pdf.to_parquet(output, index=False)
        elif ext == ".json":
            pdf.to_json(output, orient="records", indent=2, date_format="iso")
        else:
            if ext != ".csv":
                output = output.with_suffix(".csv")
            pdf.to_csv(output, index=False)

        return str(output.resolve())

class DataQualityValidator:
    @staticmethod
    def print_missing_summary(df: DataFrame):
        rows = df.count()
        print("\n" + "=" * 80)
        print("POST-IMPUTATION MISSING VALUE CHECK")
        print("=" * 80)
        for col in df.columns:
            missing = df.filter(F.col(col).isNull()).count()
            pct = missing / rows * 100 if rows else 0.0
            print(f"{col:<30} missing={missing:<5} ({pct:.2f}%)")

