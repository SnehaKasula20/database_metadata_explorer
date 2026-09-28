"""EDA package - modular EDA and profiling framework."""

from .spark import SparkSessionManager
from .sources import DataLoader
from .semantics import (
    MissingValueNormalizer, ColumnTypeDetector, SemanticSchemaRefiner,
)
from .quality import DataInconsistencyAnalyzer, DuplicateRecordAnalyzer
from .profiling import DatasetProfiler
from .imputation import ImputationRecommender
from .reporting import EDAReportEntry

__all__ = [
    "SparkSessionManager",
    "DataLoader",
    "MissingValueNormalizer",
    "ColumnTypeDetector",
    "SemanticSchemaRefiner",
    "DataInconsistencyAnalyzer",
    "DuplicateRecordAnalyzer",
    "DatasetProfiler",
    "ImputationRecommender",
    "EDAReportEntry",
]
