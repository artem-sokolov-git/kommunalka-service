class ApplicationError(Exception):
    """Base error of the application layer."""


class NotFoundError(ApplicationError):
    """Requested entity does not exist."""
