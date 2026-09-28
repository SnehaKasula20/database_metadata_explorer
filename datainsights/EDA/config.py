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

class ConfigurationManager:
    ENV_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")

    def __init__(
        self,
        config_path: str = "db_config.json",
        env_path: str = ".env"
    ):
        # Team-project layout:
        #   project/
        #     main.py
        #     EDA/
        #     config/db_config.json
        #     config/.env
        self.project_root = Path(__file__).resolve().parent.parent

        config_candidate = Path(config_path).expanduser()
        env_candidate = Path(env_path).expanduser()

        if config_candidate.is_absolute():
            self.config_path = config_candidate
        elif config_candidate.parts and config_candidate.parts[0] == "config":
            self.config_path = self.project_root / config_candidate
        else:
            self.config_path = self.project_root / "config" / config_candidate

        if env_candidate.is_absolute():
            self.env_path = env_candidate
        elif env_candidate.parts and env_candidate.parts[0] == "config":
            self.env_path = self.project_root / env_candidate
        else:
            self.env_path = self.project_root / "config" / env_candidate

        if not self.env_path.exists():
            raise FileNotFoundError(
                f".env file not found: {self.env_path}"
            )

        loaded = load_dotenv(
            dotenv_path=self.env_path,
            override=True
        )

        if not loaded:
            raise RuntimeError(
                f"Unable to load .env file: {self.env_path}"
            )

    def load_section(self, section_name: str) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path.resolve()}"
            )

        with self.config_path.open("r", encoding="utf-8") as fh:
            config = json.load(fh)

        if section_name not in config:
            raise KeyError(
                f"Missing '{section_name}' section in {self.config_path.name}"
            )

        # Resolve only the selected database section, so unused database
        # credentials do not need to exist in the current environment.
        return self._resolve_env_values(config[section_name])

    def _resolve_env_values(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._resolve_env_values(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._resolve_env_values(v) for v in value]
        if isinstance(value, str):
            match = self.ENV_PATTERN.match(value.strip())
            if match:
                env_name = match.group(1)
                env_value = os.getenv(env_name)
                if env_value is None:
                    raise ValueError(
                        f"Environment variable {env_name!r} is required "
                        f"by {self.config_path.name} but was not found "
                        f"in {self.env_path.name}."
                    )
                return env_value
        return value

