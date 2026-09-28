from __future__ import annotations

class DummySparkSession:
    """Lightweight stub replacing PySpark SparkSession for pure Pandas execution."""
    def stop(self):
        pass

class SparkSessionManager:
    @staticmethod
    def create():
        return DummySparkSession()
