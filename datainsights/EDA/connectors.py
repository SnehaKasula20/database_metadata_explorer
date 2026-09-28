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

class DatabaseConnector:
    def __init__(self, config: dict):
        self.config = config
        self.connection = None

    def connect(self, database: Optional[str] = None):
        raise NotImplementedError

    def list_databases(self) -> list[str]:
        raise NotImplementedError

    def list_schemas(self, database: str) -> list[str]:
        raise NotImplementedError

    def list_tables(self, database: str, schema: str) -> list[str]:
        raise NotImplementedError

    def read_table(self, database: str, schema: str, table: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        raise NotImplementedError

    def test_connection(self) -> None:
        if self.connection is None:
            self.connect()
        cur = self.connection.cursor()
        try:
            cur.execute(self.health_check_sql())
            cur.fetchone()
        finally:
            cur.close()

    def health_check_sql(self) -> str:
        return "SELECT 1"

    def close(self):
        if self.connection is not None:
            try:
                self.connection.close()
            finally:
                self.connection = None

    @staticmethod
    def _fetch_dataframe(cursor) -> pd.DataFrame:
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return pd.DataFrame.from_records(rows, columns=columns)

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

class SnowflakeConnector(DatabaseConnector):
    def connect(self, database: Optional[str] = None):
        import snowflake.connector
        c = self.config
        kwargs = {
            "account": c["account"],
            "user": c["user"],
            "password": c["password"],
            "warehouse": c.get("warehouse"),
            "role": c.get("role"),
        }
        if database:
            kwargs["database"] = database
        kwargs = {k: v for k, v in kwargs.items() if v not in (None, "")}
        self.connection = snowflake.connector.connect(**kwargs)
        return self.connection

    def list_databases(self) -> list[str]:
        cur = self.connection.cursor()
        try:
            cur.execute("SHOW DATABASES")
            rows = cur.fetchall()
            cols = [d[0].lower() for d in cur.description]
            name_idx = cols.index("name")
            return sorted({str(r[name_idx]) for r in rows if r[name_idx]})
        finally:
            cur.close()

    def list_schemas(self, database: str) -> list[str]:
        db = self._quote_identifier(database)
        cur = self.connection.cursor()
        try:
            cur.execute(
                f"SELECT SCHEMA_NAME FROM {db}.INFORMATION_SCHEMA.SCHEMATA "
                "WHERE SCHEMA_NAME <> 'INFORMATION_SCHEMA' ORDER BY SCHEMA_NAME"
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def list_tables(self, database: str, schema: str) -> list[str]:
        db = self._quote_identifier(database)
        cur = self.connection.cursor()
        try:
            cur.execute(
                f"SELECT TABLE_NAME FROM {db}.INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_NAME",
                (schema,),
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def read_table(self, database: str, schema: str, table: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        cur = self.connection.cursor()
        try:
            sql = (
                f"SELECT * FROM {self._quote_identifier(database)}."
                f"{self._quote_identifier(schema)}."
                f"{self._quote_identifier(table)}"
            )
            if limit and limit > 0:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            return self._fetch_dataframe(cur)
        finally:
            cur.close()

class SqlServerConnector(DatabaseConnector):
    @staticmethod
    def _q(identifier: str) -> str:
        return "[" + identifier.replace("]", "]]") + "]"

    def connect(self, database: Optional[str] = None):
        import pyodbc
        c = self.config
        target = database or c.get("initial_database") or "master"
        conn_string = (
            f"DRIVER={{{c['driver']}}};"
            f"SERVER={c['host']},{int(c.get('port', 1433))};"
            f"DATABASE={target};"
            f"UID={c['user']};PWD={c['password']};"
            f"Encrypt={c.get('encrypt', 'yes')};"
            f"TrustServerCertificate={c.get('trust_server_certificate', 'yes')};"
        )
        self.connection = pyodbc.connect(conn_string)
        return self.connection

    def list_databases(self) -> list[str]:
        cur = self.connection.cursor()
        try:
            cur.execute(
                "SELECT name FROM sys.databases "
                "WHERE state_desc='ONLINE' AND HAS_DBACCESS(name)=1 ORDER BY name"
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def list_schemas(self, database: str) -> list[str]:
        db = self._q(database)
        cur = self.connection.cursor()
        try:
            cur.execute(
                f"SELECT SCHEMA_NAME FROM {db}.INFORMATION_SCHEMA.SCHEMATA "
                "WHERE SCHEMA_NAME NOT IN ('INFORMATION_SCHEMA','sys','guest') "
                "ORDER BY SCHEMA_NAME"
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def list_tables(self, database: str, schema: str) -> list[str]:
        db = self._q(database)
        cur = self.connection.cursor()
        try:
            cur.execute(
                f"SELECT TABLE_NAME FROM {db}.INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA=? AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
                (schema,),
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def read_table(self, database: str, schema: str, table: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        cur = self.connection.cursor()
        try:
            top_clause = f"TOP ({int(limit)}) " if limit and limit > 0 else ""
            sql = f"SELECT {top_clause}* FROM {self._q(database)}.{self._q(schema)}.{self._q(table)}"
            cur.execute(sql)
            return self._fetch_dataframe(cur)
        finally:
            cur.close()

class OracleConnector(DatabaseConnector):
    def connect(self, database: Optional[str] = None):
        import oracledb
        c = self.config
        dsn = oracledb.makedsn(
            c["host"],
            int(c.get("port", 1521)),
            sid=c["sid"],
        )
        self.connection = oracledb.connect(
            user=c["user"], password=c["password"], dsn=dsn
        )
        return self.connection

    def health_check_sql(self) -> str:
        return "SELECT 1 FROM DUAL"

    def list_databases(self) -> list[str]:
        return [str(self.config["sid"])]

    def list_schemas(self, database: str) -> list[str]:
        cur = self.connection.cursor()
        try:
            cur.execute(
                "SELECT DISTINCT OWNER FROM ALL_TABLES "
                "WHERE OWNER NOT IN "
                "('SYS','SYSTEM','XDB','MDSYS','CTXSYS','ORDSYS','OUTLN','DBSNMP') "
                "ORDER BY OWNER"
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def list_tables(self, database: str, schema: str) -> list[str]:
        cur = self.connection.cursor()
        try:
            cur.execute(
                "SELECT TABLE_NAME FROM ALL_TABLES "
                "WHERE OWNER=:owner ORDER BY TABLE_NAME",
                owner=schema.upper(),
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def read_table(self, database: str, schema: str, table: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        cur = self.connection.cursor()
        try:
            sql = (
                f"SELECT * FROM {self._quote_identifier(schema.upper())}."
                f"{self._quote_identifier(table.upper())}"
            )
            if limit and limit > 0:
                sql += f" WHERE ROWNUM <= {int(limit)}"
            cur.execute(sql)
            return self._fetch_dataframe(cur)
        finally:
            cur.close()

class MySqlConnector(DatabaseConnector):
    @staticmethod
    def _q(identifier: str) -> str:
        return "`" + identifier.replace("`", "``") + "`"

    def connect(self, database: Optional[str] = None):
        c = self.config
        kwargs = {
            "host": c["host"],
            "port": int(c.get("port", 3306)),
            "user": c["user"],
            "password": c["password"],
        }
        if database:
            kwargs["database"] = database

        try:
            import pymysql
            self.connection = pymysql.connect(**kwargs)
        except Exception:
            import mysql.connector
            self.connection = mysql.connector.connect(**kwargs)
        return self.connection

    def list_databases(self) -> list[str]:
        cur = self.connection.cursor()
        try:
            cur.execute("SHOW DATABASES")
            system_dbs = {"information_schema", "mysql", "performance_schema", "sys"}
            return sorted([
                str(r[0]) for r in cur.fetchall()
                if str(r[0]).lower() not in system_dbs
            ])
        finally:
            cur.close()

    def list_schemas(self, database: str) -> list[str]:
        # MySQL DATABASE and SCHEMA are synonyms.
        return [database]

    def list_tables(self, database: str, schema: str) -> list[str]:
        cur = self.connection.cursor()
        try:
            cur.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
                (database,),
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def read_table(self, database: str, schema: str, table: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        cur = self.connection.cursor()
        try:
            sql = f"SELECT * FROM {self._q(database)}.{self._q(table)}"
            if limit and limit > 0:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            return self._fetch_dataframe(cur)
        finally:
            cur.close()

class PostgresConnector(DatabaseConnector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.current_database = None

    def connect(self, database: Optional[str] = None):
        try:
            import psycopg2 as psycopg
        except ImportError:
            import psycopg
        c = self.config
        target = database or c.get("maintenance_database") or "postgres"

        if self.connection is not None and self.current_database == target:
            return self.connection

        self.close()
        self.connection = psycopg.connect(
            host=c["host"],
            port=int(c.get("port", 5432)),
            dbname=target,
            user=c["user"],
            password=c["password"],
            sslmode=c.get("sslmode", "prefer"),
        )
        self.current_database = target
        return self.connection

    def close(self):
        super().close()
        self.current_database = None

    def list_databases(self) -> list[str]:
        cur = self.connection.cursor()
        try:
            cur.execute(
                "SELECT datname FROM pg_database "
                "WHERE datallowconn=TRUE AND NOT datistemplate ORDER BY datname"
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def list_schemas(self, database: str) -> list[str]:
        self.connect(database)
        cur = self.connection.cursor()
        try:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name <> 'information_schema' "
                "AND schema_name NOT LIKE 'pg_%' ORDER BY schema_name"
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def list_tables(self, database: str, schema: str) -> list[str]:
        self.connect(database)
        cur = self.connection.cursor()
        try:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name",
                (schema,),
            )
            return [str(r[0]) for r in cur.fetchall()]
        finally:
            cur.close()

    def read_table(self, database: str, schema: str, table: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        self.connect(database)
        cur = self.connection.cursor()
        try:
            sql = (
                f"SELECT * FROM {self._quote_identifier(schema)}."
                f"{self._quote_identifier(table)}"
            )
            if limit and limit > 0:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            return self._fetch_dataframe(cur)
        finally:
            cur.close()

class DatabaseConnectorFactory:
    @staticmethod
    def create(source_name: str, config: dict) -> DatabaseConnector:
        mapping = {
            "snowflake": SnowflakeConnector,
            "sql_server": SqlServerConnector,
            "oracle": OracleConnector,
            "mysql": MySqlConnector,
            "postgres": PostgresConnector,
        }
        try:
            return mapping[source_name](config)
        except KeyError as exc:
            raise ValueError(f"Unsupported database source: {source_name}") from exc

