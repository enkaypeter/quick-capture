from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional

from app.extensions import db

T = TypeVar("T", bound=db.Model)


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository providing common CRUD operations.

    Subclasses must set `model` to the SQLAlchemy model class.
    This abstraction allows swapping the underlying data store without
    changing service or view code.
    """

    model: type[T]

    def get_by_id(self, entity_id: int) -> Optional[T]:
        return self.model.query.get(entity_id)

    def get_all(self) -> list[T]:
        return self.model.query.all()

    def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        return instance

    def update(self, instance: T, **kwargs) -> T:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        db.session.commit()
        return instance

    def delete(self, instance: T) -> None:
        db.session.delete(instance)
        db.session.commit()

    def save(self) -> None:
        """Flush pending changes to the database."""
        db.session.commit()
