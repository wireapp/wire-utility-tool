import sys
import argparse
from . import load_from_env, setup_logging, Orchestrator


def main(argv=None):
    parser = argparse.ArgumentParser(prog='postgres-endpoint-manager')
    parser.add_argument('--test', action='store_true', help='Run test harness')
    args = parser.parse_args(argv or sys.argv[1:])

    cfg = load_from_env()
    logger = setup_logging('pg-endpoint-manager')
    orch = Orchestrator(cfg=cfg, logger=logger)
    ok = orch.run()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
