"""
test_quote.py — тесты модели Quote.
"""
from tests.conftest import TestBook, TestQuote


class TestQuoteModel:
    def test_expected_values(self, quote):
        assert quote.cfi == TestQuote.cfi
        assert quote.item_uuid == TestQuote.item_uuid
        assert quote.content == TestQuote.content

    def test_nested_book(self, quote):
        from yandex_book.book.book import Book
        assert isinstance(quote.book, Book)
        assert quote.book.uuid == TestBook.uuid

    def test_equality_uses_cfi_and_item_uuid(self):
        from yandex_book.quote.quote import Quote
        same = Quote(cfi=TestQuote.cfi, item_uuid=TestQuote.item_uuid, content='Другой текст')
        different = Quote(cfi='other-cfi', item_uuid=TestQuote.item_uuid, content=TestQuote.content)
        base = Quote(cfi=TestQuote.cfi, item_uuid=TestQuote.item_uuid)
        assert base == same
        assert base != different
        assert hash(base) == hash(same)

    def test_de_json_none(self, client):
        from yandex_book.quote.quote import Quote
        assert Quote.de_json({}, client) is None
        assert Quote.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.quote.quote import Quote
        assert Quote.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.quote.quote import Quote
        q = Quote.de_json({
            'cfi': TestQuote.cfi,
            'item_uuid': TestQuote.item_uuid,
            'content': TestQuote.content,
        }, client)
        assert q is not None
        assert q.cfi == TestQuote.cfi
        assert q.content == TestQuote.content
        assert q.book is None

