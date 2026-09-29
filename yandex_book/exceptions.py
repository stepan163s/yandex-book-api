"""
Иерархия исключений библиотеки yandex-book-api.

ApiError                      # базовое
├── UnauthorizedError         # 401/403 — неверный токен
├── BadRequestError           # 400 — неверный запрос
├── NotFoundError             # 404 — ресурс не найден
├── NetworkError              # сетевые ошибки
│   ├── TimedOutError         # таймаут
│   └── EndpointGoneError     # HTTP 410 — эндпоинт больше недоступен
├── InvalidOptionError        # недопустимое значение параметра
└── IdMissingError            # обязательный ID отсутствует
"""


class ApiError(Exception):
    """Базовое исключение библиотеки."""


class NetworkError(ApiError):
    """Проблема соединения или HTTP-ошибка (4xx/5xx)."""


class TimedOutError(NetworkError):
    """Запрос превысил время ожидания."""


class EndpointGoneError(NetworkError):
    """HTTP 410: эндпоинт больше недоступен на стороне сервиса."""


class UnauthorizedError(ApiError):
    """401 / 403 — неверный токен или недостаточно прав."""


class BadRequestError(ApiError):
    """400 — неверные параметры запроса."""


class NotFoundError(ApiError):
    """404 — запрошенный ресурс не найден."""


class InvalidOptionError(ApiError):
    """Недопустимое значение параметра (например, неверный формат ID)."""


class IdMissingError(ApiError):
    """Обязательный идентификатор отсутствует в объекте."""
