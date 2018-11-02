class PossumException(Exception):
    """Base Possum Exception"""


class PipenvPathNotFound(PossumException):
    """Pipenv could not be located"""


class SAMTemplateError(PossumException):
    """There was an error reading the template file"""
