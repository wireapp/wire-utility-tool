import time
import random
from typing import Callable, List, Tuple, Optional


def retry_with_backoff(attempts: int = 3, delay: float = 0.2):
    """Simple retry decorator with exponential backoff and jitter."""
    def decorator(fn: Callable):
        def wrapped(*args, **kwargs):
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    if i == attempts - 1:
                        raise
                    sleep_time = delay * (2 ** i) + random.random() * 0.1
                    time.sleep(sleep_time)
        return wrapped
    return decorator


def parse_nodes(pg_nodes: str) -> List[Tuple[str, str]]:
    """Parse a comma-separated PG_NODES string into list of (ip, name).

    Example: '10.0.0.1,10.0.0.2' -> [('10.0.0.1','pg-10-0-0-1'), ...]
    """
    nodes = []
    if not pg_nodes:
        return nodes
    for ip in pg_nodes.split(','):
        ip = ip.strip()
        if not ip:
            continue
        name = f"pg-{ip.replace('.', '-') }"
        nodes.append((ip, name))
    return nodes


def make_signature(primary_ip: Optional[str], standby_ips: List[str]) -> str:
    standby_list = ','.join(sorted(standby_ips)) if standby_ips else ''
    return f"primary:{primary_ip};standbys:{standby_list}"
