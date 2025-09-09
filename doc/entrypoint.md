Entrypoint change: package CLI

Summary

The container entrypoint was changed to run the package CLI module directly instead of an older monolith script. The runtime now executes the package module:

    python -m scripts.postgres_endpoint_manager.cli

Rationale

- Moves execution to a proper Python package and module, improving import hygiene and testability.
- Avoids shipping a single large monolith script and enables better modularization of code under `scripts/postgres_endpoint_manager`.
- Keeps the final image minimal by copying only the package source rather than the whole `scripts/` directory.

What changed

- Dockerfile.postgres-endpoint-manager:
  - ENTRYPOINT is now `python -m scripts.postgres_endpoint_manager.cli`.
  - The final image copies only `scripts/postgres_endpoint_manager` into `/app/scripts/postgres_endpoint_manager`.
  - `PYTHONPATH` includes `/app` so the `scripts` package resolves when running the module.
- The legacy monolith `scripts/postgres-endpoint-manager.py` was removed. A package-level compatibility wrapper is available in `scripts/postgres_endpoint_manager/__init__.py` for callers that depended on exported symbols.

How to run locally

- Build the runtime image as usual (see Makefile targets). Then run:

    docker run --rm sukisuk/postgres-endpoint-manager:latest

- For development or testing (host-mounted source), the Makefile test target mounts `./scripts` into `/app/scripts` and runs the test harness. Use:

    make test-pg-manager

Verification

- The test harness performs a runtime import check for `psycopg` and runs a comprehensive in-container test suite. Successful run example: "Comprehensive test suite completed — total_tests: 8, passed_tests: 8".

