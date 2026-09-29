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

from contextlib import contextmanager
from typing import Any, Dict, Optional

import requests

from yandex_book.exceptions import (
    NetworkError,
    TimedOutError,
)

JSONType = Dict[str, Any]

from yandex_book.utils.json import extract_error, normalize_keys, parse_json, raise_for_status
from yandex_book.utils.download import atomic_download, redirect_request, safe_headers
from requests.structures import CaseInsensitiveDict


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
        self._closed = False
        self._token = None
        self._session = requests.Session()
        self._session.headers.update(self.BASE_HEADERS)

    # ------------------------------------------------------------------ #
    # Настройка авторизации и языка                                        #
    # ------------------------------------------------------------------ #

    def set_token(self, token: str) -> None:
        """Устанавливает Auth-Token для всех последующих запросов."""
        self._token = token

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

    def close(self) -> None:
        self._session.close()
        self._closed = True

    def download(self, url: str, filepath: str, **kwargs) -> None:
        kwargs['stream'] = True
        with atomic_download(filepath) as temporary:
            with self._response('GET', url, **kwargs) as response:
                with open(temporary, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            file.write(chunk)

    @contextmanager
    def _response(self, method: str, url: str, **kwargs):
        if self._closed:
            raise RuntimeError('HTTP-клиент уже закрыт')
        kwargs.setdefault('timeout', self._timeout)
        extra = kwargs.pop('headers', {})
        headers = CaseInsensitiveDict(self._session.headers)
        if self._token:
            headers['Auth-Token'] = self._token
        headers.update(extra)
        allow_redirects = kwargs.pop('allow_redirects', True)
        response = None
        try:
            for attempt in range(11):
                headers = safe_headers(self._client, url, headers)
                response = self._session.request(method, url, headers=headers, allow_redirects=False, **kwargs)
                if (allow_redirects and response.status_code in (301, 302, 303, 307, 308)
                        and response.headers.get('Location')):
                    if attempt == 10:
                        raise NetworkError('Слишком много HTTP-перенаправлений')
                    url, method, headers = redirect_request(
                        response.status_code, method, url, response.headers['Location'], kwargs, headers)
                    response.close()
                    response = None
                    continue
                if not 200 <= response.status_code <= 299:
                    raise_for_status(response.status_code, response.content)
                yield response
                return
        except requests.Timeout as exc:
            raise TimedOutError(f'Запрос превысил таймаут ({self._timeout}с)') from exc
        except requests.RequestException as exc:
            raise NetworkError(str(exc)) from exc
        finally:
            if response is not None:
                response.close()

    def _request_wrapper(self, method: str, url: str, **kwargs) -> bytes:
        with self._response(method, url, **kwargs) as response:
            return response.content

    _extract_error = staticmethod(extract_error)
    _parse = staticmethod(parse_json)
    _normalize_keys = staticmethod(normalize_keys)
