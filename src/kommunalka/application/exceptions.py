class ApplicationError(Exception):
    """Base error of the application layer."""


class NotFoundError(ApplicationError):
    """Requested entity does not exist."""


class ConflictError(ApplicationError):
    """Storage rejected a write that conflicts with existing data, e.g. a duplicate."""
