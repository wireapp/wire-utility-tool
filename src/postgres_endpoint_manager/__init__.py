from .logging_ import get_logger
from .orchestrator import Orchestrator
from .config import Config, load_from_env
from .utils import parse_nodes, make_signature


def setup_logging(name: str = __name__):
    """Returns a configured structured logger."""
    return get_logger(name)


# Export main classes and utilities for external use
__all__ = ['Orchestrator', 'Config', 'load_from_env', 'setup_logging', 'parse_nodes', 'make_signature']
