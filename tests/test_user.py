"""
test_user.py — тесты модели User.
"""
from tests.conftest import TestUser


class TestUserModel:
    def test_expected_values(self, user):
        assert user.uuid == TestUser.uuid
        assert user.id == TestUser.id
        assert user.login == TestUser.login
        assert user.name == TestUser.name

    def test_de_json_none(self, client):
        from yandex_book.user.user import User
        assert User.de_json({}, client) is None
        assert User.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.user.user import User
        assert User.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.user.user import User
        u = User.de_json({'uuid': TestUser.uuid, 'login': TestUser.login}, client)
        assert u is not None
        assert u.uuid == TestUser.uuid
        assert u.login == TestUser.login

    def test_de_json_with_avatar(self, client):
        from yandex_book.user.user import User
        u = User.de_json({
            'uuid': 'u1',
            'login': 'test',
            'avatar': {'large': 'https://cdn.example.com/avatar.jpg'},
        }, client)
        assert u.avatar is not None
        assert u.avatar.large == 'https://cdn.example.com/avatar.jpg'

    def test_equality(self):
        from yandex_book.user.user import User
        a = User(uuid='u1')
        b = User(uuid='u2')
        c = User(uuid='u1')
        assert a != b
        assert a == c

    def test_unknown_fields_ignored(self, client):
        from yandex_book.user.user import User
        u = User.de_json({'uuid': 'u1', 'nonexistent_field': 'value'}, client)
        assert u is not None
        assert u.uuid == 'u1'
        assert not hasattr(u, 'nonexistent_field')
