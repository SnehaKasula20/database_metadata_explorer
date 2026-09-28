from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseDatabaseConnector(ABC):

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials
        self.connection = None

    @abstractmethod
    def connect(self) -> None:
        """Create database connection."""
        pass

    @abstractmethod
    def get_schemas(self) -> List[str]:
        """Return available schemas."""
        pass

    @abstractmethod
    def get_tables(self, schema_name: str) -> List[str]:
        """Return tables from schema."""
        pass

    @abstractmethod
    def get_data_dictionary(
        self,
        schema_name: str,
        table_name: str
    ) -> List[Dict[str, Any]]:
        """Return normalized table metadata."""
        pass

    @abstractmethod
    def get_sample_data(
        self,
        schema_name: str,
        table_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return a small preview of table rows."""
        pass

    @abstractmethod
    def get_jdbc_url(self) -> str:
        """Return JDBC connection URL."""
        pass

    @abstractmethod
    def get_jdbc_driver(self) -> str:
        """Return JDBC driver class."""
        pass

    @abstractmethod
    def get_jdbc_properties(self) -> Dict[str, str]:
        """Return JDBC properties."""
        pass

    def close(self) -> None:
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass

    # =========================================================================
    # EXPLICIT DASHBOARD KPI METHODS
    # =========================================================================

    def get_cpu_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Returns CPU Utilization KPI object."""
        return {
            "value": 0.0,
            "current_str": "0.0%",
            "status": "Normal",
            "avg": 0.0,
            "avg_str": "0.0%",
            "peak": 0.0,
            "peak_str": "0.0%",
            "period_str": "Last 1 Hour",
            "insight": "CPU utilization metric unavailable."
        }

    def get_iops_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Returns I/O Operations (IOPS) KPI object."""
        return {
            "value": 0,
            "current_str": "0",
            "status": "Healthy",
            "avg": 0,
            "avg_str": "0",
            "peak": 0,
            "peak_str": "0",
            "period_str": "Last 1 Hour",
            "insight": "I/O operations metric unavailable."
        }

    def get_active_connections_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Returns Active Connections KPI object."""
        return {
            "value": 0,
            "current_val": 0,
            "peak_val": 0,
            "max_connections": 100,
            "utilization_pct": 0.0,
            "status": "Normal",
            "period_str": "Last 1 Hour",
            "insight": "0 active connection(s) currently connected."
        }

    def get_qps_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Returns Throughput (QPS) KPI object."""
        return {
            "value": 0,
            "avg_qps": 0,
            "total_queries": "0",
            "status": "Normal",
            "period_str": "Last 1 Hour",
            "insight": "Average throughput rate is 0 QPS."
        }

    def get_storage_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Returns Database Storage Footprint KPI object."""
        return {
            "value": "N/A",
            "current_size": "N/A",
            "table_count": 0,
            "growth": "+0.00 MB",
            "period_str": "Last 1 Hour",
            "status": "Normal",
            "insight": "Storage footprint metric unavailable."
        }

    def get_blocked_sessions_kpi(self, time_range: str = "1h") -> Dict[str, Any]:
        """Returns Blocked Sessions KPI object."""
        return {
            "count": 0,
            "current_count": 0,
            "peak_count": 0,
            "status": "Normal",
            "status_text": "No Blocking",
            "period_str": "Last 1 Hour",
            "insight": "No lock contention or blocked sessions currently detected."
        }
