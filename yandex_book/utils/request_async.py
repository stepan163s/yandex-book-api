"""
utils/request_async.py — асинхронный HTTP-слой.

Автоматически генерируется из utils/request.py скриптом generate_async_version.py.
НЕ редактируйте этот файл вручную — изменения будут перезаписаны.

Отличия от синхронной версии:
  • Использует aiohttp вместо requests
  • Все методы — async def
  • _request_wrapper — async контекстный менеджер
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Optional

import aiohttp

from yandex_book.exceptions import (
    BadRequestError,
    NetworkError,
    NotFoundError,
    TimedOutError,
    UnauthorizedError,
)

JSONType = Dict[str, Any]

_RESERVED = frozenset({
    'type', 'from', 'import', 'class', 'return', 'pass',
    'in', 'is', 'format', 'filter', 'id', 'input', 'list',
    'dict', 'set', 'max', 'min', 'sum', 'map', 'zip',
})

_CAMEL_RE = re.compile(r'(?<=[a-z0-9])([A-Z])')


def _camel_to_snake(name: str) -> str:
    return _CAMEL_RE.sub(r'_\1', name).lower()


class RequestAsync:
    """Асинхронный HTTP-клиент для Bookmate API (aiohttp)."""

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

    GRAPHQL_HEADERS: Dict[str, str] = {
        'Accept': 'multipart/mixed; deferSpec=20220824, application/json',
    }

    def __init__(self, client: Any, timeout: int = 10) -> None:
        self._client = client
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._headers = dict(self.BASE_HEADERS)
        self._session: Optional[aiohttp.ClientSession] = None

    def set_token(self, token: str) -> None:
        self._headers['Auth-Token'] = token

    def set_language(self, language: str) -> None:
        self._headers['App-Language'] = language
        self._headers['App-Locale'] = language

    async def _get_session(self) -> aiohttp.ClientSession:
        """Лениво создаёт и возвращает aiohttp.ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=self._timeout,
            )
        return self._session

    async def close(self) -> None:
        """Закрыть сессию aiohttp. Вызывать в конце работы."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------ #
    # Публичные методы                                                     #
    # ------------------------------------------------------------------ #

    async def get(self, url: str, params: Optional[dict] = None, **kwargs) -> JSONType:
        content = await self._request_wrapper('GET', url, params=params, **kwargs)
        return self._parse(content)

    async def post(self, url: str, data: Optional[dict] = None, **kwargs) -> JSONType:
        content = await self._request_wrapper('POST', url, json=data, **kwargs)
        return self._parse(content)

    async def delete(self, url: str, **kwargs) -> JSONType:
        content = await self._request_wrapper('DELETE', url, **kwargs)
        if not content:
            return {}
        return self._parse(content)

    async def graphql(
        self, url: str, query: str, variables: dict, operation_name: str = 'Query'
    ) -> JSONType:
        payload = {
            'operationName': operation_name,
            'variables': variables,
            'query': query,
        }
        extra_headers = self.GRAPHQL_HEADERS.copy()
        content = await self._request_wrapper(
            'POST', url, json=payload, headers=extra_headers
        )
        return self._parse(content)

    async def retrieve(self, url: str, **kwargs) -> bytes:
        return await self._request_wrapper('GET', url, **kwargs)

    async def download(self, url: str, filepath: str, **kwargs) -> None:
        content = await self.retrieve(url, **kwargs)
        with open(filepath, 'wb') as f:
            f.write(content)

    # ------------------------------------------------------------------ #
    # Внутренние методы                                                    #
    # ------------------------------------------------------------------ #

    async def _request_wrapper(self, method: str, url: str, **kwargs) -> bytes:
        extra_headers = kwargs.pop('headers', {})
        session = await self._get_session()

        request_headers = dict(self._headers)
        request_headers.update(extra_headers)

        try:
            async with session.request(
                method, url, headers=request_headers, **kwargs
            ) as resp:
                content = await resp.read()
                status = resp.status

        except asyncio.TimeoutError as exc:
            raise TimedOutError('Запрос превысил таймаут') from exc
        except aiohttp.ClientConnectionError as exc:
            raise NetworkError(f'Ошибка соединения: {exc}') from exc
        except aiohttp.ClientError as exc:
            raise NetworkError(str(exc)) from exc

        if not (200 <= status <= 299):
            message = self._extract_error(content)
            if status in (401, 403):
                raise UnauthorizedError(message)
            if status == 400:
                raise BadRequestError(message)
            if status == 404:
                raise NotFoundError(message)
            raise NetworkError(f'HTTP {status}: {message}')

        return content

    def _extract_error(self, content: bytes) -> str:
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
        if not content:
            return {}
        return json.loads(content, object_hook=self._normalize_keys)

    @staticmethod
    def _normalize_keys(obj: dict) -> dict:
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
