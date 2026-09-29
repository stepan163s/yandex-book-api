# Yandex Bookmate API

Неофициальный Python-клиент для Яндекс Книг / Bookmate. Python 3.9 и новее.

Клиент предоставляет синхронные и асинхронные методы REST и GraphQL API.
Без токена доступны публичные сведения о книгах и пользователях; личная библиотека,
профиль и другие приватные данные требуют OAuth-токена.

## Установка

```bash
pip install yandex-book-api
```

Для асинхронного клиента:

```bash
pip install "yandex-book-api[async]"
```

Зависимости устанавливаются автоматически из `pyproject.toml`: `requests`,
для Python младше 3.11 — `typing_extensions`. Async-дополнение устанавливает
`aiohttp` и `aiofiles`. Отдельный `requirements.txt` не требуется.

Для разработки из клонированного репозитория:

```bash
python -m pip install -e ".[dev,async]"
```

## Получение токена

### Команда авторизации

После установки библиотеки выполните:

```bash
yandex-book-token
```

Либо запустите модуль:

```bash
python -m yandex_book.auth
```

При работе из репозитория также доступен `python get_token.py`.
Для этого способа используются только стандартные модули Python.

На macOS команда открывает Safari и до 180 секунд ждёт токен в URL активной вкладки.
Не переключайтесь с вкладки авторизации до получения результата. Если macOS запросит
доступ, разрешите процессу, из которого запущен скрипт, управлять Safari.

На Windows и Linux команда открывает браузер по умолчанию и просит вставить полную
ссылку возврата из адресной строки. На macOS ручной ввод используется, если токен
не удалось получить автоматически. Страница с сообщением об ошибке открытия
Букмейта может содержать токен в своём URL — скопируйте адрес целиком.
Используйте вкладку, открытую текущим запуском команды: скрипт проверяет домен
возврата и случайный параметр `state`. Ссылка предыдущего запуска и отдельно
скопированный токен не принимаются. Если браузер не открылся, скрипт выведет
ссылку для текущего запуска; откройте именно её.

Принудительный ручной режим и настройка ожидания:

```bash
yandex-book-token --manual
yandex-book-token --timeout 60
```

Результат — OAuth-токен, обычно начинающийся с `y0_`. Команда выводит его в консоль
и не сохраняет в файл. Дополнительные Python-пакеты для авторизации не нужны;
автоматическое чтение Safari использует системную команду macOS `osascript`.

### Вручную через браузер

Откройте [страницу авторизации Яндекса](https://oauth.yandex.ru/authorize?response_type=token&client_id=4483e97bab6e486a9822973109a14d05)
и войдите в аккаунт. После перенаправления скопируйте значение `access_token`
из URL: оно находится после `#access_token=` и заканчивается перед следующим `&`.
Если токена нет в адресе, используйте команду авторизации.

Токен передаётся в `YandexBookClient(token)`; не публикуйте его и не добавляйте в Git.

## Быстрый старт

Публичные данные:

```python
from yandex_book import YandexBookClient

with YandexBookClient() as client:
    book = client.get_book("mqK3FFjg")
    if book is not None:
        print(book.display_title)
        if book.cover is not None and book.cover.best_url:
            client.download_file(book.cover.best_url, "cover.jpg")
```

Профиль и личная библиотека:

```python
import os
from yandex_book import YandexBookClient

with YandexBookClient(os.environ["YANDEX_BOOK_TOKEN"]) as client:
    me = client.get_profile()
    if me is not None:
        print(me.name, me.login, me.id)
    for card in client.get_my_library(page=1, per_page=10):
        if card.book is not None:
            print(card.book.display_title, card.state)
```

Профиль возвращается как `User | None`, библиотека — как список `LibraryCard`.
`add_book(book_uuid)` возвращает `LibraryCard | None`, а
`remove_book(library_card_uuid)` — `True` после успешного HTTP-запроса.
Получение книги или пользователя возвращает модель либо `None`, если ответ
не содержит соответствующего объекта. HTTP 404 вызывает `NotFoundError`.

## Асинхронный клиент и закрытие сессий

```python
import asyncio
import os
from yandex_book import YandexBookClientAsync

async def main():
    async with YandexBookClientAsync(os.environ["YANDEX_BOOK_TOKEN"]) as client:
        me = await client.get_profile()
        if me is not None:
            books = await client.get_user_books(me.login)
            print(f"{me.name}: {len(books)} книг")

asyncio.run(main())
```

Без контекстного менеджера вызывайте `client.close()` или `await client.close()`
в `finally`. Контекстный менеджер закрывает HTTP-сессию и при исключении.
После закрытия клиент не принимает новые запросы; создайте новый экземпляр.
Скачивание выполняется порциями; асинхронный клиент записывает файл через `aiofiles`.
Каталог назначения создаётся автоматически. Файл сначала записывается во временный
файл рядом с назначением и заменяет его только после успешного завершения загрузки.
При обрыве существующий файл сохраняется. `Auth-Token` передаётся только адресам
API, включая проверку каждого HTTP-перенаправления. При настройке собственных
`base_url` или `graphql_url` их адреса также считаются доверенными.

## Методы клиента

Ниже приведены сигнатуры синхронного клиента. Асинхронный клиент предоставляет те же
методы с `await`, кроме конструктора; для контекстного менеджера используется `async with`.
`init()` загружает профиль в `client.me` и заполняет `client.account_login`.
`account_uuid` сохранён для совместимости; использовать его в пользовательских
маршрутах не следует.

| Метод | Возвращает |
|---|---|
| `close()` | `None` |
| `init()` | `'YandexBookClient'` |
| `get_profile()` | `Optional[User]` |
| `get_counters()` | `Dict[str, Any]` |
| `get_notifications_status()` | `Dict[str, Any]` |
| `get_access_levels()` | `Dict[str, Any]` |
| `get_privacy_settings()` | `Dict[str, Any]` |
| `get_sync_state()` | `Dict[str, Any]` |
| `get_context()` | `Dict[str, Any]` |
| `get_metadata_secret()` | `Dict[str, Any]` |
| `get_user_json()` | `Dict[str, Any]` |
| `get_push_notification_restrictions()` | `Dict[str, Any]` |
| `get_features(feature_names: Optional[List[str]]=None)` | `Dict[str, Any]` |
| `get_user(user_id: Union[int, str])` | `Optional[User]` |
| `get_user_books(user_id: Union[int, str])` | `List[Book]` |
| `get_user_audiobooks(user_id: Union[int, str])` | `List[Audiobook]` |
| `get_user_comics(user_id: Union[int, str])` | `List[Comicbook]` |
| `get_user_bookshelves(user_id: Union[int, str])` | `List[Bookshelf]` |
| `get_user_followings(user_id: Union[int, str])` | `List[User]` |
| `get_user_impressions(user_id: Union[int, str])` | `List[Impression]` |
| `get_user_quotes(user_id: Union[int, str])` | `List[Quote]` |
| `get_user_reading_achievements(user_id: Union[int, str])` | Устарел: `EndpointGoneError` при HTTP 410 |
| `get_person_books(person_id: str, role: str = 'author', page: int = 1, per_page: int = 20)` | `List[Book]` |
| `get_book(book_id: str)` | `Optional[Book]` |
| `get_book_impressions(book_id: str)` | `List[Impression]` |
| `get_audiobook(audiobook_id: str)` | `Optional[Audiobook]` |
| `get_audiobook_impressions(audiobook_id: str)` | `List[Impression]` |
| `get_comicbook(comic_id: str)` | `Optional[Comicbook]` |
| `get_comicbook_impressions(comic_id: str)` | `List[Impression]` |
| `get_my_library(limit: Optional[int]=None, offset: Optional[int]=None, *, page: Optional[int]=None, per_page: Optional[int]=None)` | `List[LibraryCard]` |
| `add_book(book_uuid: str)` | `Optional[LibraryCard]` |
| `remove_book(library_card_uuid: str)` | `bool` |
| `get_my_bookshelves(page: int=1, per_page: int=20)` | `List[Bookshelf]` |
| `get_bookshelf_books(bookshelf_uuid: str)` | `List[Book]` |
| `get_series_following(user_id: Optional[Union[int, str]]=None, page: int=1, per_page: int=20)` | `Dict[str, Any]` |
| `get_reading_achievements(year: Optional[int]=None)` | Устарел: `EndpointGoneError` при HTTP 410 |
| `get_emotions()` | `Dict[str, Any]` |
| `get_popular_searches(language: str='ru', page: int=1)` | `Dict[str, Any]` |
| `search(query: str, no_misspell: bool=False, types: Optional[List[str]]=None, cursor: str='')` | `Dict[str, Any]` |
| `get_subscriptions(cursor: str='', per_page: int=20)` | `Dict[str, Any]` |
| `get_reading_statistics(request_time: Optional[str]=None)` | `Dict[str, Any]` |
| `test_token()` | `bool` |
| `download_file(url: str, filepath: str)` | `None` |
| `search_books(query: str, no_misspell: bool=False, types: Optional[List[str]]=None, cursor: str='')` | `Dict[str, Any]` |

Параметр `user_id` в методах `get_user_*` сохранён по имени для совместимости,
но основной идентификатор — **логин** (`User.login`). Числовой ID поддерживается
только для текущего аккаунта с токеном: клиент загружает профиль и определяет логин.
Для чужого числового ID передайте логин явно. Строки считаются логинами;
`User.uuid` не используется как идентификатор маршрута. Модельные методы
`user.fetch_books()` и другие `fetch_*` также используют логин, а при его отсутствии
пытаются разрешить числовой ID своего аккаунта. Методы `get_book*` принимают UUID книги.

`get_my_library` и `get_my_bookshelves` используют `page` и `per_page`.
Для библиотеки значения по умолчанию — `page=1`, `per_page=20`; размер страницы
должен быть от 1 до 100. Чтобы получить остальные страницы, меняйте `page`.
Совместимый вызов `get_my_library(limit=10, offset=15)` возвращает нужный срез:
клиент преобразует его в одну или две страницы API. `limit` должен быть от 1 до 100,
`offset` — целым числом не меньше нуля; при передаче только `offset` используется
`limit=50`. Смешивать `limit/offset` и `page/per_page` нельзя. Вызов без аргументов
теперь использует размер страницы 20.

`get_series_following()` без `user_id` загружает профиль и запрашивает серии по
его логину; токен обязателен. Если профиль уже загружен через `init()`, он используется
повторно. Явный логин позволяет запросить серии другого пользователя.

Книги автора доступны через `client.get_person_books(uuid)` или
`person.fetch_books()`. Роль по умолчанию — `author`; также доступны `translator`,
`narrator`, `illustrator` и `publisher`. Асинхронный вариант модельного метода —
`await person.fetch_books_async()`. Оба варианта принимают `role`, `page`, `per_page`.
`book.download_cover()` и `comicbook.download_cover()` возвращают путь к файлу;
поддерживаемые размеры — `small` и `large`.
Метод `fetch_impressions()` у `Book`, `Audiobook` и `Comicbook` получает рецензии
соответствующего типа контента; асинхронный вариант — `fetch_impressions_async()`.

GraphQL-методы `search`, `search_books`, `get_subscriptions` и
`get_reading_statistics` возвращают словарь ответа. Вложенные поля словаря
нормализуются в snake_case. REST-методы с типом `Dict` также возвращают нормализованный
словарь без преобразования в модель.
Ошибки GraphQL могут возвращаться при HTTP 200: проверяйте `result.get("errors")`
перед обращением к `data`. Ответ может одновременно содержать частичные данные
и ошибки. Аргумент `types` принимает значения enum `Type` сервиса, а не имена
`__typename` из результатов; без фильтра используйте `types=None`.

## Модели

Модели экспортируются из `yandex_book`: `User`, `Person`, `Image`, `Avatar`,
`Book`, `Audiobook`, `Comicbook`, `LibraryCard`, `Bookshelf`, `Series`, `Label`,
`Quote`, `Impression`, `ReadingAchievement`, `ReadingChallenge`.

Это dataclass-модели с необязательными полями: отсутствующие в API данные обычно
имеют значение `None`. У `User` есть `id` и `uuid`; у книги — `title`, `name`,
`display_title`, `cover` и `authors`; у `Image` — `best_url`.
`Book.authors` — список `Person`: для REST он заполняется из `authors_objects`,
если поле `authors` пришло строкой. Исходная строка сохраняется в `authors_text`.
Если REST не прислал объекты авторов, список пуст; текст остаётся доступным.
Для GraphQL объекты берутся непосредственно из списка `authors`.
Неизвестные поля API игнорируются, а при `report_unknown_fields=True` их имена
попадают в лог. Модели поддерживают `to_dict()` и `to_json()`.
Объекты с одинаковым идентификатором и типом считаются равными. Если идентификатор
не задан полностью, разные экземпляры сохраняют свою идентичность и не сливаются
при добавлении в `set`. Некорректные элементы списков пропускаются отдельно.

## Ошибки

```python
from yandex_book import YandexBookClient, NotFoundError, UnauthorizedError, NetworkError

with YandexBookClient("y0_...") as client:
    try:
        user = client.get_user("nonexistent")
    except NotFoundError:
        print("Пользователь не найден")
    except UnauthorizedError:
        print("Неверный токен или недостаточно прав")
    except NetworkError:
        print("Не удалось выполнить запрос")
```

`TimedOutError` наследует `NetworkError`. HTTP 400 вызывает `BadRequestError`,
401/403 — `UnauthorizedError`, 404 — `NotFoundError`, 410 — `EndpointGoneError`,
остальные HTTP-ошибки —
`NetworkError`. `test_token()` возвращает `False` при 401/403;
ошибки сети и таймауты передаются вызывающему коду.
Некорректный JSON или JSON неожиданного типа в HTTP-ответе вызывает `NetworkError`.
`EndpointGoneError` наследует `NetworkError` и означает, что эндпоинт больше недоступен
на стороне сервиса.
Модельные методы проверяют наличие клиента и идентификатора обычными исключениями,
в том числе при запуске `python -O`: неверный клиент или размер изображения вызывает
`InvalidOptionError`, отсутствующий идентификатор — `IdMissingError`.
DEBUG-логи клиента содержат названия вызываемых методов; полные результаты,
включая приватные данные профиля, в журнал не записываются.

## Недоступные достижения чтения

Старые REST-методы `get_reading_achievements(year)` и
`get_user_reading_achievements(user_id)` больше не поддерживаются сервисом: API
возвращает HTTP 410, библиотека вызывает `EndpointGoneError` с пояснением.
Модели `ReadingAchievement` и `ReadingChallenge` сохранены для обработки старых данных.

Текущую статистику своего аккаунта можно получить через GraphQL:

```python
with YandexBookClient(os.environ["YANDEX_BOOK_TOKEN"]) as client:
    result = client.get_reading_statistics()
    if result.get("errors"):
        print("Статистика недоступна")
    else:
        statistics = result["data"]["user"]["loyalty"]["statistics"]
        print(statistics)
```

Этот ответ содержит `days_per_month`, `streak`, `streak_record`, `today_time`.
Он имеет другой формат и не заменяет годовые достижения или статистику
произвольного другого пользователя.

## Миграция с 0.1.x

В версии 2 статические методы моделей заменены методами клиента:
`User.get(id)` → `client.get_user(id)`, `User.list_books(id)` →
`client.get_user_books(id)`, `Book.get(uuid)` → `client.get_book(uuid)`.
Данные теперь представлены dataclass-моделями вместо Pydantic.

## Разработка

Установите зависимости разработки и асинхронного клиента:

```bash
python -m pip install -e ".[dev,async]"
```

Дополнение `dev` включает `build`, необходимый для сборки:

```bash
python -m pytest
python generate_async_version.py
python -m build
```

`client_async.py` генерируется из `client.py` преобразованием AST Python.
Изменения интерфейса вносятся в синхронный клиент; генератор добавляет `await`
в вызовы HTTP-слоя и других методов клиента. Тест проверяет соответствие
сгенерированного файла исходнику. HTTP-слой `request_async.py` поддерживается отдельно.
Тесты моделей и клиентов используют локальный HTTP-сервер и не требуют токена Яндекса.

## Лицензия

MIT
