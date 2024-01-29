"""
InfraHouse Toolkit Logging.
"""
import logging
import sys


class LessThanFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Filters out log messages of a lower level."""

    def __init__(self, exclusive_maximum, name=""):
        super().__init__(name)
        self.max_level = exclusive_maximum

    def filter(self, record):
        # non-zero return means we log this message
        return 1 if record.levelno < self.max_level else 0


def setup_logging(logger=None, debug=False):  # pragma: no cover
    """Configures logging for the module"""
    logger = logger or logging.getLogger()
    fmt_str = "%(asctime)s: %(levelname)s: %(name)s:%(module)s.%(funcName)s():%(lineno)d: %(message)s"

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.addFilter(LessThanFilter(logging.WARNING))
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(fmt_str))

    # Log errors and warnings to stderr
    console_handler_err = logging.StreamHandler(stream=sys.stderr)
    console_handler_err.setLevel(logging.WARNING)
    console_handler_err.setFormatter(logging.Formatter(fmt_str))

    # Log debug to stderr
    console_handler_debug = logging.StreamHandler(stream=sys.stderr)
    console_handler_debug.addFilter(LessThanFilter(logging.INFO))
    console_handler_debug.setLevel(logging.DEBUG)
    console_handler_debug.setFormatter(logging.Formatter(fmt_str))

    logger.handlers = []
    logger.addHandler(console_handler)
    logger.addHandler(console_handler_err)

    if debug:
        logger.addHandler(console_handler_debug)
        logger.debug_enabled = True

    logger.setLevel(logging.DEBUG)
