"""Errores del compilador con ubicación de origen."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int


class LumaError(Exception):
    """Error reportable al usuario durante la compilación."""

    def __init__(self, message: str, location: SourceLocation):
        self.message = message
        self.location = location
        super().__init__(f"Línea {location.line}, columna {location.column}: {message}")
