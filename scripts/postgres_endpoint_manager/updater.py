from typing import List
from datetime import datetime, timezone

ANNOTATION_KEY = 'postgres.discovery/last-topology'

class EndpointUpdater:
    def __init__(self, kube_client):
        self.kube = kube_client

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
            return True
        except Exception as e:
            # kube client wrapper will raise on ApiException or missing client
            # upstream should handle/log; here we return False to signal failure
            return False
