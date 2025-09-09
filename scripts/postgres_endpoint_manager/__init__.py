from .logging_ import StructuredFormatter, get_logger
from .exceptions import EndpointManagerError
from .utils import retry_with_backoff

from .orchestrator import Orchestrator


def setup_logging(name: str = __name__):
    """Compatibility shim that returns a configured structured logger."""
    return get_logger(name)


# Initialize module-level logger
logger = setup_logging(__name__)


class PostgreSQLEndpointManager:
    """Compatibility wrapper that delegates to the package Orchestrator.

    This preserves the old class name for any external users while keeping
    execution centralized in `scripts.postgres_endpoint_manager.orchestrator`.
    """
    def __init__(self, *args, **kwargs):
        # Instantiate orchestrator with any provided deps if passed through kwargs
        self._orch = Orchestrator(**{k: v for k, v in kwargs.items() if k in ()})

    def check_k8s_environment(self) -> bool:
        try:
            return bool(self._orch.kube and self._orch.kube.is_in_cluster())
        except Exception:
            return False

    def get_nodes_from_environment(self):
        return self._orch.cfg.pg_nodes and __import__('scripts.postgres_endpoint_manager.utils', fromlist=['parse_nodes']).parse_nodes(self._orch.cfg.pg_nodes)

    def create_topology_signature(self, topology: dict) -> str:
        from .utils import make_signature
        return make_signature(topology.get('primary_ip'), topology.get('standby_ips', []))

    def verify_topology(self, nodes):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        primary_ip = None
        primary_name = None
        standby_ips = []
        primary_ips_found = []

        with ThreadPoolExecutor(max_workers=self._orch.cfg.max_workers) as executor:
            future_to_node = {executor.submit(self.check_postgres_node, ip, name): (ip, name) for ip, name in nodes}
            for future in as_completed(future_to_node):
                ip, name = future_to_node[future]
                try:
                    res = future.result()
                except Exception:
                    continue
                if res is True or res == 'standby':
                    standby_ips.append(ip)
                elif res is False or res == 'primary':
                    primary_ips_found.append(ip)
                    primary_ip = ip
                    primary_name = name

        if len(primary_ips_found) > 1:
            primary_ip = None
            primary_name = None

        return {'primary_ip': primary_ip, 'standby_ips': sorted(standby_ips)}

    def log_info(self, msg: str, extra: dict = None):
        rec = self.__class__._make_log_record(self, 'INFO', msg, extra)
        logger.handle(rec)

    def log_error(self, msg: str, extra: dict = None):
        rec = self.__class__._make_log_record(self, 'ERROR', msg, extra)
        logger.handle(rec)

    @staticmethod
    def _make_log_record(self, level: str, msg: str, extra: dict = None):
        import logging
        record = logging.LogRecord(
            name=logger.name, level=getattr(logging, level), pathname='', lineno=0,
            msg=msg, args=(), exc_info=None
        )
        record.extra_fields = extra or {}
        return record

    def update_endpoint(self, service_name: str, target_ips, description: str, topology_signature: str) -> bool:
        return self._orch.updater.update(service_name, target_ips, topology_signature)

    def check_postgres_node(self, ip: str, name: str):
        import socket

        cfg = getattr(self._orch, 'cfg', None)
        port = getattr(cfg, 'pg_port', None) or 5432
        tcp_timeout = getattr(cfg, 'tcp_connect_timeout', None) or 1.0

        # Quick TCP pre-check to avoid long DB connect timeouts for unreachable hosts
        try:
            with socket.create_connection((ip, int(port)), timeout=float(tcp_timeout)):
                pass
        except Exception:
            # Unreachable at TCP level, treat as unknown
            return None

        try:
            # Pass configured DB credentials and connection options through to the checker
            res = self._orch.checker.is_in_recovery(
                host=ip,
                port=int(port),
                user=getattr(cfg, 'pg_user', None),
                password=getattr(cfg, 'pg_password', None),
                dbname=getattr(cfg, 'pg_database', None),
                connect_timeout=getattr(cfg, 'db_connect_timeout', None) or getattr(cfg, 'connect_timeout', None) or 5,
                sslmode=getattr(cfg, 'pg_sslmode', None)
            )
        except Exception:
            # Checker had an error; return unknown so verification can continue with other nodes
            return None

        if res is True or res == 'standby':
            return 'standby'
        if res is False or res == 'primary':
            return 'primary'
        return None

    def run(self):
        nodes = self.get_nodes_from_environment() or []
        if not nodes:
            try:
                stored = self._orch.kube.get_annotation(self._orch.cfg.rw_service, 'postgres.discovery/last-topology')
            except Exception:
                stored = None
            if stored:
                primary_ip = None
                standby_ips = []
                for part in [p.strip() for p in (stored or '').split(';') if p.strip()]:
                    if part.startswith('primary:'):
                        primary_ip = part.split(':', 1)[1] or None
                    elif part.startswith('standbys:'):
                        s = part.split(':', 1)[1].strip()
                        standby_ips = [ip.strip() for ip in s.split(',') if ip.strip()]
                nodes = []
                if primary_ip:
                    nodes.append((primary_ip, f"pg-{primary_ip.replace('.', '-') }"))
                for ip in standby_ips:
                    nodes.append((ip, f"pg-{ip.replace('.', '-') }"))

        if not nodes:
            logger.error('No PostgreSQL nodes configured')
            return False

        topology = self.verify_topology(nodes)
        if not topology.get('primary_ip'):
            logger.error('No primary found during verification')
            return False

        signature = self.create_topology_signature({'primary_ip': topology.get('primary_ip'), 'standby_ips': topology.get('standby_ips', [])})
        try:
            stored_sig = self._orch.kube.get_annotation(self._orch.cfg.rw_service, 'postgres.discovery/last-topology')
        except Exception:
            stored_sig = None

        if stored_sig and stored_sig == signature:
            logger.info('Topology unchanged; skipping updates')
            return True

        rw_ok = self.update_endpoint(self._orch.cfg.rw_service, [topology.get('primary_ip')], '', signature)
        ro_ok = self.update_endpoint(self._orch.cfg.ro_service, topology.get('standby_ips', []), '', signature)
        return bool(rw_ok and ro_ok)
