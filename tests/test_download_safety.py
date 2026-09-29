import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

from yandex_book import NetworkError, Person, YandexBookClient, YandexBookClientAsync
from yandex_book.utils.download import safe_headers


@pytest.fixture
def servers():
    calls = []
    payload = b'image data'
    target = None

    def handler(name):
        class Handler(BaseHTTPRequestHandler):
            def respond(self):
                path = urlparse(self.path).path
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                calls.append((name, self.command, self.path, dict(self.headers), body))
                if path in ('/redirect', '/post-redirect', '/local-redirect', '/loop'):
                    destination = target + '/file' if path in ('/redirect', '/post-redirect') else ('/loop' if path == '/loop' else '/file')
                    self.send_response(303 if path == '/post-redirect' else 302)
                    self.send_header('Location', destination)
                    self.end_headers()
                else:
                    self.send_response(200)
                    content = payload
                    if path.startswith('/authors/'):
                        content = b'{"books":[{"uuid":"book1","title":"Test"}]}'
                    self.send_header('Content-Length', str(100000 if path == '/broken' else len(content)))
                    self.end_headers()
                    self.wfile.write(content)
            do_GET = respond
            do_POST = respond
            def log_message(self, *_):
                pass
        return Handler

    source = ThreadingHTTPServer(('127.0.0.1', 0), handler('source'))
    external = ThreadingHTTPServer(('127.0.0.1', 0), handler('external'))
    target = f'http://127.0.0.1:{external.server_port}'
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (source, external)]
    for thread in threads:
        thread.start()
    yield f'http://127.0.0.1:{source.server_port}', target, calls, payload
    for server in (source, external):
        server.shutdown()
        server.server_close()
    for thread in threads:
        thread.join()


def token(headers):
    return next((value for key, value in headers.items() if key.lower() == 'auth-token'), None)


def test_token_is_limited_to_api_origins_sync(servers, tmp_path):
    source, external, calls, payload = servers
    with YandexBookClient('dummy-token') as client:
        client.base_url = source
        destination = tmp_path / 'direct'
        destination.write_bytes(b'old')
        client.download_file(external + '/file', str(destination))
        assert destination.read_bytes() == payload
        assert token(calls[-1][3]) is None
        client.download_file(source + '/redirect', str(tmp_path / 'redirected'))
        assert token(calls[-2][3]) == 'dummy-token'
        assert token(calls[-1][3]) is None
        client.download_file(source + '/local-redirect', str(tmp_path / 'local'))
        assert token(calls[-1][3]) == 'dummy-token'


@pytest.mark.asyncio
async def test_token_is_limited_to_api_origins_async(servers, tmp_path):
    source, external, calls, payload = servers
    async with YandexBookClientAsync('dummy-token') as client:
        client.base_url = source
        destination = tmp_path / 'direct'
        destination.write_bytes(b'old')
        await client.download_file(external + '/file', str(destination))
        assert destination.read_bytes() == payload
        assert token(calls[-1][3]) is None
        await client.download_file(source + '/redirect', str(tmp_path / 'redirected'))
        assert token(calls[-2][3]) == 'dummy-token'
        assert token(calls[-1][3]) is None
        await client.download_file(source + '/local-redirect', str(tmp_path / 'local'))
        assert token(calls[-1][3]) == 'dummy-token'


@pytest.mark.parametrize('url', [
    'http://api.bookmate.yandex.net/file',
    'https://api.bookmate.yandex.net.evil.test/file',
    'https://api.bookmate.yandex.net:8443/file',
])
def test_no_token_on_downgrade_or_similar_host(url):
    assert token(safe_headers(None, url, {'auth-token': 'dummy-token'})) is None


@pytest.mark.parametrize('existing', [False, True])
def test_broken_download_preserves_destination_sync(servers, tmp_path, existing):
    source, _, _, _ = servers
    destination = tmp_path / 'file'
    if existing:
        destination.write_bytes(b'original')
    with YandexBookClient() as client:
        with pytest.raises(NetworkError):
            client.download_file(source + '/broken', str(destination))
    assert destination.read_bytes() == b'original' if existing else not destination.exists()
    assert not list(tmp_path.glob('*.part'))
    assert not list(tmp_path.glob('.*.part'))


@pytest.mark.asyncio
@pytest.mark.parametrize('existing', [False, True])
async def test_broken_download_preserves_destination_async(servers, tmp_path, existing):
    source, _, _, _ = servers
    destination = tmp_path / 'file'
    if existing:
        destination.write_bytes(b'original')
    async with YandexBookClientAsync() as client:
        with pytest.raises(NetworkError):
            await client.download_file(source + '/broken', str(destination))
    assert destination.read_bytes() == b'original' if existing else not destination.exists()
    assert not list(tmp_path.glob('.*.part'))


def test_redirect_method_and_limit_sync(servers):
    source, _, calls, _ = servers
    with YandexBookClient('dummy-token') as client:
        client.base_url = source
        with client._request._response('POST', source + '/post-redirect', json={'hello': 'world'}) as response:
            assert response.content == b'image data'
        assert calls[-1][1] == 'GET'
        assert calls[-1][4] == b''
        with pytest.raises(NetworkError, match='перенаправлений'):
            client._request.retrieve(source + '/loop')


@pytest.mark.asyncio
async def test_redirect_method_and_limit_async(servers):
    source, _, calls, _ = servers
    async with YandexBookClientAsync('dummy-token') as client:
        client.base_url = source
        async with client._request._response('POST', source + '/post-redirect', json={'hello': 'world'}) as response:
            assert await response.read() == b'image data'
        assert calls[-1][1] == 'GET'
        assert calls[-1][4] == b''
        with pytest.raises(NetworkError, match='перенаправлений'):
            await client._request.retrieve(source + '/loop')


def test_person_books_sync(servers):
    source, _, calls, _ = servers
    with YandexBookClient() as client:
        client.base_url = source
        author = Person(uuid='author1', client=client)
        assert author.fetch_books(role='translator', page=2)[0].uuid == 'book1'
        assert calls[-1][2] == '/authors/author1/books?role=translator&page=2&per_page=20'


@pytest.mark.asyncio
async def test_person_books_async(servers):
    source, _, calls, _ = servers
    async with YandexBookClientAsync() as client:
        client.base_url = source
        author = Person(uuid='author1', client=client)
        assert (await author.fetch_books_async())[0].uuid == 'book1'
        assert 'role=author' in calls[-1][2]


@pytest.mark.asyncio
async def test_cancelled_download_preserves_destination(monkeypatch, tmp_path):
    from contextlib import asynccontextmanager
    started = asyncio.Event()
    destination = tmp_path / 'file'
    destination.write_bytes(b'original')
    class Content:
        async def iter_chunked(self, size):
            yield b'partial'
            started.set()
            await asyncio.Event().wait()
    class Response:
        content = Content()
    @asynccontextmanager
    async def response(*args, **kwargs):
        yield Response()
    async with YandexBookClientAsync() as client:
        monkeypatch.setattr(client._request, '_response', response)
        task = asyncio.create_task(client.download_file('https://example.test/file', str(destination)))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert destination.read_bytes() == b'original'
    assert not list(tmp_path.glob('.*.part'))
