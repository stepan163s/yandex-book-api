"""
client.py — синхронный клиент Яндекс Книги / Bookmate API.

Единственный публичный интерфейс для работы с API.
Async-версия генерируется скриптом generate_async_version.py.

Использование:
    from yandex_book import YandexBookClient

    client = YandexBookClient('y0_AgAAAA...')
    me = client.get_profile()
    books = client.get_user_books(me.login)

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
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urlsplit, urlunsplit

from yandex_book.utils.request import Request

from yandex_book.achievement.achievement import ReadingAchievement
from yandex_book.book.book import Audiobook, Book, Comicbook, LibraryCard
from yandex_book.bookshelf.bookshelf import Bookshelf
from yandex_book.impression.impression import Impression
from yandex_book.quote.quote import Quote
from yandex_book.user.user import User
from yandex_book.exceptions import EndpointGoneError, IdMissingError, InvalidOptionError, UnauthorizedError

logger = logging.getLogger(__name__)

# URL-константы
_REST_BASE = 'https://api.bookmate.yandex.net/api/v5'
_GRAPHQL_URL = 'https://api-gateway.bookmate.yandex.net/graphql'


def _legacy_url(base_url: str, path: str) -> str:
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, f'/a/4/{path}', '', ''))


def _validate_pagination(page: int, per_page: int) -> None:
    if type(page) is not int or page < 1:
        raise InvalidOptionError('page должен быть целым числом больше нуля')
    if type(per_page) is not int or not 1 <= per_page <= 100:
        raise InvalidOptionError('per_page должен быть целым числом от 1 до 100')

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
    def wrapper(*args, **kwargs):
        method_logger.debug('Entering: %s', method.__name__)
        result = method(*args, **kwargs)
        method_logger.debug('Exiting: %s', method.__name__)
        return result

    return wrapper


# ---------------------------------------------------------------------------
# YandexBookClient
# ---------------------------------------------------------------------------

class YandexBookClient:
    """Синхронный клиент для Bookmate / Яндекс Книги API.

    Args:
        token:                Auth-Token для авторизованных запросов.
        language:             Код языка интерфейса (по умолчанию 'ru').
        report_unknown_fields: Логировать неизвестные поля из ответов API.
        timeout:              Таймаут HTTP-запросов в секундах.
        request:              Можно передать кастомный Request-объект (для тестов).
    """

    _is_async: bool = False

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
        self.me: Optional[User] = None
        self.account_uuid: Optional[str] = None
        self.account_login: Optional[str] = None

    def close(self) -> None:
        self._request.close()

    def __enter__(self) -> 'YandexBookClient':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def init(self) -> 'YandexBookClient':
        """Загрузить данные авторизованного пользователя.

        Заполняет me и account_login. Для запросов пользователя нужен логин;
        account_uuid сохранён для совместимости и не используется в маршрутах.
        """
        self.me = self.get_profile()
        if self.me:
            self.account_uuid = self.me.uuid or str(self.me.id or '')
            self.account_login = self.me.login
        return self

    def _resolve_user_login(self, user_id: Optional[Union[int, str]]) -> str:
        if isinstance(user_id, str):
            if not user_id.strip():
                raise IdMissingError('Логин пользователя отсутствует')
            return user_id.strip()
        if user_id is not None and type(user_id) is not int:
            raise InvalidOptionError('Нужен логин пользователя')
        if user_id is not None and not self.token:
            raise InvalidOptionError('Числовой ID поддерживается только для текущего аккаунта с токеном; передайте логин')
        profile = self.me or self.get_profile()
        if profile is None or not profile.login:
            raise IdMissingError('Логин текущего пользователя отсутствует в профиле')
        if user_id is not None and profile.id != user_id:
            raise InvalidOptionError('Для другого пользователя нужен логин, а не числовой ID')
        self.me = profile
        self.account_login = profile.login
        return profile.login

    def _user_url(self, user_id: Optional[Union[int, str]], suffix: str = '') -> str:
        login = self._resolve_user_login(user_id)
        return f'{self.base_url}/users/{quote(login, safe="")}{suffix}'

    # ================================================================== #
    # ПРОФИЛЬ И АВТОРИЗАЦИЯ                                               #
    # ================================================================== #

    @log
    def get_profile(self) -> Optional[User]:
        """Получить профиль авторизованного пользователя.

        Returns:
            User — объект текущего пользователя.
        """
        url = f'{self.base_url}/profile'
        result = self._request.get(url)
        return User.de_json(result.get('user'), self)

    @log
    def get_counters(self) -> Dict[str, Any]:
        """Счётчики профиля (уведомления, сообщения и т.п.)."""
        url = f'{self.base_url}/profile/counters'
        return self._request.get(url)

    @log
    def get_notifications_status(self) -> Dict[str, Any]:
        """Статус уведомлений."""
        url = f'{self.base_url}/profile/notifications/status'
        return self._request.get(url)

    @log
    def get_access_levels(self) -> Dict[str, Any]:
        """Уровни доступа к контенту."""
        url = f'{self.base_url}/profile/access_levels'
        return self._request.get(url)

    @log
    def get_privacy_settings(self) -> Dict[str, Any]:
        """Настройки приватности профиля."""
        url = f'{self.base_url}/profile/privacy_settings'
        return self._request.get(url)

    @log
    def get_sync_state(self) -> Dict[str, Any]:
        """Состояние синхронизации данных."""
        url = f'{self.base_url}/profile/sync_state'
        return self._request.get(url)

    @log
    def get_context(self) -> Dict[str, Any]:
        """Контекст приложения."""
        url = f'{self.base_url}/context'
        return self._request.get(url)

    @log
    def get_metadata_secret(self) -> Dict[str, Any]:
        """Защищённые метаданные профиля."""
        url = f'{self.base_url}/metadata_secret'
        return self._request.get(url)

    @log
    def get_user_json(self) -> Dict[str, Any]:
        """Полный JSON объект текущего пользователя."""
        url = _legacy_url(self.base_url, 'user.json')
        return self._request.get(url)

    @log
    def get_push_notification_restrictions(self) -> Dict[str, Any]:
        """Ограничения для push-уведомлений."""
        url = _legacy_url(self.base_url, 'push_notification_settings/restrictions')
        return self._request.get(url)

    @log
    def get_features(self, feature_names: Optional[List[str]] = None) -> Dict[str, Any]:
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
        url = f'{self.base_url}/features'
        return self._request.get(url, params={'names[]': feature_names})

    # ================================================================== #
    # ПОЛЬЗОВАТЕЛИ (ПУБЛИЧНЫЕ ДАННЫЕ)                                     #
    # ================================================================== #

    @log
    def get_user(self, user_id: Union[int, str]) -> Optional[User]:
        """Получить публичный профиль пользователя.

        Args:
            user_id: логин. Числовой ID текущего аккаунта разрешается через профиль
                     при наличии токена. Для других пользователей нужен логин.

        Returns:
            User или None.
        """
        url = self._user_url(user_id)
        result = self._request.get(url)
        return User.de_json(result.get('user'), self)

    @log
    def get_user_books(self, user_id: Union[int, str]) -> List[Book]:
        """Книги пользователя."""
        url = self._user_url(user_id, '/books')
        result = self._request.get(url)
        return Book.de_list(result.get('books', []), self)

    @log
    def get_user_audiobooks(self, user_id: Union[int, str]) -> List[Audiobook]:
        """Аудиокниги пользователя."""
        url = self._user_url(user_id, '/audiobooks')
        result = self._request.get(url)
        return Audiobook.de_list(result.get('audiobooks', []), self)

    @log
    def get_user_comics(self, user_id: Union[int, str]) -> List[Comicbook]:
        """Комиксы пользователя."""
        url = self._user_url(user_id, '/comicbooks')
        result = self._request.get(url)
        return Comicbook.de_list(result.get('comicbooks', []), self)

    @log
    def get_user_bookshelves(self, user_id: Union[int, str]) -> List[Bookshelf]:
        """Полки пользователя."""
        url = self._user_url(user_id, '/bookshelves')
        result = self._request.get(url)
        return Bookshelf.de_list(result.get('bookshelves', []), self)

    @log
    def get_user_followings(self, user_id: Union[int, str]) -> List[User]:
        """Подписки пользователя (на других пользователей)."""
        url = self._user_url(user_id, '/followings')
        result = self._request.get(url)
        return User.de_list(result.get('users', []), self)

    @log
    def get_user_impressions(self, user_id: Union[int, str]) -> List[Impression]:
        """Рецензии пользователя."""
        url = self._user_url(user_id, '/impressions')
        result = self._request.get(url)
        return Impression.de_list(result.get('impressions', []), self)

    @log
    def get_user_quotes(self, user_id: Union[int, str]) -> List[Quote]:
        """Цитаты пользователя."""
        url = self._user_url(user_id, '/quotes')
        result = self._request.get(url)
        return Quote.de_list(result.get('quotes', []), self)

    @log
    def get_user_reading_achievements(self, user_id: Union[int, str]) -> List[ReadingAchievement]:
        """Устаревший эндпоинт достижений: сервис возвращает HTTP 410."""
        url = self._user_url(user_id, '/reading_achievements')
        try:
            result = self._request.get(url)
        except EndpointGoneError as exc:
            raise EndpointGoneError('Достижения чтения больше недоступны. get_reading_statistics() возвращает текущую статистику вашего аккаунта, но не заменяет годовые достижения другого пользователя.') from exc
        return ReadingAchievement.de_list(result.get('reading_achievements', []), self)

    # ================================================================== #
    # КНИГИ / АУДИОКНИГИ / КОМИКСЫ                                       #
    # ================================================================== #

    @log
    def get_person_books(self, person_id: str, role: str = 'author', page: int = 1, per_page: int = 20) -> List[Book]:
        if not person_id or not person_id.strip():
            raise IdMissingError('UUID автора отсутствует')
        if role not in ('author', 'translator', 'narrator', 'illustrator', 'publisher'):
            raise InvalidOptionError('Неизвестная роль участника книги')
        if page < 1 or per_page < 1:
            raise InvalidOptionError('page и per_page должны быть больше нуля')
        url = f'{self.base_url}/authors/{person_id}/books'
        result = self._request.get(url, params={'role': role, 'page': page, 'per_page': per_page})
        return Book.de_list(result.get('books', []), self)

    @log
    def get_book(self, book_id: str) -> Optional[Book]:
        """Получить книгу по UUID.

        Returns:
            Book или None.
        """
        url = f'{self.base_url}/books/{book_id}'
        result = self._request.get(url)
        return Book.de_json(result.get('book'), self)

    @log
    def get_book_impressions(self, book_id: str) -> List[Impression]:
        """Рецензии на книгу."""
        url = f'{self.base_url}/books/{book_id}/impressions'
        result = self._request.get(url)
        return Impression.de_list(result.get('impressions', []), self)

    @log
    def get_audiobook(self, audiobook_id: str) -> Optional[Audiobook]:
        """Получить аудиокнигу по UUID."""
        url = f'{self.base_url}/audiobooks/{audiobook_id}'
        result = self._request.get(url)
        return Audiobook.de_json(result.get('audiobook'), self)

    @log
    def get_audiobook_impressions(self, audiobook_id: str) -> List[Impression]:
        """Рецензии на аудиокнигу."""
        url = f'{self.base_url}/audiobooks/{audiobook_id}/impressions'
        result = self._request.get(url)
        return Impression.de_list(result.get('impressions', []), self)

    @log
    def get_comicbook(self, comic_id: str) -> Optional[Comicbook]:
        """Получить комикс по UUID."""
        url = f'{self.base_url}/comicbooks/{comic_id}'
        result = self._request.get(url)
        return Comicbook.de_json(result.get('comicbook'), self)

    @log
    def get_comicbook_impressions(self, comic_id: str) -> List[Impression]:
        """Рецензии на комикс."""
        url = f'{self.base_url}/comicbooks/{comic_id}/impressions'
        result = self._request.get(url)
        return Impression.de_list(result.get('impressions', []), self)

    # ================================================================== #
    # ЛИЧНАЯ БИБЛИОТЕКА                                                   #
    # ================================================================== #

    @log
    def get_my_library(self, limit: Optional[int] = None, offset: Optional[int] = None,
                       *, page: Optional[int] = None, per_page: Optional[int] = None) -> List[LibraryCard]:
        """Книги в личной библиотеке.

        Args:
            page: номер страницы, по умолчанию 1.
            per_page: размер страницы от 1 до 100, по умолчанию 20.
            limit: прежнее ограничение количества (1–100), вместо page/per_page.
            offset: прежнее смещение; при отсутствии limit используется 50.

        Returns:
            Список LibraryCard.
        """
        url = f'{self.base_url}/profile/library_cards'
        legacy = limit is not None or offset is not None
        if legacy and (page is not None or per_page is not None):
            raise InvalidOptionError('Используйте либо page/per_page, либо limit/offset')
        if not legacy:
            page = 1 if page is None else page
            per_page = 20 if per_page is None else per_page
            _validate_pagination(page, per_page)
            result = self._request.get(url, params={'page': page, 'per_page': per_page})
            return LibraryCard.de_list(result.get('library_cards', []), self)
        limit = 50 if limit is None else limit
        offset = 0 if offset is None else offset
        _validate_pagination(1, limit)
        if type(offset) is not int or offset < 0:
            raise InvalidOptionError('offset должен быть целым числом не меньше нуля')
        page, skip = divmod(offset, limit)
        page += 1
        result = self._request.get(url, params={'page': page, 'per_page': limit})
        items = result.get('library_cards', [])
        if skip and len(items) == limit:
            following = self._request.get(url, params={'page': page + 1, 'per_page': limit})
            items = items + following.get('library_cards', [])
        return LibraryCard.de_list(items[skip:skip + limit], self)

    @log
    def add_book(self, book_uuid: str) -> Optional[LibraryCard]:
        """Добавить книгу в личную библиотеку.

        Args:
            book_uuid: UUID книги.

        Returns:
            LibraryCard или None.
        """
        url = f'{self.base_url}/profile/library_cards'
        result = self._request.post(url, data={'book_uuid': book_uuid})
        return LibraryCard.de_json(result.get('library_card'), self)

    @log
    def remove_book(self, library_card_uuid: str) -> bool:
        """Удалить книгу из личной библиотеки.

        Args:
            library_card_uuid: UUID карточки библиотеки.

        Returns:
            True если успешно.
        """
        url = f'{self.base_url}/profile/library_cards/{library_card_uuid}'
        self._request.delete(url)
        return True

    # ================================================================== #
    # ПОЛКИ                                                               #
    # ================================================================== #

    @log
    def get_my_bookshelves(self, page: int = 1, per_page: int = 20) -> List[Bookshelf]:
        """Мои книжные полки.

        Returns:
            Список Bookshelf.
        """
        url = f'{self.base_url}/profile/bookshelves'
        result = self._request.get(url, params={'page': page, 'per_page': per_page})
        return Bookshelf.de_list(result.get('bookshelves', []), self)

    @log
    def get_bookshelf_books(self, bookshelf_uuid: str) -> List[Book]:
        """Книги на полке.

        Returns:
            Список Book.
        """
        url = f'{self.base_url}/bookshelves/{bookshelf_uuid}/books'
        result = self._request.get(url)
        return Book.de_list(result.get('books', []), self)

    # ================================================================== #
    # СЕРИИ                                                               #
    # ================================================================== #

    @log
    def get_series_following(
        self,
        user_id: Optional[Union[int, str]] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """Серии, на которые подписан пользователь.

        Args:
            user_id: логин пользователя. Если None — логин из своего профиля.
            page:     номер страницы.
            per_page: элементов на странице.
        """
        _validate_pagination(page, per_page)
        url = self._user_url(user_id, '/series/following')
        return self._request.get(url, params={'page': page, 'per_page': per_page})

    # ================================================================== #
    # РЕЦЕНЗИИ И ДОСТИЖЕНИЯ                                               #
    # ================================================================== #

    @log
    def get_reading_achievements(self, year: Optional[int] = None) -> Optional[ReadingAchievement]:
        """Устаревший эндпоинт достижений: сервис возвращает HTTP 410.

        Args:
            year: год (если None — текущий год).

        Returns:
            ReadingAchievement или None.
        """
        if year:
            url = f'{self.base_url}/profile/reading_achievements/{year}'
        else:
            url = f'{self.base_url}/profile/reading_achievements'
        try:
            result = self._request.get(url)
        except EndpointGoneError as exc:
            raise EndpointGoneError('Годовые достижения чтения больше недоступны. Используйте get_reading_statistics() для текущей статистики; её формат и набор показателей отличаются.') from exc
        return ReadingAchievement.de_json(result.get('reading_achievement') or result.get('data'), self)

    @log
    def get_emotions(self) -> Dict[str, Any]:
        """Доступные эмоции для рецензий."""
        url = _legacy_url(self.base_url, 'd/impressions/emotions')
        return self._request.get(url)

    # ================================================================== #
    # ПОИСК И РЕКОМЕНДАЦИИ                                               #
    # ================================================================== #

    @log
    def get_popular_searches(self, language: str = 'ru', page: int = 1) -> Dict[str, Any]:
        """Популярные поисковые запросы.

        Args:
            language: код языка ('ru', 'en', …).
            page:     номер страницы.
        """
        url = f'{self.base_url}/popular_searches/{language}'
        return self._request.get(url, params={'page': page})

    # ================================================================== #
    # GRAPHQL                                                             #
    # ================================================================== #

    @log
    def search(
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
            types:       значения enum Type из схемы GraphQL сервиса.
                         Пустой список = все типы. Имена __typename
                         в ответах не являются значениями этого enum.
            cursor:      курсор пагинации (пусто = первая страница).

        Returns:
            Нормализованный dict с data.search.page при успешном ответе.
            Ошибки GraphQL возвращаются в errors, включая HTTP 200.
        """
        variables = {
            'query': {
                'cursor': cursor,
                'noMisspell': no_misspell,
                'query': query,
                'types': types or [],
            }
        }
        return self._request.graphql(
            self.graphql_url, _GQL_SEARCH, variables, 'Search'
        )

    @log
    def get_subscriptions(
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
        return self._request.graphql(
            self.graphql_url, _GQL_SUBSCRIPTIONS, variables, 'ProfileSubscriptions'
        )

    @log
    def get_reading_statistics(self, request_time: Optional[str] = None) -> Dict[str, Any]:
        """GraphQL-статистика чтения (серии, рекорды, время за сегодня).

        Args:
            request_time: время в ISO-8601. Если None — текущее UTC-время.
        """
        if request_time is None:
            request_time = datetime.now(timezone.utc).isoformat()
        variables = {'requestTime': request_time}
        return self._request.graphql(
            self.graphql_url, _GQL_STATISTICS, variables, 'Statistics'
        )

    # ================================================================== #
    # УТИЛИТЫ                                                             #
    # ================================================================== #

    @log
    def test_token(self) -> bool:
        """Проверить валидность Auth-Token.

        Returns:
            True если токен рабочий.
        """
        try:
            result = self.get_profile()
            return result is not None
        except UnauthorizedError:
            return False

    def download_file(self, url: str, filepath: str) -> None:
        """Скачать файл по URL в локальный путь."""
        self._request.download(url, filepath)

    # ---- Алиасы для обратной совместимости ---------------------------- #

    def search_books(
        self,
        query: str,
        no_misspell: bool = False,
        types: Optional[List[str]] = None,
        cursor: str = '',
    ) -> Dict[str, Any]:
        """Алиас для search(). GraphQL-поиск книг, авторов, издателей."""
        return self.search(query, no_misspell=no_misspell, types=types, cursor=cursor)
