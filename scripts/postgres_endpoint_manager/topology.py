from dataclasses import dataclass
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class Topology:
    primary_ip: Optional[str]
    primary_name: Optional[str]
    standby_ips: List[str]


class TopologyVerifier:
    def __init__(self, checker, max_workers: int = 3, cfg=None):
        self.checker = checker
        self.max_workers = max_workers
        self.cfg = cfg

    def verify(self, nodes: List[Tuple[str, str]]) -> Topology:
        primary_ip = None
        primary_name = None
        standby_ips: List[str] = []
        primary_ips_found: List[str] = []

        # Use configured DB credentials (if available) when calling the checker so
        # authentication and sslmode behave like the monolith.
        user = getattr(self.cfg, 'pg_user', None) if self.cfg is not None else None
        password = getattr(self.cfg, 'pg_password', None) if self.cfg is not None else None
        dbname = getattr(self.cfg, 'pg_database', None) if self.cfg is not None else None
        sslmode = getattr(self.cfg, 'pg_sslmode', None) if self.cfg is not None else None

        timeout = (getattr(self.cfg, 'pg_connect_timeout', None) or 5) + 5
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_node = {executor.submit(self.checker.is_in_recovery, ip, 5432, user, password, dbname, sslmode): (ip, name) for ip, name in nodes}
            for future in as_completed(future_to_node):
                ip, name = future_to_node[future]
                try:
                    res = future.result(timeout=timeout)
                except Exception:
                    # treat as unreachable/unknown
                    # optional: log timeout/exception at higher level
                    continue
                if res is True:
                    # in recovery -> standby
                    standby_ips.append(ip)
                elif res is False:
                    primary_ips_found.append(ip)
                    primary_ip = ip
                    primary_name = name

        # If multiple primaries detected, treat as ambiguous -> clear primary
        if len(primary_ips_found) > 1:
            primary_ip = None
            primary_name = None

        return Topology(primary_ip=primary_ip, primary_name=primary_name, standby_ips=sorted(standby_ips))
