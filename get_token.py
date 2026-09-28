#!/usr/bin/env python3
from __future__ import annotations

import re
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


class OAuthResponseError(ValueError):
    pass


def extract_token(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Ввод пустой.")

    if TOKEN_PATTERN.fullmatch(value):
        return value

    parsed = urllib.parse.urlparse(value)
    for component in (parsed.fragment, parsed.query):
        params = urllib.parse.parse_qs(component, keep_blank_values=True)
        if "error" in params:
            message = params.get("error_description", params["error"])[0]
            raise OAuthResponseError(f"Яндекс OAuth вернул ошибку: {message}")
        token = params.get("access_token", [""])[0].strip()
        if token:
            return token

    match = TOKEN_PATTERN.search(value)
    if match:
        return match.group(0)

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


def wait_for_safari_token(timeout: int = SAFARI_WAIT_SECONDS) -> str | None:
    if platform.system() != "Darwin":
        return None

    deadline = time.monotonic() + timeout
    next_status = time.monotonic() + 10
    while time.monotonic() < deadline:
        current_url = read_safari_url()
        if current_url:
            try:
                return extract_token(current_url)
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
    print("Запрашиваю авторизацию Яндекса…")
    if not webbrowser.open(AUTHORIZE_URL):
        print("Не удалось открыть браузер автоматически. Откройте эту ссылку вручную:")
        print(AUTHORIZE_URL)
    else:
        print("Страница авторизации открыта в браузере.")

    try:
        if platform.system() == "Darwin":
            print("Ожидаю завершения входа и возврата в Safari…")
            token = wait_for_safari_token()
        else:
            token = None

        if token is None:
            if platform.system() == "Darwin":
                print("Не получилось автоматически получить адрес возврата Safari.")
                print(
                    "Если macOS спросила разрешение, разрешите Terminal "
                    "управлять Safari в Настройки системы → Конфиденциальность "
                    "и безопасность → Автоматизация."
                )
            else:
                print("Автоматическое чтение вкладки доступно только в Safari на macOS.")
            callback_url = input("Скопируйте и вставьте сюда полную ссылку из браузера: ")
            token = extract_token(callback_url)
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
