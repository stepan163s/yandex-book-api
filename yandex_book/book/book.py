"""
book/book.py — модели книжного контента.

Иерархия:
  Label         — тег/метка книги (например, «Новинка», «Бестселлер»)
  Book          — текстовая книга
  Audiobook     — аудиокнига (наследует Book, добавляет duration, narrators…)
  Comicbook     — комикс (наследует Audiobook)
  LibraryCard   — запись о книге в личной библиотеке пользователя
  Series        — серия книг

Дедупликация de_json:
  Логика вложенных объектов вынесена в _resolve_nested (classmethod).
  Book.de_json — единственная реализация; Audiobook и Comicbook
  только переопределяют _resolve_nested, наследуя de_json от Book.
"""
from __future__ import annotations

from dataclasses import field
from typing import TYPE_CHECKING, Any, List, Optional

from yandex_book.base import BaseModel
from yandex_book.utils import model

if TYPE_CHECKING:
    from yandex_book.client import YandexBookClient
    from yandex_book.user.user import Image, Person


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------

@model
class Label(BaseModel):
    """Метка / тег книги."""

    title: Optional[str] = None
    kind: Optional[str] = None

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.title, self.kind)


# ---------------------------------------------------------------------------
# Book
# ---------------------------------------------------------------------------

@model
class Book(BaseModel):
    """Текстовая книга."""

    uuid: Optional[str] = None
    title: Optional[str] = None
    name: Optional[str] = None          # GraphQL возвращает name вместо title
    annotation: Optional[str] = None
    editor_annotation: Optional[str] = None
    resource_type: Optional[str] = None
    language: Optional[str] = None
    age_restriction: Optional[str] = None
    owner_catalog_title: Optional[str] = None
    subscription_level: Optional[str] = None
    subscription_levels: Optional[List[str]] = field(default_factory=list)

    publication_date: Optional[int] = None
    readers_count: Optional[int] = None
    bookshelves_count: Optional[int] = None
    impressions_count: Optional[int] = None

    background_color_hex: Optional[str] = None

    cover: Optional['Image'] = None
    authors: Optional[List['Person']] = field(default_factory=list)
    authors_objects: Optional[List['Person']] = field(default_factory=list)
    translators: Optional[List['Person']] = field(default_factory=list)
    labels: Optional[List[Label]] = field(default_factory=list)

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    @property
    def display_title(self) -> Optional[str]:
        """Возвращает title или name (совместимость REST и GraphQL)."""
        return self.title or self.name

    # ------------------------------------------------------------------ #
    # Десериализация                                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def _resolve_nested(cls, data: Any, client: Any, cls_data: dict) -> None:
        """Десериализует вложенные объекты, общие для Book / Audiobook / Comicbook.

        Подклассы расширяют этот метод для своих дополнительных полей,
        не трогая de_json — он единственный и живёт только в Book.
        """
        from yandex_book.user.user import Image, Person
        cls_data['cover'] = Image.de_json(data.get('cover'), client)
        cls_data['authors'] = Person.de_list(data.get('authors', []), client)
        cls_data['authors_objects'] = Person.de_list(data.get('authors_objects', []), client)
        cls_data['translators'] = Person.de_list(data.get('translators', []), client)
        cls_data['labels'] = Label.de_list(data.get('labels', []), client)

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['Book']:
        """Единственная реализация de_json для всей иерархии книг.

        cls автоматически будет Audiobook / Comicbook когда вызывается
        как Audiobook.de_json(...), поэтому cls._resolve_nested вызывает
        нужный override, а cls(client=...) строит правильный тип.
        """
        if not cls.is_dict_model_data(data):
            return None
        cls_data = cls.cleanup_data(data, client)
        cls._resolve_nested(data, client, cls_data)
        return cls(client=client, **cls_data)

    # ---- Shortcut-методы ---------------------------------------------- #

    def fetch_impressions(self):
        """Получить рецензии на книгу."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_book_impressions(self.uuid)  # type: ignore[union-attr]

    def download_cover(self, size: str = 'large', dest: Optional[str] = None) -> str:
        """Скачать обложку книги."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        assert self.cover is not None, 'Обложка недоступна'
        url = getattr(self.cover, size, None) or self.cover.best_url
        assert url, f'URL обложки размера {size!r} не найден'
        dest = dest or f'covers/books/{self.uuid}_{size}.jpg'
        return self.client._request.download(url, dest)  # type: ignore[union-attr]

    async def fetch_impressions_async(self):
        assert self.valid_async_client(self.client), 'Требуется асинхронный клиент'
        return await self.client.get_book_impressions(self.uuid)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Audiobook
# ---------------------------------------------------------------------------

@model
class Audiobook(Book):
    """Аудиокнига. Расширяет Book аудио-специфичными полями.

    de_json унаследован от Book; здесь только _resolve_nested.
    """

    document_uuid: Optional[str] = None
    can_be_listened: Optional[bool] = None
    duration: Optional[int] = None       # секунды
    listeners_count: Optional[int] = None
    narrators: Optional[List['Person']] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    @classmethod
    def _resolve_nested(cls, data: Any, client: Any, cls_data: dict) -> None:
        Book._resolve_nested(data, client, cls_data)          # cover, authors, labels…
        from yandex_book.user.user import Person
        cls_data['narrators'] = Person.de_list(data.get('narrators', []), client)


# ---------------------------------------------------------------------------
# Comicbook
# ---------------------------------------------------------------------------

@model
class Comicbook(Audiobook):
    """Комикс. Наследует Audiobook.

    _resolve_nested и de_json оба унаследованы — здесь только поля.
    """

    comic_card: Optional[Any] = None
    pages_count: Optional[int] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    def download_cover(self, size: str = 'large', dest: Optional[str] = None) -> str:
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        assert self.cover is not None, 'Обложка недоступна'
        url = getattr(self.cover, size, None) or self.cover.best_url
        assert url, f'URL обложки размера {size!r} не найден'
        dest = dest or f'covers/comics/{self.uuid}_{size}.jpg'
        return self.client._request.download(url, dest)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# LibraryCard
# ---------------------------------------------------------------------------

@model
class LibraryCard(BaseModel):
    """Запись о книге в личной библиотеке пользователя."""

    uuid: Optional[str] = None
    state: Optional[str] = None           # 'reading', 'finished', 'want_to_read'
    reading_progress: Optional[float] = None
    added_at: Optional[int] = None
    updated_at: Optional[int] = None

    book: Optional[Book] = None
    audiobook: Optional[Audiobook] = None
    comicbook: Optional[Comicbook] = None

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['LibraryCard']:
        if not cls.is_dict_model_data(data):
            return None
        cls_data = cls.cleanup_data(data, client)
        cls_data['book'] = Book.de_json(data.get('book'), client)
        cls_data['audiobook'] = Audiobook.de_json(data.get('audiobook'), client)
        cls_data['comicbook'] = Comicbook.de_json(data.get('comicbook'), client)
        return cls(client=client, **cls_data)

    def remove(self) -> bool:
        """Удалить из библиотеки через клиент."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        assert self.uuid, 'UUID карточки отсутствует'
        return self.client.remove_book(self.uuid)  # type: ignore[union-attr]

    async def remove_async(self) -> bool:
        assert self.valid_async_client(self.client), 'Требуется асинхронный клиент'
        return await self.client.remove_book(self.uuid)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------

@model
class Series(BaseModel):
    """Серия книг."""

    uuid: Optional[str] = None
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    books_count: Optional[int] = None
    followers_count: Optional[int] = None

    cover: Optional['Image'] = None
    authors: Optional[List['Person']] = field(default_factory=list)

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    @property
    def display_title(self) -> Optional[str]:
        return self.title or self.name

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['Series']:
        if not cls.is_dict_model_data(data):
            return None
        cls_data = cls.cleanup_data(data, client)
        from yandex_book.user.user import Image, Person
        cls_data['cover'] = Image.de_json(data.get('cover'), client)
        cls_data['authors'] = Person.de_list(data.get('authors', []), client)
        return cls(client=client, **cls_data)
