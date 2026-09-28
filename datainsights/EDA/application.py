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

from .spark import SparkSessionManager
from .sources import (
    SourceSelection, LocalFileBatch, DatabaseSession, InteractiveSourceSelector,
)
from .semantics import MissingValueNormalizer, SemanticSchemaRefiner
from .quality import DataInconsistencyAnalyzer, DuplicateRecordAnalyzer
from .profiling import DatasetProfiler
from .imputation import (
    TerminalSelection, DateImputationRuleManager, ImputationRecommender, ImputationEngine,
)
from .reporting import EDAReportEntry, PDFStatisticsReportWriter
from .output import LocalOutputWriter, DataQualityValidator

class InteractiveEDAApplication:
    DATABASE_FOLLOWUP_OPTIONS = [
        "Analyze another table in the current schema",
        "Select another schema and table",
        "ALL - analyze all schemas and all tables in this database",
        "Finish and generate PDF report",
    ]

    def __init__(self, config_path="db_config.json"):
        self.spark = SparkSessionManager.create()
        self.config_path = config_path
        self.report_entries: list[EDAReportEntry] = []
        self.processed_objects: set[tuple[str, str, str]] = set()

    def run(self):
        self._banner()
        database_session = None

        try:
            selected_source = InteractiveSourceSelector(
                self.spark,
                self.config_path,
            ).select()

            if isinstance(
                selected_source,
                DatabaseSession,
            ):
                database_session = selected_source
                self._run_database_session(
                    database_session
                )

            elif isinstance(
                selected_source,
                LocalFileBatch,
            ):
                self._run_local_file_batch(
                    selected_source
                )

            else:
                # Defensive fallback for a direct SourceSelection.
                self._process_source_selection(
                    selected_source,
                    database=None,
                    schema=None,
                    table=Path(
                        selected_source.local_output_base
                    ).stem,
                    bulk_mode=False,
                )
                self._write_pdf_report()

        except Exception as exc:
            print("\nAPPLICATION ERROR")
            print(f"{type(exc).__name__}: {exc}")

            # If some tables completed before a later failure, still preserve
            # the available statistics in a PDF.
            if self.report_entries:
                try:
                    self._write_pdf_report()
                except Exception as pdf_exc:
                    print(
                        f"PDF report could not be generated: "
                        f"{type(pdf_exc).__name__}: {pdf_exc}"
                    )

        finally:
            if database_session is not None:
                database_session.close()
            self.spark.stop()

    def _run_local_file_batch(
        self,
        batch: LocalFileBatch,
    ):
        """
        Process files selected from File Explorer.

        One selected file:
            Preserve the existing interactive EDA/imputation behavior.

        Multiple selected files:
            Behave like ALL TABLES bulk EDA:
            - profile each file independently
            - no interactive date/imputation prompts
            - continue if one file fails
            - generate one combined PDF report
        """
        paths = batch.paths

        if not paths:
            raise ValueError(
                "No local files were selected."
            )

        bulk_mode = len(paths) > 1

        print("\n" + "=" * 80)

        if bulk_mode:
            print(
                "BULK EDA - MULTIPLE LOCAL FILES"
            )
        else:
            print(
                "EDA - LOCAL FILE"
            )

        print("=" * 80)

        print(
            f"Files selected: {len(paths)}"
        )

        for index, file_path in enumerate(
            paths,
            1,
        ):
            table_name = Path(
                file_path
            ).stem

            print(
                f"\nProfiling [{index}/{len(paths)}]: "
                f"{file_path}"
            )

            try:
                selection = batch.load_file(
                    file_path
                )

                self._process_source_selection(
                    selection=selection,
                    database=None,
                    schema=None,
                    table=table_name,
                    bulk_mode=bulk_mode,
                )

            except Exception as exc:
                print(
                    f"Could not profile file '{file_path}': "
                    f"{type(exc).__name__}: {exc}"
                )

                self.report_entries.append(
                    EDAReportEntry(
                        source=str(
                            Path(file_path).resolve()
                        ),
                        database=None,
                        schema=None,
                        table=table_name,
                        row_count=0,
                        column_count=0,
                        profiles=[],
                        error=(
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )
                )

                # For a single interactive file, preserve normal fail-fast
                # behavior after recording the error. For multi-file bulk
                # selection, continue to the next file.
                if not bulk_mode:
                    raise

        self._write_pdf_report()


    def _run_database_session(self, session: DatabaseSession):
        print(
            f"\nConnected database: {session.label} / {session.database}"
        )
        print(
            "The connection will remain open while you analyze tables "
            "in this database."
        )

        if session.source_key == "mysql":
            # MySQL DATABASE and SCHEMA are synonyms. There is no separate
            # schema hierarchy to browse beneath the selected database.
            self._run_mysql_database_flow(session)
            return

        # Oracle, Snowflake, SQL Server and PostgreSQL expose schema/user-level
        # namespaces inside the selected database/service.
        self._run_schema_database_flow(session)

    def _run_schema_database_flow(self, session: DatabaseSession):
        schemas = session.list_schemas()

        schema_options = schemas + ["ALL SCHEMAS"]

        selected_schema = InteractiveSourceSelector._select_numbered(
            f"SCHEMAS / USERS IN DATABASE: {session.database}",
            schema_options,
        )

        if selected_schema == "ALL SCHEMAS":
            self._profile_all_schemas(session, schemas)
            self._write_pdf_report()
            return

        tables = session.list_tables(selected_schema)
        table_options = tables + ["ALL TABLES"]

        selected_table = InteractiveSourceSelector._select_numbered(
            f"TABLES IN {session.database}.{selected_schema}",
            table_options,
        )

        if selected_table == "ALL TABLES":
            self._profile_schema_tables(
                session=session,
                schema=selected_schema,
                tables=tables,
            )
            self._write_pdf_report()
            return

        self._process_database_table(
            session,
            selected_schema,
            selected_table,
            bulk_mode=False,
        )

        self._post_single_table_menu(
            session=session,
            current_schema=selected_schema,
        )

    def _run_mysql_database_flow(self, session: DatabaseSession):
        tables = session.list_tables(session.database)
        table_options = tables + ["ALL TABLES"]

        selected_table = InteractiveSourceSelector._select_numbered(
            f"TABLES IN MYSQL DATABASE: {session.database}",
            table_options,
        )

        if selected_table == "ALL TABLES":
            self._profile_schema_tables(
                session=session,
                schema=session.database,
                tables=tables,
            )
            self._write_pdf_report()
            return

        self._process_database_table(
            session,
            session.database,
            selected_table,
            bulk_mode=False,
        )

        self._post_mysql_single_table_menu(session)

    def _post_single_table_menu(
        self,
        session: DatabaseSession,
        current_schema: str,
    ):
        """
        After one interactive table run, allow continued analysis without
        reconnecting to the database.
        """
        while True:
            print("\n" + "=" * 80)
            print("CONTINUE EDA IN CURRENT DATABASE")
            print("=" * 80)
            print("1. Analyze another table in the current schema")
            print("2. Select another schema / user")
            print("3. Analyze ALL TABLES in the current schema")
            print("4. Analyze ALL SCHEMAS / ALL TABLES")
            print("5. Finish and generate PDF report")

            choice = input("\nSelect option [1-5]: ").strip()

            if choice == "1":
                tables = session.list_tables(current_schema)
                selected = InteractiveSourceSelector._select_numbered(
                    f"TABLES IN {session.database}.{current_schema}",
                    tables + ["ALL TABLES"],
                )

                if selected == "ALL TABLES":
                    self._profile_schema_tables(
                        session,
                        current_schema,
                        tables,
                    )
                    self._write_pdf_report()
                    return

                self._process_database_table(
                    session,
                    current_schema,
                    selected,
                    bulk_mode=False,
                )

            elif choice == "2":
                schemas = session.list_schemas()
                selected_schema = InteractiveSourceSelector._select_numbered(
                    f"SCHEMAS / USERS IN DATABASE: {session.database}",
                    schemas + ["ALL SCHEMAS"],
                )

                if selected_schema == "ALL SCHEMAS":
                    self._profile_all_schemas(session, schemas)
                    self._write_pdf_report()
                    return

                current_schema = selected_schema
                tables = session.list_tables(current_schema)

                selected_table = InteractiveSourceSelector._select_numbered(
                    f"TABLES IN {session.database}.{current_schema}",
                    tables + ["ALL TABLES"],
                )

                if selected_table == "ALL TABLES":
                    self._profile_schema_tables(
                        session,
                        current_schema,
                        tables,
                    )
                    self._write_pdf_report()
                    return

                self._process_database_table(
                    session,
                    current_schema,
                    selected_table,
                    bulk_mode=False,
                )

            elif choice == "3":
                tables = session.list_tables(current_schema)
                self._profile_schema_tables(
                    session,
                    current_schema,
                    tables,
                )
                self._write_pdf_report()
                return

            elif choice == "4":
                self._profile_all_schemas(
                    session,
                    session.list_schemas(),
                )
                self._write_pdf_report()
                return

            elif choice == "5":
                self._write_pdf_report()
                return

            else:
                print("Invalid selection. Enter a number between 1 and 5.")

    def _post_mysql_single_table_menu(self, session: DatabaseSession):
        while True:
            print("\n" + "=" * 80)
            print("CONTINUE EDA IN CURRENT MYSQL DATABASE")
            print("=" * 80)
            print("1. Analyze another table")
            print("2. Analyze ALL TABLES")
            print("3. Finish and generate PDF report")

            choice = input("\nSelect option [1-3]: ").strip()

            if choice == "1":
                tables = session.list_tables(session.database)
                selected = InteractiveSourceSelector._select_numbered(
                    f"TABLES IN MYSQL DATABASE: {session.database}",
                    tables + ["ALL TABLES"],
                )

                if selected == "ALL TABLES":
                    self._profile_schema_tables(
                        session,
                        session.database,
                        tables,
                    )
                    self._write_pdf_report()
                    return

                self._process_database_table(
                    session,
                    session.database,
                    selected,
                    bulk_mode=False,
                )

            elif choice == "2":
                tables = session.list_tables(session.database)
                self._profile_schema_tables(
                    session,
                    session.database,
                    tables,
                )
                self._write_pdf_report()
                return

            elif choice == "3":
                self._write_pdf_report()
                return

            else:
                print("Invalid selection. Enter 1, 2, or 3.")

    def _profile_schema_tables(
        self,
        session: DatabaseSession,
        schema: str,
        tables: list[str],
    ):
        print("\n" + "=" * 80)
        print(
            f"BULK EDA - ALL TABLES IN "
            f"{session.database}.{schema}"
        )
        print("=" * 80)

        for index, table in enumerate(tables, 1):
            key = (session.database, schema, table)

            if key in self.processed_objects:
                print(
                    f"\nSkipping already-profiled table: "
                    f"{session.database}.{schema}.{table}"
                )
                continue

            print(
                f"\nProfiling [{index}/{len(tables)}]: "
                f"{session.database}.{schema}.{table}"
            )

            try:
                self._process_database_table(
                    session,
                    schema,
                    table,
                    bulk_mode=True,
                )
            except Exception as exc:
                print(
                    f"Could not profile {session.database}.{schema}.{table}: "
                    f"{type(exc).__name__}: {exc}"
                )

                self.report_entries.append(
                    EDAReportEntry(
                        source=session.label,
                        database=session.database,
                        schema=schema,
                        table=table,
                        row_count=0,
                        column_count=0,
                        profiles=[],
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

                self.processed_objects.add(key)

    def _profile_all_schemas(
        self,
        session: DatabaseSession,
        schemas: list[str],
    ):
        print("\n" + "=" * 80)
        print("BULK EDA - ALL SCHEMAS / ALL TABLES")
        print("=" * 80)

        total_tables = sum(
            len(session.list_tables(schema))
            for schema in schemas
        )

        completed = 0

        for schema in schemas:
            tables = session.list_tables(schema)

            print(
                f"\nSchema/User: {schema} "
                f"({len(tables)} table(s))"
            )

            for table in tables:
                completed += 1
                key = (session.database, schema, table)

                if key in self.processed_objects:
                    print(
                        f"Skipping [{completed}/{total_tables}] "
                        f"{session.database}.{schema}.{table} "
                        f"(already profiled)"
                    )
                    continue

                print(
                    f"\nProfiling [{completed}/{total_tables}]: "
                    f"{session.database}.{schema}.{table}"
                )

                try:
                    self._process_database_table(
                        session,
                        schema,
                        table,
                        bulk_mode=True,
                    )

                except Exception as exc:
                    print(
                        f"Could not profile "
                        f"{session.database}.{schema}.{table}: "
                        f"{type(exc).__name__}: {exc}"
                    )

                    self.report_entries.append(
                        EDAReportEntry(
                            source=session.label,
                            database=session.database,
                            schema=schema,
                            table=table,
                            row_count=0,
                            column_count=0,
                            profiles=[],
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )

                    self.processed_objects.add(key)

    def _process_database_table(
        self,
        session: DatabaseSession,
        schema: str,
        table: str,
        bulk_mode: bool,
    ):
        key = (session.database, schema, table)

        if key in self.processed_objects:
            print(
                f"\n{session.database}.{schema}.{table} "
                f"was already profiled in this session."
            )

            rerun = input(
                "Profile it again? [y/N]: "
            ).strip().lower()

            if rerun not in {"y", "yes"}:
                return

        selection = session.load_table(schema, table)

        self._process_source_selection(
            selection=selection,
            database=session.database,
            schema=schema,
            table=table,
            bulk_mode=bulk_mode,
        )

        self.processed_objects.add(key)

    def _process_source_selection(
        self,
        selection: SourceSelection,
        database: Optional[str],
        schema: Optional[str],
        table: str,
        bulk_mode: bool,
    ):
        print(f"\nSource: {selection.description}")

        # Analyze RAW source values first. This must run before
        # MissingValueNormalizer trims strings or converts missing tokens.
        inconsistency_info = DataInconsistencyAnalyzer.analyze(
            selection.df
        )

        df = MissingValueNormalizer.normalize(selection.df)
        df = SemanticSchemaRefiner.refine(df).cache()

        try:
            row_count = df.count()

            if row_count == 0:
                raise ValueError("Dataset contains no rows.")

            print("\nDATA PREVIEW")
            df.show(5, truncate=False)

            # Duplicate analysis is performed before imputation changes values.
            duplicate_info = DuplicateRecordAnalyzer.analyze(
                df
            )

            profiles = DatasetProfiler(df).profile()

            if bulk_mode:
                date_rules = {}

            else:
                date_rules = (
                    DateImputationRuleManager()
                    .collect_rules(
                        df,
                        profiles,
                    )
                )

            profiles = (
                ImputationRecommender
                .add_recommendations(
                    profiles,
                    date_rules,
                )
            )

            if bulk_mode:
                for profile in profiles:
                    if (
                        profile["category"]
                        in {
                            "DATETIME",
                            "DATETIME_STRING",
                        }
                        and profile[
                            "missing_count"
                        ] > 0
                    ):
                        profile[
                            "recommended_method"
                        ] = (
                            "DATE_METHOD_SELECTION_REQUIRED"
                        )

                        profile[
                            "imputation_value"
                        ] = None

                        profile[
                            "reason"
                        ] = (
                            "Bulk EDA does not select a "
                            "date NULL-replacement method. "
                            "Review this table interactively "
                            "before date imputation."
                        )

            self._print_recommendations(
                profiles
            )

            self.report_entries.append(
                EDAReportEntry(
                    source=selection.description,
                    database=database,
                    schema=schema,
                    table=table,
                    row_count=row_count,
                    column_count=len(
                        df.columns
                    ),
                    profiles=profiles,
                    duplicate_group_count=(
                        duplicate_info[
                            "duplicate_group_count"
                        ]
                    ),
                    duplicate_extra_record_count=(
                        duplicate_info[
                            "duplicate_extra_record_count"
                        ]
                    ),
                    duplicate_audit_columns=(
                        duplicate_info[
                            "audit_columns"
                        ]
                    ),
                    inconsistencies=(
                        inconsistency_info[
                            "issues"
                        ]
                    ),
                    potential_anomalies=(
                        inconsistency_info[
                            "potential_anomalies"
                        ]
                    ),
                    inconsistent_columns=(
                        inconsistency_info[
                            "inconsistent_columns"
                        ]
                    ),
                    potential_anomaly_columns=(
                        inconsistency_info[
                            "potential_anomaly_columns"
                        ]
                    ),
                )
            )

            # Bulk analysis remains profiling/reporting only.
            if bulk_mode:
                return

            eligible_columns = [
                profile["column"]
                for profile in profiles
                if (
                    profile[
                        "missing_count"
                    ] > 0
                    and profile[
                        "recommended_method"
                    ]
                    not in {
                        "NONE",
                        "LEAVE_NULL",
                    }
                )
            ]

            if not eligible_columns:
                print(
                    "\nNo columns have an actionable "
                    "imputation recommendation."
                )

                imputed = df

            else:
                print(
                    "\n"
                    + "=" * 80
                )

                print(
                    "SELECT COLUMNS FOR IMPUTATION"
                )

                print(
                    "=" * 80
                )

                print(
                    "Select only the columns where "
                    "imputation should actually be applied."
                )

                selected_columns = (
                    TerminalSelection
                    .select_many(
                        prompt=(
                            "Imputation column selection"
                        ),
                        options=eligible_columns,
                        allow_none=True,
                    )
                )

                if not selected_columns:
                    print(
                        "No columns selected. "
                        "Imputation skipped."
                    )

                    imputed = df

                else:
                    selected_profiles = [
                        profile
                        for profile in profiles
                        if profile[
                            "column"
                        ]
                        in selected_columns
                    ]

                    print(
                        "\nSelected columns: "
                        + ", ".join(
                            selected_columns
                        )
                    )

                    imputed = (
                        ImputationEngine
                        .apply(
                            df,
                            selected_profiles,
                            date_rules,
                        )
                    )

            DataQualityValidator.print_missing_summary(
                imputed
            )

            output = input(
                "\nEnter local output path "
                "(Enter for automatic name): "
            ).strip().strip('"').strip("'")

            saved = LocalOutputWriter.save(
                imputed,
                selection.local_output_base,
                output if output else None,
            )

            print(
                f"\nOutput dataset created:\n"
                f"{saved}"
            )

        finally:
            df.unpersist()

    def _write_pdf_report(self):
        if not self.report_entries:
            print("\nNo EDA statistics are available for PDF generation.")
            return

        custom_path = input(
            "\nEnter PDF report path "
            "(Enter to save automatically under EDA_REPORTS): "
        ).strip().strip('"').strip("'")

        saved_pdf = PDFStatisticsReportWriter.save(
            entries=self.report_entries,
            output_path=custom_path or None,
        )

        print(f"\nEDA statistics PDF created:\n{saved_pdf}")

    @staticmethod
    def _banner():
        print("\n" + "=" * 80)
        print("PYSPARK INTERACTIVE EDA & IMPUTATION FRAMEWORK - V3")
        print("=" * 80)
        print(
            "Sources: Snowflake, SQL Server, Oracle, MySQL, PostgreSQL, "
            "Windows File Explorer"
        )
        print(
            "Supports multi-table database EDA, multi-file local EDA, "
            "and combined PDF reporting."
        )

    @staticmethod
    def _print_recommendations(profiles):
        print("\n" + "=" * 120)
        print("IMPUTATION RECOMMENDATION SUMMARY")
        print("=" * 120)

        for p in profiles:
            print(
                f"{p['column']:<25} "
                f"{p['category']:<25} "
                f"missing={p['missing_count']:<4} "
                f"method={p['recommended_method']:<22} "
                f"value={p.get('imputation_value')} "
            )
            print(f"  Reason: {p['reason']}")

