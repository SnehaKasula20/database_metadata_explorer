"""
Database Queries Registry & Provider
Unified dynamic SQL queries and method definitions for database observability insights.
Supports MySQL, PostgreSQL, Oracle, and Microsoft SQL Server.
"""

from typing import Any, Dict, List, Optional
from . import mysql, postgres, oracle, sqlserver

NORM_MAP = {
    "mysql": mysql,
    "postgres": postgres,
    "postgresql": postgres,
    "oracle": oracle,
    "sqlserver": sqlserver,
    "sql server": sqlserver,
    "mssql": sqlserver,
}


def _resolve_module(db_type: str):
    if not db_type:
        return None
    key = str(db_type).strip().lower().replace("_", "").replace("-", "")
    compact_key = key.replace(" ", "")
    return NORM_MAP.get(key) or NORM_MAP.get(compact_key)


import re


def get_insight_query(database_type: str, insight_title: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve metadata, method name, and SQL query for a given database and insight title.
    Returns a dict with {title, method, description, query, headers, category}.
    """
    module = _resolve_module(database_type)
    if not module or not insight_title:
        return None
    raw = str(insight_title).strip()
    res = module.get_query(raw)
    if res:
        return res
    # Fallback 1: try stripped clean title without leading number
    clean = re.sub(r"^\d+\.\s*", "", raw).strip()
    if clean and clean != raw:
        res = module.get_query(clean)
        if res:
            return res
    # Fallback 2: try leading ID number e.g. '55. Check Table Fragmentation' -> '55'
    id_m = re.match(r"^(\d+)", raw)
    if id_m:
        res = module.get_query(id_m.group(1))
        if res:
            return res
    return None


def get_all_engine_queries(database_type: str) -> List[Dict[str, Any]]:
    """
    Retrieve all queries and descriptions for a specific database engine.
    """
    module = _resolve_module(database_type)
    if not module:
        return []
    return module.get_all_queries()

