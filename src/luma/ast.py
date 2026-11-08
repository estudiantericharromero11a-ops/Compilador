"""Nodos del árbol de sintaxis abstracta de Luma."""

from dataclasses import dataclass

from .errors import SourceLocation


@dataclass(frozen=True)
class Statement:
    location: SourceLocation


@dataclass(frozen=True)
class LedStatement(Statement):
    pin: int
    enabled: bool


@dataclass(frozen=True)
class WaitStatement(Statement):
    milliseconds: int


@dataclass(frozen=True)
class RepeatStatement(Statement):
    count: int
    body: tuple[Statement, ...]


@dataclass(frozen=True)
class ForeverStatement(Statement):
    body: tuple[Statement, ...]


@dataclass(frozen=True)
class ButtonDeclaration(Statement):
    name: str
    pins: tuple[int, int, int, int]


@dataclass(frozen=True)
class Display7Declaration(Statement):
    name: str
    pins: tuple[int, int, int, int, int, int, int]


@dataclass(frozen=True)
class ReadBinaryStatement(Statement):
    button_name: str
    variable: str


@dataclass(frozen=True)
class ShowDigitStatement(Statement):
    variable: str
    display_name: str


@dataclass(frozen=True)
class ClearDisplayStatement(Statement):
    display_name: str


@dataclass(frozen=True)
class IfStatement(Statement):
    variable: str
    operator: str
    value: int
    body: tuple[Statement, ...]
    else_body: tuple[Statement, ...]


@dataclass(frozen=True)
class Program:
    body: tuple[Statement, ...]
    location: SourceLocation
