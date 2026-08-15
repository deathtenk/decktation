import logging


def get_logger(name):
    """Centralize runtime logger creation while the package is scaffolded."""
    return logging.getLogger(name)
