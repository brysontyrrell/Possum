class PossumException(Exception):
    """Base Possum Exception"""


class PipenvPathNotFound(PossumException):
    """Pipenv could not be located"""
