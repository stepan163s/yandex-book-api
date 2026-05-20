"""
test_bookshelf.py — тесты модели Bookshelf.
"""
from tests.conftest import TestBookshelf, TestUser


class TestBookshelfModel:
    def test_expected_values(self, bookshelf):
        assert bookshelf.uuid == TestBookshelf.uuid
        assert bookshelf.title == TestBookshelf.title
        assert bookshelf.books_count == TestBookshelf.books_count

    def test_nested_creator(self, bookshelf):
        from yandex_book.user.user import User
        assert isinstance(bookshelf.creator, User)
        assert bookshelf.creator.login == TestUser.login

    def test_de_json_none(self, client):
        from yandex_book.bookshelf.bookshelf import Bookshelf
        assert Bookshelf.de_json({}, client) is None
        assert Bookshelf.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.bookshelf.bookshelf import Bookshelf
        assert Bookshelf.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.bookshelf.bookshelf import Bookshelf
        shelf = Bookshelf.de_json({
            'uuid': TestBookshelf.uuid,
            'title': TestBookshelf.title,
        }, client)
        assert shelf is not None
        assert shelf.uuid == TestBookshelf.uuid
        assert shelf.title == TestBookshelf.title
        assert shelf.creator is None

    def test_de_json_with_creator(self, client):
        from yandex_book.bookshelf.bookshelf import Bookshelf
        shelf = Bookshelf.de_json({
            'uuid': 's1',
            'title': 'Полка',
            'creator': {'uuid': TestUser.uuid, 'login': TestUser.login},
        }, client)
        assert shelf.creator is not None
        assert shelf.creator.uuid == TestUser.uuid

    def test_de_list(self, client):
        from yandex_book.bookshelf.bookshelf import Bookshelf
        data = [
            {'uuid': 's1', 'title': 'Полка 1'},
            {'uuid': 's2', 'title': 'Полка 2'},
        ]
        shelves = Bookshelf.de_list(data, client)
        assert len(shelves) == 2
        assert shelves[0].uuid == 's1'
        assert shelves[1].title == 'Полка 2'

    def test_equality(self):
        from yandex_book.bookshelf.bookshelf import Bookshelf
        a = Bookshelf(uuid='s1')
        b = Bookshelf(uuid='s2')
        c = Bookshelf(uuid='s1')
        assert a != b
        assert a == c
