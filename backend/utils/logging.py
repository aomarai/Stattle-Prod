import logging
import os

from pythonjsonlogger import json


def setup_logger() -> None:
    """
    Configure logging for the application.

    :return: None
    """
    log_level = os.environ.get("LOG_LEVEL", "WARNING")

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Set up JSON formatting for logs
    handler = logging.StreamHandler()
    formatter = json.JsonFormatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
    )
    handler.setFormatter(formatter)

    if not root_logger.handlers:
        root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the application.
    :param name: The name of the logger.
    :return: Logger object.
    """
    return logging.getLogger(name)
