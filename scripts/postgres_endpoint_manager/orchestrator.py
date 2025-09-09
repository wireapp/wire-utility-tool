from .config import load_from_env
from .logging_ import get_logger
from .kube import KubeClient
from .db import PostgresChecker
from .topology import TopologyVerifier
from .updater import EndpointUpdater
from .utils import parse_nodes, make_signature
from typing import Optional

class Orchestrator:
    def __init__(self, cfg=None, kube=None, checker=None, updater=None, logger=None):
        self.cfg = cfg or load_from_env()
        self.logger = logger or get_logger('pg-endpoint-manager')
        self.kube = kube or KubeClient(self.cfg.namespace)
        self.checker = checker or PostgresChecker(connect_timeout=self.cfg.pg_connect_timeout)
        self.updater = updater or EndpointUpdater(self.kube)

    def run(self) -> bool:
        # 1. discover nodes from env or stored annotation
        nodes = parse_nodes(self.cfg.pg_nodes)
        if not nodes:
            # try stored topology
            try:
                stored = self.kube.get_annotation(self.cfg.rw_service, 'postgres.discovery/last-topology')
            except Exception:
                stored = None
            if stored:
                # parse stored topology - simple parser: primary:IP;standbys:IP,IP
                primary_ip = None
                standby_ips = []
                for part in [p.strip() for p in (stored or '').split(';') if p.strip()]:
                    if part.startswith('primary:'):
                        primary_ip = part.split(':',1)[1] or None
                    elif part.startswith('standbys:'):
                        s = part.split(':',1)[1].strip()
                        standby_ips = [ip.strip() for ip in s.split(',') if ip.strip()]
                nodes = []
                if primary_ip:
                    nodes.append((primary_ip, f"pg-{primary_ip.replace('.', '-') }"))
                for ip in standby_ips:
                    nodes.append((ip, f"pg-{ip.replace('.', '-') }"))

        if not nodes:
            self.logger.error('No PostgreSQL nodes configured')
            return False

        # 2. verify topology
        verifier = TopologyVerifier(self.checker, max_workers=self.cfg.max_workers)
        topology = verifier.verify(nodes)
        if not topology.primary_ip:
            self.logger.error('No primary found during verification')
            return False

        # 3. create signature and compare then update
        signature = make_signature(topology.primary_ip, topology.standby_ips)
        try:
            stored_sig = self.kube.get_annotation(self.cfg.rw_service, 'postgres.discovery/last-topology')
        except Exception:
            stored_sig = None

        if stored_sig and stored_sig == signature:
            self.logger.info('Topology unchanged; skipping updates')
            return True

        rw_ok = self.updater.update(self.cfg.rw_service, [topology.primary_ip], signature)
        ro_ok = self.updater.update(self.cfg.ro_service, topology.standby_ips, signature)
        return bool(rw_ok and ro_ok)
