"""
test_audiobook.py — тесты модели Audiobook.
"""
from tests.conftest import TestAudiobook


class TestAudiobookModel:
    def test_expected_values(self, audiobook):
        assert audiobook.uuid == TestAudiobook.uuid
        assert audiobook.duration == TestAudiobook.duration

    def test_de_json_none(self, client):
        from yandex_book.book.book import Audiobook
        assert Audiobook.de_json({}, client) is None
        assert Audiobook.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.book.book import Audiobook
        assert Audiobook.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.book.book import Audiobook
        ab = Audiobook.de_json({
            'uuid': TestAudiobook.uuid,
            'title': TestAudiobook.title,
            'duration': TestAudiobook.duration,
        }, client)
        assert ab is not None
        assert ab.uuid == TestAudiobook.uuid
        assert ab.duration == TestAudiobook.duration

    def test_de_json_with_narrators(self, client):
        from yandex_book.book.book import Audiobook
        ab = Audiobook.de_json({
            'uuid': 'ab1',
            'title': 'Аудиокнига',
            'narrators': [{'uuid': 'n1', 'name': 'Нарратор'}],
        }, client)
        assert len(ab.narrators) == 1
        assert ab.narrators[0].name == 'Нарратор'

    def test_equality(self):
        from yandex_book.book.book import Audiobook
        a = Audiobook(uuid='ab-1')
        b = Audiobook(uuid='ab-2')
        c = Audiobook(uuid='ab-1')
        assert a != b
        assert a == c
