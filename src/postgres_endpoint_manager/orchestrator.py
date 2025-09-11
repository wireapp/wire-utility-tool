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
        # Fail fast if psycopg is not available in the runtime image
        if not getattr(self.checker, 'psycopg', None):
            self.logger.error('psycopg (PostgreSQL driver) not available in runtime image')
            raise Exception('psycopg is required in the runtime image')

    def run(self) -> bool:
        # discover nodes from env or stored annotation
        nodes = parse_nodes(self.cfg.pg_nodes)
        self.logger.info("Discovered nodes from PG_NODES", raw_nodes=self.cfg.pg_nodes, parsed_count=len(nodes) if nodes else 0)
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

        # verify topology
        self.logger.info("Starting topology verification", node_count=len(nodes), nodes=nodes)
        verifier = TopologyVerifier(self.checker, max_workers=self.cfg.max_workers, cfg=self.cfg)
        topology = verifier.verify(nodes)
        self.logger.info("Topology verification completed",
                        primary=topology.primary_ip,
                        standbys=topology.standby_ips,
                        topology_valid=bool(topology.primary_ip))

        if not topology.primary_ip:
            self.logger.error('No primary found during verification')
            return False

        # create signature and compare then update
        signature = make_signature(topology.primary_ip, topology.standby_ips)
        self.logger.info("Created topology signature", signature=signature)

        try:
            stored_sig = self.kube.get_annotation(self.cfg.rw_service, 'postgres.discovery/last-topology')
            self.logger.info("Retrieved stored signature", stored_signature=stored_sig)
        except Exception as e:
            self.logger.error("Failed to retrieve stored signature", error=str(e), error_type=type(e).__name__)
            stored_sig = None

        if stored_sig and stored_sig == signature:
            self.logger.info(
                'Topology unchanged; skipping updates',
                computed_signature=signature,
                stored_signature=stored_sig,
                topology={'primary': topology.primary_ip, 'standbys': topology.standby_ips},
            )
            return True

        self.logger.info("Updating endpoints",
                        rw_service=self.cfg.rw_service,
                        rw_targets=[topology.primary_ip],
                        ro_service=self.cfg.ro_service,
                        ro_targets=topology.standby_ips,
                        signature=signature)

        rw_ok = self.updater.update(self.cfg.rw_service, [topology.primary_ip], signature)
        ro_ok = self.updater.update(self.cfg.ro_service, topology.standby_ips, signature)

        if rw_ok and ro_ok:
            self.logger.info("All endpoints updated successfully",
                           rw_service=self.cfg.rw_service,
                           ro_service=self.cfg.ro_service,
                           signature=signature)

        if not (rw_ok and ro_ok):
            self.logger.error(
                'Failed to apply endpoint updates',
                rw_update_ok=bool(rw_ok),
                ro_update_ok=bool(ro_ok),
                computed_signature=signature,
                topology={'primary': topology.primary_ip, 'standbys': topology.standby_ips},
            )
        return bool(rw_ok and ro_ok)
