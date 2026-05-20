"""
achievement/achievement.py — достижения и статистика чтения.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from yandex_book.base import BaseModel
from yandex_book.utils import model

if TYPE_CHECKING:
    from yandex_book.client import YandexBookClient
    from yandex_book.user.user import User


@model
class ReadingChallenge(BaseModel):
    """Цель чтения (книжный челлендж) на год."""

    promised_books_count: Optional[int] = None
    finished_books_count: Optional[int] = None
    image_url: Optional[str] = None
    share_url: Optional[str] = None

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.promised_books_count,)


@model
class ReadingAchievement(BaseModel):
    """Статистика чтения пользователя за год.

    Поля:
      finished_books_count — количество прочитанных книг
      year                 — год статистики
      seconds              — суммарное время чтения в секундах
      pages                — суммарное количество страниц
      last_updated         — unix timestamp последнего обновления
      share_url            — URL для расшаривания результатов
      reading_challenge    — привязанный челлендж
      user                 — пользователь (автор достижения)
    """

    finished_books_count: Optional[int] = None
    year: Optional[int] = None
    seconds: Optional[int] = None
    pages: Optional[int] = None
    last_updated: Optional[int] = None
    share_url: Optional[str] = None

    reading_challenge: Optional[ReadingChallenge] = None
    user: Optional['User'] = None

    client: Optional['YandexBookClient'] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.year,)

    @property
    def hours(self) -> float:
        """Суммарное время чтения в часах."""
        return (self.seconds or 0) / 3600

    @classmethod
    def de_json(cls, data: Any, client: Any) -> Optional['ReadingAchievement']:
        if not cls.is_dict_model_data(data):
            return None

        cls_data = cls.cleanup_data(data, client)

        from yandex_book.user.user import User

        cls_data['reading_challenge'] = ReadingChallenge.de_json(
            data.get('reading_challenge'), client
        )
        cls_data['user'] = User.de_json(data.get('user'), client)

        return cls(client=client, **cls_data)
