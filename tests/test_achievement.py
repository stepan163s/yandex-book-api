"""
test_achievement.py — тесты модели ReadingAchievement.
"""
import pytest

from tests.conftest import TestAchievement


class TestReadingAchievementModel:
    def test_expected_values(self, achievement):
        assert achievement.year == TestAchievement.year
        assert achievement.finished_books_count == TestAchievement.finished_books_count
        assert achievement.seconds == TestAchievement.seconds

    def test_hours_property(self, achievement):
        expected_hours = TestAchievement.seconds / 3600
        assert achievement.hours == pytest.approx(expected_hours)

    def test_de_json_none(self, client):
        from yandex_book.achievement.achievement import ReadingAchievement
        assert ReadingAchievement.de_json({}, client) is None
        assert ReadingAchievement.de_json(None, client) is None

    def test_de_list_none(self, client):
        from yandex_book.achievement.achievement import ReadingAchievement
        assert ReadingAchievement.de_list([], client) == []

    def test_de_json_required(self, client):
        from yandex_book.achievement.achievement import ReadingAchievement
        ra = ReadingAchievement.de_json({
            'year': TestAchievement.year,
            'finished_books_count': TestAchievement.finished_books_count,
        }, client)
        assert ra is not None
        assert ra.year == TestAchievement.year
        assert ra.finished_books_count == TestAchievement.finished_books_count
        assert ra.reading_challenge is None

    def test_de_json_with_challenge(self, client):
        from yandex_book.achievement.achievement import ReadingAchievement
        ra = ReadingAchievement.de_json({
            'year': 2024,
            'finished_books_count': 10,
            'reading_challenge': {
                'promised_books_count': 12,
                'image_url': 'https://example.com/badge.png',
            },
        }, client)
        assert ra.reading_challenge is not None
        assert ra.reading_challenge.promised_books_count == 12

    def test_hours_zero_when_no_seconds(self):
        from yandex_book.achievement.achievement import ReadingAchievement
        ra = ReadingAchievement(year=2024)
        assert ra.hours == 0.0

    def test_equality(self):
        from yandex_book.achievement.achievement import ReadingAchievement
        a = ReadingAchievement(year=2023)
        b = ReadingAchievement(year=2024)
        c = ReadingAchievement(year=2023)
        assert a != b
        assert a == c
