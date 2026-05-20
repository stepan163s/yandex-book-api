# ============================================================
# ВНИМАНИЕ: этот файл сгенерирован автоматически.
# Источник: yandex_book/client.py
# Команда:  python generate_async_version.py
# ============================================================

"""
client_async.py — АСИНХРОННЫЙ клиент Яндекс Книги / Bookmate API.

Автоматически сгенерирован из client.py скриптом generate_async_version.py.
НЕ редактируйте этот файл вручную — изменения будут перезаписаны.

Единственный публичный интерфейс для работы с API.
Async-версия генерируется скриптом generate_async_version.py.

Использование:
    from yandex_book import YandexBookClient

    client = YandexBookClient('y0_AgAAAA...')
    me = client.get_profile()
    books = client.get_user_books(me.uuid)

Методы сгруппированы по доменам:
  • Профиль / аутентификация
  • Пользователи (публичные данные)
  • Книги / аудиокниги / комиксы
  • Личная библиотека
  • Полки
  • Рецензии и цитаты
  • Достижения и статистика
  • Поиск и рекомендации
  • GraphQL (поиск, подписки, статистика)
"""
from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from yandex_book.utils.request_async import RequestAsync as Request

logger = logging.getLogger(__name__)

# URL-константы
_REST_BASE = 'https://api.bookmate.yandex.net/api/v5'
_GRAPHQL_URL = 'https://api-gateway.bookmate.yandex.net/graphql'

# GraphQL-запросы (вынесены в константы для читаемости)
_GQL_SEARCH = """
query Search($query: SearchParamsInput!) {
    search(query: $query) {
        page {
            __typename
            ...searchSnippetAudioBookFragment
            ...searchSnippetTextBookFragment
            ...searchSnippetComicBookFragment
            ...searchSnippetTextSerialFragment
            ...bookshelfFragment
            ...personFragment
            ...publisherFragment
            ...seriesFragment
            ...topicFragment
            ...userFragment
        }
        cursor
        rankedFilter { filterType }
        misspell { correctedText correctionType }
    }
}
fragment coverFragment on Cover { url ratio backgroundColorHex }
fragment personFragment on Person { avatar { __typename ...coverFragment } name uuid worksCount roles }
fragment bookFragment on Book { annotation name cover { __typename ...coverFragment } uuid authors { __typename ...personFragment } ageRestriction editorAnnotation }
fragment publisherFragment on Publisher { avatar { __typename ...coverFragment } name uuid worksCount }
fragment publisherBookFragment on Book { publisher { __typename ...publisherFragment } }
fragment translatorsBookFragment on Book { translators { __typename ...personFragment } }
fragment topicsBookFragment on Book { topics { name totalBook uuid } }
fragment subscriptionLevelsFragment on Book { subscriptionLevels }
fragment snippetBookFragment on Book { __typename ...bookFragment ...publisherBookFragment ...translatorsBookFragment ...topicsBookFragment ...subscriptionLevelsFragment }
fragment bookTagFragment on Tag { name value }
fragment narratorsAudioBookFragment on AudioBook { narrators { __typename ...personFragment } }
fragment progressFragment on Progress { finished inLibrary progress isPublic }
fragment progressAudioBookFragment on AudioBook { progress { __typename ...progressFragment } }
fragment listenersCountAudioBookFragment on AudioBook { listenersCount }
fragment searchSnippetAudioBookFragment on AudioBook { __typename book { __typename ...snippetBookFragment tags { __typename ...bookTagFragment } } ...narratorsAudioBookFragment ...progressAudioBookFragment ...listenersCountAudioBookFragment }
fragment progressTextBookFragment on TextBook { progress { __typename ...progressFragment } }
fragment readersCountTextBookFragment on TextBook { readersCount }
fragment searchSnippetTextBookFragment on TextBook { __typename book { __typename ...snippetBookFragment tags { __typename ...bookTagFragment } } ...progressTextBookFragment ...readersCountTextBookFragment }
fragment progressComicBookFragment on ComicBook { progress { __typename ...progressFragment } }
fragment readersCountComicBookFragment on ComicBook { readersCount }
fragment searchSnippetComicBookFragment on ComicBook { __typename book { __typename ...snippetBookFragment tags { __typename ...bookTagFragment } } ...progressComicBookFragment ...readersCountComicBookFragment }
fragment textSerialFragment on TextSerial { book { __typename ...bookFragment } }
fragment episodesTextSerialFragment on TextSerial { episodes { total } }
fragment readersCountTextSerialFragment on TextSerial { readersCount }
fragment searchSnippetTextSerialFragment on TextSerial { __typename book { __typename ...snippetBookFragment tags { __typename ...bookTagFragment } } ...textSerialFragment ...episodesTextSerialFragment ...readersCountTextSerialFragment }
fragment userFragment on User { avatar { __typename ...coverFragment } name uuid followersCount login }
fragment bookshelfFragment on Bookshelf { cover { __typename ...coverFragment } name uuid user { __typename ...userFragment } posts { total } followersCount description }
fragment seriesFragment on Series { authors { __typename ...personFragment } cover { __typename ...coverFragment } name uuid items { followersCount total } }
fragment topicFragment on Topic { name slug totalBook uuid parent { name slug totalBook uuid } }
"""

_GQL_SUBSCRIPTIONS = """
query ProfileSubscriptions($subscriptionParams: SubscriptionParamsInput!) {
    profile {
        subscriptions(subscriptionParams: $subscriptionParams) {
            cursor
            page {
                __typename
                ...personFragment
                ...subscriptionPersonFragment
            }
        }
    }
}
fragment coverFragment on Cover { url ratio backgroundColorHex }
fragment personFragment on Person { avatar { __typename ...coverFragment } name uuid worksCount roles }
fragment subscriptionPersonFragment on Person { subscription { muted } }
"""

_GQL_STATISTICS = """
query Statistics($requestTime: DateTime!) {
    user(login: null) {
        loyalty(currentTime: $requestTime) {
            statistics {
                daysPerMonth
                streak
                streakRecord
                todayTime
            }
        }
    }
}
"""


# ---------------------------------------------------------------------------
# Декоратор @log — логирование без boilerplate
# ---------------------------------------------------------------------------

def log(method):
    """Добавляет debug-логирование до и после вызова метода."""
    method_logger = logging.getLogger(method.__module__)

    @functools.wraps(method)
    async def wrapper(*args, **kwargs):
        method_logger.debug('Entering: %s', method.__name__)
        result = await method(*args, **kwargs)
        method_logger.debug(result)
        method_logger.debug('Exiting: %s', method.__name__)
        return result

    return wrapper


# ---------------------------------------------------------------------------
# YandexBookClient
# ---------------------------------------------------------------------------

class YandexBookClientAsync:
    """Асинхронный клиент для Bookmate / Яндекс Книги API.

    Args:
        token:                Auth-Token для авторизованных запросов.
        language:             Код языка интерфейса (по умолчанию 'ru').
        report_unknown_fields: Логировать неизвестные поля из ответов API.
        timeout:              Таймаут HTTP-запросов в секундах.
        request:              Можно передать кастомный Request-объект (для тестов).
    """

    _is_async: bool = True

    def __init__(
        self,
        token: Optional[str] = None,
        language: str = 'ru',
        report_unknown_fields: bool = False,
        timeout: int = 10,
        request: Optional[Request] = None,
    ) -> None:
        self.token = token
        self.language = language
        self.report_unknown_fields = report_unknown_fields
        self.base_url = _REST_BASE
        self.graphql_url = _GRAPHQL_URL

        self._request: Request = request or Request(self, timeout=timeout)

        if token:
            self._request.set_token(token)
        if language:
            self._request.set_language(language)

        # Заполняется после вызова init()
        self.me: Optional[Any] = None
        self.account_uuid: Optional[str] = None

    async def init(self) -> 'YandexBookClientAsync':
        """Загрузить данные авторизованного пользователя.

        Вызывается один раз после создания клиента, если нужен account_uuid
        для методов, принимающих user_id=None.
        """
        self.me = await self.get_profile()
        if self.me:
            self.account_uuid = self.me.uuid or str(self.me.id or '')
        return self

    # ================================================================== #
    # ПРОФИЛЬ И АВТОРИЗАЦИЯ                                               #
    # ================================================================== #

    @log
    async def get_profile(self):
        """Получить профиль авторизованного пользователя.

        Returns:
            User — объект текущего пользователя.
        """
        from yandex_book.user.user import User
        url = f'{self.base_url}/profile'
        result = await self._request.get(url)
        return User.de_json(result.get('user'), self)

    @log
    async def get_counters(self) -> Dict[str, Any]:
        """Счётчики профиля (уведомления, сообщения и т.п.)."""
        url = f'{self.base_url}/profile/counters'
        return await self._request.get(url)

    @log
    async def get_notifications_status(self) -> Dict[str, Any]:
        """Статус уведомлений."""
        url = f'{self.base_url}/profile/notifications/status'
        return await self._request.get(url)

    @log
    async def get_access_levels(self) -> Dict[str, Any]:
        """Уровни доступа к контенту."""
        url = f'{self.base_url}/profile/access_levels'
        return await self._request.get(url)

    @log
    async def get_privacy_settings(self) -> Dict[str, Any]:
        """Настройки приватности профиля."""
        url = f'{self.base_url}/profile/privacy_settings'
        return await self._request.get(url)

    @log
    async def get_sync_state(self) -> Dict[str, Any]:
        """Состояние синхронизации данных."""
        url = f'{self.base_url}/profile/sync_state'
        return await self._request.get(url)

    @log
    async def get_context(self) -> Dict[str, Any]:
        """Контекст приложения."""
        url = f'{self.base_url}/context'
        return await self._request.get(url)

    @log
    async def get_metadata_secret(self) -> Dict[str, Any]:
        """Защищённые метаданные профиля."""
        url = f'{self.base_url}/metadata_secret'
        return await self._request.get(url)

    @log
    async def get_user_json(self) -> Dict[str, Any]:
        """Полный JSON объект текущего пользователя."""
        url = f'{self.base_url}/a/4/user.json'
        return await self._request.get(url)

    @log
    async def get_push_notification_restrictions(self) -> Dict[str, Any]:
        """Ограничения для push-уведомлений."""
        url = f'{self.base_url}/a/4/push_notification_settings/restrictions'
        return await self._request.get(url)

    @log
    async def get_features(self, feature_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Информация о доступных фичах приложения.

        Args:
            feature_names: список имён фич (если None — используется стандартный набор).
        """
        if feature_names is None:
            feature_names = [
                'xiva_push_sync', 'show_app_update', 'sync_audio_text_V2',
                'crm_communication', 'new_cfi_readings', 'audio_synthesis_v2',
                'year_paywall_v2', 'sync_progress_v2', 'person_subscription',
                'show_paywall_on_every_launch', 'plus_benefits_from_offer',
            ]
        params = '&'.join(f'names[]={n}' for n in feature_names)
        url = f'{self.base_url}/features?{params}'
        return await self._request.get(url)

    # ================================================================== #
    # ПОЛЬЗОВАТЕЛИ (ПУБЛИЧНЫЕ ДАННЫЕ)                                     #
    # ================================================================== #

    @log
    async def get_user(self, user_id):
        """Получить публичный профиль пользователя.

        Args:
            user_id: числовой ID или строковый UUID пользователя.

        Returns:
            User или None.
        """
        from yandex_book.user.user import User
        url = f'{self.base_url}/users/{user_id}'
        result = await self._request.get(url)
        return User.de_json(result.get('user'), self)

    @log
    async def get_user_books(self, user_id) -> List[Any]:
        """Книги пользователя."""
        from yandex_book.book.book import Book
        url = f'{self.base_url}/users/{user_id}/books'
        result = await self._request.get(url)
        return Book.de_list(result.get('books', []), self)

    @log
    async def get_user_audiobooks(self, user_id) -> List[Any]:
        """Аудиокниги пользователя."""
        from yandex_book.book.book import Audiobook
        url = f'{self.base_url}/users/{user_id}/audiobooks'
        result = await self._request.get(url)
        return Audiobook.de_list(result.get('audiobooks', []), self)

    @log
    async def get_user_comics(self, user_id) -> List[Any]:
        """Комиксы пользователя."""
        from yandex_book.book.book import Comicbook
        url = f'{self.base_url}/users/{user_id}/comicbooks'
        result = await self._request.get(url)
        return Comicbook.de_list(result.get('comicbooks', []), self)

    @log
    async def get_user_bookshelves(self, user_id) -> List[Any]:
        """Полки пользователя."""
        from yandex_book.bookshelf.bookshelf import Bookshelf
        url = f'{self.base_url}/users/{user_id}/bookshelves'
        result = await self._request.get(url)
        return Bookshelf.de_list(result.get('bookshelves', []), self)

    @log
    async def get_user_followings(self, user_id) -> List[Any]:
        """Подписки пользователя (на других пользователей)."""
        from yandex_book.user.user import User
        url = f'{self.base_url}/users/{user_id}/followings'
        result = await self._request.get(url)
        return User.de_list(result.get('users', []), self)

    @log
    async def get_user_impressions(self, user_id) -> List[Any]:
        """Рецензии пользователя."""
        from yandex_book.impression.impression import Impression
        url = f'{self.base_url}/users/{user_id}/impressions'
        result = await self._request.get(url)
        return Impression.de_list(result.get('impressions', []), self)

    @log
    async def get_user_quotes(self, user_id) -> List[Any]:
        """Цитаты пользователя."""
        from yandex_book.quote.quote import Quote
        url = f'{self.base_url}/users/{user_id}/quotes'
        result = await self._request.get(url)
        return Quote.de_list(result.get('quotes', []), self)

    @log
    async def get_user_reading_achievements(self, user_id) -> List[Any]:
        """Достижения чтения пользователя."""
        from yandex_book.achievement.achievement import ReadingAchievement
        url = f'{self.base_url}/users/{user_id}/reading_achievements'
        result = await self._request.get(url)
        return ReadingAchievement.de_list(result.get('reading_achievements', []), self)

    # ================================================================== #
    # КНИГИ / АУДИОКНИГИ / КОМИКСЫ                                       #
    # ================================================================== #

    @log
    async def get_book(self, book_id: str):
        """Получить книгу по UUID.

        Returns:
            Book или None.
        """
        from yandex_book.book.book import Book
        url = f'{self.base_url}/books/{book_id}'
        result = await self._request.get(url)
        return Book.de_json(result.get('book'), self)

    @log
    async def get_book_impressions(self, book_id: str) -> List[Any]:
        """Рецензии на книгу."""
        from yandex_book.impression.impression import Impression
        url = f'{self.base_url}/books/{book_id}/impressions'
        result = await self._request.get(url)
        return Impression.de_list(result.get('impressions', []), self)

    @log
    async def get_audiobook(self, audiobook_id: str):
        """Получить аудиокнигу по UUID."""
        from yandex_book.book.book import Audiobook
        url = f'{self.base_url}/audiobooks/{audiobook_id}'
        result = await self._request.get(url)
        return Audiobook.de_json(result.get('audiobook'), self)

    @log
    async def get_comicbook(self, comic_id: str):
        """Получить комикс по UUID."""
        from yandex_book.book.book import Comicbook
        url = f'{self.base_url}/comicbooks/{comic_id}'
        result = await self._request.get(url)
        return Comicbook.de_json(result.get('comicbook'), self)

    @log
    async def get_comicbook_impressions(self, comic_id: str) -> List[Any]:
        """Рецензии на комикс."""
        from yandex_book.impression.impression import Impression
        url = f'{self.base_url}/comicbooks/{comic_id}/impressions'
        result = await self._request.get(url)
        return Impression.de_list(result.get('impressions', []), self)

    # ================================================================== #
    # ЛИЧНАЯ БИБЛИОТЕКА                                                   #
    # ================================================================== #

    @log
    async def get_my_library(self, limit: int = 50, offset: int = 0) -> List[Any]:
        """Книги в личной библиотеке.

        Args:
            limit:  количество книг (макс. 100).
            offset: смещение для пагинации.

        Returns:
            Список LibraryCard.
        """
        from yandex_book.book.book import LibraryCard
        url = f'{self.base_url}/profile/library_cards'
        result = await self._request.get(url, params={'limit': limit, 'offset': offset})
        return LibraryCard.de_list(result.get('library_cards', []), self)

    @log
    async def add_book(self, book_uuid: str):
        """Добавить книгу в личную библиотеку.

        Args:
            book_uuid: UUID книги.

        Returns:
            LibraryCard или None.
        """
        from yandex_book.book.book import LibraryCard
        url = f'{self.base_url}/profile/library_cards'
        result = await self._request.post(url, data={'book_uuid': book_uuid})
        return LibraryCard.de_json(result.get('library_card'), self)

    @log
    async def remove_book(self, library_card_uuid: str) -> bool:
        """Удалить книгу из личной библиотеки.

        Args:
            library_card_uuid: UUID карточки библиотеки.

        Returns:
            True если успешно.
        """
        url = f'{self.base_url}/profile/library_cards/{library_card_uuid}'
        await self._request.delete(url)
        return True

    # ================================================================== #
    # ПОЛКИ                                                               #
    # ================================================================== #

    @log
    async def get_my_bookshelves(self, page: int = 1, per_page: int = 20) -> List[Any]:
        """Мои книжные полки.

        Returns:
            Список Bookshelf.
        """
        from yandex_book.bookshelf.bookshelf import Bookshelf
        url = f'{self.base_url}/profile/bookshelves'
        result = await self._request.get(url, params={'page': page, 'per_page': per_page})
        return Bookshelf.de_list(result.get('bookshelves', []), self)

    @log
    async def get_bookshelf_books(self, bookshelf_uuid: str) -> List[Any]:
        """Книги на полке.

        Returns:
            Список Book.
        """
        from yandex_book.book.book import Book
        url = f'{self.base_url}/bookshelves/{bookshelf_uuid}/books'
        result = await self._request.get(url)
        return Book.de_list(result.get('books', []), self)

    # ================================================================== #
    # СЕРИИ                                                               #
    # ================================================================== #

    @log
    async def get_series_following(
        self,
        user_id=None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """Серии, на которые подписан пользователь.

        Args:
            user_id:  ID пользователя. Если None — используется профиль.
            page:     номер страницы.
            per_page: элементов на странице.
        """
        if user_id is None:
            url = f'{self.base_url}/profile/series/following'
        else:
            url = f'{self.base_url}/users/{user_id}/series/following'
        return await self._request.get(url, params={'page': page, 'per_page': per_page})

    # ================================================================== #
    # РЕЦЕНЗИИ И ДОСТИЖЕНИЯ                                               #
    # ================================================================== #

    @log
    async def get_reading_achievements(self, year: Optional[int] = None):
        """Достижения чтения авторизованного пользователя.

        Args:
            year: год (если None — текущий год).

        Returns:
            ReadingAchievement или None.
        """
        from yandex_book.achievement.achievement import ReadingAchievement
        if year:
            url = f'{self.base_url}/profile/reading_achievements/{year}'
        else:
            url = f'{self.base_url}/profile/reading_achievements'
        result = await self._request.get(url)
        return ReadingAchievement.de_json(result.get('reading_achievement') or result.get('data'), self)

    @log
    async def get_emotions(self) -> Dict[str, Any]:
        """Доступные эмоции для рецензий."""
        url = f'{self.base_url}/a/4/d/impressions/emotions'
        return await self._request.get(url)

    # ================================================================== #
    # ПОИСК И РЕКОМЕНДАЦИИ                                               #
    # ================================================================== #

    @log
    async def get_popular_searches(self, language: str = 'ru', page: int = 1) -> Dict[str, Any]:
        """Популярные поисковые запросы.

        Args:
            language: код языка ('ru', 'en', …).
            page:     номер страницы.
        """
        url = f'{self.base_url}/popular_searches/{language}'
        return await self._request.get(url, params={'page': page})

    # ================================================================== #
    # GRAPHQL                                                             #
    # ================================================================== #

    @log
    async def search(
        self,
        query: str,
        no_misspell: bool = False,
        types: Optional[List[str]] = None,
        cursor: str = '',
    ) -> Dict[str, Any]:
        """GraphQL-поиск книг, авторов, издателей, пользователей.

        Args:
            query:       поисковый запрос (например, 'Мастер и Маргарита').
            no_misspell: не предлагать исправление опечаток.
            types:       фильтр по типам (TextBook, AudioBook, Person…).
                         Пустой список = все типы.
            cursor:      курсор пагинации (пусто = первая страница).

        Returns:
            Сырой dict с ключом data.search.page.
        """
        variables = {
            'query': {
                'cursor': cursor,
                'noMisspell': no_misspell,
                'query': query,
                'types': types or [],
            }
        }
        return await self._request.graphql(
            self.graphql_url, _GQL_SEARCH, variables, 'Search'
        )

    @log
    async def get_subscriptions(
        self,
        cursor: str = '',
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """GraphQL-запрос подписок на авторов.

        Args:
            cursor:   курсор пагинации.
            per_page: элементов на странице.
        """
        variables = {
            'subscriptionParams': {
                'cursor': cursor,
                'perPage': per_page,
                'subscriptionFilterSource': ['SUBSCRIPTION_FILTER_SOURCE_PERSON'],
            }
        }
        return await self._request.graphql(
            self.graphql_url, _GQL_SUBSCRIPTIONS, variables, 'ProfileSubscriptions'
        )

    @log
    async def get_reading_statistics(self, request_time: Optional[str] = None) -> Dict[str, Any]:
        """GraphQL-статистика чтения (серии, рекорды, время за сегодня).

        Args:
            request_time: время в ISO-8601. Если None — текущее UTC-время.
        """
        if request_time is None:
            request_time = datetime.now(timezone.utc).isoformat()
        variables = {'requestTime': request_time}
        return await self._request.graphql(
            self.graphql_url, _GQL_STATISTICS, variables, 'Statistics'
        )

    # ================================================================== #
    # УТИЛИТЫ                                                             #
    # ================================================================== #

    @log
    async def test_token(self) -> bool:
        """Проверить валидность Auth-Token.

        Returns:
            True если токен рабочий.
        """
        try:
            result = await self.get_profile()
            return result is not None
        except Exception:
            return False

    async def download_file(self, url: str, filepath: str) -> None:
        """Скачать файл по URL в локальный путь."""
        await self._request.download(url, filepath)

    # ---- Алиасы для обратной совместимости ---------------------------- #

    async def search_books(
        self,
        query: str,
        no_misspell: bool = False,
        types: Optional[List[str]] = None,
        cursor: str = '',
    ) -> Dict[str, Any]:
        """Алиас для search(). GraphQL-поиск книг, авторов, издателей."""
        return await self.search(query, no_misspell=no_misspell, types=types, cursor=cursor)
