"""
test_person.py — тесты модели Person.
"""
from tests.conftest import TestImage, TestPerson


class TestPersonModel:
    def test_expected_values(self, person):
        assert person.uuid == TestPerson.uuid
        assert person.name == TestPerson.name
        assert person.works_count == TestPerson.works_count

    def test_nested_image(self, person):
        from yandex_book.user.user import Image
        assert isinstance(person.image, Image)
        assert person.image.large == TestImage.large

    def test_de_json_none(self, client):
        from yandex_book.user.user import Person
        assert Person.de_json({}, client) is None
        assert Person.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.user.user import Person
        assert Person.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.user.user import Person
        p = Person.de_json({'uuid': TestPerson.uuid, 'name': TestPerson.name}, client)
        assert p is not None
        assert p.uuid == TestPerson.uuid
        assert p.name == TestPerson.name

    def test_de_list(self, client):
        from yandex_book.user.user import Person
        data = [
            {'uuid': 'p1', 'name': 'Автор 1'},
            {'uuid': 'p2', 'name': 'Автор 2'},
        ]
        persons = Person.de_list(data, client)
        assert len(persons) == 2
        assert persons[0].uuid == 'p1'

    def test_equality(self):
        from yandex_book.user.user import Person
        a = Person(uuid='uuid-1')
        b = Person(uuid='uuid-2')
        c = Person(uuid='uuid-1')
        assert a != b
        assert a == c

    def test_to_dict_excludes_client(self, person):
        d = person.to_dict()
        assert 'client' not in d
        assert d['uuid'] == TestPerson.uuid
