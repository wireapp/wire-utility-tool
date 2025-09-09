import sys
import argparse
from .config import load_from_env
from .logging_ import get_logger
from .orchestrator import Orchestrator


def main(argv=None):
    parser = argparse.ArgumentParser(prog='postgres-endpoint-manager')
    parser.add_argument('--test', action='store_true', help='Run test harness')
    args = parser.parse_args(argv or sys.argv[1:])

    cfg = load_from_env()
    logger = get_logger('pg-endpoint-manager')
    orch = Orchestrator(cfg=cfg, logger=logger)
    ok = orch.run()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
