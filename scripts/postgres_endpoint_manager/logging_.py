import logging
import os
import sys
import structlog


def _configure_structlog():
    """Configure structlog with a minimal, standard set of processors.

    This is intentionally simple: it uses add_log_level, stack/info/exception
    helpers, a TimeStamper, and JSONRenderer. The LOG_LEVEL env var controls
    the minimum level for filtering.
    """
    level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)

    # Basic stdlib config so any libraries using logging still emit to stdout
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None):
    """Return a plain structlog BoundLogger. Configures structlog once."""
    if not getattr(get_logger, "_configured", False):
        _configure_structlog()
        get_logger._configured = True
    return structlog.get_logger(name)