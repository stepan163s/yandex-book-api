"""
yandex_book — Python-клиент для Bookmate / Яндекс Книги API.

Быстрый старт:
    from yandex_book import YandexBookClient

    client = YandexBookClient('y0_AgAAAA...')
    me = client.get_profile()
    print(me.name, me.login)

    books = client.get_user_books(me.uuid)
    for book in books:
        print(book.display_title)
"""

__version__ = '2.0.0'
__author__ = 'stepan163s'

from yandex_book.client import YandexBookClient

try:
    from yandex_book.client_async import YandexBookClientAsync
except ImportError:
    # aiohttp не установлен — async-клиент недоступен
    YandexBookClientAsync = None  # type: ignore[assignment,misc]

# Модели — для удобного импорта из корня пакета
from yandex_book.achievement.achievement import ReadingAchievement, ReadingChallenge
from yandex_book.book.book import Audiobook, Book, Comicbook, Label, LibraryCard, Series
from yandex_book.bookshelf.bookshelf import Bookshelf
from yandex_book.exceptions import (
    ApiError,
    BadRequestError,
    IdMissingError,
    InvalidOptionError,
    NetworkError,
    NotFoundError,
    TimedOutError,
    UnauthorizedError,
)
from yandex_book.impression.impression import Impression
from yandex_book.quote.quote import Quote
from yandex_book.user.user import Avatar, Image, Person, User

__all__ = [
    # Клиенты
    'YandexBookClient',
    'YandexBookClientAsync',

    # Исключения
    'ApiError',
    'NetworkError',
    'TimedOutError',
    'UnauthorizedError',
    'BadRequestError',
    'NotFoundError',
    'InvalidOptionError',
    'IdMissingError',

    # Модели — пользователь
    'Image',
    'Avatar',
    'Person',
    'User',

    # Модели — книги
    'Label',
    'Book',
    'Audiobook',
    'Comicbook',
    'LibraryCard',
    'Series',

    # Модели — контент
    'Bookshelf',
    'Impression',
    'Quote',

    # Модели — достижения
    'ReadingChallenge',
    'ReadingAchievement',
]
