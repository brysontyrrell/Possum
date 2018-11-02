import logging
import sys


logger = logging.getLogger(__name__)


class MyFormatter(logging.Formatter):
    """This is a custom formatter for the logger to write INFO level messages
    without showing the level. All other levels display the level.

    Example output::

        >>> logger.info('A message')
        'A message'
        >>> logger.error('A message')
        'ERROR: A Message'

    """
    info_format = "%(message)s"
    error_warn_format = "%(levelname)s: %(message)s"

    def __init__(self):
        super().__init__(fmt="%(levelno)d: %(msg)s", datefmt=None, style='%')

    def format(self, record):
        original_format = self._style._fmt

        if record.levelno != logging.INFO:
            self._style._fmt = MyFormatter.error_warn_format

        elif record.levelno == logging.INFO:
            self._style._fmt = MyFormatter.info_format

        result = logging.Formatter.format(self, record)
        self._style._fmt = original_format
        return result


def configure_logger():
    """Configure the logger. For use when invoked as a CLI tool."""
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(MyFormatter())
    stream_handler.setLevel(logging.DEBUG)

    logger.addHandler(stream_handler)
    logger.setLevel(logging.INFO)
