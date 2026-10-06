"""
MySQL Database Insights & Dynamic SQL Queries
Auto-documented query methods and metadata reference for MySQL.
"""

import re
from typing import Any, Dict, List, Optional

INSIGHTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "MySQL Environment and Server Information",
        "method": "MySQLConnector.get_environment_info()",
        "description": "Environment and server configuration settings.",
        "headers": [
            "Version",
            "Comment",
            "Hostname",
            "Port",
            "Data Directory",
            "InnoDB Home"
        ],
        "category": "I/O",
        "query": "SELECT\n                @@version AS mysql_version,\n                @@version_comment AS version_comment,\n                @@hostname AS hostname,\n                @@port AS port,\n                @@datadir AS data_directory,\n                @@innodb_data_home_dir AS innodb_data_home_dir"
    },
    {
        "id": 2,
        "title": "Database/schema inventory (0 Databases)",
        "method": "MySQLConnector.get_database_inventory_sizes()",
        "description": "System schemas are excluded. Total DB size is aggregated at the bottom row.",
        "headers": [
            "Database Schema",
            "DB Size"
        ],
        "category": "Overview",
        "query": "SELECT \n                s.SCHEMA_NAME AS schema_name,\n                COALESCE(SUM(t.DATA_LENGTH + t.INDEX_LENGTH), 0) AS total_size_bytes\n            FROM INFORMATION_SCHEMA.SCHEMATA s\n            LEFT JOIN INFORMATION_SCHEMA.TABLES t \n                ON s.SCHEMA_NAME = t.TABLE_SCHEMA\n            WHERE {self._system_schema_filter()}\n            GROUP BY s.SCHEMA_NAME\n            ORDER BY total_size_bytes DESC, s.SCHEMA_NAME"
    },
    {
        "id": 3,
        "title": "Table-level storage analysis",
        "method": "MySQLConnector.get_table_level_storage_analysis()",
        "description": "All tables by size ordered by (data_length + index_length) DESC.",
        "headers": [
            "Database",
            "Table",
            "Engine",
            "Rows",
            "Data (MB)",
            "Index (MB)",
            "Total (MB)",
            "Data (GB)",
            "Index (GB)",
            "Total (GB)"
        ],
        "category": "Storage",
        "query": "SELECT \n    table_schema, \n    table_name, \n    engine, \n    table_rows, \n    ROUND(data_length / 1024 / 1024, 2) AS data_mb, \n    ROUND(index_length / 1024 / 1024, 2) AS index_mb, \n    ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb, \n    ROUND(data_length / 1024 / 1024 / 1024, 2) AS data_gb, \n    ROUND(index_length / 1024 / 1024 / 1024, 2) AS index_gb, \n    ROUND((data_length + index_length) / 1024 / 1024 / 1024, 2) AS total_gb \nFROM information_schema.tables \nWHERE table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nAND table_type = 'BASE TABLE'\nORDER BY (data_length + index_length) DESC;"
    },
    {
        "id": 4,
        "title": "Data vs index storage",
        "method": "MySQLConnector.get_data_vs_index_footprint()",
        "description": "Aggregated data vs index footprint across non-system schemas.",
        "headers": [
            "Data (MB)",
            "Index (MB)",
            "Total (MB)",
            "Data (GB)",
            "Index (GB)",
            "Total (GB)",
            "Data (TB)",
            "Index (TB)",
            "Total (TB)"
        ],
        "category": "Storage",
        "query": "SELECT\n    ROUND(SUM(data_length) / 1024 / 1024, 2) AS data_mb,\n    ROUND(SUM(index_length) / 1024 / 1024, 2) AS index_mb,\n    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS total_mb,\n    ROUND(SUM(data_length) / 1024 / 1024 / 1024, 4) AS data_gb,\n    ROUND(SUM(index_length) / 1024 / 1024 / 1024, 4) AS index_gb,\n    ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 4) AS total_gb,\n    ROUND(SUM(data_length) / 1024 / 1024 / 1024 / 1024, 6) AS data_tb,\n    ROUND(SUM(index_length) / 1024 / 1024 / 1024 / 1024, 6) AS index_tb,\n    ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024 / 1024, 6) AS total_tb\nFROM information_schema.tables\nWHERE table_schema NOT IN\n('information_schema','mysql','performance_schema','sys')\nAND table_type = 'BASE TABLE';"
    },
    {
        "id": 5,
        "title": "Top 100 largest tables",
        "method": "MySQLConnector.get_top_100_largest_tables()",
        "description": "Top 100 largest tables ordered by total storage size.",
        "headers": [
            "Database",
            "Table",
            "Engine",
            "Data Size (MB)",
            "Index Size (MB)",
            "Total Size (MB)",
            "Total Size (GB)"
        ],
        "category": "Overview",
        "query": "SELECT\n    table_schema,\n    table_name,\n    engine,\n    ROUND(data_length / 1024 / 1024, 2) AS data_mb,\n    ROUND(index_length / 1024 / 1024, 2) AS index_mb,\n    ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb,\n    ROUND((data_length + index_length) / 1024 / 1024 / 1024, 4) AS total_gb\nFROM information_schema.tables\nWHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')\nAND table_type = 'BASE TABLE'\nORDER BY (data_length + index_length) DESC\nLIMIT 100;"
    },
    {
        "id": 6,
        "title": "Table row counts",
        "method": "MySQLConnector.get_table_row_counts()",
        "description": "MySQL row counts from information_schema.tables (estimates for InnoDB).",
        "headers": [
            "Database",
            "Table",
            "Rows"
        ],
        "category": "Overview",
        "query": "SELECT\n    table_schema,\n    table_name,\n    table_rows\nFROM information_schema.tables\nWHERE table_schema NOT IN\n('information_schema','mysql','performance_schema','sys')\nORDER BY table_rows DESC;"
    },
    {
        "id": 7,
        "title": "Storage breakdown by storage engine",
        "method": "MySQLConnector.get_storage_by_engine()",
        "description": "Breakdown of storage across storage engines (InnoDB, MyISAM, etc.).",
        "headers": [
            "Engine",
            "Table Count",
            "Data (MB)",
            "Index (MB)",
            "Total (MB)",
            "Data (GB)",
            "Index (GB)",
            "Total (GB)"
        ],
        "category": "Storage",
        "query": "SELECT \n    engine, \n    COUNT(*) AS table_count, \n    ROUND(SUM(data_length) / 1024 / 1024, 2) AS data_mb, \n    ROUND(SUM(index_length) / 1024 / 1024, 2) AS index_mb, \n    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS total_mb, \n    ROUND(SUM(data_length) / 1024 / 1024 / 1024, 2) AS data_gb, \n    ROUND(SUM(index_length) / 1024 / 1024 / 1024, 2) AS index_gb, \n    ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2) AS total_gb \nFROM information_schema.tables \nWHERE table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nAND table_type = 'BASE TABLE'\nAND engine IS NOT NULL\nGROUP BY engine \nORDER BY SUM(data_length + index_length) DESC;"
    },
    {
        "id": 8,
        "title": "Check tables that aren't InnoDB",
        "method": "MySQLConnector.get_non_innodb_tables()",
        "description": "Tables using non-InnoDB engines (MyISAM, MEMORY, CSV, etc.).",
        "headers": [
            "Database",
            "Table",
            "Engine",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Overview",
        "query": "SELECT \n    table_schema, \n    table_name, \n    engine, \n    ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb, \n    ROUND((data_length + index_length) / 1024 / 1024 / 1024, 2) AS size_gb \nFROM information_schema.tables \nWHERE table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nAND table_type = 'BASE TABLE'\nAND engine <> 'InnoDB' \nORDER BY (data_length + index_length) DESC;"
    },
    {
        "id": 9,
        "title": "Detailed Partition Configuration and Sizes",
        "method": "MySQLConnector.get_detailed_partitions()",
        "description": "Partition mapping and individual partition storage details.",
        "headers": [
            "Database",
            "Table",
            "Partition",
            "Method",
            "Expression",
            "Rows",
            "Data Size",
            "Index Size"
        ],
        "category": "Storage",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                PARTITION_NAME AS partition_name,\n                PARTITION_METHOD AS partition_method,\n                PARTITION_EXPRESSION AS partition_expression,\n                TABLE_ROWS AS row_count,\n                DATA_LENGTH AS data_size_bytes,\n                INDEX_LENGTH AS index_size_bytes\n            FROM INFORMATION_SCHEMA.PARTITIONS\n            WHERE PARTITION_NAME IS NOT NULL\n              AND {self._system_table_filter('TABLE_SCHEMA')}\n            ORDER BY TABLE_SCHEMA, TABLE_NAME, PARTITION_ORDINAL_POSITION"
    },
    {
        "id": 10,
        "title": "Master (Parent) tables",
        "method": "MySQLConnector.get_master_tables()",
        "description": "Tables referenced by foreign key constraints in child tables.",
        "headers": [
            "Database",
            "Master Table Name",
            "Child FKs In",
            "Referencing Child Tables"
        ],
        "category": "Schema",
        "query": "SELECT \n                t.TABLE_SCHEMA AS schema_name,\n                t.TABLE_NAME AS table_name,\n                COALESCE(incoming.incoming_fk_count, 0) AS child_fk_count,\n                COALESCE(incoming.referencing_tables, '-') AS child_tables\n            FROM INFORMATION_SCHEMA.TABLES t\n            INNER JOIN (\n                SELECT \n                    REFERENCED_TABLE_SCHEMA AS TABLE_SCHEMA,\n                    REFERENCED_TABLE_NAME AS TABLE_NAME,\n                    COUNT(DISTINCT TABLE_NAME) AS incoming_fk_count,\n                    GROUP_CONCAT(DISTINCT TABLE_NAME ORDER BY TABLE_NAME SEPARATOR ', ') AS referencing_tables\n                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE\n                WHERE REFERENCED_TABLE_NAME IS NOT NULL\n                  AND {self._system_table_filter('REFERENCED_TABLE_SCHEMA')}\n                GROUP BY REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME\n            ) incoming ON t.TABLE_SCHEMA = incoming.TABLE_SCHEMA AND t.TABLE_NAME = incoming.TABLE_NAME\n            WHERE t.TABLE_TYPE = 'BASE TABLE'\n              AND {self._system_table_filter('t.TABLE_SCHEMA')}\n            ORDER BY incoming.incoming_fk_count DESC, t.TABLE_SCHEMA, t.TABLE_NAME"
    },
    {
        "id": 11,
        "title": "Child tables",
        "method": "MySQLConnector.get_child_tables()",
        "description": "Tables containing foreign key constraints pointing to parent tables.",
        "headers": [
            "Database",
            "Child Table Name",
            "Parent FKs Out",
            "Referenced Parent Tables"
        ],
        "category": "Schema",
        "query": "SELECT \n                t.TABLE_SCHEMA AS schema_name,\n                t.TABLE_NAME AS table_name,\n                COALESCE(outgoing.outgoing_fk_count, 0) AS parent_fk_count,\n                COALESCE(outgoing.referenced_tables, '-') AS parent_tables\n            FROM INFORMATION_SCHEMA.TABLES t\n            INNER JOIN (\n                SELECT \n                    TABLE_SCHEMA,\n                    TABLE_NAME,\n                    COUNT(DISTINCT REFERENCED_TABLE_NAME) AS outgoing_fk_count,\n                    GROUP_CONCAT(DISTINCT REFERENCED_TABLE_NAME ORDER BY REFERENCED_TABLE_NAME SEPARATOR ', ') AS referenced_tables\n                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE\n                WHERE REFERENCED_TABLE_NAME IS NOT NULL\n                  AND {self._system_table_filter('TABLE_SCHEMA')}\n                GROUP BY TABLE_SCHEMA, TABLE_NAME\n            ) outgoing ON t.TABLE_SCHEMA = outgoing.TABLE_SCHEMA AND t.TABLE_NAME = outgoing.TABLE_NAME\n            WHERE t.TABLE_TYPE = 'BASE TABLE'\n              AND {self._system_table_filter('t.TABLE_SCHEMA')}\n            ORDER BY outgoing.outgoing_fk_count DESC, t.TABLE_SCHEMA, t.TABLE_NAME"
    },
    {
        "id": 12,
        "title": "Independent tables",
        "method": "MySQLConnector.get_independent_tables()",
        "description": "Standalone tables with no foreign key relationships (neither parent nor child).",
        "headers": [
            "Database",
            "Independent Table Name"
        ],
        "category": "Overview",
        "query": "SELECT \n                t.TABLE_SCHEMA AS schema_name,\n                t.TABLE_NAME AS table_name\n            FROM INFORMATION_SCHEMA.TABLES t\n            LEFT JOIN (\n                SELECT DISTINCT TABLE_SCHEMA, TABLE_NAME\n                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE\n                WHERE REFERENCED_TABLE_NAME IS NOT NULL\n                  AND {self._system_table_filter('TABLE_SCHEMA')}\n            ) outgoing ON t.TABLE_SCHEMA = outgoing.TABLE_SCHEMA AND t.TABLE_NAME = outgoing.TABLE_NAME\n            LEFT JOIN (\n                SELECT DISTINCT REFERENCED_TABLE_SCHEMA AS TABLE_SCHEMA, REFERENCED_TABLE_NAME AS TABLE_NAME\n                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE\n                WHERE REFERENCED_TABLE_NAME IS NOT NULL\n                  AND {self._system_table_filter('REFERENCED_TABLE_SCHEMA')}\n            ) incoming ON t.TABLE_SCHEMA = incoming.TABLE_SCHEMA AND t.TABLE_NAME = incoming.TABLE_NAME\n            WHERE t.TABLE_TYPE = 'BASE TABLE'\n              AND {self._system_table_filter('t.TABLE_SCHEMA')}\n              AND outgoing.TABLE_NAME IS NULL\n              AND incoming.TABLE_NAME IS NULL\n            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME"
    },
    {
        "id": 13,
        "title": "Identify very large unpartitioned tables",
        "method": "MySQLConnector.get_large_unpartitioned_tables()",
        "description": "Unpartitioned tables sorted by total size for partitioning review.",
        "headers": [
            "Database",
            "Table",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "I/O",
        "query": "SELECT \n    table_schema, \n    table_name, \n    ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb, \n    ROUND((data_length + index_length) / 1024 / 1024 / 1024, 2) AS size_gb \nFROM information_schema.tables \nWHERE table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nAND table_type = 'BASE TABLE'\nAND table_name NOT IN ( \n    SELECT DISTINCT table_name \n    FROM information_schema.partitions \n    WHERE partition_name IS NOT NULL \n) \nORDER BY (data_length + index_length) DESC;"
    },
    {
        "id": 14,
        "title": "BLOB and TEXT Large Object Columns",
        "method": "MySQLConnector.get_large_object_columns()",
        "description": "Columns with BLOB, TEXT, or LONGTEXT data types.",
        "headers": [
            "Database",
            "Table",
            "Column",
            "Data Type",
            "Column Type"
        ],
        "category": "Structure",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                COLUMN_NAME AS column_name,\n                DATA_TYPE AS data_type,\n                COLUMN_TYPE AS column_type\n            FROM INFORMATION_SCHEMA.COLUMNS\n            WHERE {self._system_table_filter('TABLE_SCHEMA')}\n              AND DATA_TYPE IN ('tinyblob', 'blob', 'mediumblob', 'longblob', 'tinytext', 'text', 'mediumtext', 'longtext')\n            ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME"
    },
    {
        "id": 15,
        "title": "JSON Data Type Columns Inventory",
        "method": "MySQLConnector.get_json_columns()",
        "description": "Columns explicitly defined with JSON data type.",
        "headers": [
            "Database",
            "Table",
            "Column",
            "Column Type"
        ],
        "category": "Structure",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                COLUMN_NAME AS column_name,\n                COLUMN_TYPE AS column_type\n            FROM INFORMATION_SCHEMA.COLUMNS\n            WHERE DATA_TYPE = 'json'\n              AND {self._system_table_filter('TABLE_SCHEMA')}\n            ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME"
    },
    {
        "id": 16,
        "title": "Find generated columns",
        "method": "MySQLConnector.get_generated_columns()",
        "description": "Generated and virtual column definitions from information_schema.columns.",
        "headers": [
            "Database",
            "Table",
            "Column Name",
            "Generation Expression"
        ],
        "category": "Structure",
        "query": "SELECT \n    table_schema, \n    table_name, \n    column_name, \n    generation_expression \nFROM information_schema.columns \nWHERE generation_expression IS NOT NULL \n  AND generation_expression <> '' \n  AND table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nORDER BY table_schema, table_name, column_name;"
    },
    {
        "id": 17,
        "title": "Primary Keys Inventory",
        "method": "MySQLConnector.get_primary_keys()",
        "description": "Tables with defined PRIMARY KEY constraints.",
        "headers": [
            "Database",
            "Table",
            "Primary Key Columns"
        ],
        "category": "Indexes",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ', ') AS primary_key_columns\n            FROM INFORMATION_SCHEMA.STATISTICS\n            WHERE INDEX_NAME = 'PRIMARY'\n              AND {self._system_table_filter('TABLE_SCHEMA')}\n            GROUP BY TABLE_SCHEMA, TABLE_NAME\n            ORDER BY TABLE_SCHEMA, TABLE_NAME"
    },
    {
        "id": 18,
        "title": "Tables Without Primary Keys",
        "method": "MySQLConnector.get_tables_without_primary_keys()",
        "description": "Base tables created without a Primary Key constraint.",
        "headers": [
            "Database",
            "Table"
        ],
        "category": "Indexes",
        "query": "```python\ndef get_tables_without_primary_keys(self) -> List[Dict[str, Any]]:\n        return self.get_tables_without_clustered_indexes()\n```"
    },
    {
        "id": 19,
        "title": "All indexes",
        "method": "MySQLConnector.get_index_sizes()",
        "description": "Complete index inventory from information_schema.statistics.",
        "headers": [
            "Database",
            "Table",
            "Index Name",
            "Non Unique",
            "Index Type",
            "Columns"
        ],
        "category": "Indexes",
        "query": "SELECT \n    table_schema, \n    table_name, \n    index_name, \n    non_unique, \n    index_type, \n    GROUP_CONCAT( \n        column_name \n        ORDER BY seq_in_index \n    ) AS columns \nFROM information_schema.statistics \nWHERE table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nGROUP BY \n    table_schema, \n    table_name, \n    index_name, \n    non_unique, \n    index_type \nORDER BY table_schema, table_name, index_name;"
    },
    {
        "id": 20,
        "title": "Index count by table",
        "method": "MySQLConnector.get_tables_high_index_count()",
        "description": "Number of indexes per table from information_schema.statistics.",
        "headers": [
            "Database",
            "Table",
            "Index Count"
        ],
        "category": "Indexes",
        "query": "SELECT \n    table_schema, \n    table_name, \n    COUNT(DISTINCT index_name) AS index_count \nFROM information_schema.statistics \nWHERE table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nGROUP BY table_schema, table_name \nORDER BY index_count DESC;"
    },
    {
        "id": 21,
        "title": "Largest indexes",
        "method": "MySQLConnector.get_largest_indexes()",
        "description": "Top 100 tables with largest index storage overhead.",
        "headers": [
            "Database",
            "Table",
            "Index Size (MB)",
            "Index Size (GB)"
        ],
        "category": "Indexes",
        "query": "SELECT\n    table_schema,\n    table_name,\n    ROUND(index_length / 1024 / 1024, 2) AS index_mb,\n    ROUND(index_length / 1024 / 1024 / 1024, 4) AS index_gb\nFROM information_schema.tables\nWHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')\nORDER BY index_length DESC\nLIMIT 100;"
    },
    {
        "id": 22,
        "title": "Foreign key constraints",
        "method": "MySQLConnector.get_foreign_keys()",
        "description": "Foreign key referential relationships from information_schema.key_column_usage.",
        "headers": [
            "Database",
            "Table",
            "Constraint",
            "Column",
            "Ref Database",
            "Ref Table",
            "Ref Column",
            "Pos"
        ],
        "category": "Schema",
        "query": "SELECT \n    constraint_schema, \n    table_name, \n    constraint_name, \n    column_name, \n    referenced_table_schema, \n    referenced_table_name, \n    referenced_column_name, \n    ordinal_position \nFROM information_schema.key_column_usage \nWHERE referenced_table_name IS NOT NULL \n  AND constraint_schema NOT IN ('information_schema','mysql','performance_schema','sys') \nORDER BY \n    constraint_schema, \n    table_name, \n    constraint_name, \n    ordinal_position;"
    },
    {
        "id": 23,
        "title": "Tables Labeled by High Foreign Key Dependencies",
        "method": "MySQLConnector.get_tables_many_foreign_keys()",
        "description": "Tables ordered by foreign key reference density.",
        "headers": [
            "Database",
            "Table",
            "Foreign Keys Count"
        ],
        "category": "Schema",
        "query": "SELECT\n                CONSTRAINT_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                COUNT(DISTINCT CONSTRAINT_NAME) AS foreign_key_count\n            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE\n            WHERE REFERENCED_TABLE_NAME IS NOT NULL\n              AND {self._system_table_filter('CONSTRAINT_SCHEMA')}\n            GROUP BY CONSTRAINT_SCHEMA, TABLE_NAME\n            ORDER BY foreign_key_count DESC, CONSTRAINT_SCHEMA, TABLE_NAME"
    },
    {
        "id": 24,
        "title": "Unique Constraints and Indexes",
        "method": "MySQLConnector.get_unique_constraints()",
        "description": "Enforced unique constraint indexes.",
        "headers": [
            "Database",
            "Table",
            "Index Name",
            "Unique Columns"
        ],
        "category": "Indexes",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                INDEX_NAME AS index_name,\n                GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ', ') AS unique_columns\n            FROM INFORMATION_SCHEMA.STATISTICS\n            WHERE NON_UNIQUE = 0\n              AND {self._system_table_filter('TABLE_SCHEMA')}\n            GROUP BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME\n            ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME"
    },
    {
        "id": 25,
        "title": "Potential duplicate indexes",
        "method": "MySQLConnector.get_duplicate_indexes()",
        "description": "Tables with multiple indexes covering the exact same sequence of columns.",
        "headers": [
            "Database",
            "Table",
            "Index Columns",
            "Count",
            "Duplicate Indexes"
        ],
        "category": "Indexes",
        "query": "SELECT \n    table_schema, \n    table_name, \n    index_columns, \n    COUNT(*) AS duplicate_count, \n    GROUP_CONCAT(index_name ORDER BY index_name SEPARATOR ', ') AS indexes \nFROM (\n    SELECT \n        table_schema, \n        table_name, \n        index_name, \n        GROUP_CONCAT( \n            column_name \n            ORDER BY seq_in_index \n            SEPARATOR ',' \n        ) AS index_columns \n    FROM information_schema.statistics \n    WHERE table_schema NOT IN ( \n        'information_schema', \n        'mysql', \n        'performance_schema', \n        'sys' \n    ) \n    GROUP BY \n        table_schema, \n        table_name, \n        index_name \n) AS sub_indexes \nGROUP BY \n    table_schema, \n    table_name, \n    index_columns \nHAVING COUNT(*) > 1 \nORDER BY \n    table_schema, \n    table_name;"
    },
    {
        "id": 26,
        "title": "AUTO_INCREMENT Column Specifications",
        "method": "MySQLConnector.get_auto_increment_columns()",
        "description": "Auto-increment primary keys and surrogate identifier columns.",
        "headers": [
            "Database",
            "Table",
            "Column",
            "Column Type",
            "Specification"
        ],
        "category": "I/O",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                COLUMN_NAME AS column_name,\n                COLUMN_TYPE AS column_type,\n                EXTRA AS extra_info\n            FROM INFORMATION_SCHEMA.COLUMNS\n            WHERE EXTRA LIKE '%auto_increment%'\n              AND {self._system_table_filter('TABLE_SCHEMA')}\n            ORDER BY TABLE_SCHEMA, TABLE_NAME"
    },
    {
        "id": 27,
        "title": "Find Tables with Different Collations",
        "method": "MySQLConnector.get_tables_with_different_collations()",
        "description": "Distribution of table collation settings across schemas.",
        "headers": [
            "Database Schema",
            "Table Collation",
            "Table Count"
        ],
        "category": "I/O",
        "query": "SELECT \n                TABLE_SCHEMA AS schema_name, \n                TABLE_COLLATION AS table_collation, \n                COUNT(*) AS table_count \n            FROM INFORMATION_SCHEMA.TABLES \n            WHERE TABLE_TYPE = 'BASE TABLE'\n              AND {self._system_table_filter('TABLE_SCHEMA')} \n            GROUP BY TABLE_SCHEMA, TABLE_COLLATION \n            ORDER BY TABLE_SCHEMA, table_count DESC"
    },
    {
        "id": 28,
        "title": "Table Comments and Documentation",
        "method": "MySQLConnector.get_table_comments()",
        "description": "Documented table comments in schema metadata.",
        "headers": [
            "Database",
            "Table",
            "Comment / Description"
        ],
        "category": "I/O",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS table_name,\n                TABLE_COMMENT AS table_comment\n            FROM INFORMATION_SCHEMA.TABLES\n            WHERE TABLE_TYPE = 'BASE TABLE'\n              AND TABLE_COMMENT IS NOT NULL\n              AND TABLE_COMMENT <> ''\n              AND {self._system_table_filter()}\n            ORDER BY TABLE_SCHEMA, TABLE_NAME"
    },
    {
        "id": 29,
        "title": "Stored Procedures and Routines Inventory",
        "method": "MySQLConnector.get_stored_procedures()",
        "description": "Programmability routines (PROCEDURE / FUNCTION).",
        "headers": [
            "Database",
            "Routine Name",
            "Type",
            "Return Type",
            "Created",
            "Last Altered"
        ],
        "category": "Objects",
        "query": "SELECT\n                ROUTINE_SCHEMA AS schema_name,\n                ROUTINE_NAME AS routine_name,\n                ROUTINE_TYPE AS routine_type,\n                DATA_TYPE AS return_type,\n                CREATED AS created_time,\n                LAST_ALTERED AS last_altered\n            FROM INFORMATION_SCHEMA.ROUTINES\n            WHERE {self._system_table_filter('ROUTINE_SCHEMA')}\n            ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME"
    },
    {
        "id": 30,
        "title": "Database Views Inventory",
        "method": "MySQLConnector.get_views_inventory()",
        "description": "Logical views defined in schema metadata.",
        "headers": [
            "Database",
            "View Name"
        ],
        "category": "Objects",
        "query": "SELECT\n                TABLE_SCHEMA AS schema_name,\n                TABLE_NAME AS view_name\n            FROM INFORMATION_SCHEMA.VIEWS\n            WHERE {self._system_table_filter('TABLE_SCHEMA')}\n            ORDER BY TABLE_SCHEMA, TABLE_NAME"
    },
    {
        "id": 31,
        "title": "Database Triggers Inventory",
        "method": "MySQLConnector.get_triggers_inventory()",
        "description": "Event-driven database triggers details.",
        "headers": [
            "Trigger Schema",
            "Trigger Name",
            "Target Schema",
            "Target Table",
            "Event Manipulation",
            "Action Timing",
            "Action Statement"
        ],
        "category": "Objects",
        "query": "SELECT\n                TRIGGER_SCHEMA AS trigger_schema,\n                TRIGGER_NAME AS trigger_name,\n                EVENT_OBJECT_SCHEMA AS event_object_schema,\n                EVENT_OBJECT_TABLE AS event_object_table,\n                EVENT_MANIPULATION AS event_manipulation,\n                ACTION_TIMING AS action_timing,\n                ACTION_STATEMENT AS action_statement\n            FROM INFORMATION_SCHEMA.TRIGGERS\n            WHERE {self._system_table_filter('TRIGGER_SCHEMA')}\n            ORDER BY TRIGGER_SCHEMA, EVENT_OBJECT_TABLE"
    },
    {
        "id": 32,
        "title": "Scheduled Events Inventory",
        "method": "MySQLConnector.get_scheduled_events()",
        "description": "MySQL Event Scheduler background tasks inventory.",
        "headers": [
            "Event Schema",
            "Event Name",
            "Status",
            "Event Type",
            "Execute At",
            "Interval Value",
            "Interval Field",
            "Last Executed"
        ],
        "category": "Objects",
        "query": "SELECT\n                EVENT_SCHEMA AS event_schema,\n                EVENT_NAME AS event_name,\n                STATUS AS status,\n                EVENT_TYPE AS event_type,\n                EXECUTE_AT AS execute_at,\n                INTERVAL_VALUE AS interval_value,\n                INTERVAL_FIELD AS interval_field,\n                LAST_EXECUTED AS last_executed\n            FROM INFORMATION_SCHEMA.EVENTS\n            WHERE {self._system_table_filter('EVENT_SCHEMA')}\n            ORDER BY EVENT_SCHEMA, EVENT_NAME"
    },
    {
        "id": 33,
        "title": "Database User Accounts and Security Inventory",
        "method": "MySQLConnector.get_user_accounts()",
        "description": "User authentication accounts configured in mysql.user.",
        "headers": [
            "User",
            "Host",
            "Plugin",
            "Account Locked",
            "Password Expired"
        ],
        "category": "Security",
        "query": "SELECT\n                User AS user_name,\n                Host AS host_name,\n                plugin AS plugin_name,\n                account_locked AS account_locked,\n                password_expired AS password_expired\n            FROM mysql.user\n            ORDER BY User, Host"
    },
    {
        "id": 34,
        "title": "InnoDB Buffer Pool Configuration and Status",
        "method": "MySQLConnector.get_buffer_pool_status()",
        "description": "InnoDB buffer pool variables and runtime status metrics.",
        "headers": [
            "Type",
            "Metric / Variable Name",
            "Value"
        ],
        "category": "I/O",
        "query": "```python\ndef get_buffer_pool_status(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\"SHOW VARIABLES LIKE 'innodb_buffer_pool%'\")\n            for row in cursor.fetchall():\n                results.append(\n                    {\n                        \"setting_type\": \"Variable\",\n                        \"metric_name\": row[0],\n                        \"setting_value\": str(row[1]),\n                    }\n                )\n            cursor.execute(\"SHOW STATUS LIKE 'Innodb_buffer_pool%'\")\n            for row in cursor.fetchall():\n                results.append(\n                    {\n                        \"setting_type\": \"Status\",\n                        \"metric_name\": row[0],\n                        \"setting_value\": str(row[1]),\n                    }\n                )\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 35,
        "title": "Temporary Tables Global Status Metrics",
        "method": "MySQLConnector.get_temporary_tables_status()",
        "description": "Created_tmp_tables, Created_tmp_disk_tables, and Created_tmp_files metrics.",
        "headers": [
            "Metric Name",
            "Metric Value"
        ],
        "category": "I/O",
        "query": "```python\ndef get_temporary_tables_status(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\"SHOW GLOBAL STATUS LIKE 'Created_tmp%'\")\n            for row in cursor.fetchall():\n                results.append({\"metric_name\": row[0], \"metric_value\": str(row[1])})\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 36,
        "title": "Connections and Thread Activity Status",
        "method": "MySQLConnector.get_connection_thread_status()",
        "description": "Threads connected, Threads running, and max_connections settings.",
        "headers": [
            "Metric / Variable Name",
            "Value"
        ],
        "category": "I/O",
        "query": "```python\ndef get_connection_thread_status(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\"SHOW GLOBAL STATUS LIKE 'Threads%'\")\n            for row in cursor.fetchall():\n                results.append({\"metric_name\": row[0], \"metric_value\": str(row[1])})\n            cursor.execute(\"SHOW VARIABLES LIKE 'max_connections'\")\n            for row in cursor.fetchall():\n                results.append({\"metric_name\": row[0], \"metric_value\": str(row[1])})\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 37,
        "title": "Active InnoDB Transactions",
        "method": "MySQLConnector.get_active_transactions()",
        "description": "Currently executing transactions in InnoDB.",
        "headers": [
            "Trx ID",
            "Started",
            "Duration (s)",
            "State",
            "Rows Locked",
            "Rows Modified"
        ],
        "category": "I/O",
        "query": "SELECT\n                trx_id AS transaction_id,\n                trx_started AS started_time,\n                TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS duration_sec,\n                trx_state AS state,\n                trx_rows_locked AS rows_locked,\n                trx_rows_modified AS rows_modified\n            FROM INFORMATION_SCHEMA.INNODB_TRX\n            ORDER BY trx_started"
    },
    {
        "id": 38,
        "title": "Long-running transactions",
        "method": "MySQLConnector.get_long_running_transactions()",
        "description": "InnoDB active transactions ordered by oldest start time.",
        "headers": [
            "Trx ID",
            "Started",
            "Duration (s)",
            "State",
            "Tables Locked",
            "Rows Locked",
            "Rows Modified"
        ],
        "category": "I/O",
        "query": "SELECT\n                trx_id AS transaction_id,\n                trx_started AS started_time,\n                TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS duration_seconds,\n                trx_state AS state,\n                trx_tables_locked AS tables_locked,\n                trx_rows_locked AS rows_locked,\n                trx_rows_modified AS rows_modified\n            FROM INFORMATION_SCHEMA.INNODB_TRX\n            ORDER BY trx_started ASC"
    },
    {
        "id": 39,
        "title": "Active Data Locks and Lock Waits",
        "method": "MySQLConnector.get_data_locks()",
        "description": "Currently held locks and waiting transactions in performance_schema.data_locks.",
        "headers": [
            "Lock ID",
            "Database",
            "Table",
            "Type",
            "Mode",
            "Status",
            "Lock Data"
        ],
        "category": "I/O",
        "query": "SELECT\n                ENGINE_LOCK_ID AS lock_id,\n                OBJECT_SCHEMA AS schema_name,\n                OBJECT_NAME AS table_name,\n                LOCK_TYPE AS lock_type,\n                LOCK_MODE AS lock_mode,\n                LOCK_STATUS AS lock_status,\n                LOCK_DATA AS lock_data\n            FROM performance_schema.data_locks\n            WHERE {self._system_table_filter('OBJECT_SCHEMA')}\n            LIMIT 50"
    },
    {
        "id": 40,
        "title": "Deadlocks",
        "method": "MySQLConnector.get_deadlocks_info()",
        "description": "innodb_print_all_deadlocks setting and LATEST DETECTED DEADLOCK status.",
        "headers": [
            "Metric / Event",
            "Details / Value"
        ],
        "category": "Locks",
        "query": "```python\ndef get_deadlocks_info(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\"SHOW VARIABLES LIKE 'innodb_print_all_deadlocks'\")\n            for row in cursor.fetchall():\n                results.append(\n                    {\n                        \"metric_name\": row[0],\n                        \"status_details\": f\"Setting Value: {row[1]}\",\n                    }\n                )\n\n            cursor.execute(\"SHOW ENGINE INNODB STATUS\")\n            row = cursor.fetchone()\n            if row and len(row) >= 3:\n                engine_status = str(row[2])\n                if \"LATEST DETECTED DEADLOCK\" in engine_status:\n                    deadlock_part = engine_status.split(\"LATEST DETECTED DEADLOCK\")[\n                        1\n                    ].split(\"------------------------\")[0]\n                    clean_text = \" \".join(deadlock_part.strip().split())[:150]\n                    results.append(\n                        {\n                            \"metric_name\": \"LATEST_DETECTED_DEADLOCK\",\n                            \"status_details\": clean_text,\n                        }\n                    )\n                else:\n                    results.append(\n                        {\n                            \"metric_name\": \"LATEST_DETECTED_DEADLOCK\",\n                            \"status_details\": \"No recent deadlock recorded in engine status.\",\n                        }\n                    )\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 41,
        "title": "Slow Queries",
        "method": "MySQLConnector.get_slow_queries()",
        "description": "Slow queries from performance_schema.events_statements_summary_by_digest ranked by wait time.",
        "headers": [
            "Digest Text",
            "Count Star",
            "Total Seconds",
            "Avg Seconds",
            "Sum Rows Examined",
            "Sum Rows Sent"
        ],
        "category": "Query Performance",
        "query": "SELECT \n                DIGEST_TEXT, \n                COUNT_STAR, \n                SUM_TIMER_WAIT / 1000000000000 AS total_seconds, \n                AVG_TIMER_WAIT / 1000000000000 AS avg_seconds, \n                SUM_ROWS_EXAMINED, \n                SUM_ROWS_SENT \n            FROM performance_schema.events_statements_summary_by_digest \n            WHERE {self._system_table_filter('SCHEMA_NAME')}\n              AND DIGEST_TEXT IS NOT NULL\n              AND SUM_TIMER_WAIT >= 10000000000\n            ORDER BY SUM_TIMER_WAIT DESC \n            LIMIT {limit}"
    },
    {
        "id": 42,
        "title": "Top Queries Examining Huge Row Volumes",
        "method": "MySQLConnector.get_high_examined_rows_queries()",
        "description": "Queries reading high numbers of rows relative to output from performance_schema.events_statements_summary_by_digest.",
        "headers": [
            "Digest Text",
            "Count Star",
            "Sum Rows Examined",
            "Sum Rows Sent",
            "Avg Rows Examined"
        ],
        "category": "Overview",
        "query": "SELECT \n                DIGEST_TEXT, \n                COUNT_STAR, \n                SUM_ROWS_EXAMINED, \n                SUM_ROWS_SENT, \n                SUM_ROWS_EXAMINED / NULLIF(COUNT_STAR,0) AS avg_rows_examined \n            FROM performance_schema.events_statements_summary_by_digest \n            WHERE {self._system_table_filter('SCHEMA_NAME')}\n              AND DIGEST_TEXT IS NOT NULL\n            ORDER BY SUM_ROWS_EXAMINED DESC \n            LIMIT {limit}"
    },
    {
        "id": 43,
        "title": "Most Frequently Executed Queries",
        "method": "MySQLConnector.get_frequent_executed_queries()",
        "description": "Queries with highest cumulative execution count from performance_schema.events_statements_summary_by_digest.",
        "headers": [
            "Digest Text",
            "Count Star",
            "Avg Time (ms)"
        ],
        "category": "Query Performance",
        "query": "SELECT \n                DIGEST_TEXT, \n                COUNT_STAR, \n                AVG_TIMER_WAIT / 1000000000 AS avg_ms \n            FROM performance_schema.events_statements_summary_by_digest \n            WHERE {self._system_table_filter('SCHEMA_NAME')}\n              AND DIGEST_TEXT IS NOT NULL\n            ORDER BY COUNT_STAR DESC \n            LIMIT {limit}"
    },
    {
        "id": 44,
        "title": "Table I/O activity",
        "method": "MySQLConnector.get_table_io_activity()",
        "description": "Top 100 tables ranked by total read and write I/O activity.",
        "headers": [
            "Database",
            "Table",
            "Reads",
            "Writes",
            "Fetches",
            "Inserts",
            "Updates",
            "Deletes"
        ],
        "category": "I/O",
        "query": "SELECT\n                OBJECT_SCHEMA AS schema_name,\n                OBJECT_NAME AS table_name,\n                COUNT_READ AS count_read,\n                COUNT_WRITE AS count_write,\n                COUNT_FETCH AS count_fetch,\n                COUNT_INSERT AS count_insert,\n                COUNT_UPDATE AS count_update,\n                COUNT_DELETE AS count_delete\n            FROM performance_schema.table_io_waits_summary_by_table\n            WHERE {self._system_table_filter('OBJECT_SCHEMA')}\n            ORDER BY (COUNT_READ + COUNT_WRITE) DESC\n            LIMIT 100"
    },
    {
        "id": 45,
        "title": "Table wait time",
        "method": "MySQLConnector.get_table_wait_times()",
        "description": "Tables experiencing highest total I/O wait latency.",
        "headers": [
            "Database",
            "Table",
            "Total Ops",
            "Wait Time (s)"
        ],
        "category": "I/O",
        "query": "SELECT\n                OBJECT_SCHEMA AS schema_name,\n                OBJECT_NAME AS table_name,\n                COUNT_STAR AS total_ops,\n                SUM_TIMER_WAIT / 1000000000000 AS wait_sec\n            FROM performance_schema.table_io_waits_summary_by_table\n            WHERE {self._system_table_filter('OBJECT_SCHEMA')}\n            ORDER BY SUM_TIMER_WAIT DESC\n            LIMIT {limit}"
    },
    {
        "id": 46,
        "title": "Replication status",
        "method": "MySQLConnector.get_replication_status()",
        "description": "Source/Primary and Replica thread status.",
        "headers": [
            "Node Role",
            "Replication State"
        ],
        "category": "I/O",
        "query": "```python\ndef get_replication_status(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor(dictionary=True)\n            try:\n                cursor.execute(\"SHOW REPLICA STATUS\")\n                rows = cursor.fetchall()\n                for row in rows:\n                    results.append(\n                        {\n                            \"role\": \"Replica\",\n                            \"status_info\": f\"Source_Host: {row.get('Source_Host','-')}, Slave_IO_Running: {row.get('Slave_IO_Running','-')}, Slave_SQL_Running: {row.get('Slave_SQL_Running','-')}\",\n                        }\n                    )\n            except Exception:\n                try:\n                    cursor.execute(\"SHOW SLAVE STATUS\")\n                    rows = cursor.fetchall()\n                    for row in rows:\n                        results.append(\n                            {\n                                \"role\": \"Slave\",\n                                \"status_info\": f\"Master_Host: {row.get('Master_Host','-')}, Slave_IO_Running: {row.get('Slave_IO_Running','-')}, Slave_SQL_Running: {row.get('Slave_SQL_Running','-')}\",\n                            }\n                        )\n                except Exception:\n                    pass\n            if not results:\n                results.append(\n                    {\n                        \"role\": \"Source/Standalone\",\n                        \"status_info\": \"Server operating as primary source / standalone node.\",\n                    }\n                )\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 47,
        "title": "Binary log configuration",
        "method": "MySQLConnector.get_binlog_config()",
        "description": "log_bin, binlog_format, expire_logs, max_binlog_size.",
        "headers": [
            "Configuration Variable",
            "Value"
        ],
        "category": "I/O",
        "query": "```python\ndef get_binlog_config(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\n                \"SHOW VARIABLES WHERE Variable_name IN ('log_bin', 'binlog_format', 'binlog_expire_logs_seconds', 'max_binlog_size')\"\n            )\n            for row in cursor.fetchall():\n                results.append({\"variable_name\": row[0], \"setting_value\": str(row[1])})\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 48,
        "title": "GTID",
        "method": "MySQLConnector.get_gtid_info()",
        "description": "Global Transaction Identifier configuration and executed GTID sets.",
        "headers": [
            "GTID Property",
            "Value"
        ],
        "category": "Replication",
        "query": "```python\ndef get_gtid_info(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\"SHOW VARIABLES LIKE 'gtid%'\")\n            for row in cursor.fetchall():\n                results.append({\"property_name\": row[0], \"property_value\": str(row[1])})\n            try:\n                cursor.execute(\"SELECT @@GLOBAL.gtid_executed\")\n                val = cursor.fetchone()\n                if val:\n                    results.append(\n                        {\n                            \"property_name\": \"gtid_executed\",\n                            \"property_value\": str(val[0])[:100],\n                        }\n                    )\n            except Exception:\n                pass\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 49,
        "title": "Binary log size",
        "method": "MySQLConnector.get_binary_logs_info()",
        "description": "Replication binary log files recorded on server.",
        "headers": [
            "Log File Name",
            "File Size"
        ],
        "category": "Storage",
        "query": "```python\ndef get_binary_logs_info(self) -> List[Dict[str, Any]]:\n        try:\n            cursor = self.connection.cursor(dictionary=True)\n            cursor.execute(\"SHOW BINARY LOGS\")\n            rows = cursor.fetchall()\n            cursor.close()\n            return [\n                {\n                    \"log_name\": row.get(\"Log_name\", \"-\"),\n                    \"file_size\": row.get(\"File_size\", 0),\n                }\n                for row in rows\n            ]\n        except Exception:\n            return []\n```"
    },
    {
        "id": 50,
        "title": "InnoDB tablespaces",
        "method": "MySQLConnector.get_innodb_tablespaces()",
        "description": "InnoDB tablespaces inventory from information_schema.innodb_tablespaces.",
        "headers": [
            "Space ID",
            "Tablespace Name",
            "Space Type",
            "Row Format",
            "State"
        ],
        "category": "Storage",
        "query": "SELECT\n    SPACE,\n    NAME,\n    SPACE_TYPE,\n    ROW_FORMAT,\n    STATE\nFROM information_schema.innodb_tablespaces;"
    },
    {
        "id": 51,
        "title": "File-per-table configuration",
        "method": "MySQLConnector.get_file_per_table_config()",
        "description": "innodb_file_per_table setting.",
        "headers": [
            "Setting",
            "Value"
        ],
        "category": "I/O",
        "query": "```python\ndef get_file_per_table_config(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\"SHOW VARIABLES LIKE 'innodb_file_per_table'\")\n            for row in cursor.fetchall():\n                results.append({\"setting_name\": row[0], \"setting_value\": str(row[1])})\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 52,
        "title": "MySQL data directory",
        "method": "MySQLConnector.get_datadir_info()",
        "description": "Datadir path.",
        "headers": [
            "Directory Setting",
            "Path"
        ],
        "category": "Environment",
        "query": "```python\ndef get_datadir_info(self) -> List[Dict[str, Any]]:\n        results = []\n        try:\n            cursor = self.connection.cursor()\n            cursor.execute(\"SHOW VARIABLES LIKE 'datadir'\")\n            for row in cursor.fetchall():\n                results.append({\"setting_name\": row[0], \"setting_value\": str(row[1])})\n            cursor.close()\n        except Exception:\n            pass\n        return results\n```"
    },
    {
        "id": 53,
        "title": "Identify tables that haven't been used",
        "method": "MySQLConnector.get_least_active_tables()",
        "description": "Tables with zero recorded read and write operations (completely unused) for obsolescence assessment.",
        "headers": [
            "Database",
            "Table",
            "Reads",
            "Writes",
            "Total I/O Ops"
        ],
        "category": "Overview",
        "query": "SELECT \n                t.TABLE_SCHEMA AS OBJECT_SCHEMA, \n                t.TABLE_NAME AS OBJECT_NAME, \n                COALESCE(i.COUNT_READ, 0) AS COUNT_READ, \n                COALESCE(i.COUNT_WRITE, 0) AS COUNT_WRITE \n            FROM information_schema.TABLES t\n            LEFT JOIN performance_schema.table_io_waits_summary_by_table i\n                ON t.TABLE_SCHEMA = i.OBJECT_SCHEMA \n               AND t.TABLE_NAME = i.OBJECT_NAME\n            WHERE t.TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')\n              AND t.TABLE_TYPE = 'BASE TABLE'\n              AND COALESCE(i.COUNT_READ, 0) = 0\n              AND COALESCE(i.COUNT_WRITE, 0) = 0\n            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME"
    },
    {
        "id": 54,
        "title": "Identify hot tables",
        "method": "MySQLConnector.get_hot_tables()",
        "description": "Top active workload tables ranked by total read/write I/O operations.",
        "headers": [
            "Database",
            "Table",
            "Reads",
            "Writes",
            "Inserts",
            "Updates",
            "Deletes",
            "Total I/O Ops"
        ],
        "category": "Overview",
        "query": "SELECT\n                OBJECT_SCHEMA AS schema_name,\n                OBJECT_NAME AS table_name,\n                COUNT_READ AS count_read,\n                COUNT_WRITE AS count_write,\n                COUNT_FETCH AS count_fetch,\n                COUNT_INSERT AS count_insert,\n                COUNT_UPDATE AS count_update,\n                COUNT_DELETE AS count_delete,\n                (COUNT_READ + COUNT_WRITE) AS total_ops\n            FROM performance_schema.table_io_waits_summary_by_table\n            WHERE {self._system_table_filter('OBJECT_SCHEMA')}\n            ORDER BY total_ops DESC\n            LIMIT {limit}"
    },
    {
        "id": 55,
        "title": "Fragmentation Details",
        "method": "MySQLConnector.get_fragmentation_details()",
        "description": "Tables with unused fragmented space (DATA_FREE).",
        "headers": [
            "Database",
            "Table",
            "Data Size",
            "Fragmented Space",
            "Fragmentation %"
        ],
        "category": "I/O",
        "query": "SELECT \n    table_schema, \n    table_name, \n    data_length, \n    index_length, \n    data_free \nFROM information_schema.tables \nWHERE engine = 'InnoDB' \nAND table_schema NOT IN \n('information_schema','mysql','performance_schema','sys') \nORDER BY data_free DESC;"
    },
    {
        "id": 56,
        "title": "Foreign-key dependency graph",
        "method": "MySQLConnector.get_foreign_keys()",
        "description": "Referential dependency graph for migration sequencing.",
        "headers": [
            "Database",
            "Child Table",
            "Child Column",
            "Ref Database",
            "Parent Table",
            "Parent Column"
        ],
        "category": "Schema",
        "query": "SELECT \n    constraint_schema, \n    table_name, \n    constraint_name, \n    column_name, \n    referenced_table_schema, \n    referenced_table_name, \n    referenced_column_name, \n    ordinal_position \nFROM information_schema.key_column_usage \nWHERE referenced_table_name IS NOT NULL \n  AND constraint_schema NOT IN ('information_schema','mysql','performance_schema','sys') \nORDER BY \n    constraint_schema, \n    table_name, \n    constraint_name, \n    ordinal_position;"
    },
    {
        "id": 57,
        "title": "Stored code dependencies",
        "method": "MySQLConnector.get_stored_procedures()",
        "description": "Stored procedures, triggers, events, and views dependency inventory.",
        "headers": [
            "Programmability Object",
            "Total Count"
        ],
        "category": "Overview",
        "query": "SELECT\n                ROUTINE_SCHEMA AS schema_name,\n                ROUTINE_NAME AS routine_name,\n                ROUTINE_TYPE AS routine_type,\n                DATA_TYPE AS return_type,\n                CREATED AS created_time,\n                LAST_ALTERED AS last_altered\n            FROM INFORMATION_SCHEMA.ROUTINES\n            WHERE {self._system_table_filter('ROUTINE_SCHEMA')}\n            ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME"
    },
    {
        "id": 58,
        "title": "MySQL Key System Configuration Variables",
        "method": "MySQLConnector.get_server_variables()",
        "description": "Engine, memory, connection, and binlog configuration parameters.",
        "headers": [
            "Variable Name",
            "Setting Value"
        ],
        "category": "I/O",
        "query": "SELECT VARIABLE_NAME AS var_name, VARIABLE_VALUE AS var_value\n            FROM INFORMATION_SCHEMA.GLOBAL_VARIABLES\n            WHERE VARIABLE_NAME IN ({target_vars})\n            ORDER BY VARIABLE_NAME"
    }
]

# Pre-indexed dictionary for fast O(1) lookup
_INDEX_BY_TITLE: Dict[str, Dict[str, Any]] = {}
_INDEX_BY_ID: Dict[str, Dict[str, Any]] = {}

for item in INSIGHTS:
    raw_title = item.get("title", "")
    _INDEX_BY_TITLE[raw_title.lower()] = item
    clean_title = re.sub(r"^\d+\.\s*", "", raw_title).strip().lower()
    _INDEX_BY_TITLE[clean_title] = item
    _INDEX_BY_ID[str(item.get("id"))] = item

_MYSQL_ALIASES = {
    "check table fragmentation": "55",
    "table fragmentation": "55",
    "fragmentation": "55",
    "fragmentation details": "55",
    "mysql version and environment": "1",
    "version and environment": "1",
    "tables with partitions and detailed partition information": "9",
    "partitions": "9",
    "find very large columns": "14",
    "large columns": "14",
    "find json columns": "15",
    "json columns": "15",
    "foreign keys / relationships": "22",
    "foreign keys": "22",
    "tables with many foreign-key relationships": "23",
    "check auto_increment information": "26",
    "auto_increment": "26",
    "tables with comments / documentation": "28",
    "table comments": "28",
    "events / scheduled jobs": "32",
    "scheduled events": "32",
    "users and privileges": "33",
    "transaction activity": "37",
    "queries examining huge amounts of data": "42",
    "configuration assessment": "58",
}
for alias, id_val in _MYSQL_ALIASES.items():
    if id_val in _INDEX_BY_ID:
        _INDEX_BY_TITLE[alias] = _INDEX_BY_ID[id_val]


def get_query(title_or_key: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata, method name, and query for an insight by title, id, method, or keyword."""
    if not title_or_key:
        return None
    raw = str(title_or_key).strip()
    k = raw.lower()
    
    # 1. Exact match in indexed titles / aliases
    if k in _INDEX_BY_TITLE:
        return _INDEX_BY_TITLE[k]
    
    clean_k = re.sub(r"^\d+\.\s*", "", k).strip()
    if clean_k in _INDEX_BY_TITLE:
        return _INDEX_BY_TITLE[clean_k]
        
    # 2. Match exact ID or leading ID number e.g. '55' or '55. Check Table Fragmentation'
    if k in _INDEX_BY_ID:
        return _INDEX_BY_ID[k]
    id_m = re.match(r"^(\d+)", raw)
    if id_m and id_m.group(1) in _INDEX_BY_ID:
        return _INDEX_BY_ID[id_m.group(1)]

    # 3. Match method name
    for item in INSIGHTS:
        meth = str(item.get("method", "")).lower()
        if clean_k and (clean_k == meth or clean_k in meth or meth.endswith(f".{clean_k}") or meth.endswith(f".{clean_k}()")):
            return item

    # 4. Substring / Keyword matching
    for title_k, item in _INDEX_BY_TITLE.items():
        if len(clean_k) >= 4 and (clean_k in title_k or title_k in clean_k):
            return item
            
    # 5. Word token matching
    k_tokens = [w for w in clean_k.split() if len(w) > 3 and w not in ["database", "table", "mysql", "oracle", "postgres", "sqlserver", "check", "find", "with", "information"]]
    if k_tokens:
        for title_k, item in _INDEX_BY_TITLE.items():
            if all(t in title_k for t in k_tokens):
                return item

    return None


def get_all_queries() -> List[Dict[str, Any]]:
    """Return all insight definitions for MySQL."""
    return INSIGHTS
