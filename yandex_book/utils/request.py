"""
utils/request.py — синхронный HTTP-слой.

Изолирует весь HTTP от бизнес-логики. Клиент не использует requests напрямую —
только через self._request.

Ключевые возможности:
  • Нормализация ключей JSON: camelCase / kebab-case → snake_case (object_hook)
  • Единая точка обработки ошибок (_request_wrapper)
  • Bookmate-специфичные заголовки
  • Поддержка Auth-Token авторизации
  • GraphQL-метод для api-gateway.bookmate.yandex.net
  • download() для скачивания файлов
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import requests

from yandex_book.exceptions import (
    BadRequestError,
    NetworkError,
    NotFoundError,
    TimedOutError,
    UnauthorizedError,
)

JSONType = Dict[str, Any]

# Ключевые слова Python, конфликтующие с именами полей.
# При нормализации JSON-ключей добавляем _ в конец.
_RESERVED = frozenset({
    'type', 'from', 'import', 'class', 'return', 'pass',
    'in', 'is', 'format', 'filter', 'id', 'input', 'list',
    'dict', 'set', 'max', 'min', 'sum', 'map', 'zip',
})

# Regex для преобразования camelCase → snake_case.
# Пример: bookUuid → book_uuid, listenerCount → listener_count
_CAMEL_RE = re.compile(r'(?<=[a-z0-9])([A-Z])')


def _camel_to_snake(name: str) -> str:
    return _CAMEL_RE.sub(r'_\1', name).lower()


class Request:
    """Синхронный HTTP-клиент для Bookmate API.

    Используется как self._request в YandexBookClient.
    """

    # Базовые заголовки, имитирующие Android-клиент Bookmate.
    BASE_HEADERS: Dict[str, str] = {
        'Accept-Encoding': 'gzip',
        'App-Language': 'ru',
        'App-Locale': 'ru',
        'App-Platform': 'android',
        'Bookmate-Version': '20200305',
        'Device-Os': 'Android',
        'User-Agent': 'okhttp/4.12.0',
        'Content-Type': 'application/json',
    }

    # Дополнительный заголовок для GraphQL-эндпоинта.
    GRAPHQL_HEADERS: Dict[str, str] = {
        'Accept': 'multipart/mixed; deferSpec=20220824, application/json',
    }

    def __init__(self, client: Any, timeout: int = 10) -> None:
        self._client = client
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(self.BASE_HEADERS)

    # ------------------------------------------------------------------ #
    # Настройка авторизации и языка                                        #
    # ------------------------------------------------------------------ #

    def set_token(self, token: str) -> None:
        """Устанавливает Auth-Token для всех последующих запросов."""
        self._session.headers['Auth-Token'] = token

    def set_language(self, language: str) -> None:
        """Устанавливает App-Language / App-Locale."""
        self._session.headers['App-Language'] = language
        self._session.headers['App-Locale'] = language

    # ------------------------------------------------------------------ #
    # Публичные методы                                                     #
    # ------------------------------------------------------------------ #

    def get(self, url: str, params: Optional[dict] = None, **kwargs) -> JSONType:
        """GET-запрос → нормализованный dict."""
        content = self._request_wrapper('GET', url, params=params, **kwargs)
        return self._parse(content)

    def post(self, url: str, data: Optional[dict] = None, **kwargs) -> JSONType:
        """POST-запрос с JSON-телом → нормализованный dict."""
        content = self._request_wrapper('POST', url, json=data, **kwargs)
        return self._parse(content)

    def delete(self, url: str, **kwargs) -> JSONType:
        """DELETE-запрос → нормализованный dict (или пустой dict при 204)."""
        content = self._request_wrapper('DELETE', url, **kwargs)
        if not content:
            return {}
        return self._parse(content)

    def graphql(self, url: str, query: str, variables: dict,
                operation_name: str = 'Query') -> JSONType:
        """GraphQL POST-запрос → нормализованный dict.

        Не нормализует ключи в секции __typename и переданных variables,
        только ключи ответа API.
        """
        payload = {
            'operationName': operation_name,
            'variables': variables,
            'query': query,
        }
        extra_headers = self.GRAPHQL_HEADERS.copy()
        content = self._request_wrapper(
            'POST', url, json=payload, headers=extra_headers
        )
        return self._parse(content)

    def retrieve(self, url: str, **kwargs) -> bytes:
        """GET-запрос → сырые байты (без JSON-парсинга).

        Используется для скачивания медиафайлов.
        """
        return self._request_wrapper('GET', url, **kwargs)

    def download(self, url: str, filepath: str, **kwargs) -> None:
        """Скачивает файл по URL и сохраняет в filepath."""
        content = self.retrieve(url, stream=True, **kwargs)
        with open(filepath, 'wb') as f:
            f.write(content)

    # ------------------------------------------------------------------ #
    # Внутренние методы                                                    #
    # ------------------------------------------------------------------ #

    def _request_wrapper(self, method: str, url: str, **kwargs) -> bytes:
        """Единая точка выполнения HTTP-запроса и обработки ошибок."""
        kwargs.setdefault('timeout', self._timeout)

        # Merge extra headers without overwriting session headers.
        extra = kwargs.pop('headers', {})
        if extra:
            merged = dict(self._session.headers)
            merged.update(extra)
            kwargs['headers'] = merged

        try:
            resp = self._session.request(method, url, **kwargs)
        except requests.Timeout as exc:
            raise TimedOutError(f'Запрос превысил таймаут ({self._timeout}с)') from exc
        except requests.ConnectionError as exc:
            raise NetworkError(f'Ошибка соединения: {exc}') from exc
        except requests.RequestException as exc:
            raise NetworkError(str(exc)) from exc

        if not (200 <= resp.status_code <= 299):
            message = self._extract_error(resp.content)
            if resp.status_code in (401, 403):
                raise UnauthorizedError(message)
            if resp.status_code == 400:
                raise BadRequestError(message)
            if resp.status_code == 404:
                raise NotFoundError(message)
            raise NetworkError(f'HTTP {resp.status_code}: {message}')

        return resp.content

    def _extract_error(self, content: bytes) -> str:
        """Извлекает сообщение об ошибке из тела ответа."""
        try:
            data = json.loads(content)
            return (
                data.get('message')
                or data.get('error')
                or data.get('errors', [{}])[0].get('message', '')
                or 'Unknown error'
            )
        except Exception:
            return content.decode('utf-8', errors='replace') or 'Unknown error'

    def _parse(self, content: bytes) -> JSONType:
        """JSON-парсинг с нормализацией ключей за один проход."""
        if not content:
            return {}
        return json.loads(content, object_hook=self._normalize_keys)

    @staticmethod
    def _normalize_keys(obj: dict) -> dict:
        """Нормализует ключи JSON во время парсинга.

        Преобразования (в порядке):
          1. kebab-case → snake_case  (book-uuid → book_uuid)
          2. camelCase  → snake_case  (bookUuid  → book_uuid)
          3. lower()                  (LANG → lang)
          4. reserved → reserved_    (type → type_)
          5. _0field   → _0field     (0field → _0field, если начинается с цифры)
        """
        result: dict = {}
        for key, value in obj.items():
            key = key.replace('-', '_')
            key = _camel_to_snake(key)
            key = key.lower()
            if key in _RESERVED:
                key += '_'
            if key and key[0].isdigit():
                key = '_' + key
            result[key] = value
        return result
