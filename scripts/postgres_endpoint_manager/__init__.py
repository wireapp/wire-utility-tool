import os
from .logging_ import get_logger
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
        logger.info("Parsing PostgreSQL nodes from environment", raw_nodes=self._orch.cfg.pg_nodes)
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
                    # Log future exception so we see failed node checks
                    try:
                        exc = future.exception()
                    except Exception:
                        exc = None
                    logger.error(
                        "Node check failed (future exception)",
                        node_name=name,
                        node_ip=ip,
                        error=str(exc),
                        error_type=type(exc).__name__ if exc else None,
                    )
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

    def update_endpoint(self, service_name: str, target_ips, description: str, topology_signature: str) -> bool:
        return self._orch.updater.update(service_name, target_ips, topology_signature)

    def check_postgres_node(self, ip: str, name: str):
        import socket

        cfg = getattr(self._orch, 'cfg', None)
        port = getattr(cfg, 'pg_port', None) or 5432
        tcp_timeout = getattr(cfg, 'tcp_connect_timeout', None) or 1.0

        # Log TCP connection attempt
        logger.info(
            "Attempting TCP connectivity check",
            node_name=name,
            node_ip=ip,
            connect_port=int(port),
            timeout=tcp_timeout,
        )

        try:
            with socket.create_connection((ip, int(port)), timeout=float(tcp_timeout)):
                pass
            logger.info(
                "TCP connectivity check passed",
                node_name=name,
                node_ip=ip,
                port=int(port),
                timeout=tcp_timeout,
            )
        except Exception as e:
            # Unreachable at TCP level, treat as unknown and log the connectivity failure
            logger.error(
                "TCP connectivity check failed",
                node_name=name,
                node_ip=ip,
                status="DOWN",
                connectivity_check="tcp_connect",
                error=str(e),
                timeout=tcp_timeout,
            )
            return None

        try:
            # Log planned (non-secret) connection parameters for debugging (structured kw-only)
            logger.info(
                "Attempting DB driver connect",
                connect_host=ip,
                connect_port=int(port),
                connect_timeout=getattr(cfg, 'pg_connect_timeout', None),
            )

            # Pass configured DB credentials and connection options through to the checker
            res = self._orch.checker.is_in_recovery(
                ip,
                int(port),
                getattr(cfg, 'pg_user', None),
                getattr(cfg, 'pg_password', None),
                getattr(cfg, 'pg_database', None),
                getattr(cfg, 'pg_sslmode', None)
            )
        except Exception:
            # Checker had an error; log it and return unknown so verification can continue
            import traceback as _tb
            logger.error(
                "DB checker failed",
                node_name=name,
                node_ip=ip,
                error=_tb.format_exc(),
            )
            return None

        if res is True or res == 'standby':
            return 'standby'
        if res is False or res == 'primary':
            return 'primary'
        return None

    def run(self):
        # Always log entry to run method with env diagnostics
        logger.info("PostgreSQL Endpoint Manager run() started",
                   log_level_env=os.getenv('LOG_LEVEL', 'NOT_SET'),
                   pg_nodes_env=os.getenv('PG_NODES', 'NOT_SET'))

        nodes = self.get_nodes_from_environment() or []
        # Log discovered nodes so we always see what will be checked
        cfg = getattr(self._orch, 'cfg', None)
        logger.info(
            "Nodes discovered from environment",
            pg_nodes=getattr(cfg, 'pg_nodes', None),
            total_nodes=len(nodes),
            nodes=nodes,
        )
        if not nodes:
            try:
                # Log attempt to fetch stored topology annotation from kube
                logger.info("Kube: fetching stored topology annotation", service=self._orch.cfg.rw_service, annotation='postgres.discovery/last-topology')
                stored = self._orch.kube.get_annotation(self._orch.cfg.rw_service, 'postgres.discovery/last-topology')
                logger.info("Kube: fetched annotation", service=self._orch.cfg.rw_service, stored_signature=stored)
            except Exception as e:
                logger.error("Kube: failed to fetch stored topology annotation", service=getattr(self._orch.cfg, 'rw_service', None), error=str(e), error_type=type(e).__name__)
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

        logger.info("Starting topology verification", node_count=len(nodes))
        topology = self.verify_topology(nodes)
        logger.info("Topology verification completed", topology=topology)

        if not topology.get('primary_ip'):
            logger.error('No primary found during verification')
            return False

        signature = self.create_topology_signature({'primary_ip': topology.get('primary_ip'), 'standby_ips': topology.get('standby_ips', [])})
        logger.info("Computed topology signature", signature=signature)
        try:
            stored_sig = self._orch.kube.get_annotation(self._orch.cfg.rw_service, 'postgres.discovery/last-topology')
            logger.info("Kube: fetched annotation before update", service=self._orch.cfg.rw_service, stored_signature=stored_sig)
        except Exception as e:
            logger.error("Kube: failed to fetch stored topology annotation before update", service=getattr(self._orch.cfg, 'rw_service', None), error=str(e), error_type=type(e).__name__)
            stored_sig = None

        if stored_sig and stored_sig == signature:
            logger.info('Topology unchanged; skipping updates', computed_signature=signature, stored_signature=stored_sig, topology=topology)
            return True

        # Attempt endpoint updates and log kube client results
        rw_ok = self.update_endpoint(self._orch.cfg.rw_service, [topology.get('primary_ip')], '', signature)
        ro_ok = self.update_endpoint(self._orch.cfg.ro_service, topology.get('standby_ips', []), '', signature)

        logger.info(
            "Kube: endpoint update results",
            rw_service=getattr(self._orch.cfg, 'rw_service', None),
            ro_service=getattr(self._orch.cfg, 'ro_service', None),
            rw_ok=bool(rw_ok),
            ro_ok=bool(ro_ok),
            signature=signature,
        )

        if not (rw_ok and ro_ok):
            logger.error("Kube: one or more endpoint updates failed", rw_ok=bool(rw_ok), ro_ok=bool(ro_ok), signature=signature)

        return bool(rw_ok and ro_ok)
