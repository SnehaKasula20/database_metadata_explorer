"""
Oracle Database Insights & Dynamic SQL Queries
Auto-documented query methods and metadata reference for Oracle.
"""

import re
from typing import Any, Dict, List, Optional

INSIGHTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Oracle version and environment",
        "method": "OracleConnector.get_environment_info()",
        "description": "Oracle server, instance, and database configuration details.",
        "headers": [
            "Banner",
            "Instance",
            "Host",
            "Version",
            "Status",
            "DB Status",
            "DB Name",
            "Open Mode",
            "Role"
        ],
        "category": "I/O",
        "query": "SELECT\n                (SELECT banner FROM v$version WHERE ROWNUM = 1) AS banner,\n                (SELECT instance_name FROM v$instance WHERE ROWNUM = 1) AS instance_name,\n                (SELECT host_name FROM v$instance WHERE ROWNUM = 1) AS host_name,\n                (SELECT version FROM v$instance WHERE ROWNUM = 1) AS version,\n                (SELECT status FROM v$instance WHERE ROWNUM = 1) AS status,\n                (SELECT database_status FROM v$instance WHERE ROWNUM = 1) AS database_status,\n                (SELECT name FROM v$database WHERE ROWNUM = 1) AS db_name,\n                (SELECT open_mode FROM v$database WHERE ROWNUM = 1) AS open_mode,\n                (SELECT database_role FROM v$database WHERE ROWNUM = 1) AS database_role\n            FROM DUAL"
    },
    {
        "id": 2,
        "title": "Schema inventory",
        "method": "OracleConnector.get_schema_inventory()",
        "description": "Database user schemas inventory with actual allocated size.",
        "headers": [
            "Schema Name",
            "Actual Size (MB)"
        ],
        "category": "Overview",
        "query": "```python\ndef get_schema_inventory(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT u.username AS schema_name,\n                   ROUND(NVL(SUM(s.bytes)/1024/1024, 0), 2) AS actual_size_mb\n            FROM dba_users u\n            LEFT JOIN dba_segments s\n                ON s.owner = u.username\n            WHERE {self._system_schema_filter('u.username')}\n            GROUP BY u.username\n            ORDER BY actual_size_mb DESC, u.username\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT u.username AS schema_name,\n                       ROUND(NVL(SUM(s.bytes)/1024/1024, 0), 2) AS actual_size_mb\n                FROM all_users u\n                LEFT JOIN all_segments s\n                    ON s.owner = u.username\n                WHERE {self._system_schema_filter('u.username')}\n                GROUP BY u.username\n                ORDER BY actual_size_mb DESC, u.username\n            \"\"\"\n            rows = self._execute_query(query_all)\n        if rows:\n            total_mb = sum(float(r.get(\"actual_size_mb\") or 0) for r in rows)\n            rows.append({\"schema_name\": \"TOTAL\", \"actual_size_mb\": round(total_mb, 2)})\n        return rows\n```"
    },
    {
        "id": 3,
        "title": "Schema/table storage analysis",
        "method": "OracleConnector.get_schema_table_storage_analysis()",
        "description": "Database-wide table segment sizes in MB and GB.",
        "headers": [
            "Schema",
            "Table Name",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Storage",
        "query": "```python\ndef get_schema_table_storage_analysis(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT owner AS schema_name,\n                   segment_name AS table_name,\n                   ROUND(SUM(bytes)/POWER(1024,2),2) AS size_mb,\n                   ROUND(SUM(bytes)/POWER(1024,3),2) AS size_gb\n            FROM dba_segments\n            WHERE segment_type LIKE 'TABLE%' AND {self._system_schema_filter('owner')}\n            GROUP BY owner, segment_name\n            ORDER BY SUM(bytes) DESC\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT owner AS schema_name,\n                       segment_name AS table_name,\n                       ROUND(SUM(bytes)/POWER(1024,2),2) AS size_mb,\n                       ROUND(SUM(bytes)/POWER(1024,3),2) AS size_gb\n                FROM all_segments\n                WHERE segment_type LIKE 'TABLE%' AND {self._system_schema_filter('owner')}\n                GROUP BY owner, segment_name\n                ORDER BY SUM(bytes) DESC\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 4,
        "title": "Total data vs index storage",
        "method": "OracleConnector.get_total_data_vs_index_storage()",
        "description": "Total database table vs index storage footprint in GB.",
        "headers": [
            "Table Storage (GB)",
            "Index Storage (GB)",
            "Total Storage (GB)"
        ],
        "category": "Storage",
        "query": "```python\ndef get_total_data_vs_index_storage(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT\n                ROUND(SUM(CASE WHEN segment_type LIKE 'TABLE%' THEN bytes ELSE 0 END)/POWER(1024,3),2) AS table_gb,\n                ROUND(SUM(CASE WHEN segment_type LIKE 'INDEX%' THEN bytes ELSE 0 END)/POWER(1024,3),2) AS index_gb,\n                ROUND(SUM(bytes)/POWER(1024,3),2) AS total_gb\n            FROM dba_segments\n            WHERE {self._system_schema_filter('owner')}\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows or rows[0].get(\"total_gb\") is None:\n            query_all = f\"\"\"\n                SELECT\n                    ROUND(SUM(CASE WHEN segment_type LIKE 'TABLE%' THEN bytes ELSE 0 END)/POWER(1024,3),2) AS table_gb,\n                    ROUND(SUM(CASE WHEN segment_type LIKE 'INDEX%' THEN bytes ELSE 0 END)/POWER(1024,3),2) AS index_gb,\n                    ROUND(SUM(bytes)/POWER(1024,3),2) AS total_gb\n                FROM all_segments\n                WHERE {self._system_schema_filter('owner')}\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 5,
        "title": "Top 100 largest segments",
        "method": "OracleConnector.get_top_100_largest_segments()",
        "description": "Top 100 largest segments in the database by total allocated size.",
        "headers": [
            "Schema",
            "Segment Name",
            "Segment Type",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Storage",
        "query": "```python\ndef get_top_100_largest_segments(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT owner AS schema_name,\n                   segment_name,\n                   segment_type,\n                   ROUND(bytes/POWER(1024,2),2) AS size_mb,\n                   ROUND(bytes/POWER(1024,3),2) AS size_gb\n            FROM (\n                SELECT owner, segment_name, segment_type, bytes\n                FROM dba_segments\n                WHERE {self._system_schema_filter('owner')}\n                ORDER BY bytes DESC\n            )\n            WHERE ROWNUM <= 100\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT owner AS schema_name,\n                       segment_name,\n                       segment_type,\n                       ROUND(bytes/POWER(1024,2),2) AS size_mb,\n                       ROUND(bytes/POWER(1024,3),2) AS size_gb\n                FROM (\n                    SELECT owner, segment_name, segment_type, bytes\n                    FROM all_segments\n                    WHERE {self._system_schema_filter('owner')}\n                    ORDER BY bytes DESC\n                )\n                WHERE ROWNUM <= 100\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 6,
        "title": "Table row counts / statistics",
        "method": "OracleConnector.get_table_row_counts_stats()",
        "description": "Table row counts based on dictionary optimizer statistics.",
        "headers": [
            "Schema",
            "Table Name",
            "Rows (Est)",
            "Last Analyzed"
        ],
        "category": "Overview",
        "query": "```python\ndef get_table_row_counts_stats(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT owner AS schema_name,\n                   table_name,\n                   num_rows,\n                   TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed\n            FROM dba_tables\n            WHERE {self._system_schema_filter('owner')}\n            ORDER BY num_rows DESC NULLS LAST\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT owner AS schema_name,\n                       table_name,\n                       num_rows,\n                       TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed\n                FROM all_tables\n                WHERE {self._system_schema_filter('owner')}\n                ORDER BY num_rows DESC NULLS LAST\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 7,
        "title": "Tablespace usage",
        "method": "OracleConnector.get_tablespace_usage()",
        "description": "Allocated size by tablespace from datafiles.",
        "headers": [
            "Tablespace Name",
            "Allocated Space (GB)"
        ],
        "category": "Storage",
        "query": "```python\ndef get_tablespace_usage(self) -> List[Dict[str, Any]]:\n        query_dba = \"\"\"\n            SELECT tablespace_name,\n                   ROUND(SUM(bytes)/POWER(1024,3),2) AS allocated_gb\n            FROM dba_data_files\n            GROUP BY tablespace_name\n            ORDER BY allocated_gb DESC\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_metrics = \"\"\"\n                SELECT tablespace_name,\n                       ROUND((tablespace_size * (SELECT TO_NUMBER(NVL((SELECT value FROM v$parameter WHERE name = 'db_block_size'), '8192')) FROM DUAL)) / POWER(1024,3), 2) AS allocated_gb\n                FROM user_tablespace_usage_metrics\n                ORDER BY allocated_gb DESC\n            \"\"\"\n            rows = self._execute_query(query_metrics)\n        return rows\n```"
    },
    {
        "id": 8,
        "title": "Tablespace free space",
        "method": "OracleConnector.get_tablespace_free_space()",
        "description": "Tablespace allocation, free space, and used space metrics.",
        "headers": [
            "Tablespace Name",
            "Allocated (GB)",
            "Free Space (GB)",
            "Used Space (GB)"
        ],
        "category": "Storage",
        "query": "```python\ndef get_tablespace_free_space(self) -> List[Dict[str, Any]]:\n        query_metrics = \"\"\"\n            SELECT\n                m.tablespace_name,\n                ROUND(m.tablespace_size * p.block_size / POWER(1024, 3), 2) AS allocated_gb,\n                ROUND(m.used_space * p.block_size / POWER(1024, 3), 2) AS used_gb,\n                ROUND((m.tablespace_size - m.used_space) * p.block_size / POWER(1024, 3), 2) AS free_gb,\n                ROUND((m.used_space / NULLIF(m.tablespace_size, 0)) * 100, 2) AS used_pct\n            FROM dba_tablespace_usage_metrics m\n            CROSS JOIN (\n                SELECT TO_NUMBER(NVL((SELECT value FROM v$parameter WHERE name = 'db_block_size'), '8192')) AS block_size\n                FROM DUAL\n            ) p\n            ORDER BY used_pct DESC\n        \"\"\"\n        rows = self._execute_query(query_metrics)\n        if not rows:\n            query_user_metrics = \"\"\"\n                SELECT\n                    m.tablespace_name,\n                    ROUND(m.tablespace_size * p.block_size / POWER(1024, 3), 2) AS allocated_gb,\n                    ROUND(m.used_space * p.block_size / POWER(1024, 3), 2) AS used_gb,\n                    ROUND((m.tablespace_size - m.used_space) * p.block_size / POWER(1024, 3), 2) AS free_gb,\n                    ROUND((m.used_space / NULLIF(m.tablespace_size, 0)) * 100, 2) AS used_pct\n                FROM user_tablespace_usage_metrics m\n                CROSS JOIN (\n                    SELECT TO_NUMBER(NVL((SELECT value FROM v$parameter WHERE name = 'db_block_size'), '8192')) AS block_size\n                    FROM DUAL\n                ) p\n                ORDER BY used_pct DESC\n            \"\"\"\n            rows = self._execute_query(query_user_metrics)\n        if not rows:\n            query_dba = \"\"\"\n                SELECT df.tablespace_name,\n                       ROUND(SUM(df.bytes)/POWER(1024,3),2) AS allocated_gb,\n                       ROUND(NVL(fs.free_bytes,0)/POWER(1024,3),2) AS free_gb,\n                       ROUND((SUM(df.bytes)-NVL(fs.free_bytes,0))/POWER(1024,3),2) AS used_gb\n                FROM dba_data_files df\n                LEFT JOIN (\n                    SELECT tablespace_name, SUM(bytes) free_bytes\n                    FROM dba_free_space\n                    GROUP BY tablespace_name\n                ) fs ON fs.tablespace_name = df.tablespace_name\n                GROUP BY df.tablespace_name, fs.free_bytes\n                ORDER BY used_gb DESC\n            \"\"\"\n            rows = self._execute_query(query_dba)\n        if not rows:\n            query_user = \"\"\"\n                SELECT tablespace_name,\n                       0 AS allocated_gb,\n                       ROUND(SUM(bytes)/POWER(1024,3),2) AS free_gb,\n                       0 AS used_gb\n                FROM user_free_space\n                GROUP BY tablespace_name\n                ORDER BY free_gb DESC\n            \"\"\"\n            rows = self._execute_query(query_user)\n        return rows\n```"
    },
    {
        "id": 9,
        "title": "Datafiles",
        "method": "OracleConnector.get_datafiles_inventory()",
        "description": "Oracle database datafiles physical layout and autoextend parameters.",
        "headers": [
            "File Path",
            "Tablespace",
            "Size (GB)",
            "Autoextensible",
            "Max Size (GB)"
        ],
        "category": "Storage",
        "query": "```python\ndef get_datafiles_inventory(self) -> List[Dict[str, Any]]:\n        query_dba = \"\"\"\n            SELECT file_name,\n                   tablespace_name,\n                   ROUND(bytes/POWER(1024,3),2) AS size_gb,\n                   autoextensible,\n                   ROUND(maxbytes/POWER(1024,3),2) AS max_size_gb\n            FROM dba_data_files\n            ORDER BY bytes DESC\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_v = \"\"\"\n                SELECT name AS file_name,\n                       '' AS tablespace_name,\n                       ROUND(bytes/POWER(1024,3),2) AS size_gb,\n                       'UNKNOWN' AS autoextensible,\n                       0 AS max_size_gb\n                FROM v$datafile\n                ORDER BY bytes DESC\n            \"\"\"\n            rows = self._execute_query(query_v)\n        return rows\n```"
    },
    {
        "id": 10,
        "title": "Master (Parent) tables",
        "method": "OracleConnector.get_master_tables()",
        "description": "Tables referenced by foreign key constraints in child tables.",
        "headers": [
            "Schema",
            "Master Table Name",
            "Child FKs In",
            "Referencing Child Tables"
        ],
        "category": "Schema",
        "query": "```python\ndef get_master_tables(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT r.r_owner AS schema_name,\n                   p.table_name AS table_name,\n                   COUNT(DISTINCT r.owner || '.' || r.table_name) AS child_fk_count,\n                   LISTAGG(DISTINCT r.owner || '.' || r.table_name, ', ')\n                       WITHIN GROUP (ORDER BY r.owner, r.table_name) AS child_tables\n            FROM dba_constraints p\n            JOIN dba_constraints r\n                ON r.r_owner = p.owner\n               AND r.r_constraint_name = p.constraint_name\n            WHERE p.constraint_type IN ('P', 'U')\n              AND r.constraint_type = 'R'\n              AND {self._system_schema_filter('p.owner')}\n            GROUP BY r.r_owner, p.table_name\n            ORDER BY child_fk_count DESC, r.r_owner, p.table_name\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT r.r_owner AS schema_name,\n                       p.table_name AS table_name,\n                       COUNT(DISTINCT r.owner || '.' || r.table_name) AS child_fk_count,\n                       LISTAGG(DISTINCT r.owner || '.' || r.table_name, ', ')\n                           WITHIN GROUP (ORDER BY r.owner, r.table_name) AS child_tables\n                FROM all_constraints p\n                JOIN all_constraints r\n                    ON r.r_owner = p.owner\n                   AND r.r_constraint_name = p.constraint_name\n                WHERE p.constraint_type IN ('P', 'U')\n                  AND r.constraint_type = 'R'\n                  AND {self._system_schema_filter('p.owner')}\n                GROUP BY r.r_owner, p.table_name\n                ORDER BY child_fk_count DESC, r.r_owner, p.table_name\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return [\n            {\n                \"schema_name\": row.get(\"schema_name\") or \"-\",\n                \"table_name\": row.get(\"table_name\") or \"-\",\n                \"child_fk_count\": int(row.get(\"child_fk_count\") or 0),\n                \"child_tables\": row.get(\"child_tables\") or \"-\",\n            }\n            for row in rows\n        ]\n```"
    },
    {
        "id": 11,
        "title": "Child tables",
        "method": "OracleConnector.get_child_tables()",
        "description": "Tables containing foreign key constraints pointing to parent tables.",
        "headers": [
            "Schema",
            "Child Table Name",
            "Parent FKs Out",
            "Referenced Parent Tables"
        ],
        "category": "Schema",
        "query": "```python\ndef get_child_tables(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT r.owner AS schema_name,\n                   r.table_name AS table_name,\n                   COUNT(DISTINCT r.r_owner || '.' || p.table_name) AS parent_fk_count,\n                   LISTAGG(DISTINCT r.r_owner || '.' || p.table_name, ', ')\n                       WITHIN GROUP (ORDER BY r.r_owner, p.table_name) AS parent_tables\n            FROM dba_constraints r\n            JOIN dba_constraints p\n                ON r.r_owner = p.owner\n               AND r.r_constraint_name = p.constraint_name\n            WHERE r.constraint_type = 'R'\n              AND {self._system_schema_filter('r.owner')}\n            GROUP BY r.owner, r.table_name\n            ORDER BY parent_fk_count DESC, r.owner, r.table_name\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT r.owner AS schema_name,\n                       r.table_name AS table_name,\n                       COUNT(DISTINCT r.r_owner || '.' || p.table_name) AS parent_fk_count,\n                       LISTAGG(DISTINCT r.r_owner || '.' || p.table_name, ', ')\n                           WITHIN GROUP (ORDER BY r.r_owner, p.table_name) AS parent_tables\n                FROM all_constraints r\n                JOIN all_constraints p\n                    ON r.r_owner = p.owner\n                   AND r.r_constraint_name = p.constraint_name\n                WHERE r.constraint_type = 'R'\n                  AND {self._system_schema_filter('r.owner')}\n                GROUP BY r.owner, r.table_name\n                ORDER BY parent_fk_count DESC, r.owner, r.table_name\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return [\n            {\n                \"schema_name\": row.get(\"schema_name\") or \"-\",\n                \"table_name\": row.get(\"table_name\") or \"-\",\n                \"parent_fk_count\": int(row.get(\"parent_fk_count\") or 0),\n                \"parent_tables\": row.get(\"parent_tables\") or \"-\",\n            }\n            for row in rows\n        ]\n```"
    },
    {
        "id": 12,
        "title": "Independent tables",
        "method": "OracleConnector.get_independent_tables()",
        "description": "Standalone tables with no foreign key relationships (neither parent nor child).",
        "headers": [
            "Schema",
            "Independent Table Name"
        ],
        "category": "Overview",
        "query": "```python\ndef get_independent_tables(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT t.owner AS schema_name,\n                   t.table_name AS table_name\n            FROM dba_tables t\n            WHERE {self._system_schema_filter('t.owner')}\n              AND NOT EXISTS (\n                  SELECT 1 FROM dba_constraints c\n                  WHERE c.owner = t.owner\n                    AND c.table_name = t.table_name\n                    AND c.constraint_type = 'R'\n              )\n              AND NOT EXISTS (\n                  SELECT 1 FROM dba_constraints r\n                  JOIN dba_constraints p\n                      ON r.r_owner = p.owner\n                     AND r.r_constraint_name = p.constraint_name\n                  WHERE p.owner = t.owner\n                    AND p.table_name = t.table_name\n                    AND r.constraint_type = 'R'\n              )\n            ORDER BY t.owner, t.table_name\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT t.owner AS schema_name,\n                       t.table_name AS table_name\n                FROM all_tables t\n                WHERE {self._system_schema_filter('t.owner')}\n                  AND NOT EXISTS (\n                      SELECT 1 FROM all_constraints c\n                      WHERE c.owner = t.owner\n                        AND c.table_name = t.table_name\n                        AND c.constraint_type = 'R'\n                  )\n                  AND NOT EXISTS (\n                      SELECT 1 FROM all_constraints r\n                      JOIN all_constraints p\n                          ON r.r_owner = p.owner\n                         AND r.r_constraint_name = p.constraint_name\n                      WHERE p.owner = t.owner\n                        AND p.table_name = t.table_name\n                        AND r.constraint_type = 'R'\n                  )\n                ORDER BY t.owner, t.table_name\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return [\n            {\"schema_name\": row.get(\"schema_name\") or \"-\", \"table_name\": row.get(\"table_name\") or \"-\"}\n            for row in rows\n        ]\n```"
    },
    {
        "id": 13,
        "title": "Large unpartitioned tables",
        "method": "OracleConnector.get_large_unpartitioned_tables()",
        "description": "Unpartitioned tables ranked by segment size.",
        "headers": [
            "Schema",
            "Table Name",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "I/O",
        "query": "```python\ndef get_large_unpartitioned_tables(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT t.owner AS schema_name,\n                   t.table_name,\n                   ROUND(s.bytes/POWER(1024,2),2) AS size_mb,\n                   ROUND(s.bytes/POWER(1024,3),2) AS size_gb\n            FROM dba_tables t\n            JOIN (\n                SELECT owner, segment_name, SUM(bytes) bytes\n                FROM dba_segments\n                WHERE segment_type LIKE 'TABLE%'\n                GROUP BY owner, segment_name\n            ) s ON s.owner=t.owner AND s.segment_name=t.table_name\n            WHERE {self._system_table_filter('t.owner')}\n              AND t.partitioned = 'NO'\n            ORDER BY s.bytes DESC\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT t.owner AS schema_name,\n                       t.table_name,\n                       ROUND(s.bytes/POWER(1024,2),2) AS size_mb,\n                       ROUND(s.bytes/POWER(1024,3),2) AS size_gb\n                FROM all_tables t\n                JOIN (\n                    SELECT owner, segment_name, SUM(bytes) bytes\n                    FROM all_segments\n                    WHERE segment_type LIKE 'TABLE%'\n                    GROUP BY owner, segment_name\n                ) s ON s.owner=t.owner AND s.segment_name=t.table_name\n                WHERE {self._system_table_filter('t.owner')}\n                  AND t.partitioned = 'NO'\n                ORDER BY s.bytes DESC\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 14,
        "title": "Partition inventory",
        "method": "OracleConnector.get_partition_inventory()",
        "description": "Partitioned tables and total partition counts.",
        "headers": [
            "Schema",
            "Table Name",
            "Partition Count"
        ],
        "category": "I/O",
        "query": "SELECT table_owner AS schema_name,\n                   table_name,\n                   COUNT(*) AS partition_count\n            FROM dba_tab_partitions\n            WHERE {self._system_schema_filter('table_owner')}\n            GROUP BY table_owner, table_name\n            ORDER BY partition_count DESC"
    },
    {
        "id": 15,
        "title": "Detailed partition information",
        "method": "OracleConnector.get_detailed_partition_info()",
        "description": "Partition definitions, positions, and optimizer statistics.",
        "headers": [
            "Schema",
            "Table Name",
            "Partition Name",
            "Position",
            "Rows (Est)",
            "Last Analyzed"
        ],
        "category": "I/O",
        "query": "SELECT table_owner AS schema_name,\n                   table_name,\n                   partition_name,\n                   partition_position,\n                   num_rows,\n                   TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed\n            FROM dba_tab_partitions\n            WHERE {self._system_schema_filter('table_owner')}\n            ORDER BY table_owner, table_name, partition_position"
    },
    {
        "id": 16,
        "title": "Large object columns",
        "method": "OracleConnector.get_large_object_columns()",
        "description": "Tables containing BLOB, CLOB, NCLOB, or LONG columns.",
        "headers": [
            "Schema",
            "Table Name",
            "Column Name",
            "LOB Type"
        ],
        "category": "Structure",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   column_name,\n                   data_type\n            FROM dba_tab_columns\n            WHERE {self._system_schema_filter('owner')}\n              AND data_type IN ('BLOB','CLOB','NCLOB','LONG','LONG RAW')\n            ORDER BY owner, table_name, column_name"
    },
    {
        "id": 17,
        "title": "JSON-related columns",
        "method": "OracleConnector.get_json_columns()",
        "description": "Columns storing JSON documents or JSON data types.",
        "headers": [
            "Schema",
            "Table Name",
            "Column Name",
            "Data Type"
        ],
        "category": "Structure",
        "query": "```python\ndef get_json_columns(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT DISTINCT\n                c.owner AS schema_name,\n                c.table_name,\n                c.column_name,\n                c.data_type\n            FROM dba_tab_columns c\n            LEFT JOIN dba_constraints con\n                ON con.owner = c.owner\n               AND con.table_name = c.table_name\n            LEFT JOIN dba_cons_columns cc\n                ON cc.owner = con.owner\n               AND cc.constraint_name = con.constraint_name\n               AND cc.table_name = con.table_name\n               AND cc.column_name = c.column_name\n            WHERE c.data_type IN ('CLOB', 'BLOB', 'VARCHAR2', 'NVARCHAR2', 'JSON')\n              AND (\n                    c.data_type = 'JSON' \n                    OR c.data_type LIKE '%JSON%'\n                    OR (con.search_condition_vc LIKE '%IS JSON%' AND UPPER(con.search_condition_vc) LIKE '%' || UPPER(c.column_name) || '%')\n                  )\n              AND {self._system_schema_filter('c.owner')}\n            ORDER BY c.owner, c.table_name, c.column_name\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT DISTINCT\n                    c.owner AS schema_name,\n                    c.table_name,\n                    c.column_name,\n                    c.data_type\n                FROM all_tab_columns c\n                LEFT JOIN all_constraints con\n                    ON con.owner = c.owner\n                   AND con.table_name = c.table_name\n                LEFT JOIN all_cons_columns cc\n                    ON cc.owner = con.owner\n                   AND cc.constraint_name = con.constraint_name\n                   AND cc.table_name = con.table_name\n                   AND cc.column_name = c.column_name\n                WHERE c.data_type IN ('CLOB', 'BLOB', 'VARCHAR2', 'NVARCHAR2', 'JSON')\n                  AND (\n                        c.data_type = 'JSON' \n                        OR c.data_type LIKE '%JSON%'\n                        OR (con.search_condition_vc LIKE '%IS JSON%' AND UPPER(con.search_condition_vc) LIKE '%' || UPPER(c.column_name) || '%')\n                      )\n                  AND {self._system_schema_filter('c.owner')}\n                ORDER BY c.owner, c.table_name, c.column_name\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 18,
        "title": "Primary keys",
        "method": "OracleConnector.get_primary_keys()",
        "description": "Primary key constraints inventory.",
        "headers": [
            "Schema",
            "Table Name",
            "Constraint Name",
            "Status"
        ],
        "category": "Indexes",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   constraint_name,\n                   status\n            FROM dba_constraints\n            WHERE {self._system_schema_filter('owner')}\n              AND constraint_type = 'P'\n            ORDER BY owner, table_name"
    },
    {
        "id": 19,
        "title": "Tables without primary keys",
        "method": "OracleConnector.get_tables_without_primary_keys()",
        "description": "Tables defined without an explicit Primary Key.",
        "headers": [
            "Schema",
            "Table Name"
        ],
        "category": "Indexes",
        "query": "SELECT t.owner AS schema_name,\n                   t.table_name\n            FROM dba_tables t\n            LEFT JOIN dba_constraints c\n              ON c.owner = t.owner\n             AND c.table_name = t.table_name\n             AND c.constraint_type = 'P'\n            WHERE {self._system_table_filter('t.owner')}\n              AND c.constraint_name IS NULL\n            ORDER BY t.owner, t.table_name"
    },
    {
        "id": 20,
        "title": "All indexes",
        "method": "OracleConnector.get_all_indexes()",
        "description": "Database indexes inventory.",
        "headers": [
            "Schema",
            "Table Name",
            "Index Name",
            "Index Type",
            "Uniqueness",
            "Status"
        ],
        "category": "Indexes",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   index_name,\n                   index_type,\n                   uniqueness,\n                   status\n            FROM dba_indexes\n            WHERE {self._system_schema_filter('owner')}\n            ORDER BY owner, table_name, index_name"
    },
    {
        "id": 21,
        "title": "Index columns",
        "method": "OracleConnector.get_index_columns()",
        "description": "Index column mapping positions.",
        "headers": [
            "Schema",
            "Table Name",
            "Index Name",
            "Position",
            "Column Name"
        ],
        "category": "Indexes",
        "query": "SELECT index_owner AS schema_name,\n                   table_name,\n                   index_name,\n                   column_position,\n                   column_name\n            FROM dba_ind_columns\n            WHERE {self._system_schema_filter('index_owner')}\n            ORDER BY index_owner, table_name, index_name, column_position"
    },
    {
        "id": 22,
        "title": "Index count by table",
        "method": "OracleConnector.get_index_count_by_table()",
        "description": "Total indexes per table ranked by count.",
        "headers": [
            "Schema",
            "Table Name",
            "Index Count"
        ],
        "category": "Indexes",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   COUNT(*) AS index_count\n            FROM dba_indexes\n            WHERE {self._system_schema_filter('owner')}\n            GROUP BY owner, table_name\n            ORDER BY index_count DESC"
    },
    {
        "id": 23,
        "title": "Largest indexes",
        "method": "OracleConnector.get_largest_indexes()",
        "description": "Top 100 largest indexes by total segment size.",
        "headers": [
            "Schema",
            "Index Name",
            "Index Size (MB)",
            "Index Size (GB)"
        ],
        "category": "Indexes",
        "query": "SELECT owner AS schema_name,\n                   segment_name AS index_name,\n                   ROUND(bytes/POWER(1024,2),2) AS index_mb,\n                   ROUND(bytes/POWER(1024,3),2) AS index_gb\n            FROM dba_segments\n            WHERE {self._system_schema_filter('owner')}\n              AND segment_type LIKE 'INDEX%'\n            ORDER BY bytes DESC\n            FETCH FIRST 100 ROWS ONLY"
    },
    {
        "id": 24,
        "title": "Foreign keys / relationships",
        "method": "OracleConnector.get_foreign_keys()",
        "description": "Foreign key referential constraints.",
        "headers": [
            "Schema",
            "Table Name",
            "Constraint Name",
            "Ref Schema",
            "Ref Constraint"
        ],
        "category": "I/O",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   constraint_name,\n                   r_owner AS referenced_schema,\n                   r_constraint_name AS referenced_constraint\n            FROM dba_constraints\n            WHERE {self._system_schema_filter('owner')}\n              AND constraint_type = 'R'\n            ORDER BY owner, table_name, constraint_name"
    },
    {
        "id": 25,
        "title": "Detailed foreign-key columns",
        "method": "OracleConnector.get_detailed_foreign_key_columns()",
        "description": "Detailed column-to-column referential constraint mapping.",
        "headers": [
            "Child Schema",
            "Child Table",
            "Constraint",
            "Child Column",
            "Ref Schema",
            "Ref Table",
            "Ref Column",
            "Position"
        ],
        "category": "Structure",
        "query": "SELECT a.owner AS schema_name,\n                   a.table_name,\n                   a.constraint_name,\n                   a.column_name,\n                   c.r_owner AS referenced_schema,\n                   c_pk.table_name AS referenced_table,\n                   b.column_name AS referenced_column,\n                   a.position\n            FROM dba_cons_columns a\n            JOIN dba_constraints c\n              ON c.owner = a.owner\n             AND c.constraint_name = a.constraint_name\n            JOIN dba_constraints c_pk\n              ON c_pk.owner = c.r_owner\n             AND c_pk.constraint_name = c.r_constraint_name\n            JOIN dba_cons_columns b\n              ON b.owner = c_pk.owner\n             AND b.constraint_name = c_pk.constraint_name\n             AND b.position = a.position\n            WHERE {self._system_schema_filter('a.owner')}\n              AND c.constraint_type = 'R'\n            ORDER BY a.owner, a.table_name, a.constraint_name, a.position"
    },
    {
        "id": 26,
        "title": "Tables with many foreign-key relationships",
        "method": "OracleConnector.get_tables_many_foreign_keys()",
        "description": "Tables ranked by number of outgoing foreign key constraints.",
        "headers": [
            "Schema",
            "Table Name",
            "Foreign Key Count"
        ],
        "category": "I/O",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   COUNT(*) AS foreign_key_count\n            FROM dba_constraints\n            WHERE {self._system_schema_filter('owner')}\n              AND constraint_type = 'R'\n            GROUP BY owner, table_name\n            ORDER BY foreign_key_count DESC"
    },
    {
        "id": 27,
        "title": "Unique constraints",
        "method": "OracleConnector.get_unique_constraints()",
        "description": "Unique constraints inventory.",
        "headers": [
            "Schema",
            "Table Name",
            "Constraint Name",
            "Status"
        ],
        "category": "Overview",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   constraint_name,\n                   status\n            FROM dba_constraints\n            WHERE {self._system_schema_filter('owner')}\n              AND constraint_type = 'U'\n            ORDER BY owner, table_name, constraint_name"
    },
    {
        "id": 28,
        "title": "Duplicate/redundant index candidates",
        "method": "OracleConnector.get_duplicate_index_candidates()",
        "description": "Candidate redundant indexes sharing the exact same first column.",
        "headers": [
            "Schema",
            "Table Name",
            "Index A",
            "Index B",
            "Leading Column"
        ],
        "category": "Indexes",
        "query": "SELECT a.index_owner AS schema_name,\n                   a.table_name,\n                   a.index_name AS index_a,\n                   b.index_name AS index_b,\n                   a.column_name AS first_column\n            FROM dba_ind_columns a\n            JOIN dba_ind_columns b\n              ON b.index_owner = a.index_owner\n             AND b.table_name = a.table_name\n             AND b.column_position = 1\n             AND b.column_name = a.column_name\n             AND b.index_name <> a.index_name\n            WHERE {self._system_schema_filter('a.index_owner')}\n              AND a.column_position = 1\n            ORDER BY a.index_owner, a.table_name, a.index_name, b.index_name"
    },
    {
        "id": 29,
        "title": "Character sets and collations",
        "method": "OracleConnector.get_charsets_and_collations()",
        "description": "NLS database character set configuration.",
        "headers": [
            "NLS Parameter",
            "Value"
        ],
        "category": "I/O",
        "query": "SELECT parameter, value\n            FROM nls_database_parameters\n            WHERE parameter IN ('NLS_CHARACTERSET','NLS_NCHAR_CHARACTERSET')"
    },
    {
        "id": 30,
        "title": "Tables with comments / documentation",
        "method": "OracleConnector.get_table_comments()",
        "description": "Table documentation comments from dictionary.",
        "headers": [
            "Schema",
            "Table Name",
            "Comments"
        ],
        "category": "I/O",
        "query": "SELECT owner AS schema_name,\n                   table_name,\n                   comments\n            FROM dba_tab_comments\n            WHERE {self._system_schema_filter('owner')}\n              AND comments IS NOT NULL\n            ORDER BY owner, table_name"
    },
    {
        "id": 31,
        "title": "Stored procedures",
        "method": "OracleConnector.get_stored_procedures()",
        "description": "Stored procedures inventory.",
        "headers": [
            "Schema",
            "Procedure Name",
            "Status",
            "Created",
            "Last DDL Time"
        ],
        "category": "Objects",
        "query": "SELECT owner AS schema_name,\n                   object_name,\n                   status,\n                   TO_CHAR(created, 'YYYY-MM-DD HH24:MI:SS') AS created,\n                   TO_CHAR(last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') AS last_ddl_time\n            FROM dba_objects\n            WHERE {self._system_schema_filter('owner')}\n              AND object_type = 'PROCEDURE'\n            ORDER BY owner, object_name"
    },
    {
        "id": 32,
        "title": "Functions",
        "method": "OracleConnector.get_functions()",
        "description": "Database functions inventory.",
        "headers": [
            "Schema",
            "Function Name",
            "Status",
            "Created",
            "Last DDL Time"
        ],
        "category": "I/O",
        "query": "SELECT owner AS schema_name,\n                   object_name,\n                   status,\n                   TO_CHAR(created, 'YYYY-MM-DD HH24:MI:SS') AS created,\n                   TO_CHAR(last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') AS last_ddl_time\n            FROM dba_objects\n            WHERE {self._system_schema_filter('owner')}\n              AND object_type = 'FUNCTION'\n            ORDER BY owner, object_name"
    },
    {
        "id": 33,
        "title": "Packages",
        "method": "OracleConnector.get_packages()",
        "description": "Packages and package bodies inventory.",
        "headers": [
            "Schema",
            "Object Type",
            "Package Name",
            "Status",
            "Created",
            "Last DDL Time"
        ],
        "category": "Objects",
        "query": "SELECT owner AS schema_name,\n                   object_type,\n                   object_name,\n                   status,\n                   TO_CHAR(created, 'YYYY-MM-DD HH24:MI:SS') AS created,\n                   TO_CHAR(last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') AS last_ddl_time\n            FROM dba_objects\n            WHERE {self._system_schema_filter('owner')}\n              AND object_type IN ('PACKAGE', 'PACKAGE BODY')\n            ORDER BY owner, object_type, object_name"
    },
    {
        "id": 34,
        "title": "Views",
        "method": "OracleConnector.get_views()",
        "description": "Database views inventory.",
        "headers": [
            "Schema",
            "View Name"
        ],
        "category": "Objects",
        "query": "SELECT owner AS schema_name,\n                   view_name\n            FROM dba_views\n            WHERE {self._system_schema_filter('owner')}\n            ORDER BY owner, view_name"
    },
    {
        "id": 35,
        "title": "Triggers",
        "method": "OracleConnector.get_triggers()",
        "description": "Database triggers inventory.",
        "headers": [
            "Schema",
            "Trigger Name",
            "Table Name",
            "Event",
            "Type",
            "Status"
        ],
        "category": "Objects",
        "query": "SELECT owner AS schema_name,\n                   trigger_name,\n                   table_name,\n                   triggering_event,\n                   trigger_type,\n                   status\n            FROM dba_triggers\n            WHERE {self._system_schema_filter('owner')}\n            ORDER BY owner, table_name, trigger_name"
    },
    {
        "id": 36,
        "title": "Scheduled jobs",
        "method": "OracleConnector.get_scheduled_jobs()",
        "description": "Oracle Scheduler jobs inventory.",
        "headers": [
            "Schema",
            "Job Name",
            "Enabled",
            "State",
            "Job Type",
            "Last Start",
            "Next Run"
        ],
        "category": "Objects",
        "query": "SELECT owner AS schema_name,\n                   job_name,\n                   enabled,\n                   state,\n                   job_type,\n                   TO_CHAR(last_start_date, 'YYYY-MM-DD HH24:MI:SS') AS last_start_date,\n                   TO_CHAR(next_run_date, 'YYYY-MM-DD HH24:MI:SS') AS next_run_date\n            FROM dba_scheduler_jobs\n            WHERE {self._system_schema_filter('owner')}\n            ORDER BY next_run_date"
    },
    {
        "id": 37,
        "title": "Users and privileges",
        "method": "OracleConnector.get_users_and_privileges()",
        "description": "Database user accounts and account status.",
        "headers": [
            "Username",
            "Account Status",
            "Created Date",
            "Profile"
        ],
        "category": "Security",
        "query": "SELECT username,\n                   account_status,\n                   TO_CHAR(created, 'YYYY-MM-DD') AS created,\n                   profile\n            FROM dba_users\n            WHERE {self._system_schema_filter('username')}\n            ORDER BY username"
    },
    {
        "id": 38,
        "title": "Tablespace and segment status",
        "method": "OracleConnector.get_tablespace_and_segment_status()",
        "description": "Tablespace definitions and segment management parameters.",
        "headers": [
            "Tablespace Name",
            "Status",
            "Contents",
            "Extent Management",
            "Segment Management"
        ],
        "category": "Storage",
        "query": "SELECT tablespace_name,\n                   status,\n                   contents,\n                   extent_management,\n                   segment_space_management\n            FROM dba_tablespaces\n            ORDER BY tablespace_name"
    },
    {
        "id": 39,
        "title": "SGA / memory configuration",
        "method": "OracleConnector.get_sga_memory_config()",
        "description": "System Global Area (SGA) memory components.",
        "headers": [
            "Memory Component",
            "Allocated Value (Bytes)"
        ],
        "category": "I/O",
        "query": "SELECT name, TO_CHAR(value) AS value\n            FROM v$sga\n            ORDER BY name"
    },
    {
        "id": 40,
        "title": "PGA configuration and usage",
        "method": "OracleConnector.get_pga_config_usage()",
        "description": "Program Global Area (PGA) metrics and limits.",
        "headers": [
            "PGA Metric Name",
            "Value"
        ],
        "category": "I/O",
        "query": "SELECT name, TO_CHAR(value) AS value\n            FROM v$pgastat\n            ORDER BY name"
    },
    {
        "id": 41,
        "title": "Temporary tablespace usage",
        "method": "OracleConnector.get_temp_tablespace_usage()",
        "description": "Temporary tablespaces usage and allocation.",
        "headers": [
            "Tablespace Name",
            "Total Size",
            "Allocated Space",
            "Free Space"
        ],
        "category": "Storage",
        "query": "SELECT tablespace_name,\n                   tablespace_size,\n                   allocated_space,\n                   free_space\n            FROM dba_temp_free_space\n            ORDER BY tablespace_name"
    },
    {
        "id": 42,
        "title": "Sessions and connections",
        "method": "OracleConnector.get_sessions_and_connections()",
        "description": "Active session connections count grouped by status.",
        "headers": [
            "Session Status",
            "Active Session Count"
        ],
        "category": "I/O",
        "query": "SELECT status,\n                   COUNT(*) AS session_count\n            FROM v$session\n            GROUP BY status\n            ORDER BY status"
    },
    {
        "id": 43,
        "title": "Long-running sessions",
        "method": "OracleConnector.get_long_running_sessions()",
        "description": "Active user sessions ranked by elapsed time.",
        "headers": [
            "SID",
            "Serial#",
            "Username",
            "Status",
            "Wait Event",
            "SQL ID",
            "Elapsed (s)"
        ],
        "category": "I/O",
        "query": "SELECT sid,\n                   serial#,\n                   username,\n                   status,\n                   event,\n                   sql_id,\n                   last_call_et AS elapsed_seconds\n            FROM v$session\n            WHERE username IS NOT NULL\n            ORDER BY last_call_et DESC"
    },
    {
        "id": 44,
        "title": "Locks",
        "method": "OracleConnector.get_locks()",
        "description": "Active database locks blocking session execution.",
        "headers": [
            "Blocking SID",
            "Waiting SID",
            "Lock Type",
            "ID1",
            "ID2",
            "Blocking Mode",
            "Waiting Request"
        ],
        "category": "Locks",
        "query": "SELECT\n                l1.sid AS blocking_sid,\n                l2.sid AS waiting_sid,\n                l1.type,\n                l1.id1,\n                l1.id2,\n                l1.lmode AS blocking_mode,\n                l2.request AS waiting_request\n            FROM v$lock l1\n            JOIN v$lock l2\n              ON l1.id1 = l2.id1\n             AND l1.id2 = l2.id2\n            WHERE l1.block = 1\n              AND l2.request > 0"
    },
    {
        "id": 45,
        "title": "Blocking sessions",
        "method": "OracleConnector.get_blocking_sessions()",
        "description": "Sessions currently waiting on blocking sessions.",
        "headers": [
            "SID",
            "Serial#",
            "Username",
            "Blocking SID",
            "Wait Event",
            "Seconds in Wait"
        ],
        "category": "I/O",
        "query": "SELECT sid,\n                   serial#,\n                   username,\n                   blocking_session,\n                   event,\n                   seconds_in_wait\n            FROM v$session\n            WHERE blocking_session IS NOT NULL\n            ORDER BY seconds_in_wait DESC"
    },
    {
        "id": 46,
        "title": "Slow / resource-intensive SQL",
        "method": "OracleConnector.get_slow_sql()",
        "description": "Top SQL queries ranked by cumulative elapsed time from V$SQL.",
        "headers": [
            "SQL ID",
            "Executions",
            "Elapsed (s)",
            "CPU (s)",
            "Buffer Gets",
            "Disk Reads",
            "Rows Processed",
            "SQL Text Sample"
        ],
        "category": "Query Performance",
        "query": "SELECT *\n            FROM (\n                SELECT sql_id,\n                       executions,\n                       ROUND(elapsed_time/1000000, 2) AS elapsed_seconds,\n                       ROUND(cpu_time/1000000, 2) AS cpu_seconds,\n                       buffer_gets,\n                       disk_reads,\n                       rows_processed,\n                       SUBSTR(sql_text, 1, 100) AS sql_text_sample\n                FROM v$sql\n                ORDER BY elapsed_time DESC\n            )\n            WHERE ROWNUM <= 50"
    },
    {
        "id": 47,
        "title": "SQL examining large amounts of data",
        "method": "OracleConnector.get_large_data_examination_sql()",
        "description": "Top SQL queries ranked by buffer gets (data examination).",
        "headers": [
            "SQL ID",
            "Executions",
            "Buffer Gets",
            "Disk Reads",
            "Rows Processed",
            "SQL Text Sample"
        ],
        "category": "Overview",
        "query": "SELECT *\n            FROM (\n                SELECT sql_id,\n                       executions,\n                       buffer_gets,\n                       disk_reads,\n                       rows_processed,\n                       SUBSTR(sql_text, 1, 100) AS sql_text_sample\n                FROM v$sql\n                ORDER BY buffer_gets DESC\n            )\n            WHERE ROWNUM <= 50"
    },
    {
        "id": 48,
        "title": "Most frequently executed SQL",
        "method": "OracleConnector.get_frequently_executed_sql()",
        "description": "Top SQL queries ranked by cumulative execution count.",
        "headers": [
            "SQL ID",
            "Executions",
            "Elapsed Seconds",
            "SQL Text Sample"
        ],
        "category": "Query Performance",
        "query": "SELECT *\n            FROM (\n                SELECT sql_id,\n                       executions,\n                       ROUND(elapsed_time/1000000, 2) AS elapsed_seconds,\n                       SUBSTR(sql_text, 1, 100) AS sql_text_sample\n                FROM v$sql\n                ORDER BY executions DESC\n            )\n            WHERE ROWNUM <= 50"
    },
    {
        "id": 49,
        "title": "Top wait events",
        "method": "OracleConnector.get_top_wait_events()",
        "description": "System wait events ranked by total time waited.",
        "headers": [
            "Event Name",
            "Total Waits",
            "Time Waited",
            "Wait Seconds"
        ],
        "category": "I/O",
        "query": "SELECT event,\n                   total_waits,\n                   time_waited,\n                   ROUND(time_waited/100,2) AS wait_seconds\n            FROM v$system_event\n            ORDER BY time_waited DESC\n            FETCH FIRST 50 ROWS ONLY"
    },
    {
        "id": 50,
        "title": "Database time / load profile",
        "method": "OracleConnector.get_database_time_load_profile()",
        "description": "Database CPU, DB time, commits, and rollbacks metrics.",
        "headers": [
            "Sysstat Metric Name",
            "Value"
        ],
        "category": "Overview",
        "query": "SELECT name,\n                   value\n            FROM v$sysstat\n            WHERE name IN (\n                'DB time',\n                'DB CPU',\n                'user commits',\n                'user rollbacks',\n                'execute count'\n            )\n            ORDER BY name"
    },
    {
        "id": 51,
        "title": "Data Guard / database role",
        "method": "OracleConnector.get_dataguard_db_role()",
        "description": "Oracle Data Guard role and open status.",
        "headers": [
            "DB Name",
            "DB Unique Name",
            "Open Mode",
            "DB Role",
            "Protection Mode",
            "Protection Level",
            "Switchover Status"
        ],
        "category": "Replication",
        "query": "SELECT name,\n                   db_unique_name,\n                   open_mode,\n                   database_role,\n                   protection_mode,\n                   protection_level,\n                   switchover_status\n            FROM v$database"
    },
    {
        "id": 52,
        "title": "Archive log configuration",
        "method": "OracleConnector.get_archive_log_config()",
        "description": "Archive log destination and format parameters.",
        "headers": [
            "Parameter Name",
            "Setting Value"
        ],
        "category": "I/O",
        "query": "SELECT name,\n                   value\n            FROM v$parameter\n            WHERE name IN ('log_archive_dest_1','log_archive_dest_2','log_archive_format')\n            ORDER BY name"
    },
    {
        "id": 53,
        "title": "Archive log generation",
        "method": "OracleConnector.get_archive_log_generation()",
        "description": "Recent archive log generation history.",
        "headers": [
            "Thread#",
            "Sequence#",
            "First Time",
            "Next Time",
            "Blocks",
            "Block Size"
        ],
        "category": "I/O",
        "query": "SELECT thread#,\n                   sequence#,\n                   TO_CHAR(first_time, 'YYYY-MM-DD HH24:MI:SS') AS first_time,\n                   TO_CHAR(next_time, 'YYYY-MM-DD HH24:MI:SS') AS next_time,\n                   blocks,\n                   block_size\n            FROM v$archived_log\n            WHERE first_time IS NOT NULL\n            ORDER BY first_time DESC\n            FETCH FIRST 100 ROWS ONLY"
    },
    {
        "id": 54,
        "title": "Redo generation",
        "method": "OracleConnector.get_redo_generation()",
        "description": "Redo size, writes, and entries statistics.",
        "headers": [
            "Metric Name",
            "Value"
        ],
        "category": "I/O",
        "query": "SELECT name,\n                   value\n            FROM v$sysstat\n            WHERE name IN ('redo size','redo writes','redo entries')\n            ORDER BY name"
    },
    {
        "id": 55,
        "title": "Undo configuration and usage",
        "method": "OracleConnector.get_undo_config_usage()",
        "description": "Undo tablespaces status and retention settings.",
        "headers": [
            "Undo Tablespace Name",
            "Status",
            "Retention (s)"
        ],
        "category": "I/O",
        "query": "SELECT tablespace_name,\n                   status,\n                   TO_CHAR(retention) AS retention\n            FROM dba_tablespaces\n            WHERE contents = 'UNDO'"
    },
    {
        "id": 56,
        "title": "Oracle datafiles / physical layout",
        "method": "OracleConnector.get_datafiles_physical_layout()",
        "description": "Oracle datafiles physical layout.",
        "headers": [
            "File ID",
            "File Name",
            "Tablespace Name",
            "Size (GB)",
            "Autoextensible",
            "Status"
        ],
        "category": "Storage",
        "query": "SELECT file_id,\n                   file_name,\n                   tablespace_name,\n                   ROUND(bytes/POWER(1024,3),2) AS size_gb,\n                   autoextensible,\n                   status\n            FROM dba_data_files\n            ORDER BY bytes DESC"
    },
    {
        "id": 57,
        "title": "ASM disk group capacity",
        "method": "OracleConnector.get_asm_diskgroup_capacity()",
        "description": "ASM disk groups total capacity and free space.",
        "headers": [
            "Diskgroup Name",
            "Type",
            "Total (MB)",
            "Free (MB)",
            "Used %"
        ],
        "category": "Overview",
        "query": "SELECT name,\n                   type,\n                   total_mb,\n                   free_mb,\n                   ROUND((total_mb-free_mb)/NULLIF(total_mb,0)*100,2) AS used_pct\n            FROM v$asm_diskgroup\n            ORDER BY used_pct DESC"
    },
    {
        "id": 58,
        "title": "Database files and storage",
        "method": "OracleConnector.get_database_files_storage()",
        "description": "Database files summary by file type.",
        "headers": [
            "File Type Category",
            "File Count"
        ],
        "category": "Storage",
        "query": "SELECT file_type,\n                   COUNT(*) AS file_count\n            FROM v$database\n            CROSS JOIN (\n                SELECT 'DATAFILE' AS file_type FROM dual\n                UNION ALL SELECT 'TEMPFILE' FROM dual\n                UNION ALL SELECT 'CONTROLFILE' FROM dual\n                UNION ALL SELECT 'ONLINE REDO' FROM dual\n            )\n            GROUP BY file_type"
    },
    {
        "id": 59,
        "title": "Identify archival candidates",
        "method": "OracleConnector.get_archival_candidates()",
        "description": "Large tables (>10k rows) with minimal DML modifications (<=100) identified for archiving.",
        "headers": [
            "Schema",
            "Table Name",
            "Partitioned",
            "Rows (Est)",
            "Inserts",
            "Updates",
            "Deletes",
            "Last Analyzed",
            "Last Modified"
        ],
        "category": "Overview",
        "query": "```python\ndef get_archival_candidates(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT\n                t.owner AS schema_name,\n                t.table_name,\n                t.partitioned,\n                t.num_rows,\n                NVL(m.total_inserts, 0) AS inserts,\n                NVL(m.total_updates, 0) AS updates,\n                NVL(m.total_deletes, 0) AS deletes,\n                TO_CHAR(t.last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed,\n                TO_CHAR(m.last_modified, 'YYYY-MM-DD HH24:MI:SS') AS last_modified\n            FROM dba_tables t\n            LEFT JOIN (\n                SELECT\n                    table_owner,\n                    table_name,\n                    SUM(inserts) AS total_inserts,\n                    SUM(updates) AS total_updates,\n                    SUM(deletes) AS total_deletes,\n                    MAX(timestamp) AS last_modified\n                FROM all_tab_modifications\n                GROUP BY table_owner, table_name\n            ) m ON m.table_owner = t.owner AND m.table_name = t.table_name\n            WHERE {self._system_schema_filter('t.owner')}\n              AND t.num_rows IS NOT NULL\n              AND t.num_rows > 10000\n              AND (NVL(m.total_inserts, 0) + NVL(m.total_updates, 0) + NVL(m.total_deletes, 0)) <= 100\n            ORDER BY t.num_rows DESC NULLS LAST\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT\n                    t.owner AS schema_name,\n                    t.table_name,\n                    t.partitioned,\n                    t.num_rows,\n                    NVL(m.total_inserts, 0) AS inserts,\n                    NVL(m.total_updates, 0) AS updates,\n                    NVL(m.total_deletes, 0) AS deletes,\n                    TO_CHAR(t.last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed,\n                    TO_CHAR(m.last_modified, 'YYYY-MM-DD HH24:MI:SS') AS last_modified\n                FROM all_tables t\n                LEFT JOIN (\n                    SELECT\n                        table_owner,\n                        table_name,\n                        SUM(inserts) AS total_inserts,\n                        SUM(updates) AS total_updates,\n                        SUM(deletes) AS total_deletes,\n                        MAX(timestamp) AS last_modified\n                    FROM all_tab_modifications\n                    GROUP BY table_owner, table_name\n                ) m ON m.table_owner = t.owner AND m.table_name = t.table_name\n                WHERE {self._system_schema_filter('t.owner')}\n                  AND t.num_rows IS NOT NULL\n                  AND t.num_rows > 10000\n                  AND (NVL(m.total_inserts, 0) + NVL(m.total_updates, 0) + NVL(m.total_deletes, 0)) <= 100\n                ORDER BY t.num_rows DESC NULLS LAST\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 60,
        "title": "Identify tables with limited usage",
        "method": "OracleConnector.get_limited_usage_tables()",
        "description": "Tables with minimal recorded DML modifications.",
        "headers": [
            "Schema",
            "Table Name",
            "Inserts",
            "Updates",
            "Deletes",
            "Last Modified"
        ],
        "category": "Overview",
        "query": "SELECT table_owner AS schema_name,\n                   table_name,\n                   inserts,\n                   updates,\n                   deletes,\n                   TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS last_modified\n            FROM all_tab_modifications\n            WHERE {self._system_schema_filter('table_owner')}\n            ORDER BY (inserts + updates + deletes) ASC"
    },
    {
        "id": 61,
        "title": "Identify hot tables / objects",
        "method": "OracleConnector.get_hot_tables_objects()",
        "description": "Top active workload tables ranked by DML modifications.",
        "headers": [
            "Schema",
            "Table Name",
            "Inserts",
            "Updates",
            "Deletes",
            "Last Modified"
        ],
        "category": "Overview",
        "query": "SELECT table_owner AS schema_name,\n                   table_name,\n                   inserts,\n                   updates,\n                   deletes,\n                   TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS last_modified\n            FROM all_tab_modifications\n            WHERE {self._system_schema_filter('table_owner')}\n            ORDER BY (inserts + updates + deletes) DESC"
    },
    {
        "id": 62,
        "title": "Segment space / fragmentation candidates",
        "method": "OracleConnector.get_fragmentation_candidates()",
        "description": "Segment space allocation and fragmentation candidates.",
        "headers": [
            "Schema",
            "Segment Name",
            "Segment Type",
            "Size (MB)",
            "Size (GB)"
        ],
        "category": "Storage",
        "query": "```python\ndef get_fragmentation_candidates(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT owner AS schema_name,\n                   segment_name,\n                   segment_type,\n                   ROUND(bytes/POWER(1024,2),2) AS size_mb,\n                   ROUND(bytes/POWER(1024,3),2) AS size_gb\n            FROM dba_segments\n            WHERE {self._system_schema_filter('owner')}\n            ORDER BY bytes DESC\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT owner AS schema_name,\n                       segment_name,\n                       segment_type,\n                       ROUND(bytes/POWER(1024,2),2) AS size_mb,\n                       ROUND(bytes/POWER(1024,3),2) AS size_gb\n                FROM all_segments\n                WHERE {self._system_schema_filter('owner')}\n                ORDER BY bytes DESC\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 63,
        "title": "Foreign-key dependency graph",
        "method": "OracleConnector.get_foreign_key_dependency_graph()",
        "description": "Referential dependency graph for migration sequencing.",
        "headers": [
            "Child Schema",
            "Child Table",
            "Child Column",
            "Ref Schema",
            "Ref Table",
            "Ref Column"
        ],
        "category": "Schema",
        "query": "SELECT a.owner AS schema_name,\n                   a.table_name,\n                   a.column_name,\n                   c_pk.owner AS referenced_schema,\n                   c_pk.table_name AS referenced_table,\n                   b.column_name AS referenced_column\n            FROM dba_cons_columns a\n            JOIN dba_constraints c\n              ON c.owner = a.owner\n             AND c.constraint_name = a.constraint_name\n            JOIN dba_constraints c_pk\n              ON c_pk.owner = c.r_owner\n             AND c_pk.constraint_name = c.r_constraint_name\n            JOIN dba_cons_columns b\n              ON b.owner = c_pk.owner\n             AND b.constraint_name = c_pk.constraint_name\n             AND b.position = a.position\n            WHERE {self._system_schema_filter('a.owner')}\n              AND c.constraint_type = 'R'\n            ORDER BY a.owner, a.table_name, c_pk.table_name"
    },
    {
        "id": 64,
        "title": "Stored code dependencies",
        "method": "OracleConnector.get_stored_code_dependencies()",
        "description": "Summary counts of Oracle stored procedures, functions, packages, views, triggers, jobs, and code dependencies.",
        "headers": [
            "Programmability Object / Dependency Type",
            "Total Count"
        ],
        "category": "Overview",
        "query": "```python\ndef get_stored_code_dependencies(self) -> List[Dict[str, Any]]:\n        query_dba = f\"\"\"\n            SELECT type AS object_type,\n                   COUNT(*) AS dependency_count\n            FROM dba_dependencies\n            WHERE {self._system_schema_filter('owner')}\n            GROUP BY type\n            ORDER BY dependency_count DESC\n        \"\"\"\n        rows = self._execute_query(query_dba)\n        if not rows:\n            query_all = f\"\"\"\n                SELECT type AS object_type,\n                       COUNT(*) AS dependency_count\n                FROM all_dependencies\n                WHERE {self._system_schema_filter('owner')}\n                GROUP BY type\n                ORDER BY dependency_count DESC\n            \"\"\"\n            rows = self._execute_query(query_all)\n        return rows\n```"
    },
    {
        "id": 65,
        "title": "Configuration assessment (Top 10)",
        "method": "OracleConnector.get_configuration_assessment()",
        "description": "Top 10 key Oracle database initialization parameters from V$PARAMETER.",
        "headers": [
            "Parameter Name",
            "Value",
            "Display Value"
        ],
        "category": "I/O",
        "query": "SELECT name,\n                   value,\n                   display_value\n            FROM v$parameter\n            WHERE name IN (\n                'db_name',\n                'sga_target',\n                'pga_aggregate_target',\n                'memory_target',\n                'processes',\n                'sessions',\n                'open_cursors',\n                'db_block_size',\n                'db_recovery_file_dest_size',\n                'optimizer_mode'\n            )\n            ORDER BY CASE name\n                WHEN 'db_name' THEN 1\n                WHEN 'sga_target' THEN 2\n                WHEN 'pga_aggregate_target' THEN 3\n                WHEN 'memory_target' THEN 4\n                WHEN 'processes' THEN 5\n                WHEN 'sessions' THEN 6\n                WHEN 'open_cursors' THEN 7\n                WHEN 'db_block_size' THEN 8\n                WHEN 'db_recovery_file_dest_size' THEN 9\n                WHEN 'optimizer_mode' THEN 10\n                ELSE 11\n            END"
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


_ORACLE_ALIASES = {
    "check table fragmentation": "60",
    "segment space / fragmentation candidates": "60",
    "fragmentation": "60",
    "schema inventory": "2",
    "database sizes": "2",
    "top 100 largest segments": "4",
    "top 100 tables": "4",
}
for alias, id_val in _ORACLE_ALIASES.items():
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
        
    # 2. Match exact ID or leading ID number e.g. '60' or '60. Segment space'
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
    """Return all insight definitions for Oracle."""
    return INSIGHTS
