"""
user/user.py — модели пользователя.

Модели (снизу вверх по зависимостям):
  Image   — обложка / аватар (url разных размеров)
  Avatar  — аватар пользователя (наследует Image)
  Person  — автор / переводчик / нарратор
  User    — полноценный пользователь платформы
"""
from __future__ import annotations

from dataclasses import field
from typing import TYPE_CHECKING, Any, List, Optional

from yandex_book.base import BaseModel
from yandex_book.utils import model

if TYPE_CHECKING:
    from yandex_book.client import YandexBookClient


# ---------------------------------------------------------------------------
# Image / Cover
# ---------------------------------------------------------------------------

@model
class Image(BaseModel):
    """Изображение (обложка книги, аватар, etc.)."""

    small: Optional[str] = None
    large: Optional[str] = None
    placeholder: Optional[str] = None
    ratio: Optional[float] = None
    background_color_hex: Optional[str] = None
    url: Optional[str] = None          # GraphQL API возвращает url вместо large

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.large or self.url,)

    @property
    def best_url(self) -> Optional[str]:
        """Возвращает наилучший доступный URL изображения."""
        return self.large or self.url or self.small or self.placeholder


@model
class Avatar(Image):
    """Аватар пользователя. Наследует все поля Image."""

    def __post_init__(self) -> None:
        self._id_attrs = (self.large or self.url,)


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------

@model
class Person(BaseModel):
    """Автор, переводчик, нарратор или любой другой участник."""

    uuid: Optional[str] = None
    name: Optional[str] = None
    locale: Optional[str] = None
    works_count: Optional[int] = None
    image: Optional[Image] = None
    avatar: Optional[Image] = None     # GraphQL использует avatar вместо image
    removed: Optional[bool] = None
    roles: Optional[List[str]] = field(default_factory=list)

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid,)

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['Person']:
        if not cls.is_dict_model_data(data):
            return None
        cls_data = cls.cleanup_data(data, client)
        cls_data['image'] = Image.de_json(data.get('image'), client)
        cls_data['avatar'] = Image.de_json(data.get('avatar'), client)
        return cls(client=client, **cls_data)

    def fetch_books(self) -> list:
        """Получить книги автора через клиент."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_person_books(self.uuid)  # type: ignore[union-attr]

    async def fetch_books_async(self) -> list:
        assert self.valid_async_client(self.client), 'Требуется асинхронный клиент'
        return await self.client.get_person_books(self.uuid)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

@model
class User(BaseModel):
    """Пользователь платформы Bookmate / Яндекс Книги."""

    uuid: Optional[str] = None
    id: Optional[int] = None
    login: Optional[str] = None
    name: Optional[str] = None
    avatar: Optional[Avatar] = None
    image: Optional[Image] = None

    bookshelves_count: Optional[int] = None
    cards_count: Optional[int] = None
    followers_count: Optional[int] = None
    followings_count: Optional[int] = None
    library_cards_count: Optional[int] = None
    following: Optional[bool] = None

    gender: Optional[str] = None
    background_color_hex: Optional[str] = None
    about: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    vk: Optional[str] = None
    site: Optional[str] = None
    social_networks: Optional[List[Any]] = field(default_factory=list)

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.uuid or self.id,)

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['User']:
        if not cls.is_dict_model_data(data):
            return None
        cls_data = cls.cleanup_data(data, client)
        cls_data['avatar'] = Avatar.de_json(data.get('avatar'), client)
        cls_data['image'] = Image.de_json(data.get('image'), client)
        return cls(client=client, **cls_data)

    def download_avatar(self, size: str = 'large', dest: Optional[str] = None) -> str:
        """Скачать аватар пользователя.

        Args:
            size: 'large' или 'small'.
            dest: путь сохранения (авто если None).

        Returns:
            Путь к сохранённому файлу.
        """
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        assert self.avatar is not None, 'Аватар недоступен'
        url = getattr(self.avatar, size, None) or self.avatar.best_url
        assert url, f'URL аватара размера {size!r} не найден'
        dest = dest or f'avatars/{self.uuid or self.id}_{size}.jpg'
        import os
        os.makedirs(os.path.dirname(dest), exist_ok=True) if os.path.dirname(dest) else None
        self.client._request.download(url, dest)  # type: ignore[union-attr]
        return dest

    # ---- Shortcut-методы на клиент ----------------------------------- #

    def fetch_books(self):
        """Получить книги пользователя."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_user_books(self.uuid or self.id)  # type: ignore[union-attr]

    def fetch_audiobooks(self):
        """Получить аудиокниги пользователя."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_user_audiobooks(self.uuid or self.id)  # type: ignore[union-attr]

    def fetch_bookshelves(self):
        """Получить полки пользователя."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_user_bookshelves(self.uuid or self.id)  # type: ignore[union-attr]

    def fetch_quotes(self):
        """Получить цитаты пользователя."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_user_quotes(self.uuid or self.id)  # type: ignore[union-attr]

    def fetch_impressions(self):
        """Получить рецензии пользователя."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_user_impressions(self.uuid or self.id)  # type: ignore[union-attr]

    def fetch_followings(self):
        """Получить подписки пользователя."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_user_followings(self.uuid or self.id)  # type: ignore[union-attr]

    def fetch_reading_achievements(self):
        """Получить достижения пользователя."""
        assert self.valid_client(self.client), 'Требуется синхронный клиент'
        return self.client.get_user_reading_achievements(self.uuid or self.id)  # type: ignore[union-attr]

    # ---- Async shortcuts --------------------------------------------- #

    async def fetch_books_async(self):
        assert self.valid_async_client(self.client), 'Требуется асинхронный клиент'
        return await self.client.get_user_books(self.uuid or self.id)  # type: ignore[union-attr]

    async def fetch_audiobooks_async(self):
        assert self.valid_async_client(self.client), 'Требуется асинхронный клиент'
        return await self.client.get_user_audiobooks(self.uuid or self.id)  # type: ignore[union-attr]
