"""
base.py — базовые классы всех моделей библиотеки.

Иерархия:
    BaseObject              ← утилитарные методы (valid_client и т.п.)
        └── BaseModel       ← де/сериализация, eq, hash, repr
                └── все ~70 доменных моделей (через @model)

Поток данных:
    HTTP-ответ (bytes)
        → Request._parse()          # json.loads() с object_hook нормализацией
        → dict[snake_case]
        → Model.de_json(data, client)
        → Python dataclass с ссылкой на client
"""
from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

JSONType = Dict[str, Any]

# Ключевые слова Python, которые нельзя использовать как имена полей.
# При нормализации ключей JSON добавляется _ в конец.
PYTHON_RESERVED = frozenset({
    'type', 'from', 'import', 'class', 'return', 'pass',
    'in', 'is', 'format', 'filter', 'id', 'input', 'list',
    'dict', 'set', 'max', 'min', 'sum', 'map', 'zip',
})

Self = TypeVar('Self', bound='BaseModel')


# ---------------------------------------------------------------------------
# Утилиты сериализации
# ---------------------------------------------------------------------------

def _recursive_to_dict(value: Any, for_request: bool) -> Any:
    """Рекурсивно сериализует вложенные объекты."""
    if isinstance(value, BaseModel):
        return value.to_dict(for_request)
    if isinstance(value, list):
        return [_recursive_to_dict(v, for_request) for v in value]
    if isinstance(value, dict):
        return {k: _recursive_to_dict(v, for_request) for k, v in value.items()}
    return value


def _snake_to_camel(name: str) -> str:
    """snake_case → camelCase. Пример: book_uuid → bookUuid."""
    parts = name.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])


# ---------------------------------------------------------------------------
# BaseObject — утилитарные методы
# ---------------------------------------------------------------------------

class BaseObject:
    """Утилитарные методы, не связанные с сериализацией."""

    @staticmethod
    def valid_client(client: Any) -> bool:
        """Проверяет, что client — это синхронный клиент (не None, не async)."""
        return client is not None and not getattr(client, '_is_async', False)

    @staticmethod
    def valid_async_client(client: Any) -> bool:
        """Проверяет, что client — это асинхронный клиент."""
        return client is not None and getattr(client, '_is_async', False)


# ---------------------------------------------------------------------------
# BaseModel — основа всех моделей
# ---------------------------------------------------------------------------

class BaseModel(BaseObject):
    """Базовый класс для всех доменных моделей.

    Не является dataclass сам по себе — подклассы декорируются через @model.
    Предоставляет:
      • de_json  / de_list   — десериализация dict/list → объект/список
      • cleanup_data         — фильтрация неизвестных полей API
      • to_dict  / to_json   — сериализация обратно в dict/JSON
      • __eq__   / __hash__  — сравнение через _id_attrs
      • __repr__             — человекочитаемое представление
    """

    # Перекрывается в __post_init__ каждого подкласса.
    _id_attrs: tuple = ()

    # ------------------------------------------------------------------ #
    # Проверка типа данных                                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    def is_dict_model_data(cls, data: Any) -> bool:
        """Возвращает True если data — непустой dict."""
        return isinstance(data, dict) and bool(data)

    @classmethod
    def is_array_model_data(cls, data: Any) -> bool:
        """Возвращает True если data — непустой список dict-ов."""
        return (
            isinstance(data, list)
            and bool(data)
            and isinstance(data[0], dict)
        )

    # ------------------------------------------------------------------ #
    # Фильтрация данных                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def cleanup_data(cls, data: JSONType, client: Any) -> JSONType:
        """Оставляет только поля, объявленные в dataclass.

        Неизвестные поля (новые в API) молча игнорируются.
        Если client.report_unknown_fields=True — они логируются.
        """
        known = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        # client — служебное поле, передаём отдельно
        known.discard('client')

        clean: JSONType = {}
        unknown: JSONType = {}

        for k, v in data.items():
            (clean if k in known else unknown)[k] = v

        if unknown and getattr(client, 'report_unknown_fields', False):
            logger.warning('%s: неизвестные поля API: %s', cls.__name__, list(unknown))

        return clean

    # ------------------------------------------------------------------ #
    # Десериализация                                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def de_json(cls: Type[Self], data: Any, client: Any) -> Optional[Self]:
        """dict → объект модели.

        Базовая реализация — плоская модель без вложенных объектов.
        Подклассы со вложенными моделями обязаны переопределить этот метод.
        """
        if not cls.is_dict_model_data(data):
            return None
        cls_data = cls.cleanup_data(data, client)
        return cls(client=client, **cls_data)  # type: ignore[call-arg]

    @classmethod
    def de_list(cls: Type[Self], data: Any, client: Any) -> List[Self]:
        """list[dict] → list[объект модели]."""
        if not cls.is_array_model_data(data):
            return []
        items = [cls.de_json(item, client) for item in data]
        return [item for item in items if item is not None]  # type: ignore[misc]

    # ------------------------------------------------------------------ #
    # Сериализация                                                          #
    # ------------------------------------------------------------------ #

    def to_dict(self, for_request: bool = False) -> JSONType:
        """Рекурсивная сериализация в dict.

        Args:
            for_request: если True — ключи преобразуются в camelCase
                         (для отправки обратно в API).
        """
        raw = self.__dict__.copy()
        raw.pop('client', None)
        raw.pop('_id_attrs', None)

        if for_request:
            result: JSONType = {}
            for k, v in raw.items():
                camel = _snake_to_camel(k)
                result[camel] = _recursive_to_dict(v, for_request)
            return result

        result = {}
        for k, v in raw.items():
            key = f'{k}_' if k in PYTHON_RESERVED else k
            result[key] = _recursive_to_dict(v, for_request)
        return result

    def to_json(self, for_request: bool = False) -> str:
        """Сериализация в JSON-строку."""
        return json.dumps(self.to_dict(for_request), ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Идентичность                                                          #
    # ------------------------------------------------------------------ #

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self._id_attrs == other._id_attrs
        return False

    def __hash__(self) -> int:
        frozen = tuple(
            frozenset(a) if isinstance(a, list) else a
            for a in self._id_attrs
        )
        return hash((self.__class__, frozen))

    def __repr__(self) -> str:
        try:
            fields = dataclasses.fields(self)  # type: ignore[arg-type]
        except TypeError:
            return f'{self.__class__.__name__}()'
        attrs = ', '.join(
            f'{f.name}={getattr(self, f.name)!r}'
            for f in fields
            if f.name not in ('client', '_id_attrs')
        )
        return f'{self.__class__.__name__}({attrs})'
