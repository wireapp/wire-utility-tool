import logging
import os
import sys
import structlog


def _configure_structlog():
    """Configure structlog following recommended patterns from structlog docs.
    """
    # Get log level from environment, default to INFO
    log_level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, log_level_name, logging.INFO)

    # Configure standard library logging first (this affects wrapped loggers)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,           # Filter by log level first
            structlog.stdlib.add_logger_name,           # Add logger name
            structlog.stdlib.add_log_level,             # Add log level
            structlog.stdlib.PositionalArgumentsFormatter(),  # Handle positional args
            structlog.processors.StackInfoRenderer(),    # Stack info when requested
            structlog.processors.format_exc_info,       # Format exceptions
            structlog.processors.TimeStamper(fmt="iso"), # ISO timestamp
            structlog.dev.ConsoleRenderer(),             # Pretty console output
        ],
        wrapper_class=structlog.stdlib.BoundLogger,     # Use stdlib integration
        logger_factory=structlog.stdlib.LoggerFactory(),  # Create stdlib loggers
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None):
    """Return a configured structured logger."""
    if not getattr(get_logger, "_configured", False):
        _configure_structlog()
        get_logger._configured = True
    return structlog.get_logger(name)