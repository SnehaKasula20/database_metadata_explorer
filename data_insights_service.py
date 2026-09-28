import logging
import os
import sys
from typing import Any, Dict, List, Optional

from datainsights.EDA.connectors import DatabaseConnectorFactory
from datainsights.EDA.sources import DataLoader

from datainsights.EDA.semantics import MissingValueNormalizer, SemanticSchemaRefiner
from datainsights.EDA.quality import DataInconsistencyAnalyzer, DuplicateRecordAnalyzer
from datainsights.EDA.profiling import DatasetProfiler
from datainsights.EDA.imputation import ImputationRecommender
from datainsights.EDA.reporting import EDAReportEntry

logger = logging.getLogger("data_insights_service")

# Mapping from explorer database types to Data Insights connector keys
DB_TYPE_MAP = {
    "PostgreSQL": "postgres",
    "MySQL": "mysql",
    "Oracle": "oracle",
    "SQL Server": "sql_server",
    "postgres": "postgres",
    "mysql": "mysql",
    "oracle": "oracle",
    "sql_server": "sql_server",
}


class DataInsightsService:
    """Service wrapper for Data Insights profiling & reporting operations."""

    def __init__(self):
        self.cached_profile_entries: Dict[str, EDAReportEntry] = {}
        self.cached_profile_payloads: Dict[str, Dict[str, Any]] = {}

    def get_spark(self):
        return None

    @staticmethod
    def map_credentials(db_type: str, creds: dict) -> dict:
        source_name = DB_TYPE_MAP.get(db_type, db_type.lower())
        host = creds.get("host", "localhost")
        port = creds.get("port")
        username = creds.get("username") or creds.get("user") or ""
        password = creds.get("password") or ""
        database = creds.get("database") or creds.get("dbname") or ""

        if source_name == "postgres":
            mapped = {
                "host": host,
                "port": int(port) if port else 5432,
                "user": username,
                "password": password,
                "maintenance_database": database or "postgres",
            }
        elif source_name == "mysql":
            mapped = {
                "host": host,
                "port": int(port) if port else 3306,
                "user": username,
                "password": password,
            }
            if database:
                mapped["database"] = database
        elif source_name == "oracle":
            sid = creds.get("sid") or creds.get("service_name") or "ORCL"
            mapped = {
                "host": host,
                "port": int(port) if port else 1521,
                "user": username,
                "password": password,
                "sid": sid,
            }
        elif source_name == "sql_server":
            mapped = {
                "driver": creds.get("driver", "ODBC Driver 17 for SQL Server"),
                "host": host,
                "port": int(port) if port else 1433,
                "user": username,
                "password": password,
                "initial_database": database or "master",
                "encrypt": creds.get("encrypt", "no"),
                "trust_server_certificate": creds.get(
                    "trust_server_certificate", "yes"
                ),
            }
        else:
            mapped = creds.copy()
            if "username" in mapped and "user" not in mapped:
                mapped["user"] = mapped.pop("username")
        return mapped

    def get_connector(self, db_type: str, creds: dict):
        source_name = DB_TYPE_MAP.get(db_type, db_type.lower())
        config = self.map_credentials(db_type, creds)
        connector = DatabaseConnectorFactory.create(source_name, config)
        connector.connect()
        return connector

    def list_databases(self, db_type: str, creds: dict) -> List[str]:
        connector = self.get_connector(db_type, creds)
        try:
            return connector.list_databases()
        finally:
            connector.close()

    def list_schemas(
        self, db_type: str, creds: dict, database: Optional[str] = None
    ) -> List[str]:
        connector = self.get_connector(db_type, creds)
        try:
            target_db = (
                database
                or creds.get("database")
                or creds.get("service_name")
                or "default"
            )
            return connector.list_schemas(target_db)
        finally:
            connector.close()

    def list_tables(
        self, db_type: str, creds: dict, database: str, schema: str
    ) -> List[str]:
        connector = self.get_connector(db_type, creds)
        try:
            return connector.list_tables(database, schema)
        finally:
            connector.close()

    def profile_table(
        self,
        db_type: str,
        creds: dict,
        database: str,
        schema: str,
        table: str,
        limit: Optional[int] = 1000,
    ) -> Dict[str, Any]:
        connector = self.get_connector(db_type, creds)
        try:
            # Full table scan when limit is 0 (None), otherwise apply requested limit
            effective_limit = None if limit == 0 else limit
            pdf = connector.read_table(database, schema, table, limit=effective_limit)
        finally:
            connector.close()

        if pdf.empty:
            raise ValueError(f"Table '{schema}.{table}' contains no data rows.")

        # 1. RAW Inconsistency Analysis
        inconsistency_info = DataInconsistencyAnalyzer.analyze(pdf)

        # 2. Normalization & Refinement
        norm_df = MissingValueNormalizer.normalize(pdf)
        refined_df = SemanticSchemaRefiner.refine(norm_df)

        # 3. Duplicate Analysis
        duplicate_info = DuplicateRecordAnalyzer.analyze(refined_df)

        # 4. Column Profiling
        profiles = DatasetProfiler(refined_df).profile()

        # 5. Imputation Recommendations
        profiles = ImputationRecommender.add_recommendations(profiles, date_rules={})

        row_count = len(refined_df)
        col_count = len(refined_df.columns)

        # Store report entry for PDF export
        cache_key = f"{database}.{schema}.{table}"
        entry = EDAReportEntry(
            source=f"{db_type} ({database})",
            database=database,
            schema=schema,
            table=table,
            row_count=row_count,
            column_count=col_count,
            profiles=profiles,
            duplicate_group_count=duplicate_info.get("duplicate_group_count", 0),
            duplicate_extra_record_count=duplicate_info.get(
                "duplicate_extra_record_count", 0
            ),
            duplicate_audit_columns=duplicate_info.get("audit_columns"),
            inconsistencies=inconsistency_info.get("issues"),
            potential_anomalies=inconsistency_info.get("potential_anomalies"),
            inconsistent_columns=inconsistency_info.get("inconsistent_columns"),
            potential_anomaly_columns=inconsistency_info.get(
                "potential_anomaly_columns"
            ),
        )
        self.cached_profile_entries[cache_key] = entry

        # Construct JSON response for dashboard frontend
        payload = self._build_dashboard_payload(
            database=database,
            schema=schema,
            table=table,
            row_count=row_count,
            col_count=col_count,
            profiles=profiles,
            inconsistency_info=inconsistency_info,
            duplicate_info=duplicate_info,
        )
        self.cached_profile_payloads[cache_key] = payload
        return payload

    def get_cached_or_profile_table(
        self,
        db_type: str,
        creds: dict,
        database: str,
        schema: str,
        table: str,
        limit: Optional[int] = 1000,
    ) -> Dict[str, Any]:
        cache_key = f"{database}.{schema}.{table}"
        if cache_key in self.cached_profile_payloads:
            return self.cached_profile_payloads[cache_key]
        return self.profile_table(db_type, creds, database, schema, table, limit=limit)

    def _build_dashboard_payload(
        self,
        database: str,
        schema: str,
        table: str,
        row_count: int,
        col_count: int,
        profiles: List[Dict[str, Any]],
        inconsistency_info: Dict[str, Any],
        duplicate_info: Dict[str, Any],
    ) -> Dict[str, Any]:

        total_missing_cells = sum(p.get("missing_count", 0) for p in profiles)
        total_total_cells = sum(p.get("total_rows", row_count) for p in profiles)
        missing_pct = round((total_missing_cells / max(1, total_total_cells)) * 100, 2)

        duplicate_extra = duplicate_info.get("duplicate_extra_record_count", 0)
        duplicate_groups = duplicate_info.get("duplicate_group_count", 0)
        duplicate_pct = round((duplicate_extra / max(1, row_count)) * 100, 2)

        inconsistencies = inconsistency_info.get("issues", [])
        potential_anomalies = inconsistency_info.get("potential_anomalies", [])

        # 1. Missing Values by Column
        missing_by_col = {
            "labels": [p["column"] for p in profiles],
            "values": [round(p.get("missing_percentage", 0), 2) for p in profiles],
            "counts": [p.get("missing_count", 0) for p in profiles],
        }

        # 2. Data Quality Overview (Doughnut)
        complete_cells = max(0, total_total_cells - total_missing_cells)
        quality_overview = {
            "labels": [
                "Complete Data Cells",
                "Missing Cells",
                "Confirmed Inconsistencies",
                "Potential Anomalies",
            ],
            "values": [
                complete_cells,
                total_missing_cells,
                len(inconsistencies),
                len(potential_anomalies),
            ],
        }

        # 3. Unique vs Duplicate Records
        unique_records = max(0, row_count - duplicate_extra)
        record_duplicates = {
            "labels": ["Unique Records", "Duplicate Extra Records"],
            "values": [unique_records, duplicate_extra],
        }

        # 4. Semantic Type Distribution
        category_counts = {}
        for p in profiles:
            cat = p.get("category", "OTHER")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        semantic_distribution = {
            "labels": list(category_counts.keys()),
            "values": list(category_counts.values()),
        }

        # 5. Numeric Distributions (Top numeric columns)
        numeric_profiles = [
            p
            for p in profiles
            if p.get("statistics", {}).get("mean") is not None
            or p.get("category") in {"NUMERICAL_DISCRETE", "NUMERICAL_CONTINUOUS"}
        ]
        numeric_summary = {
            "labels": [p["column"] for p in numeric_profiles],
            "means": [p.get("statistics", {}).get("mean") for p in numeric_profiles],
            "medians": [
                p.get("statistics", {}).get("median") for p in numeric_profiles
            ],
            "stddevs": [
                p.get("statistics", {}).get("stddev") for p in numeric_profiles
            ],
            "mins": [p.get("statistics", {}).get("min") for p in numeric_profiles],
            "maxs": [p.get("statistics", {}).get("max") for p in numeric_profiles],
        }

        # 6. Categorical Distributions
        cat_profiles = [
            p
            for p in profiles
            if p.get("category")
            in {"CATEGORICAL_NOMINAL", "CATEGORICAL_ORDINAL", "BOOLEAN"}
        ]
        categorical_summary = []
        for cp in cat_profiles[:5]:
            dist = cp.get("statistics", {}).get("distribution", [])
            categorical_summary.append(
                {
                    "column": cp["column"],
                    "labels": [str(d.get("value")) for d in dist[:5]],
                    "counts": [d.get("count", 0) for d in dist[:5]],
                }
            )

        # Build Imputation Recommendations Table Data
        imputation_recommendations = []
        for p in profiles:
            rec_method = (
                p.get("recommended_method")
                or p.get("recommendation", {}).get("method")
                or "None (Complete)"
            )
            reason = (
                p.get("reason")
                or p.get("recommendation", {}).get("reason")
                or "No missing values detected."
            )
            imputation_recommendations.append(
                {
                    "column": p["column"],
                    "missing_count": p.get("missing_count", 0),
                    "missing_pct": round(p.get("missing_percentage", 0), 2),
                    "recommended_method": rec_method,
                    "reason": reason,
                }
            )

        return {
            "success": True,
            "database": database,
            "schema": schema,
            "table": table,
            "summary": {
                "total_rows": row_count,
                "total_columns": col_count,
                "missing_cells": total_missing_cells,
                "missing_percentage": missing_pct,
                "duplicate_extra_records": duplicate_extra,
                "duplicate_groups": duplicate_groups,
                "duplicate_percentage": duplicate_pct,
                "inconsistencies": len(inconsistencies),
                "potential_anomalies": len(potential_anomalies),
            },
            "charts": {
                "missing_by_col": missing_by_col,
                "quality_overview": quality_overview,
                "record_duplicates": record_duplicates,
                "semantic_distribution": semantic_distribution,
                "numeric_summary": numeric_summary,
                "categorical_summary": categorical_summary,
            },
            "profiles": profiles,
            "column_profiles": profiles,
            "inconsistencies": inconsistencies,
            "potential_anomalies": potential_anomalies,
            "duplicate_info": duplicate_info,
            "imputation_recommendations": imputation_recommendations,
        }


# Singleton service instance
data_insights_service = DataInsightsService()
