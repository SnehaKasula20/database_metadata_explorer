import logging
from pathlib import Path
from getpass import getpass
from typing import Any, Dict, List

from config.config import load_database_config
from database_connectors.base import BaseDatabaseConnector

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


class DatabaseMetadataExplorer:

    CONFIG_PATH = Path(__file__).resolve().parent / "config" / "database_config.json"

    DATABASES = {
        1: "PostgreSQL",
        2: "SQL Server",
        3: "Oracle",
        4: "MySQL",
    }

    REQUIRED_CREDENTIAL_FIELDS = {
        "PostgreSQL": {"host", "port", "username", "password", "database"},
        "SQL Server": {"host", "port", "username", "password", "database", "schema"},
        "Oracle": {"host", "port", "username", "password", "service_name"},
        "MySQL": {"host", "port", "username", "password"},
    }
    CONFIG_PLACEHOLDERS = {"CHANGE_ME", "REPLACE_ME", "TODO"}

    def __init__(self):

        self.connector: BaseDatabaseConnector | None = None
        self.database_type: str | None = None
        self.credentials: Dict[str, Any] = {}
        self.config: Dict[str, Any] = load_database_config(self.CONFIG_PATH)

        self.spark = None

    # Database Options

    def display_database_options(self) -> None:

        print("\n========================================")
        print("     DATABASE METADATA EXPLORER")
        print("========================================")

        print("\nSelect Database:")

        for number, database in self.DATABASES.items():
            print(f"{number}. {database}")

        print()

    # Database Choice

    def get_database_choice(self) -> str:

        while True:

            try:

                choice = int(input("Enter your choice: ").strip())

                if choice in self.DATABASES:

                    return self.DATABASES[choice]

                print("Invalid choice. Please select a number from 1 to 4.")

            except ValueError:

                print("Please enter a valid number.")

    # Credentials

    def get_credentials(self, database_type: str) -> Dict[str, Any]:

        configured_credentials = dict(self.config.get(database_type, {}))
        has_saved_values = any(
            self._is_configured_value(value)
            for value in configured_credentials.values()
        )

        if has_saved_values:
            print(f"\nLoaded saved values from {self.CONFIG_PATH.name}.")

        credentials: Dict[str, Any] = {}

        print(f"\n{database_type} Connection")
        print("-" * 40)

        if database_type == "PostgreSQL":

            credentials["host"] = self._prompt_or_use(
                "Host: ", configured_credentials.get("host")
            )
            credentials["port"] = self._prompt_or_use(
                "Port [5432]: ", configured_credentials.get("port"), "5432"
            )
            credentials["username"] = self._prompt_or_use(
                "Username: ", configured_credentials.get("username")
            )
            credentials["password"] = self._prompt_or_use_password(
                configured_credentials.get("password")
            )
            credentials["database"] = self._prompt_or_use(
                "Database Name [optional, press Enter for ALL databases]: ",
                configured_credentials.get("database"),
                "",
            )

        elif database_type == "SQL Server":

            credentials["host"] = self._prompt_or_use(
                "Host: ", configured_credentials.get("host")
            )
            credentials["port"] = self._prompt_or_use(
                "Port [1433]: ", configured_credentials.get("port"), "1433"
            )
            credentials["username"] = self._prompt_or_use(
                "Username: ", configured_credentials.get("username")
            )
            credentials["password"] = self._prompt_or_use_password(
                configured_credentials.get("password")
            )
            credentials["database"] = self._prompt_or_use(
                "Database Name [optional, press Enter for ALL databases]: ",
                configured_credentials.get("database"),
                "",
            )
            credentials["schema"] = self._prompt_or_use(
                "Schema Name [dbo]: ", configured_credentials.get("schema"), "dbo"
            )

        elif database_type == "Oracle":

            credentials["host"] = self._prompt_or_use(
                "Host: ", configured_credentials.get("host")
            )
            credentials["port"] = self._prompt_or_use(
                "Port [1521]: ", configured_credentials.get("port"), "1521"
            )
            credentials["username"] = self._prompt_or_use(
                "Username: ", configured_credentials.get("username")
            )
            credentials["password"] = self._prompt_or_use_password(
                configured_credentials.get("password")
            )
            credentials["service_name"] = self._prompt_or_use(
                "Service Name: ", configured_credentials.get("service_name")
            )
            schema_val = configured_credentials.get("schema")
            if self._is_configured_value(schema_val):
                credentials["schema"] = str(schema_val).strip().upper()
            else:
                schema_input = input("Schema/Owner [optional, press Enter for entire DB]: ").strip()
                credentials["schema"] = schema_input.upper() if schema_input else credentials["username"].upper()

        elif database_type == "MySQL":

            credentials["host"] = self._prompt_or_use(
                "Host: ", configured_credentials.get("host")
            )
            credentials["port"] = self._prompt_or_use(
                "Port [3306]: ", configured_credentials.get("port"), "3306"
            )
            credentials["username"] = self._prompt_or_use(
                "Username: ", configured_credentials.get("username")
            )
            credentials["password"] = self._prompt_or_use_password(
                configured_credentials.get("password")
            )



        return credentials

    def _is_configured_value(self, value: Any) -> bool:

        if value is None:
            return False

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                return False

            if normalized.upper() in self.CONFIG_PLACEHOLDERS:
                return False

        return True

    def _prompt_or_use(
        self,
        prompt: str,
        configured_value: Any,
        default_value: str | None = None,
    ) -> str:

        if self._is_configured_value(configured_value):
            return str(configured_value).strip()

        value = input(prompt).strip()

        if value:
            return value

        return default_value or ""

    def _prompt_or_use_password(self, configured_value: Any) -> str:

        if self._is_configured_value(configured_value):
            return str(configured_value)

        return getpass("Password: ")

    # Create Connection

    def create_connection(
        self, database_type: str, credentials: Dict[str, Any]
    ) -> None:

        if database_type == "PostgreSQL":
            from database_connectors.postgres import PostgreSQLConnector
            connector_class = PostgreSQLConnector
        elif database_type == "SQL Server":
            from database_connectors.sqlserver import SQLServerConnector
            connector_class = SQLServerConnector
        elif database_type == "Oracle":
            from database_connectors.oracle import OracleConnector
            connector_class = OracleConnector
        elif database_type == "MySQL":
            from database_connectors.mysql import MySQLConnector
            connector_class = MySQLConnector

        else:
            raise ValueError(f"Unsupported database: {database_type}")

        self.connector = connector_class(credentials)

        logger.info("Connecting to %s", database_type)

        self.connector.connect()

        logger.info("Connection successful")

    # Schemas

    def get_schemas(self) -> List[str]:

        if not self.connector:

            raise RuntimeError("Database is not connected.")

        return self.connector.get_schemas()

    # Tables

    def get_tables(self, schema_name: str) -> List[str]:

        if not self.connector:

            raise RuntimeError("Database is not connected.")

        return self.connector.get_tables(schema_name)

    # Data Dictionary

    def get_data_dictionary(
        self, schema_name: str, table_name: str
    ) -> List[Dict[str, Any]]:

        if not self.connector:

            raise RuntimeError("Database is not connected.")

        return self.connector.get_data_dictionary(schema_name, table_name)

    # Display Data Dictionary

    def display_table_metadata(self, metadata: List[Dict[str, Any]]) -> None:

        if not metadata:

            print("\nNo metadata found.")

            return

        print("\nDATA DICTIONARY")
        print("-" * 120)

        headers = [
            "Column",
            "Position",
            "Data Type",
            "Length",
            "Precision",
            "Scale",
            "Nullable",
            "Primary Key",
            "Default",
        ]

        print(
            f"{headers[0]:25} "
            f"{headers[1]:8} "
            f"{headers[2]:20} "
            f"{headers[3]:10} "
            f"{headers[4]:10} "
            f"{headers[5]:8} "
            f"{headers[6]:10} "
            f"{headers[7]:12} "
            f"{headers[8]:20}"
        )

        print("-" * 120)

        for row in metadata:

            print(
                f"{str(row['column_name']):25} "
                f"{str(row['column_position']):8} "
                f"{str(row['data_type']):20} "
                f"{str(row['character_length'] or '-'):10} "
                f"{str(row['numeric_precision'] or '-'):10} "
                f"{str(row['numeric_scale'] or '-'):8} "
                f"{str(row['nullable']):10} "
                f"{str(row['primary_key']):12} "
                f"{str(row['default_value'] or '-'):20}"
            )

    # Database Insights

    def get_unused_indexes(self, schema_name: str) -> List[Dict[str, Any]]:

        if not self.connector:
            raise RuntimeError("Database is not connected.")

        if self.database_type not in {
            "MySQL",
            "PostgreSQL",
            "SQL Server",
            "Oracle",
                    }:
            raise NotImplementedError(
                "Database insights are currently implemented for the supported databases only."
            )

        return self.connector.get_unused_indexes(schema_name)

    def get_tables_by_row_count(
        self, schema_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:

        if not self.connector:
            raise RuntimeError("Database is not connected.")

        return self.connector.get_tables_by_row_count(schema_name, limit)

    def get_tables_with_zero_indexes(self, schema_name: str) -> List[Dict[str, Any]]:

        if not self.connector:
            raise RuntimeError("Database is not connected.")

        return self.connector.get_tables_with_zero_indexes(schema_name)

    # -------------------------------------------------------------------------
    # CHART DATA METHODS & QUERIES
    # -------------------------------------------------------------------------

    def get_top_cpu_queries(self) -> Dict[str, Any]:
        """Retrieve top CPU-consuming queries for performance charts."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")
        if hasattr(self.connector, "get_top_cpu_queries"):
            return self.connector.get_top_cpu_queries()
        return {"available": False, "reason": "Not supported for this database engine.", "items": []}

    def get_top_io_activity(self) -> Dict[str, Any]:
        """Retrieve top I/O activity statistics for performance charts."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")
        if hasattr(self.connector, "get_top_io_activity"):
            return self.connector.get_top_io_activity()
        return {"available": False, "reason": "Not supported for this database engine.", "items": []}

    def get_top_wait_events(self) -> Dict[str, Any]:
        """Retrieve top wait events statistics for performance charts."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")
        if hasattr(self.connector, "get_top_wait_events"):
            return self.connector.get_top_wait_events()
        return {"available": False, "reason": "Not supported for this database engine.", "items": []}

    def get_cache_efficiency(self) -> Dict[str, Any]:
        """Retrieve buffer cache efficiency statistics for performance charts."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")
        if hasattr(self.connector, "get_cache_efficiency"):
            return self.connector.get_cache_efficiency()
        return {"available": False, "reason": "Not supported for this database engine.", "hit_ratio": 99.4, "miss_ratio": 0.6, "status": "Normal"}

    def get_data_vs_index_storage(self) -> List[Dict[str, Any]]:
        """Retrieve Data vs Index storage breakdown for charts."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")
        if hasattr(self.connector, "get_data_vs_index_storage"):
            return self.connector.get_data_vs_index_storage()
        return [{"label": "Data Size", "value": "0 MB"}, {"label": "Index Size", "value": "0 MB"}]

    def get_top_largest_tables(self) -> List[Dict[str, Any]]:
        """Retrieve top 10 largest tables for charts."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")
        if hasattr(self.connector, "get_top_largest_tables"):
            return self.connector.get_top_largest_tables()
        return []

    def display_insight_menu(self) -> str:

        print(f"\nDatabase : " f"{self.credentials.get('database', '-')}")

        print(f"Schema   : " f"{self.credentials.get('schema', '-')}")

        print("\nSelect an Insight:")
        print("1. Unused Indexes")
        print("2. Tables with More Rows")
        print("3. Tables with Zero Indexes")
        print("4. Exit (or 'q')")

        while True:
            try:
                choice = input("\nEnter your choice: ").strip()

                if choice in {"1", "2", "3", "4"}:
                    return choice
                if choice.lower() in {"q", "quit", "exit"}:
                    return "4"

                print("Invalid choice. Please select 1 to 4.")

            except KeyboardInterrupt:
                raise

    def _get_mysql_fetchers(self) -> List[tuple[str, Any]]:
        return [
            ("1. MySQL Version And Environment", self._get_mysql_environment_info_data),
            ("2. Database/Schema Inventory", self._get_mysql_database_count_data),
            ("3. Table-Level Storage Analysis", self._get_mysql_table_level_storage_analysis_data),
            ("4. Data Vs Index Storage", self._get_mysql_data_vs_index_footprint_data),
            ("5. Top 100 Largest Tables", self._get_mysql_top_100_largest_tables_data),
            ("6. Table Row Counts", self._get_mysql_row_counts_data),
            ("7. Storage By Engine", self._get_mysql_storage_by_engine_data),
            ("8. Check Tables That Aren't InnoDB", self._get_mysql_non_innodb_tables_data),
            ("9. Tables With Partitions And Detailed Partition Information", self._get_mysql_detailed_partitions_data),
            ("10. Master (Parent) Tables", self._get_mysql_master_tables_data),
            ("11. Child Tables", self._get_mysql_child_tables_data),
            ("12. Independent Tables", self._get_mysql_independent_tables_data),
            ("13. Identify Very Large Unpartitioned Tables", self._get_mysql_large_unpartitioned_tables_data),
            ("14. Find Very Large Columns", self._get_mysql_large_object_columns_data),
            ("15. Find JSON Columns", self._get_mysql_json_columns_data),
            ("16. Find Generated Columns", self._get_mysql_generated_columns_data),
            ("17. Primary Keys", self._get_mysql_primary_keys_data),
            ("18. Tables Without Primary Keys", self._get_mysql_without_primary_keys_data),
            ("19. All Indexes", self._get_mysql_index_sizes_data),
            ("20. Index Count By Table", self._get_mysql_high_index_count_data),
            ("21. Largest Indexes", self._get_mysql_largest_indexes_data),
            ("22. Foreign Keys / Relationships", self._get_mysql_foreign_keys_data),
            ("23. Tables With Many Foreign-Key Relationships", self._get_mysql_tables_many_foreign_keys_data),
            ("24. Unique Constraints", self._get_mysql_unique_constraints_data),
            ("25. Potential Duplicate Indexes", self._get_mysql_duplicate_indexes_data),
            ("26. Check AUTO_INCREMENT Information", self._get_mysql_auto_increment_columns_data),
            ("27. Find Tables With Different Collations", self._get_mysql_tables_different_collations_data),
            ("28. Tables With Comments / Documentation", self._get_mysql_table_comments_data),
            ("29. Stored Procedures", self._get_mysql_stored_procedures_data),
            ("30. Views", self._get_mysql_views_inventory_data),
            ("31. Triggers", self._get_mysql_triggers_inventory_data),
            ("32. Events / Scheduled Jobs", self._get_mysql_scheduled_events_data),
            ("33. Users And Privileges", self._get_mysql_user_accounts_data),
            ("34. InnoDB Buffer Pool", self._get_mysql_buffer_pool_data),
            ("35. Temporary Tables", self._get_mysql_temporary_tables_data),
            ("36. Connections", self._get_mysql_connections_data),
            ("37. Transaction Activity", self._get_mysql_active_transactions_data),
            ("38. Long-Running Transactions", self._get_mysql_long_running_transactions_data),
            ("39. Locks", self._get_mysql_locks_data),
            ("40. Deadlocks", self._get_mysql_deadlocks_data),
            ("41. Slow Queries", self._get_mysql_top_cpu_queries_data),
            ("42. Queries Examining Huge Amounts Of Data", self._get_mysql_high_examined_rows_data),
            ("43. Most Frequently Executed Queries", self._get_mysql_frequent_executed_queries_data),
            ("44. Table I/O Activity", self._get_mysql_table_io_activity_data),
            ("45. Table Wait Time", self._get_mysql_table_wait_times_data),
            ("46. Replication Status", self._get_mysql_replication_status_data),
            ("47. Binary Log Configuration", self._get_mysql_binlog_config_data),
            ("48. GTID", self._get_mysql_gtid_info_data),
            ("49. Binary Log Size", self._get_mysql_binary_logs_info_data),
            ("50. InnoDB Tablespaces", self._get_mysql_innodb_tablespaces_data),
            ("51. File-Per-Table Configuration", self._get_mysql_file_per_table_config_data),
            ("52. MySQL Data Directory", self._get_mysql_datadir_info_data),
            ("53. Identify Tables That Haven't Been Used", self._get_mysql_least_active_tables_data),
            ("54. Identify Hot Tables", self._get_mysql_hot_tables_data),
            ("55. Check Table Fragmentation", self._get_mysql_fragmentation_details_data),
            ("56. Foreign-Key Dependency Graph", self._get_mysql_foreign_key_graph_data),
            ("57. Stored Code Dependencies", self._get_mysql_stored_code_dependencies_data),
            ("58. Configuration Assessment", self._get_mysql_server_variables_data),
        ]

    def display_mysql_menu(self) -> str:
        print("\nMySQL Metadata Questions & Insights")
        print("-" * 60)
        fetchers = self._get_mysql_fetchers()
        for label, _ in fetchers:
            print(f"{label}")
        print("59. All Reports (Export PDF)")
        print("60. Exit (or 'q')")

        valid_choices = {str(i) for i in range(1, 61)}

        while True:
            try:
                choice = input("\nEnter your choice [1-60]: ").strip()

                if choice in valid_choices:
                    return choice
                if choice.lower() in {"q", "quit", "exit"}:
                    return "60"

                print("Invalid choice. Please select 1 to 60 (or 'q' to exit).")

            except KeyboardInterrupt:
                raise

    def _get_mysql_master_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_master_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "child_fk_count", "child_tables"],
        )
        return {
            "title": "9. Master (Parent) Tables",
            "headers": ["Database", "Master Table Name", "Child FKs In", "Referencing Child Tables"],
            "rows": formatted_rows,
            "note": "Tables referenced by foreign key constraints in child tables.",
        }

    def _get_mysql_child_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_child_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "parent_fk_count", "parent_tables"],
        )
        return {
            "title": "10. Child Tables",
            "headers": ["Database", "Child Table Name", "Parent FKs Out", "Referenced Parent Tables"],
            "rows": formatted_rows,
            "note": "Tables containing foreign key constraints pointing to parent tables.",
        }

    def _get_mysql_independent_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_independent_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name"],
        )
        return {
            "title": "11. Independent Tables",
            "headers": ["Database", "Independent Table Name"],
            "rows": formatted_rows,
            "note": "Standalone tables with no foreign key relationships (neither parent nor child).",
        }

    def _get_mysql_missing_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_missing_indexes()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "full_scans"]
        )
        return {
            "title": "Missing Indexes",
            "headers": ["Database", "Table", "Full Table Scans"],
            "rows": formatted_rows,
            "note": "Tables accessed via full table scans where indexes could improve performance.",
        }

    def _get_mysql_high_index_count_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_high_index_count()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "index_count"]
        )
        return {
            "title": "17. Index Count By Table",
            "headers": ["Database", "Table", "Index Count"],
            "rows": formatted_rows,
            "note": "Number of indexes per table from information_schema.statistics.",
        }

    def _get_mysql_without_clustered_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_without_clustered_indexes()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name"])
        return {
            "title": "Tables Without Clustered Indexes",
            "headers": ["Database", "Table"],
            "rows": formatted_rows,
            "note": "InnoDB tables defined without an explicit Primary Key (Clustered Index).",
        }

    def _get_mysql_without_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_without_indexes()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name"])
        return {
            "title": "Tables Without Indexes",
            "headers": ["Database", "Table"],
            "rows": formatted_rows,
            "note": "Base tables with zero index definitions.",
        }

    def _get_mysql_all_unused_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_all_unused_indexes()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "index_name", "columns", "read_count"]
        )
        return {
            "title": "Unused Indexes",
            "headers": ["Database", "Table", "Index", "Columns", "Read Count"],
            "rows": formatted_rows,
            "note": "Secondary indexes with zero recorded read operations.",
        }

    def _get_mysql_without_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_without_primary_keys()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name"])
        return {
            "title": "Tables Without Primary Keys",
            "headers": ["Database", "Table"],
            "rows": formatted_rows,
            "note": "Base tables created without a Primary Key constraint.",
        }

    def _get_mysql_top_cpu_queries_data(self) -> Dict[str, Any]:
        if hasattr(self.connector, "get_slow_queries"):
            rows = self.connector.get_slow_queries(limit=50)
        else:
            rows = self.connector.get_top_cpu_queries()
        formatted_rows = self._normalize_rows(
            rows, ["digest_text", "count_star", "total_seconds", "avg_seconds", "sum_rows_examined", "sum_rows_sent"]
        )
        return {
            "title": "Slow Queries",
            "headers": ["Digest Text", "Count Star", "Total Seconds", "Avg Seconds", "Sum Rows Examined", "Sum Rows Sent"],
            "rows": formatted_rows,
            "note": "Slow queries from performance_schema.events_statements_summary_by_digest ranked by wait time.",
        }

    def _get_mysql_top_heavy_write_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_heavy_write_tables()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "write_count", "write_time_sec"]
        )
        return {
            "title": "Top Heavy Write Tables",
            "headers": ["Database", "Table", "Write Count", "Write Time (s)"],
            "rows": formatted_rows,
            "note": "Top tables ranked by write operation activity.",
        }

    def _get_mysql_top_io_queries_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_io_queries()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "query_sample", "total_io_bytes", "exec_count"],
            size_columns={"total_io_bytes"},
        )
        return {
            "title": "Top I/O Intensive Queries",
            "headers": ["Database", "Query Sample", "Total I/O", "Exec Count"],
            "rows": formatted_rows,
            "note": "Top queries ranked by total byte read/write volume.",
        }

    def _get_mysql_partition_row_counts_data(self) -> Dict[str, Any]:
        rows = self.connector.get_partition_row_counts()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "partition_name", "row_count"]
        )
        return {
            "title": "Top Tables By Row Count And Partition",
            "headers": ["Database", "Table", "Partition Name", "Rows"],
            "rows": formatted_rows,
            "note": "Table partitions ordered by row count.",
        }

    def _get_mysql_large_varchar_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_varchar_columns()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "column_name", "data_type", "char_length"]
        )
        return {
            "title": "Large Varchar And Text Columns Tables",
            "headers": ["Database", "Table", "Column", "Data Type", "Max Length"],
            "rows": formatted_rows,
            "note": "Columns with large text or varchar definitions.",
        }

    def _get_mysql_fragmentation_details_data(self) -> Dict[str, Any]:
        rows = self.connector.get_fragmentation_details()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "data_size_bytes", "fragmented_bytes", "fragmentation_pct"],
            size_columns={"data_size_bytes", "fragmented_bytes"},
        )
        return {
            "title": "Fragmentation Details",
            "headers": ["Database", "Table", "Data Size", "Fragmented Space", "Fragmentation %"],
            "rows": formatted_rows,
            "note": "Tables with unused fragmented space (DATA_FREE).",
        }

    def _get_mysql_environment_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_environment_info()
        formatted_rows = self._normalize_rows(
            rows,
            ["mysql_version", "version_comment", "hostname", "port", "data_directory", "innodb_data_home_dir"],
        )
        return {
            "title": "MySQL Environment And Server Information",
            "headers": ["Version", "Comment", "Hostname", "Port", "Data Directory", "InnoDB Home"],
            "rows": formatted_rows,
            "note": "Environment and server configuration settings.",
        }

    def _get_mysql_database_sizes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_sizes()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "total_size_bytes"],
            size_columns={"total_size_bytes"},
        )
        return {
            "title": "Database Schema Sizes Inventory",
            "headers": ["Database Schema", "Total Size"],
            "rows": formatted_rows,
            "note": "Database storage sizes excluding system schemas.",
        }

    def _get_mysql_data_vs_index_footprint_data(self) -> Dict[str, Any]:
        rows = self.connector.get_data_vs_index_footprint()
        formatted_rows = self._normalize_rows(
            rows,
            ["data_mb", "index_mb", "total_mb", "data_gb", "index_gb", "total_gb", "data_tb", "index_tb", "total_tb"],
        )
        return {
            "title": "4. Data Vs Index Storage",
            "headers": ["Data (MB)", "Index (MB)", "Total (MB)", "Data (GB)", "Index (GB)", "Total (GB)", "Data (TB)", "Index (TB)", "Total (TB)"],
            "rows": formatted_rows,
            "note": "Aggregated data vs index footprint across non-system schemas.",
        }

    def _get_mysql_storage_by_engine_data(self) -> Dict[str, Any]:
        rows = self.connector.get_storage_by_engine()
        formatted_rows = self._normalize_rows(
            rows,
            ["engine_name", "table_count", "data_mb", "index_mb", "total_mb", "data_gb", "index_gb", "total_gb"],
        )
        return {
            "title": "6. Storage Breakdown By Storage Engine",
            "headers": ["Engine", "Table Count", "Data (MB)", "Index (MB)", "Total (MB)", "Data (GB)", "Index (GB)", "Total (GB)"],
            "rows": formatted_rows,
            "note": "Breakdown of storage across storage engines (InnoDB, MyISAM, etc.).",
        }

    def _get_mysql_non_innodb_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_non_innodb_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "engine_name", "size_mb", "size_gb"],
        )
        return {
            "title": "7. Check Tables That Aren't InnoDB",
            "headers": ["Database", "Table", "Engine", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Tables using non-InnoDB engines (MyISAM, MEMORY, CSV, etc.).",
        }

    def _get_mysql_detailed_partitions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_detailed_partitions()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "partition_name", "partition_method", "partition_expression", "row_count", "data_size_bytes", "index_size_bytes"],
            size_columns={"data_size_bytes", "index_size_bytes"},
        )
        return {
            "title": "Detailed Partition Configuration And Sizes",
            "headers": ["Database", "Table", "Partition", "Method", "Expression", "Rows", "Data Size", "Index Size"],
            "rows": formatted_rows,
            "note": "Partition mapping and individual partition storage details.",
        }

    def _get_mysql_large_unpartitioned_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_unpartitioned_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "size_mb", "size_gb"],
        )
        return {
            "title": "9. Identify Very Large Unpartitioned Tables",
            "headers": ["Database", "Table", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Unpartitioned tables sorted by total size for partitioning review.",
        }

    def _get_mysql_large_object_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_object_columns()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "column_name", "data_type", "column_type"],
        )
        return {
            "title": "BLOB And TEXT Large Object Columns",
            "headers": ["Database", "Table", "Column", "Data Type", "Column Type"],
            "rows": formatted_rows,
            "note": "Columns with BLOB, TEXT, or LONGTEXT data types.",
        }

    def _get_mysql_json_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_json_columns()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "column_name", "column_type"],
        )
        return {
            "title": "JSON Data Type Columns Inventory",
            "headers": ["Database", "Table", "Column", "Column Type"],
            "rows": formatted_rows,
            "note": "Columns explicitly defined with JSON data type.",
        }

    def _get_mysql_generated_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_generated_columns()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "column_name", "generation_expression"],
        )
        return {
            "title": "13. Find Generated Columns",
            "headers": ["Database", "Table", "Column Name", "Generation Expression"],
            "rows": formatted_rows,
            "note": "Generated and virtual column definitions from information_schema.columns.",
        }

    def _get_mysql_auto_increment_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_auto_increment_columns()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "column_name", "column_type", "extra_info"],
        )
        return {
            "title": "AUTO_INCREMENT Column Specifications",
            "headers": ["Database", "Table", "Column", "Column Type", "Specification"],
            "rows": formatted_rows,
            "note": "Auto-increment primary keys and surrogate identifier columns.",
        }

    def _get_mysql_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_primary_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "primary_key_columns"],
        )
        return {
            "title": "Primary Keys Inventory",
            "headers": ["Database", "Table", "Primary Key Columns"],
            "rows": formatted_rows,
            "note": "Tables with defined PRIMARY KEY constraints.",
        }

    def _get_mysql_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_foreign_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "constraint_name", "column_name", "ref_schema", "ref_table", "ref_column", "ordinal_position"],
        )
        return {
            "title": "19. Foreign Key Constraints",
            "headers": ["Database", "Table", "Constraint", "Column", "Ref Database", "Ref Table", "Ref Column", "Pos"],
            "rows": formatted_rows,
            "note": "Foreign key referential relationships from information_schema.key_column_usage.",
        }

    def _get_mysql_tables_many_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_many_foreign_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "foreign_key_count"],
        )
        return {
            "title": "Tables Labeled By High Foreign Key Dependencies",
            "headers": ["Database", "Table", "Foreign Keys Count"],
            "rows": formatted_rows,
            "note": "Tables ordered by foreign key reference density.",
        }

    def _get_mysql_unique_constraints_data(self) -> Dict[str, Any]:
        rows = self.connector.get_unique_constraints()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "index_name", "unique_columns"],
        )
        return {
            "title": "Unique Constraints And Indexes",
            "headers": ["Database", "Table", "Index Name", "Unique Columns"],
            "rows": formatted_rows,
            "note": "Enforced unique constraint indexes.",
        }

    def _get_mysql_tables_different_collations_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_with_different_collations()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_collation", "table_count"],
        )
        return {
            "title": "Find Tables With Different Collations",
            "headers": ["Database Schema", "Table Collation", "Table Count"],
            "rows": formatted_rows,
            "note": "Distribution of table collation settings across schemas.",
        }

    def _get_mysql_table_comments_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_comments()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "table_comment"],
        )
        return {
            "title": "Table Comments And Documentation",
            "headers": ["Database", "Table", "Comment / Description"],
            "rows": formatted_rows,
            "note": "Documented table comments in schema metadata.",
        }

    def _get_mysql_stored_procedures_data(self) -> Dict[str, Any]:
        rows = self.connector.get_stored_procedures()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "routine_name", "routine_type", "return_type", "created_time", "last_altered"],
        )
        return {
            "title": "Stored Procedures And Routines Inventory",
            "headers": ["Database", "Routine Name", "Type", "Return Type", "Created", "Last Altered"],
            "rows": formatted_rows,
            "note": "Programmability routines (PROCEDURE / FUNCTION).",
        }

    def _get_mysql_views_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_views_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "view_name"],
        )
        return {
            "title": "Database Views Inventory",
            "headers": ["Database", "View Name"],
            "rows": formatted_rows,
            "note": "Logical views defined in schema metadata.",
        }

    def _get_mysql_triggers_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_triggers_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "trigger_schema",
                "trigger_name",
                "event_object_schema",
                "event_object_table",
                "event_manipulation",
                "action_timing",
                "action_statement",
            ],
        )
        return {
            "title": "Database Triggers Inventory",
            "headers": [
                "Trigger Schema",
                "Trigger Name",
                "Target Schema",
                "Target Table",
                "Event Manipulation",
                "Action Timing",
                "Action Statement",
            ],
            "rows": formatted_rows,
            "note": "Event-driven database triggers details.",
        }

    def _get_mysql_scheduled_events_data(self) -> Dict[str, Any]:
        rows = self.connector.get_scheduled_events()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "event_schema",
                "event_name",
                "status",
                "event_type",
                "execute_at",
                "interval_value",
                "interval_field",
                "last_executed",
            ],
        )
        return {
            "title": "Scheduled Events Inventory",
            "headers": [
                "Event Schema",
                "Event Name",
                "Status",
                "Event Type",
                "Execute At",
                "Interval Value",
                "Interval Field",
                "Last Executed",
            ],
            "rows": formatted_rows,
            "note": "MySQL Event Scheduler background tasks inventory.",
        }

    def _get_mysql_user_accounts_data(self) -> Dict[str, Any]:
        rows = self.connector.get_user_accounts()
        formatted_rows = self._normalize_rows(
            rows,
            ["user_name", "host_name", "plugin_name", "account_locked", "password_expired"],
        )
        return {
            "title": "Database User Accounts And Security Inventory",
            "headers": ["User", "Host", "Plugin", "Account Locked", "Password Expired"],
            "rows": formatted_rows,
            "note": "User authentication accounts configured in mysql.user.",
        }

    def _get_mysql_active_transactions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_active_transactions()
        formatted_rows = self._normalize_rows(
            rows,
            ["transaction_id", "started_time", "duration_sec", "state", "rows_locked", "rows_modified"],
        )
        return {
            "title": "Active InnoDB Transactions",
            "headers": ["Trx ID", "Started", "Duration (s)", "State", "Rows Locked", "Rows Modified"],
            "rows": formatted_rows,
            "note": "Currently executing transactions in InnoDB.",
        }

    def _get_mysql_high_examined_rows_data(self) -> Dict[str, Any]:
        rows = self.connector.get_high_examined_rows_queries(limit=50)
        formatted_rows = self._normalize_rows(
            rows,
            ["digest_text", "count_star", "sum_rows_examined", "sum_rows_sent", "avg_rows_examined"],
        )
        return {
            "title": "Top Queries Examining Huge Row Volumes",
            "headers": ["Digest Text", "Count Star", "Sum Rows Examined", "Sum Rows Sent", "Avg Rows Examined"],
            "rows": formatted_rows,
            "note": "Queries reading high numbers of rows relative to output from performance_schema.events_statements_summary_by_digest.",
        }

    def _get_mysql_server_variables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_server_variables()
        formatted_rows = self._normalize_rows(rows, ["var_name", "var_value"])
        return {
            "title": "MySQL Key System Configuration Variables",
            "headers": ["Variable Name", "Setting Value"],
            "rows": formatted_rows,
            "note": "Engine, memory, connection, and binlog configuration parameters.",
        }

    def _get_mysql_column_collations_data(self) -> Dict[str, Any]:
        rows = self.connector.get_column_collations()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "column_name", "char_set", "collation_name"]
        )
        return {
            "title": "Column Level Character Sets And Collations",
            "headers": ["Database", "Table", "Column", "Character Set", "Collation"],
            "rows": formatted_rows,
            "note": "Column-level character set and collation audit.",
        }

    def _get_mysql_schema_privileges_data(self) -> Dict[str, Any]:
        rows = self.connector.get_schema_privileges()
        formatted_rows = self._normalize_rows(
            rows, ["grantee", "schema_name", "privilege_type"]
        )
        return {
            "title": "Database Schema Privileges Inventory",
            "headers": ["Grantee User", "Database Schema", "Privilege Granted"],
            "rows": formatted_rows,
            "note": "Granted schema privileges across users.",
        }

    def _get_mysql_schema_privileges_data(self) -> Dict[str, Any]:
        rows = self.connector.get_schema_privileges()
        formatted_rows = self._normalize_rows(
            rows, ["grantee", "schema_name", "privilege_type"]
        )
        return {
            "title": "Database Schema Privileges Inventory",
            "headers": ["Grantee User", "Database Schema", "Privilege Granted"],
            "rows": formatted_rows,
            "note": "Granted schema privileges across users.",
        }

    def _get_mysql_buffer_pool_data(self) -> Dict[str, Any]:
        rows = self.connector.get_buffer_pool_status()
        formatted_rows = self._normalize_rows(rows, ["setting_type", "metric_name", "setting_value"])
        return {
            "title": "InnoDB Buffer Pool Configuration And Status",
            "headers": ["Type", "Metric / Variable Name", "Value"],
            "rows": formatted_rows,
            "note": "InnoDB buffer pool variables and runtime status metrics.",
        }

    def _get_mysql_temporary_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_temporary_tables_status()
        formatted_rows = self._normalize_rows(rows, ["metric_name", "metric_value"])
        return {
            "title": "Temporary Tables Global Status Metrics",
            "headers": ["Metric Name", "Metric Value"],
            "rows": formatted_rows,
            "note": "Created_tmp_tables, Created_tmp_disk_tables, and Created_tmp_files metrics.",
        }

    def _get_mysql_connections_data(self) -> Dict[str, Any]:
        rows = self.connector.get_connection_thread_status()
        formatted_rows = self._normalize_rows(rows, ["metric_name", "metric_value"])
        return {
            "title": "Connections And Thread Activity Status",
            "headers": ["Metric / Variable Name", "Value"],
            "rows": formatted_rows,
            "note": "Threads connected, Threads running, and max_connections settings.",
        }

    def _get_mysql_locks_data(self) -> Dict[str, Any]:
        rows = self.connector.get_data_locks()
        formatted_rows = self._normalize_rows(
            rows, ["lock_id", "schema_name", "table_name", "lock_type", "lock_mode", "lock_status", "lock_data"]
        )
        return {
            "title": "Active Data Locks And Lock Waits",
            "headers": ["Lock ID", "Database", "Table", "Type", "Mode", "Status", "Lock Data"],
            "rows": formatted_rows,
            "note": "Currently held locks and waiting transactions in performance_schema.data_locks.",
        }

    def _get_mysql_deadlocks_data(self) -> Dict[str, Any]:
        rows = self.connector.get_deadlocks_info()
        formatted_rows = self._normalize_rows(rows, ["metric_name", "status_details"])
        return {
            "title": "41. Deadlocks",
            "headers": ["Metric / Event", "Details / Value"],
            "rows": formatted_rows,
            "note": "innodb_print_all_deadlocks setting and LATEST DETECTED DEADLOCK status.",
        }

    def _get_mysql_replication_status_data(self) -> Dict[str, Any]:
        rows = self.connector.get_replication_status()
        formatted_rows = self._normalize_rows(rows, ["role", "status_info"])
        return {
            "title": "47. Replication Status",
            "headers": ["Node Role", "Replication State"],
            "rows": formatted_rows,
            "note": "Source/Primary and Replica thread status.",
        }

    def _get_mysql_binlog_config_data(self) -> Dict[str, Any]:
        rows = self.connector.get_binlog_config()
        formatted_rows = self._normalize_rows(rows, ["variable_name", "setting_value"])
        return {
            "title": "48. Binary Log Configuration",
            "headers": ["Configuration Variable", "Value"],
            "rows": formatted_rows,
            "note": "log_bin, binlog_format, expire_logs, max_binlog_size.",
        }

    def _get_mysql_gtid_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_gtid_info()
        formatted_rows = self._normalize_rows(rows, ["property_name", "property_value"])
        return {
            "title": "49. GTID",
            "headers": ["GTID Property", "Value"],
            "rows": formatted_rows,
            "note": "Global Transaction Identifier configuration and executed GTID sets.",
        }

    def _get_mysql_file_per_table_config_data(self) -> Dict[str, Any]:
        rows = self.connector.get_file_per_table_config()
        formatted_rows = self._normalize_rows(rows, ["setting_name", "setting_value"])
        return {
            "title": "53. File-Per-Table Configuration",
            "headers": ["Setting", "Value"],
            "rows": formatted_rows,
            "note": "innodb_file_per_table setting.",
        }

    def _get_mysql_datadir_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_datadir_info()
        formatted_rows = self._normalize_rows(rows, ["setting_name", "setting_value"])
        return {
            "title": "54. MySQL Data Directory",
            "headers": ["Directory Setting", "Path"],
            "rows": formatted_rows,
            "note": "Datadir path.",
        }

    def _get_mysql_foreign_key_graph_data(self) -> Dict[str, Any]:
        rows = self.connector.get_foreign_keys()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "column_name", "ref_schema", "ref_table", "ref_column"]
        )
        return {
            "title": "58. Foreign-Key Dependency Graph",
            "headers": ["Database", "Child Table", "Child Column", "Ref Database", "Parent Table", "Parent Column"],
            "rows": formatted_rows,
            "note": "Referential dependency graph for migration sequencing.",
        }

    def _get_mysql_top_100_largest_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_100_largest_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "engine_name", "data_mb", "index_mb", "total_mb", "total_gb"]
        )
        return {
            "title": "5. Top 100 Largest Tables",
            "headers": ["Database", "Table", "Engine", "Data Size (MB)", "Index Size (MB)", "Total Size (MB)", "Total Size (GB)"],
            "rows": formatted_rows,
            "note": "Top 100 largest tables ordered by total storage size.",
        }

    def _get_mysql_largest_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_largest_indexes()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "index_mb", "index_gb"]
        )
        return {
            "title": "18. Largest Indexes",
            "headers": ["Database", "Table", "Index Size (MB)", "Index Size (GB)"],
            "rows": formatted_rows,
            "note": "Top 100 tables with largest index storage overhead.",
        }

    def _get_mysql_duplicate_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_duplicate_indexes()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "index_columns", "duplicate_count", "indexes"]
        )
        return {
            "title": "22. Potential Duplicate Indexes",
            "headers": ["Database", "Table", "Index Columns", "Count", "Duplicate Indexes"],
            "rows": formatted_rows,
            "note": "Tables with multiple indexes covering the exact same sequence of columns.",
        }

    def _get_mysql_long_running_transactions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_long_running_transactions()
        formatted_rows = self._normalize_rows(
            rows, ["transaction_id", "started_time", "duration_seconds", "state", "tables_locked", "rows_locked", "rows_modified"]
        )
        return {
            "title": "39. Long-Running Transactions",
            "headers": ["Trx ID", "Started", "Duration (s)", "State", "Tables Locked", "Rows Locked", "Rows Modified"],
            "rows": formatted_rows,
            "note": "InnoDB active transactions ordered by oldest start time.",
        }

    def _get_mysql_table_io_activity_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_io_activity()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "count_read", "count_write", "count_fetch", "count_insert", "count_update", "count_delete"]
        )
        return {
            "title": "45. Table I/O Activity",
            "headers": ["Database", "Table", "Reads", "Writes", "Fetches", "Inserts", "Updates", "Deletes"],
            "rows": formatted_rows,
            "note": "Top 100 tables ranked by total read and write I/O activity.",
        }

    def _get_mysql_frequent_executed_queries_data(self) -> Dict[str, Any]:
        rows = self.connector.get_frequent_executed_queries(limit=50)
        formatted_rows = self._normalize_rows(
            rows, ["digest_text", "count_star", "avg_ms"]
        )
        return {
            "title": "Most Frequently Executed Queries",
            "headers": ["Digest Text", "Count Star", "Avg Time (ms)"],
            "rows": formatted_rows,
            "note": "Queries with highest cumulative execution count from performance_schema.events_statements_summary_by_digest.",
        }

    def _get_mysql_table_wait_times_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_wait_times()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "total_ops", "wait_sec"]
        )
        return {
            "title": "46. Table Wait Time",
            "headers": ["Database", "Table", "Total Ops", "Wait Time (s)"],
            "rows": formatted_rows,
            "note": "Tables experiencing highest total I/O wait latency.",
        }

    def _get_mysql_binary_logs_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_binary_logs_info()
        formatted_rows = self._normalize_rows(
            rows, ["log_name", "file_size"], size_columns={"file_size"}
        )
        return {
            "title": "50. Binary Log Size",
            "headers": ["Log File Name", "File Size"],
            "rows": formatted_rows,
            "note": "Replication binary log files recorded on server.",
        }

    def _get_mysql_innodb_tablespaces_data(self) -> Dict[str, Any]:
        rows = self.connector.get_innodb_tablespaces()
        formatted_rows = self._normalize_rows(
            rows,
            ["space_id", "tablespace_name", "space_type", "row_format", "state"],
        )
        return {
            "title": "51. InnoDB Tablespaces",
            "headers": ["Space ID", "Tablespace Name", "Space Type", "Row Format", "State"],
            "rows": formatted_rows,
            "note": "InnoDB tablespaces inventory from information_schema.innodb_tablespaces.",
        }

    def _get_mysql_least_active_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_least_active_tables()
        formatted_rows = self._normalize_rows(
            rows, ["schema_name", "table_name", "count_read", "count_write", "total_ops"]
        )
        return {
            "title": "59. Identify Tables That Haven't Been Used",
            "headers": ["Database", "Table", "Reads", "Writes", "Total I/O Ops"],
            "rows": formatted_rows,
            "note": "Tables with zero recorded read and write operations (completely unused) for obsolescence assessment.",
        }

    def _get_mysql_hot_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_hot_tables(limit=100)
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "count_read", "count_write", "count_insert", "count_update", "count_delete", "total_ops"],
        )
        return {
            "title": "60. Identify Hot Tables",
            "headers": ["Database", "Table", "Reads", "Writes", "Inserts", "Updates", "Deletes", "Total I/O Ops"],
            "rows": formatted_rows,
            "note": "Top active workload tables ranked by total read/write I/O operations.",
        }

    def _get_mysql_stored_code_dependencies_data(self) -> Dict[str, Any]:
        routines = self.connector.get_stored_procedures()
        triggers = self.connector.get_triggers_inventory()
        events = self.connector.get_scheduled_events()
        views = self.connector.get_views_inventory()
        summary_rows = [
            ["Stored Procedures & Functions", str(len(routines))],
            ["Database Triggers", str(len(triggers))],
            ["Scheduled Events", str(len(events))],
            ["Database Views", str(len(views))],
        ]
        return {
            "title": "59. Stored Code Dependencies",
            "headers": ["Programmability Object", "Total Count"],
            "rows": summary_rows,
            "note": "Stored procedures, triggers, events, and views dependency inventory.",
        }

    def _get_mysql_table_level_storage_analysis_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_level_storage_analysis()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "engine_name", "table_rows", "data_mb", "index_mb", "total_mb", "data_gb", "index_gb", "total_gb"]
        )
        return {
            "title": "3. Table-Level Storage Analysis",
            "headers": ["Database", "Table", "Engine", "Rows", "Data (MB)", "Index (MB)", "Total (MB)", "Data (GB)", "Index (GB)", "Total (GB)"],
            "rows": formatted_rows,
            "note": "All tables by size ordered by (data_length + index_length) DESC.",
        }

    def _show_mysql_all_reports(self) -> None:
        """Collect all 58 MySQL metadata reports strictly following document sequence and generate PDF report."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")

        import time
        fetch_start = time.time()

        reports_data = []
        fetchers = self._get_mysql_fetchers()

        for label, fetcher in fetchers:
            print(f" -> Gathering data: {label}...")
            try:
                data = fetcher()
                data["title"] = label
                reports_data.append(data)
            except Exception as e:
                logger.error("Error gathering data for %s: %s", label, e)

        fetch_time = time.time() - fetch_start

        print("\n -> Building PDF document...")

        # Generate & Auto-Open PDF Report
        try:
            import os
            import sys
            from pdf_generator import PDFReportGenerator

            pdf_start = time.time()
            pdf_gen = PDFReportGenerator()
            pdf_path = pdf_gen.generate_report(
                reports_data,
                database_name="MySQL",
                credentials_info=self.credentials,
            )
            pdf_build_time = time.time() - pdf_start
            total_elapsed = time.time() - fetch_start

            print("\n" + "=" * 80)
            print(" SUCCESS: ALL 58 REPORTS EXPORTED TO PDF!")
            print(f" PDF File Saved At: {pdf_path}")
            print(f" Time Taken to Fetch Data from DB: {fetch_time:.2f} seconds")
            print(f" Time Taken to Build PDF Document: {pdf_build_time:.2f} seconds")
            print(f" Total Process Time: {total_elapsed:.2f} seconds")
            print("=" * 80)
            logger.info("PDF report saved to %s (took %.2fs)", pdf_path, total_elapsed)

            # Auto-open PDF file in system viewer
            if hasattr(os, "startfile"):
                os.startfile(str(pdf_path))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(pdf_path)])
            elif sys.platform.startswith("linux"):
                import subprocess
                subprocess.run(["xdg-open", str(pdf_path)])

        except Exception as exc:
            logger.error("Failed to generate PDF report: %s", exc)
            print(f"\n[Error] Could not generate PDF report: {exc}")

    def run_mysql_insights(self) -> None:
        fetchers = self._get_mysql_fetchers()
        while True:
            choice = self.display_mysql_menu()

            if choice == "60":
                print("\nExiting MySQL metadata questions.")
                break
            elif choice == "59":
                self._show_mysql_all_reports()
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(fetchers):
                        label, fetcher = fetchers[idx]
                        data = fetcher()
                        self._show_paginated_table_report(
                            label, data.get("headers", []), data.get("rows", []), note=data.get("note")
                        )
                except Exception as e:
                    print(f"Error displaying insight: {e}")

    def _get_oracle_fetchers(self) -> List[tuple[str, Any]]:
        return [
            ("1. Oracle Version And Environment", self._get_oracle_environment_info_data),
            ("2. Schema Inventory", self._get_oracle_schema_inventory_data),
            ("3. Schema/Table Storage Analysis", self._get_oracle_schema_table_storage_analysis_data),
            ("4. Total Data Vs Index Storage", self._get_oracle_total_data_vs_index_storage_data),
            ("5. Top 100 Largest Segments", self._get_oracle_top_100_largest_segments_data),
            ("6. Table Row Counts / Statistics", self._get_oracle_table_row_counts_stats_data),
            ("7. Tablespace Usage", self._get_oracle_tablespace_usage_data),
            ("8. Tablespace Free Space", self._get_oracle_tablespace_free_space_data),
            ("9. Datafiles", self._get_oracle_datafiles_inventory_data),
            ("10. Master (Parent) Tables", self._get_oracle_master_tables_data),
            ("11. Child Tables", self._get_oracle_child_tables_data),
            ("12. Independent Tables", self._get_oracle_independent_tables_data),
            ("13. Large Unpartitioned Tables", self._get_oracle_large_unpartitioned_tables_data),
            ("14. Partition Inventory", self._get_oracle_partition_inventory_data),
            ("15. Detailed Partition Information", self._get_oracle_detailed_partition_info_data),
            ("16. Large Object Columns", self._get_oracle_large_object_columns_data),
            ("17. JSON-Related Columns", self._get_oracle_json_columns_data),
            ("18. Primary Keys", self._get_oracle_primary_keys_data),
            ("19. Tables Without Primary Keys", self._get_oracle_without_primary_keys_data),
            ("20. All Indexes", self._get_oracle_all_indexes_data),
            ("21. Index Columns", self._get_oracle_index_columns_data),
            ("22. Index Count By Table", self._get_oracle_index_count_by_table_data),
            ("23. Largest Indexes", self._get_oracle_largest_indexes_data),
            ("24. Foreign Keys / Relationships", self._get_oracle_foreign_keys_data),
            ("25. Detailed Foreign-Key Columns", self._get_oracle_detailed_foreign_key_columns_data),
            ("26. Tables With Many Foreign-Key Relationships", self._get_oracle_tables_many_foreign_keys_data),
            ("27. Unique Constraints", self._get_oracle_unique_constraints_data),
            ("28. Duplicate/Redundant Index Candidates", self._get_oracle_duplicate_index_candidates_data),
            ("29. Character Sets And Collations", self._get_oracle_charsets_and_collations_data),
            ("30. Tables With Comments / Documentation", self._get_oracle_table_comments_data),
            ("31. Stored Procedures", self._get_oracle_stored_procedures_data),
            ("32. Functions", self._get_oracle_functions_data),
            ("33. Packages", self._get_oracle_packages_data),
            ("34. Views", self._get_oracle_views_data),
            ("35. Triggers", self._get_oracle_triggers_data),
            ("36. Scheduled Jobs", self._get_oracle_scheduled_jobs_data),
            ("37. Users And Privileges", self._get_oracle_users_and_privileges_data),
            ("38. Tablespace And Segment Status", self._get_oracle_tablespace_and_segment_status_data),
            ("39. SGA / Memory Configuration", self._get_oracle_sga_memory_config_data),
            ("40. PGA Configuration And Usage", self._get_oracle_pga_config_usage_data),
            ("41. Temporary Tablespace Usage", self._get_oracle_temp_tablespace_usage_data),
            ("42. Sessions And Connections", self._get_oracle_sessions_and_connections_data),
            ("43. Long-Running Sessions", self._get_oracle_long_running_sessions_data),
            ("44. Locks", self._get_oracle_locks_data),
            ("45. Blocking Sessions", self._get_oracle_blocking_sessions_data),
            ("46. Slow / Resource-Intensive SQL", self._get_oracle_slow_sql_data),
            ("47. SQL Examining Large Amounts Of Data", self._get_oracle_large_data_examination_sql_data),
            ("48. Most Frequently Executed SQL", self._get_oracle_frequently_executed_sql_data),
            ("49. Top Wait Events", self._get_oracle_top_wait_events_data),
            ("50. Database Time / Load Profile", self._get_oracle_database_time_load_profile_data),
            ("51. Data Guard / Database Role", self._get_oracle_dataguard_db_role_data),
            ("52. Archive Log Configuration", self._get_oracle_archive_log_config_data),
            ("53. Archive Log Generation", self._get_oracle_archive_log_generation_data),
            ("54. Redo Generation", self._get_oracle_redo_generation_data),
            ("55. Undo Configuration And Usage", self._get_oracle_undo_config_usage_data),
            ("56. Oracle Datafiles / Physical Layout", self._get_oracle_datafiles_physical_layout_data),
            ("57. ASM Disk Group Capacity", self._get_oracle_asm_diskgroup_capacity_data),
            ("58. Database Files And Storage", self._get_oracle_database_files_storage_data),
            ("59. Identify Archival Candidates", self._get_oracle_archival_candidates_data),
            ("60. Identify Tables With Limited Usage", self._get_oracle_limited_usage_tables_data),
            ("61. Identify Hot Tables / Objects", self._get_oracle_hot_tables_objects_data),
            ("62. Segment Space / Fragmentation Candidates", self._get_oracle_fragmentation_candidates_data),
            ("63. Foreign-Key Dependency Graph", self._get_oracle_foreign_key_dependency_graph_data),
            ("64. Stored Code Dependencies", self._get_oracle_stored_code_dependencies_data),
            ("65. Configuration Assessment", self._get_oracle_configuration_assessment_data),
        ]

    def display_oracle_menu(self) -> str:
        print("\nOracle Metadata Questions & Insights")
        print("-" * 60)
        fetchers = self._get_oracle_fetchers()
        for label, _ in fetchers:
            print(f"{label}")
        print("66. All Reports (Export PDF)")
        print("67. Exit (or 'q')")

        valid_choices = {str(i) for i in range(1, 68)}

        while True:
            try:
                choice = input("\nEnter your choice [1-67]: ").strip()

                if choice in valid_choices:
                    return choice
                if choice.lower() in {"q", "quit", "exit"}:
                    return "67"

                print("Invalid choice. Please select 1 to 67 (or 'q' to exit).")

            except KeyboardInterrupt:
                raise

    def _show_oracle_all_reports(self) -> None:
        """Collect all 65 Oracle metadata reports strictly following document sequence and generate PDF report."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")

        import time
        fetch_start = time.time()

        reports_data = []
        fetchers = self._get_oracle_fetchers()

        for label, fetcher in fetchers:
            print(f" -> Gathering data: {label}...")
            try:
                data = fetcher()
                data["title"] = label
                reports_data.append(data)
            except Exception as e:
                logger.error("Error gathering data for %s: %s", label, e)

        fetch_time = time.time() - fetch_start

        print("\n -> Building PDF document...")

        try:
            import os
            import sys
            from pdf_generator import PDFReportGenerator

            pdf_start = time.time()
            pdf_gen = PDFReportGenerator()
            pdf_path = pdf_gen.generate_report(
                reports_data,
                database_name="Oracle",
                credentials_info=self.credentials,
            )
            pdf_build_time = time.time() - pdf_start
            total_elapsed = time.time() - fetch_start

            print("\n" + "=" * 80)
            print(" SUCCESS: ALL 65 REPORTS EXPORTED TO PDF!")
            print(f" PDF File Saved At: {pdf_path}")
            print(f" Time Taken to Fetch Data from DB: {fetch_time:.2f} seconds")
            print(f" Time Taken to Build PDF Document: {pdf_build_time:.2f} seconds")
            print(f" Total Process Time: {total_elapsed:.2f} seconds")
            print("=" * 80)
            logger.info("PDF report saved to %s (took %.2fs)", pdf_path, total_elapsed)

            if hasattr(os, "startfile"):
                os.startfile(str(pdf_path))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(pdf_path)])
            elif sys.platform.startswith("linux"):
                import subprocess
                subprocess.run(["xdg-open", str(pdf_path)])

        except Exception as exc:
            logger.error("Failed to generate PDF report: %s", exc)
            print(f"\n[Error] Could not generate PDF report: {exc}")

    def run_oracle_insights(self) -> None:
        fetchers = self._get_oracle_fetchers()
        while True:
            choice = self.display_oracle_menu()

            if choice == "67":
                print("\nExiting Oracle metadata questions.")
                break
            elif choice == "66":
                self._show_oracle_all_reports()
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(fetchers):
                        label, fetcher = fetchers[idx]
                        data = fetcher()
                        self._show_paginated_table_report(
                            label, data.get("headers", []), data.get("rows", []), note=data.get("note")
                        )
                except Exception as e:
                    print(f"Error displaying insight: {e}")


    def _get_postgres_fetchers(self) -> List[tuple[str, Any]]:
        return [
            ("1. PostgreSQL Version And Environment", self._get_postgres_environment_info_data),
            ("2. Database Inventory", self._get_postgres_database_inventory_data),
            ("3. Schema/Table Storage Analysis", self._get_postgres_schema_table_storage_analysis_data),
            ("4. Total Table Vs Index Storage", self._get_postgres_total_table_vs_index_storage_data),
            ("5. Top 100 Tables", self._get_postgres_top_100_largest_relations_data),
            ("6. Tablespace Usage", self._get_postgres_tablespace_usage_data),
            ("7. Tablespace Object Storage", self._get_postgres_tablespace_object_storage_data),
            ("8. Database Files / Physical Layout", self._get_postgres_database_files_data),
            ("9. Master (Parent) Tables", self._get_postgres_master_tables_data),
            ("10. Child Tables", self._get_postgres_child_tables_data),
            ("11. Independent Tables", self._get_postgres_independent_tables_data),
            ("12. Large Unpartitioned Tables", self._get_postgres_large_unpartitioned_tables_data),
            ("13. Partition Inventory", self._get_postgres_partition_inventory_data),
            ("14. Detailed Partition Information", self._get_postgres_detailed_partition_info_data),
            ("15. Large Object Columns", self._get_postgres_large_object_columns_data),
            ("16. JSON / JSONB Columns", self._get_postgres_json_columns_data),
            ("17. Primary Keys", self._get_postgres_primary_keys_data),
            ("18. Tables Without Primary Keys", self._get_postgres_tables_without_primary_keys_data),
            ("19. All Indexes", self._get_postgres_all_indexes_data),
            ("20. Index Columns", self._get_postgres_index_columns_data),
            ("21. Index Count By Table", self._get_postgres_index_count_by_table_data),
            ("22. Largest Indexes", self._get_postgres_largest_indexes_data),
            ("23. Foreign Keys / Relationships", self._get_postgres_foreign_keys_data),
            ("24. Tables With Many Foreign-Key Relationships", self._get_postgres_tables_many_foreign_keys_data),
            ("25. Unique Constraints", self._get_postgres_unique_constraints_data),
            ("26. Duplicate/Redundant Index Candidates", self._get_postgres_duplicate_index_candidates_data),
            ("27. Character Sets And Collations", self._get_postgres_character_sets_and_collations_data),
            ("28. Tables With Comments / Documentation", self._get_postgres_table_comments_data),
            ("29. Stored Procedures", self._get_postgres_stored_procedures_data),
            ("30. Functions", self._get_postgres_functions_data),
            ("31. Views", self._get_postgres_views_data),
            ("32. Triggers", self._get_postgres_triggers_data),
            ("33. Scheduled Jobs", self._get_postgres_scheduled_jobs_data),
            ("34. Users And Roles", self._get_postgres_users_and_roles_data),
            ("35. Tablespace Status And Configuration", self._get_postgres_tablespace_status_data),
            ("36. Shared Memory / Memory Configuration", self._get_postgres_memory_configuration_data),
            ("37. Memory And Cache Statistics", self._get_postgres_memory_cache_statistics_data),
            ("38. Temporary File Usage", self._get_postgres_temp_file_usage_data),
            ("39. Sessions And Connections", self._get_postgres_sessions_and_connections_data),
            ("40. Long-Running Sessions / Queries", self._get_postgres_long_running_sessions_data),
            ("41. Locks", self._get_postgres_locks_data),
            ("42. Blocking Sessions", self._get_postgres_blocking_sessions_data),
            ("43. Slow / Resource-Intensive SQL", self._get_postgres_slow_sql_data),
            ("44. SQL Examining / Reading Large Amounts Of Data", self._get_postgres_large_data_examination_sql_data),
            ("45. Most Frequently Executed SQL", self._get_postgres_frequently_executed_sql_data),
            ("46. Top Wait Events", self._get_postgres_top_wait_events_data),
            ("47. Database Workload / Activity Profile", self._get_postgres_database_activity_profile_data),
            ("48. Replication / Database Role", self._get_postgres_replication_status_data),
            ("49. WAL / Archive Configuration", self._get_postgres_wal_archive_configuration_data),
            ("50. WAL Generation", self._get_postgres_wal_generation_data),
            ("51. WAL / Checkpoint Activity", self._get_postgres_wal_checkpoint_activity_data),
            ("52. Transaction ID / Vacuum Health", self._get_postgres_transaction_vacuum_health_data),
            ("53. PostgreSQL Data Directory / Physical Layout", self._get_postgres_physical_layout_data),
            ("54. Tablespace Locations", self._get_postgres_storage_capacity_data),
            ("55. Database Object Storage Summary", self._get_postgres_database_storage_summary_data),
            ("56. Identify Archival Candidates", self._get_postgres_archival_candidates_data),
            ("57. Identify Tables With Limited Usage", self._get_postgres_tables_with_limited_usage_data),
            ("58. Identify Hot Tables / Objects", self._get_postgres_hot_tables_data),
            ("59. Table Bloat / Vacuum Candidates", self._get_postgres_table_bloat_candidates_data),
            ("60. Stored Code / Object Dependencies", self._get_postgres_stored_code_dependencies_data),
            ("61. Configuration Assessment", self._get_postgres_configuration_assessment_data),
        ]

    def display_postgres_menu(self) -> str:
        print("\nPostgreSQL Metadata Questions & Insights")
        print("-" * 60)
        fetchers = self._get_postgres_fetchers()
        for label, _ in fetchers:
            print(f"{label}")
        print("62. All Reports (Export PDF)")
        print("63. Exit (or 'q')")

        valid_choices = {str(i) for i in range(1, 64)}

        while True:
            try:
                choice = input("\nEnter your choice [1-63]: ").strip()

                if choice in valid_choices:
                    return choice
                if choice.lower() in {"q", "quit", "exit"}:
                    return "63"

                print("Invalid choice. Please select 1 to 63 (or 'q' to exit).")

            except KeyboardInterrupt:
                raise

    def _show_postgres_all_reports(self) -> None:
        """Collect all 61 PostgreSQL metadata reports strictly following document sequence and generate PDF report."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")

        import time
        fetch_start = time.time()

        reports_data = []
        fetchers = self._get_postgres_fetchers()

        for label, fetcher in fetchers:
            print(f" -> Gathering data: {label}...")
            try:
                data = fetcher()
                data["title"] = label
                reports_data.append(data)
            except Exception as e:
                logger.error("Error gathering data for %s: %s", label, e)

        fetch_time = time.time() - fetch_start

        print("\n -> Building PDF document...")

        try:
            import os
            import sys
            from pdf_generator import PDFReportGenerator

            pdf_start = time.time()
            pdf_gen = PDFReportGenerator()
            pdf_path = pdf_gen.generate_report(
                reports_data,
                database_name="PostgreSQL",
                credentials_info=self.credentials,
            )
            pdf_build_time = time.time() - pdf_start
            total_elapsed = time.time() - fetch_start

            print("\n" + "=" * 80)
            print(" SUCCESS: ALL 61 REPORTS EXPORTED TO PDF!")
            print(f" PDF File Saved At: {pdf_path}")
            print(f" Time Taken to Fetch Data from DB: {fetch_time:.2f} seconds")
            print(f" Time Taken to Build PDF Document: {pdf_build_time:.2f} seconds")
            print(f" Total Process Time: {total_elapsed:.2f} seconds")
            print("=" * 80)
            logger.info("PDF report saved to %s (took %.2fs)", pdf_path, total_elapsed)

            if hasattr(os, "startfile"):
                os.startfile(str(pdf_path))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(pdf_path)])
            elif sys.platform.startswith("linux"):
                import subprocess
                subprocess.run(["xdg-open", str(pdf_path)])

        except Exception as exc:
            logger.error("Failed to generate PDF report: %s", exc)
            print(f"\n[Error] Could not generate PDF report: {exc}")

    def run_postgres_insights(self) -> None:
        fetchers = self._get_postgres_fetchers()
        while True:
            choice = self.display_postgres_menu()

            if choice == "63":
                print("\nExiting PostgreSQL metadata questions.")
                break
            elif choice == "62":
                self._show_postgres_all_reports()
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(fetchers):
                        label, fetcher = fetchers[idx]
                        data = fetcher()
                        self._show_paginated_table_report(
                            label, data.get("headers", []), data.get("rows", []), note=data.get("note")
                        )
                except Exception as e:
                    print(f"Error displaying insight: {e}")

    def _get_postgres_environment_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_environment_info()
        formatted_rows = self._normalize_rows(
            rows,
            ["postgres_version", "server_version", "database_name", "server_address", "port", "current_user"],
        )
        return {
            "title": "1. PostgreSQL Version And Environment",
            "headers": ["PostgreSQL Version", "Server Version", "Database", "Server Address", "Port", "Current User"],
            "rows": formatted_rows,
            "note": "PostgreSQL server, database, connection and version information.",
        }

    def _get_postgres_database_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "owner", "size_mb", "size_gb"],
        )
        if rows:
            total_mb = sum(float(r.get("size_mb", 0) or 0) for r in rows)
            total_gb = round(total_mb / 1024.0, 2)

            total_row = [
                "TOTAL",
                "-",
                f"{round(total_mb, 2):.2f}",
                f"{total_gb:.2f}",
            ]
            formatted_rows.append(total_row)

        return {
            "title": "2. Database Inventory",
            "headers": ["Database Name", "Owner", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Databases visible to the current PostgreSQL cluster with their sizes.",
        }

    def _get_postgres_schema_table_storage_analysis_data(self) -> Dict[str, Any]:
        rows = self.connector.get_schema_table_storage_analysis()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "size_mb", "size_gb"],
        )
        return {
            "title": "3. Schema/Table Storage Analysis",
            "headers": ["Schema", "Table Name", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Table storage analysis (including indexes and TOAST).",
        }

    def _get_postgres_total_table_vs_index_storage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_total_table_vs_index_storage()
        if rows:
            sum_table_mb = sum(float(r.get("table_mb", 0) or 0) for r in rows)
            sum_index_mb = sum(float(r.get("index_mb", 0) or 0) for r in rows)
            sum_total_mb = sum(float(r.get("total_mb", 0) or 0) for r in rows)

            sum_table_gb = round(sum_table_mb / 1024.0, 2)
            sum_index_gb = round(sum_index_mb / 1024.0, 2)
            sum_total_gb = round(sum_total_mb / 1024.0, 2)

            single_row = [{
                "table_mb": f"{sum_table_mb:.2f}",
                "index_mb": f"{sum_index_mb:.2f}",
                "total_mb": f"{sum_total_mb:.2f}",
                "table_gb": f"{sum_table_gb:.2f}",
                "index_gb": f"{sum_index_gb:.2f}",
                "total_gb": f"{sum_total_gb:.2f}",
            }]
        else:
            single_row = []

        formatted_rows = self._normalize_rows(
            single_row,
            ["table_mb", "index_mb", "total_mb", "table_gb", "index_gb", "total_gb"],
        )
        return {
            "title": "4. Total Table Vs Index Storage",
            "headers": [
                "Table Storage (MB)",
                "Index Storage (MB)",
                "Total Storage (MB)",
                "Table Storage (GB)",
                "Index Storage (GB)",
                "Total Storage (GB)",
            ],
            "rows": formatted_rows,
            "note": "Database-wide table heap, index and total relation storage.",
        }

    def _get_postgres_top_100_largest_relations_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_100_largest_relations()
        rows.sort(
            key=lambda r: (
                int(r.get("row_count") if r.get("row_count") is not None else 0),
                float(r.get("size_mb") if r.get("size_mb") is not None else 0),
            ),
            reverse=True,
        )
        rows = rows[:100]
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "relation_name", "relation_type", "row_count", "size_mb", "size_gb"],
        )
        return {
            "title": "5. Top 100 Tables",
            "headers": ["Database", "Schema", "Table Name", "Relation Type", "Row Count", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Top 100 largest user tables/partitioned tables by row count.",
        }

    def _get_postgres_tablespace_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tablespace_usage()
        formatted_rows = self._normalize_rows(
            rows,
            ["tablespace_name", "owner", "location", "size_gb"],
        )
        return {
            "title": "6. Tablespace Usage",
            "headers": ["Tablespace Name", "Owner", "Location", "Size (GB)"],
            "rows": formatted_rows,
            "note": "PostgreSQL tablespaces and the size of objects stored in each.",
        }

    def _get_postgres_tablespace_object_storage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tablespace_object_storage()
        formatted_rows = self._normalize_rows(
            rows,
            ["tablespace_name", "object_count", "total_size_gb"],
        )
        return {
            "title": "7. Tablespace Object Storage",
            "headers": ["Tablespace Name", "Object Count", "Total Object Size (GB)"],
            "rows": formatted_rows,
            "note": "Object storage assigned to each PostgreSQL tablespace, including objects that inherit the current database's default tablespace.",
        }

    def _get_postgres_database_files_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_files()
        formatted_rows = self._normalize_rows(
            rows,
            ["tablespace_name", "location"],
        )
        return {
            "title": "8. Database Files / Physical Layout",
            "headers": ["Database File / Tablespace", "Location"],
            "rows": formatted_rows,
            "note": "PostgreSQL exposes data directories and tablespace locations rather than Oracle-style DBA_DATA_FILES.",
        }

    def _get_postgres_master_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_master_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "child_fk_count", "child_tables"],
        )
        return {
            "title": "9. Master (Parent) Tables",
            "headers": ["Schema", "Parent Table", "Child FK Count", "Referencing Child Tables"],
            "rows": formatted_rows,
            "note": "Tables referenced by foreign-key constraints.",
        }

    def _get_postgres_child_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_child_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "parent_fk_count", "parent_tables"],
        )
        return {
            "title": "10. Child Tables",
            "headers": ["Schema", "Child Table", "Parent FK Count", "Referenced Parent Tables"],
            "rows": formatted_rows,
            "note": "Tables containing foreign keys referencing parent tables.",
        }

    def _get_postgres_independent_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_independent_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name"],
        )
        return {
            "title": "11. Independent Tables",
            "headers": ["Schema", "Table Name"],
            "rows": formatted_rows,
            "note": "Tables with no incoming or outgoing foreign-key relationships.",
        }

    def _get_postgres_large_unpartitioned_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_unpartitioned_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "size_mb", "size_gb"],
        )
        return {
            "title": "12. Large Unpartitioned Tables",
            "headers": ["Schema", "Table Name", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Large tables that are not partitioned, for partitioning review.",
        }

    def _get_postgres_partition_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_partition_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "partition_count"],
        )
        return {
            "title": "13. Partition Inventory",
            "headers": ["Schema", "Parent Table", "Partition Count"],
            "rows": formatted_rows,
            "note": "Partitioned tables and their child partition counts.",
        }

    def _get_postgres_detailed_partition_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_detailed_partition_info()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "parent_table", "partition_name", "partition_bound"],
        )
        return {
            "title": "14. Detailed Partition Information",
            "headers": ["Schema", "Parent Table", "Partition Name", "Partition Bound"],
            "rows": formatted_rows,
            "note": "Partition hierarchy and partition bounds.",
        }

    def _get_postgres_large_object_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_object_columns()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "column_name", "data_type"],
        )
        return {
            "title": "15. Large Object Columns",
            "headers": ["Schema", "Table Name", "Column Name", "Data Type"],
            "rows": formatted_rows,
            "note": "Columns using PostgreSQL large-value types such as bytea, text and XML.",
        }

    def _get_postgres_json_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_json_columns()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "column_name", "data_type"],
        )
        return {
            "title": "16. JSON / JSONB Columns",
            "headers": ["Schema", "Table Name", "Column Name", "Data Type"],
            "rows": formatted_rows,
            "note": "Columns explicitly defined with PostgreSQL json or jsonb data types.",
        }

    def _get_postgres_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_primary_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "constraint_name", "definition"],
        )
        return {
            "title": "17. Primary Keys",
            "headers": ["Schema", "Table Name", "Constraint Name", "Definition"],
            "rows": formatted_rows,
            "note": "Primary-key constraints and their definitions.",
        }

    def _get_postgres_tables_without_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_without_primary_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name"],
        )
        return {
            "title": "18. Tables Without Primary Keys",
            "headers": ["Schema", "Table Name"],
            "rows": formatted_rows,
            "note": "User tables without an explicit primary-key constraint.",
        }

    def _get_postgres_all_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_all_indexes()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "index_name", "idx_scan", "size_mb", "size_gb"],
        )
        return {
            "title": "19. All Indexes",
            "headers": ["Schema", "Table Name", "Index Name", "Index Scans", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "PostgreSQL index inventory and status.",
        }

    def _get_postgres_index_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_columns()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "index_name", "column_position", "column_name"],
        )
        return {
            "title": "20. Index Columns",
            "headers": ["Schema", "Table Name", "Index Name", "Column Position", "Column Name"],
            "rows": formatted_rows,
            "note": "Columns and positions used by each index.",
        }

    def _get_postgres_index_count_by_table_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_count_by_table()
        rows.sort(
            key=lambda r: int(r.get("index_count") if r.get("index_count") is not None else 0),
            reverse=True,
        )
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_count"],
        )
        return {
            "title": "21. Index Count By Table",
            "headers": ["Database", "Schema", "Table Name", "Index Count"],
            "rows": formatted_rows,
            "note": "Number of indexes defined on each user table.",
        }

    def _get_postgres_largest_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_largest_indexes()
        rows.sort(
            key=lambda r: float(r.get("size_mb") if r.get("size_mb") is not None else 0),
            reverse=True,
        )
        rows = rows[:100]
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_name", "size_mb", "size_gb"],
        )
        return {
            "title": "22. Largest Indexes",
            "headers": ["Database", "Schema", "Table Name", "Index Name", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Largest user indexes by physical size.",
        }

    def _get_postgres_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_foreign_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "constraint_name", "definition"],
        )
        return {
            "title": "23. Foreign Keys / Relationships",
            "headers": ["Database", "Schema", "Table Name", "Constraint Name", "Definition"],
            "rows": formatted_rows,
            "note": "Foreign-key relationship inventory.",
        }

    def _get_postgres_tables_many_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_many_foreign_keys()
        rows.sort(
            key=lambda r: int(r.get("foreign_key_count") if r.get("foreign_key_count") is not None else 0),
            reverse=True,
        )
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "foreign_key_count"],
        )
        return {
            "title": "24. Tables With Many Foreign-Key Relationships",
            "headers": ["Database", "Schema", "Table Name", "Foreign Key Count"],
            "rows": formatted_rows,
            "note": "Tables with many foreign-key constraints.",
        }

    def _get_postgres_unique_constraints_data(self) -> Dict[str, Any]:
        rows = self.connector.get_unique_constraints()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "constraint_name", "definition"],
        )
        return {
            "title": "25. Unique Constraints",
            "headers": ["Schema", "Table Name", "Constraint Name", "Definition"],
            "rows": formatted_rows,
            "note": "Unique constraints inventory.",
        }

    def _get_postgres_duplicate_index_candidates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_duplicate_index_candidates()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "index_a", "index_b", "definition"],
        )
        return {
            "title": "26. Duplicate/Redundant Index Candidates",
            "headers": ["Schema", "Table Name", "Index A", "Index B", "Definition"],
            "rows": formatted_rows,
            "note": "Candidate duplicate indexes with the same normalized CREATE INDEX definition.",
        }

    def _get_postgres_character_sets_and_collations_data(self) -> Dict[str, Any]:
        rows = self.connector.get_character_sets_and_collations()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "database_encoding", "server_encoding", "lc_collate", "lc_ctype"],
        )
        return {
            "title": "27. Character Sets And Collations",
            "headers": ["Database Name", "Database Encoding", "Server Encoding", "LC_COLLATE", "LC_CTYPE"],
            "rows": formatted_rows,
            "note": "Current database encoding and locale configuration.",
        }

    def _get_postgres_table_comments_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_comments()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "comments"],
        )
        return {
            "title": "28. Tables With Comments / Documentation",
            "headers": ["Schema", "Table Name", "Comments"],
            "rows": formatted_rows,
            "note": "Table comments stored in PostgreSQL catalog.",
        }

    def _get_postgres_stored_procedures_data(self) -> Dict[str, Any]:
        rows = self.connector.get_stored_procedures()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "procedure_name", "language", "owner", "definition"],
        )
        return {
            "title": "29. Stored Procedures",
            "headers": ["Schema", "Procedure Name", "Language", "Owner", "Definition"],
            "rows": formatted_rows,
            "note": "Procedures created with CREATE PROCEDURE.",
        }

    def _get_postgres_functions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_functions()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "function_name", "return_type", "language", "volatility"],
        )
        return {
            "title": "30. Functions",
            "headers": ["Schema", "Function Name", "Return Type", "Language", "Volatility"],
            "rows": formatted_rows,
            "note": "PostgreSQL functions inventory.",
        }

    def _get_postgres_views_data(self) -> Dict[str, Any]:
        rows = self.connector.get_views()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "view_name", "definition", "object_type"],
        )
        return {
            "title": "31. Views",
            "headers": ["Schema", "View Name", "Definition", "Object Type"],
            "rows": formatted_rows,
            "note": "Regular and materialized view inventory.",
        }

    def _get_postgres_triggers_data(self) -> Dict[str, Any]:
        rows = self.connector.get_triggers()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "trigger_name", "definition"],
        )
        return {
            "title": "32. Triggers",
            "headers": ["Schema", "Table Name", "Trigger Name", "Definition"],
            "rows": formatted_rows,
            "note": "Table trigger inventory.",
        }

    def _get_postgres_scheduled_jobs_data(self) -> Dict[str, Any]:
        rows = self.connector.get_scheduled_jobs()
        formatted_rows = self._normalize_rows(
            rows,
            ["job_name", "schedule", "active", "command", "database"],
        )
        return {
            "title": "33. Scheduled Jobs",
            "headers": ["Job Name", "Schedule", "Active", "Command", "Database"],
            "rows": formatted_rows,
            "note": "PostgreSQL pg_cron scheduled jobs inventory.",
        }

    def _get_postgres_users_and_roles_data(self) -> Dict[str, Any]:
        rows = self.connector.get_users_and_roles()
        formatted_rows = self._normalize_rows(
            rows,
            ["role_name", "is_superuser", "can_create_database", "can_create_role", "can_login", "replication_role", "connection_limit", "valid_until"],
        )
        return {
            "title": "34. Users And Roles",
            "headers": ["Role Name", "Superuser", "Create DB", "Create Role", "Login", "Replication", "Connection Limit", "Valid Until"],
            "rows": formatted_rows,
            "note": "PostgreSQL role/account configuration.",
        }

    def _get_postgres_tablespace_status_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tablespace_status()
        formatted_rows = self._normalize_rows(
            rows,
            ["tablespace_name", "owner", "location"],
        )
        return {
            "title": "35. Tablespace Status And Configuration",
            "headers": ["Tablespace Name", "Owner", "Location"],
            "rows": formatted_rows,
            "note": "PostgreSQL tablespace definitions and physical locations.",
        }

    def _get_postgres_memory_configuration_data(self) -> Dict[str, Any]:
        rows = self.connector.get_memory_configuration()
        formatted_rows = self._normalize_rows(
            rows,
            ["parameter", "setting", "unit"],
        )
        return {
            "title": "36. Shared Memory / Memory Configuration",
            "headers": ["Parameter", "Setting", "Unit"],
            "rows": formatted_rows,
            "note": "PostgreSQL memory-related configuration such as shared_buffers and work_mem.",
        }

    def _get_postgres_memory_cache_statistics_data(self) -> Dict[str, Any]:
        rows = self.connector.get_memory_cache_statistics()
        formatted_rows = self._normalize_rows(
            rows,
            ["metric", "value"],
        )
        return {
            "title": "37. Memory And Cache Statistics",
            "headers": ["Metric", "Value"],
            "rows": formatted_rows,
            "note": "PostgreSQL cache-hit and backend activity statistics.",
        }

    def _get_postgres_temp_file_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_temp_file_usage()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "temp_files", "size_mb", "size_gb", "temp_bytes"],
        )
        return {
            "title": "38. Temporary File Usage",
            "headers": ["Database", "Temp Files", "Size (MB)", "Size (GB)", "Pretty Size"],
            "rows": formatted_rows,
            "note": "Temporary-file generation by database (only databases with active temp file usage are displayed).",
        }

    def _get_postgres_sessions_and_connections_data(self) -> Dict[str, Any]:
        rows = self.connector.get_sessions_and_connections()
        formatted_rows = self._normalize_rows(
            rows,
            ["state", "session_count"],
        )
        return {
            "title": "39. Sessions And Connections",
            "headers": ["State", "Session Count"],
            "rows": formatted_rows,
            "note": "Current PostgreSQL backend sessions grouped by state.",
        }

    def _get_postgres_long_running_sessions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_long_running_sessions()
        formatted_rows = self._normalize_rows(
            rows,
            ["pid", "username", "database_name", "state", "duration", "wait_event_type", "wait_event", "query_sample"],
        )
        return {
            "title": "40. Long-Running Sessions / Queries",
            "headers": ["PID", "User", "Database", "State", "Duration", "Wait Type", "Wait Event", "Query Sample"],
            "rows": formatted_rows,
            "note": "Active sessions running for at least five minutes.",
        }

    def _get_postgres_locks_data(self) -> Dict[str, Any]:
        rows = self.connector.get_locks()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "pid",
                "locktype",
                "mode",
                "granted",
                "relation",
                "transaction_id",
                "lock_category",
                "fastpath",
                "username",
                "database_name",
            ],
        )
        return {
            "title": "41. Locks",
            "headers": [
                "PID",
                "Lock Type",
                "Mode",
                "Granted",
                "Relation",
                "Transaction ID",
                "Lock Category",
                "Fast Path",
                "User",
                "Database",
            ],
            "rows": formatted_rows,
            "note": "Current locks held or awaited by PostgreSQL sessions, including default VirtualXID and catalog locks.",
        }

    def _get_postgres_blocking_sessions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_blocking_sessions()
        formatted_rows = self._normalize_rows(
            rows,
            ["blocked_pid", "blocking_pid", "blocked_user", "blocking_user", "blocked_duration", "blocked_query", "blocking_query"],
        )
        return {
            "title": "42. Blocking Sessions",
            "headers": ["Blocked PID", "Blocking PID", "Blocked User", "Blocking User", "Blocked Duration", "Blocked Query", "Blocking Query"],
            "rows": formatted_rows,
            "note": "Sessions waiting for locks held by other sessions.",
        }

    def _get_postgres_slow_sql_data(self) -> Dict[str, Any]:
        rows = self.connector.get_slow_sql()
        formatted_rows = self._normalize_rows(
            rows,
            ["queryid", "calls", "total_seconds", "mean_ms", "rows", "query_sample"],
        )
        return {
            "title": "43. Slow / Resource-Intensive SQL",
            "headers": ["Query ID", "Calls", "Total Sec", "Mean (ms)", "Rows", "Query Sample"],
            "rows": formatted_rows,
            "note": "Top SQL statements by cumulative execution time.",
        }

    def _get_postgres_large_data_examination_sql_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_data_examination_sql()
        formatted_rows = self._normalize_rows(
            rows,
            ["queryid", "calls", "shared_blks_read", "temp_blks_read", "rows", "query_sample"],
        )
        return {
            "title": "44. SQL Examining / Reading Large Amounts Of Data",
            "headers": ["Query ID", "Calls", "Shared Blks Read", "Temp Blks Read", "Rows", "Query Sample"],
            "rows": formatted_rows,
            "note": "SQL statements responsible for high block-read activity.",
        }

    def _get_postgres_frequently_executed_sql_data(self) -> Dict[str, Any]:
        rows = self.connector.get_frequently_executed_sql()
        formatted_rows = self._normalize_rows(
            rows,
            ["queryid", "calls", "total_seconds", "query_sample"],
        )
        return {
            "title": "45. Most Frequently Executed SQL",
            "headers": ["Query ID", "Calls", "Total Sec", "Query Sample"],
            "rows": formatted_rows,
            "note": "SQL statements ranked by execution count.",
        }

    def _get_postgres_top_wait_events_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_wait_events()
        formatted_rows = self._normalize_rows(
            rows,
            ["wait_event_type", "wait_event", "active_sessions"],
        )
        return {
            "title": "46. Top Wait Events",
            "headers": ["Wait Event Type", "Wait Event", "Active Sessions"],
            "rows": formatted_rows,
            "note": "Current sessions waiting on PostgreSQL wait events.",
        }

    def _get_postgres_database_activity_profile_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_activity_profile()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "xact_commit", "xact_rollback", "blks_read", "blks_hit", "tup_returned", "tup_fetched", "tup_inserted", "tup_updated", "tup_deleted", "temp_bytes"],
        )
        return {
            "title": "47. Database Workload / Activity Profile",
            "headers": ["Database", "Commits", "Rollbacks", "Blks Read", "Blks Hit", "Tup Returned", "Tup Fetched", "Inserts", "Updates", "Deletes", "Temp Bytes"],
            "rows": formatted_rows,
            "note": "High-level workload and I/O activity by database.",
        }

    def _get_postgres_replication_status_data(self) -> Dict[str, Any]:
        rows = self.connector.get_replication_status()
        formatted_rows = self._normalize_rows(
            rows,
            ["is_in_recovery", "database_role", "current_or_replay_wal_lsn", "replication_sessions"],
        )
        return {
            "title": "48. Replication / Database Role",
            "headers": ["In Recovery", "Database Role", "WAL LSN", "Replication Sessions"],
            "rows": formatted_rows,
            "note": "PostgreSQL recovery and replication state.",
        }

    def _get_postgres_wal_archive_configuration_data(self) -> Dict[str, Any]:
        rows = self.connector.get_wal_archive_configuration()
        formatted_rows = self._normalize_rows(
            rows,
            ["parameter", "setting"],
        )
        return {
            "title": "49. WAL / Archive Configuration",
            "headers": ["Parameter", "Setting"],
            "rows": formatted_rows,
            "note": "WAL and archive-related configuration.",
        }

    def _get_postgres_wal_generation_data(self) -> Dict[str, Any]:
        rows = self.connector.get_wal_generation()
        if rows and isinstance(rows[0], dict):
            keys = list(rows[0].keys())
            headers = [k.replace("_", " ").title() for k in keys]
            formatted_rows = self._normalize_rows(rows, keys)
        else:
            keys = ["wal_records", "wal_fpi", "wal_bytes", "wal_buffers_full"]
            headers = ["WAL Records", "WAL FPI", "WAL Bytes", "Buffers Full"]
            formatted_rows = self._normalize_rows(rows, keys)
        return {
            "title": "50. WAL Generation",
            "headers": headers,
            "rows": formatted_rows,
            "note": "Cumulative WAL generation statistics.",
        }

    def _get_postgres_wal_checkpoint_activity_data(self) -> Dict[str, Any]:
        rows = self.connector.get_wal_checkpoint_activity()
        formatted_rows = self._normalize_rows(
            rows,
            ["checkpoints_timed", "checkpoints_req", "checkpoint_write_time", "checkpoint_sync_time", "buffers_checkpoint"],
        )
        return {
            "title": "51. WAL / Checkpoint Activity",
            "headers": ["Timed Checkpoints", "Req Checkpoints", "Write Time", "Sync Time", "Buffers Checkpoint"],
            "rows": formatted_rows,
            "note": "Checkpoint activity.",
        }

    def _get_postgres_transaction_vacuum_health_data(self) -> Dict[str, Any]:
        rows = self.connector.get_transaction_vacuum_health()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "frozen_xid_age"],
        )
        return {
            "title": "52. Transaction ID / Vacuum Health",
            "headers": ["Database", "Frozen XID Age"],
            "rows": formatted_rows,
            "note": "Transaction-ID age and vacuum-related risk indicators.",
        }

    def _get_postgres_physical_layout_data(self) -> Dict[str, Any]:
        rows = self.connector.get_physical_layout()
        formatted_rows = self._normalize_rows(
            rows,
            ["data_directory", "config_file", "hba_file", "ident_file"],
        )
        return {
            "title": "53. PostgreSQL Data Directory / Physical Layout",
            "headers": ["Data Directory", "Config File", "HBA File", "Ident File"],
            "rows": formatted_rows,
            "note": "Important PostgreSQL physical and configuration file locations.",
        }

    def _get_postgres_storage_capacity_data(self) -> Dict[str, Any]:
        rows = self.connector.get_storage_capacity()
        formatted_rows = self._normalize_rows(
            rows,
            ["tablespace_name", "location"],
        )
        return {
            "title": "54. Tablespace Locations",
            "headers": ["Tablespace Name", "Location"],
            "rows": formatted_rows,
            "note": "PostgreSQL tablespace locations.",
        }

    def _get_postgres_database_storage_summary_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_storage_summary()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "database_name",
                "relation_count",
                "table_mb",
                "index_mb",
                "total_mb",
                "table_gb",
                "index_gb",
                "total_gb",
            ],
        )
        return {
            "title": "55. Database Object Storage Summary",
            "headers": [
                "Database",
                "Relation Count",
                "Table Size (MB)",
                "Index Size (MB)",
                "Total Size (MB)",
                "Table Size (GB)",
                "Index Size (GB)",
                "Total Size (GB)",
            ],
            "rows": formatted_rows,
            "note": "Current database storage summary for user tables and indexes.",
        }

    def _get_postgres_archival_candidates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_archival_candidates()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "estimated_rows", "last_analyze", "last_autoanalyze", "total_size_gb"],
        )
        return {
            "title": "56. Identify Archival Candidates",
            "headers": ["Schema", "Table Name", "Estimated Rows", "Last Analyze", "Last Autoanalyze", "Total Size (GB)"],
            "rows": formatted_rows,
            "note": "Candidate tables for archival review based on estimated row count and physical size.",
        }

    def _get_postgres_tables_with_limited_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_with_limited_usage()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "seq_scan", "idx_scan", "total_scans", "seq_tup_read", "idx_tup_fetch"],
        )
        return {
            "title": "57. Identify Tables With Limited Usage",
            "headers": ["Schema", "Table Name", "Seq Scans", "Index Scans", "Total Scans", "Seq Tup Read", "Index Tup Fetch"],
            "rows": formatted_rows,
            "note": "Tables with low observed access activity.",
        }

    def _get_postgres_hot_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_hot_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "seq_scan", "idx_scan", "inserts", "updates", "deletes", "total_scans"],
        )
        return {
            "title": "58. Identify Hot Tables / Objects",
            "headers": ["Schema", "Table Name", "Seq Scans", "Index Scans", "Inserts", "Updates", "Deletes", "Total Scans"],
            "rows": formatted_rows,
            "note": "Tables with high observed read/write activity.",
        }

    def _get_postgres_table_bloat_candidates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_bloat_candidates()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "live_tuples", "dead_tuples", "dead_tuple_pct", "last_vacuum", "last_autovacuum"],
        )
        return {
            "title": "59. Table Bloat / Vacuum Candidates",
            "headers": ["Schema", "Table Name", "Live Tuples", "Dead Tuples", "Dead Tuple %", "Last Vacuum", "Last Autovacuum"],
            "rows": formatted_rows,
            "note": "Tables with dead tuples and potentially overdue vacuum activity.",
        }

    def _get_postgres_stored_code_dependencies_data(self) -> Dict[str, Any]:
        rows = self.connector.get_stored_code_dependencies()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "object_name", "object_type", "referenced_object"],
        )
        return {
            "title": "60. Stored Code / Object Dependencies",
            "headers": ["Schema", "Object Name", "Object Type", "Referenced Object"],
            "rows": formatted_rows,
            "note": "Dependency relationships for views, materialized views, functions and procedures.",
        }

    def _get_postgres_configuration_assessment_data(self) -> Dict[str, Any]:
        rows = self.connector.get_configuration_assessment()
        formatted_rows = self._normalize_rows(
            rows,
            ["parameter_name", "setting", "unit", "description"],
        )
        return {
            "title": "61. Configuration Assessment",
            "headers": ["Parameter Name", "Setting", "Unit", "Description"],
            "rows": formatted_rows,
            "note": "Key PostgreSQL server configuration parameters.",
        }


    def _get_sqlserver_fetchers(self) -> List[tuple[str, Any]]:
        return [
            ("1. Server Environment", self._get_sqlserver_server_environment_data),
            ("2. Database Inventory", self._get_sqlserver_database_inventory_data),
            ("3. Database File Configuration", self._get_sqlserver_database_file_configuration_data),
            ("4. Data Vs Log Storage", self._get_sqlserver_data_vs_log_storage_data),
            ("5. Database Free Space", self._get_sqlserver_database_free_space_data),
            ("6. Top 100 Largest Tables", self._get_sqlserver_largest_tables_data),
            ("7. Schema Inventory", self._get_sqlserver_schema_inventory_data),
            ("8. Master (Parent) Tables", self._get_sqlserver_master_tables_data),
            ("9. Child Tables", self._get_sqlserver_child_tables_data),
            ("10. Independent Tables", self._get_sqlserver_independent_tables_data),
            ("11. Table Inventory", self._get_sqlserver_table_inventory_data),
            ("12. Primary Keys", self._get_sqlserver_primary_keys_data),
            ("13. Tables Without Primary Keys", self._get_sqlserver_tables_without_primary_keys_data),
            ("14. Foreign Keys", self._get_sqlserver_foreign_keys_data),
            ("15. Tables With Many Foreign Keys", self._get_sqlserver_tables_with_many_foreign_keys_data),
            ("16. Index Inventory", self._get_sqlserver_index_inventory_data),
            ("17. Index Count By Table", self._get_sqlserver_index_count_by_table_data),
            ("18. Largest Indexes", self._get_sqlserver_largest_indexes_data),
            ("19. Disabled Indexes", self._get_sqlserver_disabled_indexes_data),
            ("20. Fragmented Indexes", self._get_sqlserver_fragmented_indexes_data),
            ("21. Index Usage", self._get_sqlserver_index_usage_data),
            ("22. Duplicate Or Overlapping Indexes", self._get_sqlserver_duplicate_or_overlapping_indexes_data),
            ("23. Missing Index Recommendations", self._get_sqlserver_missing_index_recommendations_data),
            ("24. Views", self._get_sqlserver_views_data),
            ("25. Stored Procedures", self._get_sqlserver_stored_procedures_data),
            ("26. Functions", self._get_sqlserver_functions_data),
            ("27. Triggers", self._get_sqlserver_triggers_data),
            ("28. Object Dependencies", self._get_sqlserver_object_dependencies_data),
            ("29. Database Roles", self._get_sqlserver_database_roles_data),
            ("30. Database Permissions", self._get_sqlserver_database_permissions_data),
            ("31. SQL Agent Jobs", self._get_sqlserver_sql_agent_jobs_data),
            ("32. Failed SQL Agent Jobs", self._get_sqlserver_failed_sql_agent_jobs_data),
            ("33. Active Sessions", self._get_sqlserver_active_sessions_data),
            ("34. Blocking Sessions", self._get_sqlserver_blocking_sessions_data),
            ("35. Long-Running Requests", self._get_sqlserver_long_running_requests_data),
            ("36. Top CPU Queries", self._get_sqlserver_top_cpu_queries_data),
            ("37. Top IO Queries", self._get_sqlserver_top_io_queries_data),
            ("38. Wait Statistics", self._get_sqlserver_wait_statistics_data),
            ("39. Active Transactions", self._get_sqlserver_active_transactions_data),
            ("40. Long-Running Transactions", self._get_sqlserver_long_running_transactions_data),
            ("41. Memory Usage", self._get_sqlserver_memory_usage_data),
            ("42. TempDB Usage", self._get_sqlserver_tempdb_usage_data),
            ("43. TempDB File Configuration", self._get_sqlserver_tempdb_file_configuration_data),
            ("44. Query Store Status", self._get_sqlserver_query_store_status_data),
            ("45. Database Scoped Configuration", self._get_sqlserver_database_scoped_configuration_data),
            ("46. Recovery Model And Log Reuse", self._get_sqlserver_recovery_model_and_log_reuse_data),
            ("47. Backup History", self._get_sqlserver_backup_history_data),
            ("48. Databases Without Recent Full Backup", self._get_sqlserver_databases_without_recent_full_backup_data),
            ("49. Always On Availability Status", self._get_sqlserver_always_on_availability_status_data),
            ("50. Always On Database Synchronization", self._get_sqlserver_always_on_database_synchronization_data),
            ("51. Linked Servers", self._get_sqlserver_linked_servers_data),
            ("52. Server Logins And Roles", self._get_sqlserver_server_logins_and_roles_data),
            ("53. Database Owners", self._get_sqlserver_database_owners_data),
            ("54. Auto Close And Auto Shrink", self._get_sqlserver_auto_close_and_auto_shrink_data),
            ("55. Statistics Inventory", self._get_sqlserver_statistics_inventory_data),
            ("56. Stale Statistics Candidates", self._get_sqlserver_stale_statistics_candidates_data),
            ("57. Deadlock Extended Events Sessions", self._get_sqlserver_deadlock_xevent_sessions_data),
            ("58. Server Configuration", self._get_sqlserver_server_configuration_data),
            ("59. CPU Schedulers", self._get_sqlserver_cpu_schedulers_data),
            ("60. Database Health Summary", self._get_sqlserver_database_health_summary_data),
        ]

    def display_sqlserver_menu(self) -> str:
        print("\nSQL Server Metadata Questions & Insights")
        print("-" * 60)
        fetchers = self._get_sqlserver_fetchers()
        for label, _ in fetchers:
            print(f"{label}")
        print(f"{len(fetchers) + 1}. All Reports (Export PDF)")
        print(f"{len(fetchers) + 2}. Exit (or 'q')")

        total_opts = len(fetchers) + 2
        valid_choices = {str(i) for i in range(1, total_opts + 1)}

        while True:
            try:
                choice = input(f"\nEnter your choice [1-{total_opts}]: ").strip()

                if choice in valid_choices:
                    return choice
                if choice.lower() in {"q", "quit", "exit"}:
                    return str(total_opts)

                print(f"Invalid choice. Please select 1 to {total_opts} (or 'q' to exit).")

            except KeyboardInterrupt:
                raise

    def _show_sqlserver_all_reports(self) -> None:
        """Collect all 60 SQL Server metadata reports strictly following document sequence and generate PDF report."""
        if not self.connector:
            raise RuntimeError("Database is not connected.")

        import time
        fetch_start = time.time()

        reports_data = []
        fetchers = self._get_sqlserver_fetchers()

        for label, fetcher in fetchers:
            print(f" -> Gathering data: {label}...")
            try:
                data = fetcher()
                data["title"] = label
                reports_data.append(data)
            except Exception as e:
                logger.error("Error gathering data for %s: %s", label, e)

        fetch_time = time.time() - fetch_start

        print("\n -> Building PDF document...")

        try:
            import os
            import sys
            from pdf_generator import PDFReportGenerator

            pdf_start = time.time()
            pdf_gen = PDFReportGenerator()
            pdf_path = pdf_gen.generate_report(
                reports_data,
                database_name="SQL Server",
                credentials_info=self.credentials,
            )
            pdf_build_time = time.time() - pdf_start
            total_elapsed = time.time() - fetch_start

            print("\n" + "=" * 80)
            print(" SUCCESS: ALL 60 REPORTS EXPORTED TO PDF!")
            print(f" PDF File Saved At: {pdf_path}")
            print(f" Time Taken to Fetch Data from DB: {fetch_time:.2f} seconds")
            print(f" Time Taken to Build PDF Document: {pdf_build_time:.2f} seconds")
            print(f" Total Process Time: {total_elapsed:.2f} seconds")
            print("=" * 80)
            logger.info("PDF report saved to %s (took %.2fs)", pdf_path, total_elapsed)

            if hasattr(os, "startfile"):
                os.startfile(str(pdf_path))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(pdf_path)])
            elif sys.platform.startswith("linux"):
                import subprocess
                subprocess.run(["xdg-open", str(pdf_path)])

        except Exception as exc:
            logger.error("Failed to generate PDF report: %s", exc)
            print(f"\n[Error] Could not generate PDF report: {exc}")

    def run_sqlserver_insights(self) -> None:
        fetchers = self._get_sqlserver_fetchers()
        export_choice = str(len(fetchers) + 1)
        exit_choice = str(len(fetchers) + 2)
        while True:
            choice = self.display_sqlserver_menu()

            if choice == exit_choice:
                print("\nExiting SQL Server metadata questions.")
                break
            elif choice == export_choice:
                self._show_sqlserver_all_reports()
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(fetchers):
                        label, fetcher = fetchers[idx]
                        data = fetcher()
                        self._show_paginated_table_report(
                            label, data.get("headers", []), data.get("rows", []), note=data.get("note")
                        )
                except Exception as e:
                    print(f"Error displaying insight: {e}")

    # Data methods for SQL Server
    def _get_sqlserver_server_environment_data(self) -> Dict[str, Any]:
        rows = self.connector.get_server_environment()
        formatted_rows = self._normalize_rows(
            rows,
            ["server_name", "product_version", "edition", "engine_edition"],
        )
        return {
            "title": "1. Server Environment",
            "headers": ["Server Name", "Product Version", "Edition", "Engine Edition"],
            "rows": formatted_rows,
            "note": "Identifies the SQL Server instance version and edition.",
        }

    def _get_sqlserver_database_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "database_name",
                "state_desc",
                "recovery_model_desc",
                "compatibility_level",
                "data_size_gb",
                "log_size_gb",
                "total_size_gb",
            ],
        )
        return {
            "title": "2. Database Inventory",
            "headers": [
                "Database Name",
                "State",
                "Recovery Model",
                "Compatibility Level",
                "Data Size (GB)",
                "Log Size (GB)",
                "Total Size (GB)",
            ],
            "rows": formatted_rows,
            "note": "Lists databases, state, recovery model, storage allocations, and total summary size.",
        }

    def _get_sqlserver_database_sizes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_sizes()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "data_size_gb", "log_size_gb", "total_size_gb"],
        )
        return {
            "title": "3. Database Sizes",
            "headers": ["Database Name", "Data Size (GB)", "Log Size (GB)", "Total Size (GB)"],
            "rows": formatted_rows,
            "note": "Shows total data-file and log-file size for each database.",
        }

    def _get_sqlserver_database_file_configuration_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_file_configuration()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "logical_file_name", "file_type", "physical_name", "size_gb", "growth_setting"],
        )
        return {
            "title": "3. Database File Configuration",
            "headers": ["Database Name", "Logical File Name", "File Type", "Physical Name", "Size (GB)", "Growth Setting"],
            "rows": formatted_rows,
            "note": "Reviews database file locations, sizes, and autogrowth configuration.",
        }

    def _get_sqlserver_data_vs_log_storage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_data_vs_log_storage()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "data_gb", "log_gb", "log_to_data_ratio_pct"],
        )
        return {
            "title": "4. Data Vs Log Storage",
            "headers": ["Database Name", "Data (GB)", "Log (GB)", "Log To Data Ratio (%)"],
            "rows": formatted_rows,
            "note": "Highlights databases where transaction-log allocation is large relative to data allocation.",
        }

    def _get_sqlserver_database_free_space_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_free_space()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "file_name", "allocated_gb", "used_gb", "free_gb", "free_pct"],
        )
        return {
            "title": "5. Database Free Space",
            "headers": ["Database Name", "File Name", "Allocated (GB)", "Used (GB)", "Free (GB)", "Free (%)"],
            "rows": formatted_rows,
            "note": "Estimates allocated, used, and free space within data files.",
        }

    def _get_sqlserver_largest_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_largest_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "row_count", "reserved_mb", "reserved_gb"],
        )
        return {
            "title": "6. Top 100 Largest Tables",
            "headers": ["Database Name", "Schema", "Table Name", "Row Count", "Reserved (MB)", "Reserved (GB)"],
            "rows": formatted_rows,
            "note": "Finds the top 100 largest user tables by row count across online user databases.",
        }

    def _get_sqlserver_table_row_counts_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_row_counts()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "row_count"],
        )
        return {
            "title": "8. Table Row Counts",
            "headers": ["Database Name", "Schema", "Table Name", "Row Count"],
            "rows": formatted_rows,
            "note": "Reports approximate row counts for user tables using partition metadata.",
        }

    def _get_sqlserver_schema_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_schema_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "object_count"],
        )
        return {
            "title": "7. Schema Inventory",
            "headers": ["Database Name", "Schema", "Object Count"],
            "rows": formatted_rows,
            "note": "Shows user schemas and the number of objects they contain.",
        }

    def _get_sqlserver_master_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_master_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "child_fk_count", "child_tables"],
        )
        return {
            "title": "8. Master (Parent) Tables",
            "headers": ["Database Name", "Schema", "Master Table Name", "Child FKs In", "Referencing Child Tables"],
            "rows": formatted_rows,
            "note": "Tables referenced by foreign key constraints in child tables.",
        }

    def _get_sqlserver_child_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_child_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "parent_fk_count", "parent_tables"],
        )
        return {
            "title": "9. Child Tables",
            "headers": ["Database Name", "Schema", "Child Table Name", "Parent FKs Out", "Referenced Parent Tables"],
            "rows": formatted_rows,
            "note": "Tables containing foreign key constraints pointing to parent tables.",
        }

    def _get_sqlserver_independent_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_independent_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name"],
        )
        return {
            "title": "10. Independent Tables",
            "headers": ["Database Name", "Schema", "Independent Table Name"],
            "rows": formatted_rows,
            "note": "Standalone tables with no foreign key relationships (neither parent nor child).",
        }

    def _get_sqlserver_table_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "create_date", "modify_date"],
        )
        return {
            "title": "11. Table Inventory",
            "headers": ["Database Name", "Schema", "Table Name", "Create Date", "Modify Date"],
            "rows": formatted_rows,
            "note": "Inventories user tables and their creation/modification metadata.",
        }

    def _get_sqlserver_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_primary_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "primary_key_name", "key_columns"],
        )
        return {
            "title": "12. Primary Keys",
            "headers": ["Database Name", "Schema", "Table Name", "Primary Key Name", "Key Columns"],
            "rows": formatted_rows,
            "note": "Lists primary keys and their participating columns.",
        }

    def _get_sqlserver_tables_without_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_without_primary_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name"],
        )
        return {
            "title": "13. Tables Without Primary Keys",
            "headers": ["Database Name", "Schema", "Table Name"],
            "rows": formatted_rows,
            "note": "Identifies user tables that do not have a primary key.",
        }

    def _get_sqlserver_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_foreign_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "parent_schema", "parent_table", "child_schema", "child_table", "foreign_key_name"],
        )
        return {
            "title": "14. Foreign Keys",
            "headers": ["Database Name", "Parent Schema", "Parent Table", "Child Schema", "Child Table", "Foreign Key Name"],
            "rows": formatted_rows,
            "note": "Maps foreign-key relationships between tables.",
        }

    def _get_sqlserver_tables_with_many_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_with_many_foreign_keys()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "foreign_key_count"],
        )
        return {
            "title": "15. Tables With Many Foreign Keys",
            "headers": ["Database Name", "Schema", "Table Name", "Foreign Key Count"],
            "rows": formatted_rows,
            "note": "Identifies tables with many foreign-key relationships, useful for dependency and design review.",
        }

    def _get_sqlserver_index_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_name", "index_type", "is_unique", "is_disabled"],
        )
        return {
            "title": "16. Index Inventory",
            "headers": ["Database Name", "Schema", "Table Name", "Index Name", "Index Type", "Is Unique", "Is Disabled"],
            "rows": formatted_rows,
            "note": "Inventories indexes and their main properties.",
        }

    def _get_sqlserver_index_count_by_table_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_count_by_table()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_count"],
        )
        return {
            "title": "17. Index Count By Table",
            "headers": ["Database Name", "Schema", "Table Name", "Index Count"],
            "rows": formatted_rows,
            "note": "Finds tables with unusually high numbers of indexes.",
        }

    def _get_sqlserver_largest_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_largest_indexes()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_name", "size_mb", "size_gb"],
        )
        return {
            "title": "18. Largest Indexes",
            "headers": ["Database Name", "Schema", "Table Name", "Index Name", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Identifies the top 100 largest indexes consuming the most storage.",
        }

    def _get_sqlserver_disabled_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_disabled_indexes()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_name"],
        )
        return {
            "title": "19. Disabled Indexes",
            "headers": ["Database Name", "Schema", "Table Name", "Index Name"],
            "rows": formatted_rows,
            "note": "Finds disabled indexes that may affect query performance or maintenance processes.",
        }

    def _get_sqlserver_fragmented_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_fragmented_indexes()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_name", "avg_fragmentation_pct", "page_count"],
        )
        return {
            "title": "20. Fragmented Indexes",
            "headers": ["Database Name", "Schema", "Table Name", "Index Name", "Avg Fragmentation (%)", "Page Count"],
            "rows": formatted_rows,
            "note": "Finds indexes with significant logical fragmentation using LIMITED sampling.",
        }

    def _get_sqlserver_index_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_usage()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_name", "seeks", "scans", "lookups", "updates"],
        )
        return {
            "title": "21. Index Usage",
            "headers": ["Database Name", "Schema", "Table Name", "Index Name", "Seeks", "Scans", "Lookups", "Updates"],
            "rows": formatted_rows,
            "note": "Shows index read/write activity for active indexes with recorded usage.",
        }

    def _get_sqlserver_duplicate_or_overlapping_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_duplicate_or_overlapping_indexes()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "index_1", "index_2", "key_columns"],
        )
        return {
            "title": "22. Duplicate Or Overlapping Indexes",
            "headers": ["Database Name", "Schema", "Table Name", "Index 1", "Index 2", "Key Columns"],
            "rows": formatted_rows,
            "note": "Finds indexes with identical leading key-column definitions on the same table.",
        }

    def _get_sqlserver_missing_index_recommendations_data(self) -> Dict[str, Any]:
        rows = self.connector.get_missing_index_recommendations()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "user_seeks", "user_scans", "avg_total_user_cost", "avg_user_impact", "equality_columns", "inequality_columns", "included_columns"],
        )
        return {
            "title": "23. Missing Index Recommendations",
            "headers": ["Database Name", "Schema", "Table Name", "User Seeks", "User Scans", "Avg Cost", "Avg Impact (%)", "Equality Columns", "Inequality Columns", "Included Columns"],
            "rows": formatted_rows,
            "note": "Shows missing-index DMV recommendations that SQL Server has generated since the relevant DMV counters were populated.",
        }

    def _get_sqlserver_views_data(self) -> Dict[str, Any]:
        rows = self.connector.get_views()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "view_name", "create_date", "modify_date"],
        )
        return {
            "title": "24. Views",
            "headers": ["Database Name", "Schema", "View Name", "Create Date", "Modify Date"],
            "rows": formatted_rows,
            "note": "Inventories views used in the database.",
        }

    def _get_sqlserver_stored_procedures_data(self) -> Dict[str, Any]:
        rows = self.connector.get_stored_procedures()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "procedure_name", "create_date", "modify_date"],
        )
        return {
            "title": "25. Stored Procedures",
            "headers": ["Database Name", "Schema", "Procedure Name", "Create Date", "Modify Date"],
            "rows": formatted_rows,
            "note": "Inventories stored procedures and modification timestamps.",
        }

    def _get_sqlserver_functions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_functions()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "function_name", "function_type", "create_date", "modify_date"],
        )
        return {
            "title": "26. Functions",
            "headers": ["Database Name", "Schema", "Function Name", "Function Type", "Create Date", "Modify Date"],
            "rows": formatted_rows,
            "note": "Inventories user-defined functions.",
        }

    def _get_sqlserver_triggers_data(self) -> Dict[str, Any]:
        rows = self.connector.get_triggers()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "trigger_name", "is_disabled"],
        )
        return {
            "title": "27. Triggers",
            "headers": ["Database Name", "Schema", "Table Name", "Trigger Name", "Is Disabled"],
            "rows": formatted_rows,
            "note": "Inventories DML triggers on user tables.",
        }

    def _get_sqlserver_object_dependencies_data(self) -> Dict[str, Any]:
        rows = self.connector.get_object_dependencies()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "database_name",
                "referencing_schema",
                "referencing_object",
                "referencing_object_type",
                "referenced_schema",
                "referenced_object",
                "referenced_object_type",
            ],
        )
        return {
            "title": "28. Object Dependencies",
            "headers": [
                "Database Name",
                "Referencing Schema",
                "Referencing Object",
                "Referencing Object Type",
                "Referenced Schema",
                "Referenced Object",
                "Referenced Object Type",
            ],
            "rows": formatted_rows,
            "note": "Maps module/object dependencies for impact analysis.",
        }

    def _get_sqlserver_database_roles_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_roles()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "role_name", "member_name"],
        )
        return {
            "title": "29. Database Roles",
            "headers": ["Database Name", "Role Name", "Member Name"],
            "rows": formatted_rows,
            "note": "Shows database role memberships for security review.",
        }

    def _get_sqlserver_database_permissions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_permissions()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "grantee", "permission_name", "state_desc", "schema_name", "object_name"],
        )
        return {
            "title": "30. Database Permissions",
            "headers": ["Database Name", "Grantee", "Permission", "State", "Schema", "Object Name"],
            "rows": formatted_rows,
            "note": "Reviews explicit database/object permissions granted or denied to non-system principals on user objects.",
        }

    def _get_sqlserver_sql_agent_jobs_data(self) -> Dict[str, Any]:
        rows = self.connector.get_sql_agent_jobs()
        formatted_rows = self._normalize_rows(
            rows,
            ["job_name", "enabled", "owner", "date_created"],
        )
        return {
            "title": "31. SQL Agent Jobs",
            "headers": ["Job Name", "Enabled", "Owner", "Date Created"],
            "rows": formatted_rows,
            "note": "Inventories SQL Server Agent jobs and their enabled state.",
        }

    def _get_sqlserver_failed_sql_agent_jobs_data(self) -> Dict[str, Any]:
        rows = self.connector.get_failed_sql_agent_jobs()
        formatted_rows = self._normalize_rows(
            rows,
            ["job_name", "run_datetime", "run_status", "message"],
        )
        return {
            "title": "32. Failed SQL Agent Jobs",
            "headers": ["Job Name", "Run Datetime", "Run Status", "Message"],
            "rows": formatted_rows,
            "note": "Finds recent SQL Server Agent job executions that did not succeed.",
        }

    def _get_sqlserver_active_sessions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_active_sessions()
        formatted_rows = self._normalize_rows(
            rows,
            ["session_id", "login_name", "host_name", "program_name", "status", "cpu_time", "memory_usage", "reads", "writes"],
        )
        return {
            "title": "33. Active Sessions",
            "headers": ["Session ID", "Login Name", "Host Name", "Program Name", "Status", "CPU Time", "Memory Usage", "Reads", "Writes"],
            "rows": formatted_rows,
            "note": "Shows currently active user sessions and their resource counters.",
        }

    def _get_sqlserver_blocking_sessions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_blocking_sessions()
        formatted_rows = self._normalize_rows(
            rows,
            ["session_id", "blocking_session_id", "wait_type", "wait_time_ms", "database_name", "sql_text"],
        )
        return {
            "title": "34. Blocking Sessions",
            "headers": ["Session ID", "Blocking Session ID", "Wait Type", "Wait Time (ms)", "Database", "SQL Text"],
            "rows": formatted_rows,
            "note": "Identifies currently blocked requests and their blockers.",
        }

    def _get_sqlserver_long_running_requests_data(self) -> Dict[str, Any]:
        rows = self.connector.get_long_running_requests()
        formatted_rows = self._normalize_rows(
            rows,
            ["session_id", "database_name", "start_time", "elapsed_seconds", "cpu_time_ms", "sql_text"],
        )
        return {
            "title": "35. Long-Running Requests",
            "headers": ["Session ID", "Database", "Start Time", "Elapsed Sec", "CPU Time (ms)", "SQL Text"],
            "rows": formatted_rows,
            "note": "Finds currently executing requests with high elapsed time.",
        }

    def _get_sqlserver_top_cpu_queries_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_cpu_queries()
        formatted_rows = self._normalize_rows(
            rows,
            ["execution_count", "total_cpu_ms", "avg_cpu_ms", "total_elapsed_ms", "sql_text"],
        )
        return {
            "title": "36. Top CPU Queries",
            "headers": ["Exec Count", "Total CPU (ms)", "Avg CPU (ms)", "Total Elapsed (ms)", "SQL Text"],
            "rows": formatted_rows,
            "note": "Finds cached query statements consuming the most CPU.",
        }

    def _get_sqlserver_top_io_queries_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_io_queries()
        formatted_rows = self._normalize_rows(
            rows,
            ["execution_count", "total_logical_reads", "avg_logical_reads", "total_logical_writes", "sql_text"],
        )
        return {
            "title": "37. Top IO Queries",
            "headers": ["Exec Count", "Total Logical Reads", "Avg Logical Reads", "Total Logical Writes", "SQL Text"],
            "rows": formatted_rows,
            "note": "Finds cached queries with high logical I/O activity.",
        }

    def _get_sqlserver_wait_statistics_data(self) -> Dict[str, Any]:
        rows = self.connector.get_wait_statistics()
        formatted_rows = self._normalize_rows(
            rows,
            ["wait_type", "waiting_tasks_count", "wait_time_ms", "signal_wait_time_ms"],
        )
        return {
            "title": "38. Wait Statistics",
            "headers": ["Wait Type", "Waiting Tasks Count", "Wait Time (ms)", "Signal Wait Time (ms)"],
            "rows": formatted_rows,
            "note": "Displays top 20 meaningful resource wait statistics, excluding known idle background tasks.",
        }

    def _get_sqlserver_active_transactions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_active_transactions()
        formatted_rows = self._normalize_rows(
            rows,
            ["transaction_id", "transaction_begin_time", "transaction_state", "session_id"],
        )
        return {
            "title": "39. Active Transactions",
            "headers": ["Transaction ID", "Begin Time", "State", "Session ID"],
            "rows": formatted_rows,
            "note": "Lists active transactions and their current state.",
        }

    def _get_sqlserver_long_running_transactions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_long_running_transactions()
        formatted_rows = self._normalize_rows(
            rows,
            ["session_id", "transaction_begin_time", "elapsed_minutes", "database_name"],
        )
        return {
            "title": "40. Long-Running Transactions",
            "headers": ["Session ID", "Begin Time", "Elapsed (min)", "Database Name"],
            "rows": formatted_rows,
            "note": "Identifies transactions that have remained active for a long time.",
        }

    def _get_sqlserver_memory_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_memory_usage()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "total_physical_memory_gb",
                "used_physical_memory_gb",
                "available_physical_memory_gb",
                "memory_state",
            ],
        )
        return {
            "title": "41. Memory Usage",
            "headers": [
                "Total Physical Memory (GB)",
                "Used Physical Memory (GB)",
                "Available Physical Memory (GB)",
                "Memory State",
            ],
            "rows": formatted_rows,
            "note": "Reports operating-system memory visibility and SQL Server memory state.",
        }

    def _get_sqlserver_tempdb_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tempdb_usage()
        formatted_rows = self._normalize_rows(
            rows,
            ["session_id", "user_objects_mb", "internal_objects_mb", "total_allocated_mb"],
        )
        return {
            "title": "42. TempDB Usage",
            "headers": ["Session ID", "User Objects (MB)", "Internal Objects (MB)", "Total Allocated (MB)"],
            "rows": formatted_rows,
            "note": "Shows current TempDB allocation by session.",
        }

    def _get_sqlserver_tempdb_file_configuration_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tempdb_file_configuration()
        formatted_rows = self._normalize_rows(
            rows,
            ["file_id", "file_name", "physical_name", "size_mb", "growth_setting"],
        )
        return {
            "title": "43. TempDB File Configuration",
            "headers": ["File ID", "File Name", "Physical Name", "Size (MB)", "Growth Setting"],
            "rows": formatted_rows,
            "note": "Reviews TempDB data/log file sizing and growth settings.",
        }

    def _get_sqlserver_query_store_status_data(self) -> Dict[str, Any]:
        rows = self.connector.get_query_store_status()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "desired_state", "actual_state", "readonly_reason", "current_storage_size_mb", "max_storage_size_mb"],
        )
        return {
            "title": "44. Query Store Status",
            "headers": ["Database Name", "Desired State", "Actual State", "Readonly Reason", "Current Storage (MB)", "Max Storage (MB)"],
            "rows": formatted_rows,
            "note": "Reviews Query Store configuration and storage state per database.",
        }

    def _get_sqlserver_database_scoped_configuration_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_scoped_configuration()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "configuration_name", "value", "value_for_secondary"],
        )
        return {
            "title": "45. Database Scoped Configuration",
            "headers": ["Database Name", "Configuration Name", "Value", "Value For Secondary"],
            "rows": formatted_rows,
            "note": "Reviews top 10 key database-scoped configuration settings per database.",
        }

    def _get_sqlserver_recovery_model_and_log_reuse_data(self) -> Dict[str, Any]:
        rows = self.connector.get_recovery_model_and_log_reuse()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "recovery_model_desc", "log_reuse_wait_desc"],
        )
        return {
            "title": "46. Recovery Model And Log Reuse",
            "headers": ["Database Name", "Recovery Model", "Log Reuse Wait Reason"],
            "rows": formatted_rows,
            "note": "Identifies recovery model and reasons that may prevent transaction-log reuse.",
        }

    def _get_sqlserver_backup_history_data(self) -> Dict[str, Any]:
        rows = self.connector.get_backup_history()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "backup_type", "backup_start_date", "backup_finish_date", "backup_size_mb"],
        )
        return {
            "title": "47. Backup History",
            "headers": ["Database Name", "Backup Type", "Start Date", "Finish Date", "Backup Size (MB)"],
            "rows": formatted_rows,
            "note": "Reviews recent database backup history and backup types.",
        }

    def _get_sqlserver_databases_without_recent_full_backup_data(self) -> Dict[str, Any]:
        rows = self.connector.get_databases_without_recent_full_backup()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "last_full_backup"],
        )
        return {
            "title": "48. Databases Without Recent Full Backup",
            "headers": ["Database Name", "Last Full Backup"],
            "rows": formatted_rows,
            "note": "Identifies databases with no recorded full backup or no full backup within the selected assessment window.",
        }

    def _get_sqlserver_always_on_availability_status_data(self) -> Dict[str, Any]:
        rows = self.connector.get_always_on_availability_status()
        formatted_rows = self._normalize_rows(
            rows,
            ["group_name", "replica_server", "role_desc", "operational_state_desc", "connected_state_desc"],
        )
        return {
            "title": "49. Always On Availability Status",
            "headers": ["Group Name", "Replica Server", "Role", "Operational State", "Connected State"],
            "rows": formatted_rows,
            "note": "Reviews Always On availability replica health when HADR is configured.",
        }

    def _get_sqlserver_always_on_database_synchronization_data(self) -> Dict[str, Any]:
        rows = self.connector.get_always_on_database_synchronization()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "replica_server", "synchronization_state_desc", "synchronization_health_desc"],
        )
        return {
            "title": "50. Always On Database Synchronization",
            "headers": ["Database Name", "Replica Server", "Synchronization State", "Synchronization Health"],
            "rows": formatted_rows,
            "note": "Reviews database-level Always On synchronization and health.",
        }

    def _get_sqlserver_linked_servers_data(self) -> Dict[str, Any]:
        rows = self.connector.get_linked_servers()
        formatted_rows = self._normalize_rows(
            rows,
            ["server_name", "product", "provider", "data_source", "is_linked"],
        )
        return {
            "title": "51. Linked Servers",
            "headers": ["Server Name", "Product", "Provider", "Data Source", "Is Linked"],
            "rows": formatted_rows,
            "note": "Inventories configured linked servers and remote data providers.",
        }

    def _get_sqlserver_server_logins_and_roles_data(self) -> Dict[str, Any]:
        rows = self.connector.get_server_logins_and_roles()
        formatted_rows = self._normalize_rows(
            rows,
            ["login_name", "login_type", "is_disabled", "server_role"],
        )
        return {
            "title": "52. Server Logins And Roles",
            "headers": ["Login Name", "Login Type", "Is Disabled", "Server Role"],
            "rows": formatted_rows,
            "note": "Reviews SQL/Windows logins, disabled status, and fixed server-role membership.",
        }

    def _get_sqlserver_database_owners_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_owners()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "owner_name"],
        )
        return {
            "title": "53. Database Owners",
            "headers": ["Database Name", "Owner Name"],
            "rows": formatted_rows,
            "note": "Reviews database ownership for governance and security assessment.",
        }

    def _get_sqlserver_auto_close_and_auto_shrink_data(self) -> Dict[str, Any]:
        rows = self.connector.get_auto_close_and_auto_shrink()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "is_auto_close_on", "is_auto_shrink_on"],
        )
        return {
            "title": "54. Auto Close And Auto Shrink",
            "headers": ["Database Name", "Auto Close", "Auto Shrink"],
            "rows": formatted_rows,
            "note": "Identifies databases configured with AUTO_CLOSE or AUTO_SHRINK.",
        }

    def _get_sqlserver_statistics_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_statistics_inventory()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "statistics_name", "auto_created", "user_created", "no_recompute"],
        )
        return {
            "title": "55. Statistics Inventory",
            "headers": ["Database Name", "Schema", "Table Name", "Statistics Name", "Auto Created", "User Created", "No Recompute"],
            "rows": formatted_rows,
            "note": "Inventories table statistics and their creation/recompute properties.",
        }

    def _get_sqlserver_stale_statistics_candidates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_stale_statistics_candidates()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "schema_name", "table_name", "statistics_name", "rows", "modification_counter"],
        )
        return {
            "title": "56. Stale Statistics Candidates",
            "headers": ["Database Name", "Schema", "Table Name", "Statistics Name", "Rows", "Modification Counter"],
            "rows": formatted_rows,
            "note": "Identifies statistics with a high modification counter relative to their recorded row count.",
        }

    def _get_sqlserver_deadlock_xevent_sessions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_deadlock_xevent_sessions()
        formatted_rows = self._normalize_rows(
            rows,
            ["session_name", "startup_state", "state_desc"],
        )
        return {
            "title": "57. Deadlock Extended Events Sessions",
            "headers": ["Session Name", "Startup State", "State"],
            "rows": formatted_rows,
            "note": "Checks Extended Events sessions for deadlock monitoring configuration.",
        }

    def _get_sqlserver_server_configuration_data(self) -> Dict[str, Any]:
        rows = self.connector.get_server_configuration()
        formatted_rows = self._normalize_rows(
            rows,
            ["configuration_name", "value_in_use", "minimum", "maximum", "description"],
        )
        return {
            "title": "58. Server Configuration",
            "headers": ["Configuration Name", "Value In Use", "Minimum", "Maximum", "Description"],
            "rows": formatted_rows,
            "note": "Reviews top 10 key instance-level configuration options and their active values.",
        }

    def _get_sqlserver_cpu_schedulers_data(self) -> Dict[str, Any]:
        rows = self.connector.get_cpu_schedulers()
        formatted_rows = self._normalize_rows(
            rows,
            ["scheduler_id", "status", "cpu_id", "is_online", "is_idle", "current_tasks_count", "runnable_tasks_count"],
        )
        return {
            "title": "59. CPU Schedulers",
            "headers": ["Scheduler ID", "Status", "CPU ID", "Is Online", "Is Idle", "Current Tasks Count", "Runnable Tasks Count"],
            "rows": formatted_rows,
            "note": "Shows SQL Server scheduler state and runnable workload indicators.",
        }

    def _get_sqlserver_database_health_summary_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_health_summary()
        formatted_rows = self._normalize_rows(
            rows,
            ["database_name", "state_desc", "recovery_model_desc", "compatibility_level", "user_access_desc", "is_read_only", "is_auto_close_on", "is_auto_shrink_on", "log_reuse_wait_desc"],
        )
        return {
            "title": "60. Database Health Summary",
            "headers": ["Database Name", "State", "Recovery Model", "Compat Level", "User Access", "Is Read Only", "Auto Close", "Auto Shrink", "Log Reuse Wait Reason"],
            "rows": formatted_rows,
            "note": "Provides a compact operational health summary for user databases.",
        }

    def _get_oracle_environment_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_environment_info()
        formatted_rows = self._normalize_rows(
            rows,
            ["banner", "instance_name", "host_name", "version", "status", "database_status", "db_name", "open_mode", "database_role"],
        )
        return {
            "title": "1. Oracle Version And Environment",
            "headers": ["Banner", "Instance", "Host", "Version", "Status", "DB Status", "DB Name", "Open Mode", "Role"],
            "rows": formatted_rows,
            "note": "Oracle server, instance, and database configuration details.",
        }

    def _get_oracle_schema_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_schema_inventory()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "actual_size_mb"])
        return {
            "title": "2. Schema Inventory",
            "headers": ["Schema Name", "Actual Size (MB)"],
            "rows": formatted_rows,
            "note": f"Database user schemas inventory with actual allocated size. Last row shows total. ({max(0, len(rows) - 1)} user schemas).",
        }

    def _get_oracle_master_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_master_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "child_fk_count", "child_tables"],
        )
        return {
            "title": "9. Master (Parent) Tables",
            "headers": ["Schema", "Master Table Name", "Child FKs In", "Referencing Child Tables"],
            "rows": formatted_rows,
            "note": "Tables referenced by foreign key constraints in child tables.",
        }

    def _get_oracle_child_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_child_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "parent_fk_count", "parent_tables"],
        )
        return {
            "title": "10. Child Tables",
            "headers": ["Schema", "Child Table Name", "Parent FKs Out", "Referenced Parent Tables"],
            "rows": formatted_rows,
            "note": "Tables containing foreign key constraints pointing to parent tables.",
        }

    def _get_oracle_independent_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_independent_tables()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name"],
        )
        return {
            "title": "11. Independent Tables",
            "headers": ["Schema", "Independent Table Name"],
            "rows": formatted_rows,
            "note": "Standalone tables with no foreign key relationships (neither parent nor child).",
        }

    def _get_oracle_schema_table_storage_analysis_data(self) -> Dict[str, Any]:
        rows = self.connector.get_schema_table_storage_analysis()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "size_mb", "size_gb"])
        return {
            "title": "3. Schema/Table Storage Analysis",
            "headers": ["Schema", "Table Name", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Database-wide table segment sizes in MB and GB.",
        }

    def _get_oracle_total_data_vs_index_storage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_total_data_vs_index_storage()
        formatted_rows = self._normalize_rows(rows, ["table_gb", "index_gb", "total_gb"])
        return {
            "title": "4. Total Data Vs Index Storage",
            "headers": ["Table Storage (GB)", "Index Storage (GB)", "Total Storage (GB)"],
            "rows": formatted_rows,
            "note": "Total database table vs index storage footprint in GB.",
        }

    def _get_oracle_top_100_largest_segments_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_100_largest_segments()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "segment_name", "segment_type", "size_mb", "size_gb"])
        return {
            "title": "5. Top 100 Largest Segments",
            "headers": ["Schema", "Segment Name", "Segment Type", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Top 100 largest segments in the database by total allocated size.",
        }

    def _get_oracle_table_row_counts_stats_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_row_counts_stats()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "num_rows", "last_analyzed"])
        return {
            "title": "6. Table Row Counts / Statistics",
            "headers": ["Schema", "Table Name", "Rows (Est)", "Last Analyzed"],
            "rows": formatted_rows,
            "note": "Table row counts based on dictionary optimizer statistics.",
        }

    def _get_oracle_tablespace_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tablespace_usage()
        formatted_rows = self._normalize_rows(rows, ["tablespace_name", "allocated_gb"])
        return {
            "title": "6. Tablespace Usage",
            "headers": ["Tablespace Name", "Allocated Space (GB)"],
            "rows": formatted_rows,
            "note": "Allocated size by tablespace from datafiles.",
        }

    def _get_oracle_tablespace_free_space_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tablespace_free_space()
        formatted_rows = self._normalize_rows(rows, ["tablespace_name", "allocated_gb", "free_gb", "used_gb"])
        return {
            "title": "7. Tablespace Free Space",
            "headers": ["Tablespace Name", "Allocated (GB)", "Free Space (GB)", "Used Space (GB)"],
            "rows": formatted_rows,
            "note": "Tablespace allocation, free space, and used space metrics.",
        }

    def _get_oracle_datafiles_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_datafiles_inventory()
        formatted_rows = self._normalize_rows(rows, ["file_name", "tablespace_name", "size_gb", "autoextensible", "max_size_gb"])
        return {
            "title": "8. Datafiles",
            "headers": ["File Path", "Tablespace", "Size (GB)", "Autoextensible", "Max Size (GB)"],
            "rows": formatted_rows,
            "note": "Oracle database datafiles physical layout and autoextend parameters.",
        }

    def _get_oracle_large_unpartitioned_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_unpartitioned_tables()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "size_mb", "size_gb"])
        return {
            "title": "9. Large Unpartitioned Tables",
            "headers": ["Schema", "Table Name", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Unpartitioned tables ranked by segment size.",
        }

    def _get_oracle_partition_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_partition_inventory()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "partition_count"])
        return {
            "title": "10. Partition Inventory",
            "headers": ["Schema", "Table Name", "Partition Count"],
            "rows": formatted_rows,
            "note": "Partitioned tables and total partition counts.",
        }

    def _get_oracle_detailed_partition_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_detailed_partition_info()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "partition_name", "partition_position", "num_rows", "last_analyzed"])
        return {
            "title": "11. Detailed Partition Information",
            "headers": ["Schema", "Table Name", "Partition Name", "Position", "Rows (Est)", "Last Analyzed"],
            "rows": formatted_rows,
            "note": "Partition definitions, positions, and optimizer statistics.",
        }

    def _get_oracle_column_inventory_data(self) -> Dict[str, Any]:
        rows = self.connector.get_column_inventory()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "column_id", "column_name", "data_type", "data_length", "data_precision", "data_scale", "nullable"])
        return {
            "title": "12. Column Inventory",
            "headers": ["Schema", "Table", "ID", "Column Name", "Data Type", "Length", "Precision", "Scale", "Nullable"],
            "rows": formatted_rows,
            "note": "Complete column definitions dictionary.",
        }

    def _get_oracle_large_object_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_object_columns()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "column_name", "data_type"])
        return {
            "title": "13. Large Object Columns",
            "headers": ["Schema", "Table Name", "Column Name", "LOB Type"],
            "rows": formatted_rows,
            "note": "Tables containing BLOB, CLOB, NCLOB, or LONG columns.",
        }

    def _get_oracle_json_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_json_columns()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "column_name", "data_type"])
        return {
            "title": "14. JSON-Related Columns",
            "headers": ["Schema", "Table Name", "Column Name", "Data Type"],
            "rows": formatted_rows,
            "note": "Columns storing JSON documents or JSON data types.",
        }

    def _get_oracle_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_primary_keys()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "constraint_name", "status"])
        return {
            "title": "15. Primary Keys",
            "headers": ["Schema", "Table Name", "Constraint Name", "Status"],
            "rows": formatted_rows,
            "note": "Primary key constraints inventory.",
        }

    def _get_oracle_without_primary_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_without_primary_keys()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name"])
        return {
            "title": "16. Tables Without Primary Keys",
            "headers": ["Schema", "Table Name"],
            "rows": formatted_rows,
            "note": "Tables defined without an explicit Primary Key.",
        }

    def _get_oracle_all_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_all_indexes()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "index_name", "index_type", "uniqueness", "status"])
        return {
            "title": "17. All Indexes",
            "headers": ["Schema", "Table Name", "Index Name", "Index Type", "Uniqueness", "Status"],
            "rows": formatted_rows,
            "note": "Database indexes inventory.",
        }

    def _get_oracle_index_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_columns()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "index_name", "column_position", "column_name"])
        return {
            "title": "18. Index Columns",
            "headers": ["Schema", "Table Name", "Index Name", "Position", "Column Name"],
            "rows": formatted_rows,
            "note": "Index column mapping positions.",
        }

    def _get_oracle_index_count_by_table_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_count_by_table()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "index_count"])
        return {
            "title": "19. Index Count By Table",
            "headers": ["Schema", "Table Name", "Index Count"],
            "rows": formatted_rows,
            "note": "Total indexes per table ranked by count.",
        }

    def _get_oracle_largest_indexes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_largest_indexes()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "index_name", "index_mb", "index_gb"])
        return {
            "title": "20. Largest Indexes",
            "headers": ["Schema", "Table Name", "Index Name", "Index Size (MB)", "Index Size (GB)"],
            "rows": formatted_rows,
            "note": "Top 100 largest indexes by total segment size.",
        }

    def _get_oracle_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_foreign_keys()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "constraint_name", "referenced_schema", "referenced_constraint"])
        return {
            "title": "21. Foreign Keys / Relationships",
            "headers": ["Schema", "Table Name", "Constraint Name", "Ref Schema", "Ref Constraint"],
            "rows": formatted_rows,
            "note": "Foreign key referential constraints.",
        }

    def _get_oracle_detailed_foreign_key_columns_data(self) -> Dict[str, Any]:
        rows = self.connector.get_detailed_foreign_key_columns()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "constraint_name", "column_name", "referenced_schema", "referenced_table", "referenced_column", "position"])
        return {
            "title": "22. Detailed Foreign-Key Columns",
            "headers": ["Child Schema", "Child Table", "Constraint", "Child Column", "Ref Schema", "Ref Table", "Ref Column", "Position"],
            "rows": formatted_rows,
            "note": "Detailed column-to-column referential constraint mapping.",
        }

    def _get_oracle_tables_many_foreign_keys_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tables_many_foreign_keys()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "foreign_key_count"])
        return {
            "title": "23. Tables With Many Foreign-Key Relationships",
            "headers": ["Schema", "Table Name", "Foreign Key Count"],
            "rows": formatted_rows,
            "note": "Tables ranked by number of outgoing foreign key constraints.",
        }

    def _get_oracle_unique_constraints_data(self) -> Dict[str, Any]:
        rows = self.connector.get_unique_constraints()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "constraint_name", "status"])
        return {
            "title": "24. Unique Constraints",
            "headers": ["Schema", "Table Name", "Constraint Name", "Status"],
            "rows": formatted_rows,
            "note": "Unique constraints inventory.",
        }

    def _get_oracle_duplicate_index_candidates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_duplicate_index_candidates()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "index_a", "index_b", "first_column"])
        return {
            "title": "24. Duplicate/Redundant Index Candidates",
            "headers": ["Schema", "Table Name", "Index A", "Index B", "Leading Column"],
            "rows": formatted_rows,
            "note": "Candidate redundant indexes sharing the exact same first column.",
        }

    def _get_oracle_null_analysis_data(self) -> Dict[str, Any]:
        rows = self.connector.get_null_analysis()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "column_name", "nullable"])
        return {
            "title": "25. NULL Analysis",
            "headers": ["Schema", "Table Name", "Column Name", "Nullable"],
            "rows": formatted_rows,
            "note": "Columns accepting NULL values across user schemas.",
        }

    def _get_oracle_charsets_and_collations_data(self) -> Dict[str, Any]:
        rows = self.connector.get_charsets_and_collations()
        formatted_rows = self._normalize_rows(rows, ["parameter", "value"])
        return {
            "title": "27. Character Sets And Collations",
            "headers": ["NLS Parameter", "Value"],
            "rows": formatted_rows,
            "note": "NLS database character set configuration.",
        }

    def _get_oracle_table_comments_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_comments()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "comments"])
        return {
            "title": "28. Tables With Comments / Documentation",
            "headers": ["Schema", "Table Name", "Comments"],
            "rows": formatted_rows,
            "note": "Table documentation comments from dictionary.",
        }

    def _get_oracle_stored_procedures_data(self) -> Dict[str, Any]:
        rows = self.connector.get_stored_procedures()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "object_name", "status", "created", "last_ddl_time"])
        return {
            "title": "31. Stored Procedures",
            "headers": ["Schema", "Procedure Name", "Status", "Created", "Last DDL Time"],
            "rows": formatted_rows,
            "note": "Stored procedures inventory.",
        }

    def _get_oracle_functions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_functions()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "object_name", "status", "created", "last_ddl_time"])
        return {
            "title": "31. Functions",
            "headers": ["Schema", "Function Name", "Status", "Created", "Last DDL Time"],
            "rows": formatted_rows,
            "note": "Database functions inventory.",
        }

    def _get_oracle_packages_data(self) -> Dict[str, Any]:
        rows = self.connector.get_packages()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "object_type", "object_name", "status", "created", "last_ddl_time"])
        return {
            "title": "32. Packages",
            "headers": ["Schema", "Object Type", "Package Name", "Status", "Created", "Last DDL Time"],
            "rows": formatted_rows,
            "note": "Packages and package bodies inventory.",
        }

    def _get_oracle_views_data(self) -> Dict[str, Any]:
        rows = self.connector.get_views()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "view_name"])
        return {
            "title": "30. Views",
            "headers": ["Schema", "View Name"],
            "rows": formatted_rows,
            "note": "Database views inventory.",
        }

    def _get_oracle_triggers_data(self) -> Dict[str, Any]:
        rows = self.connector.get_triggers()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "trigger_name", "table_name", "triggering_event", "trigger_type", "status"])
        return {
            "title": "31. Triggers",
            "headers": ["Schema", "Trigger Name", "Table Name", "Event", "Type", "Status"],
            "rows": formatted_rows,
            "note": "Database triggers inventory.",
        }

    def _get_oracle_scheduled_jobs_data(self) -> Dict[str, Any]:
        rows = self.connector.get_scheduled_jobs()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "job_name", "enabled", "state", "job_type", "last_start_date", "next_run_date"])
        return {
            "title": "31. Scheduled Jobs",
            "headers": ["Schema", "Job Name", "Enabled", "State", "Job Type", "Last Start", "Next Run"],
            "rows": formatted_rows,
            "note": "Oracle Scheduler jobs inventory.",
        }

    def _get_oracle_users_and_privileges_data(self) -> Dict[str, Any]:
        rows = self.connector.get_users_and_privileges()
        formatted_rows = self._normalize_rows(rows, ["username", "account_status", "created", "profile"])
        return {
            "title": "32. Users And Privileges",
            "headers": ["Username", "Account Status", "Created Date", "Profile"],
            "rows": formatted_rows,
            "note": "Database user accounts and account status.",
        }

    def _get_oracle_tablespace_and_segment_status_data(self) -> Dict[str, Any]:
        rows = self.connector.get_tablespace_and_segment_status()
        formatted_rows = self._normalize_rows(rows, ["tablespace_name", "status", "contents", "extent_management", "segment_space_management"])
        return {
            "title": "33. Tablespace And Segment Status",
            "headers": ["Tablespace Name", "Status", "Contents", "Extent Management", "Segment Management"],
            "rows": formatted_rows,
            "note": "Tablespace definitions and segment management parameters.",
        }

    def _get_oracle_sga_memory_config_data(self) -> Dict[str, Any]:
        rows = self.connector.get_sga_memory_config()
        formatted_rows = self._normalize_rows(rows, ["name", "value"])
        return {
            "title": "34. SGA / Memory Configuration",
            "headers": ["Memory Component", "Allocated Value (Bytes)"],
            "rows": formatted_rows,
            "note": "System Global Area (SGA) memory components.",
        }

    def _get_oracle_pga_config_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_pga_config_usage()
        formatted_rows = self._normalize_rows(rows, ["name", "value"])
        return {
            "title": "35. PGA Configuration And Usage",
            "headers": ["PGA Metric Name", "Value"],
            "rows": formatted_rows,
            "note": "Program Global Area (PGA) metrics and limits.",
        }

    def _get_oracle_temp_tablespace_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_temp_tablespace_usage()
        formatted_rows = self._normalize_rows(rows, ["tablespace_name", "tablespace_size", "allocated_space", "free_space"])
        return {
            "title": "36. Temporary Tablespace Usage",
            "headers": ["Tablespace Name", "Total Size", "Allocated Space", "Free Space"],
            "rows": formatted_rows,
            "note": "Temporary tablespaces usage and allocation.",
        }

    def _get_oracle_sessions_and_connections_data(self) -> Dict[str, Any]:
        rows = self.connector.get_sessions_and_connections()
        formatted_rows = self._normalize_rows(rows, ["status", "session_count"])
        return {
            "title": "37. Sessions And Connections",
            "headers": ["Session Status", "Active Session Count"],
            "rows": formatted_rows,
            "note": "Active session connections count grouped by status.",
        }

    def _get_oracle_long_running_sessions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_long_running_sessions()
        formatted_rows = self._normalize_rows(rows, ["sid", "serial#", "username", "status", "event", "sql_id", "elapsed_seconds"])
        return {
            "title": "38. Long-Running Sessions",
            "headers": ["SID", "Serial#", "Username", "Status", "Wait Event", "SQL ID", "Elapsed (s)"],
            "rows": formatted_rows,
            "note": "Active user sessions ranked by elapsed time.",
        }

    def _get_oracle_locks_data(self) -> Dict[str, Any]:
        rows = self.connector.get_locks()
        formatted_rows = self._normalize_rows(rows, ["blocking_sid", "waiting_sid", "type", "id1", "id2", "blocking_mode", "waiting_request"])
        return {
            "title": "39. Locks",
            "headers": ["Blocking SID", "Waiting SID", "Lock Type", "ID1", "ID2", "Blocking Mode", "Waiting Request"],
            "rows": formatted_rows,
            "note": "Active database locks blocking session execution.",
        }

    def _get_oracle_blocking_sessions_data(self) -> Dict[str, Any]:
        rows = self.connector.get_blocking_sessions()
        formatted_rows = self._normalize_rows(rows, ["sid", "serial#", "username", "blocking_session", "event", "seconds_in_wait"])
        return {
            "title": "40. Blocking Sessions",
            "headers": ["SID", "Serial#", "Username", "Blocking SID", "Wait Event", "Seconds In Wait"],
            "rows": formatted_rows,
            "note": "Sessions currently waiting on blocking sessions.",
        }

    def _get_oracle_slow_sql_data(self) -> Dict[str, Any]:
        rows = self.connector.get_slow_sql()
        formatted_rows = self._normalize_rows(rows, ["sql_id", "executions", "elapsed_seconds", "cpu_seconds", "buffer_gets", "disk_reads", "rows_processed", "sql_text_sample"])
        return {
            "title": "41. Slow / Resource-Intensive SQL",
            "headers": ["SQL ID", "Executions", "Elapsed (s)", "CPU (s)", "Buffer Gets", "Disk Reads", "Rows Processed", "SQL Text Sample"],
            "rows": formatted_rows,
            "note": "Top SQL queries ranked by cumulative elapsed time from V$SQL.",
        }

    def _get_oracle_large_data_examination_sql_data(self) -> Dict[str, Any]:
        rows = self.connector.get_large_data_examination_sql()
        formatted_rows = self._normalize_rows(rows, ["sql_id", "executions", "buffer_gets", "disk_reads", "rows_processed", "sql_text_sample"])
        return {
            "title": "42. SQL Examining Large Amounts Of Data",
            "headers": ["SQL ID", "Executions", "Buffer Gets", "Disk Reads", "Rows Processed", "SQL Text Sample"],
            "rows": formatted_rows,
            "note": "Top SQL queries ranked by buffer gets (data examination).",
        }

    def _get_oracle_frequently_executed_sql_data(self) -> Dict[str, Any]:
        rows = self.connector.get_frequently_executed_sql()
        formatted_rows = self._normalize_rows(rows, ["sql_id", "executions", "elapsed_seconds", "sql_text_sample"])
        return {
            "title": "43. Most Frequently Executed SQL",
            "headers": ["SQL ID", "Executions", "Elapsed Seconds", "SQL Text Sample"],
            "rows": formatted_rows,
            "note": "Top SQL queries ranked by cumulative execution count.",
        }

    def _get_oracle_top_wait_events_data(self) -> Dict[str, Any]:
        rows = self.connector.get_top_wait_events()
        formatted_rows = self._normalize_rows(rows, ["event", "total_waits", "time_waited", "wait_seconds"])
        return {
            "title": "44. Top Wait Events",
            "headers": ["Event Name", "Total Waits", "Time Waited", "Wait Seconds"],
            "rows": formatted_rows,
            "note": "System wait events ranked by total time waited.",
        }

    def _get_oracle_database_time_load_profile_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_time_load_profile()
        formatted_rows = self._normalize_rows(rows, ["name", "value"])
        return {
            "title": "45. Database Time / Load Profile",
            "headers": ["Sysstat Metric Name", "Value"],
            "rows": formatted_rows,
            "note": "Database CPU, DB time, commits, and rollbacks metrics.",
        }

    def _get_oracle_dataguard_db_role_data(self) -> Dict[str, Any]:
        rows = self.connector.get_dataguard_db_role()
        formatted_rows = self._normalize_rows(rows, ["name", "db_unique_name", "open_mode", "database_role", "protection_mode", "protection_level", "switchover_status"])
        return {
            "title": "46. Data Guard / Database Role",
            "headers": ["DB Name", "DB Unique Name", "Open Mode", "DB Role", "Protection Mode", "Protection Level", "Switchover Status"],
            "rows": formatted_rows,
            "note": "Oracle Data Guard role and open status.",
        }

    def _get_oracle_archive_log_config_data(self) -> Dict[str, Any]:
        rows = self.connector.get_archive_log_config()
        formatted_rows = self._normalize_rows(rows, ["name", "value"])
        return {
            "title": "47. Archive Log Configuration",
            "headers": ["Parameter Name", "Setting Value"],
            "rows": formatted_rows,
            "note": "Archive log destination and format parameters.",
        }

    def _get_oracle_archive_log_generation_data(self) -> Dict[str, Any]:
        rows = self.connector.get_archive_log_generation()
        formatted_rows = self._normalize_rows(rows, ["thread#", "sequence#", "first_time", "next_time", "blocks", "block_size"])
        return {
            "title": "48. Archive Log Generation",
            "headers": ["Thread#", "Sequence#", "First Time", "Next Time", "Blocks", "Block Size"],
            "rows": formatted_rows,
            "note": "Recent archive log generation history.",
        }

    def _get_oracle_redo_generation_data(self) -> Dict[str, Any]:
        rows = self.connector.get_redo_generation()
        formatted_rows = self._normalize_rows(rows, ["name", "value"])
        return {
            "title": "49. Redo Generation",
            "headers": ["Metric Name", "Value"],
            "rows": formatted_rows,
            "note": "Redo size, writes, and entries statistics.",
        }

    def _get_oracle_undo_config_usage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_undo_config_usage()
        formatted_rows = self._normalize_rows(rows, ["tablespace_name", "status", "retention"])
        return {
            "title": "50. Undo Configuration And Usage",
            "headers": ["Undo Tablespace Name", "Status", "Retention (s)"],
            "rows": formatted_rows,
            "note": "Undo tablespaces status and retention settings.",
        }

    def _get_oracle_datafiles_physical_layout_data(self) -> Dict[str, Any]:
        rows = self.connector.get_datafiles_physical_layout()
        formatted_rows = self._normalize_rows(rows, ["file_id", "file_name", "tablespace_name", "size_gb", "autoextensible", "status"])
        return {
            "title": "51. Oracle Datafiles / Physical Layout",
            "headers": ["File ID", "File Name", "Tablespace Name", "Size (GB)", "Autoextensible", "Status"],
            "rows": formatted_rows,
            "note": "Oracle datafiles physical layout.",
        }

    def _get_oracle_asm_diskgroup_capacity_data(self) -> Dict[str, Any]:
        rows = self.connector.get_asm_diskgroup_capacity()
        formatted_rows = self._normalize_rows(rows, ["name", "type", "total_mb", "free_mb", "used_pct"])
        return {
            "title": "52. ASM Disk Group Capacity",
            "headers": ["Diskgroup Name", "Type", "Total (MB)", "Free (MB)", "Used %"],
            "rows": formatted_rows,
            "note": "ASM disk groups total capacity and free space.",
        }

    def _get_oracle_database_files_storage_data(self) -> Dict[str, Any]:
        rows = self.connector.get_database_files_storage()
        formatted_rows = self._normalize_rows(rows, ["file_type", "file_count"])
        return {
            "title": "53. Database Files And Storage",
            "headers": ["File Type Category", "File Count"],
            "rows": formatted_rows,
            "note": "Database files summary by file type.",
        }

    def _get_oracle_unqueryable_oracle_info_data(self) -> Dict[str, Any]:
        rows = self.connector.get_unqueryable_oracle_info()
        formatted_rows = self._normalize_rows(rows, ["component", "note"])
        return {
            "title": "55. What Oracle Queries Cannot Tell You",
            "headers": ["Infrastructure Category", "Description / Recommendation"],
            "rows": formatted_rows,
            "note": "Infrastructure assessment requirements beyond SQL data dictionary.",
        }

    def _get_oracle_storage_growth_snapshots_data(self) -> Dict[str, Any]:
        rows = self.connector.get_storage_growth_snapshots()
        formatted_rows = self._normalize_rows(rows, ["snapshot_id", "begin_interval_time", "end_interval_time"])
        return {
            "title": "56. Most Important: Storage Growth",
            "headers": ["Snapshot ID", "Begin Interval Time", "End Interval Time"],
            "rows": formatted_rows,
            "note": "AWR snapshot intervals for calculating database growth over time.",
        }

    def _get_oracle_data_age_analysis_data(self) -> Dict[str, Any]:
        rows = self.connector.get_data_age_analysis()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "column_name", "data_type"])
        return {
            "title": "57. Data Age Analysis",
            "headers": ["Schema", "Table Name", "Date/Time Column", "Data Type"],
            "rows": formatted_rows,
            "note": "Date and timestamp columns inventory for data aging.",
        }

    def _get_oracle_archival_candidates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_archival_candidates()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "partitioned", "num_rows", "inserts", "updates", "deletes", "last_analyzed", "last_modified"])
        return {
            "title": "54. Identify Archival Candidates",
            "headers": ["Schema", "Table Name", "Partitioned", "Rows (Est)", "Inserts", "Updates", "Deletes", "Last Analyzed", "Last Modified"],
            "rows": formatted_rows,
            "note": "Large tables (>10k rows) with minimal DML modifications (<=100) identified for archiving.",
        }

    def _get_oracle_limited_usage_tables_data(self) -> Dict[str, Any]:
        rows = self.connector.get_limited_usage_tables()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "inserts", "updates", "deletes", "last_modified"])
        return {
            "title": "55. Identify Tables With Limited Usage",
            "headers": ["Schema", "Table Name", "Inserts", "Updates", "Deletes", "Last Modified"],
            "rows": formatted_rows,
            "note": "Tables with minimal recorded DML modifications.",
        }

    def _get_oracle_hot_tables_objects_data(self) -> Dict[str, Any]:
        rows = self.connector.get_hot_tables_objects()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "inserts", "updates", "deletes", "last_modified"])
        return {
            "title": "56. Identify Hot Tables / Objects",
            "headers": ["Schema", "Table Name", "Inserts", "Updates", "Deletes", "Last Modified"],
            "rows": formatted_rows,
            "note": "Top active workload tables ranked by DML modifications.",
        }

    def _get_oracle_fragmentation_candidates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_fragmentation_candidates()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "segment_name", "segment_type", "size_mb", "size_gb"])
        return {
            "title": "57. Segment Space / Fragmentation Candidates",
            "headers": ["Schema", "Segment Name", "Segment Type", "Size (MB)", "Size (GB)"],
            "rows": formatted_rows,
            "note": "Segment space allocation and fragmentation candidates.",
        }

    def _get_oracle_foreign_key_dependency_graph_data(self) -> Dict[str, Any]:
        rows = self.connector.get_foreign_key_dependency_graph()
        formatted_rows = self._normalize_rows(rows, ["schema_name", "table_name", "column_name", "referenced_schema", "referenced_table", "referenced_column"])
        return {
            "title": "58. Foreign-Key Dependency Graph",
            "headers": ["Child Schema", "Child Table", "Child Column", "Ref Schema", "Ref Table", "Ref Column"],
            "rows": formatted_rows,
            "note": "Referential dependency graph for migration sequencing.",
        }

    def _get_oracle_stored_code_dependencies_data(self) -> Dict[str, Any]:
        procs = self.connector.get_stored_procedures()
        funcs = self.connector.get_functions()
        pkgs = self.connector.get_packages()
        views = self.connector.get_views()
        triggers = self.connector.get_triggers()
        jobs = self.connector.get_scheduled_jobs()
        deps = self.connector.get_stored_code_dependencies()

        summary_rows = [
            ["Stored Procedures", str(len(procs))],
            ["Functions", str(len(funcs))],
            ["Packages & Package Bodies", str(len(pkgs))],
            ["Database Views", str(len(views))],
            ["Database Triggers", str(len(triggers))],
            ["Scheduler Jobs", str(len(jobs))],
        ]

        for d in deps:
            obj_type = d.get("object_type") or "-"
            dep_cnt = d.get("dependency_count") or 0
            summary_rows.append([f"Dependencies ({obj_type})", str(dep_cnt)])

        return {
            "title": "61. Stored Code Dependencies",
            "headers": ["Programmability Object / Dependency Type", "Total Count"],
            "rows": summary_rows,
            "note": "Summary counts of Oracle stored procedures, functions, packages, views, triggers, jobs, and code dependencies.",
        }

    def _get_oracle_configuration_assessment_data(self) -> Dict[str, Any]:
        rows = self.connector.get_configuration_assessment()
        formatted_rows = self._normalize_rows(rows, ["name", "value", "display_value"])
        return {
            "title": "62. Configuration Assessment (Top 10)",
            "headers": ["Parameter Name", "Value", "Display Value"],
            "rows": formatted_rows,
            "note": "Top 10 key Oracle database initialization parameters from V$PARAMETER.",
        }


    def _format_size(self, size_bytes: Any) -> str:

        if size_bytes in {None, ""}:
            return "-"

        try:
            size = float(size_bytes)
        except (TypeError, ValueError):
            return str(size_bytes)

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.2f} {unit}"
            size /= 1024

        return f"{size:.2f} PB"

    def _format_numeric_value(self, value: Any) -> str:
        if value is None or value == "":
            return "-"
        import decimal
        if isinstance(value, (float, decimal.Decimal)):
            try:
                return f"{float(value):.2f}"
            except Exception:
                pass
        val_str = str(value)
        import re
        if re.fullmatch(r"^-?\d+\.\d+$", val_str):
            try:
                return f"{float(val_str):.2f}"
            except Exception:
                pass
        m = re.fullmatch(r"^(-?\d+\.\d+)\s*([A-Za-z%]+.*)$", val_str)
        if m:
            try:
                num = float(m.group(1))
                unit = m.group(2)
                return f"{num:.2f} {unit}"
            except Exception:
                pass
        return val_str

    def _normalize_rows(
        self,
        rows: List[Dict[str, Any]],
        columns: List[str],
        size_columns: set[str] | None = None,
    ) -> List[List[str]]:

        size_columns = size_columns or set()
        normalized_rows: List[List[str]] = []

        for row in rows:
            normalized_row: List[str] = []

            for column in columns:
                value = row.get(column, "-")

                if column in size_columns:
                    normalized_row.append(self._format_size(value))
                else:
                    normalized_row.append(self._format_numeric_value(value))

            normalized_rows.append(normalized_row)

        return normalized_rows

    def _print_name_rows(
        self,
        headers: List[str],
        rows: List[List[str]],
        column_widths: List[int] | None = None,
    ) -> None:

        if not rows:
            print("No records found.")
            return

        widths = column_widths or [max(len(header), 12) for header in headers]
        header_line = " | ".join(
            f"{headers[index]:<{widths[index]}}" for index in range(len(headers))
        )
        separator = "-+-".join("-" * widths[index] for index in range(len(headers)))

        print(header_line)
        print(separator)

        for row in rows:
            print(
                " | ".join(
                    f"{(row[index] if index < len(row) else '-'):<{widths[index]}}"
                    for index in range(len(headers))
                )
            )

    def _show_paginated_table_report(
        self,
        title: str,
        headers: List[str],
        rows: List[List[str]],
        page_size: int = 100,
        note: str | None = None,
        paginate: bool = True,
    ) -> None:

        print(f"\n{'=' * 80}")
        print(f" {title}")
        print(f"{'=' * 80}")

        if note:
            print(f"Note: {note}\n")

        if not rows:
            self._print_name_rows(headers, rows)
            return

        column_widths = [
            max(
                len(headers[i]),
                max((len(str(row[i])) for row in rows if i < len(row)), default=0),
            )
            for i in range(len(headers))
        ]

        total_rows = len(rows)

        if total_rows <= page_size or not paginate:
            self._print_name_rows(headers, rows, column_widths)
            print(f"\nTotal Records: {total_rows}")
        else:
            current_index = 0
            page_num = 1
            total_pages = (total_rows + page_size - 1) // page_size

            while current_index < total_rows:
                page_rows = rows[current_index : current_index + page_size]
                end_index = min(current_index + page_size, total_rows)

                print(
                    f"\nPage {page_num} of {total_pages} (Records {current_index + 1}-{end_index} of {total_rows}):"
                )
                print("-" * 80)
                self._print_name_rows(headers, page_rows, column_widths)

                current_index += page_size
                page_num += 1

                if current_index < total_rows:
                    user_input = (
                        input(
                            "\nPress Enter for next page, 'a' for all remaining, or 'q' to quit: "
                        )
                        .strip()
                        .lower()
                    )
                    if user_input in {"q", "quit"}:
                        print("\nExiting report.")
                        return
                    elif user_input in {"a", "all"}:
                        remaining_rows = rows[current_index:]
                        print(
                            f"\nRemaining Records ({current_index + 1}-{total_rows}):"
                        )
                        print("-" * 80)
                        self._print_name_rows(headers, remaining_rows, column_widths)
                        break

            print(f"\nTotal Records: {total_rows}")

    def _format_count(self, value: Any) -> str:

        try:
            return f"{int(float(value)):,}"
        except (TypeError, ValueError):
            return "-"

    def _coerce_number(self, value: Any) -> float:

        try:
            if value in {None, ""}:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _get_mysql_database_count_data(self) -> Dict[str, Any]:
        if hasattr(self.connector, "get_database_inventory_sizes"):
            db_data = self.connector.get_database_inventory_sizes()
        else:
            names = self.connector.get_database_names()
            db_data = [
                {
                    "schema_name": name,
                    "tables_count": 0,
                    "data_bytes": 0,
                    "index_bytes": 0,
                    "total_size_bytes": 0,
                }
                for name in names
            ]

        rows = []
        total_tables = 0
        total_data_bytes = 0
        total_index_bytes = 0
        total_bytes = 0

        for item in db_data:
            schema_name = item.get("schema_name", "-")
            tables = int(item.get("tables_count") or 0)
            data_b = int(item.get("data_bytes") or 0)
            idx_b = int(item.get("index_bytes") or 0)
            size_b = int(item.get("total_size_bytes") or 0)

            total_tables += tables
            total_data_bytes += data_b
            total_index_bytes += idx_b
            total_bytes += size_b

            data_mb = round(data_b / (1024 * 1024), 2)
            idx_mb = round(idx_b / (1024 * 1024), 2)
            size_mb = round(size_b / (1024 * 1024), 2)
            size_gb = round(size_b / (1024 * 1024 * 1024), 2)

            rows.append([
                schema_name,
                tables,
                f"{data_mb:.2f}",
                f"{idx_mb:.2f}",
                f"{size_mb:.2f}",
                f"{size_gb:.2f}",
            ])

        total_row = [
            "TOTAL",
            total_tables,
            f"{round(total_data_bytes / (1024 * 1024), 2):.2f}",
            f"{round(total_index_bytes / (1024 * 1024), 2):.2f}",
            f"{round(total_bytes / (1024 * 1024), 2):.2f}",
            f"{round(total_bytes / (1024 * 1024 * 1024), 2):.2f}",
        ]
        rows.append(total_row)

        return {
            "title": f"2. Database/Schema Inventory ({len(db_data)} Databases)",
            "headers": [
                "Database Name",
                "Tables",
                "Data Size (MB)",
                "Index Size (MB)",
                "Total Size (MB)",
                "Total Size (GB)",
            ],
            "rows": rows,
            "note": "System schemas are excluded. Total DB size is aggregated at the bottom row.",
        }

    def _get_mysql_table_count_data(self) -> Dict[str, Any]:
        tables = self.connector.get_table_names()
        rows = [[row["schema_name"], row["table_name"]] for row in tables]
        return {
            "title": f"No Of Tables ({len(tables)})",
            "headers": ["Database", "Table"],
            "rows": rows,
            "note": "Base tables only. Views are excluded.",
        }

    def _get_mysql_table_sizes_data(self, order_by_size: bool = False) -> Dict[str, Any]:
        rows = (
            self.connector.get_tables_by_size_desc()
            if order_by_size
            else self.connector.get_table_sizes()
        )
        title = "Table Wise Size in Descending Order" if order_by_size else "Each Table Size"
        formatted_rows = self._normalize_rows(
            rows,
            [
                "schema_name",
                "table_name",
                "row_count",
                "data_size_bytes",
                "index_size_bytes",
                "total_size_bytes",
            ],
            size_columns={"data_size_bytes", "index_size_bytes", "total_size_bytes"},
        )
        return {
            "title": title,
            "headers": ["Database", "Table", "Rows", "Data Size", "Index Size", "Total Size"],
            "rows": formatted_rows,
            "note": "Tables are ordered by size when requested.",
        }

    def _get_mysql_index_sizes_data(self) -> Dict[str, Any]:
        rows = self.connector.get_index_sizes()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "schema_name",
                "table_name",
                "index_name",
                "non_unique",
                "index_type",
                "columns",
            ],
        )
        return {
            "title": "16. All Indexes",
            "headers": ["Database", "Table", "Index Name", "Non Unique", "Index Type", "Columns"],
            "rows": formatted_rows,
            "note": "Complete index inventory from information_schema.statistics.",
        }

    def _get_mysql_row_counts_data(self) -> Dict[str, Any]:
        rows = self.connector.get_table_row_counts()
        formatted_rows = self._normalize_rows(
            rows,
            ["schema_name", "table_name", "row_count"],
        )
        return {
            "title": "6. Table Row Counts",
            "headers": ["Database", "Table", "Rows"],
            "rows": formatted_rows,
            "note": "MySQL row counts from information_schema.tables (estimates for InnoDB).",
        }

    def _get_mysql_creation_dates_data(self) -> Dict[str, Any]:
        rows = self.connector.get_creation_dates()
        formatted_rows = self._normalize_rows(
            rows,
            [
                "schema_name",
                "table_name",
                "table_created",
                "index_name",
                "index_created",
            ],
        )
        return {
            "title": "Creation Date Of Tables And Indexes",
            "headers": ["Database", "Table", "Table Created", "Index", "Index Created"],
            "rows": formatted_rows,
            "note": "Index creation time is not stored directly by default.",
        }

    def display_unused_indexes(self, schema_name: str) -> None:

        try:
            if False:
                self._show_paginated_table_report(
                    "Unused Indexes",
                    ["Table", "Index", "Column", "Reads"],
                    [],
                    note="Snowflake does not expose a comparable unused index usage metric in this app.",
                )
                return

            rows = self.get_unused_indexes(schema_name)

            if not rows:
                self._show_paginated_table_report(
                    "Unused Indexes",
                    ["Table", "Index", "Column", "Reads"],
                    [],
                    note="No unused indexes were found, or no index usage information is available.",
                )
                return

            formatted_rows = self._normalize_rows(
                rows,
                ["table_name", "index_name", "column_name", "read_count"],
            )
            self._show_paginated_table_report(
                "Unused Indexes",
                ["Table", "Index", "Column", "Reads"],
                formatted_rows,
            )

            if self.database_type == "PostgreSQL":
                print(
                    "\nNote: An index is shown here when PostgreSQL "
                    "reports zero recorded scans in pg_stat_user_indexes."
                )
            elif self.database_type == "SQL Server":
                print(
                    "\nNote: SQL Server usage stats are based on "
                    "sys.dm_db_index_usage_stats since the last engine restart."
                )
            elif self.database_type == "Oracle":
                print(
                    "\nNote: Oracle usage stats depend on index monitoring "
                    "being enabled in V$OBJECT_USAGE."
                )
            elif False:
                print(
                    "\nNote: Snowflake does not expose a comparable unused "
                    "index usage metric in this app."
                )
            else:
                print(
                    "\nNote: An index is shown here when MySQL "
                    "performance_schema reports zero recorded reads."
                )

        except Exception as exc:
            logger.error("Unable to retrieve unused indexes: %s", exc)
            print("\nUnable to retrieve unused indexes.")
            if self.database_type == "PostgreSQL":
                print("Make sure PostgreSQL statistics views are available.")
            elif self.database_type == "SQL Server":
                print("Make sure SQL Server DMV permissions are available.")
            elif self.database_type == "Oracle":
                print("Make sure Oracle index monitoring is enabled.")
            elif False:
                print(
                    "Snowflake does not expose a comparable unused index "
                    "usage metric in this app."
                )
            else:
                print("Make sure MySQL performance_schema is enabled.")

    def display_tables_by_row_count(self, schema_name: str) -> None:

        while True:
            try:
                limit = int(
                    input("How many tables do you want to display? " "[10]: ").strip()
                    or "10"
                )

                if limit > 0:
                    break

                print("Enter a number greater than 0.")

            except ValueError:
                print("Please enter a valid number.")

        try:
            rows = self.get_tables_by_row_count(schema_name, limit)

            if not rows:
                self._show_paginated_table_report(
                    "Tables With More Rows",
                    ["Table", "Rows"],
                    [],
                    note="No tables found.",
                )
                return

            formatted_rows = self._normalize_rows(rows, ["table_name", "row_count"])
            self._show_paginated_table_report(
                f"Tables With More Rows (Top {limit})",
                ["Table", "Rows"],
                formatted_rows,
            )

            if self.database_type == "PostgreSQL":
                print("\nNote: n_live_tup is an estimate maintained by PostgreSQL.")
            elif self.database_type == "SQL Server":
                print(
                    "\nNote: row_count comes from sys.dm_db_partition_stats "
                    "and is an approximate count."
                )
            elif self.database_type == "Oracle":
                print(
                    "\nNote: NUM_ROWS is statistics-based and may be stale "
                    "until table statistics are refreshed."
                )
            elif False:
                print(
                    "\nNote: ROW_COUNT comes from Snowflake Information "
                    "Schema for the current database."
                )
            else:
                print(
                    "\nNote: TABLE_ROWS for InnoDB tables is an "
                    "estimate maintained by MySQL."
                )

        except Exception as exc:
            logger.error("Unable to retrieve table row counts: %s", exc)
            print("\nUnable to retrieve table row counts.")

    def display_tables_with_zero_indexes(self, schema_name: str) -> None:

        try:
            rows = self.get_tables_with_zero_indexes(schema_name)

            if not rows:
                self._show_paginated_table_report(
                    "Tables With Zero Indexes",
                    ["Table"],
                    [],
                    note="No tables with zero indexes were found.",
                )
                return

            formatted_rows = self._normalize_rows(rows, ["table_name"])
            self._show_paginated_table_report(
                "Tables With Zero Indexes",
                ["Table"],
                formatted_rows,
            )

            if self.database_type == "PostgreSQL":
                print(
                    "\nNote: This lists tables with no entries in pg_index "
                    "other than the primary key, if any."
                )
            elif self.database_type == "SQL Server":
                print(
                    "\nNote: This lists tables without secondary, "
                    "non-primary indexes."
                )
            elif self.database_type == "Oracle":
                print("\nNote: This lists tables without rows in ALL_INDEXES.")
            elif False:
                print(
                    "\nNote: This lists tables without indexes in "
                    "INFORMATION_SCHEMA.INDEXES."
                )

        except Exception as exc:
            logger.error("Unable to retrieve tables with zero indexes: %s", exc)
            print("\nUnable to retrieve tables with zero indexes.")

    def run_insights(self, schema_name: str) -> None:

        while True:

            choice = self.display_insight_menu()

            if choice == "1":
                self.display_unused_indexes(schema_name)

            elif choice == "2":
                self.display_tables_by_row_count(schema_name)

            elif choice == "3":
                self.display_tables_with_zero_indexes(schema_name)

            elif choice == "4":
                print("\nExiting database insights.")
                break

    # Read Table Using Pyspark

    def read_table_data(self, schema_name: str, table_name: str):
        if not self.connector:
            raise RuntimeError("Database is not connected.")

        if self.spark is None:
            from pyspark.sql import SparkSession

            builder = SparkSession.builder.appName("DatabaseMetadataExplorer").config(
                "spark.ui.showConsoleProgress", "false"
            )

            jdbc_jar = self._get_spark_jdbc_jar_path()

            if jdbc_jar:
                builder = builder.config("spark.driver.extraClassPath", jdbc_jar)

            self.spark = builder.getOrCreate()
            self.spark.sparkContext.setLogLevel("ERROR")

        jdbc_url = self.connector.get_jdbc_url()

        jdbc_properties = self.connector.get_jdbc_properties()

        def quote_double(value: str) -> str:
            return '"' + value.replace('"', '""') + '"'

        def quote_brackets(value: str) -> str:
            return "[" + value.replace("]", "]]") + "]"

        if self.database_type == "PostgreSQL":
            qualified_table = f"{quote_double(schema_name)}.{quote_double(table_name)}"
        elif self.database_type == "MySQL":
            qualified_table = (
                f"`{schema_name.replace('`', '``')}`."
                f"`{table_name.replace('`', '``')}`"
            )
        elif self.database_type == "SQL Server":
            qualified_table = (
                f"{quote_brackets(schema_name)}.{quote_brackets(table_name)}"
            )
        elif self.database_type == "Oracle":
            qualified_table = f"{schema_name.upper()}.{table_name.upper()}"
        elif False:
            qualified_table = f"{quote_double(schema_name)}.{quote_double(table_name)}"
        else:
            qualified_table = f"{schema_name}.{table_name}"

        logger.info("Reading table using PySpark JDBC: %s", qualified_table)

        df = (
            self.spark.read.format("jdbc")
            .option("url", jdbc_url)
            .option("dbtable", qualified_table)
            .options(**jdbc_properties)
            .load()
        )

        return df

    def _get_spark_jdbc_jar_path(self) -> str | None:

        jdbc_jars = {
            "MySQL": "mysql-connector-j-9.7.0.jar",
            "PostgreSQL": "postgresql-42.7.13.jar",
            "SQL Server": "mssql-jdbc-13.4.0.jre11.jar",
            "Oracle": "ojdbc8.jar",
        }

        if not self.database_type:
            return None

        jar_name = jdbc_jars.get(self.database_type)

        if not jar_name:
            return None

        return str(Path(__file__).resolve().parent / "jdbc-drivers" / jar_name)

    # Display Sample Data

    def display_sample_data(self, schema_name: str, table_name: str) -> None:

        print("\nSAMPLE DATA")
        print("-" * 80)

        try:
            if not self.connector:
                raise RuntimeError("Database is not connected.")

            rows = self.connector.get_sample_data(schema_name, table_name, limit=10)

            if not rows:
                print("Table contains no rows.")
                return

            self._display_rows(rows)

        except Exception as exc:
            logger.error("Unable to read sample data: %s", exc)

            print("\nUnable to read sample data.")

    def _display_rows(self, rows: List[Dict[str, Any]]) -> None:

        if not rows:
            print("No rows to display.")
            return

        columns = list(rows[0].keys())
        widths = {
            column: min(
                max(len(str(column)), *(len(str(row.get(column, ""))) for row in rows)),
                40,
            )
            for column in columns
        }

        header = " | ".join(
            f"{column[:widths[column]]:<{widths[column]}}" for column in columns
        )
        separator = "-+-".join("-" * widths[column] for column in columns)

        print(header)
        print(separator)

        for row in rows:
            print(
                " | ".join(
                    f"{str(row.get(column, ''))[:widths[column]]:<{widths[column]}}"
                    for column in columns
                )
            )

    # Table Selection

    def select_table(self, tables: List[str]) -> List[str]:

        print("\nAvailable Tables")
        print("-" * 40)

        for index, table in enumerate(tables, start=1):
            print(f"{index}. {table}")

        print(f"{len(tables) + 1}. Process all tables")

        while True:

            try:

                choice = int(input("\nSelect table: ").strip())

                if 1 <= choice <= len(tables):

                    return [tables[choice - 1]]

                if choice == len(tables) + 1:

                    return tables

                print("Invalid selection.")

            except ValueError:

                print("Please enter a valid number.")

    # Close Connection

    def close_connection(self) -> None:

        if self.connector:

            self.connector.close()

            logger.info("Database connection closed.")

        if self.spark:

            self.spark.stop()

            logger.info("Spark session stopped.")

    # Main Run Method

    def run(self) -> None:

        try:
            self.display_database_options()

            self.database_type = self.get_database_choice()

            self.credentials = self.get_credentials(self.database_type)

            print("\nConnecting...")

            self.create_connection(self.database_type, self.credentials)

            print("\nConnection successful!")

            if self.database_type == "MySQL":
                print("\n========================================")
                print("             MYSQL QUESTIONS")
                print("========================================")
                self.run_mysql_insights()
                return

            if self.database_type == "SQL Server":
                print("\n========================================")
                print("         SQL SERVER QUESTIONS")
                print("========================================")
                self.run_sqlserver_insights()
                return

            if self.database_type == "Oracle":
                print("\n========================================")
                print("            ORACLE QUESTIONS")
                print("========================================")
                self.run_oracle_insights()
                return

            database_name = self.credentials.get(
                "database", self.credentials.get("service_name", "-")
            )

            if self.database_type == "PostgreSQL":
                print("\n========================================")
                print("         POSTGRESQL QUESTIONS")
                print("========================================")
                self.run_postgres_insights()
                return

            schema_name = self.credentials.get("schema")

            print(f"\nDatabase : {database_name}")
            print(f"Schema   : {schema_name or '-'}")

            # Schema Selection

            if not schema_name:

                schemas = self.get_schemas()

                if not schemas:
                    print("\nNo schemas found.")
                    return

                print("\nAvailable Schemas")
                print("-" * 40)

                for index, schema in enumerate(schemas, start=1):
                    print(f"{index}. {schema}")

                while True:
                    try:
                        schema_choice = int(input("\nSelect schema: ").strip())

                        if 1 <= schema_choice <= len(schemas):
                            schema_name = schemas[schema_choice - 1]
                            break

                        print("Invalid schema selection.")

                    except ValueError:
                        print("Please enter a valid number.")

            # Table List First

            tables = self.get_tables(schema_name)

            if not tables:
                print(f"\nNo tables found in " f"schema '{schema_name}'.")
                return

            selected_tables = self.select_table(tables)

            # Metadata + Sample Data

            for table_name in selected_tables:

                print("\n========================================")
                print(f"Table: {table_name}")
                print("========================================")

                metadata = self.get_data_dictionary(schema_name, table_name)

                self.display_table_metadata(metadata)

                self.display_sample_data(schema_name, table_name)

            # Insights After Table Data

            if self.database_type in {
                "MySQL",
                "PostgreSQL",
                "SQL Server",
                "Oracle",
                            }:

                print("\n\n========================================")
                print("           DATABASE INSIGHTS")
                print("========================================")

                self.run_insights(schema_name)

        except ValueError as exc:

            logger.error("Invalid input: %s", exc)

            print(f"\nInvalid input: {exc}")

        except Exception as exc:

            logger.error("Application error: %s", exc)

            print("\nUnable to complete the operation.")

            print(
                "Please verify your credentials, "
                "database, schema, permissions, "
                "and JDBC configuration."
            )

        finally:

            self.close_connection()

    # =========================================================================
    # EXPLICIT DASHBOARD KPI DELEGATED METHODS
    # =========================================================================

    def get_top_slow_queries_by_wait_time(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Delegates Top Slow Queries by wait time collection to active database connector."""
        if self.connector and hasattr(self.connector, "get_top_slow_queries_by_wait_time"):
            return self.connector.get_top_slow_queries_by_wait_time(limit=limit)
        elif self.connector and hasattr(self.connector, "get_slow_queries"):
            return self.connector.get_slow_queries(limit=limit)
        return []

    def get_cpu_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Delegates CPU Utilization KPI collection to active database connector."""
        if self.connector and hasattr(self.connector, "get_cpu_kpi"):
            return self.connector.get_cpu_kpi(time_range)
        return {
            "value": 0.0, "current_str": "0.0%", "status": "Normal", "avg": 0.0,
            "avg_str": "0.0%", "peak": 0.0, "peak_str": "0.0%", "period_str": "Last 1 Hour",
            "insight": "CPU utilization metric unavailable."
        }

    def get_iops_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Delegates I/O Operations KPI collection to active database connector."""
        if self.connector and hasattr(self.connector, "get_iops_kpi"):
            return self.connector.get_iops_kpi(time_range)
        return {
            "value": 0, "current_str": "0", "status": "Healthy", "avg": 0,
            "avg_str": "0", "peak": 0, "peak_str": "0", "period_str": "Last 1 Hour",
            "insight": "I/O operations metric unavailable."
        }

    def get_active_connections_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Delegates Active Connections KPI collection to active database connector."""
        if self.connector and hasattr(self.connector, "get_active_connections_kpi"):
            return self.connector.get_active_connections_kpi(time_range)
        return {
            "value": 0, "current_val": 0, "peak_val": 0, "max_connections": 100,
            "utilization_pct": 0.0, "status": "Normal", "period_str": "Last 1 Hour",
            "insight": "0 active connection(s) currently connected."
        }

    def get_qps_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Delegates Throughput (QPS) KPI collection to active database connector."""
        if self.connector and hasattr(self.connector, "get_qps_kpi"):
            return self.connector.get_qps_kpi(time_range)
        return {
            "value": 0, "avg_qps": 0, "total_queries": "0", "status": "Normal",
            "period_str": "Last 1 Hour", "insight": "Average throughput rate is 0 QPS."
        }

    def get_storage_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Delegates Database Storage Footprint KPI collection to active database connector."""
        if self.connector and hasattr(self.connector, "get_storage_kpi"):
            return self.connector.get_storage_kpi(time_range)
        return {
            "value": "N/A", "current_size": "N/A", "table_count": 0, "growth": "+0.00 MB",
            "period_str": "Last 1 Hour", "status": "Normal",
            "insight": "Storage footprint metric unavailable."
        }

    def get_blocked_sessions_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Delegates Blocked Sessions KPI collection to active database connector."""
        if self.connector and hasattr(self.connector, "get_blocked_sessions_kpi"):
            return self.connector.get_blocked_sessions_kpi(time_range)
        return {
            "count": 0, "current_count": 0, "peak_count": 0, "status": "Normal",
            "status_text": "No Blocking", "period_str": "Last 1 Hour",
            "insight": "No lock contention or blocked sessions currently detected."
        }
