"""
test_library_card.py — тесты модели LibraryCard.
"""
from tests.conftest import TestBook, TestLibraryCard


class TestLibraryCardModel:
    def test_expected_values(self, library_card):
        assert library_card.uuid == TestLibraryCard.uuid
        assert library_card.state == TestLibraryCard.state
        assert library_card.reading_progress == TestLibraryCard.reading_progress
        assert library_card.book is not None
        assert library_card.book.uuid == TestBook.uuid

    def test_de_json(self, client):
        from yandex_book.book.book import LibraryCard
        lc = LibraryCard.de_json({
            'uuid': 'lc-uuid-1',
            'state': 'reading',
            'book': {'uuid': TestBook.uuid, 'title': TestBook.title},
        }, client)
        assert lc.uuid == 'lc-uuid-1'
        assert lc.state == 'reading'
        assert lc.book is not None
        assert lc.book.uuid == TestBook.uuid

    def test_de_json_none(self, client):
        from yandex_book.book.book import LibraryCard
        assert LibraryCard.de_json({}, client) is None
        assert LibraryCard.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.book.book import LibraryCard
        assert LibraryCard.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.book.book import LibraryCard
        lc = LibraryCard.de_json({'uuid': 'lc-1', 'state': 'want_to_read'}, client)
        assert lc is not None
        assert lc.uuid == 'lc-1'
        assert lc.state == 'want_to_read'
        assert lc.book is None

    def test_de_json_with_audiobook(self, client):
        from yandex_book.book.book import LibraryCard
        lc = LibraryCard.de_json({
            'uuid': 'lc-2',
            'audiobook': {'uuid': 'ab-1', 'title': 'Аудио'},
        }, client)
        assert lc.audiobook is not None
        assert lc.audiobook.uuid == 'ab-1'

    def test_equality(self):
        from yandex_book.book.book import LibraryCard
        a = LibraryCard(uuid='lc-1')
        b = LibraryCard(uuid='lc-2')
        c = LibraryCard(uuid='lc-1')
        assert a != b
        assert a == c
