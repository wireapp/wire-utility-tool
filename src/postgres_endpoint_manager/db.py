from typing import Optional
from .exceptions import EndpointManagerError
from .utils import retry_with_backoff


class PostgresChecker:
    """Encapsulate psycopg checks. psycopg_module may be injected for tests."""
    def __init__(self, connect_timeout: int = 5, psycopg_module=None):
        self.connect_timeout = connect_timeout
        # Allow optional injection for tests; if not provided, try to import psycopg
        if psycopg_module is not None:
            self.psycopg = psycopg_module
        else:
            try:
                import psycopg
                self.psycopg = psycopg
            except Exception:
                # leave as None; callers will get EndpointManagerError when used
                self.psycopg = None

    @retry_with_backoff()
    def is_in_recovery(self, host: str, port: int, user: str, password: str, dbname: str, sslmode: Optional[str] = None) -> Optional[bool]:
        if not self.psycopg:
            raise EndpointManagerError('psycopg not available')
        conn_kwargs = dict(host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=self.connect_timeout)
        if sslmode:
            conn_kwargs['sslmode'] = sslmode
        conn = self.psycopg.connect(**conn_kwargs)
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_is_in_recovery();')
                row = cur.fetchone()
            return row[0] if row is not None else None
        finally:
            try:
                conn.close()
            except Exception:
                pass
