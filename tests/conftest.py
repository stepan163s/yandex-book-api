"""
conftest.py — общие фикстуры для всех тестов.

Клиент создаётся без токена — HTTP-запросы не выполняются.
Фикстуры моделей используют конструкторы напрямую, не de_json.
"""
import pytest

from yandex_book.client import YandexBookClient


@pytest.fixture(scope='session')
def client():
    """Клиент без токена — только для тестирования моделей."""
    with YandexBookClient() as instance:
        yield instance


# ---------------------------------------------------------------------------
# Тестовые данные (константы)
# ---------------------------------------------------------------------------

class TestImage:
    large = 'https://cdn.example.com/cover_large.jpg'
    small = 'https://cdn.example.com/cover_small.jpg'
    background_color_hex = '#ffffff'


class TestPerson:
    uuid = 'author-uuid-1'
    name = 'Лев Толстой'
    works_count = 42


class TestUser:
    uuid = 'user-uuid-1'
    id = 12345
    login = 'testuser'
    name = 'Иван Тестов'
    followers_count = 100


class TestBook:
    uuid = 'book-uuid-1'
    title = 'Война и мир'
    annotation = 'Великий роман'
    language = 'ru'


class TestAudiobook:
    uuid = 'audio-uuid-1'
    title = 'Мастер и Маргарита'
    duration = 72000  # 20 часов


class TestBookshelf:
    uuid = 'shelf-uuid-1'
    title = 'Моя полка'
    books_count = 10


class TestQuote:
    cfi = 'epubcfi(/6/4!/4/2/1:0)'
    item_uuid = 'book-uuid-1'
    content = 'Все счастливые семьи похожи...'


class TestLibraryCard:
    uuid = 'lc-uuid-1'
    state = 'reading'
    reading_progress = 0.42


class TestAchievement:
    year = 2024
    finished_books_count = 25
    seconds = 360000
    pages = 5000


# ---------------------------------------------------------------------------
# Фикстуры (конструкторы)
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def image(client):
    from yandex_book.user.user import Image
    return Image(
        large=TestImage.large,
        small=TestImage.small,
        background_color_hex=TestImage.background_color_hex,
        client=client,
    )


@pytest.fixture(scope='session')
def person(client, image):
    from yandex_book.user.user import Person
    return Person(
        uuid=TestPerson.uuid,
        name=TestPerson.name,
        works_count=TestPerson.works_count,
        image=image,
        client=client,
    )


@pytest.fixture(scope='session')
def user(client):
    from yandex_book.user.user import User
    return User(
        uuid=TestUser.uuid,
        id=TestUser.id,
        login=TestUser.login,
        name=TestUser.name,
        followers_count=TestUser.followers_count,
        client=client,
    )


@pytest.fixture(scope='session')
def book(client):
    from yandex_book.book.book import Book
    return Book(
        uuid=TestBook.uuid,
        title=TestBook.title,
        annotation=TestBook.annotation,
        language=TestBook.language,
        client=client,
    )


@pytest.fixture(scope='session')
def audiobook(client):
    from yandex_book.book.book import Audiobook
    return Audiobook(
        uuid=TestAudiobook.uuid,
        title=TestAudiobook.title,
        duration=TestAudiobook.duration,
        client=client,
    )


@pytest.fixture(scope='session')
def bookshelf(client, user):
    from yandex_book.bookshelf.bookshelf import Bookshelf
    return Bookshelf(
        uuid=TestBookshelf.uuid,
        title=TestBookshelf.title,
        books_count=TestBookshelf.books_count,
        creator=user,
        client=client,
    )


@pytest.fixture(scope='session')
def library_card(client, book):
    from yandex_book.book.book import LibraryCard
    return LibraryCard(
        uuid=TestLibraryCard.uuid,
        state=TestLibraryCard.state,
        reading_progress=TestLibraryCard.reading_progress,
        book=book,
        client=client,
    )


@pytest.fixture(scope='session')
def quote(client, book):
    from yandex_book.quote.quote import Quote
    return Quote(
        cfi=TestQuote.cfi,
        item_uuid=TestQuote.item_uuid,
        content=TestQuote.content,
        book=book,
        client=client,
    )


@pytest.fixture(scope='session')
def achievement(client):
    from yandex_book.achievement.achievement import ReadingAchievement
    return ReadingAchievement(
        year=TestAchievement.year,
        finished_books_count=TestAchievement.finished_books_count,
        seconds=TestAchievement.seconds,
        pages=TestAchievement.pages,
        client=client,
    )
