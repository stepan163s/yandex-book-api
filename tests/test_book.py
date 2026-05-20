"""
test_book.py — тесты модели Book.
"""
from tests.conftest import TestBook


class TestBookModel:
    def test_expected_values(self, book):
        assert book.uuid == TestBook.uuid
        assert book.title == TestBook.title
        assert book.annotation == TestBook.annotation

    def test_display_title(self, book):
        assert book.display_title == TestBook.title

    def test_display_title_fallback(self):
        from yandex_book.book.book import Book
        b = Book(name='GraphQL Title')
        assert b.display_title == 'GraphQL Title'

    def test_de_json_none(self, client):
        from yandex_book.book.book import Book
        assert Book.de_json({}, client) is None
        assert Book.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.book.book import Book
        assert Book.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.book.book import Book
        b = Book.de_json({'uuid': TestBook.uuid, 'title': TestBook.title}, client)
        assert b is not None
        assert b.uuid == TestBook.uuid
        assert b.title == TestBook.title

    def test_de_json_with_authors(self, client):
        from yandex_book.book.book import Book
        b = Book.de_json({
            'uuid': 'b1',
            'title': 'Тест',
            'authors': [{'uuid': 'a1', 'name': 'Автор'}],
        }, client)
        assert len(b.authors) == 1
        assert b.authors[0].name == 'Автор'

    def test_equality(self):
        from yandex_book.book.book import Book
        a = Book(uuid='book-1')
        b = Book(uuid='book-2')
        c = Book(uuid='book-1')
        assert a != b
        assert a == c

    def test_to_dict(self, book):
        d = book.to_dict()
        assert d['uuid'] == TestBook.uuid
        assert 'client' not in d
