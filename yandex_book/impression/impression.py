"""
impression/impression.py — рецензия / впечатление о книге.
"""
from __future__ import annotations

from dataclasses import field
from typing import TYPE_CHECKING, Any, List, Optional

from yandex_book.base import BaseModel
from yandex_book.utils import model

if TYPE_CHECKING:
    from yandex_book.book.book import Audiobook, Book
    from yandex_book.client import YandexBookClient
    from yandex_book.user.user import User


@model
class Impression(BaseModel):
    """Рецензия / впечатление пользователя о книге или аудиокниге."""

    uuid: Optional[str] = None
    content: Optional[str] = None       # текст рецензии
    created_at: Optional[int] = None    # unix timestamp
    updated_at: Optional[int] = None

    liked: Optional[bool] = None
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None

    emotion: Optional[str] = None       # эмоция (label)

    book: Optional['Book'] = None
    resource: Optional['Audiobook'] = None
    user: Optional['User'] = None
    liker_users: Optional[List['User']] = field(default_factory=list)

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['Impression']:
        if not cls.is_dict_model_data(data):
            return None

        cls_data = cls.cleanup_data(data, client)

        from yandex_book.book.book import Audiobook, Book
        from yandex_book.user.user import User

        cls_data['book'] = Book.de_json(data.get('book'), client)
        cls_data['resource'] = Audiobook.de_json(data.get('resource'), client)
        cls_data['user'] = User.de_json(data.get('user'), client)
        cls_data['liker_users'] = User.de_list(data.get('liker_users', []), client)

        return cls(client=client, **cls_data)
