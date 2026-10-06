"""
SQLServer Database Insights & Dynamic SQL Queries
Auto-documented query methods and metadata reference for SQLServer.
"""

import re
from typing import Any, Dict, List, Optional

INSIGHTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Server Environment",
        "method": "SQLServerConnector.get_server_environment()",
        "description": "Identifies the SQL Server instance version and edition.",
        "headers": [
            "Server Name",
            "Product Version",
            "Edition",
            "Engine Edition"
        ],
        "category": "Environment",
        "query": "SELECT\n                CAST(SERVERPROPERTY('ServerName') AS NVARCHAR(255)) AS server_name,\n                CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(255)) AS product_version,\n                CAST(SERVERPROPERTY('Edition') AS NVARCHAR(255)) AS edition,\n                CAST(SERVERPROPERTY('EngineEdition') AS NVARCHAR(255)) AS engine_edition"
    },
    {
        "id": 2,
        "title": "Database Inventory",
        "method": "SQLServerConnector.get_database_inventory()",
        "description": "Lists databases, state, recovery model, storage allocations, and total summary size.",
        "headers": [
            "Database Name",
            "State",
            "Recovery Model",
            "Compatibility Level",
            "Data Size (GB)",
            "Log Size (GB)",
            "Total Size (GB)"
        ],
        "category": "Overview",
        "query": "SELECT\n                d.name AS database_name,\n                d.state_desc,\n                d.recovery_model_desc,\n                d.compatibility_level,\n                ROUND(SUM(CASE WHEN f.type_desc = \\'ROWS\\' THEN f.size ELSE 0 END) * 8.0 / 1024 / 1024, 2) AS data_size_gb,\n                ROUND(SUM(CASE WHEN f.type_desc = \\'LOG\\' THEN f.size ELSE 0 END) * 8.0 / 1024 / 1024, 2) AS log_size_gb,\n                ROUND(SUM(f.size) * 8.0 / 1024 / 1024, 2) AS total_size_gb\n            FROM sys.databases d\n            LEFT JOIN sys.master_files f ON f.database_id = d.database_id\n            WHERE {db_cond}\n            GROUP BY d.name, d.state_desc, d.recovery_model_desc, d.compatibility_level\n            ORDER BY total_size_gb DESC"
    },
    {
        "id": 3,
        "title": "Database File Configuration",
        "method": "SQLServerConnector.get_database_file_configuration()",
        "description": "Reviews database file locations, sizes, and autogrowth configuration.",
        "headers": [
            "Database Name",
            "Logical File Name",
            "File Type",
            "Physical Name",
            "Size (GB)",
            "Growth Setting"
        ],
        "category": "I/O",
        "query": "SELECT\n                DB_NAME(database_id) AS database_name,\n                name AS logical_file_name,\n                type_desc AS file_type,\n                physical_name,\n                ROUND(size * 8.0 / 1024 / 1024, 2) AS size_gb,\n                CASE\n                    WHEN is_percent_growth = 1 THEN CONCAT(growth, '%')\n                    ELSE CONCAT(ROUND(growth * 8.0 / 1024, 2), ' MB')\n                END AS growth_setting\n            FROM sys.master_files\n            WHERE {db_cond}\n            ORDER BY size DESC"
    },
    {
        "id": 4,
        "title": "Data Vs Log Storage",
        "method": "SQLServerConnector.get_data_vs_log_storage()",
        "description": "Highlights databases where transaction-log allocation is large relative to data allocation.",
        "headers": [
            "Database Name",
            "Data (GB)",
            "Log (GB)",
            "Log to Data Ratio (%)"
        ],
        "category": "Storage",
        "query": "WITH sizes AS (\n                SELECT\n                    database_id,\n                    SUM(CASE WHEN type_desc = 'ROWS' THEN size ELSE 0 END) AS data_pages,\n                    SUM(CASE WHEN type_desc = 'LOG' THEN size ELSE 0 END) AS log_pages\n                FROM sys.master_files\n                WHERE {db_cond}\n                GROUP BY database_id\n            )\n            SELECT\n                DB_NAME(database_id) AS database_name,\n                ROUND(data_pages * 8.0 / 1024 / 1024, 2) AS data_gb,\n                ROUND(log_pages * 8.0 / 1024 / 1024, 2) AS log_gb,\n                ROUND(log_pages * 100.0 / NULLIF(data_pages, 0), 2) AS log_to_data_ratio_pct\n            FROM sizes\n            ORDER BY log_to_data_ratio_pct DESC"
    },
    {
        "id": 5,
        "title": "Database Free Space",
        "method": "SQLServerConnector.get_database_free_space()",
        "description": "Estimates allocated, used, and free space within data files.",
        "headers": [
            "Database Name",
            "File Name",
            "Allocated (GB)",
            "Used (GB)",
            "Free (GB)",
            "Free (%)"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                df.name AS file_name,\n                ROUND(df.size * 8.0 / 1024 / 1024, 2) AS allocated_gb,\n                ROUND(FILEPROPERTY(df.name, ''SpaceUsed'') * 8.0 / 1024 / 1024, 2) AS used_gb,\n                ROUND((df.size - FILEPROPERTY(df.name, ''SpaceUsed'')) * 8.0 / 1024 / 1024, 2) AS free_gb,\n                ROUND((df.size - FILEPROPERTY(df.name, ''SpaceUsed'')) * 100.0 / NULLIF(df.size,0), 2) AS free_pct\n            FROM sys.database_files df\n            WHERE df.type_desc = ''ROWS'';\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 6,
        "title": "Top 100 Largest Tables",
        "method": "SQLServerConnector.get_largest_tables()",
        "description": "Finds the top 100 largest user tables by row count across online user databases.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Row Count",
            "Reserved (MB)",
            "Reserved (GB)"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT TOP (100)\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                SUM(p.rows) AS row_count,\n                ROUND(SUM(a.total_pages) * 8.0 / 1024, 2) AS reserved_mb,\n                ROUND(SUM(a.total_pages) * 8.0 / 1024 / 1024, 4) AS reserved_gb\n            FROM sys.tables t\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            JOIN sys.indexes i ON i.object_id = t.object_id AND i.index_id IN (0,1)\n            JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id = i.index_id\n            JOIN sys.allocation_units a ON a.container_id = p.partition_id\n            GROUP BY s.name, t.name\n            ORDER BY SUM(p.rows) DESC;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 7,
        "title": "Schema Inventory",
        "method": "SQLServerConnector.get_schema_inventory()",
        "description": "Shows user schemas and the number of objects they contain.",
        "headers": [
            "Database Name",
            "Schema",
            "Object Count"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                COUNT(o.object_id) AS object_count\n            FROM sys.schemas s\n            LEFT JOIN sys.objects o ON o.schema_id = s.schema_id\n            WHERE s.name NOT IN (''sys'', ''INFORMATION_SCHEMA'')\n            GROUP BY s.name\n            HAVING COUNT(o.object_id) > 0\n            ORDER BY object_count DESC;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 8,
        "title": "Master (Parent) Tables",
        "method": "SQLServerConnector.get_master_tables()",
        "description": "Tables referenced by foreign key constraints in child tables.",
        "headers": [
            "Database Name",
            "Schema",
            "Master Table Name",
            "Child FKs In",
            "Referencing Child Tables"
        ],
        "category": "Schema",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            WITH rel AS (\n                SELECT DISTINCT\n                    ps.name AS schema_name,\n                    pt.name AS table_name,\n                    CONCAT(cs.name, ''.'', ct.name) AS child_table,\n                    fk.object_id AS fk_id\n                FROM sys.foreign_keys fk\n                JOIN sys.tables pt ON pt.object_id = fk.referenced_object_id\n                JOIN sys.schemas ps ON ps.schema_id = pt.schema_id\n                JOIN sys.tables ct ON ct.object_id = fk.parent_object_id\n                JOIN sys.schemas cs ON cs.schema_id = ct.schema_id\n            )\n            SELECT\n                DB_NAME() AS database_name,\n                schema_name,\n                table_name,\n                COUNT(DISTINCT fk_id) AS child_fk_count,\n                STRING_AGG(child_table, '', '') WITHIN GROUP (ORDER BY child_table) AS child_tables\n            FROM rel\n            GROUP BY schema_name, table_name\n            ORDER BY child_fk_count DESC, schema_name, table_name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 9,
        "title": "Child Tables",
        "method": "SQLServerConnector.get_child_tables()",
        "description": "Tables containing foreign key constraints pointing to parent tables.",
        "headers": [
            "Database Name",
            "Schema",
            "Child Table Name",
            "Parent FKs Out",
            "Referenced Parent Tables"
        ],
        "category": "Schema",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            WITH rel AS (\n                SELECT DISTINCT\n                    cs.name AS schema_name,\n                    ct.name AS table_name,\n                    CONCAT(ps.name, ''.'', pt.name) AS parent_table,\n                    fk.object_id AS fk_id\n                FROM sys.foreign_keys fk\n                JOIN sys.tables ct ON ct.object_id = fk.parent_object_id\n                JOIN sys.schemas cs ON cs.schema_id = ct.schema_id\n                JOIN sys.tables pt ON pt.object_id = fk.referenced_object_id\n                JOIN sys.schemas ps ON ps.schema_id = pt.schema_id\n            )\n            SELECT\n                DB_NAME() AS database_name,\n                schema_name,\n                table_name,\n                COUNT(DISTINCT fk_id) AS parent_fk_count,\n                STRING_AGG(parent_table, '', '') WITHIN GROUP (ORDER BY parent_table) AS parent_tables\n            FROM rel\n            GROUP BY schema_name, table_name\n            ORDER BY parent_fk_count DESC, schema_name, table_name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 10,
        "title": "Independent Tables",
        "method": "SQLServerConnector.get_independent_tables()",
        "description": "Standalone tables with no foreign key relationships (neither parent nor child).",
        "headers": [
            "Database Name",
            "Schema",
            "Independent Table Name"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name\n            FROM sys.tables t\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            LEFT JOIN (\n                SELECT parent_object_id AS object_id FROM sys.foreign_keys\n                UNION\n                SELECT referenced_object_id AS object_id FROM sys.foreign_keys\n            ) fk ON fk.object_id = t.object_id\n            WHERE fk.object_id IS NULL\n              AND t.is_ms_shipped = 0\n            ORDER BY s.name, t.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 11,
        "title": "Table Inventory",
        "method": "SQLServerConnector.get_table_inventory()",
        "description": "Inventories user tables and their creation/modification metadata.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Create Date",
            "Modify Date"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                t.create_date,\n                t.modify_date\n            FROM sys.tables t\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            ORDER BY s.name, t.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 12,
        "title": "Primary Keys",
        "method": "SQLServerConnector.get_primary_keys()",
        "description": "Lists primary keys and their participating columns.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Primary Key Name",
            "Key Columns"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                kc.name AS primary_key_name,\n                STRING_AGG(c.name, '', '') WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_columns\n            FROM sys.key_constraints kc\n            JOIN sys.tables t ON t.object_id = kc.parent_object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id\n            JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id\n            WHERE kc.type = ''PK''\n            GROUP BY s.name, t.name, kc.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 13,
        "title": "Tables Without Primary Keys",
        "method": "SQLServerConnector.get_tables_without_primary_keys()",
        "description": "Identifies user tables that do not have a primary key.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name\n            FROM sys.tables t\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            LEFT JOIN sys.indexes i\n                ON i.object_id = t.object_id\n               AND i.is_primary_key = 1\n            WHERE i.object_id IS NULL\n              AND t.is_ms_shipped = 0\n            ORDER BY s.name, t.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 14,
        "title": "Foreign Keys",
        "method": "SQLServerConnector.get_foreign_keys()",
        "description": "Maps foreign-key relationships between tables.",
        "headers": [
            "Database Name",
            "Parent Schema",
            "Parent Table",
            "Child Schema",
            "Child Table",
            "Foreign Key Name"
        ],
        "category": "Schema",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                ps.name AS parent_schema,\n                pt.name AS parent_table,\n                rs.name AS child_schema,\n                rt.name AS child_table,\n                fk.name AS foreign_key_name\n            FROM sys.foreign_keys fk\n            JOIN sys.tables pt ON pt.object_id = fk.referenced_object_id\n            JOIN sys.schemas ps ON ps.schema_id = pt.schema_id\n            JOIN sys.tables rt ON rt.object_id = fk.parent_object_id\n            JOIN sys.schemas rs ON rs.schema_id = rt.schema_id\n            ORDER BY parent_schema, parent_table, child_schema, child_table;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 15,
        "title": "Tables With Many Foreign Keys",
        "method": "SQLServerConnector.get_tables_with_many_foreign_keys()",
        "description": "Identifies tables with many foreign-key relationships, useful for dependency and design review.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Foreign Key Count"
        ],
        "category": "Schema",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                COUNT(fk.object_id) AS foreign_key_count\n            FROM sys.tables t\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            LEFT JOIN sys.foreign_keys fk ON fk.parent_object_id = t.object_id\n            GROUP BY s.name, t.name\n            HAVING COUNT(fk.object_id) > 0\n            ORDER BY foreign_key_count DESC;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 16,
        "title": "Index Inventory",
        "method": "SQLServerConnector.get_index_inventory()",
        "description": "Inventories indexes and their main properties.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Index Name",
            "Index Type",
            "Is Unique",
            "Is Disabled"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                i.name AS index_name,\n                i.type_desc AS index_type,\n                i.is_unique,\n                i.is_disabled\n            FROM sys.indexes i\n            JOIN sys.tables t ON t.object_id = i.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            WHERE i.index_id > 0\n            ORDER BY i.type_desc, s.name, t.name, i.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 17,
        "title": "Index Count By Table",
        "method": "SQLServerConnector.get_index_count_by_table()",
        "description": "Finds tables with unusually high numbers of indexes.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Index Count"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                COUNT(i.index_id) AS index_count\n            FROM sys.tables t\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            LEFT JOIN sys.indexes i ON i.object_id = t.object_id AND i.index_id > 0\n            GROUP BY s.name, t.name\n            ORDER BY index_count DESC;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 18,
        "title": "Largest Indexes",
        "method": "SQLServerConnector.get_largest_indexes()",
        "description": "Identifies the top 100 largest indexes consuming the most storage.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Index Name",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT TOP (100)\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                i.name AS index_name,\n                ROUND(SUM(ps.reserved_page_count) * 8.0 / 1024, 2) AS size_mb,\n                ROUND(SUM(ps.reserved_page_count) * 8.0 / 1024 / 1024, 4) AS size_gb\n            FROM sys.dm_db_partition_stats ps\n            JOIN sys.indexes i ON i.object_id = ps.object_id AND i.index_id = ps.index_id\n            JOIN sys.tables t ON t.object_id = i.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            GROUP BY s.name, t.name, i.name\n            ORDER BY SUM(ps.reserved_page_count) DESC;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 19,
        "title": "Disabled Indexes",
        "method": "SQLServerConnector.get_disabled_indexes()",
        "description": "Finds disabled indexes that may affect query performance or maintenance processes.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Index Name"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                i.name AS index_name\n            FROM sys.indexes i\n            JOIN sys.tables t ON t.object_id = i.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            WHERE i.is_disabled = 1\n            ORDER BY s.name, t.name, i.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 20,
        "title": "Fragmented Indexes",
        "method": "SQLServerConnector.get_fragmented_indexes()",
        "description": "Finds indexes with significant logical fragmentation using LIMITED sampling.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Index Name",
            "Avg Fragmentation (%)",
            "Page Count"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                i.name AS index_name,\n                ips.avg_fragmentation_in_percent AS avg_fragmentation_pct,\n                ips.page_count\n            FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, ''LIMITED'') ips\n            JOIN sys.indexes i ON i.object_id = ips.object_id AND i.index_id = ips.index_id\n            JOIN sys.tables t ON t.object_id = ips.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            WHERE ips.index_id > 0\n              AND ips.page_count >= 1000\n              AND ips.avg_fragmentation_in_percent >= 30\n            ORDER BY ips.avg_fragmentation_in_percent DESC;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 21,
        "title": "Index Usage",
        "method": "SQLServerConnector.get_index_usage()",
        "description": "Shows index read/write activity for active indexes with recorded usage.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Index Name",
            "Seeks",
            "Scans",
            "Lookups",
            "Updates"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                i.name AS index_name,\n                COALESCE(us.user_seeks,0) AS seeks,\n                COALESCE(us.user_scans,0) AS scans,\n                COALESCE(us.user_lookups,0) AS lookups,\n                COALESCE(us.user_updates,0) AS updates\n            FROM sys.indexes i\n            JOIN sys.tables t ON t.object_id = i.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            LEFT JOIN sys.dm_db_index_usage_stats us\n                ON us.database_id = DB_ID()\n               AND us.object_id = i.object_id\n               AND us.index_id = i.index_id\n            WHERE i.index_id > 0\n              AND (COALESCE(us.user_seeks,0) + COALESCE(us.user_scans,0) + COALESCE(us.user_lookups,0) + COALESCE(us.user_updates,0)) > 0\n            ORDER BY (COALESCE(us.user_seeks,0) + COALESCE(us.user_scans,0) + COALESCE(us.user_lookups,0) + COALESCE(us.user_updates,0)) DESC, s.name, t.name, i.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 22,
        "title": "Duplicate Or Overlapping Indexes",
        "method": "SQLServerConnector.get_duplicate_or_overlapping_indexes()",
        "description": "Finds indexes with identical leading key-column definitions on the same table.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Index 1",
            "Index 2",
            "Key Columns"
        ],
        "category": "Indexes",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            WITH idx AS (\n                SELECT\n                    i.object_id,\n                    i.index_id,\n                    i.name,\n                    STRING_AGG(c.name, '', '') WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_columns\n                FROM sys.indexes i\n                JOIN sys.index_columns ic\n                  ON ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.key_ordinal > 0\n                JOIN sys.columns c\n                  ON c.object_id = ic.object_id AND c.column_id = ic.column_id\n                WHERE i.index_id > 0\n                GROUP BY i.object_id, i.index_id, i.name\n            )\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                a.name AS index_1,\n                b.name AS index_2,\n                a.key_columns\n            FROM idx a\n            JOIN idx b ON a.object_id = b.object_id\n                      AND a.key_columns = b.key_columns\n                      AND a.index_id < b.index_id\n            JOIN sys.tables t ON t.object_id = a.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            ORDER BY s.name, t.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 23,
        "title": "Missing Index Recommendations",
        "method": "SQLServerConnector.get_missing_index_recommendations()",
        "description": "Shows missing-index DMV recommendations that SQL Server has generated since the relevant DMV counters were populated.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "User Seeks",
            "User Scans",
            "Avg Cost",
            "Avg Impact (%)",
            "Equality Columns",
            "Inequality Columns",
            "Included Columns"
        ],
        "category": "I/O",
        "query": "SELECT\n                DB_NAME(mid.database_id) AS database_name,\n                OBJECT_SCHEMA_NAME(mid.object_id, mid.database_id) AS schema_name,\n                OBJECT_NAME(mid.object_id, mid.database_id) AS table_name,\n                migs.user_seeks,\n                migs.user_scans,\n                migs.avg_total_user_cost,\n                migs.avg_user_impact,\n                mid.equality_columns,\n                mid.inequality_columns,\n                mid.included_columns\n            FROM sys.dm_db_missing_index_groups mig\n            JOIN sys.dm_db_missing_index_group_stats migs\n                ON mig.index_group_handle = migs.group_handle\n            JOIN sys.dm_db_missing_index_details mid\n                ON mig.index_handle = mid.index_handle\n            WHERE {db_cond}\n            ORDER BY (migs.user_seeks + migs.user_scans) DESC"
    },
    {
        "id": 24,
        "title": "Views",
        "method": "SQLServerConnector.get_views()",
        "description": "Inventories views used in the database.",
        "headers": [
            "Database Name",
            "Schema",
            "View Name",
            "Create Date",
            "Modify Date"
        ],
        "category": "Objects",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                v.name AS view_name,\n                v.create_date,\n                v.modify_date\n            FROM sys.views v\n            JOIN sys.schemas s ON s.schema_id = v.schema_id\n            ORDER BY s.name, v.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 25,
        "title": "Stored Procedures",
        "method": "SQLServerConnector.get_stored_procedures()",
        "description": "Inventories stored procedures and modification timestamps.",
        "headers": [
            "Database Name",
            "Schema",
            "Procedure Name",
            "Create Date",
            "Modify Date"
        ],
        "category": "Objects",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                p.name AS procedure_name,\n                p.create_date,\n                p.modify_date\n            FROM sys.procedures p\n            JOIN sys.schemas s ON s.schema_id = p.schema_id\n            ORDER BY s.name, p.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 26,
        "title": "Functions",
        "method": "SQLServerConnector.get_functions()",
        "description": "Inventories user-defined functions.",
        "headers": [
            "Database Name",
            "Schema",
            "Function Name",
            "Function Type",
            "Create Date",
            "Modify Date"
        ],
        "category": "I/O",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                o.name AS function_name,\n                o.type_desc AS function_type,\n                o.create_date,\n                o.modify_date\n            FROM sys.objects o\n            JOIN sys.schemas s ON s.schema_id = o.schema_id\n            WHERE o.type IN (''FN'', ''IF'', ''TF'')\n            ORDER BY s.name, o.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 27,
        "title": "Triggers",
        "method": "SQLServerConnector.get_triggers()",
        "description": "Inventories DML triggers on user tables.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Trigger Name",
            "Is Disabled"
        ],
        "category": "Objects",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                tr.name AS trigger_name,\n                tr.is_disabled\n            FROM sys.triggers tr\n            JOIN sys.tables t ON t.object_id = tr.parent_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            WHERE tr.parent_class = 1\n            ORDER BY s.name, t.name, tr.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 28,
        "title": "Object Dependencies",
        "method": "SQLServerConnector.get_object_dependencies()",
        "description": "Maps module/object dependencies for impact analysis.",
        "headers": [
            "Database Name",
            "Referencing Schema",
            "Referencing Object",
            "Referencing Object Type",
            "Referenced Schema",
            "Referenced Object",
            "Referenced Object Type"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                OBJECT_SCHEMA_NAME(d.referencing_id) AS referencing_schema,\n                OBJECT_NAME(d.referencing_id) AS referencing_object,\n                COALESCE(o.type_desc, ''<unknown>'') AS referencing_object_type,\n                COALESCE(d.referenced_schema_name, ''<external/unknown>'') AS referenced_schema,\n                COALESCE(d.referenced_entity_name, ''<unknown>'') AS referenced_object,\n                COALESCE(ref_o.type_desc, d.referenced_class_desc, ''<unknown>'') AS referenced_object_type\n            FROM sys.sql_expression_dependencies d\n            LEFT JOIN sys.objects o ON o.object_id = d.referencing_id\n            LEFT JOIN sys.objects ref_o ON ref_o.object_id = d.referenced_id\n            WHERE d.referencing_id IS NOT NULL\n            ORDER BY referencing_schema, referencing_object;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 29,
        "title": "Database Roles",
        "method": "SQLServerConnector.get_database_roles()",
        "description": "Shows database role memberships for security review.",
        "headers": [
            "Database Name",
            "Role Name",
            "Member Name"
        ],
        "category": "Security",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                r.name AS role_name,\n                m.name AS member_name\n            FROM sys.database_role_members drm\n            JOIN sys.database_principals r ON r.principal_id = drm.role_principal_id\n            JOIN sys.database_principals m ON m.principal_id = drm.member_principal_id\n            ORDER BY r.name, m.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 30,
        "title": "Database Permissions",
        "method": "SQLServerConnector.get_database_permissions()",
        "description": "Reviews explicit database/object permissions granted or denied to non-system principals on user objects.",
        "headers": [
            "Database Name",
            "Grantee",
            "Permission",
            "State",
            "Schema",
            "Object Name"
        ],
        "category": "I/O",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                grantee.name AS grantee,\n                dp.permission_name,\n                dp.state_desc,\n                COALESCE(OBJECT_SCHEMA_NAME(dp.major_id), '''') AS schema_name,\n                COALESCE(OBJECT_NAME(dp.major_id), '''') AS object_name\n            FROM sys.database_permissions dp\n            JOIN sys.database_principals grantee\n                ON grantee.principal_id = dp.grantee_principal_id\n            WHERE grantee.name NOT IN (''public'', ''guest'', ''sys'', ''INFORMATION_SCHEMA'')\n              AND (dp.major_id = 0 OR OBJECT_SCHEMA_NAME(dp.major_id) NOT IN (''sys'', ''INFORMATION_SCHEMA''))\n              AND (dp.major_id = 0 OR OBJECTPROPERTY(dp.major_id, ''IsMSShipped'') = 0 OR OBJECTPROPERTY(dp.major_id, ''IsMSShipped'') IS NULL)\n            ORDER BY grantee.name, dp.permission_name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 31,
        "title": "SQL Agent Jobs",
        "method": "SQLServerConnector.get_sql_agent_jobs()",
        "description": "Inventories SQL Server Agent jobs and their enabled state.",
        "headers": [
            "Job Name",
            "Enabled",
            "Owner",
            "Date Created"
        ],
        "category": "Overview",
        "query": "SELECT\n                j.name AS job_name,\n                j.enabled,\n                SUSER_SNAME(j.owner_sid) AS owner,\n                j.date_created\n            FROM msdb.dbo.sysjobs j\n            ORDER BY j.name"
    },
    {
        "id": 32,
        "title": "Failed SQL Agent Jobs",
        "method": "SQLServerConnector.get_failed_sql_agent_jobs()",
        "description": "Finds recent SQL Server Agent job executions that did not succeed.",
        "headers": [
            "Job Name",
            "Run Datetime",
            "Run Status",
            "Message"
        ],
        "category": "Overview",
        "query": "SELECT TOP (100)\n                j.name AS job_name,\n                msdb.dbo.agent_datetime(h.run_date, h.run_time) AS run_datetime,\n                h.run_status,\n                h.message\n            FROM msdb.dbo.sysjobhistory h\n            JOIN msdb.dbo.sysjobs j ON j.job_id = h.job_id\n            WHERE h.step_id = 0\n              AND h.run_status <> 1\n            ORDER BY run_datetime DESC"
    },
    {
        "id": 33,
        "title": "Active Sessions",
        "method": "SQLServerConnector.get_active_sessions()",
        "description": "Shows currently active user sessions and their resource counters.",
        "headers": [
            "Session ID",
            "Login Name",
            "Host Name",
            "Program Name",
            "Status",
            "CPU Time",
            "Memory Usage",
            "Reads",
            "Writes"
        ],
        "category": "I/O",
        "query": "SELECT\n                s.session_id,\n                s.login_name,\n                s.host_name,\n                s.program_name,\n                s.status,\n                s.cpu_time,\n                s.memory_usage,\n                s.reads,\n                s.writes\n            FROM sys.dm_exec_sessions s\n            WHERE s.is_user_process = 1\n            ORDER BY s.cpu_time DESC"
    },
    {
        "id": 34,
        "title": "Blocking Sessions",
        "method": "SQLServerConnector.get_blocking_sessions()",
        "description": "Identifies currently blocked requests and their blockers.",
        "headers": [
            "Session ID",
            "Blocking Session ID",
            "Wait Type",
            "Wait Time (ms)",
            "Database",
            "SQL Text"
        ],
        "category": "I/O",
        "query": "SELECT\n                r.session_id,\n                r.blocking_session_id,\n                r.wait_type,\n                r.wait_time AS wait_time_ms,\n                DB_NAME(r.database_id) AS database_name,\n                t.text AS sql_text\n            FROM sys.dm_exec_requests r\n            CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t\n            WHERE r.blocking_session_id <> 0\n              AND {db_cond}\n            ORDER BY r.wait_time DESC"
    },
    {
        "id": 35,
        "title": "Long-Running Requests",
        "method": "SQLServerConnector.get_long_running_requests()",
        "description": "Finds currently executing requests with high elapsed time.",
        "headers": [
            "Session ID",
            "Database",
            "Start Time",
            "Elapsed Sec",
            "CPU Time (ms)",
            "SQL Text"
        ],
        "category": "Overview",
        "query": "SELECT\n                r.session_id,\n                DB_NAME(r.database_id) AS database_name,\n                r.start_time,\n                DATEDIFF(SECOND, r.start_time, GETDATE()) AS elapsed_seconds,\n                r.cpu_time AS cpu_time_ms,\n                t.text AS sql_text\n            FROM sys.dm_exec_requests r\n            CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t\n            WHERE r.session_id <> @@SPID\n              AND {db_cond}\n            ORDER BY elapsed_seconds DESC"
    },
    {
        "id": 36,
        "title": "Top CPU Queries",
        "method": "SQLServerConnector.get_top_cpu_queries()",
        "description": "Finds cached query statements consuming the most CPU.",
        "headers": [
            "Exec Count",
            "Total CPU (ms)",
            "Avg CPU (ms)",
            "Total Elapsed (ms)",
            "SQL Text"
        ],
        "category": "Query Performance",
        "query": "SELECT TOP (100)\n                qs.execution_count,\n                qs.total_worker_time / 1000 AS total_cpu_ms,\n                qs.total_worker_time / NULLIF(qs.execution_count,0) / 1000 AS avg_cpu_ms,\n                qs.total_elapsed_time / 1000 AS total_elapsed_ms,\n                SUBSTRING(st.text,\n                          (qs.statement_start_offset/2)+1,\n                          ((CASE qs.statement_end_offset\n                                WHEN -1 THEN DATALENGTH(st.text)\n                                ELSE qs.statement_end_offset END\n                            - qs.statement_start_offset)/2)+1) AS sql_text\n            FROM sys.dm_exec_query_stats qs\n            CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st\n            ORDER BY qs.total_worker_time DESC"
    },
    {
        "id": 37,
        "title": "Top IO Queries",
        "method": "SQLServerConnector.get_top_io_queries()",
        "description": "Finds cached queries with high logical I/O activity.",
        "headers": [
            "Exec Count",
            "Total Logical Reads",
            "Avg Logical Reads",
            "Total Logical Writes",
            "SQL Text"
        ],
        "category": "I/O",
        "query": "SELECT TOP (100)\n                qs.execution_count,\n                qs.total_logical_reads,\n                qs.total_logical_reads / NULLIF(qs.execution_count,0) AS avg_logical_reads,\n                qs.total_logical_writes,\n                SUBSTRING(st.text,\n                          (qs.statement_start_offset/2)+1,\n                          ((CASE qs.statement_end_offset\n                                WHEN -1 THEN DATALENGTH(st.text)\n                                ELSE qs.statement_end_offset END\n                            - qs.statement_start_offset)/2)+1) AS sql_text\n            FROM sys.dm_exec_query_stats qs\n            CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st\n            ORDER BY qs.total_logical_reads + qs.total_logical_writes DESC"
    },
    {
        "id": 38,
        "title": "Wait Statistics",
        "method": "SQLServerConnector.get_wait_statistics()",
        "description": "Displays top 20 meaningful resource wait statistics, excluding known idle background tasks.",
        "headers": [
            "Wait Type",
            "Waiting Tasks Count",
            "Wait Time (ms)",
            "Signal Wait Time (ms)"
        ],
        "category": "I/O",
        "query": "SELECT TOP (20)\n                wait_type,\n                waiting_tasks_count,\n                wait_time_ms,\n                signal_wait_time_ms\n            FROM sys.dm_os_wait_stats\n            WHERE wait_time_ms > 0\n              AND wait_type NOT IN (\n                'BROKER_EVENTHANDLER', 'BROKER_RECEIVE_WAITFOR', 'BROKER_TASK_STOP',\n                'BROKER_TO_FLUSH', 'BROKER_TRANSMITTER', 'CHECKPOINT_QUEUE', 'CHKPT',\n                'CLR_AUTO_EVENT', 'CLR_MANUAL_EVENT', 'CLR_SEMAPHORE', 'CXCONSUMER',\n                'DBMIRROR_DBM_EVENT', 'DBMIRROR_EVENTS_QUEUE', 'DBMIRROR_WORKER_QUEUE',\n                'DBMIRRORING_CMD', 'DIRTY_PAGE_POLL', 'DISPATCHER_QUEUE_SEMAPHORE',\n                'EXECSYNC', 'FSAGENT', 'FT_IFTS_SCHEDULER_IDLE_WAIT', 'FT_IFTSHC_MUTEX',\n                'HADR_CLUSAPI_CALL', 'HADR_FILESTREAM_IOMGR_IOCOMPLETION', 'HADR_LOGCAPTURE_WAIT',\n                'HADR_NOTIFICATION_DEQUEUE', 'HADR_TIMER_TASK', 'HADR_WORK_QUEUE',\n                'KSOURCE_WAKEUP', 'LAZYWRITER_SLEEP', 'LOGMGR_QUEUE', 'MEMORY_ALLOCATION_EXT',\n                'ONDEMAND_TASK_QUEUE', 'PARALLEL_REDO_DRAIN_WORKSPACE', 'PARALLEL_REDO_LOG_CACHE',\n                'PARALLEL_REDO_TRAN_LIST', 'PARALLEL_REDO_WORKER_SYNC', 'PARALLEL_REDO_WORKER_WAIT',\n                'PREEMPTIVE_OS_FLUSHFILTERBUFFERS', 'PREEMPTIVE_XE_GETTARGETSTATE',\n                'PWAIT_ALL_COMPONENTS_INITIALIZED', 'PWAIT_DIRECTLOGCONSUMER_GETNEXT',\n                'QDS_PERSIST_TASK_MAIN_LOOP_SLEEP', 'QDS_ASYNC_QUEUE',\n                'QDS_CLEANUP_STALE_QUERIES_TASK_MAIN_LOOP_SLEEP', 'QDS_SHUTDOWN_QUEUE',\n                'REDUNDANT_CLIENT_INFO', 'REQUEST_FOR_DEADLOCK_SEARCH', 'RESOURCE_QUEUE',\n                'SERVER_IDLE_CHECK', 'SLEEP_BPOOL_FLUSH', 'SLEEP_DBSTARTUP', 'SLEEP_DCOMSTARTUP',\n                'SLEEP_MASTERDBREADY', 'SLEEP_MASTERMDREADY', 'SLEEP_MASTERUPGRADED',\n                'SLEEP_MSDBSTARTUP', 'SLEEP_SYSTEMTASK', 'SLEEP_TASK', 'SLEEP_TEMPDBSTARTUP',\n                'SNI_HTTP_ACCEPT', 'SOS_WORK_DISPATCHER', 'SP_SERVER_DIAGNOSTICS_SLEEP',\n                'SQLTRACE_BUFFER_FLUSH', 'SQLTRACE_INCREMENTAL_FLUSH_SLEEP', 'SQLTRACE_WAIT_ENTRIES',\n                'STARTUP_DEPENDENCY_MANAGER', 'WAIT_FOR_RESULTS', 'WAITFOR',\n                'WAITFOR_TASKSHUTDOWN', 'WAIT_XTP_HOST_WAIT', 'WAIT_XTP_OFFLINE_CKPT_NEW_LOG',\n                'WAIT_XTP_CKPT_CLOSE', 'XE_DISPATCHER_JOIN', 'XE_DISPATCHER_WAIT',\n                'XE_TIMER_EVENT', 'XE_LIVE_TARGET_TVF'\n            )\n            ORDER BY wait_time_ms DESC"
    },
    {
        "id": 39,
        "title": "Active Transactions",
        "method": "SQLServerConnector.get_active_transactions()",
        "description": "Lists active transactions and their current state.",
        "headers": [
            "Transaction ID",
            "Begin Time",
            "State",
            "Session ID"
        ],
        "category": "I/O",
        "query": "SELECT\n                at.transaction_id,\n                at.transaction_begin_time,\n                at.transaction_state,\n                st.session_id\n            FROM sys.dm_tran_active_transactions at\n            LEFT JOIN sys.dm_tran_session_transactions st\n                ON st.transaction_id = at.transaction_id\n            ORDER BY at.transaction_begin_time"
    },
    {
        "id": 40,
        "title": "Long-Running Transactions",
        "method": "SQLServerConnector.get_long_running_transactions()",
        "description": "Identifies transactions that have remained active for a long time.",
        "headers": [
            "Session ID",
            "Begin Time",
            "Elapsed (min)",
            "Database Name"
        ],
        "category": "I/O",
        "query": "SELECT\n                st.session_id,\n                at.transaction_begin_time,\n                DATEDIFF(MINUTE, at.transaction_begin_time, GETDATE()) AS elapsed_minutes,\n                DB_NAME(dt.database_id) AS database_name\n            FROM sys.dm_tran_active_transactions at\n            JOIN sys.dm_tran_session_transactions st\n                ON st.transaction_id = at.transaction_id\n            LEFT JOIN sys.dm_tran_database_transactions dt\n                ON dt.transaction_id = at.transaction_id\n            WHERE {db_cond}\n            ORDER BY elapsed_minutes DESC"
    },
    {
        "id": 41,
        "title": "Memory Usage",
        "method": "SQLServerConnector.get_memory_usage()",
        "description": "Reports operating-system memory visibility and SQL Server memory state.",
        "headers": [
            "Total Physical Memory (GB)",
            "Used Physical Memory (GB)",
            "Available Physical Memory (GB)",
            "Memory State"
        ],
        "category": "Overview",
        "query": "SELECT\n                ROUND(total_physical_memory_kb / 1024.0 / 1024, 2) AS total_physical_memory_gb,\n                ROUND((total_physical_memory_kb - available_physical_memory_kb) / 1024.0 / 1024, 2) AS used_physical_memory_gb,\n                ROUND(available_physical_memory_kb / 1024.0 / 1024, 2) AS available_physical_memory_gb,\n                system_memory_state_desc AS memory_state\n            FROM sys.dm_os_sys_memory"
    },
    {
        "id": 42,
        "title": "TempDB Usage",
        "method": "SQLServerConnector.get_tempdb_usage()",
        "description": "Shows current TempDB allocation by session.",
        "headers": [
            "Session ID",
            "User Objects (MB)",
            "Internal Objects (MB)",
            "Total Allocated (MB)"
        ],
        "category": "Overview",
        "query": "SELECT\n                session_id,\n                ROUND((user_objects_alloc_page_count - user_objects_dealloc_page_count) * 8.0 / 1024, 2) AS user_objects_mb,\n                ROUND((internal_objects_alloc_page_count - internal_objects_dealloc_page_count) * 8.0 / 1024, 2) AS internal_objects_mb,\n                ROUND(((user_objects_alloc_page_count - user_objects_dealloc_page_count) + (internal_objects_alloc_page_count - internal_objects_dealloc_page_count)) * 8.0 / 1024, 2) AS total_allocated_mb\n            FROM sys.dm_db_session_space_usage\n            WHERE ((user_objects_alloc_page_count - user_objects_dealloc_page_count) + (internal_objects_alloc_page_count - internal_objects_dealloc_page_count)) > 0\n            ORDER BY total_allocated_mb DESC"
    },
    {
        "id": 43,
        "title": "TempDB File Configuration",
        "method": "SQLServerConnector.get_tempdb_file_configuration()",
        "description": "Reviews TempDB data/log file sizing and growth settings.",
        "headers": [
            "File ID",
            "File Name",
            "Physical Name",
            "Size (MB)",
            "Growth Setting"
        ],
        "category": "I/O",
        "query": "USE tempdb;\n            SELECT\n                file_id,\n                name AS file_name,\n                physical_name,\n                ROUND(size * 8.0 / 1024, 2) AS size_mb,\n                CASE\n                    WHEN is_percent_growth = 1 THEN CONCAT(growth, '%')\n                    ELSE CONCAT(ROUND(growth * 8.0 / 1024, 2), ' MB')\n                END AS growth_setting\n            FROM sys.database_files\n            ORDER BY file_id;"
    },
    {
        "id": 44,
        "title": "Query Store Status",
        "method": "SQLServerConnector.get_query_store_status()",
        "description": "Reviews Query Store configuration and storage state per database.",
        "headers": [
            "Database Name",
            "Desired State",
            "Actual State",
            "Readonly Reason",
            "Current Storage (MB)",
            "Max Storage (MB)"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                desired_state_desc AS desired_state,\n                actual_state_desc AS actual_state,\n                readonly_reason,\n                current_storage_size_mb,\n                max_storage_size_mb\n            FROM sys.database_query_store_options;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 45,
        "title": "Database Scoped Configuration",
        "method": "SQLServerConnector.get_database_scoped_configuration()",
        "description": "Reviews top 10 key database-scoped configuration settings per database.",
        "headers": [
            "Database Name",
            "Configuration Name",
            "Value",
            "Value for Secondary"
        ],
        "category": "I/O",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT TOP (10)\n                DB_NAME() AS database_name,\n                name AS configuration_name,\n                CAST(value AS NVARCHAR(255)) AS value,\n                CAST(value_for_secondary AS NVARCHAR(255)) AS value_for_secondary\n            FROM sys.database_scoped_configurations\n            WHERE LOWER(name) IN (\n                ''maxdop'',\n                ''legacy_cardinality_estimation'',\n                ''parameter_sniffing'',\n                ''query_optimizer_hotfixes'',\n                ''identity_cache'',\n                ''optimize_for_ad_hoc_workloads'',\n                ''elevate_online'',\n                ''elevate_resumable'',\n                ''lightweight_query_profiling'',\n                ''paused_resumable_index_abort_duration_minutes''\n            )\n            ORDER BY name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 46,
        "title": "Recovery Model And Log Reuse",
        "method": "SQLServerConnector.get_recovery_model_and_log_reuse()",
        "description": "Identifies recovery model and reasons that may prevent transaction-log reuse.",
        "headers": [
            "Database Name",
            "Recovery Model",
            "Log Reuse Wait Reason"
        ],
        "category": "Overview",
        "query": "SELECT\n                name AS database_name,\n                recovery_model_desc,\n                log_reuse_wait_desc\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond}\n            ORDER BY name"
    },
    {
        "id": 47,
        "title": "Backup History",
        "method": "SQLServerConnector.get_backup_history()",
        "description": "Reviews recent database backup history and backup types.",
        "headers": [
            "Database Name",
            "Backup Type",
            "Start Date",
            "Finish Date",
            "Backup Size (MB)"
        ],
        "category": "Overview",
        "query": "SELECT TOP (200)\n                d.name AS database_name,\n                CASE bs.type\n                    WHEN 'D' THEN 'FULL'\n                    WHEN 'I' THEN 'DIFFERENTIAL'\n                    WHEN 'L' THEN 'LOG'\n                    ELSE bs.type\n                END AS backup_type,\n                bs.backup_start_date,\n                bs.backup_finish_date,\n                ROUND(bs.backup_size / 1024.0 / 1024, 2) AS backup_size_mb\n            FROM msdb.dbo.backupset bs\n            JOIN sys.databases d ON d.name = bs.database_name\n            WHERE {db_cond}\n            ORDER BY bs.backup_finish_date DESC"
    },
    {
        "id": 48,
        "title": "Databases Without Recent Full Backup",
        "method": "SQLServerConnector.get_databases_without_recent_full_backup()",
        "description": "Identifies databases with no recorded full backup or no full backup within the selected assessment window.",
        "headers": [
            "Database Name",
            "Last Full Backup"
        ],
        "category": "Overview",
        "query": "SELECT\n                d.name AS database_name,\n                MAX(bs.backup_finish_date) AS last_full_backup\n            FROM sys.databases d\n            LEFT JOIN msdb.dbo.backupset bs\n                ON bs.database_name = d.name\n               AND bs.type = 'D'\n            WHERE {db_cond}\n            GROUP BY d.name\n            HAVING MAX(bs.backup_finish_date) IS NULL\n                OR MAX(bs.backup_finish_date) < DATEADD(DAY, -7, GETDATE())\n            ORDER BY last_full_backup"
    },
    {
        "id": 49,
        "title": "Always On Availability Status",
        "method": "SQLServerConnector.get_always_on_availability_status()",
        "description": "Reviews Always On availability replica health when HADR is configured.",
        "headers": [
            "Group Name",
            "Replica Server",
            "Role",
            "Operational State",
            "Connected State"
        ],
        "category": "Overview",
        "query": "SELECT\n                ag.name AS group_name,\n                ar.replica_server_name AS replica_server,\n                ars.role_desc,\n                ars.operational_state_desc,\n                ars.connected_state_desc\n            FROM sys.availability_groups ag\n            JOIN sys.availability_replicas ar\n                ON ar.group_id = ag.group_id\n            JOIN sys.dm_hadr_availability_replica_states ars\n                ON ars.replica_id = ar.replica_id\n            ORDER BY ag.name, ar.replica_server_name"
    },
    {
        "id": 50,
        "title": "Always On Database Synchronization",
        "method": "SQLServerConnector.get_always_on_database_synchronization()",
        "description": "Reviews database-level Always On synchronization and health.",
        "headers": [
            "Database Name",
            "Replica Server",
            "Synchronization State",
            "Synchronization Health"
        ],
        "category": "I/O",
        "query": "SELECT\n                DB_NAME(drs.database_id) AS database_name,\n                ar.replica_server_name AS replica_server,\n                drs.synchronization_state_desc,\n                drs.synchronization_health_desc\n            FROM sys.dm_hadr_database_replica_states drs\n            JOIN sys.availability_replicas ar\n                ON ar.replica_id = drs.replica_id\n            WHERE {db_cond}\n            ORDER BY database_name, replica_server"
    },
    {
        "id": 51,
        "title": "Linked Servers",
        "method": "SQLServerConnector.get_linked_servers()",
        "description": "Inventories configured linked servers and remote data providers.",
        "headers": [
            "Server Name",
            "Product",
            "Provider",
            "Data Source",
            "Is Linked"
        ],
        "category": "Overview",
        "query": "SELECT\n                name AS server_name,\n                product,\n                provider,\n                data_source,\n                is_linked\n            FROM sys.servers\n            WHERE is_linked = 1\n            ORDER BY name"
    },
    {
        "id": 52,
        "title": "Server Logins And Roles",
        "method": "SQLServerConnector.get_server_logins_and_roles()",
        "description": "Reviews SQL/Windows logins, disabled status, and fixed server-role membership.",
        "headers": [
            "Login Name",
            "Login Type",
            "Is Disabled",
            "Server Role"
        ],
        "category": "Security",
        "query": "SELECT\n                sp.name AS login_name,\n                sp.type_desc AS login_type,\n                sp.is_disabled,\n                sr.name AS server_role\n            FROM sys.server_principals sp\n            LEFT JOIN sys.server_role_members srm\n                ON srm.member_principal_id = sp.principal_id\n            LEFT JOIN sys.server_principals sr\n                ON sr.principal_id = srm.role_principal_id\n            WHERE sp.type IN ('S','U','G')\n            ORDER BY sp.name, sr.name"
    },
    {
        "id": 53,
        "title": "Database Owners",
        "method": "SQLServerConnector.get_database_owners()",
        "description": "Reviews database ownership for governance and security assessment.",
        "headers": [
            "Database Name",
            "Owner Name"
        ],
        "category": "Overview",
        "query": "SELECT\n                d.name AS database_name,\n                SUSER_SNAME(d.owner_sid) AS owner_name\n            FROM sys.databases d\n            WHERE {db_cond}\n            ORDER BY d.name"
    },
    {
        "id": 54,
        "title": "Auto Close And Auto Shrink",
        "method": "SQLServerConnector.get_auto_close_and_auto_shrink()",
        "description": "Identifies databases configured with AUTO_CLOSE or AUTO_SHRINK.",
        "headers": [
            "Database Name",
            "Auto Close",
            "Auto Shrink"
        ],
        "category": "Overview",
        "query": "SELECT\n                name AS database_name,\n                is_auto_close_on,\n                is_auto_shrink_on\n            FROM sys.databases\n            WHERE {db_cond}\n            ORDER BY name"
    },
    {
        "id": 55,
        "title": "Statistics Inventory",
        "method": "SQLServerConnector.get_statistics_inventory()",
        "description": "Inventories table statistics and their creation/recompute properties.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Statistics Name",
            "Auto Created",
            "User Created",
            "No Recompute"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                st.name AS statistics_name,\n                st.auto_created,\n                st.user_created,\n                st.no_recompute\n            FROM sys.stats st\n            JOIN sys.tables t ON t.object_id = st.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            ORDER BY s.name, t.name, st.name;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 56,
        "title": "Stale Statistics Candidates",
        "method": "SQLServerConnector.get_stale_statistics_candidates()",
        "description": "Identifies statistics with a high modification counter relative to their recorded row count.",
        "headers": [
            "Database Name",
            "Schema",
            "Table Name",
            "Statistics Name",
            "Rows",
            "Modification Counter"
        ],
        "category": "Overview",
        "query": "DECLARE @sql nvarchar(max) = N'';\n            SELECT @sql = @sql + N'\n            USE ' + QUOTENAME(name) + N';\n            SELECT TOP (100)\n                DB_NAME() AS database_name,\n                s.name AS schema_name,\n                t.name AS table_name,\n                st.name AS statistics_name,\n                sp.rows,\n                sp.modification_counter\n            FROM sys.stats st\n            JOIN sys.tables t ON t.object_id = st.object_id\n            JOIN sys.schemas s ON s.schema_id = t.schema_id\n            CROSS APPLY sys.dm_db_stats_properties(st.object_id, st.stats_id) sp\n            WHERE sp.modification_counter > 0\n            ORDER BY sp.rows DESC;\n            '\n            FROM sys.databases\n            WHERE state_desc = 'ONLINE'\n              AND {db_cond};\n            EXEC sys.sp_executesql @sql;"
    },
    {
        "id": 57,
        "title": "Deadlock Extended Events Sessions",
        "method": "SQLServerConnector.get_deadlock_xevent_sessions()",
        "description": "Checks Extended Events sessions for deadlock monitoring configuration.",
        "headers": [
            "Session Name",
            "Startup State",
            "State"
        ],
        "category": "I/O",
        "query": "SELECT\n                name AS session_name,\n                CASE WHEN startup_state = 1 THEN 'STARTUP_ENABLED' ELSE 'STARTUP_DISABLED' END AS startup_state,\n                CASE WHEN CAST(CASE WHEN EXISTS (\n                    SELECT 1\n                    FROM sys.dm_xe_sessions xs\n                    WHERE xs.name = s.name\n                ) THEN 1 ELSE 0 END AS bit) = 1 THEN 'RUNNING' ELSE 'STOPPED' END AS state_desc\n            FROM sys.server_event_sessions s\n            WHERE name LIKE '%deadlock%'\n            ORDER BY name"
    },
    {
        "id": 58,
        "title": "Server Configuration",
        "method": "SQLServerConnector.get_server_configuration()",
        "description": "Reviews top 10 key instance-level configuration options and their active values.",
        "headers": [
            "Configuration Name",
            "Value In Use",
            "Minimum",
            "Maximum",
            "Description"
        ],
        "category": "I/O",
        "query": "SELECT TOP (10)\n                name AS configuration_name,\n                CAST(value_in_use AS BIGINT) AS value_in_use,\n                CAST(minimum AS BIGINT) AS minimum,\n                CAST(maximum AS BIGINT) AS maximum,\n                CAST(description AS NVARCHAR(500)) AS description\n            FROM sys.configurations\n            WHERE LOWER(name) IN (\n                'max server memory (mb)',\n                'min server memory (mb)',\n                'max degree of parallelism',\n                'cost threshold for parallelism',\n                'optimize for ad hoc workloads',\n                'fill factor (%)',\n                'backup compression default',\n                'remote admin connections',\n                'clr enabled',\n                'contained database authentication'\n            )\n            ORDER BY configuration_name"
    },
    {
        "id": 59,
        "title": "CPU Schedulers",
        "method": "SQLServerConnector.get_cpu_schedulers()",
        "description": "Shows SQL Server scheduler state and runnable workload indicators.",
        "headers": [
            "Scheduler ID",
            "Status",
            "CPU ID",
            "Is Online",
            "Is Idle",
            "Current Tasks Count",
            "Runnable Tasks Count"
        ],
        "category": "Query Performance",
        "query": "SELECT\n                scheduler_id,\n                status,\n                cpu_id,\n                is_online,\n                is_idle,\n                current_tasks_count,\n                runnable_tasks_count\n            FROM sys.dm_os_schedulers\n            WHERE status = 'VISIBLE ONLINE'\n            ORDER BY runnable_tasks_count DESC"
    },
    {
        "id": 60,
        "title": "Database Health Summary",
        "method": "SQLServerConnector.get_database_health_summary()",
        "description": "Provides a compact operational health summary for user databases.",
        "headers": [
            "Database Name",
            "State",
            "Recovery Model",
            "Compat Level",
            "User Access",
            "Is Read Only",
            "Auto Close",
            "Auto Shrink",
            "Log Reuse Wait Reason"
        ],
        "category": "Overview",
        "query": "SELECT\n                name AS database_name,\n                state_desc,\n                recovery_model_desc,\n                compatibility_level,\n                user_access_desc,\n                is_read_only,\n                is_auto_close_on,\n                is_auto_shrink_on,\n                log_reuse_wait_desc\n            FROM sys.databases\n            WHERE {db_cond}\n            ORDER BY name"
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


_SQLSERVER_ALIASES = {
    "check table fragmentation": "20",
    "fragmented indexes": "20",
    "table fragmentation": "20",
    "fragmentation": "20",
    "database sizes": "2",
    "database inventory": "2",
    "top 100 largest tables": "4",
    "top 100 tables": "4",
    "table row counts": "5",
}
for alias, id_val in _SQLSERVER_ALIASES.items():
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
        
    # 2. Match exact ID or leading ID number e.g. '20' or '20. Fragmented Indexes'
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
    """Return all insight definitions for SQLServer."""
    return INSIGHTS
