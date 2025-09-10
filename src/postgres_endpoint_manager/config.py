from dataclasses import dataclass
import os
from typing import Optional

@dataclass
class Config:
    namespace: str
    rw_service: str
    ro_service: str
    pg_nodes: str
    pg_user: str
    pg_password: str
    pg_database: str
    pg_connect_timeout: int
    pg_port: int
    pg_sslmode: str
    tcp_connect_timeout: float
    max_workers: int


def load_from_env() -> Config:
    """Load configuration from environment variables with sensible defaults."""
    chart = os.environ.get('CHART_NAME', os.environ.get('HELM_RELEASE', 'postgres-external'))
    return Config(
        namespace=os.environ.get('NAMESPACE') or os.environ.get('DEFAULT_NAMESPACE', 'default'),
        rw_service=os.environ.get('RW_SERVICE', f'{chart}-rw'),
        ro_service=os.environ.get('RO_SERVICE', f'{chart}-ro'),
        pg_nodes=os.environ.get('PG_NODES', ''),
        pg_user=os.environ.get('PGUSER', 'repmgr'),
        pg_password=os.environ.get('PGPASSWORD', 'securepassword'),
        pg_database=os.environ.get('PGDATABASE', 'repmgr'),
    pg_connect_timeout=int(os.environ.get('PGCONNECT_TIMEOUT', '5')),
    # Optional additional settings used by the package
    pg_port=int(os.environ.get('PGPORT', os.environ.get('PG_PORT', '5432'))),
    pg_sslmode=os.environ.get('PGSSLMODE', ''),
    tcp_connect_timeout=float(os.environ.get('TCP_CONNECT_TIMEOUT', '1.0')),
        max_workers=int(os.environ.get('MAX_WORKERS', '3')),
    )
