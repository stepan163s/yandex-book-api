import subprocess
import sys

import pytest

from yandex_book import (
    Audiobook, Book, Comicbook, Image, User, Person, LibraryCard, Bookshelf,
    IdMissingError, InvalidOptionError, YandexBookClient,
)


@pytest.mark.parametrize('model', [Book, User, Person, LibraryCard, Bookshelf])
def test_unidentified_objects_keep_their_identity(model):
    a, b = model(), model()
    assert a == a
    assert a != b
    assert len({a, b}) == 2
    assert model(uuid='same') == model(uuid='same')
    assert len({model(uuid='same'), model(uuid='same')}) == 1


def test_mixed_list_keeps_valid_entries():
    books = Book.de_list([None, {}, 123, {'uuid': 'b1'}, 'invalid', {'uuid': 'b2'}], None)
    assert [book.uuid for book in books] == ['b1', 'b2']


@pytest.mark.parametrize('model', [Book, Audiobook, Comicbook])
def test_rest_authors_preserve_text_and_objects(model):
    book = model.de_json({
        'uuid': 'book1', 'authors': 'Автор один, Автор два',
        'authors_objects': [{'uuid': 'a1', 'name': 'Автор один'}, {'uuid': 'a2', 'name': 'Автор два'}],
    }, None)
    assert book.authors_text == 'Автор один, Автор два'
    assert [author.uuid for author in book.authors] == ['a1', 'a2']
    assert book.to_dict()['authors_text'] == 'Автор один, Автор два'
    assert book.authors == book.authors_objects


@pytest.mark.parametrize('model', [Book, Audiobook, Comicbook])
def test_rest_authors_text_without_objects(model):
    book = model.de_json({'uuid': 'book1', 'authors': 'Автор один, Автор два'}, None)
    assert book.authors_text == 'Автор один, Автор два'
    assert book.authors == []


@pytest.mark.parametrize('model', [Book, Audiobook, Comicbook])
def test_graphql_authors_and_string_list(model):
    book = model.de_json({'uuid': 'book1', 'authors': [
        {'uuid': 'a1', 'name': 'Автор один'}, 'Автор два', None, '', 123,
    ]}, None)
    assert [author.name for author in book.authors] == ['Автор один', 'Автор два']
    assert book.authors[0].uuid == 'a1'
    assert book.authors_text is None


@pytest.mark.parametrize('authors', [None, [], ''])
def test_authors_fallback_to_objects(authors):
    book = Book.de_json({'uuid': 'book1', 'authors': authors,
                         'authors_objects': [{'uuid': 'a1', 'name': 'Автор'}]}, None)
    assert book.authors[0].uuid == 'a1'


@pytest.mark.parametrize('model,directory', [(Book, 'books'), (Comicbook, 'comics')])
def test_cover_default_directory_and_return_value(model, directory, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with YandexBookClient() as client:
        class Response:
            status_code = 200
            def iter_content(self, chunk_size):
                yield b'image'
            def close(self):
                pass
        monkeypatch.setattr(client._request._session, 'request', lambda *a, **kw: Response())
        book = model(uuid='b1', cover=Image(large='https://example.test/cover'), client=client)
        path = book.download_cover()
        assert path == f'covers/{directory}/b1_large.jpg'
        assert (tmp_path / path).read_bytes() == b'image'


def test_client_and_identifier_checks():
    with pytest.raises(InvalidOptionError):
        Book(uuid='b1').fetch_impressions()
    with YandexBookClient() as client:
        with pytest.raises(IdMissingError):
            LibraryCard(client=client).remove()
        with pytest.raises(InvalidOptionError):
            Book(uuid='b1', cover=Image(large='url'), client=client).download_cover(size='unknown')
        with pytest.raises(IdMissingError):
            Person(client=client).fetch_books()


def test_checks_survive_optimized_python():
    program = '''from yandex_book import Book, InvalidOptionError, LibraryCard, YandexBookClient, IdMissingError
try:
    Book().fetch_impressions()
except InvalidOptionError:
    pass
else:
    raise RuntimeError("client check was skipped")
with YandexBookClient() as client:
    try:
        LibraryCard(client=client).remove()
    except IdMissingError:
        pass
    else:
        raise RuntimeError("identifier check was skipped")
'''
    result = subprocess.run([sys.executable, '-O', '-c', program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('method,suffix', [
    ('fetch_books','books'), ('fetch_audiobooks','audiobooks'),
    ('fetch_bookshelves','bookshelves'), ('fetch_quotes','quotes'),
    ('fetch_impressions','impressions'), ('fetch_followings','followings'),
])
def test_user_shortcuts_prefer_login_over_old_identifiers(method,suffix,monkeypatch):
    calls=[]
    with YandexBookClient() as client:
        monkeypatch.setattr(client._request,'get',lambda url,**kwargs: calls.append(url) or {})
        user=User(uuid='old-uuid',id=123,login='current-login',client=client)
        assert getattr(user,method)() == []
    assert calls == [f'https://api.bookmate.yandex.net/api/v5/users/current-login/{suffix}']


@pytest.mark.asyncio
@pytest.mark.parametrize('method,suffix', [('fetch_books_async','books'),('fetch_audiobooks_async','audiobooks')])
async def test_async_user_shortcuts_prefer_login(method,suffix,monkeypatch):
    from yandex_book import YandexBookClientAsync
    calls=[]
    async def get(url,**kwargs):
        calls.append(url)
        return {}
    async with YandexBookClientAsync() as client:
        monkeypatch.setattr(client._request,'get',get)
        user=User(uuid='old-uuid',id=123,login='current-login',client=client)
        assert await getattr(user,method)() == []
    assert calls == [f'https://api.bookmate.yandex.net/api/v5/users/current-login/{suffix}']
