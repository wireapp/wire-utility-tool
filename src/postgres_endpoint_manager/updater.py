from typing import List
from datetime import datetime, timezone
from .logging_ import get_logger

ANNOTATION_KEY = 'postgres.discovery/last-topology'

class EndpointUpdater:
    def __init__(self, kube_client):
        self.kube = kube_client
        self.logger = get_logger('endpoint-updater')

    def build_payload(self, target_ips: List[str], signature: str) -> dict:
        body = {
            'metadata': {
                'annotations': {
                    ANNOTATION_KEY: signature,
                    'postgres.discovery/last-update': datetime.now(timezone.utc).isoformat()
                }
            },
            'subsets': [
                {
                    'addresses': [{'ip': ip} for ip in target_ips],
                    'ports': [{'port': 5432, 'protocol': 'TCP', 'name': 'postgresql'}]
                }
            ] if target_ips else []
        }
        return body

    def update(self, service_name: str, target_ips: List[str], signature: str) -> bool:
        body = self.build_payload(target_ips, signature)
        try:
            self.kube.patch_endpoints(service_name, body)
            self.logger.info("Endpoint updated successfully",
                           service=service_name,
                           target_ips=target_ips,
                           endpoint_count=len(target_ips))
            return True
        except Exception as e:
            self.logger.error("Failed to update endpoint",
                            service=service_name,
                            target_ips=target_ips,
                            error=str(e),
                            error_type=type(e).__name__)
            return False
