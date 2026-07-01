# 📚 Yandex Bookmate API v2.0

**Неофициальный Python API для Яндекс.Книг с нативной аутентификацией Bookmate**

> ⚠️ **Версия 2.0 — несовместима с v0.1.x**
>
> Это полностью переписанная версия библиотеки. Если вы использовали версию `0.1.2` и ниже, ознакомьтесь с [руководством по миграции](#миграция-с-v01x-на-v20).

---

## Что нового в v2.0

- **Клиент-серверная архитектура** — единый `YandexBookClient` вместо статических методов на моделях
- **OAuth-авторизация** — приватные методы (библиотека, полки, профиль) через Яндекс OAuth-токен
- **20+ приватных методов** — управление библиотекой, полками, достижениями, уведомлениями и др.
- **GraphQL-поддержка** — поиск, подписки, статистика чтения через GraphQL endpoint
- **Async-версия** — полноценный асинхронный клиент на aiohttp (`pip install yandex-book-api[async]`)
- **Dataclass-модели** вместо Pydantic — легковеснее, без внешних зависимостей для моделей
- **Кастомные исключения** — `UnauthorizedError`, `NotFoundError`, `BadRequestError` и др.
- **Тесты** — pytest-покрытие основных моделей

---

## Миграция с v0.1.x на v2.0

### Ключевые отличия

| | v0.1.x | v2.0 |
|---|---|---|
| **Архитектура** | Статические методы на моделях (`User.get()`) | Единый клиент `YandexBookClient` |
| **Модели** | Pydantic `BaseModel` | Dataclass через `@model` декоратор |
| **Зависимости** | `pydantic>=2.0`, `requests` | Только `requests` (pydantic убран) |
| **Python** | `>=3.8` | `>=3.9` |
| **Авторизация** | Нет | OAuth-токен Яндекса |
| **Async** | Нет | `aiohttp` (опционально) |
| **Ошибки** | `requests.HTTPError` | `ApiError`, `UnauthorizedError`, `NotFoundError`… |

### Примеры миграции

**Было (v0.1.x):**
```python
from yandex_book import User, Book

user = User.get("b1234567890")
books = User.list_books(user.id)
book = Book.get("mqK3FFjg")
book.download_cover(size="small", dest="cover.jpg")
```

**Стало (v2.0):**
```python
from yandex_book import YandexBookClient

# Без токена — только публичные методы
client = YandexBookClient()
user = client.get_user("b1234567890")
books = client.get_user_books(user.id_)

# С токеном — все методы
client = YandexBookClient('y0_AgAAAA...')
book = client.get_book("mqK3FFjg")
client.download_file(book.cover.small, "cover.jpg")

# Приватные методы (требуют токен)
my_library = client.get_my_library()
client.add_book("mqK3FFjg")
```

---

## Содержание

- [Установка](#установка)
- [Получение токена](#получение-токена)
- [Публичные методы](#публичные-методы-без-авторизации)
- [Приватные методы](#приватные-методы-с-авторизацией)
- [Модели данных](#модели-данных)
- [Примеры](#примеры)

---

## Установка

Установите библиотеку через pip:

```bash
pip install yandex-book-api
```

Если вы хотите использовать асинхронный клиент (на базе `aiohttp`), установите его с дополнительными зависимостями:

```bash
pip install yandex-book-api[async]
```

Для локальной разработки (в режиме редактирования):

```bash
pip install -e .
```

---

## Получение токена

Нужен токен Яндекса формат: `y0_AgAAAA...` 

**Способ 1: Через OAuth  - РЕКОМЕНДУЕТСЯ**
- Откройте: `https://oauth.yandex.ru/authorize?response_type=token&client_id=4483e97bab6e486a9822973109a14d05`
- Скопируйте весь `access_token` из URL (начинается с `y0_`)
- Используйте как токен для Client


---

## Публичные методы (без авторизации)

### User.get()

Получить информацию о пользователе.

| Параметр | Тип       | Описание |
|----------|-----------|---------|
| **user_id** | `int\|str` | ID пользователя |

**Возвращает:** User объект с полями:

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | `int` | Числовой ID |
| `login` | `str` | Логин пользователя |
| `name` | `str?` | Полное имя |
| `avatar` | `Avatar?` | Аватар |
| `library_cards_count` | `int?` | Кол-во книг в библиотеке |
| `followers_count` | `int?` | Кол-во подписчиков |
| `followings_count` | `int?` | Кол-во подписок |
| `bookshelves_count` | `int?` | Кол-во полок |
| `about` | `str?` | О себе |
| `facebook`, `twitter`, `vk`, `site` | `str?` | Соцсети/сайт |

---

### User.list_books()

Получить публичные книги пользователя.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **user_id** | `int\|str` | ID пользователя |

**Возвращает:** `List[Book]` с полями:

| Поле | Тип | Описание |
|------|-----|---------|
| `uuid` | `str` | Уникальный ID книги |
| `title` | `str?` | Название |
| `annotation` | `str?` | Аннотация |
| `cover` | `Image?` | Обложка (small, large, placeholder) |
| `authors_objects` | `List[Person]?` | Авторы |

---

### User.list_audiobooks()

Получить публичные аудиокниги пользователя.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **user_id** | `int\|str` | ID пользователя |

**Возвращает:** `List[Audiobook]` (наследует Book + дополнительные поля):

| Поле | Тип | Описание |
|------|-----|---------|
| `duration` | `int?` | Длительность в секундах |
| `language` | `str?` | Язык |
| `narrators` | `List[Person]?` | Чтецы/рассказчики |
| `listeners_count` | `int?` | Кол-во слушателей |
| `age_restriction` | `str?` | Возрастное ограничение |

---

### User.list_quotes()

Получить цитаты пользователя (публично).

| Параметр | Тип | Описание |
|----------|-----|---------|
| **user_id** | `int\|str` | ID пользователя |

**Возвращает:** `List[Quote]` с полями:

| Поле | Тип | Описание |
|------|-----|---------|
| `content` | `str` | Текст цитаты |
| `book` | `Book` | Книга, откуда цитата |
| `created_at` | `int` | Timestamp создания |
| `likes_count` | `int` | Кол-во лайков |
| `comments_count` | `int` | Кол-во комментариев |

---

### User.list_bookshelves()

Получить полки пользователя.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **user_id** | `int\|str` | ID пользователя |

**Возвращает:** `List[Bookshelf]`

| Поле | Тип | Описание |
|------|-----|---------|
| `uuid` | `str` | ID полки |
| `title` | `str` | Название |
| `annotation` | `str?` | Описание |
| `books_count` | `int?` | Кол-во книг |
| `followers_count` | `int?` | Подписчиков |

---

### User.list_impressions()

Получить рецензии пользователя.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **user_id** | `int\|str` | ID пользователя |

**Возвращает:** `List[Impression]`

| Поле | Тип | Описание |
|------|-----|---------|
| `content` | `str?` | Текст рецензии |
| `book` | `Book?` | Книга |
| `likes_count` | `int?` | Лайки |
| `comments_count` | `int?` | Комментарии |

---

### Book.get()

Получить информацию о книге.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **book_id** | `str` | UUID книги |

**Возвращает:** Book объект

| Поле | Тип | Описание |
|------|-----|---------|
| `uuid` | `str` | Уникальный ID |
| `title` | `str?` | Название |
| `annotation` | `str?` | Описание |
| `cover` | `Image?` | Обложка |
| `authors_objects` | `List[Person]?` | Авторы |

---

### Book.impressions()

Получить рецензии на книгу.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **book_id** | `str` | UUID книги |

**Возвращает:** `List[Impression]`

---

## Приватные методы (с авторизацией)

### Client(auth_token)

Инициализировать авторизованный клиент.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **auth_token** | `str` | Ваш Auth-Token |

---

### client.test_token()

Проверить валидность токена.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `bool` - True если токен работает |

---

### client.get_profile()

Получить свой профиль.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с ключом `user` содержащим профиль |

**Поля user:**

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | `int` | Числовой ID |
| `login` | `str` | Ваш логин |
| `name` | `str?` | Имя |
| `email` | `str?` | Email |
| `library_cards_count` | `int?` | Кол-во книг |
| `followers_count` | `int?` | Подписчиков |
| `following_count` | `int?` | Подписок |

---

### client.get_my_library()

Получить мою приватную библиотеку.

| Параметр | Тип | Default | Описание |
|----------|-----|---------|---------|
| **limit** | `int` | 50 | Кол-во книг (макс 100) |
| **offset** | `int` | 0 | Смещение для пагинации |

**Возвращает:** `Dict` с ключом `data` содержащим список карточек:

| Поле | Тип | Описание |
|------|-----|---------|
| `uuid` | `str` | UUID карточки библиотеки |
| `book` | `Book` | Объект книги (title, annotation, cover и т.д.) |
| `progress` | `int` | Прогресс чтения (0-100%) |
| `state` | `str` | Статус: `pending`, `reading`, `finished` |
| `started_at` | `int?` | Timestamp начала |
| `finished_at` | `int?` | Timestamp завершения |

---

### client.add_book()

Добавить книгу в мою библиотеку.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **book_id** | `str` | UUID книги |

**Возвращает:** `Dict` с полями:

| Поле | Тип | Описание |
|------|-----|---------|
| `status` | `str` | `success` или `error` |
| `book_id` | `str` | UUID добавленной книги |
| `book_title` | `str?` | Название книги |
| `library_card_uuid` | `str?` | UUID карточки в библиотеке |
| `error` | `str?` | Сообщение ошибки если есть |

---

### client.remove_book()

Удалить книгу из моей библиотеки.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **library_card_uuid** | `str` | UUID карточки (из get_my_library) |

**Возвращает:** `Dict` с полями:

| Поле | Тип | Описание |
|------|-----|---------|
| `status` | `str` | `success` или `error` |
| `message` | `str?` | Описание результата |
| `error` | `str?` | Сообщение ошибки если есть |

---

### client.get_my_bookshelves()

Получить мои книжные полки.

| Параметр | Тип | Default | Описание |
|----------|-----|---------|---------|
| **page** | `int` | 1 | Номер страницы |
| **per_page** | `int` | 20 | Кол-во полок на странице |

**Возвращает:** `Dict` с ключом `data` содержащим список полок:

| Поле | Тип | Описание |
|------|-----|---------|
| `uuid` | `str` | UUID полки |
| `title` | `str` | Название полки |
| `annotation` | `str?` | Описание |
| `books_count` | `int?` | Кол-во книг на полке |
| `followers_count` | `int?` | Подписчиков |

---

### client.get_notifications_status()

Получить статус уведомлений.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с информацией о новых уведомлениях |

---

### client.get_reading_achievements()

Получить достижения за год.

| Параметр | Тип | Описание |
|----------|-----|---------|
| **year** | `int?` | Год для статистики (по умолчанию текущий) |

**Возвращает:** `Dict` с полями:

| Поле | Тип | Описание |
|------|-----|---------|
| `finished_books_count` | `int` | Книг прочитано |
| `pages` | `int` | Всего страниц |
| `seconds` | `int` | Всего секунд чтения |
| `year` | `int` | Год |
| `reading_challenge` | `Dict?` | Информация о челлендже |

---

### client.get_popular_searches()

Получить популярные поиски.

| Параметр | Тип | Default | Описание |
|----------|-----|---------|---------|
| **language** | `str` | `ru` | Код языка |
| **page** | `int` | 1 | Номер страницы |

**Возвращает:** `Dict` с ключом `data` содержащим список популярных запросов

---

### client.get_emotions()

Получить доступные эмоции для рецензий.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с ключом `data` содержащим список эмоций |

---

### client.get_access_levels()

Получить уровни доступа к контенту.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с информацией об уровнях доступа |

---

### client.get_counters()

Получить счётчики профиля.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` со счётчиками (сообщения, уведомления и т.д.) |

---

### client.get_context()

Получить контекст приложения.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с контекстной информацией приложения |

---

### client.get_privacy_settings()

Получить настройки приватности.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с настройками приватности профиля |

---

### client.get_sync_state()

Получить состояние синхронизации.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с состоянием синхронизации данных |

---

### client.get_metadata_secret()

Получить секретные метаданные.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с защищёнными метаданными профиля |

---

### client.get_user_json()

Получить полные данные пользователя.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с полным JSON объектом пользователя |

---

### client.get_push_notification_restrictions()

Получить ограничения для push уведомлений.

| | |
|---|---|
| **Параметры** | Нет |
| **Возвращает** | `Dict` с настройками ограничений для push уведомлений |

---

### client.get_features()

Получить информацию о функциях.

| Параметр | Тип | Default | Описание |
|----------|-----|---------|---------|
| **feature_names** | `List[str]?` | Стандартные | Список названий функций для проверки |

**Возвращает:** `Dict` с информацией о доступности функций

---

### client.get_series_following()

Получить серии, на которые я подписан.

| Параметр | Тип | Default | Описание |
|----------|-----|---------|---------|
| **user_id** | `str?` | Не требуется | ID пользователя (если None - свои серии) |
| **page** | `int` | 1 | Номер страницы |
| **per_page** | `int` | 20 | Кол-во серий на странице |

**Возвращает:** `Dict` с ключом `series` содержащим список серий:

| Поле | Тип | Описание |
|------|-----|---------|
| `uuid` | `str` | Уникальный ID серии |
| `title` | `str` | Название серии |
| `description` | `str?` | Описание серии |
| `books_count` | `int?` | Кол-во книг в серии |

---

## Таблица всех REST методов Client

Всего **21 метод** (+ новый `get_series_following`):

| № | Метод | Параметры | Назначение |
|---|-------|-----------|-----------|
| 1 | `test_token()` | — | Проверка валидности токена |
| 2 | `get_profile()` | — | Получить свой профиль |
| 3 | `get_my_library()` | limit, offset | Получить мою библиотеку |
| 4 | `add_book()` | book_id | Добавить книгу в библиотеку |
| 5 | `remove_book()` | library_card_uuid | Удалить книгу из библиотеки |
| 6 | `get_my_bookshelves()` | page, per_page | Получить мои полки |
| 7 | `get_notifications_status()` | — | Статус уведомлений |
| 8 | `get_reading_achievements()` | year | Достижения за год |
| 9 | `get_popular_searches()` | language, page | Популярные поиски |
| 10 | `get_emotions()` | — | Доступные эмоции |
| 11 | `get_access_levels()` | — | Уровни доступа |
| 12 | `get_counters()` | — | Счётчики профиля |
| 13 | `get_context()` | — | Контекст приложения |
| 14 | `get_privacy_settings()` | — | Настройки приватности |
| 15 | `get_sync_state()` | — | Состояние синхронизации |
| 16 | `get_metadata_secret()` | — | Секретные метаданные |
| 17 | `get_user_json()` | — | Полные данные пользователя |
| 18 | `get_push_notification_restrictions()` | — | Ограничения push уведомлений |
| 19 | `get_features()` | feature_names | Информация о функциях |
| 20 | `get_series_following()` | user_id, page, per_page | Серии подписок |

---

## Модели данных

### Image / Avatar

| Поле | Тип | Описание |
|------|-----|---------|
| `small` | `str?` | URL миниатюры |
| `large` | `str?` | URL большого изображения |
| `placeholder` | `str?` | Base64 заглушка |
| `ratio` | `float?` | Соотношение сторон |
| `background_color_hex` | `str?` | Цвет фона (HEX) |

---

### Person

| Поле | Тип | Описание |
|------|-----|---------|
| `name` | `str` | Имя (автор, иллюстратор, чтец) |
| `locale` | `str?` | Локаль (ru, en и т.д.) |
| `uuid` | `str?` | Уникальный ID |
| `works_count` | `int?` | Кол-во работ |
| `image` | `Image?` | Профильное изображение |

---

### Label

| Поле | Тип | Описание |
|------|-----|---------|
| `title` | `str` | Название метки |
| `kind` | `str` | Тип метки |

---

## Примеры

### Публичные методы (без токена)

```python
from yandex_book import YandexBookClient

client = YandexBookClient()

# Получить пользователя
user = client.get_user("b1234567890")
print(user.name, user.login)

# Книги пользователя
books = client.get_user_books(user.id_)
for book in books[:3]:
    print(book.display_title)

# Информация о книге
book = client.get_book("mqK3FFjg")
print(book.title, book.annotation)
```

### Приватные методы (с токеном)

```python
from yandex_book import YandexBookClient

client = YandexBookClient('y0_AgAAAA...')

# Проверить токен
if client.test_token():
    print("Токен валиден!")

# Профиль
me = client.get_profile()
print(me.name, me.login)

# Библиотека
library = client.get_my_library(limit=10)
for card in library:
    print(card.book.display_title, card.state)

# Добавить / удалить книгу
client.add_book("mqK3FFjg")

# Поиск через GraphQL
results = client.search("Мастер и Маргарита")
```

### Async-версия

```python
import asyncio
from yandex_book import YandexBookClientAsync

async def main():
    client = YandexBookClientAsync('y0_AgAAAA...')
    me = await client.get_profile()
    books = await client.get_user_books(me.id_)
    print(f"{me.name}: {len(books)} книг")
    await client._request.close()

asyncio.run(main())
```

### Обработка ошибок

```python
from yandex_book import YandexBookClient, NotFoundError, UnauthorizedError

client = YandexBookClient('y0_AgAAAA...')

try:
    user = client.get_user("nonexistent")
except NotFoundError:
    print("Пользователь не найден")
except UnauthorizedError:
    print("Неверный токен")
```

---

## Лицензия

MIT

