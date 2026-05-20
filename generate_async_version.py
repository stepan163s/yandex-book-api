"""
generate_async_version.py — генератор асинхронной версии клиента.

Запуск:
    python generate_async_version.py

Генерирует:
    yandex_book/client_async.py  — async-версия YandexBookClient
    (request_async.py написан вручную — содержит aiohttp-специфику)

Принцип: простые замены строк в исходнике client.py.
Никакого дублирования вручную.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CLIENT_SRC = ROOT / 'yandex_book' / 'client.py'
CLIENT_DST = ROOT / 'yandex_book' / 'client_async.py'

# ---------------------------------------------------------------------------
# Таблица замен: (old, new, is_regex)
#   is_regex=True  → re.sub(old, new, source, MULTILINE)
#   is_regex=False → source.replace(old, new)
#
# ВАЖНО: порядок имеет значение.
# Более специфичные паттерны должны идти ПЕРЕД общими.
# ---------------------------------------------------------------------------

REPLACEMENTS_CLIENT = [
    # ---- Класс и импорт -----------------------------------------------
    ('class YandexBookClient:', 'class YandexBookClientAsync:', False),

    # Docstring класса: синхронный → асинхронный
    ('Синхронный клиент для Bookmate', 'Асинхронный клиент для Bookmate', False),

    (
        'from yandex_book.utils.request import Request',
        'from yandex_book.utils.request_async import RequestAsync as Request',
        False,
    ),

    ('_is_async: bool = False', '_is_async: bool = True', False),

    # ---- Публичные методы → async def --------------------------------
    # Паттерн: ровно 4 пробела + def + имя (не dunder).
    # Работает и для однострочных сигнатур def f(self, ...) и
    # для многострочных def f(\n    self,\n    ...).
    (r'^    def (?!__)([\w]+)\(', r'    async def \1(', True),

    # ---- Декоратор log: wrapper и вызов метода -----------------------
    ('    def wrapper(*args, **kwargs):', '    async def wrapper(*args, **kwargs):', False),
    ('        result = method(*args, **kwargs)', '        result = await method(*args, **kwargs)', False),

    # ---- result = self._request.X( -----------------------------------
    # (специфичные — до общих return/bare вариантов)
    ('result = self._request.get(', 'result = await self._request.get(', False),
    ('result = self._request.post(', 'result = await self._request.post(', False),
    ('result = self._request.delete(', 'result = await self._request.delete(', False),
    ('result = self._request.graphql(', 'result = await self._request.graphql(', False),

    # ---- return self._request.X( -------------------------------------
    # Методы, которые возвращают результат запроса напрямую без result=
    ('return self._request.get(', 'return await self._request.get(', False),
    ('return self._request.post(', 'return await self._request.post(', False),
    ('return self._request.graphql(', 'return await self._request.graphql(', False),

    # ---- Голые вызовы без return и без result= -----------------------
    # remove_book: self._request.delete(url)
    ('        self._request.delete(url)', '        await self._request.delete(url)', False),
    # download_file: self._request.download(url, filepath)
    ('        self._request.download(url, filepath)', '        await self._request.download(url, filepath)', False),

    # ---- Вызовы других async-методов внутри клиента -----------------
    ('self.me = self.get_profile()', 'self.me = await self.get_profile()', False),
    ('result = self.get_profile()', 'result = await self.get_profile()', False),
    ('return self.search(', 'return await self.search(', False),

    # ---- Return annotation -------------------------------------------
    ("-> 'YandexBookClient':", "-> 'YandexBookClientAsync':", False),

    # ---- Хедер файла -------------------------------------------------
    (
        '"""\nclient.py — синхронный клиент Яндекс Книги / Bookmate API.',
        (
            '"""\nclient_async.py — АСИНХРОННЫЙ клиент Яндекс Книги / Bookmate API.\n\n'
            'Автоматически сгенерирован из client.py скриптом generate_async_version.py.\n'
            'НЕ редактируйте этот файл вручную — изменения будут перезаписаны.'
        ),
        False,
    ),
]


def apply_replacements(source: str, replacements: list) -> str:
    for item in replacements:
        old, new = item[0], item[1]
        is_regex = item[2] if len(item) > 2 else False
        if is_regex:
            source = re.sub(old, new, source, flags=re.MULTILINE)
        else:
            source = source.replace(old, new)
    return source


def generate_client_async() -> None:
    if not CLIENT_SRC.exists():
        print(f'Ошибка: {CLIENT_SRC} не найден', file=sys.stderr)
        sys.exit(1)

    source = CLIENT_SRC.read_text(encoding='utf-8')
    result = apply_replacements(source, REPLACEMENTS_CLIENT)

    warning = (
        '# ============================================================\n'
        '# ВНИМАНИЕ: этот файл сгенерирован автоматически.\n'
        '# Источник: yandex_book/client.py\n'
        '# Команда:  python generate_async_version.py\n'
        '# ============================================================\n\n'
    )
    result = warning + result

    CLIENT_DST.write_text(result, encoding='utf-8')
    print(f'Создан: {CLIENT_DST}')


if __name__ == '__main__':
    generate_client_async()
    print('Готово.')
