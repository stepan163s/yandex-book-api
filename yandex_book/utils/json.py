import json
import keyword
import re

from yandex_book.exceptions import BadRequestError, EndpointGoneError, NetworkError, NotFoundError, UnauthorizedError

PYTHON_RESERVED = frozenset(keyword.kwlist)
_CAMEL_RE = re.compile(r'(?<=[a-z0-9])([A-Z])')


def normalize_keys(obj: dict) -> dict:
    result = {}
    for key, value in obj.items():
        key = _CAMEL_RE.sub(r'_\1', key.replace('-', '_')).lower()
        if key in PYTHON_RESERVED:
            key += '_'
        if key and key[0].isdigit():
            key = '_' + key
        result[key] = value
    return result


def parse_json(content: bytes) -> dict:
    if not content:
        return {}
    try:
        result = json.loads(content, object_hook=normalize_keys)
    except (ValueError, UnicodeDecodeError) as exc:
        raise NetworkError('API вернул некорректный JSON') from exc
    if not isinstance(result, dict):
        raise NetworkError('API вернул JSON неожиданного типа: ожидался объект')
    return result


def extract_error(content: bytes) -> str:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            message = data.get('message') or data.get('error')
            if message:
                return str(message)
            errors = data.get('errors')
            if isinstance(errors, list) and errors and isinstance(errors[0], dict):
                return str(errors[0].get('message') or 'Unknown error')
    except (ValueError, UnicodeDecodeError):
        pass
    return content.decode('utf-8', errors='replace') or 'Unknown error'


def raise_for_status(status: int, content: bytes) -> None:
    if 200 <= status <= 299:
        return
    message = extract_error(content)
    exception = {
        400: BadRequestError, 401: UnauthorizedError,
        403: UnauthorizedError, 404: NotFoundError,
        410: EndpointGoneError,
    }.get(status)
    if exception:
        if status == 410:
            raise exception('HTTP 410: эндпоинт больше недоступен на стороне сервиса')
        raise exception(message)
    raise NetworkError(f'HTTP {status}: {message}')
