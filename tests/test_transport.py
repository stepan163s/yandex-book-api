import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from yandex_book import (
    Audiobook, Book, Comicbook,
    BadRequestError, EndpointGoneError, IdMissingError, InvalidOptionError, NetworkError, NotFoundError, TimedOutError,
    UnauthorizedError, YandexBookClient, YandexBookClientAsync,
)
from yandex_book.utils.request import Request


@pytest.fixture
def api_server():
    calls = []
    payload = b'a' * 200000

    class Handler(BaseHTTPRequestHandler):
        def respond(self):
            path = urlparse(self.path).path
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            calls.append((self.command, self.path, dict(self.headers), body))
            status = 200
            if path.startswith('/error/'):
                status = int(path.rsplit('/', 1)[1])
                content = json.dumps({'message': 'test error'}).encode()
            elif path == '/profile':
                content = b'{"user":{"id":123,"login":"test","followersCount":5}}'
            elif path == '/profile/library_cards':
                params = parse_qs(urlparse(self.path).query)
                size = int(params.get('per_page', [20])[0])
                page = int(params.get('page', [1])[0])
                cards = [{'uuid':f'card{i}', 'book':{'uuid':f'book{i}', 'title':'Test'}} for i in range(1, 8)]
                content = json.dumps({'library_cards':cards[(page-1)*size:page*size]}).encode()
            elif path == '/profile/reading_achievements' or path.endswith('/reading_achievements'):
                status = 410
                content = b'{"error":{"code":410}}'
            elif path == '/file':
                content = payload
            elif path == '/invalid-json':
                content = b'<html>upstream error</html>'
            elif path == '/invalid-encoding':
                content = b'\xff'
            elif path == '/json-array':
                content = b'[]'
            elif path == '/json-null':
                content = b'null'
            elif path.endswith('/impressions'):
                content = b'{"impressions":[{"uuid":"review1","content":"Review"}]}'
            elif path == '/metadata_secret':
                content = b'{"secret":"private-metadata-value"}'
            elif path == '/graphql-errors':
                content = b'{"errors":[{"message":"Partial failure"}],"data":{"search":{"page":[]}}}'
            elif self.command == 'DELETE':
                status, content = 204, b''
            else:
                content = b'{"data":{"search":{"page":{"__typename":"Book","hasNextPage":true}}}}'
            self.send_response(status)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        do_GET = respond
        do_POST = respond
        do_DELETE = respond

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}', calls, payload
    server.shutdown()
    server.server_close()
    thread.join()


def test_response_to_model_and_request_parameters(api_server):
    url, calls, _ = api_server
    with YandexBookClient('test-token') as client:
        client.base_url = url
        me = client.get_profile()
        assert (me.id, me.login, me.followers_count) == (123, 'test', 5)
        assert me.to_dict()['id'] == 123
        cards = client.get_my_library(limit=3, offset=6)
        assert cards[0].book.uuid == 'book7'
        assert calls[-1][1] == '/profile/library_cards?page=3&per_page=3'
        assert client.remove_book('card1') is True
    assert client._request._closed


@pytest.mark.parametrize('model,route', [
    (Book, 'books'), (Audiobook, 'audiobooks'), (Comicbook, 'comicbooks'),
])
def test_model_impressions_use_content_route(api_server, model, route):
    url, calls, _ = api_server
    with YandexBookClient() as client:
        client.base_url = url
        reviews = model(uuid='item1', client=client).fetch_impressions()
        assert reviews[0].uuid == 'review1'
        assert calls[-1][1] == f'/{route}/item1/impressions'


@pytest.mark.asyncio
@pytest.mark.parametrize('model,route', [
    (Book, 'books'), (Audiobook, 'audiobooks'), (Comicbook, 'comicbooks'),
])
async def test_async_model_impressions_use_content_route(api_server, model, route):
    url, calls, _ = api_server
    async with YandexBookClientAsync() as client:
        client.base_url = url
        reviews = await model(uuid='item1', client=client).fetch_impressions_async()
        assert reviews[0].uuid == 'review1'
        assert calls[-1][1] == f'/{route}/item1/impressions'


@pytest.mark.parametrize('path', ['/invalid-json', '/invalid-encoding', '/json-array', '/json-null'])
def test_invalid_json_is_network_error(api_server, path):
    url, _, _ = api_server
    with YandexBookClient() as client:
        with pytest.raises(NetworkError, match='JSON'):
            client._request.get(url + path)


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['/invalid-json', '/invalid-encoding', '/json-array', '/json-null'])
async def test_async_invalid_json_is_network_error(api_server, path):
    url, _, _ = api_server
    async with YandexBookClientAsync() as client:
        with pytest.raises(NetworkError, match='JSON'):
            await client._request.get(url + path)


def test_debug_log_excludes_private_result(api_server, caplog):
    url, _, _ = api_server
    with caplog.at_level(logging.DEBUG, logger='yandex_book.client'):
        with YandexBookClient() as client:
            client.base_url = url
            assert client.get_metadata_secret()['secret'] == 'private-metadata-value'
    assert 'get_metadata_secret' in caplog.text
    assert 'private-metadata-value' not in caplog.text


@pytest.mark.asyncio
async def test_async_debug_log_excludes_private_result(api_server, caplog):
    url, _, _ = api_server
    with caplog.at_level(logging.DEBUG, logger='yandex_book.client_async'):
        async with YandexBookClientAsync() as client:
            client.base_url = url
            assert (await client.get_metadata_secret())['secret'] == 'private-metadata-value'
    assert 'get_metadata_secret' in caplog.text
    assert 'private-metadata-value' not in caplog.text


def test_graphql_errors_preserve_partial_data(api_server):
    url, _, _ = api_server
    with YandexBookClient() as client:
        client.graphql_url = url + '/graphql-errors'
        result = client.search('query')
        assert result['errors'][0]['message'] == 'Partial failure'
        assert result['data']['search']['page'] == []


@pytest.mark.asyncio
async def test_async_graphql_errors_preserve_partial_data(api_server):
    url, _, _ = api_server
    async with YandexBookClientAsync() as client:
        client.graphql_url = url + '/graphql-errors'
        result = await client.search('query')
        assert result['errors'][0]['message'] == 'Partial failure'
        assert result['data']['search']['page'] == []


@pytest.mark.asyncio
async def test_async_response_to_model_and_cleanup(api_server, tmp_path):
    url, calls, payload = api_server
    async with YandexBookClientAsync('test-token') as client:
        client.base_url = url
        client.graphql_url = url + '/graphql'
        me = await client.get_profile()
        assert me.id == 123
        assert (await client.init()).account_uuid == '123'
        assert client.account_login == 'test'
        assert (await client.get_my_library())[0].book.uuid == 'book1'
        assert await client.remove_book('card1') is True
        result = await client.search_books('query')
        assert result['data']['search']['page']['has_next_page'] is True
        assert calls[-1][2]['Auth-Token'] == 'test-token'
        destination = tmp_path / 'download'
        await client.download_file(url + '/file', str(destination))
        assert destination.read_bytes() == payload
    assert client._request._session.closed
    with pytest.raises(RuntimeError, match='закрыт'):
        await client.get_profile()


@pytest.mark.parametrize('status,error', [
    (400, BadRequestError), (401, UnauthorizedError), (403, UnauthorizedError),
    (404, NotFoundError), (410, EndpointGoneError), (429, NetworkError), (500, NetworkError),
])
def test_http_errors(api_server, status, error):
    url, _, _ = api_server
    with YandexBookClient() as client:
        with pytest.raises(error, match='410' if status == 410 else 'test error'):
            client._request.get(f'{url}/error/{status}')


@pytest.mark.asyncio
@pytest.mark.parametrize('status,error', [
    (400, BadRequestError), (401, UnauthorizedError), (403, UnauthorizedError),
    (404, NotFoundError), (410, EndpointGoneError), (429, NetworkError), (500, NetworkError),
])
async def test_async_http_errors(api_server, status, error):
    url, _, _ = api_server
    async with YandexBookClientAsync() as client:
        with pytest.raises(error, match='410' if status == 410 else 'test error'):
            await client._request.get(f'{url}/error/{status}')


def test_graphql_preserves_headers_and_payload(api_server):
    url, calls, _ = api_server
    with YandexBookClient('test-token', language='en') as client:
        client.graphql_url = url + '/graphql'
        result = client.search('query')
        assert result['data']['search']['page']['__typename'] == 'Book'
        method, _, headers, body = calls[-1]
        assert method == 'POST'
        assert headers['Auth-Token'] == 'test-token'
        assert headers['App-Language'] == 'en'
        assert json.loads(body)['variables']['query']['noMisspell'] is False


def test_download_never_reads_entire_success_response(monkeypatch, tmp_path):
    class StreamResponse:
        status_code = 200
        closed = False

        @property
        def content(self):
            raise AssertionError('streaming must not read response.content')

        def iter_content(self, chunk_size):
            assert chunk_size == 65536
            yield b'one'
            yield b''
            yield b'two'

        def close(self):
            self.closed = True

    response = StreamResponse()
    with YandexBookClient() as client:
        def request(*_args, **kwargs):
            assert kwargs['stream'] is True
            return response
        monkeypatch.setattr(client._request._session, 'request', request)
        destination = tmp_path / 'file'
        client.download_file('https://example.test/file', str(destination))
        assert destination.read_bytes() == b'onetwo'
    assert response.closed


def test_timeout_is_not_treated_as_invalid_token(monkeypatch):
    with YandexBookClient() as client:
        def timeout(*_args, **_kwargs):
            raise requests.Timeout('test')
        monkeypatch.setattr(client._request._session, 'request', timeout)
        with pytest.raises(TimedOutError):
            client.test_token()


@pytest.mark.asyncio
async def test_async_timeout_and_close_before_first_request(monkeypatch):
    client = YandexBookClientAsync()
    class ResponseContext:
        async def __aenter__(self):
            raise asyncio.TimeoutError()
        async def __aexit__(self, *args):
            pass
    class Session:
        def request(self, *args, **kwargs):
            return ResponseContext()
    async def session():
        return Session()
    monkeypatch.setattr(client._request, '_get_session', session)
    with pytest.raises(TimedOutError):
        await client.test_token()
    await client.close()
    untouched = YandexBookClientAsync()
    await untouched.close()
    await untouched.close()
    with pytest.raises(RuntimeError):
        await untouched.get_profile()


def test_normalization_preserves_builtins_and_handles_keywords():
    request = Request(None)
    try:
        parsed = request._parse(b'{"id":7,"type":"book","class":"test","bookUuid":"b1"}')
        assert parsed == {'id': 7, 'type': 'book', 'class_': 'test', 'book_uuid': 'b1'}
    finally:
        request.close()


def test_sync_context_closes_on_exception():
    client = YandexBookClient()
    with pytest.raises(ValueError):
        with client:
            raise ValueError('test')
    assert client._request._closed
    with pytest.raises(RuntimeError, match='закрыт'):
        client.get_profile()


@pytest.mark.asyncio
async def test_async_context_closes_on_exception(api_server):
    url, _, _ = api_server
    client = YandexBookClientAsync()
    with pytest.raises(ValueError):
        async with client:
            client.base_url = url
            await client.get_profile()
            raise ValueError('test')
    assert client._request._session.closed


@pytest.mark.asyncio
async def test_async_download_never_reads_entire_response(api_server, monkeypatch, tmp_path):
    import aiohttp
    url, _, payload = api_server
    async def forbid_read(_self):
        raise AssertionError('streaming must not call response.read()')
    monkeypatch.setattr(aiohttp.ClientResponse, 'read', forbid_read)
    async with YandexBookClientAsync() as client:
        destination = tmp_path / 'file'
        await client.download_file(url + '/file', str(destination))
        assert destination.read_bytes() == payload


@pytest.mark.parametrize('limit,offset', [(1,0), (3,1), (3,3), (3,5), (3,6), (3,7), (3,8)])
def test_library_legacy_pagination_returns_exact_slice(api_server, limit, offset):
    url, calls, _ = api_server
    with YandexBookClient() as client:
        client.base_url = url
        cards = client.get_my_library(limit=limit, offset=offset)
    assert [card.uuid for card in cards] == [f'card{i}' for i in range(1,8)][offset:offset+limit]
    assert all('limit=' not in call[1] and 'offset=' not in call[1] for call in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('limit,offset', [(3,1), (3,5), (3,8)])
async def test_async_library_legacy_pagination_returns_exact_slice(api_server, limit, offset):
    url, calls, _ = api_server
    async with YandexBookClientAsync() as client:
        client.base_url = url
        cards = await client.get_my_library(limit=limit, offset=offset)
    assert [card.uuid for card in cards] == [f'card{i}' for i in range(1,8)][offset:offset+limit]
    assert all('limit=' not in call[1] and 'offset=' not in call[1] for call in calls)


def test_library_page_pagination(api_server):
    url, calls, _ = api_server
    with YandexBookClient() as client:
        client.base_url = url
        assert [card.uuid for card in client.get_my_library(page=2, per_page=2)] == ['card3','card4']
        assert calls[-1][1] == '/profile/library_cards?page=2&per_page=2'
        assert len(client.get_my_library()) == 7
        assert calls[-1][1] == '/profile/library_cards?page=1&per_page=20'


@pytest.mark.asyncio
async def test_async_library_page_pagination(api_server):
    url, calls, _ = api_server
    async with YandexBookClientAsync() as client:
        client.base_url = url
        assert [card.uuid for card in await client.get_my_library(page=2, per_page=2)] == ['card3','card4']
        assert calls[-1][1] == '/profile/library_cards?page=2&per_page=2'


@pytest.mark.parametrize('kwargs', [
    {'limit':0}, {'limit':101}, {'offset':-1}, {'offset':1.5}, {'offset':True},
    {'page':0}, {'per_page':101}, {'page':True}, {'per_page':1.5},
    {'limit':3,'page':2}, {'offset':1,'per_page':3},
])
def test_library_rejects_invalid_pagination(kwargs):
    with YandexBookClient() as client:
        with pytest.raises(InvalidOptionError):
            client.get_my_library(**kwargs)


@pytest.mark.parametrize('method,route', [
    ('get_user',''), ('get_user_books','/books'), ('get_user_audiobooks','/audiobooks'),
    ('get_user_comics','/comicbooks'), ('get_user_bookshelves','/bookshelves'),
    ('get_user_followings','/followings'), ('get_user_impressions','/impressions'),
    ('get_user_quotes','/quotes'), ('get_series_following','/series/following'),
])
def test_current_numeric_user_id_resolves_login(api_server, method, route):
    url, calls, _ = api_server
    with YandexBookClient('test-token') as client:
        client.base_url = url
        getattr(client,method)(123)
        assert urlparse(calls[-1][1]).path == '/users/test'+route
        assert calls[0][1] == '/profile'
        before = len(calls)
        getattr(client,method)(123)
        assert len(calls) == before+1
        assert client.account_login == 'test'


@pytest.mark.asyncio
@pytest.mark.parametrize('method,route', [
    ('get_user_books','/books'), ('get_user_audiobooks','/audiobooks'),
    ('get_series_following','/series/following'),
])
async def test_async_current_numeric_user_id_resolves_login(api_server, method, route):
    url, calls, _ = api_server
    async with YandexBookClientAsync('test-token') as client:
        client.base_url = url
        await getattr(client,method)(123)
        assert urlparse(calls[-1][1]).path == '/users/test'+route
        assert calls[0][1] == '/profile'


def test_user_login_is_escaped_and_needs_no_profile(api_server):
    url, calls, _ = api_server
    with YandexBookClient() as client:
        client.base_url = url
        client.get_user_books('test/other?x=1')
    assert calls[0][1] == '/users/test%2Fother%3Fx%3D1/books'
    assert len(calls) == 1


def test_unsupported_user_identifiers_are_rejected(api_server):
    url, calls, _ = api_server
    with YandexBookClient() as client:
        with pytest.raises(InvalidOptionError,match='логин'):
            client.get_user(123)
        with pytest.raises(IdMissingError):
            client.get_user(' ')
        with pytest.raises(InvalidOptionError):
            client.get_user(True)
    with YandexBookClient('test-token') as client:
        client.base_url = url
        with pytest.raises(InvalidOptionError,match='другого пользователя'):
            client.get_user(456)
    assert [call[1] for call in calls] == ['/profile']


def test_current_series_uses_profile_login(api_server):
    url, calls, _ = api_server
    with YandexBookClient('test-token') as client:
        client.base_url = url
        client.get_series_following()
    assert [call[1] for call in calls] == ['/profile','/users/test/series/following?page=1&per_page=20']


@pytest.mark.asyncio
async def test_async_current_series_uses_profile_login(api_server):
    url, calls, _ = api_server
    async with YandexBookClientAsync('test-token') as client:
        client.base_url = url
        await client.get_series_following()
    assert [call[1] for call in calls] == ['/profile','/users/test/series/following?page=1&per_page=20']


@pytest.mark.parametrize('method,route', [
    ('get_user_json','/a/4/user.json'),
    ('get_push_notification_restrictions','/a/4/push_notification_settings/restrictions'),
    ('get_emotions','/a/4/d/impressions/emotions'),
])
def test_legacy_routes_use_server_root(api_server,method,route):
    url, calls, _ = api_server
    with YandexBookClient('test-token') as client:
        client.base_url = url+'/api/v5'
        getattr(client,method)()
    assert calls[-1][1] == route
    assert calls[-1][2]['Auth-Token'] == 'test-token'


@pytest.mark.asyncio
@pytest.mark.parametrize('method,route', [
    ('get_user_json','/a/4/user.json'),
    ('get_push_notification_restrictions','/a/4/push_notification_settings/restrictions'),
    ('get_emotions','/a/4/d/impressions/emotions'),
])
async def test_async_legacy_routes_use_server_root(api_server,method,route):
    url, calls, _ = api_server
    async with YandexBookClientAsync('test-token') as client:
        client.base_url = url+'/api/v5'
        await getattr(client,method)()
    assert calls[-1][1] == route
    assert calls[-1][2]['Auth-Token'] == 'test-token'


@pytest.mark.parametrize('method,args', [('get_reading_achievements',()),('get_user_reading_achievements',('test',))])
def test_removed_achievements_have_actionable_error(api_server,method,args):
    url, _, _ = api_server
    with YandexBookClient() as client:
        client.base_url = url
        with pytest.raises(EndpointGoneError,match='get_reading_statistics'):
            getattr(client,method)(*args)


@pytest.mark.asyncio
@pytest.mark.parametrize('method,args', [('get_reading_achievements',()),('get_user_reading_achievements',('test',))])
async def test_async_removed_achievements_have_actionable_error(api_server,method,args):
    url, _, _ = api_server
    async with YandexBookClientAsync() as client:
        client.base_url = url
        with pytest.raises(EndpointGoneError,match='get_reading_statistics'):
            await getattr(client,method)(*args)
