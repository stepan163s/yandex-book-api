import ast
from pathlib import Path

from generate_async_version import render_async

ROOT = Path(__file__).resolve().parents[1]


def test_async_client_matches_source():
    source = (ROOT / 'yandex_book/client.py').read_text()
    assert render_async(source) == (ROOT / 'yandex_book/client_async.py').read_text()


def test_generator_awaits_new_client_method_calls():
    source = '''from yandex_book.utils.request import Request
class YandexBookClient:
    def __init__(self):
        self._request = Request(self)
    def get_profile(self):
        return self._request.get("url")
    def another(self):
        return self.get_profile()
'''
    tree = ast.parse(render_async(source))
    client = tree.body[-1]
    assert isinstance(client.body[0], ast.FunctionDef)
    assert isinstance(client.body[-1], ast.AsyncFunctionDef)
    assert isinstance(client.body[-1].body[0].value, ast.Await)


def test_generator_rejects_unknown_transport_calls():
    import pytest
    with pytest.raises(ValueError, match='Неизвестный метод HTTP'):
        render_async('class YandexBookClient:\n    def foo(self):\n        return self._request.new_operation()\n')
