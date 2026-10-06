"""
PostgreSQL Database Insights & Dynamic SQL Queries
Auto-documented query methods and metadata reference for PostgreSQL.
"""

import re
from typing import Any, Dict, List, Optional

INSIGHTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "PostgreSQL version and environment",
        "method": "PostgreSQLConnector.get_environment_info()",
        "description": "PostgreSQL server, database, connection and version information.",
        "headers": [
            "PostgreSQL Version",
            "Server Version",
            "Database",
            "Server Address",
            "Port",
            "Current User"
        ],
        "category": "I/O",
        "query": "SELECT\n    version() AS postgres_version,\n    current_setting('server_version') AS server_version,\n    current_database() AS database_name,\n    inet_server_addr() AS server_address,\n    inet_server_port() AS port,\n    current_user AS current_user;"
    },
    {
        "id": 2,
        "title": "Database inventory",
        "method": "PostgreSQLConnector.get_database_inventory()",
        "description": "Databases visible to the current PostgreSQL cluster with their sizes.",
        "headers": [
            "Database Name",
            "Owner",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Overview",
        "query": "SELECT\n    d.datname AS database_name,\n    pg_get_userbyid(d.datdba) AS owner,\n    ROUND((sz.raw_bytes / 1024.0 / 1024)::numeric, 2) AS size_mb,\n    ROUND((sz.raw_bytes / 1024.0 / 1024 / 1024)::numeric, 2) AS size_gb\nFROM pg_database d\nJOIN (\n    SELECT oid, pg_database_size(oid) AS raw_bytes\n    FROM pg_database\n    WHERE datallowconn = true\n      AND datistemplate = false\n) sz ON d.oid = sz.oid\nORDER BY sz.raw_bytes DESC;"
    },
    {
        "id": 3,
        "title": "Schema/table storage analysis",
        "method": "PostgreSQLConnector.get_schema_table_storage_analysis()",
        "description": "Table storage analysis (including indexes and TOAST).",
        "headers": [
            "Schema",
            "Table Name",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Storage",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    ROUND((pg_total_relation_size(c.oid) / 1024.0 / 1024)::numeric, 2) AS size_mb,\n    ROUND((pg_total_relation_size(c.oid) / 1024.0 / 1024 / 1024)::numeric, 2) AS size_gb\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%'\nORDER BY pg_total_relation_size(c.oid) DESC;"
    },
    {
        "id": 4,
        "title": "Total table vs index storage",
        "method": "PostgreSQLConnector.get_total_table_vs_index_storage()",
        "description": "Database-wide table heap, index and total relation storage.",
        "headers": [
            "Table Storage (MB)",
            "Index Storage (MB)",
            "Total Storage (MB)",
            "Table Storage (GB)",
            "Index Storage (GB)",
            "Total Storage (GB)"
        ],
        "category": "Storage",
        "query": "SELECT\n    ROUND((COALESCE(SUM(pg_relation_size(c.oid)), 0) / 1024.0 / 1024)::numeric, 2) AS table_mb,\n    ROUND((COALESCE(SUM(pg_indexes_size(c.oid)), 0) / 1024.0 / 1024)::numeric, 2) AS index_mb,\n    ROUND((COALESCE(SUM(pg_total_relation_size(c.oid)), 0) / 1024.0 / 1024)::numeric, 2) AS total_mb,\n    ROUND((COALESCE(SUM(pg_relation_size(c.oid)), 0) / 1024.0 / 1024 / 1024)::numeric, 2) AS table_gb,\n    ROUND((COALESCE(SUM(pg_indexes_size(c.oid)), 0) / 1024.0 / 1024 / 1024)::numeric, 2) AS index_gb,\n    ROUND((COALESCE(SUM(pg_total_relation_size(c.oid)), 0) / 1024.0 / 1024 / 1024)::numeric, 2) AS total_gb\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%';"
    },
    {
        "id": 5,
        "title": "Top 100 tables",
        "method": "PostgreSQLConnector.get_top_100_largest_relations()",
        "description": "Top 100 largest user tables/partitioned tables by row count.",
        "headers": [
            "Database",
            "Schema",
            "Table Name",
            "Relation Type",
            "Row Count",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Overview",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS relation_name,\n    CASE c.relkind\n        WHEN 'r' THEN 'Table'\n        WHEN 'p' THEN 'Partitioned Table'\n        WHEN 'i' THEN 'Index'\n        WHEN 'm' THEN 'Materialized View'\n        WHEN 'v' THEN 'View'\n        ELSE c.relkind::text\n    END AS relation_type,\n    GREATEST(c.reltuples::bigint, 0) AS row_count,\n    ROUND((pg_total_relation_size(c.oid) / 1024.0 / 1024)::numeric, 2) AS size_mb,\n    ROUND((pg_total_relation_size(c.oid) / 1024.0 / 1024 / 1024)::numeric, 2) AS size_gb\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%'\nORDER BY GREATEST(c.reltuples::bigint, 0) DESC, pg_total_relation_size(c.oid) DESC\nLIMIT 100;"
    },
    {
        "id": 6,
        "title": "Tablespace usage",
        "method": "PostgreSQLConnector.get_tablespace_usage()",
        "description": "PostgreSQL tablespaces and the size of objects stored in each.",
        "headers": [
            "Tablespace Name",
            "Owner",
            "Location",
            "Size (GB)"
        ],
        "category": "Storage",
        "query": "WITH relation_sizes AS (\n    SELECT\n        c.oid,\n        c.reltablespace,\n        pg_total_relation_size(c.oid) AS total_size\n    FROM pg_class c\n    JOIN pg_namespace n ON n.oid = c.relnamespace\n    WHERE c.relkind IN ('r','p','m')\n      AND n.nspname NOT IN ('pg_catalog','information_schema')\n      AND n.nspname NOT LIKE 'pg_toast%'\n)\nSELECT\n    t.spcname AS tablespace_name,\n    pg_get_userbyid(t.spcowner) AS owner,\n    COALESCE(NULLIF(pg_tablespace_location(t.oid), ''), current_setting('data_directory')) AS location,\n    ROUND(COALESCE(SUM(rs.total_size), 0) / 1024.0 / 1024 / 1024, 2) AS size_gb\nFROM pg_tablespace t\nLEFT JOIN relation_sizes rs\n  ON rs.reltablespace = t.oid\n  OR (rs.reltablespace = 0 AND t.oid = (\n      SELECT dattablespace\n      FROM pg_database\n      WHERE datname = current_database()\n  ))\nGROUP BY t.oid, t.spcname, t.spcowner\nORDER BY size_gb DESC;"
    },
    {
        "id": 7,
        "title": "Tablespace object storage",
        "method": "PostgreSQLConnector.get_tablespace_object_storage()",
        "description": "Object storage assigned to each PostgreSQL tablespace, including objects",
        "headers": [
            "Tablespace Name",
            "Object Count",
            "Total Object Size (GB)"
        ],
        "category": "Storage",
        "query": "WITH relation_sizes AS (\n    SELECT\n        c.oid,\n        CASE\n            WHEN c.reltablespace = 0 THEN d.dattablespace\n            ELSE c.reltablespace\n        END AS tablespace_oid\n    FROM pg_class c\n    JOIN pg_namespace n ON n.oid = c.relnamespace\n    CROSS JOIN (\n        SELECT dattablespace\n        FROM pg_database\n        WHERE datname = current_database()\n    ) d\n    WHERE c.relkind IN ('r','p','i','I','m')\n      AND n.nspname NOT IN ('pg_catalog','information_schema')\n      AND n.nspname NOT LIKE 'pg_toast%'\n)\nSELECT\n    t.spcname AS tablespace_name,\n    COUNT(rs.oid) AS object_count,\n    ROUND(\n        COALESCE(SUM(pg_total_relation_size(rs.oid)), 0)\n        / 1024.0 / 1024 / 1024,\n        2\n    ) AS total_size_gb\nFROM pg_tablespace t\nLEFT JOIN relation_sizes rs\n  ON rs.tablespace_oid = t.oid\nGROUP BY t.oid, t.spcname\nORDER BY total_size_gb DESC;"
    },
    {
        "id": 8,
        "title": "Database files / physical layout",
        "method": "PostgreSQLConnector.get_database_files()",
        "description": "PostgreSQL exposes data directories and tablespace locations rather than",
        "headers": [
            "Database File / Tablespace",
            "Location"
        ],
        "category": "Overview",
        "query": "SELECT\n    spcname AS tablespace_name,\n    COALESCE(\n        NULLIF(pg_tablespace_location(oid), ''),\n        current_setting('data_directory')\n    ) AS location\nFROM pg_tablespace\nORDER BY spcname;"
    },
    {
        "id": 9,
        "title": "Master (Parent) tables",
        "method": "PostgreSQLConnector.get_master_tables()",
        "description": "Tables referenced by foreign-key constraints.",
        "headers": [
            "Schema",
            "Parent Table",
            "Child FK Count",
            "Referencing Child Tables"
        ],
        "category": "Schema",
        "query": "SELECT\n    parent_ns.nspname AS schema_name,\n    parent.relname AS table_name,\n    COUNT(*) AS child_fk_count,\n    STRING_AGG(DISTINCT child_ns.nspname || '.' || child.relname, ', '\n               ORDER BY child_ns.nspname || '.' || child.relname) AS child_tables\nFROM pg_constraint con\nJOIN pg_class parent ON parent.oid = con.confrelid\nJOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace\nJOIN pg_class child ON child.oid = con.conrelid\nJOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace\nWHERE con.contype = 'f'\n  AND parent_ns.nspname NOT IN ('pg_catalog','information_schema')\nGROUP BY parent_ns.nspname, parent.relname\nORDER BY child_fk_count DESC, schema_name, table_name;"
    },
    {
        "id": 10,
        "title": "Child tables",
        "method": "PostgreSQLConnector.get_child_tables()",
        "description": "Tables containing foreign keys referencing parent tables.",
        "headers": [
            "Schema",
            "Child Table",
            "Parent FK Count",
            "Referenced Parent Tables"
        ],
        "category": "Schema",
        "query": "SELECT\n    child_ns.nspname AS schema_name,\n    child.relname AS table_name,\n    COUNT(*) AS parent_fk_count,\n    STRING_AGG(DISTINCT parent_ns.nspname || '.' || parent.relname, ', '\n               ORDER BY parent_ns.nspname || '.' || parent.relname) AS parent_tables\nFROM pg_constraint con\nJOIN pg_class child ON child.oid = con.conrelid\nJOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace\nJOIN pg_class parent ON parent.oid = con.confrelid\nJOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace\nWHERE con.contype = 'f'\n  AND child_ns.nspname NOT IN ('pg_catalog','information_schema')\nGROUP BY child_ns.nspname, child.relname\nORDER BY parent_fk_count DESC, schema_name, table_name;"
    },
    {
        "id": 11,
        "title": "Independent tables",
        "method": "PostgreSQLConnector.get_independent_tables()",
        "description": "Tables with no incoming or outgoing foreign-key relationships.",
        "headers": [
            "Schema",
            "Table Name"
        ],
        "category": "Overview",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%'\n  AND NOT EXISTS (\n      SELECT 1 FROM pg_constraint fk\n      WHERE fk.conrelid = c.oid AND fk.contype = 'f'\n  )\n  AND NOT EXISTS (\n      SELECT 1 FROM pg_constraint fk\n      WHERE fk.confrelid = c.oid AND fk.contype = 'f'\n  )\nORDER BY n.nspname, c.relname;"
    },
    {
        "id": 12,
        "title": "Large unpartitioned tables",
        "method": "PostgreSQLConnector.get_large_unpartitioned_tables()",
        "description": "Large tables that are not partitioned, for partitioning review.",
        "headers": [
            "Schema",
            "Table Name",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "I/O",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    ROUND(pg_total_relation_size(c.oid) / 1024.0 / 1024, 2) AS size_mb,\n    ROUND(pg_total_relation_size(c.oid) / 1024.0 / 1024 / 1024, 2) AS size_gb\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind = 'r'\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%'\n  AND NOT EXISTS (\n      SELECT 1\n      FROM pg_inherits i\n      WHERE i.inhrelid = c.oid\n  )\nORDER BY pg_total_relation_size(c.oid) DESC;"
    },
    {
        "id": 13,
        "title": "Partition inventory",
        "method": "PostgreSQLConnector.get_partition_inventory()",
        "description": "Partitioned tables and their child partition counts.",
        "headers": [
            "Schema",
            "Parent Table",
            "Partition Count"
        ],
        "category": "I/O",
        "query": "SELECT\n    parent_ns.nspname AS schema_name,\n    parent.relname AS table_name,\n    COUNT(*) AS partition_count\nFROM pg_inherits i\nJOIN pg_class parent ON parent.oid = i.inhparent\nJOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace\nWHERE parent_ns.nspname NOT IN ('pg_catalog','information_schema')\nGROUP BY parent_ns.nspname, parent.relname\nORDER BY partition_count DESC;"
    },
    {
        "id": 14,
        "title": "Detailed partition information",
        "method": "PostgreSQLConnector.get_detailed_partition_info()",
        "description": "Partition hierarchy and partition bounds.",
        "headers": [
            "Schema",
            "Parent Table",
            "Partition Name",
            "Partition Bound"
        ],
        "category": "I/O",
        "query": "SELECT\n    parent_ns.nspname AS schema_name,\n    parent.relname AS parent_table,\n    child.relname AS partition_name,\n    pg_get_expr(child.relpartbound, child.oid) AS partition_bound\nFROM pg_inherits i\nJOIN pg_class parent ON parent.oid = i.inhparent\nJOIN pg_class child ON child.oid = i.inhrelid\nJOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace\nWHERE parent_ns.nspname NOT IN ('pg_catalog','information_schema')\nORDER BY parent_ns.nspname, parent.relname, child.relname;"
    },
    {
        "id": 15,
        "title": "Large object columns",
        "method": "PostgreSQLConnector.get_large_object_columns()",
        "description": "Columns using PostgreSQL large-value types such as bytea, text and XML.",
        "headers": [
            "Schema",
            "Table Name",
            "Column Name",
            "Data Type"
        ],
        "category": "Structure",
        "query": "SELECT\n    table_schema AS schema_name,\n    table_name,\n    column_name,\n    data_type\nFROM information_schema.columns\nWHERE table_schema NOT IN ('pg_catalog','information_schema')\n  AND data_type IN ('bytea','text','xml')\nORDER BY table_schema, table_name, ordinal_position;"
    },
    {
        "id": 16,
        "title": "JSON / JSONB columns",
        "method": "PostgreSQLConnector.get_json_columns()",
        "description": "Columns explicitly defined with PostgreSQL json or jsonb data types.",
        "headers": [
            "Schema",
            "Table Name",
            "Column Name",
            "Data Type"
        ],
        "category": "Structure",
        "query": "SELECT\n    table_schema AS schema_name,\n    table_name,\n    column_name,\n    data_type\nFROM information_schema.columns\nWHERE table_schema NOT IN ('pg_catalog','information_schema')\n  AND data_type IN ('json','jsonb')\nORDER BY table_schema, table_name, ordinal_position;"
    },
    {
        "id": 17,
        "title": "Primary keys",
        "method": "PostgreSQLConnector.get_primary_keys()",
        "description": "Primary-key constraints and their definitions.",
        "headers": [
            "Schema",
            "Table Name",
            "Constraint Name",
            "Definition"
        ],
        "category": "Indexes",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    con.conname AS constraint_name,\n    pg_get_constraintdef(con.oid) AS definition\nFROM pg_constraint con\nJOIN pg_class c ON c.oid = con.conrelid\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE con.contype = 'p'\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\nORDER BY n.nspname, c.relname, con.conname;"
    },
    {
        "id": 18,
        "title": "Tables without primary keys",
        "method": "PostgreSQLConnector.get_tables_without_primary_keys()",
        "description": "User tables without an explicit primary-key constraint.",
        "headers": [
            "Schema",
            "Table Name"
        ],
        "category": "Indexes",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND NOT EXISTS (\n      SELECT 1\n      FROM pg_constraint con\n      WHERE con.conrelid = c.oid\n        AND con.contype = 'p'\n  )\nORDER BY n.nspname, c.relname;"
    },
    {
        "id": 19,
        "title": "All indexes",
        "method": "PostgreSQLConnector.get_all_indexes()",
        "description": "PostgreSQL index inventory and status.",
        "headers": [
            "Schema",
            "Table Name",
            "Index Name",
            "Index Scans",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Indexes",
        "query": "SELECT\n    schemaname AS schema_name,\n    tablename AS table_name,\n    indexrelname AS index_name,\n    idx_scan,\n    ROUND((pg_relation_size(indexrelid) / 1024.0 / 1024)::numeric, 2) AS size_mb,\n    ROUND((pg_relation_size(indexrelid) / 1024.0 / 1024 / 1024)::numeric, 2) AS size_gb\nFROM pg_stat_all_indexes\nWHERE schemaname NOT IN ('pg_catalog','information_schema')\n  AND schemaname NOT LIKE 'pg_toast%'\nORDER BY pg_relation_size(indexrelid) DESC;"
    },
    {
        "id": 20,
        "title": "Index columns",
        "method": "PostgreSQLConnector.get_index_columns()",
        "description": "Columns and positions used by each index.",
        "headers": [
            "Schema",
            "Table Name",
            "Index Name",
            "Column Position",
            "Column Name"
        ],
        "category": "Indexes",
        "query": "SELECT\n    n.nspname AS schema_name,\n    t.relname AS table_name,\n    i.relname AS index_name,\n    k.n AS column_position,\n    a.attname AS column_name\nFROM pg_index ix\nJOIN pg_class t ON t.oid = ix.indrelid\nJOIN pg_class i ON i.oid = ix.indexrelid\nJOIN pg_namespace n ON n.oid = t.relnamespace\nCROSS JOIN LATERAL generate_subscripts(ix.indkey, 1) AS k(n)\nJOIN pg_attribute a\n  ON a.attrelid = t.oid\n AND a.attnum = ix.indkey[k.n]\nWHERE n.nspname NOT IN ('pg_catalog','information_schema')\nORDER BY n.nspname, t.relname, i.relname, k.n;"
    },
    {
        "id": 21,
        "title": "Index count by table",
        "method": "PostgreSQLConnector.get_index_count_by_table()",
        "description": "Number of indexes defined on each user table.",
        "headers": [
            "Schema",
            "Table Name",
            "Index Count"
        ],
        "category": "Indexes",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    COUNT(i.indexrelid) AS index_count\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nJOIN pg_index i ON i.indrelid = c.oid\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%'\nGROUP BY n.nspname, c.relname\nHAVING COUNT(i.indexrelid) > 0\nORDER BY index_count DESC, n.nspname, c.relname;"
    },
    {
        "id": 22,
        "title": "Largest indexes",
        "method": "PostgreSQLConnector.get_largest_indexes()",
        "description": "Largest user indexes by physical size.",
        "headers": [
            "Schema",
            "Table Name",
            "Index Name",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Indexes",
        "query": "SELECT\n    schemaname AS schema_name,\n    tablename AS table_name,\n    indexrelname AS index_name,\n    ROUND(pg_relation_size(indexrelid) / 1024.0 / 1024, 2) AS size_mb,\n    ROUND(pg_relation_size(indexrelid) / 1024.0 / 1024 / 1024, 2) AS size_gb\nFROM pg_stat_all_indexes\nWHERE schemaname NOT IN ('pg_catalog','information_schema')\nORDER BY pg_relation_size(indexrelid) DESC\nLIMIT 100;"
    },
    {
        "id": 23,
        "title": "Foreign keys / relationships",
        "method": "PostgreSQLConnector.get_foreign_keys()",
        "description": "Foreign-key relationship inventory.",
        "headers": [
            "Schema",
            "Table Name",
            "Constraint Name",
            "Definition"
        ],
        "category": "I/O",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    con.conname AS constraint_name,\n    pg_get_constraintdef(con.oid) AS definition\nFROM pg_constraint con\nJOIN pg_class c ON c.oid = con.conrelid\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE con.contype = 'f'\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\nORDER BY n.nspname, c.relname, con.conname;"
    },
    {
        "id": 24,
        "title": "Tables with many foreign-key relationships",
        "method": "PostgreSQLConnector.get_tables_many_foreign_keys()",
        "description": "Tables ranked by number of outgoing foreign-key constraints.",
        "headers": [
            "Schema",
            "Table Name",
            "Foreign Key Count"
        ],
        "category": "I/O",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    COUNT(*) AS foreign_key_count\nFROM pg_constraint con\nJOIN pg_class c ON c.oid = con.conrelid\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE con.contype = 'f'\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\nGROUP BY n.nspname, c.relname\nORDER BY foreign_key_count DESC;"
    },
    {
        "id": 25,
        "title": "Unique constraints",
        "method": "PostgreSQLConnector.get_unique_constraints()",
        "description": "Unique constraints inventory.",
        "headers": [
            "Schema",
            "Table Name",
            "Constraint Name",
            "Definition"
        ],
        "category": "Overview",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    con.conname AS constraint_name,\n    pg_get_constraintdef(con.oid, true) AS definition\nFROM pg_constraint con\nJOIN pg_class c ON c.oid = con.conrelid\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE con.contype = 'u'\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\nORDER BY n.nspname, c.relname, con.conname;"
    },
    {
        "id": 26,
        "title": "Duplicate/redundant index candidates",
        "method": "PostgreSQLConnector.get_duplicate_index_candidates()",
        "description": "Candidate duplicate indexes with the same normalized CREATE INDEX",
        "headers": [
            "Schema",
            "Table Name",
            "Index A",
            "Index B",
            "Definition"
        ],
        "category": "Indexes",
        "query": "WITH idx AS (\n    SELECT\n        n.nspname AS schema_name,\n        t.relname AS table_name,\n        i.relname AS index_name,\n        regexp_replace(\n            pg_get_indexdef(ix.indexrelid),\n            '^CREATE (UNIQUE )?INDEX [^ ]+ ON ',\n            'CREATE \u0001INDEX ON '\n        ) AS normalized_definition\n    FROM pg_index ix\n    JOIN pg_class t ON t.oid = ix.indrelid\n    JOIN pg_class i ON i.oid = ix.indexrelid\n    JOIN pg_namespace n ON n.oid = t.relnamespace\n    WHERE n.nspname NOT IN ('pg_catalog','information_schema')\n      AND n.nspname NOT LIKE 'pg_toast%'\n)\nSELECT\n    a.schema_name,\n    a.table_name,\n    a.index_name AS index_a,\n    b.index_name AS index_b,\n    a.normalized_definition AS definition\nFROM idx a\nJOIN idx b\n  ON b.schema_name = a.schema_name\n AND b.table_name = a.table_name\n AND b.normalized_definition = a.normalized_definition\n AND b.index_name > a.index_name\nORDER BY a.schema_name, a.table_name, a.index_name, b.index_name;"
    },
    {
        "id": 27,
        "title": "Character sets and collations",
        "method": "PostgreSQLConnector.get_character_sets_and_collations()",
        "description": "Current database encoding and locale configuration.",
        "headers": [
            "Database Name",
            "Database Encoding",
            "Server Encoding",
            "LC_COLLATE",
            "LC_CTYPE"
        ],
        "category": "I/O",
        "query": "SELECT\n    current_database() AS database_name,\n    pg_encoding_to_char(encoding) AS database_encoding,\n    current_setting('server_encoding') AS server_encoding,\n    datcollate AS lc_collate,\n    datctype AS lc_ctype\nFROM pg_database\nWHERE datname = current_database();"
    },
    {
        "id": 28,
        "title": "Tables with comments / documentation",
        "method": "PostgreSQLConnector.get_table_comments()",
        "description": "Table comments stored in PostgreSQL catalog.",
        "headers": [
            "Schema",
            "Table Name",
            "Comments"
        ],
        "category": "I/O",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    obj_description(c.oid, 'pg_class') AS comments\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('r','p','v','m')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND obj_description(c.oid, 'pg_class') IS NOT NULL\nORDER BY n.nspname, c.relname;"
    },
    {
        "id": 29,
        "title": "Stored procedures",
        "method": "PostgreSQLConnector.get_stored_procedures()",
        "description": "Procedures created with CREATE PROCEDURE.",
        "headers": [
            "Schema",
            "Procedure Name",
            "Language",
            "Owner",
            "Definition"
        ],
        "category": "Objects",
        "query": "SELECT\n    n.nspname AS schema_name,\n    p.proname AS procedure_name,\n    l.lanname AS language,\n    pg_get_userbyid(p.proowner) AS owner,\n    pg_get_functiondef(p.oid) AS definition\nFROM pg_proc p\nJOIN pg_namespace n ON n.oid = p.pronamespace\nJOIN pg_language l ON l.oid = p.prolang\nWHERE p.prokind = 'p'\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND NOT EXISTS (\n      SELECT 1 FROM pg_depend dep\n      WHERE dep.classid = 'pg_proc'::regclass\n        AND dep.objid = p.oid\n        AND dep.deptype = 'e'\n  )\nORDER BY n.nspname, p.proname;"
    },
    {
        "id": 30,
        "title": "Functions",
        "method": "PostgreSQLConnector.get_functions()",
        "description": "PostgreSQL functions inventory.",
        "headers": [
            "Schema",
            "Function Name",
            "Return Type",
            "Language",
            "Volatility"
        ],
        "category": "I/O",
        "query": "SELECT\n    n.nspname AS schema_name,\n    p.proname AS function_name,\n    pg_get_function_result(p.oid) AS return_type,\n    l.lanname AS language,\n    p.provolatile AS volatility,\n    p.proparallel AS parallel_safety\nFROM pg_proc p\nJOIN pg_namespace n ON n.oid = p.pronamespace\nJOIN pg_language l ON l.oid = p.prolang\nWHERE p.prokind = 'f'\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND NOT EXISTS (\n      SELECT 1 FROM pg_depend dep\n      WHERE dep.classid = 'pg_proc'::regclass\n        AND dep.objid = p.oid\n        AND dep.deptype = 'e'\n  )\nORDER BY n.nspname, p.proname;"
    },
    {
        "id": 31,
        "title": "Views",
        "method": "PostgreSQLConnector.get_views()",
        "description": "Regular and materialized view inventory.",
        "headers": [
            "Schema",
            "View Name",
            "Definition"
        ],
        "category": "Objects",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS view_name,\n    pg_get_viewdef(c.oid) AS definition,\n    CASE c.relkind\n        WHEN 'v' THEN 'VIEW'\n        WHEN 'm' THEN 'MATERIALIZED VIEW'\n    END AS object_type\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('v', 'm')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND NOT EXISTS (\n      SELECT 1 FROM pg_depend dep\n      WHERE dep.classid = 'pg_class'::regclass\n        AND dep.objid = c.oid\n        AND dep.deptype = 'e'\n  )\nORDER BY n.nspname, c.relname;"
    },
    {
        "id": 32,
        "title": "Triggers",
        "method": "PostgreSQLConnector.get_triggers()",
        "description": "Table trigger inventory.",
        "headers": [
            "Schema",
            "Table Name",
            "Trigger Name",
            "Definition"
        ],
        "category": "Objects",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    t.tgname AS trigger_name,\n    pg_get_triggerdef(t.oid, true) AS definition\nFROM pg_trigger t\nJOIN pg_class c ON c.oid = t.tgrelid\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE NOT t.tgisinternal\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\nORDER BY n.nspname, c.relname, t.tgname;"
    },
    {
        "id": 33,
        "title": "Scheduled jobs",
        "method": "PostgreSQLConnector.get_scheduled_jobs()",
        "description": "PostgreSQL itself does not provide a universal built-in scheduler equivalent",
        "headers": [
            "Job Name",
            "Schedule",
            "Active",
            "Database"
        ],
        "category": "Objects",
        "query": "SELECT\n    jobid::text AS job_name,\n    schedule,\n    active::text AS active,\n    command,\n    database\nFROM cron.job\nORDER BY jobid;"
    },
    {
        "id": 34,
        "title": "Users and roles",
        "method": "PostgreSQLConnector.get_users_and_roles()",
        "description": "PostgreSQL role/account configuration.",
        "headers": [
            "Role Name",
            "Superuser",
            "Create DB",
            "Create Role",
            "Login",
            "Connection Limit"
        ],
        "category": "Security",
        "query": "SELECT\n    rolname AS role_name,\n    rolsuper AS is_superuser,\n    rolcreatedb AS can_create_database,\n    rolcreaterole AS can_create_role,\n    rolcanlogin AS can_login,\n    rolreplication AS replication_role,\n    rolconnlimit AS connection_limit,\n    rolvaliduntil AS valid_until\nFROM pg_roles\nWHERE rolname NOT LIKE 'pg_%'\nORDER BY rolname;"
    },
    {
        "id": 35,
        "title": "Tablespace status and configuration",
        "method": "PostgreSQLConnector.get_tablespace_status()",
        "description": "PostgreSQL tablespace definitions and physical locations.",
        "headers": [
            "Tablespace Name",
            "Owner",
            "Location"
        ],
        "category": "Storage",
        "query": "SELECT\n    spcname AS tablespace_name,\n    pg_get_userbyid(spcowner) AS owner,\n    COALESCE(\n        NULLIF(pg_tablespace_location(oid), ''),\n        current_setting('data_directory')\n    ) AS location\nFROM pg_tablespace\nORDER BY spcname;"
    },
    {
        "id": 36,
        "title": "Shared memory / memory configuration",
        "method": "PostgreSQLConnector.get_memory_configuration()",
        "description": "PostgreSQL memory-related configuration such as shared_buffers and work_mem.",
        "headers": [
            "Parameter",
            "Setting",
            "Unit"
        ],
        "category": "I/O",
        "query": "SELECT\n    name AS parameter,\n    setting,\n    unit\nFROM pg_settings\nWHERE name IN (\n    'shared_buffers',\n    'work_mem',\n    'maintenance_work_mem',\n    'effective_cache_size',\n    'temp_buffers',\n    'wal_buffers',\n    'huge_pages'\n)\nORDER BY name;"
    },
    {
        "id": 37,
        "title": "Memory and cache statistics",
        "method": "PostgreSQLConnector.get_memory_cache_statistics()",
        "description": "PostgreSQL cache-hit and backend activity statistics.",
        "headers": [
            "Metric",
            "Value"
        ],
        "category": "Overview",
        "query": "SELECT\n    'blks_hit' AS metric,\n    SUM(blks_hit)::numeric AS value\nFROM pg_stat_database\nUNION ALL\nSELECT\n    'blks_read',\n    SUM(blks_read)::numeric\nFROM pg_stat_database\nUNION ALL\nSELECT\n    'temp_bytes',\n    SUM(temp_bytes)::numeric\nFROM pg_stat_database;"
    },
    {
        "id": 38,
        "title": "Temporary file usage",
        "method": "PostgreSQLConnector.get_temp_file_usage()",
        "description": "Temporary-file generation by database (filters out 0 temp usage).",
        "headers": [
            "Database",
            "Temp Files",
            "Size (MB)",
            "Size (GB)",
            "Pretty Size"
        ],
        "category": "Overview",
        "query": "SELECT\n    datname AS database_name,\n    temp_files,\n    ROUND((temp_bytes / 1024.0 / 1024)::numeric, 2) AS size_mb,\n    ROUND((temp_bytes / 1024.0 / 1024 / 1024)::numeric, 2) AS size_gb,\n    pg_size_pretty(temp_bytes) AS temp_bytes\nFROM pg_stat_database\nWHERE datname IS NOT NULL\n  AND (temp_files > 0 OR temp_bytes > 0)\nORDER BY pg_stat_database.temp_bytes DESC;"
    },
    {
        "id": 39,
        "title": "Sessions and connections",
        "method": "PostgreSQLConnector.get_sessions_and_connections()",
        "description": "Current PostgreSQL backend sessions grouped by state.",
        "headers": [
            "State",
            "Session Count"
        ],
        "category": "I/O",
        "query": "SELECT\n    COALESCE(state, 'unknown') AS state,\n    COUNT(*) AS session_count\nFROM pg_stat_activity\nGROUP BY state\nORDER BY session_count DESC;"
    },
    {
        "id": 40,
        "title": "Long-running sessions / queries",
        "method": "PostgreSQLConnector.get_long_running_sessions()",
        "description": "Active sessions whose current query has been running for at least",
        "headers": [
            "PID",
            "User",
            "Database",
            "State",
            "Duration",
            "Query"
        ],
        "category": "I/O",
        "query": "SELECT\n    pid,\n    usename AS username,\n    datname AS database_name,\n    state,\n    clock_timestamp() - query_start AS duration,\n    wait_event_type,\n    wait_event,\n    LEFT(query, 200) AS query_sample\nFROM pg_stat_activity\nWHERE state = 'active'\n  AND query_start IS NOT NULL\n  AND clock_timestamp() - query_start >= INTERVAL '5 minutes'\nORDER BY query_start ASC\nLIMIT 100;"
    },
    {
        "id": 41,
        "title": "Locks",
        "method": "PostgreSQLConnector.get_locks()",
        "description": "Current locks held or awaited by PostgreSQL sessions, displaying default VirtualXID locks, system catalog relation locks, fastpath locks, and user table/transaction locks.",
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
            "Database"
        ],
        "category": "Locks",
        "query": "SELECT\n    l.pid,\n    l.locktype,\n    l.mode,\n    l.granted::text AS granted,\n    COALESCE(l.relation::regclass::text, 'N/A') AS relation,\n    COALESCE(l.transactionid::text, 'N/A') AS transaction_id,\n    CASE\n        WHEN l.locktype = 'virtualxid' THEN 'VirtualXID (Default Session Lock)'\n        WHEN l.locktype = 'transactionid' THEN 'TransactionID (Row/Txn Lock)'\n        WHEN l.locktype = 'relation' AND n.nspname IN ('pg_catalog', 'information_schema') THEN 'System Relation (Catalog Lock)'\n        WHEN l.locktype = 'relation' THEN 'User Relation (' || COALESCE(l.relation::regclass::text, 'OID ' || l.relation::text) || ')'\n        ELSE INITCAP(l.locktype)\n    END AS lock_category,\n    l.fastpath::text AS fastpath,\n    a.usename AS username,\n    a.datname AS database_name\nFROM pg_locks l\nLEFT JOIN pg_class c ON c.oid = l.relation\nLEFT JOIN pg_namespace n ON n.oid = c.relnamespace\nLEFT JOIN pg_stat_activity a ON a.pid = l.pid\nORDER BY l.granted, l.pid, l.locktype;"
    },
    {
        "id": 42,
        "title": "Blocking sessions",
        "method": "PostgreSQLConnector.get_blocking_sessions()",
        "description": "Sessions waiting for locks held by other sessions.",
        "headers": [
            "Blocked PID",
            "Blocking PID",
            "Blocked Query",
            "Blocking Query"
        ],
        "category": "I/O",
        "query": "SELECT\n    blocked.pid AS blocked_pid,\n    blocking.pid AS blocking_pid,\n    blocked.usename AS blocked_user,\n    blocking.usename AS blocking_user,\n    clock_timestamp() - blocked.query_start AS blocked_duration,\n    LEFT(blocked.query, 200) AS blocked_query,\n    LEFT(blocking.query, 200) AS blocking_query\nFROM pg_stat_activity blocked\nCROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS bp(blocking_pid)\nJOIN pg_stat_activity blocking ON blocking.pid = bp.blocking_pid\nORDER BY blocked_duration DESC;"
    },
    {
        "id": 43,
        "title": "Slow / resource-intensive SQL",
        "method": "PostgreSQLConnector.get_slow_sql()",
        "description": "Top SQL statements by cumulative execution time.",
        "headers": [
            "Query ID",
            "Calls",
            "Total Time",
            "Mean Time",
            "Rows",
            "Query"
        ],
        "category": "Query Performance",
        "query": "SELECT\n    queryid::text AS queryid,\n    calls,\n    ROUND((total_exec_time / 1000.0)::numeric, 2) AS total_seconds,\n    ROUND(mean_exec_time::numeric, 2) AS mean_ms,\n    rows,\n    LEFT(query, 200) AS query_sample\nFROM pg_stat_statements\nORDER BY total_exec_time DESC\nLIMIT 50;"
    },
    {
        "id": 44,
        "title": "SQL examining / reading large amounts of data",
        "method": "PostgreSQLConnector.get_large_data_examination_sql()",
        "description": "SQL statements responsible for high block-read activity.",
        "headers": [
            "Query ID",
            "Calls",
            "Shared Blocks Read",
            "Temp Blocks Read",
            "Rows",
            "Query"
        ],
        "category": "Overview",
        "query": "SELECT\n    queryid,\n    calls,\n    shared_blks_read,\n    temp_blks_read,\n    rows,\n    LEFT(query, 200) AS query_sample\nFROM pg_stat_statements\nORDER BY shared_blks_read DESC\nLIMIT 50;"
    },
    {
        "id": 45,
        "title": "Most frequently executed SQL",
        "method": "PostgreSQLConnector.get_frequently_executed_sql()",
        "description": "SQL statements ranked by execution count.",
        "headers": [
            "Query ID",
            "Calls",
            "Total Time",
            "Query"
        ],
        "category": "Query Performance",
        "query": "SELECT\n    queryid,\n    calls,\n    ROUND(total_exec_time / 1000.0, 2) AS total_seconds,\n    LEFT(query, 200) AS query_sample\nFROM pg_stat_statements\nORDER BY calls DESC\nLIMIT 50;"
    },
    {
        "id": 46,
        "title": "Top wait events",
        "method": "PostgreSQLConnector.get_top_wait_events()",
        "description": "Current sessions waiting on PostgreSQL wait events.",
        "headers": [
            "Wait Event Type",
            "Wait Event",
            "Active Sessions"
        ],
        "category": "I/O",
        "query": "SELECT\n    wait_event_type,\n    wait_event,\n    COUNT(*) AS active_sessions\nFROM pg_stat_activity\nWHERE wait_event IS NOT NULL\nGROUP BY wait_event_type, wait_event\nORDER BY active_sessions DESC, wait_event_type, wait_event;"
    },
    {
        "id": 47,
        "title": "Database workload / activity profile",
        "method": "PostgreSQLConnector.get_database_activity_profile()",
        "description": "High-level workload and I/O activity by database.",
        "headers": [
            "Database",
            "Transactions",
            "Blocks Read",
            "Blocks Hit",
            "Tuples Returned",
            "Temp Bytes"
        ],
        "category": "Overview",
        "query": "SELECT\n    datname AS database_name,\n    xact_commit,\n    xact_rollback,\n    blks_read,\n    blks_hit,\n    tup_returned,\n    tup_fetched,\n    tup_inserted,\n    tup_updated,\n    tup_deleted,\n    temp_bytes\nFROM pg_stat_database\nORDER BY (xact_commit + xact_rollback) DESC;"
    },
    {
        "id": 48,
        "title": "Replication / database role",
        "method": "PostgreSQLConnector.get_replication_status()",
        "description": "PostgreSQL recovery and replication state.",
        "headers": [
            "In Recovery",
            "Primary/Standby State",
            "WAL LSN",
            "Replication Sessions"
        ],
        "category": "I/O",
        "query": "SELECT\n    pg_is_in_recovery() AS is_in_recovery,\n    CASE\n        WHEN pg_is_in_recovery() THEN 'STANDBY/RECOVERY'\n        ELSE 'PRIMARY'\n    END AS database_role,\n    CASE\n        WHEN pg_is_in_recovery() THEN pg_last_wal_replay_lsn()\n        ELSE pg_current_wal_lsn()\n    END AS current_or_replay_wal_lsn,\n    CASE\n        WHEN pg_is_in_recovery() THEN NULL\n        ELSE (SELECT COUNT(*) FROM pg_stat_replication)\n    END AS replication_sessions;"
    },
    {
        "id": 49,
        "title": "WAL / archive configuration",
        "method": "PostgreSQLConnector.get_wal_archive_configuration()",
        "description": "WAL and archive-related configuration.",
        "headers": [
            "Parameter",
            "Setting"
        ],
        "category": "I/O",
        "query": "SELECT\n    name,\n    setting,\n    unit\nFROM pg_settings\nWHERE name IN (\n    'wal_level',\n    'archive_mode',\n    'archive_command',\n    'archive_timeout',\n    'max_wal_size',\n    'min_wal_size'\n)\nORDER BY name;"
    },
    {
        "id": 50,
        "title": "WAL generation",
        "method": "PostgreSQLConnector.get_wal_generation()",
        "description": "Cumulative WAL generation statistics.",
        "headers": [
            "WAL Records",
            "WAL Full Page Images",
            "WAL Bytes",
            "WAL FPI"
        ],
        "category": "I/O",
        "query": "SELECT * FROM pg_stat_wal;"
    },
    {
        "id": 51,
        "title": "WAL / checkpoint activity",
        "method": "PostgreSQLConnector.get_wal_checkpoint_activity()",
        "description": "Checkpoint activity from pg_stat_checkpointer. This catalog view is",
        "headers": [
            "Checkpoints",
            "Write Time",
            "Sync Time",
            "Buffers Written"
        ],
        "category": "Replication",
        "query": "SELECT\n    num_timed AS checkpoints_timed,\n    num_requested AS checkpoints_req,\n    write_time AS checkpoint_write_time,\n    sync_time AS checkpoint_sync_time,\n    buffers_written AS buffers_checkpoint\nFROM pg_stat_checkpointer;"
    },
    {
        "id": 52,
        "title": "Transaction ID / vacuum health",
        "method": "PostgreSQLConnector.get_transaction_vacuum_health()",
        "description": "Transaction-ID age and vacuum-related risk indicators.",
        "headers": [
            "Database",
            "Age(relfrozenxid)",
            "Oldest XID Age"
        ],
        "category": "I/O",
        "query": "SELECT\n    datname AS database_name,\n    age(datfrozenxid) AS frozen_xid_age\nFROM pg_database\nORDER BY age(datfrozenxid) DESC;"
    },
    {
        "id": 53,
        "title": "PostgreSQL data directory / physical layout",
        "method": "PostgreSQLConnector.get_physical_layout()",
        "description": "Important PostgreSQL physical and configuration file locations.",
        "headers": [
            "Data Directory",
            "Config File",
            "HBA File",
            "Ident File"
        ],
        "category": "Environment",
        "query": "SELECT\n    current_setting('data_directory') AS data_directory,\n    current_setting('config_file') AS config_file,\n    current_setting('hba_file') AS hba_file,\n    current_setting('ident_file') AS ident_file;"
    },
    {
        "id": 54,
        "title": "Tablespace locations",
        "method": "PostgreSQLConnector.get_storage_capacity()",
        "description": "PostgreSQL tablespace locations. This query does not provide filesystem",
        "headers": [
            "Tablespace Name",
            "Location"
        ],
        "category": "Storage",
        "query": "SELECT\n    spcname AS tablespace_name,\n    COALESCE(\n        NULLIF(pg_tablespace_location(oid), ''),\n        current_setting('data_directory')\n    ) AS location\nFROM pg_tablespace\nORDER BY spcname;"
    },
    {
        "id": 55,
        "title": "Database object storage summary",
        "method": "PostgreSQLConnector.get_database_storage_summary()",
        "description": "Current database storage summary for user tables and indexes.",
        "headers": [
            "Database",
            "Relation Count",
            "Table Size (MB)",
            "Index Size (MB)",
            "Total Size (MB)",
            "Table Size (GB)",
            "Index Size (GB)",
            "Total Size (GB)"
        ],
        "category": "Storage",
        "query": "SELECT\n    current_database() AS database_name,\n    COUNT(*) AS relation_count,\n    ROUND((COALESCE(SUM(pg_relation_size(c.oid)), 0) / 1024.0 / 1024)::numeric, 2) AS table_mb,\n    ROUND((COALESCE(SUM(pg_indexes_size(c.oid)), 0) / 1024.0 / 1024)::numeric, 2) AS index_mb,\n    ROUND((COALESCE(SUM(pg_total_relation_size(c.oid)), 0) / 1024.0 / 1024)::numeric, 2) AS total_mb,\n    ROUND((COALESCE(SUM(pg_relation_size(c.oid)), 0) / 1024.0 / 1024 / 1024)::numeric, 2) AS table_gb,\n    ROUND((COALESCE(SUM(pg_indexes_size(c.oid)), 0) / 1024.0 / 1024 / 1024)::numeric, 2) AS index_gb,\n    ROUND((COALESCE(SUM(pg_total_relation_size(c.oid)), 0) / 1024.0 / 1024 / 1024)::numeric, 2) AS total_gb\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%'\n  AND n.nspname NOT LIKE 'pg_temp_%';"
    },
    {
        "id": 56,
        "title": "Identify archival candidates",
        "method": "PostgreSQLConnector.get_archival_candidates()",
        "description": "Candidate tables for archival review based primarily on estimated row",
        "headers": [
            "Schema",
            "Table Name",
            "Estimated Rows",
            "Last Analyze",
            "Last Autoanalyze",
            "Table Size"
        ],
        "category": "Overview",
        "query": "SELECT\n    n.nspname AS schema_name,\n    c.relname AS table_name,\n    c.reltuples AS estimated_rows,\n    st.last_analyze,\n    st.last_autoanalyze,\n    ROUND(\n        pg_total_relation_size(c.oid) / 1024.0 / 1024 / 1024,\n        2\n    ) AS total_size_gb\nFROM pg_class c\nJOIN pg_namespace n ON n.oid = c.relnamespace\nLEFT JOIN pg_stat_all_tables st ON st.relid = c.oid\nWHERE c.relkind IN ('r','p')\n  AND n.nspname NOT IN ('pg_catalog','information_schema')\n  AND n.nspname NOT LIKE 'pg_toast%'\n  AND c.reltuples > 10000\nORDER BY pg_total_relation_size(c.oid) DESC;"
    },
    {
        "id": 57,
        "title": "Identify tables with limited usage",
        "method": "PostgreSQLConnector.get_tables_with_limited_usage()",
        "description": "Tables with low observed access activity since statistics reset.",
        "headers": [
            "Schema",
            "Table Name",
            "Sequential Scans",
            "Index Scans",
            "Rows Fetched"
        ],
        "category": "Overview",
        "query": "SELECT\n    schemaname AS schema_name,\n    relname AS table_name,\n    seq_scan,\n    idx_scan,\n    COALESCE(seq_scan,0) + COALESCE(idx_scan,0) AS total_scans,\n    seq_tup_read,\n    idx_tup_fetch\nFROM pg_stat_user_tables\nORDER BY total_scans ASC, schemaname, relname;"
    },
    {
        "id": 58,
        "title": "Identify hot tables / objects",
        "method": "PostgreSQLConnector.get_hot_tables()",
        "description": "Tables with high observed read/write activity.",
        "headers": [
            "Schema",
            "Table Name",
            "Sequential Scans",
            "Index Scans",
            "Inserts",
            "Updates",
            "Deletes"
        ],
        "category": "Overview",
        "query": "SELECT\n    schemaname AS schema_name,\n    relname AS table_name,\n    seq_scan,\n    idx_scan,\n    n_tup_ins AS inserts,\n    n_tup_upd AS updates,\n    n_tup_del AS deletes,\n    (COALESCE(seq_scan,0) + COALESCE(idx_scan,0)) AS total_scans\nFROM pg_stat_user_tables\nWHERE (\n    COALESCE(seq_scan,0) +\n    COALESCE(idx_scan,0) +\n    COALESCE(n_tup_ins,0) +\n    COALESCE(n_tup_upd,0) +\n    COALESCE(n_tup_del,0)\n) > 0\nORDER BY (\n    COALESCE(seq_scan,0) +\n    COALESCE(idx_scan,0) +\n    COALESCE(n_tup_ins,0) +\n    COALESCE(n_tup_upd,0) +\n    COALESCE(n_tup_del,0)\n) DESC\nLIMIT 100;"
    },
    {
        "id": 59,
        "title": "Table bloat / vacuum candidates",
        "method": "PostgreSQLConnector.get_table_bloat_candidates()",
        "description": "Tables with dead tuples and potentially overdue vacuum activity.",
        "headers": [
            "Schema",
            "Table Name",
            "Dead Tuples",
            "Live Tuples",
            "Last Vacuum",
            "Last Autovacuum"
        ],
        "category": "Overview",
        "query": "SELECT\n    schemaname AS schema_name,\n    relname AS table_name,\n    n_live_tup AS live_tuples,\n    n_dead_tup AS dead_tuples,\n    ROUND(\n        100.0 * n_dead_tup /\n        NULLIF(n_live_tup + n_dead_tup, 0), 2\n    ) AS dead_tuple_pct,\n    last_vacuum,\n    last_autovacuum\nFROM pg_stat_user_tables\nWHERE n_dead_tup > 0\nORDER BY dead_tuple_pct DESC NULLS LAST, n_dead_tup DESC;"
    },
    {
        "id": 60,
        "title": "Stored code / object dependencies",
        "method": "PostgreSQLConnector.get_stored_code_dependencies()",
        "description": "Dependency relationships for views, materialized views, functions and",
        "headers": [
            "Schema",
            "Object Name",
            "Object Type",
            "Referenced Object"
        ],
        "category": "Overview",
        "query": "SELECT DISTINCT\n    v_ns.nspname AS schema_name,\n    v.relname AS object_name,\n    CASE v.relkind\n        WHEN 'v' THEN 'VIEW'\n        WHEN 'm' THEN 'MATERIALIZED VIEW'\n    END AS object_type,\n    ref_ns.nspname || '.' || ref.relname AS referenced_object\nFROM pg_class v\nJOIN pg_namespace v_ns ON v_ns.oid = v.relnamespace\nJOIN pg_rewrite r ON r.ev_class = v.oid\nJOIN pg_depend d ON d.classid = 'pg_rewrite'::regclass AND d.objid = r.oid AND d.refclassid = 'pg_class'::regclass\nJOIN pg_class ref ON ref.oid = d.refobjid\nJOIN pg_namespace ref_ns ON ref_ns.oid = ref.relnamespace\nWHERE v.relkind IN ('v', 'm')\n  AND ref.oid <> v.oid\n  AND v_ns.nspname NOT IN ('pg_catalog','information_schema')\n  AND ref_ns.nspname NOT IN ('pg_catalog','information_schema')\n\nUNION ALL\n\nSELECT DISTINCT\n    p_ns.nspname AS schema_name,\n    p.proname AS object_name,\n    CASE p.prokind\n        WHEN 'f' THEN 'FUNCTION'\n        WHEN 'p' THEN 'PROCEDURE'\n        ELSE 'FUNCTION'\n    END AS object_type,\n    ref_ns.nspname || '.' || ref.relname AS referenced_object\nFROM pg_proc p\nJOIN pg_namespace p_ns ON p_ns.oid = p.pronamespace\nJOIN pg_depend d ON d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.refclassid = 'pg_class'::regclass\nJOIN pg_class ref ON ref.oid = d.refobjid\nJOIN pg_namespace ref_ns ON ref_ns.oid = ref.relnamespace\nWHERE p.prokind IN ('f', 'p')\n  AND p_ns.nspname NOT IN ('pg_catalog','information_schema')\n  AND ref_ns.nspname NOT IN ('pg_catalog','information_schema')\nORDER BY schema_name, object_name, referenced_object;\n\nNOTE:\nFor dependency rows involving objects not represented by pg_class/pg_proc,\nadditional pg_depend catalog decoding may be required. pg_depend is the\nauthoritative PostgreSQL dependency catalog."
    },
    {
        "id": 61,
        "title": "Configuration assessment (Top 10)",
        "method": "PostgreSQLConnector.get_configuration_assessment()",
        "description": "Key PostgreSQL server configuration parameters useful for assessment.",
        "headers": [
            "Parameter Name",
            "Setting",
            "Unit",
            "Context"
        ],
        "category": "I/O",
        "query": "SELECT\n    name AS parameter_name,\n    setting,\n    unit,\n    short_desc AS description\nFROM pg_settings\nWHERE name IN (\n    'max_connections',\n    'shared_buffers',\n    'effective_cache_size',\n    'work_mem',\n    'maintenance_work_mem',\n    'wal_buffers',\n    'checkpoint_timeout',\n    'max_wal_size',\n    'random_page_cost',\n    'effective_io_concurrency'\n)\nORDER BY CASE name\n    WHEN 'max_connections' THEN 1\n    WHEN 'shared_buffers' THEN 2\n    WHEN 'effective_cache_size' THEN 3\n    WHEN 'work_mem' THEN 4\n    WHEN 'maintenance_work_mem' THEN 5\n    WHEN 'wal_buffers' THEN 6\n    WHEN 'checkpoint_timeout' THEN 7\n    WHEN 'max_wal_size' THEN 8\n    WHEN 'random_page_cost' THEN 9\n    WHEN 'effective_io_concurrency' THEN 10\n    ELSE 11\nEND;\n\n\n================================================================================\nSCHEMA FILTERING / CONNECTOR IMPLEMENTATION\n================================================================================\n\nFor connector implementations that support:\n  1. One selected schema\n  2. Entire database\n\napply the schema predicate dynamically.\n\nFor pg_class / pg_namespace based queries:\n    AND n.nspname = :schema_name\n\nFor information_schema queries:\n    AND table_schema = :schema_name\n\nFor pg_stat_user_tables / pg_stat_all_indexes:\n    AND schemaname = :schema_name\n\nFor pg_proc / pg_namespace based queries:\n    AND n.nspname = :schema_name\n\nWhen \"Entire Database\" is selected, omit the schema predicate.\n\nDo NOT apply schema filtering to cluster/database-wide insights such as:\n  - PostgreSQL version/environment\n  - Database inventory\n  - Users and roles\n  - Server memory/configuration\n  - WAL/archive configuration\n  - Replication role\n  - Physical/configuration file locations\n\nFor PostgreSQL extensions:\n  - pg_stat_statements queries require pg_stat_statements.\n  - cron.job queries require pg_cron.\n  - pg_stat_checkpointer is used for current PostgreSQL checkpoint statistics.\n\nImportant:\n  - Estimated row counts (reltuples/n_live_tup) are not exact counts.\n  - Dead-tuple percentage is not exact physical bloat percentage.\n  - Tablespace location queries do not provide filesystem total/used/free capacity.\n  - Partition hierarchy queries using pg_inherits should be interpreted carefully because\n    pg_inherits also represents table inheritance.\n  - Duplicate-index candidates require review before dropping any index.\n  - Archival/limited-usage candidates are recommendations only and depend on workload,\n    retention policies and statistics-reset timing.\n\n================================================================================\nEND OF POSTGRESQL INSIGHTS & SQL QUERIES REFERENCE\n================================================================================"
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


_PG_ALIASES = {
    "scheduled jobs": "33",
    "events / scheduled jobs": "33",
    "events": "33",
    "slow / resource-intensive sql": "43",
    "slow queries": "43",
    "wal generation": "50",
    "binary log size": "50",
    "check table fragmentation": "60",
    "table bloat / vacuum candidates": "60",
    "fragmentation": "60",
}
for alias, id_val in _PG_ALIASES.items():
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
        
    # 2. Match exact ID or leading ID number e.g. '33' or '33. Scheduled Jobs'
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
    """Return all insight definitions for PostgreSQL."""
    return INSIGHTS
