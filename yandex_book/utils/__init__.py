"""
utils/__init__.py — декоратор @model.

Превращает класс модели в dataclass с кастомным eq/repr.
Применяется ко всем доменным моделям библиотеки.
"""
import dataclasses
from typing import Type, TypeVar

try:
    from typing import dataclass_transform  # Python 3.11+
except ImportError:
    from typing_extensions import dataclass_transform  # type: ignore[no-redef]

T = TypeVar('T')


@dataclass_transform()
def model(cls: Type[T]) -> Type[T]:
    """Декоратор для классов моделей.

    Эквивалентен @dataclass(eq=False, repr=False):
      - eq=False   → используем собственный __eq__ / __hash__ через _id_attrs
      - repr=False → используем собственный __repr__ из BaseModel
    """
    return dataclasses.dataclass(eq=False, repr=False)(cls)  # type: ignore[return-value]
