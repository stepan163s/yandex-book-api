#!/usr/bin/env python3
from __future__ import annotations

import re
import secrets
import argparse
import platform
import subprocess
import sys
import time
import urllib.parse
import webbrowser


CLIENT_ID = "4483e97bab6e486a9822973109a14d05"
AUTHORIZE_URL = (
    "https://oauth.yandex.ru/authorize"
    f"?response_type=token&client_id={CLIENT_ID}"
)
TOKEN_PATTERN = re.compile(r"y0_[A-Za-z0-9._~-]+")
SAFARI_WAIT_SECONDS = 180
CALLBACK_HOST = f'yx{CLIENT_ID}.oauth.yandex.ru'


class OAuthResponseError(ValueError):
    pass


def extract_token(value: str, expected_state: str | None = None) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Ввод пустой.")

    if expected_state is None and TOKEN_PATTERN.fullmatch(value):
        return value

    parsed = urllib.parse.urlparse(value)
    if expected_state is not None:
        if parsed.scheme != 'https' or parsed.hostname != CALLBACK_HOST:
            raise ValueError('Нужна ссылка возврата Яндекса из текущей авторизации.')
        states = []
        for component in (parsed.fragment, parsed.query):
            states.extend(urllib.parse.parse_qs(component, keep_blank_values=True).get('state', []))
        if len(states) != 1 or not secrets.compare_digest(states[0].encode(), expected_state.encode()):
            raise ValueError('Ссылка относится к другому запуску. Завершите текущую авторизацию.')
    for component in (parsed.fragment, parsed.query):
        params = urllib.parse.parse_qs(component, keep_blank_values=True)
        if "error" in params:
            message = params.get("error_description", params["error"])[0]
            raise OAuthResponseError(f"Яндекс OAuth вернул ошибку: {message}")
        token = params.get("access_token", [""])[0].strip()
        if token:
            return token

    raise ValueError(
        "В ссылке не найден access_token. Нужна полная ссылка возврата "
        "из адресной строки браузера."
    )


def read_safari_url() -> str | None:
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "Safari" to get URL of front document'],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def wait_for_safari_token(timeout: int = SAFARI_WAIT_SECONDS,
                          expected_state: str | None = None) -> str | None:
    if platform.system() != "Darwin":
        return None

    deadline = time.monotonic() + timeout
    next_status = time.monotonic() + 10
    while time.monotonic() < deadline:
        current_url = read_safari_url()
        if current_url and urllib.parse.urlparse(current_url).hostname == CALLBACK_HOST:
            try:
                return extract_token(current_url, expected_state)
            except OAuthResponseError:
                raise
            except ValueError:
                pass

        if time.monotonic() >= next_status:
            print("Вход ещё не завершён, продолжаю ждать…")
            next_status = time.monotonic() + 10
        time.sleep(1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description='Получение OAuth-токена Яндекс Книг')
    parser.add_argument('--manual', action='store_true', help='Ввести ссылку вручную')
    parser.add_argument('--timeout', type=int, default=SAFARI_WAIT_SECONDS,
                        help='Время ожидания Safari в секундах (по умолчанию 180)')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout должен быть больше нуля')
    state = secrets.token_urlsafe(32)
    authorize_url = AUTHORIZE_URL + '&' + urllib.parse.urlencode({'state': state})
    print("Запрашиваю авторизацию Яндекса…")
    try:
        browser = webbrowser.get('safari') if platform.system() == 'Darwin' else webbrowser
        opened = browser.open(authorize_url)
    except webbrowser.Error:
        opened = False
    if not opened:
        print("Не удалось открыть браузер автоматически. Откройте эту ссылку вручную:")
        print(authorize_url)
    else:
        print("Страница авторизации открыта в браузере.")

    try:
        if platform.system() == "Darwin" and not args.manual:
            print("Ожидаю завершения входа и возврата в Safari…")
            token = wait_for_safari_token(args.timeout, state)
        else:
            token = None

        if token is None:
            if platform.system() == "Darwin" and not args.manual:
                print("Не получилось автоматически получить адрес возврата Safari.")
                print(
                    "Если macOS спросила разрешение, разрешите Terminal "
                    "управлять Safari в Настройки системы → Конфиденциальность "
                    "и безопасность → Автоматизация."
                )
            elif platform.system() != 'Darwin':
                print("Автоматическое чтение вкладки доступно только в Safari на macOS.")
            while token is None:
                callback_url = input("Скопируйте и вставьте сюда полную ссылку из браузера: ")
                try:
                    token = extract_token(callback_url, state)
                except OAuthResponseError:
                    raise
                except ValueError as exc:
                    print(f'Ссылка не подходит: {exc}')
    except (EOFError, KeyboardInterrupt):
        print("\nАвторизация отменена.", file=sys.stderr)
        return 1
    except (OAuthResponseError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print("\nАвторизация завершена успешно. Токен получен:")
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
