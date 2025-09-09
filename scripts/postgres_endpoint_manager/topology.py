from dataclasses import dataclass
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class Topology:
    primary_ip: Optional[str]
    primary_name: Optional[str]
    standby_ips: List[str]


class TopologyVerifier:
    def __init__(self, checker, max_workers: int = 3):
        self.checker = checker
        self.max_workers = max_workers

    def verify(self, nodes: List[Tuple[str, str]]) -> Topology:
        primary_ip = None
        primary_name = None
        standby_ips: List[str] = []
        primary_ips_found: List[str] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_node = {executor.submit(self.checker.is_in_recovery, ip, 5432, None, None, None): (ip, name) for ip, name in nodes}
            for future in as_completed(future_to_node):
                ip, name = future_to_node[future]
                try:
                    res = future.result()
                except Exception:
                    # treat as unreachable/unknown
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
