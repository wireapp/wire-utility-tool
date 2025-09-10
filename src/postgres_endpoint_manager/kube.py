from typing import Optional

try:
    from kubernetes import client, config
    K8S_AVAILABLE = True
except Exception:
    K8S_AVAILABLE = False


class KubeClient:
    """Lightweight wrapper around CoreV1Api for endpoints operations.

    Instantiate with an injected CoreV1Api for tests, or with no arg to
    auto-load in-cluster config when available.
    """
    def __init__(self, namespace: str, api: Optional[object] = None):
        self.namespace = namespace
        self.v1 = api
        if self.v1 is None and K8S_AVAILABLE:
            try:
                config.load_incluster_config()
                self.v1 = client.CoreV1Api()
            except Exception:
                self.v1 = None

    def read_endpoints(self, name: str):
        if not self.v1:
            raise RuntimeError('k8s client not initialized')
        return self.v1.read_namespaced_endpoints(name=name, namespace=self.namespace)

    def patch_endpoints(self, name: str, body: dict):
        if not self.v1:
            raise RuntimeError('k8s client not initialized')
        return self.v1.patch_namespaced_endpoints(name=name, namespace=self.namespace, body=body)

    def get_annotation(self, name: str, key: str) -> Optional[str]:
        ep = self.read_endpoints(name)
        annotations = getattr(ep.metadata, 'annotations', None) or {}
        return annotations.get(key)
