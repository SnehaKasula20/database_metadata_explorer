from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
import pandas as pd
import numpy as np


class DataLoader:
    def __init__(self, spark: Any = None):
        self.spark = spark

    def pandas_to_spark(self, pdf: pd.DataFrame) -> pd.DataFrame:
        if pdf.empty:
            raise ValueError("Source DataFrame is empty.")
        return pdf.copy()

    def from_local_file(self, file_path: str) -> pd.DataFrame:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset does not exist: {file_path}")

        ext = path.suffix.lower()
        if ext == ".csv":
            return pd.read_csv(str(path))
        elif ext == ".parquet":
            return pd.read_parquet(str(path))
        elif ext == ".json":
            return pd.read_json(str(path))
        elif ext in {".xlsx", ".xls"}:
            return pd.read_excel(str(path))

        raise ValueError(f"Unsupported file format: {ext}")
