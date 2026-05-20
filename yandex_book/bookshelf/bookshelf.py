"""
bookshelf/bookshelf.py — книжная полка пользователя.
"""
from __future__ import annotations

from dataclasses import field
from typing import TYPE_CHECKING, Any, List, Optional

from yandex_book.base import BaseModel
from yandex_book.utils import model

if TYPE_CHECKING:
    from yandex_book.client import YandexBookClient
    from yandex_book.user.user import Image, Person, User


@model
class Bookshelf(BaseModel):
    """Книжная полка — коллекция книг, созданная пользователем."""

    uuid: Optional[str] = None
    title: Optional[str] = None
    annotation: Optional[str] = None
    books_count: Optional[int] = None
    followers_count: Optional[int] = None
    posts_count: Optional[int] = None
    following: Optional[bool] = None

    cover: Optional['Image'] = None
    creator: Optional['User'] = None
    authors: Optional[List['Person']] = field(default_factory=list)

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['Bookshelf']:
        if not cls.is_dict_model_data(data):
            return None

        cls_data = cls.cleanup_data(data, client)

        from yandex_book.user.user import Image, Person, User

        cls_data['cover'] = Image.de_json(data.get('cover'), client)
        cls_data['creator'] = User.de_json(data.get('creator'), client)
        cls_data['authors'] = Person.de_list(data.get('authors', []), client)

        return cls(client=client, **cls_data)

    # ---- Shortcut-методы ---------------------------------------------- #

    def fetch_books(self):
        """Получить книги на полке."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_bookshelf_books(self.uuid)  # type: ignore[union-attr]

    async def fetch_books_async(self):
        assert self.valid_async_client(self.client), 'Требуется асинхронный клиент'
        return await self.client.get_bookshelf_books(self.uuid)  # type: ignore[union-attr]
