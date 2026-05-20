"""
test_image.py — тесты модели Image.
"""
from tests.conftest import TestImage


class TestImageModel:
    def test_expected_values(self, image):
        assert image.large == TestImage.large
        assert image.small == TestImage.small
        assert image.background_color_hex == TestImage.background_color_hex

    def test_best_url(self, image):
        assert image.best_url == TestImage.large

    def test_de_json_none(self, client):
        from yandex_book.user.user import Image
        assert Image.de_json({}, client) is None
        assert Image.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.user.user import Image
        assert Image.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.user.user import Image
        img = Image.de_json({'large': TestImage.large}, client)
        assert img is not None
        assert img.large == TestImage.large
        assert img.small is None

    def test_equality(self):
        from yandex_book.user.user import Image
        a = Image(large='https://a.com/img.jpg')
        b = Image(large='https://b.com/img.jpg')
        c = Image(large='https://a.com/img.jpg')
        assert a != b
        assert a == c
        assert hash(a) == hash(c)

    def test_to_dict(self, image):
        d = image.to_dict()
        assert d['large'] == TestImage.large
        assert 'client' not in d

    def test_to_dict_for_request(self, image):
        d = image.to_dict(for_request=True)
        assert 'large' in d
        assert 'small' in d
        assert 'backgroundColorHex' in d
        assert 'client' not in d
