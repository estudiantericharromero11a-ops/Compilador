"""Definiciones de tokens del lenguaje Luma."""

from dataclasses import dataclass
from enum import Enum, auto

from .errors import SourceLocation


class TokenKind(Enum):
    START = auto()
    END = auto()
    LED = auto()
    ON = auto()
    OFF = auto()
    WAIT = auto()
    REPEAT = auto()
    END_REPEAT = auto()
    BUTTONS = auto()
    AS = auto()
    DISPLAY7 = auto()
    ACTIVE_LOW = auto()
    READ_BINARY = auto()
    IF = auto()
    ELSE = auto()
    END_IF = auto()
    SHOW = auto()
    IN = auto()
    CLEAR = auto()
    FOREVER = auto()
    END_FOREVER = auto()
    NUMBER = auto()
    IDENTIFIER = auto()
    OPERATOR = auto()
    EOL = auto()
    EOF = auto()


KEYWORDS = {
    "INICIAR": TokenKind.START,
    "FINALIZAR": TokenKind.END,
    "LED": TokenKind.LED,
    "ENCENDER": TokenKind.ON,
    "APAGAR": TokenKind.OFF,
    "ESPERAR": TokenKind.WAIT,
    "REPETIR": TokenKind.REPEAT,
    "FIN_REPETIR": TokenKind.END_REPEAT,
    "BOTONES": TokenKind.BUTTONS,
    "COMO": TokenKind.AS,
    "DISPLAY7": TokenKind.DISPLAY7,
    "ACTIVO_BAJO": TokenKind.ACTIVE_LOW,
    "LEER_BINARIO": TokenKind.READ_BINARY,
    "SI": TokenKind.IF,
    "SINO": TokenKind.ELSE,
    "FIN_SI": TokenKind.END_IF,
    "MOSTRAR": TokenKind.SHOW,
    "EN": TokenKind.IN,
    "LIMPIAR": TokenKind.CLEAR,
    "REPETIR_SIEMPRE": TokenKind.FOREVER,
    "FIN_REPETIR_SIEMPRE": TokenKind.END_FOREVER,
}


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    location: SourceLocation
