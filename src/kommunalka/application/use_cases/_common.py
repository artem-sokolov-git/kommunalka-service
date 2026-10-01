from uuid import UUID

from kommunalka.application.exceptions import NotFoundError


def require[T](entity: T | None, kind: str, entity_id: UUID) -> T:
    if entity is None:
        raise NotFoundError(f"{kind} {entity_id} not found")
    return entity
