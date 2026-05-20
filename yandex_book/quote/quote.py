"""
quote/quote.py — цитата из книги.
"""
from __future__ import annotations

from dataclasses import field
from typing import TYPE_CHECKING, Any, List, Optional

from yandex_book.base import BaseModel
from yandex_book.utils import model

if TYPE_CHECKING:
    from yandex_book.book.book import Book
    from yandex_book.client import YandexBookClient
    from yandex_book.user.user import Image, Person


@model
class Quote(BaseModel):
    """Цитата — выделенный фрагмент книги с комментарием пользователя."""

    # Идентификация позиции в тексте
    cfi: Optional[str] = None            # EPUB CFI (позиция начала)
    start_node_xpath: Optional[str] = None
    start_node_offset: Optional[int] = None
    finish_node_xpath: Optional[str] = None
    finish_node_offset: Optional[int] = None

    item_uuid: Optional[str] = None      # UUID книги/аудиокниги

    # Содержимое
    content: Optional[str] = None        # текст цитаты
    comment: Optional[str] = None        # комментарий пользователя
    color: Optional[int] = None          # цвет подсветки
    style: Optional[str] = None          # стиль подсветки
    state: Optional[str] = None          # состояние (active / deleted)

    # Метаданные
    created_at: Optional[int] = None     # unix timestamp
    progress: Optional[int] = None       # прогресс в % на момент цитаты
    liked: Optional[bool] = None
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None

    # Связанные объекты
    book: Optional['Book'] = None
    cover: Optional['Image'] = None
    authors: Optional[str] = None        # строка с именами (REST API)
    authors_objects: Optional[List['Person']] = field(default_factory=list)

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.cfi, self.item_uuid)

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['Quote']:
        if not cls.is_dict_model_data(data):
            return None

        cls_data = cls.cleanup_data(data, client)

        from yandex_book.book.book import Book
        from yandex_book.user.user import Image, Person

        cls_data['book'] = Book.de_json(data.get('book'), client)
        cls_data['cover'] = Image.de_json(data.get('cover'), client)
        cls_data['authors_objects'] = Person.de_list(
            data.get('authors_objects', []), client
        )

        return cls(client=client, **cls_data)
