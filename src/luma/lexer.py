"""Analizador léxico de Luma."""

from .errors import LumaError, SourceLocation
from .tokens import KEYWORDS, Token, TokenKind


class Lexer:
    """Convierte texto Luma en tokens con posiciones de línea y columna."""

    def __init__(self, source: str):
        self.source = source

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        index = 0
        line = 1
        column = 1
        source = self.source

        while index < len(source):
            char = source[index]
            location = SourceLocation(line, column)

            if char in " \t":
                index += 1
                column += 1
                continue
            if char == "\r":
                index += 1
                if index < len(source) and source[index] == "\n":
                    index += 1
                tokens.append(Token(TokenKind.EOL, "\n", location))
                line += 1
                column = 1
                continue
            if char == "\n":
                tokens.append(Token(TokenKind.EOL, char, location))
                index += 1
                line += 1
                column = 1
                continue
            if char == '"':
                index += 1
                column += 1
                value: list[str] = []
                while index < len(source) and source[index] != '"':
                    current = source[index]
                    if current in "\r\n":
                        raise LumaError("Las cadenas de texto no pueden ocupar varias líneas", location)
                    if current == "\\":
                        if index + 1 >= len(source) or source[index + 1] not in ('"', "\\"):
                            raise LumaError("Secuencia de escape no permitida en la cadena", SourceLocation(line, column))
                        value.append(source[index + 1])
                        index += 2
                        column += 2
                    else:
                        if not 32 <= ord(current) <= 126:
                            raise LumaError(
                                "Las cadenas solo admiten caracteres ASCII imprimibles",
                                SourceLocation(line, column),
                            )
                        value.append(current)
                        index += 1
                        column += 1
                if index >= len(source):
                    raise LumaError("Falta cerrar la cadena de texto", location)
                index += 1
                column += 1
                tokens.append(Token(TokenKind.STRING, "".join(value), location))
                continue
            if char == "#":
                while index < len(source) and source[index] not in "\r\n":
                    index += 1
                    column += 1
                continue
            if char.isascii() and (char.isalpha() or char == "_"):
                start = index
                while index < len(source):
                    current = source[index]
                    if not (current.isascii() and (current.isalnum() or current == "_")):
                        break
                    index += 1
                    column += 1
                lexeme = source[start:index]
                kind = KEYWORDS.get(lexeme.upper(), TokenKind.IDENTIFIER)
                tokens.append(Token(kind, lexeme, location))
                continue
            if char.isascii() and char.isdigit():
                start = index
                while index < len(source) and source[index].isascii() and source[index].isdigit():
                    index += 1
                    column += 1
                tokens.append(Token(TokenKind.NUMBER, source[start:index], location))
                continue

            if char in "<>!=":
                operator = source[index : index + 2]
                if operator in ("<=", ">=", "==", "!="):
                    tokens.append(Token(TokenKind.OPERATOR, operator, location))
                    index += 2
                    column += 2
                elif char == "=":
                    tokens.append(Token(TokenKind.ASSIGNMENT, char, location))
                    index += 1
                    column += 1
                elif char in "<>":
                    tokens.append(Token(TokenKind.OPERATOR, char, location))
                    index += 1
                    column += 1
                else:
                    raise LumaError(f"Operador no permitido: {char!r}", location)
                continue

            raise LumaError(f"Carácter no permitido: {char!r}", location)

        tokens.append(Token(TokenKind.EOF, "", SourceLocation(line, column)))
        return tokens
