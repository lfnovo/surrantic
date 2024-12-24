import logging
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> None:
    """Configure logging for the application.
    
    Args:
        level: The logging level to use. Defaults to logging.INFO.
        log_file: Optional path to log file. If None, only console logging is used.
    """
    # Create a formatter that includes all necessary information
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Get the root logger and set its level
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers and add our configured ones
    root_logger.handlers = []
    root_logger.addHandler(console_handler)

    # Add file handler if log_file is specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set specific levels for different loggers
    logging.getLogger('surrantic').setLevel(level)
    
    # Suppress noisy loggers
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('surrealdb').setLevel(logging.WARNING)
    logging.getLogger('surrealdb').setLevel(logging.WARNING)
