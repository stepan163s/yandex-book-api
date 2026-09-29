"""Асинхронный HTTP-слой на aiohttp; поддерживается отдельно от клиента."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import aiohttp
import aiofiles
from multidict import CIMultiDict

from yandex_book.exceptions import (
    NetworkError,
    TimedOutError,
)

JSONType = Dict[str, Any]

from yandex_book.utils.json import extract_error, normalize_keys, parse_json, raise_for_status
from yandex_book.utils.download import atomic_download, redirect_request, safe_headers


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
        self._closed = False

    def set_token(self, token: str) -> None:
        self._headers['Auth-Token'] = token

    def set_language(self, language: str) -> None:
        self._headers['App-Language'] = language
        self._headers['App-Locale'] = language

    async def _get_session(self) -> aiohttp.ClientSession:
        """Лениво создаёт и возвращает aiohttp.ClientSession."""
        if self._closed:
            raise RuntimeError('HTTP-клиент уже закрыт')
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={key: value for key, value in self._headers.items() if key.lower() != 'auth-token'},
                timeout=self._timeout,
            )
        return self._session

    async def close(self) -> None:
        """Закрыть сессию aiohttp. Вызывать в конце работы."""
        self._closed = True
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
        with atomic_download(filepath) as temporary:
            async with self._response('GET', url, **kwargs) as response:
                async with aiofiles.open(temporary, 'wb') as file:
                    async for chunk in response.content.iter_chunked(65536):
                        await file.write(chunk)

    @asynccontextmanager
    async def _response(self, method: str, url: str, **kwargs):
        extra_headers = kwargs.pop('headers', {})
        session = await self._get_session()
        headers = CIMultiDict(self._headers)
        headers.update(extra_headers)
        allow_redirects = kwargs.pop('allow_redirects', True)
        timeout = kwargs.get('timeout', self._timeout)
        if not isinstance(timeout, aiohttp.ClientTimeout):
            timeout = aiohttp.ClientTimeout(total=timeout)
        deadline = asyncio.get_running_loop().time() + timeout.total if timeout.total else None
        try:
            for attempt in range(11):
                if deadline is not None:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError()
                    kwargs['timeout'] = aiohttp.ClientTimeout(
                        total=remaining, connect=timeout.connect,
                        sock_read=timeout.sock_read, sock_connect=timeout.sock_connect,
                    )
                headers = safe_headers(self._client, url, headers)
                async with session.request(method, url, headers=headers, allow_redirects=False, **kwargs) as response:
                    if (allow_redirects and response.status in (301, 302, 303, 307, 308)
                            and response.headers.get('Location')):
                        if attempt == 10:
                            raise NetworkError('Слишком много HTTP-перенаправлений')
                        url, method, headers = redirect_request(
                            response.status, method, str(response.url), response.headers['Location'], kwargs, headers)
                        continue
                    if not 200 <= response.status <= 299:
                        raise_for_status(response.status, await response.read())
                    yield response
                    return
        except asyncio.TimeoutError as exc:
            raise TimedOutError('Запрос превысил таймаут') from exc
        except aiohttp.ClientError as exc:
            raise NetworkError(str(exc)) from exc

    async def _request_wrapper(self, method: str, url: str, **kwargs) -> bytes:
        async with self._response(method, url, **kwargs) as response:
            return await response.read()

    _extract_error = staticmethod(extract_error)
    _parse = staticmethod(parse_json)
    _normalize_keys = staticmethod(normalize_keys)
