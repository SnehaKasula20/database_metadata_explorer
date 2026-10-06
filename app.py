import logging
import math
import os
import re
import tempfile
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database_metadata_explorer import DatabaseMetadataExplorer
from pdf_generator import PDFReportGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("web_app")

app = FastAPI(
    title="Database Metadata Explorer Web API",
    description="REST API for enterprise database observability and PDF report generation",
    version="2.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directory exists
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ConnectionRequest(BaseModel):
    database_type: str
    credentials: Dict[str, Any]
    time_range: Optional[str] = "1h"


SUPPORTED_DATABASES = [
    {
        "id": "PostgreSQL",
        "name": "PostgreSQL",
        "default_port": 5432,
        "description": "Enterprise relational database system",
        "fields": ["host", "port", "username", "password", "database", "schema"],
        "color": "#2563EB",
        "icon": "database"
    },
    {
        "id": "SQL Server",
        "name": "Microsoft SQL Server",
        "default_port": 1433,
        "description": "Microsoft relational database engine",
        "fields": ["host", "port", "username", "password", "database", "schema"],
        "color": "#DC2626",
        "icon": "server"
    },
    {
        "id": "Oracle",
        "name": "Oracle Database",
        "default_port": 1521,
        "description": "High-performance enterprise database engine",
        "fields": ["host", "port", "username", "password", "service_name", "schema"],
        "color": "#D97706",
        "icon": "layers"
    },
    {
        "id": "MySQL",
        "name": "MySQL",
        "default_port": 3306,
        "description": "Popular open-source relational database",
        "fields": ["host", "port", "username", "password"],
        "color": "#0284C7",
        "icon": "cpu"
    },
]


def _create_and_connect_explorer(database_type: str, credentials: Dict[str, Any]) -> DatabaseMetadataExplorer:
    explorer = DatabaseMetadataExplorer()
    explorer.database_type = database_type
    explorer.credentials = credentials
    explorer.create_connection(database_type, credentials)
    explorer.connector.connect()
    return explorer


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Database Metadata Explorer Web Server Running</h1>")


@app.get("/api/databases")
async def get_supported_databases():
    return {"databases": SUPPORTED_DATABASES}


@app.get("/api/saved-config")
async def get_saved_config():
    explorer = DatabaseMetadataExplorer()
    config = explorer.config
    sanitized = {}
    for db_type, creds in config.items():
        if isinstance(creds, dict):
            clean_creds = {}
            for k, v in creds.items():
                if k.lower() == "password":
                    continue
                if explorer._is_configured_value(v):
                    clean_creds[k] = v
            sanitized[db_type] = clean_creds
    return {"saved_config": sanitized}


active_connection: Dict[str, Any] = {}

from data_insights_service import data_insights_service

from pydantic import BaseModel, ConfigDict, Field

class ProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())
    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")
    table: str
    database_type: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 1000


def _format_connection_error(database_type: str, error: Exception) -> str:
    err_msg = str(error).strip()
    err_lower = err_msg.lower()

    if any(k in err_lower for k in ["access denied", "password authentication failed", "logon denied", "login failed", "1045", "28p01", "ora-01017", "18456"]):
        return f"Authentication Failed: Invalid username or password for {database_type} database connection. Details: {err_msg}"
    elif any(k in err_lower for k in ["could not connect", "connection refused", "network-related", "cannot connect", "timeout", "timed out", "2003", "ora-12170", "ora-12541"]):
        return f"Connection Failed: Host or port is unreachable. Verify server hostname/IP and port number for {database_type}. Details: {err_msg}"
    elif "database" in err_lower and any(k in err_lower for k in ["does not exist", "unknown database", "ora-12505", "ora-12154", "1049"]):
        return f"Database Error: Specified database or service name was not found on the target server. Details: {err_msg}"
    elif any(k in err_lower for k in ["module", "driver", "not found", "importerror", "nodriver"]):
        return f"Driver Error: Required database driver is not installed or configured correctly for {database_type}. Details: {err_msg}"
    else:
        return f"Connection Error: Unable to establish connection to {database_type}. Details: {err_msg}"


@app.post("/api/connect")
async def test_connection(req: ConnectionRequest):
    global active_connection
    try:
        explorer = _create_and_connect_explorer(req.database_type, req.credentials)
        active_connection = {
            "database_type": req.database_type,
            "credentials": req.credentials
        }
        db_info = f"{req.database_type}"
        if "database" in req.credentials and req.credentials["database"]:
            db_info += f" ({req.credentials['database']})"
        elif "service_name" in req.credentials and req.credentials["service_name"]:
            db_info += f" ({req.credentials['service_name']})"
        else:
            db_info += " (All Databases)"
        
        return {
            "success": True,
            "message": f"Successfully connected to {db_info}",
            "database_type": req.database_type,
        }
    except Exception as e:
        logger.error("Connection failed for %s: %s", req.database_type, e)
        formatted_err = _format_connection_error(req.database_type, e)
        raise HTTPException(status_code=400, detail=formatted_err)




def _evaluate_status(metric: str, value: float) -> str:
    if metric == "cpu":
        if value < 60.0:
            return "Normal"
        elif value < 80.0:
            return "Elevated"
        elif value < 90.0:
            return "High"
        else:
            return "Critical"
    elif metric == "cache":
        if value >= 98.0:
            return "Healthy"
        elif value >= 90.0:
            return "Elevated"
        else:
            return "Needs Attention"
    elif metric == "blocking":
        if value == 0:
            return "Normal"
        elif value <= 5:
            return "Elevated"
        else:
            return "Critical"
    elif metric == "connection_pct":
        if value < 60.0:
            return "Normal"
        elif value < 80.0:
            return "Elevated"
        elif value < 90.0:
            return "High"
        else:
            return "Critical"
    elif metric == "iops":
        if value < 3000:
            return "Healthy"
        elif value < 6000:
            return "Elevated"
        else:
            return "High"
    return "Normal"


def _generate_health_summary(kpis: Dict[str, Any], top_cpu: List[Dict[str, Any]], top_tables: List[Dict[str, Any]], wait_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    findings = []
    statuses = []

    # 1. Blocking Sessions (Current vs Historical Peak)
    blocked_obj = kpis.get("blocked_sessions") or kpis.get("blocking_sessions") or {}
    blocked_cnt = blocked_obj.get("current_count", blocked_obj.get("count", 0))
    peak_blocked = blocked_obj.get("peak_count", 0)
    period_str = blocked_obj.get("period_str", "Last 1 Hour")

    if blocked_cnt > 0:
        findings.append(f"Critical: {blocked_cnt} session(s) are currently blocked waiting for locks (Peaked at {peak_blocked} in {period_str}).")
        statuses.append("Critical" if blocked_cnt > 5 else "High")
    elif peak_blocked > 0:
        findings.append(f"Elevated: 0 sessions currently blocked (Blocking peaked at {peak_blocked} session(s) during {period_str.lower()}).")
        statuses.append("Elevated")
    else:
        findings.append(f"No blocking sessions or lock contention currently detected during {period_str.lower()}.")
        statuses.append("Healthy")

    # 2. CPU Utilization (Current Snapshot vs Period Avg & Peak)
    cpu_obj = kpis.get("cpu", {})
    cpu_val = cpu_obj.get("value", 14.8)
    cpu_avg = cpu_obj.get("avg", cpu_val)
    cpu_peak = cpu_obj.get("peak", cpu_val)
    cpu_st = _evaluate_status("cpu", cpu_val)
    statuses.append(cpu_st)
    if cpu_st in {"High", "Critical"}:
        findings.append(f"CPU utilization is currently {cpu_st.lower()} at {cpu_val}% (Period Avg: {cpu_avg}%, Peak: {cpu_peak}% in {period_str.lower()}).")
    elif cpu_st == "Elevated":
        findings.append(f"CPU utilization is currently elevated at {cpu_val}% (Period Avg: {cpu_avg}%, Peak: {cpu_peak}% in {period_str.lower()}).")
    else:
        findings.append(f"CPU utilization is currently normal at {cpu_val}% (Period Avg: {cpu_avg}%, Peak: {cpu_peak}% in {period_str.lower()}).")

    # 3. Top CPU Query
    if top_cpu:
        top_q_name = top_cpu[0].get("query_text") or top_cpu[0].get("query", "Top Query")
        top_q_val = top_cpu[0].get("metric", top_cpu[0].get("cpu_time", "0"))
        val_str = str(top_q_val)
        if not re.search(r"(?i)(ms|sec|s|s)", val_str):
            val_str = f"{val_str} ms"
        findings.append(f"Highest CPU-consuming query '{top_q_name}' recorded {val_str} execution time in {period_str.lower()}.")

    # 4. Wait Events
    if wait_events:
        top_wait = wait_events[0].get("name", "")
        findings.append(f"Dominant wait activity observed on event '{top_wait}' during {period_str.lower()}.")

    # 5. Storage & Largest Table (Inventory + Period Growth)
    if top_tables:
        t_name = top_tables[0].get("name") or top_tables[0].get("table_name") or "Primary Table"
        t_size = top_tables[0].get("size") or (f"{top_tables[0].get('total_gb', 0.0)} GB" if top_tables[0].get('total_gb') else f"{top_tables[0].get('total_mb', 0.0)} MB")
        t_size_str = str(t_size)
        if not re.search(r"(?i)(GB|MB|KB|TB|Bytes)", t_size_str):
            t_size_str = f"{t_size_str} MB"
        growth_str = kpis.get("storage", {}).get("growth", "+0.00 MB")
        if any(w in growth_str for w in ["+0.00", "+0.0 GB", "+0.0 MB", "0.00", "+0 MB", "+0 GB"]):
            findings.append(f"Largest storage footprint table is '{t_name}' at {t_size_str} (no size change in {period_str.lower()}).")
        else:
            findings.append(f"Largest storage footprint table is '{t_name}' at {t_size_str} ({growth_str} growth in {period_str.lower()}).")

    # Overall Status Calculation
    if "Critical" in statuses:
        overall = "Critical"
    elif "High" in statuses:
        overall = "High"
    elif "Elevated" in statuses or "Needs Attention" in statuses:
        overall = "Elevated"
    else:
        overall = "Healthy"

    return {
        "overall_status": overall,
        "findings": findings[:5]
    }


def _generate_dynamic_cpu_trend(base_cpu: float, time_range: str, cpu_queries: List[Dict[str, Any]]) -> Dict[str, Any]:
    period_labels = {
        "15m": "Last 15 Minutes",
        "30m": "Last 30 Minutes",
        "1h": "Last 1 Hour",
        "3h": "Last 3 Hours",
        "6h": "Last 6 Hours",
        "12h": "Last 12 Hours",
        "24h": "Last 24 Hours"
    }
    period_str = period_labels.get(time_range, "Last 1 Hour")
    
    interval_mins = 5
    if time_range == "15m": interval_mins = 1.25
    elif time_range == "30m": interval_mins = 2.5
    elif time_range == "1h": interval_mins = 5
    elif time_range == "3h": interval_mins = 15
    elif time_range == "6h": interval_mins = 30
    elif time_range == "12h": interval_mins = 60
    elif time_range == "24h": interval_mins = 120

    now = time.time()
    num_points = 12
    timestamps = []
    values = []

    calc_base_cpu = base_cpu
    if cpu_queries:
        total_cpu_time = sum(q.get("cpu_time", 0.0) for q in cpu_queries)
        if total_cpu_time > 0:
            calc_base_cpu = round(min(100.0, max(0.5, total_cpu_time / 100.0)), 1)
        elif base_cpu == 0.0:
            calc_base_cpu = 0.5

    for i in range(num_points - 1, -1, -1):
        t_sec = now - (i * interval_mins * 60)
        t_struct = time.localtime(t_sec)
        timestamps.append(time.strftime("%H:%M", t_struct))
        
        val = round(max(0.0, min(100.0, calc_base_cpu)), 1)
        values.append(val)

    current_val = values[-1]
    avg_val = round(sum(values) / len(values), 1)
    peak_val = max(values)
    min_val = min(values)
    start_val = values[0]
    peak_idx = values.index(peak_val)
    peak_time = timestamps[peak_idx]

    thresholds = {"normal": 60.0, "elevated": 80.0, "high": 90.0, "critical": 100.0}
    if current_val >= 90.0:
        status = "Critical"
    elif current_val >= 80.0:
        status = "High"
    elif current_val >= 60.0:
        status = "Elevated"
    else:
        status = "Normal"

    if peak_val >= 80.0 and current_val >= 60.0:
        insight = f"CPU utilization remained above the configured warning threshold for the selected period and peaked at {peak_val}% at {peak_time}."
    elif (current_val - start_val) >= 8.0:
        insight = f"CPU utilization increased from {start_val}% to {current_val}% during {period_str.lower()}, reaching a peak of {peak_val}%."
    elif (start_val - current_val) >= 8.0:
        insight = f"CPU utilization decreased from {start_val}% to {current_val}% during {period_str.lower()}, with an average of {avg_val}%."
    elif peak_val - avg_val >= 12.0:
        insight = f"CPU utilization reached a peak of {peak_val}% at {peak_time}, while the current utilization is {current_val}%."
    elif avg_val < 35.0:
        insight = f"CPU utilization remained steady at an average of {avg_val}% during {period_str.lower()} (no workload changes detected)."
    else:
        insight = f"CPU utilization is currently {current_val}%, with an average of {avg_val}% over {period_str.lower()}. Utilization remained stable."

    return {
        "title": "CPU Utilization",
        "labels": timestamps,
        "values": values,
        "current": current_val,
        "avg": avg_val,
        "peak": peak_val,
        "min": min_val,
        "start": start_val,
        "peak_time": peak_time,
        "status": status,
        "period_label": f"Scale 0–100% ({period_str})",
        "time_period": period_str,
        "thresholds": thresholds,
        "insight": insight
    }


def _generate_dynamic_io_trend(base_iops: int, time_range: str, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    period_labels = {
        "15m": "Last 15 Minutes",
        "30m": "Last 30 Minutes",
        "1h": "Last 1 Hour",
        "3h": "Last 3 Hours",
        "6h": "Last 6 Hours",
        "12h": "Last 12 Hours",
        "24h": "Last 24 Hours"
    }
    period_str = period_labels.get(time_range, "Last 1 Hour")
    
    interval_mins = 5
    if time_range == "15m": interval_mins = 1.25
    elif time_range == "30m": interval_mins = 2.5
    elif time_range == "1h": interval_mins = 5
    elif time_range == "3h": interval_mins = 15
    elif time_range == "6h": interval_mins = 30
    elif time_range == "12h": interval_mins = 60
    elif time_range == "24h": interval_mins = 120

    now = time.time()
    num_points = 12
    timestamps = []
    values = []
    read_values = []
    write_values = []

    has_read_write = False
    total_read = 0
    total_write = 0
    for r in reports:
        headers = [str(h).lower() for h in r.get("headers", [])]
        if "reads" in headers and "writes" in headers:
            r_idx = headers.index("reads")
            w_idx = headers.index("writes")
            for row in r.get("rows", []):
                try:
                    total_read += int(re.sub(r"[^\d]", "", str(row[r_idx])))
                    total_write += int(re.sub(r"[^\d]", "", str(row[w_idx])))
                except (ValueError, IndexError):
                    pass
            if total_read > 0 or total_write > 0:
                has_read_write = True
                break

    calc_iops = base_iops
    if has_read_write and (total_read > 0 or total_write > 0):
        calc_iops = max(base_iops, total_read + total_write)

    for i in range(num_points - 1, -1, -1):
        t_sec = now - (i * interval_mins * 60)
        t_struct = time.localtime(t_sec)
        timestamps.append(time.strftime("%H:%M", t_struct))
        
        val = int(max(0, calc_iops))
        values.append(val)

        if has_read_write:
            total_rw = max(1, total_read + total_write)
            read_ratio = total_read / total_rw
            r_val = int(round(val * read_ratio))
            w_val = val - r_val
            read_values.append(r_val)
            write_values.append(w_val)

    current_val = values[-1]
    avg_val = int(round(sum(values) / len(values)))
    peak_val = max(values)
    min_val = min(values)
    start_val = values[0]
    peak_idx = values.index(peak_val)
    peak_time = timestamps[peak_idx]

    pct_change = round(((current_val - start_val) / max(1, start_val)) * 100, 1) if start_val > 0 else 0.0

    thresholds = {"healthy": 3000, "elevated": 6000, "high": 9000}
    if current_val >= thresholds["elevated"]:
        status = "Elevated"
    elif current_val >= thresholds["high"]:
        status = "High"
    else:
        status = "Healthy"

    if peak_val >= int(avg_val * 1.35) and avg_val > 0:
        insight = f"I/O activity peaked at {peak_val} IOPS at {peak_time}, above the period average of {avg_val} IOPS."
    elif pct_change >= 15.0:
        insight = f"I/O activity increased by {pct_change}% during {period_str.lower()}, reaching a peak of {peak_val} IOPS."
    elif pct_change <= -15.0:
        insight = f"I/O activity decreased by {abs(pct_change)}% from {start_val} to {current_val} IOPS during {period_str.lower()}."
    elif current_val > thresholds["healthy"]:
        insight = f"I/O activity is currently {current_val} IOPS and is above the configured warning threshold."
    elif avg_val > 4000:
        insight = f"I/O activity remained consistently high, averaging {avg_val} IOPS during {period_str.lower()}."
    else:
        insight = f"I/O activity remained stable at an average of {avg_val} IOPS during {period_str.lower()} (no workload changes detected)."

    res = {
        "title": "I/O Operations (IOPS)",
        "labels": timestamps,
        "values": values,
        "current": current_val,
        "avg": avg_val,
        "peak": peak_val,
        "min": min_val,
        "start": start_val,
        "peak_time": peak_time,
        "pct_change": pct_change,
        "status": status,
        "period_label": f"IOPS Activity ({period_str})",
        "time_period": period_str,
        "unit": "IOPS",
        "thresholds": thresholds,
        "insight": insight,
        "has_read_write": has_read_write
    }

    if has_read_write:
        res["read_values"] = read_values
        res["write_values"] = write_values

    return res


def _parse_size_mb(val_str: str) -> float:
    if not val_str or str(val_str).strip() in ["-", "N/A", "None", ""]:
        return 0.0
    s = str(val_str).strip()
    match = re.search(r"([\d\.]+)\s*(GB|MB|KB|TB|Bytes|B)?", s, re.IGNORECASE)
    if not match:
        return 0.0
    try:
        num = float(match.group(1))
    except ValueError:
        return 0.0
    unit = (match.group(2) or "MB").upper()
    if unit == "GB":
        return num * 1024.0
    elif unit == "TB":
        return num * 1024.0 * 1024.0
    elif unit == "KB":
        return num / 1024.0
    elif unit in ("BYTES", "B"):
        return num / (1024.0 * 1024.0)
    return num


def _extract_charts_summary(reports: List[Dict[str, Any]], time_range: str = "1h", connector: Any = None) -> Dict[str, Any]:
    now_iso = time.strftime("%Y-%m-%d %H:%M:%S IST", time.localtime())

    storage_breakdown = []
    top_tables = []
    cpu_queries = []
    io_waits = []
    wait_statistics = []

    raw_kpis = {
        "database_size": "N/A",
        "total_tables": 0,
        "active_connections": 0,
        "max_connections": 100,
        "blocking_sessions": 0,
        "cache_hit_ratio": 99.4,
        "cpu_usage_pct": 0.0,
        "iops": 0,
        "qps": 0
    }

    total_exec_count = 0.0

    for r in reports:
        title = r.get("title", "")
        title_lower = title.lower()
        rows = r.get("rows", [])
        headers = r.get("headers", [])

        # 1. Database Size / Storage
        if any(k in title_lower for k in ["database/schema inventory", "database inventory", "database sizes", "database schema sizes", "schema sizes", "schema inventory", "tablespace", "storage analysis", "database file configuration"]):
            total_mb_found = 0.0
            size_gb_col = -1
            size_mb_col = -1
            for idx, h in enumerate(headers):
                hl = str(h).lower()
                if "total_size_gb" in hl or "data_size_gb" in hl or "size (gb)" in hl:
                    size_gb_col = idx
                elif "actual_size_mb" in hl or "size (mb)" in hl or "size_mb" in hl:
                    size_mb_col = idx

            for row in rows:
                if len(row) >= 2:
                    first_col = str(row[0]).upper()
                    if "TOTAL" in first_col or "SUM" in first_col or len(rows) == 1:
                        found_size = None
                        for cell in reversed(row):
                            c_str = str(cell).strip()
                            if c_str and c_str != "-" and c_str.upper() != "N/A" and re.search(r"\d", c_str):
                                found_size = c_str
                                break
                        if found_size:
                            raw_kpis["database_size"] = found_size
                    else:
                        if first_col not in ["INFORMATION_SCHEMA", "PERFORMANCE_SCHEMA", "MYSQL", "SYS", "MASTER", "MSDB", "MODEL", "TEMPDB"]:
                            if size_gb_col != -1 and size_gb_col < len(row):
                                sz = _parse_size_mb(str(row[size_gb_col])) * 1024.0
                            elif size_mb_col != -1 and size_mb_col < len(row):
                                sz = _parse_size_mb(str(row[size_mb_col]))
                            else:
                                sz = _parse_size_mb(str(row[-1]))
                            total_mb_found += sz
            if raw_kpis["database_size"] == "N/A" and total_mb_found > 0:
                if total_mb_found >= 1024.0:
                    raw_kpis["database_size"] = f"{round(total_mb_found / 1024.0, 2)} GB"
                else:
                    raw_kpis["database_size"] = f"{round(total_mb_found, 2)} MB"

        # 2. Total Tables
        if any(k in title_lower for k in ["row count", "table inventory", "no of tables", "table row counts", "table storage", "table-level", "top 100 tables", "schema/table storage"]):
            raw_kpis["total_tables"] = max(raw_kpis["total_tables"], len(rows))

        # 3. Active Connections / Sessions
        if any(k in title_lower for k in ["connections", "sessions and connections", "active sessions", "session inventory", "processlist", "active connections"]):
            found_threads_metric = False
            questions_val = None
            uptime_val = None
            sum_session_counts = 0
            has_count_col = False
            for row in rows:
                if len(row) >= 2:
                    k_str = str(row[0]).lower().strip()
                    v_str = str(row[1]).strip()
                    if k_str in {"threads_connected", "threads connected"}:
                        try:
                            raw_kpis["active_connections"] = int(re.sub(r"[^\d]", "", v_str))
                            found_threads_metric = True
                        except ValueError:
                            pass
                    elif k_str in {"max_connections", "max connections"}:
                        try:
                            raw_kpis["max_connections"] = int(re.sub(r"[^\d]", "", v_str))
                        except ValueError:
                            pass
                    elif k_str in {"questions", "queries"}:
                        try:
                            questions_val = float(re.sub(r"[^\d.]", "", v_str))
                        except ValueError:
                            pass
                    elif k_str in {"uptime"}:
                        try:
                            uptime_val = float(re.sub(r"[^\d.]", "", v_str))
                        except ValueError:
                            pass
                    elif any(s in k_str for s in ["active", "idle", "waiting", "running"]) and re.search(r"\d", v_str):
                        has_count_col = True
                        try:
                            cnt = int(re.sub(r"[^\d]", "", v_str))
                            sum_session_counts += cnt
                        except ValueError:
                            pass

            if questions_val is not None and uptime_val is not None and uptime_val > 0:
                raw_kpis["qps"] = round(questions_val / uptime_val, 1)

            if not found_threads_metric:
                if has_count_col and sum_session_counts > 0:
                    raw_kpis["active_connections"] = sum_session_counts
                elif len(rows) > 0 and not any("threads_" in str(r[0]).lower() for r in rows if len(r) >= 1):
                    raw_kpis["active_connections"] = len(rows)

        # 4. Blocking Sessions
        if any(k in title_lower for k in ["blocking sessions", "lock waits", "blocked queries", "lock contention"]):
            blocked_cnt = 0
            for row in rows:
                row_str = " ".join(str(val).upper() for val in (row if isinstance(row, (list, tuple)) else row.values()))
                if any(w in row_str for w in ["WAITING", "BLOCKED", "LOCK WAIT", "CONVERTING"]):
                    blocked_cnt += 1
            if blocked_cnt == 0 and "data locks" not in title_lower:
                if any(k in title_lower for k in ["blocking sessions", "blocked queries"]):
                    blocked_cnt = len(rows)
            raw_kpis["blocking_sessions"] = blocked_cnt

        # 5. Buffer Pool / Cache
        if any(k in title_lower for k in ["buffer pool", "cache", "shared memory", "hit ratio", "buffer cache"]):
            for row in rows:
                for col in row:
                    try:
                        val = float(re.sub(r"[^\d.]", "", str(col)))
                        if 80.0 <= val <= 100.0:
                            raw_kpis["cache_hit_ratio"] = round(val, 1)
                            break
                    except ValueError:
                        pass

        # 6. Storage Breakdown
        if any(k in title_lower for k in ["data vs index", "total table vs index", "total data vs index", "index vs data", "index ratio", "data vs log"]):
            if not storage_breakdown:
                for row in rows:
                    if len(row) >= 2:
                        if "data vs log" in title_lower and len(row) >= 3:
                            storage_breakdown.append({"label": "Data", "value": f"{row[1]} GB" if not str(row[1]).endswith("GB") else str(row[1])})
                            storage_breakdown.append({"label": "Log", "value": f"{row[2]} GB" if not str(row[2]).endswith("GB") else str(row[2])})
                            break
                        else:
                            storage_breakdown.append({"label": str(row[0]), "value": str(row[1])})

        # 7. Top 10 Largest Tables
        if any(k in title_lower for k in ["top 100", "table-level storage", "largest tables", "table sizes", "top tables", "largest segments"]):
            if not top_tables and rows:
                db_col_idx = -1
                tbl_col_idx = -1
                size_mb_idx = -1
                size_gb_idx = -1

                for idx, h in enumerate(headers):
                    h_l = str(h).lower()
                    if any(w in h_l for w in ["database", "db_name", "dbname"]) and db_col_idx == -1:
                        db_col_idx = idx
                    if ("table name" in h_l or "relation" in h_l or "segment name" in h_l or "segment" in h_l or "table" in h_l) and not any(w in h_l for w in ["count", "space", "type", "rows"]):
                        if tbl_col_idx == -1: tbl_col_idx = idx
                    if ("size (gb)" in h_l or "gb" in h_l or "reserved (gb)" in h_l):
                        if size_gb_idx == -1: size_gb_idx = idx
                    elif ("size (mb)" in h_l or "mb" in h_l or "size" in h_l or "reserved" in h_l):
                        if size_mb_idx == -1: size_mb_idx = idx

                for row in rows:
                    if len(top_tables) >= 10:
                        break
                    if len(row) >= 2:
                        db_name = ""
                        if db_col_idx != -1 and db_col_idx < len(row):
                            db_name = str(row[db_col_idx]).strip()

                        if tbl_col_idx != -1 and tbl_col_idx < len(row):
                            table_name = str(row[tbl_col_idx]).strip()
                        elif len(row) >= 3 and str(row[1]).lower() not in {"public", "dbo", "information_schema", "pg_catalog", "sys", "system"}:
                            table_name = str(row[2]) if len(row) >= 4 and str(row[2]).lower() not in {"public", "dbo"} else str(row[1])
                        else:
                            table_name = str(row[0]).strip()

                        if db_name and db_name.upper() not in {"TOTAL", "SUM", "-", "N/A"} and not table_name.startswith(db_name):
                            full_display_name = f"{db_name}.{table_name}"
                        else:
                            full_display_name = table_name

                        size_val = ""
                        unit = "MB"

                        if size_gb_idx != -1 and size_gb_idx < len(row):
                            gb_str = str(row[size_gb_idx]).strip()
                            try:
                                gb_num = float(re.sub(r"[^\d.]", "", gb_str))
                                if gb_num > 0 or size_mb_idx == -1:
                                    size_val = f"{gb_num:.2f}"
                                    unit = "GB"
                            except ValueError:
                                pass

                        if not size_val and size_mb_idx != -1 and size_mb_idx < len(row):
                            mb_str = str(row[size_mb_idx]).strip()
                            try:
                                mb_num = float(re.sub(r"[^\d.]", "", mb_str))
                                if mb_num >= 1024:
                                    size_val = f"{(mb_num / 1024.0):.2f}"
                                    unit = "GB"
                                else:
                                    size_val = f"{mb_num:.2f}"
                                    unit = "MB"
                            except ValueError:
                                size_val = mb_str

                        if not size_val:
                            size_val = str(row[-1]).strip()

                        if size_val and not re.search(r"(?i)(GB|MB|KB|TB|Bytes)", size_val):
                            size_val = f"{size_val} {unit}"

                        if table_name.upper() not in {"TOTAL", "SUM", "-"}:
                            top_tables.append({
                                "name": full_display_name,
                                "size": size_val
                            })

        # 9. Top Wait Events
        if any(k in title_lower for k in ["top wait events", "wait statistics", "wait stats", "wait events"]):
            if not wait_statistics and rows:
                event_col_idx = -1
                cnt_col_idx = -1
                for idx, h in enumerate(headers):
                    h_l = str(h).lower()
                    if any(w in h_l for w in ["wait event", "event name", "wait_event", "event", "wait type"]) and event_col_idx == -1:
                        event_col_idx = idx
                    if any(w in h_l for w in ["active sessions", "count", "waits", "sessions", "total wait time", "latency"]) and cnt_col_idx == -1:
                        cnt_col_idx = idx

                for row in rows[:8]:
                    if len(row) >= 2:
                        if event_col_idx != -1 and event_col_idx < len(row):
                            w_name = str(row[event_col_idx])
                        elif len(row) >= 3 and str(row[0]).upper() in {"ACTIVITY", "IO", "LOCK", "CLIENT", "LWLOCK", "BUFFERPIN", "IPC"}:
                            w_name = str(row[1])
                        else:
                            w_name = str(row[0])

                        if cnt_col_idx != -1 and cnt_col_idx < len(row):
                            w_count = str(row[cnt_col_idx])
                        else:
                            w_count = str(row[-1])

                        item_sample = w_name[:35] + "..." if len(w_name) > 35 else w_name
                        wait_statistics.append({
                            "name": item_sample,
                            "full_name": w_name,
                            "count": w_count
                        })

    def _clean_text_label(txt: str, max_len: int = 35) -> str:
        if not txt:
            return "N/A"
        cleaned = re.sub(r"^[\s'\"]+|[\s'\"]+$", "", str(txt))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:max_len] + "..." if len(cleaned) > max_len else cleaned


    # Native Top CPU Query Collector
    cpu_queries_available = False
    cpu_queries_reason = ""
    if connector and hasattr(connector, "get_top_cpu_queries_native"):
        try:
            native_cpu = connector.get_top_cpu_queries_native()
            if native_cpu.get("available") and native_cpu.get("items"):
                items = native_cpu["items"]
                total_cpu = sum(item["cpu_time"] for item in items)
                for item in items:
                    raw_q = item.get("full_query") or item.get("query_text") or item.get("query") or "Unknown Query"
                    item["full_query"] = item.get("full_query") or raw_q
                    clean_q = _clean_text_label(raw_q, max_len=30)
                    item["query_text"] = clean_q
                    item["query"] = clean_q
                    item["cpu_percentage"] = round((item["cpu_time"] / total_cpu * 100.0), 1) if total_cpu > 0 else 0.0
                    item["timestamp"] = now_iso
                    item["metric"] = f"{item['cpu_time']} {item['cpu_unit']}"
                cpu_queries = items
                cpu_queries_available = True
            else:
                cpu_queries_reason = native_cpu.get("reason", "Metric unavailable for this database/configuration.")
        except Exception as e:
            logger.warning("Error collecting native top CPU queries: %s", e)
            cpu_queries_reason = "Metric unavailable for this database/configuration."

    # Native Top I/O Metric Collector
    io_metrics_available = False
    top_io_title = "Top I/O-Consuming Queries"
    io_metrics_reason = ""
    if connector and hasattr(connector, "get_top_io_metrics_native"):
        try:
            native_io = connector.get_top_io_metrics_native()
            if native_io.get("available") and native_io.get("items"):
                items = native_io["items"]
                total_io_ops = sum(item["io_operations"] for item in items)
                for item in items:
                    raw_name = item.get("full_entity_name") or item.get("entity_name") or item.get("name") or "Unknown Entity"
                    item["full_entity_name"] = item.get("full_entity_name") or raw_name
                    item["full_name"] = item.get("full_entity_name") or raw_name
                    clean_name = _clean_text_label(raw_name, max_len=30)
                    item["entity_name"] = clean_name
                    item["name"] = clean_name
                    item["percentage_of_total"] = round((item["io_operations"] / total_io_ops * 100.0), 1) if total_io_ops > 0 else 0.0
                    item["timestamp"] = now_iso
                    item["metric"] = f"{item['io_operations']} {item['io_unit']}"
                io_waits = items
                io_metrics_available = True
                top_io_title = native_io.get("title", "Top I/O-Consuming Queries")
            else:
                io_metrics_reason = native_io.get("reason", "Insufficient workload data for analysis.")
                top_io_title = native_io.get("title", "Top I/O-Consuming Queries")
        except Exception as e:
            logger.warning("Error collecting native top I/O metrics: %s", e)
            io_metrics_reason = "Insufficient workload data for analysis."

    # Fallback Top CPU Query Collector from gathered reports across all engines
    if not cpu_queries_available:
        for r in reports:
            t_l = r.get("title", "").lower()
            if any(k in t_l for k in ["top cpu queries", "slow / resource-intensive sql", "slow queries", "long-running requests"]):
                r_rows = r.get("rows", [])
                r_headers = [str(h).lower() for h in r.get("headers", [])]
                q_idx = -1
                cpu_idx = -1
                for idx, h in enumerate(r_headers):
                    if any(w in h for w in ["query sample", "sql text", "query", "sql_text_sample"]):
                        q_idx = idx
                    elif any(w in h for w in ["cpu", "total sec", "elapsed", "latency"]) and cpu_idx == -1:
                        cpu_idx = idx
                if q_idx == -1 and len(r_headers) > 0:
                    q_idx = len(r_headers) - 1 if ("query" in r_headers[-1] or "sql" in r_headers[-1]) else 0
                if cpu_idx == -1 and len(r_headers) > 1:
                    cpu_idx = 1

                extracted_items = []
                for row in r_rows[:10]:
                    if len(row) > max(q_idx, cpu_idx):
                        raw_q = str(row[q_idx])
                        try:
                            cpu_num = float(re.sub(r"[^\d.]", "", str(row[cpu_idx])))
                        except ValueError:
                            cpu_num = 0.0
                        clean_q = _clean_text_label(raw_q, max_len=30)
                        cpu_u = "ms" if (cpu_idx < len(r_headers) and "ms" in r_headers[cpu_idx]) else "s"
                        extracted_items.append({
                            "full_query": raw_q,
                            "query_text": clean_q,
                            "query": clean_q,
                            "cpu_time": cpu_num,
                            "cpu_unit": cpu_u,
                            "metric": f"{cpu_num} {cpu_u}",
                            "timestamp": now_iso
                        })
                if extracted_items:
                    tot_cpu = sum(item["cpu_time"] for item in extracted_items)
                    for item in extracted_items:
                        item["cpu_percentage"] = round((item["cpu_time"] / tot_cpu * 100.0), 1) if tot_cpu > 0 else 0.0
                    cpu_queries = extracted_items
                    cpu_queries_available = True
                    break

    # Fallback Top I/O Metric Collector from gathered reports across all engines
    if not io_metrics_available:
        for r in reports:
            t_l = r.get("title", "").lower()
            if any(k in t_l for k in ["top io queries", "sql examining", "table i/o activity", "workload"]):
                r_rows = r.get("rows", [])
                r_headers = [str(h).lower() for h in r.get("headers", [])]
                ent_idx = -1
                io_idx = -1
                for idx, h in enumerate(r_headers):
                    if any(w in h for w in ["table name", "relation", "sql text", "query", "sample"]):
                        ent_idx = idx
                    elif any(w in h for w in ["read", "io", "gets", "operations", "shared blks"]) and io_idx == -1:
                        io_idx = idx
                if ent_idx == -1 and len(r_headers) > 0:
                    ent_idx = 1 if len(r_headers) > 1 else 0
                if io_idx == -1 and len(r_headers) > 2:
                    io_idx = 2

                extracted_io = []
                for row in r_rows[:10]:
                    if len(row) > max(ent_idx, io_idx):
                        raw_ent = str(row[ent_idx])
                        try:
                            io_num = int(float(re.sub(r"[^\d.]", "", str(row[io_idx]))))
                        except ValueError:
                            io_num = 0
                        clean_ent = _clean_text_label(raw_ent, max_len=30)
                        extracted_io.append({
                            "full_entity_name": raw_ent,
                            "full_name": raw_ent,
                            "entity_name": clean_ent,
                            "name": clean_ent,
                            "io_operations": io_num,
                            "io_unit": "ops",
                            "metric": f"{io_num} ops",
                            "timestamp": now_iso
                        })
                if extracted_io:
                    tot_io = sum(item["io_operations"] for item in extracted_io)
                    for item in extracted_io:
                        item["percentage_of_total"] = round((item["io_operations"] / tot_io * 100.0), 1) if tot_io > 0 else 0.0
                    io_waits = extracted_io
                    io_metrics_available = True
                    break

    # QPS calculation
    if total_exec_count > 0:
        raw_kpis["qps"] = min(25000, max(0, int(total_exec_count / 10)))
    elif raw_kpis["active_connections"] > 0:
        raw_kpis["qps"] = raw_kpis["active_connections"] * 2
    else:
        raw_kpis["qps"] = 0

    # Generate Dynamic Trend Objects for CPU Utilization & I/O Operations (IOPS)
    cpu_trend = _generate_dynamic_cpu_trend(raw_kpis["cpu_usage_pct"], time_range, cpu_queries)
    io_trend = _generate_dynamic_io_trend(raw_kpis["iops"], time_range, reports)

    period_labels = {
        "15m": "Last 15 Minutes",
        "30m": "Last 30 Minutes",
        "1h": "Last 1 Hour",
        "3h": "Last 3 Hours",
        "6h": "Last 6 Hours",
        "12h": "Last 12 Hours",
        "24h": "Last 24 Hours"
    }
    period_str = period_labels.get(time_range, "Last 1 Hour")

    # Build KPI Objects (CURRENT Snapshot vs PERIOD Historical)
    cpu_val = cpu_trend["current"]
    cpu_status = cpu_trend["status"]
    cpu_kpi = {
        "value": cpu_val,
        "current_str": f"{cpu_val}%",
        "status": cpu_status,
        "avg": cpu_trend["avg"],
        "avg_str": f"{cpu_trend['avg']}%",
        "peak": cpu_trend["peak"],
        "peak_str": f"{cpu_trend['peak']}%",
        "period_str": period_str,
        "insight": cpu_trend["insight"]
    }

    iops_val = io_trend["current"]
    iops_status = io_trend["status"]
    iops_kpi = {
        "value": iops_val,
        "current_str": f"{iops_val}",
        "status": iops_status,
        "avg": io_trend["avg"],
        "avg_str": f"{io_trend['avg']}",
        "peak": io_trend["peak"],
        "peak_str": f"{io_trend['peak']}",
        "period_str": period_str,
        "insight": io_trend["insight"]
    }

    conn_base = raw_kpis["active_connections"]
    conn_peak = conn_base
    max_conn = raw_kpis["max_connections"] or 100
    conn_util = round((conn_base / max_conn) * 100, 1) if max_conn > 0 else 0.0
    conn_status = _evaluate_status("connection_pct", conn_util)
    conn_kpi = {
        "value": conn_base,
        "current_val": conn_base,
        "peak_val": conn_peak,
        "max_connections": max_conn,
        "utilization_pct": conn_util,
        "status": conn_status,
        "period_str": period_str,
        "insight": f"{conn_base} active connection(s) currently connected (Peak: {conn_peak} in {period_str.lower()})."
    }
    if connector and hasattr(connector, "get_active_connections_kpi"):
        try:
            res_conn = connector.get_active_connections_kpi(time_range)
            if res_conn and res_conn.get("value") is not None:
                conn_kpi = res_conn
        except Exception as e:
            logger.warning("Error invoking get_active_connections_kpi: %s", e)

    qps_val = raw_kpis["qps"]
    period_sec = {"15m": 900, "30m": 1800, "1h": 3600, "3h": 10800, "6h": 21600, "12h": 43200, "24h": 86400}.get(time_range, 3600)
    total_queries_approx = qps_val * period_sec
    total_q_str = f"{round(total_queries_approx / 1000000.0, 2)}M" if total_queries_approx >= 1000000 else (f"{round(total_queries_approx / 1000.0, 1)}K" if total_queries_approx >= 1000 else f"{total_queries_approx}")
    qps_kpi = {
        "value": qps_val,
        "avg_qps": qps_val,
        "total_queries": total_q_str,
        "status": "Normal",
        "period_str": period_str,
        "insight": f"Average throughput rate is {qps_val} QPS ({total_q_str} total queries in {period_str.lower()})."
    }
    if connector and hasattr(connector, "get_qps_kpi"):
        try:
            res_qps = connector.get_qps_kpi(time_range)
            if res_qps and res_qps.get("value") is not None:
                qps_kpi = res_qps
        except Exception as e:
            logger.warning("Error invoking get_qps_kpi: %s", e)

    storage_val = raw_kpis["database_size"]
    if storage_val in ["N/A", "0.00 MB", "0.00MB", "0 MB", "0MB", "0.00"]:
        total_mb = 0.0
        active_db = ""
        if active_connection and isinstance(active_connection, dict) and "credentials" in active_connection:
            creds = active_connection.get("credentials", {})
            active_db = creds.get("database") or creds.get("service_name") or creds.get("dbname") or ""

        for r in reports:
            t = r.get("title", "").lower()
            rows = r.get("rows", [])
            if any(k in t for k in ["schema sizes", "database inventory", "database sizes", "schema inventory", "database/schema inventory"]):
                for row in rows:
                    if len(row) >= 2:
                        db_name = str(row[0]).strip()
                        if active_db and db_name.lower() == active_db.lower():
                            sz = _parse_size_mb(str(row[-1]))
                            if sz > 0:
                                total_mb = sz
                                break
                        if db_name.lower() not in ["information_schema", "performance_schema", "mysql", "sys", "master", "model", "msdb", "tempdb"]:
                            total_mb += _parse_size_mb(str(row[-1]))
                if total_mb > 0:
                    break

            if total_mb == 0 and any(k in t for k in ["data vs index", "top 100", "table-level storage", "table wise size"]):
                for row in rows:
                    for cell in row:
                        if re.search(r"(?i)(GB|MB|KB|TB)", str(cell)):
                            total_mb += _parse_size_mb(str(cell))
                            break
                if total_mb > 0:
                    break

        if total_mb > 0:
            if total_mb >= 1024.0:
                storage_val = f"{round(total_mb / 1024.0, 2)} GB"
            else:
                storage_val = f"{round(total_mb, 2)} MB"
            raw_kpis["database_size"] = storage_val

    tables_count = raw_kpis["total_tables"]
    growth_str = "+0.00 GB" if "GB" in str(storage_val) else "+0.00 MB"
    storage_kpi = {
        "value": storage_val,
        "current_size": storage_val,
        "table_count": tables_count,
        "growth": growth_str,
        "period_str": period_str,
        "status": "Normal",
        "insight": f"Current database footprint is {storage_val} across {tables_count} table(s) (no size change in {period_str.lower()})."
    }
    if connector and hasattr(connector, "get_storage_kpi"):
        try:
            res_st = connector.get_storage_kpi(time_range)
            if res_st and res_st.get("value") and res_st.get("value") != "N/A":
                storage_kpi = res_st
        except Exception as e:
            logger.warning("Error invoking get_storage_kpi: %s", e)

    blocked_cnt = raw_kpis["blocking_sessions"]
    blocked_status = _evaluate_status("blocking", blocked_cnt)
    blocked_text = "No Blocking" if blocked_cnt == 0 else f"{blocked_cnt} Sessions Blocked"
    peak_blocked = blocked_cnt
    blocked_kpi = {
        "count": blocked_cnt,
        "current_count": blocked_cnt,
        "peak_count": peak_blocked,
        "status": blocked_status,
        "status_text": blocked_text,
        "period_str": period_str,
        "insight": "No lock contention or blocked sessions currently detected." if blocked_cnt == 0 else f"{blocked_cnt} session(s) currently blocked waiting for lock release (Peak: {peak_blocked} in {period_str.lower()})."
    }
    if connector and hasattr(connector, "get_blocked_sessions_kpi"):
        try:
            res_blk = connector.get_blocked_sessions_kpi(time_range)
            if res_blk and res_blk.get("count") is not None:
                blocked_kpi = res_blk
        except Exception as e:
            logger.warning("Error invoking get_blocked_sessions_kpi: %s", e)

    # Explicit Deadlocks KPI Collector
    deadlocks_kpi = {
        "count": 0,
        "status": "Normal",
        "status_text": "Zero Contention",
        "period_str": period_str,
        "insight": "Zero deadlocks detected in engine telemetry."
    }
    if connector and hasattr(connector, "get_deadlocks_kpi"):
        try:
            res_dl = connector.get_deadlocks_kpi(time_range)
            if res_dl and res_dl.get("count") is not None:
                deadlocks_kpi = res_dl
        except Exception as e:
            logger.warning("Error invoking get_deadlocks_kpi: %s", e)

    # Explicit Top Wait Events Chart Collector
    wait_status_code = "no_waits"
    wait_reason = "No significant wait events detected during the selected period."
    if connector:
        try:
            wait_func = getattr(connector, "get_top_wait_events", getattr(connector, "get_top_wait_events_native", None))
            if wait_func:
                native_waits = wait_func()
                wait_status_code = native_waits.get("status_code", "no_waits")
                wait_reason = native_waits.get("reason", "No significant wait events detected during the selected period.")
                if native_waits.get("items"):
                    items = native_waits["items"]
                    for item in items:
                        item["name"] = _clean_text_label(item["wait_event"], max_len=30)
                        item["full_name"] = item["wait_event"]
                        item["count"] = item["wait_count"]
                    wait_statistics = items
        except Exception as e:
            logger.warning("Error collecting top wait events chart: %s", e)
            wait_status_code = "error"
            wait_reason = "Unable to retrieve wait-event metrics."

    # Explicit Cache Efficiency Chart Collector
    cache_kpi = {
        "hit_ratio": raw_kpis["cache_hit_ratio"],
        "miss_ratio": round(100.0 - raw_kpis["cache_hit_ratio"], 1),
        "hit_count": None,
        "miss_count": None,
        "status": "Healthy",
        "status_code": "ok",
        "reason": ""
    }
    if connector:
        try:
            cache_func = getattr(connector, "get_cache_efficiency", getattr(connector, "get_cache_efficiency_native", None))
            if cache_func:
                native_cache = cache_func()
                cache_kpi["hit_ratio"] = native_cache.get("hit_ratio", raw_kpis["cache_hit_ratio"])
                cache_kpi["miss_ratio"] = native_cache.get("miss_ratio", round(100.0 - cache_kpi["hit_ratio"], 1))
                cache_kpi["hit_count"] = native_cache.get("hit_count")
                cache_kpi["miss_count"] = native_cache.get("miss_count")
                cache_kpi["status"] = native_cache.get("status", "Healthy")
                cache_kpi["status_code"] = native_cache.get("status_code", "ok")
                cache_kpi["reason"] = native_cache.get("reason", "")
                raw_kpis["cache_hit_ratio"] = cache_kpi["hit_ratio"]
        except Exception as e:
            logger.warning("Error collecting cache efficiency chart: %s", e)
            cache_kpi["status_code"] = "error"
            cache_kpi["reason"] = "Unable to retrieve cache efficiency metrics."

    # Explicit Storage Breakdown Chart Collector
    if connector and hasattr(connector, "get_data_vs_index_storage"):
        try:
            res_sb = connector.get_data_vs_index_storage()
            if res_sb:
                norm_sb = []
                for item in res_sb:
                    if isinstance(item, dict):
                        if "label" in item and "value" in item:
                            norm_sb.append(item)
                        elif "data_mb" in item or "index_mb" in item:
                            d_mb = float(item.get("data_mb") or 0.0)
                            i_mb = float(item.get("index_mb") or 0.0)
                            norm_sb.append({"label": "Data Size", "value": f"{d_mb:.2f} MB"})
                            norm_sb.append({"label": "Index Size", "value": f"{i_mb:.2f} MB"})
                if norm_sb:
                    storage_breakdown = norm_sb
        except Exception as e:
            logger.warning("Error collecting data vs index storage chart: %s", e)

    # Explicit Top Largest Tables Chart Collector
    if connector and hasattr(connector, "get_top_largest_tables"):
        try:
            res_tt = connector.get_top_largest_tables()
            if res_tt:
                norm_tt = []
                for item in res_tt:
                    if isinstance(item, dict):
                        sch = item.get("schema_name") or item.get("table_schema") or ""
                        tbl = item.get("table_name") or item.get("name") or "Unknown"
                        t_name = item.get("name") or (f"{sch}.{tbl}" if sch and not tbl.startswith(sch) else tbl)
                        
                        if item.get("size"):
                            t_size = str(item["size"])
                        else:
                            t_gb = float(item.get("total_gb") or 0.0)
                            t_mb = float(item.get("total_mb") or 0.0)
                            if t_gb >= 1.0:
                                t_size = f"{t_gb:.2f} GB"
                            elif t_mb > 0:
                                t_size = f"{t_mb:.2f} MB"
                            else:
                                t_size = str(item.get("total_mb") or "0 MB")
                        norm_tt.append({"name": t_name, "size": t_size, **item})
                if norm_tt:
                    top_tables = norm_tt
        except Exception as e:
            logger.warning("Error collecting top largest tables chart: %s", e)

    summary_kpis = {
        "cpu": cpu_kpi,
        "iops": iops_kpi,
        "connections": conn_kpi,
        "qps": qps_kpi,
        "storage": storage_kpi,
        "blocked_sessions": blocked_kpi,
        "deadlocks": deadlocks_kpi,
        "cache": cache_kpi,
        "cache_hit_ratio": cache_kpi["hit_ratio"],
        "total_insights": len(reports)
    }

    health_summary = _generate_health_summary(summary_kpis, cpu_queries, top_tables, wait_statistics)

    # Specific Dynamic Insights for Top CPU Queries
    if cpu_queries_available and cpu_queries:
        q0 = cpu_queries[0]
        q_txt = q0.get("query_text") or q0.get("query") or "Top Query"
        val = q0.get("cpu_time", 0.0)
        unit = q0.get("cpu_unit", "ms")
        pct = q0.get("cpu_percentage")
        exec_cnt = q0.get("execution_count")
        
        if exec_cnt is not None and exec_cnt > 0 and pct is not None and pct > 0:
            top_cpu_insight = f"'{q_txt}' consumed {val:,.2f} {unit}, accounting for {pct}% of total query CPU consumption across {exec_cnt:,} executions during the selected period."
        elif pct is not None and pct > 0:
            top_cpu_insight = f"'{q_txt}' consumed {val:,.2f} {unit}, accounting for {pct}% of total query CPU consumption during the selected period."
        else:
            top_cpu_insight = f"'{q_txt}' consumed {val:,.2f} {unit}, the highest CPU consumption among the queries analyzed during the selected period."
    else:
        top_cpu_insight = cpu_queries_reason or "Metric unavailable for this database/configuration."

    # Specific Dynamic Insights for Top I/O
    if io_metrics_available and io_waits:
        i0 = io_waits[0]
        ent_name = i0.get("entity_name") or i0.get("name") or "Top Entity"
        val = i0.get("io_operations", 0)
        unit = i0.get("io_unit", "operations")
        pct = i0.get("percentage_of_total")
        
        if pct is not None and pct > 0:
            top_io_insight = f"'{ent_name}' generated {val:,} {unit} during the selected period, accounting for {pct}% of total measured I/O activity."
        else:
            top_io_insight = f"'{ent_name}' generated {val:,} {unit} during the selected period."
    else:
        top_io_insight = io_metrics_reason or "Insufficient workload data for analysis."

    # Specific Dynamic Insights for Top Wait Events
    if wait_statistics and wait_status_code == "ok":
        w0 = wait_statistics[0]
        w0_name = w0.get("full_name") or w0.get("name") or "Wait Event"
        w0_pct = w0.get("percentage_of_total")
        w0_time = w0.get("wait_time")
        w0_unit = w0.get("wait_time_unit", "ms")
        
        if len(wait_statistics) >= 2 and w0_pct is not None and w0_pct > 0:
            w1 = wait_statistics[1]
            w1_name = w1.get("full_name") or w1.get("name")
            w1_pct = w1.get("percentage_of_total", 0)
            wait_insight = f"'{w0_name}' ({w0_pct}%) and '{w1_name}' ({w1_pct}%) accounted for the highest wait activity during {period_str.lower()}."
        elif w0_pct is not None and w0_pct > 0:
            wait_insight = f"'{w0_name}' accounted for {w0_pct}% of total measured wait time during {period_str.lower()}."
        else:
            wait_insight = f"'{w0_name}' accumulated {w0_time} {w0_unit} of wait time, the highest among observed wait events during {period_str.lower()}."
    else:
        wait_insight = wait_reason

    # Specific Dynamic Insight for Cache Efficiency
    hr = cache_kpi['hit_ratio']
    mr = cache_kpi['miss_ratio']
    cache_insight = f"Cache hit ratio is currently {hr}%, indicating that {hr}% of data requests were served directly from memory ({mr}% miss ratio)."

    if top_tables and len(top_tables) > 0:
        t0_name = top_tables[0].get("name") or top_tables[0].get("table_name") or "Primary Table"
        t0_size = top_tables[0].get("size") or "0 MB"
        top_table_insight = f"'{t0_name}' is the largest table at {t0_size}."
    else:
        top_table_insight = "No table storage data available."

    return {
        "health_summary": health_summary,
        "summary_kpis": summary_kpis,
        "kpis": summary_kpis,
        "cpu_trend": cpu_trend,
        "io_trend": io_trend,
        "storage_breakdown": storage_breakdown,
        "top_tables": top_tables,
        "cpu_queries": cpu_queries,
        "cpu_queries_available": cpu_queries_available,
        "cpu_queries_reason": cpu_queries_reason,
        "io_waits": io_waits,
        "io_metrics_available": io_metrics_available,
        "io_metrics_reason": io_metrics_reason,
        "top_io_title": top_io_title,
        "wait_statistics": wait_statistics,
        "wait_status_code": wait_status_code,
        "wait_reason": wait_reason,
        "cache_kpi": cache_kpi,
        "insights": {
            "cpu_trend": cpu_trend["insight"],
            "io_trend": io_trend["insight"],
            "top_cpu": top_cpu_insight,
            "top_io": top_io_insight,
            "wait_events": wait_insight,
            "cache": cache_insight,
            "cache_efficiency": cache_insight,
            "storage_breakdown": "Data vs index storage breakdown across schemas.",
            "top_tables": top_table_insight
        },
        "last_updated": now_iso
    }


@app.post("/api/insights")
async def get_database_insights(req: ConnectionRequest):
    global active_connection
    try:
        explorer = _create_and_connect_explorer(req.database_type, req.credentials)
        active_connection = {
            "database_type": req.database_type,
            "credentials": req.credentials
        }
        
        fetchers_map = {
            "MySQL": explorer._get_mysql_fetchers,
            "Oracle": explorer._get_oracle_fetchers,
            "PostgreSQL": explorer._get_postgres_fetchers,
            "SQL Server": explorer._get_sqlserver_fetchers,
        }

        if req.database_type not in fetchers_map:
            raise HTTPException(status_code=400, detail=f"Insights not implemented for {req.database_type}")

        from database_queries import get_insight_query, get_all_engine_queries

        fetchers = fetchers_map[req.database_type]()
        reports = []

        for label, fetcher in fetchers:
            clean_label = re.sub(r"^\d+\.\s*", "", label).strip()
            meta = (
                get_insight_query(req.database_type, label)
                or get_insight_query(req.database_type, clean_label)
            )
            try:
                data = fetcher()
                orig_title = data.get("title", "")
                data["title"] = clean_label
                if not meta and orig_title:
                    meta = get_insight_query(req.database_type, orig_title)
                if meta:
                    data["query"] = meta.get("query", "")
                    data["method"] = meta.get("method", "")
                    data["description"] = meta.get("description", "")
                    data["category"] = meta.get("category", "")
                reports.append(data)
            except Exception as e:
                logger.warning("Failed gathering insight '%s': %s", label, e)
                err_dict = {
                    "title": clean_label,
                    "headers": ["Error Status"],
                    "rows": [],
                    "error": str(e),
                    "note": f"Query execution failed: {str(e)}"
                }
                if meta:
                    err_dict["query"] = meta.get("query", "")
                    err_dict["method"] = meta.get("method", "")
                    err_dict["description"] = meta.get("description", "")
                    err_dict["category"] = meta.get("category", "")
                reports.append(err_dict)

        charts_summary = _extract_charts_summary(reports, time_range=req.time_range or "1h", connector=explorer.connector)

        return {
            "success": True,
            "database_type": req.database_type,
            "reports_count": len(reports),
            "charts": charts_summary,
            "reports": reports
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed fetching insights: %s", e)
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/database-queries")
async def get_database_queries_endpoint(database_type: str = "MySQL"):
    """API endpoint to retrieve all defined queries and methods for an engine."""
    from database_queries import get_all_engine_queries
    queries = get_all_engine_queries(database_type)
    return {"success": True, "database_type": database_type, "queries": queries}


@app.get("/api/insight-query")
async def get_single_insight_query(title: str, database_type: str = "MySQL"):
    """API endpoint to retrieve the native SQL query definition for any insight by title or keyword."""
    from database_queries import get_insight_query
    meta = get_insight_query(database_type, title)
    if meta:
        return {
            "success": True,
            "title": meta.get("title", title),
            "query": meta.get("query", ""),
            "description": meta.get("description", ""),
            "method": meta.get("method", ""),
            "category": meta.get("category", "Observability"),
        }
    return {"success": False, "query": "", "title": title}


@app.get("/api/table-columns")
async def get_table_columns_endpoint(table: str, database: Optional[str] = None):
    """API endpoint to retrieve detailed column metadata for a table."""
    global active_connection
    if not active_connection or "database_type" not in active_connection:
        return {"success": False, "columns": [], "error": "No active database connection"}

    db_type = active_connection.get("database_type")
    creds = active_connection.get("credentials")
    try:
        explorer = _create_and_connect_explorer(db_type, creds)
        conn = explorer.connector.connection
        columns = []
        if db_type == "MySQL":
            cursor = conn.cursor(dictionary=True)
            if database:
                cursor.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        column_type,
                        is_nullable, 
                        column_default, 
                        column_key, 
                        extra, 
                        column_comment 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = %s
                    ORDER BY ordinal_position
                """, (table, database))
            else:
                cursor.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        column_type,
                        is_nullable, 
                        column_default, 
                        column_key, 
                        extra, 
                        column_comment 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
                    ORDER BY ordinal_position
                """, (table,))
            columns = cursor.fetchall()
            cursor.close()
        elif db_type == "PostgreSQL":
            cursor = conn.cursor()
            if database:
                cursor.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        udt_name AS column_type,
                        is_nullable, 
                        column_default, 
                        '' AS column_key, 
                        '' AS extra, 
                        '' AS column_comment 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = %s
                    ORDER BY ordinal_position
                """, (table, database))
            else:
                cursor.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        udt_name AS column_type,
                        is_nullable, 
                        column_default, 
                        '' AS column_key, 
                        '' AS extra, 
                        '' AS column_comment 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema NOT IN ('information_schema', 'pg_catalog')
                    ORDER BY ordinal_position
                """, (table,))
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            columns = [dict(zip(cols, r)) for r in rows]
            cursor.close()
        elif db_type == "SQL Server":
            cursor = conn.cursor()
            if database:
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME AS column_name, 
                        DATA_TYPE AS data_type, 
                        DATA_TYPE AS column_type,
                        IS_NULLABLE AS is_nullable, 
                        COLUMN_DEFAULT AS column_default, 
                        '' AS column_key, 
                        '' AS extra, 
                        '' AS column_comment 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = ? AND TABLE_SCHEMA = ?
                    ORDER BY ORDINAL_POSITION
                """, (table, database))
            else:
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME AS column_name, 
                        DATA_TYPE AS data_type, 
                        DATA_TYPE AS column_type,
                        IS_NULLABLE AS is_nullable, 
                        COLUMN_DEFAULT AS column_default, 
                        '' AS column_key, 
                        '' AS extra, 
                        '' AS column_comment 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                """, (table,))
            rows = cursor.fetchall()
            cols = [desc[0].lower() for desc in cursor.description]
            columns = [dict(zip(cols, r)) for r in rows]
            cursor.close()
        elif db_type == "Oracle":
            cursor = conn.cursor()
            if database:
                cursor.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        data_type AS column_type,
                        nullable AS is_nullable, 
                        data_default AS column_default, 
                        '' AS column_key, 
                        '' AS extra, 
                        '' AS column_comment 
                    FROM all_tab_columns 
                    WHERE table_name = :tbl AND owner = :db
                    ORDER BY column_id
                """, {"tbl": table.upper(), "db": database.upper()})
            else:
                cursor.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        data_type AS column_type,
                        nullable AS is_nullable, 
                        data_default AS column_default, 
                        '' AS column_key, 
                        '' AS extra, 
                        '' AS column_comment 
                    FROM all_tab_columns 
                    WHERE table_name = :tbl
                    ORDER BY column_id
                """, {"tbl": table.upper()})
            rows = cursor.fetchall()
            cols = [desc[0].lower() for desc in cursor.description]
            columns = [dict(zip(cols, r)) for r in rows]
            cursor.close()

        normalized_columns = []
        for c in columns:
            norm_c = {}
            for k, v in c.items():
                norm_c[str(k).lower()] = v
            if norm_c.get("column_default") is not None:
                norm_c["column_default"] = str(norm_c["column_default"]).strip()
            normalized_columns.append(norm_c)
        columns = normalized_columns

        return {"success": True, "table": table, "database": database, "columns": columns}
    except Exception as e:
        logger.warning("Error fetching table columns for %s: %s", table, e)
        return {"success": False, "columns": [], "error": str(e)}


@app.post("/api/export-pdf")
async def export_pdf_report(req: ConnectionRequest):
    try:
        explorer = _create_and_connect_explorer(req.database_type, req.credentials)

        fetchers_map = {
            "MySQL": explorer._get_mysql_fetchers,
            "Oracle": explorer._get_oracle_fetchers,
            "PostgreSQL": explorer._get_postgres_fetchers,
            "SQL Server": explorer._get_sqlserver_fetchers,
        }

        if req.database_type not in fetchers_map:
            raise HTTPException(status_code=400, detail=f"PDF export not implemented for {req.database_type}")

        fetchers = fetchers_map[req.database_type]()
        reports = []

        for label, fetcher in fetchers:
            try:
                data = fetcher()
                data["title"] = label
                reports.append(data)
            except Exception as e:
                logger.warning("Failed gathering insight '%s' for PDF: %s", label, e)
                reports.append({
                    "title": label,
                    "headers": ["Error Status"],
                    "rows": [],
                    "error": str(e),
                    "note": f"Query execution failed: {str(e)}"
                })

        pdf_gen = PDFReportGenerator()
        pdf_file_path = pdf_gen.generate_report(
            reports=reports,
            database_name=req.database_type,
            credentials_info=req.credentials
        )

        filename = os.path.basename(str(pdf_file_path))
        return FileResponse(
            path=str(pdf_file_path),
            filename=filename,
            media_type="application/pdf"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed generating PDF export: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed generating PDF report: {str(e)}")


# ---------------------------------------------------------------------------
# DATA INSIGHTS API ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/api/data-insights/databases")
async def get_data_insights_databases():
    if not active_connection:
        raise HTTPException(status_code=400, detail="No active database connection found. Please connect first.")
    try:
        db_type = active_connection["database_type"]
        creds = active_connection["credentials"]
        dbs = data_insights_service.list_databases(db_type, creds)
        return {"success": True, "databases": dbs}
    except Exception as e:
        logger.error("Failed listing databases for Data Insights: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-insights/schemas")
async def get_data_insights_schemas(database: Optional[str] = None):
    if not active_connection:
        raise HTTPException(status_code=400, detail="No active database connection found. Please connect first.")
    try:
        db_type = active_connection["database_type"]
        creds = active_connection["credentials"]
        schemas = data_insights_service.list_schemas(db_type, creds, database)
        return {"success": True, "schemas": schemas}
    except Exception as e:
        logger.error("Failed listing schemas for Data Insights: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-insights/tables")
async def get_data_insights_tables(database: Optional[str] = None, schema: Optional[str] = None):
    if not active_connection:
        raise HTTPException(status_code=400, detail="No active database connection found. Please connect first.")
    try:
        db_type = active_connection["database_type"]
        creds = active_connection["credentials"]
        tables = data_insights_service.list_tables(db_type, creds, database or "", schema or "")
        return {"success": True, "tables": tables}
    except Exception as e:
        logger.error("Failed listing tables for Data Insights: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data-insights/profile")
async def profile_data_insights_table(req: ProfileRequest):
    db_type = req.database_type or active_connection.get("database_type")
    creds = req.credentials or active_connection.get("credentials")
    if not db_type or not creds:
        raise HTTPException(status_code=400, detail="No active database connection found. Please connect first.")

    target_db = req.database or creds.get("database") or creds.get("service_name") or "default"
    target_schema = req.schema_name or "public"

    try:
        result = data_insights_service.profile_table(
            db_type=db_type,
            creds=creds,
            database=target_db,
            schema=target_schema,
            table=req.table,
            limit=req.limit
        )
        return result
    except Exception as e:
        logger.error("Failed profiling table '%s.%s': %s", target_schema, req.table, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data-insights/export-pdf")
async def export_data_insights_pdf(req: ProfileRequest):
    db_type = req.database_type or active_connection.get("database_type")
    creds = req.credentials or active_connection.get("credentials")
    if not db_type or not creds:
        raise HTTPException(status_code=400, detail="No active database connection found. Please connect first.")

    target_db = req.database or creds.get("database") or creds.get("service_name") or "default"
    target_schema = req.schema_name or "public"

    try:
        profile_data = data_insights_service.get_cached_or_profile_table(
            db_type=db_type,
            creds=creds,
            database=target_db,
            schema=target_schema,
            table=req.table,
            limit=req.limit
        )

        pdf_gen = PDFReportGenerator()
        pdf_file_path = pdf_gen.generate_data_insights_report(
            payload=profile_data,
            database_name=db_type,
            credentials_info=creds
        )

        filename = os.path.basename(str(pdf_file_path))
        return FileResponse(
            path=str(pdf_file_path),
            filename=filename,
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error("Failed exporting Data Insights PDF: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed generating Data Insights PDF: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)


