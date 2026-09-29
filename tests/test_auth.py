import pytest
from urllib.parse import parse_qs, urlparse

from yandex_book import auth


def test_callback_decoding_and_error():
    assert auth.extract_token('https://example.test/#access_token=y0_Test%2D123&token_type=bearer') == 'y0_Test-123'
    with pytest.raises(auth.OAuthResponseError, match='access_denied'):
        auth.extract_token('https://example.test/#error=access_denied')
    with pytest.raises(ValueError):
        auth.extract_token('https://example.test/y0_unrelated')


@pytest.mark.parametrize('suffix', ['#access_token=y0_correct&state=current', '?access_token=y0_correct&state=current'])
def test_callback_matches_current_state(suffix):
    assert auth.extract_token(f'https://{auth.CALLBACK_HOST}/{suffix}', 'current') == 'y0_correct'


@pytest.mark.parametrize('value', [
    f'https://{auth.CALLBACK_HOST}/#access_token=y0_old&state=previous',
    f'https://{auth.CALLBACK_HOST}/#access_token=y0_old',
    f'https://{auth.CALLBACK_HOST}/#access_token=y0_old&state=current&state=current',
    f'https://{auth.CALLBACK_HOST}/?state=current#access_token=y0_old&state=current',
    f'https://{auth.CALLBACK_HOST}/#access_token=y0_old&state=%D1%82%D0%B5%D1%81%D1%82',
    'https://example.test/#access_token=y0_old&state=current',
    f'http://{auth.CALLBACK_HOST}/#access_token=y0_old&state=current',
    'y0_old',
])
def test_callback_rejects_other_authorizations(value):
    with pytest.raises(ValueError):
        auth.extract_token(value, 'current')


def test_oauth_error_with_matching_state():
    with pytest.raises(auth.OAuthResponseError, match='access_denied'):
        auth.extract_token(f'https://{auth.CALLBACK_HOST}/#error=access_denied&state=current', 'current')


def test_safari_ignores_other_sites(monkeypatch):
    monkeypatch.setattr(auth.platform, 'system', lambda: 'Darwin')
    urls = iter([
        'https://example.test/#access_token=y0_unrelated',
        f'https://{auth.CALLBACK_HOST}/#access_token=y0_correct',
    ])
    monkeypatch.setattr(auth, 'read_safari_url', lambda: next(urls))
    monkeypatch.setattr(auth.time, 'sleep', lambda _: None)
    assert auth.wait_for_safari_token(10) == 'y0_correct'


def test_manual_mode_retries_invalid_link(monkeypatch, capsys):
    monkeypatch.setattr(auth.sys, 'argv', ['yandex-book-token', '--manual'])
    monkeypatch.setattr(auth.platform, 'system', lambda: 'Linux')
    opened = []
    monkeypatch.setattr(auth.webbrowser, 'open', lambda url: opened.append(url) or True)
    state = 'current-authorization'
    monkeypatch.setattr(auth.secrets, 'token_urlsafe', lambda _: state)
    values = iter(['invalid', f'https://{auth.CALLBACK_HOST}/#access_token=y0_correct&state={state}'])
    monkeypatch.setattr('builtins.input', lambda _: next(values))
    assert auth.main() == 0
    output = capsys.readouterr().out
    assert 'Ссылка не подходит' in output
    assert 'y0_correct' in output
    assert parse_qs(urlparse(opened[0]).query)['state'] == [state]
