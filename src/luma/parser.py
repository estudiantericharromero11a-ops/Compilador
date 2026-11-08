"""Analizador sintáctico recursivo descendente de Luma."""

from .ast import (
    ButtonDeclaration,
    ClearDisplayStatement,
    Display7Declaration,
    ForeverStatement,
    IfStatement,
    LedStatement,
    Program,
    ReadBinaryStatement,
    RepeatStatement,
    ShowDigitStatement,
    Statement,
    WaitStatement,
)
from .errors import LumaError
from .tokens import Token, TokenKind


class Parser:
    """Construye el AST y exige una instrucción por línea."""

    MAX_NESTING = 32

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def parse(self) -> Program:
        self._skip_eols()
        start = self._expect(TokenKind.START, "El programa debe comenzar con INICIAR")
        self._expect_line_end()
        body = self._parse_statements(depth=0, stop_kinds={TokenKind.END})
        end = self._expect(TokenKind.END, "Se esperaba FINALIZAR")
        self._expect_line_end()
        self._skip_eols()
        if self._current().kind is not TokenKind.EOF:
            raise LumaError("No se permiten instrucciones después de FINALIZAR", self._current().location)
        return Program(tuple(body), start.location)

    def _parse_statements(self, depth: int, stop_kinds: set[TokenKind]) -> list[Statement]:
        statements: list[Statement] = []
        while True:
            self._skip_eols()
            token = self._current()
            if token.kind is TokenKind.EOF:
                if TokenKind.END_REPEAT in stop_kinds:
                    raise LumaError("Falta FIN_REPETIR para cerrar el bloque", token.location)
                if TokenKind.END_FOREVER in stop_kinds:
                    raise LumaError("Falta FIN_REPETIR_SIEMPRE para cerrar el bloque", token.location)
                if TokenKind.END_IF in stop_kinds:
                    raise LumaError("Falta FIN_SI para cerrar el bloque", token.location)
                raise LumaError("Falta FINALIZAR al final del programa", token.location)
            if token.kind in stop_kinds:
                return statements
            if token.kind is TokenKind.END:
                if TokenKind.END_REPEAT in stop_kinds:
                    raise LumaError("Falta FIN_REPETIR antes de FINALIZAR", token.location)
                if TokenKind.END_FOREVER in stop_kinds:
                    raise LumaError("Falta FIN_REPETIR_SIEMPRE antes de FINALIZAR", token.location)
                if TokenKind.END_IF in stop_kinds:
                    raise LumaError("Falta FIN_SI antes de FINALIZAR", token.location)
                raise LumaError("Falta el cierre del bloque antes de FINALIZAR", token.location)
            if token.kind in (TokenKind.REPEAT, TokenKind.FOREVER, TokenKind.IF):
                if depth >= self.MAX_NESTING:
                    raise LumaError(
                        f"Los bloques no pueden anidarse más de {self.MAX_NESTING} niveles",
                        token.location,
                    )
            if token.kind is TokenKind.REPEAT:
                statements.append(self._parse_repeat(depth))
            elif token.kind is TokenKind.FOREVER:
                statements.append(self._parse_forever(depth))
            elif token.kind is TokenKind.IF:
                statements.append(self._parse_if(depth))
            elif token.kind is TokenKind.LED:
                statements.append(self._parse_led())
            elif token.kind is TokenKind.WAIT:
                statements.append(self._parse_wait())
            elif token.kind is TokenKind.BUTTONS:
                statements.append(self._parse_button_declaration())
            elif token.kind is TokenKind.DISPLAY7:
                statements.append(self._parse_display_declaration())
            elif token.kind is TokenKind.READ_BINARY:
                statements.append(self._parse_read_binary())
            elif token.kind is TokenKind.SHOW:
                statements.append(self._parse_show_digit())
            elif token.kind is TokenKind.CLEAR:
                statements.append(self._parse_clear_display())
            else:
                raise LumaError(f"Instrucción inesperada: {token.lexeme!r}", token.location)

    def _parse_repeat(self, depth: int) -> RepeatStatement:
        token = self._expect(TokenKind.REPEAT, "Se esperaba REPETIR")
        count = self._integer("Se esperaba el número de repeticiones")
        self._expect_line_end()
        body = self._parse_statements(depth + 1, {TokenKind.END_REPEAT})
        self._expect(TokenKind.END_REPEAT, "Falta FIN_REPETIR")
        self._expect_line_end()
        return RepeatStatement(token.location, count, tuple(body))

    def _parse_forever(self, depth: int) -> ForeverStatement:
        token = self._expect(TokenKind.FOREVER, "Se esperaba REPETIR_SIEMPRE")
        self._expect_line_end()
        body = self._parse_statements(depth + 1, {TokenKind.END_FOREVER})
        self._expect(TokenKind.END_FOREVER, "Falta FIN_REPETIR_SIEMPRE")
        self._expect_line_end()
        return ForeverStatement(token.location, tuple(body))

    def _parse_if(self, depth: int) -> IfStatement:
        token = self._expect(TokenKind.IF, "Se esperaba SI")
        variable = self._identifier("Se esperaba el nombre de una variable después de SI")
        operator = self._expect(TokenKind.OPERATOR, "Se esperaba un operador de comparación")
        value = self._integer("Se esperaba un número después del operador")
        self._expect_line_end()
        then_body = self._parse_statements(depth + 1, {TokenKind.ELSE, TokenKind.END_IF})
        else_body: list[Statement] = []
        if self._current().kind is TokenKind.ELSE:
            self._advance()
            self._expect_line_end()
            else_body = self._parse_statements(depth + 1, {TokenKind.END_IF})
        self._expect(TokenKind.END_IF, "Falta FIN_SI")
        self._expect_line_end()
        return IfStatement(token.location, variable, operator.lexeme, value, tuple(then_body), tuple(else_body))

    def _parse_button_declaration(self) -> ButtonDeclaration:
        token = self._expect(TokenKind.BUTTONS, "Se esperaba BOTONES")
        pins = (
            self._integer("Se esperaban cuatro pines para los botones"),
            self._integer("Se esperaban cuatro pines para los botones"),
            self._integer("Se esperaban cuatro pines para los botones"),
            self._integer("Se esperaban cuatro pines para los botones"),
        )
        self._expect(TokenKind.AS, "Se esperaba COMO y el nombre del grupo de botones")
        name = self._identifier("Se esperaba el nombre del grupo de botones")
        self._expect_line_end()
        return ButtonDeclaration(token.location, name, pins)

    def _parse_display_declaration(self) -> Display7Declaration:
        token = self._expect(TokenKind.DISPLAY7, "Se esperaba DISPLAY7")
        pins = (
            self._integer("Se esperaban siete pines para el display"),
            self._integer("Se esperaban siete pines para el display"),
            self._integer("Se esperaban siete pines para el display"),
            self._integer("Se esperaban siete pines para el display"),
            self._integer("Se esperaban siete pines para el display"),
            self._integer("Se esperaban siete pines para el display"),
            self._integer("Se esperaban siete pines para el display"),
        )
        self._expect(TokenKind.ACTIVE_LOW, "Se esperaba ACTIVO_BAJO para un display de cátodo común")
        self._expect(TokenKind.AS, "Se esperaba COMO y el nombre del display")
        name = self._identifier("Se esperaba el nombre del display")
        self._expect_line_end()
        return Display7Declaration(token.location, name, pins)

    def _parse_read_binary(self) -> ReadBinaryStatement:
        token = self._expect(TokenKind.READ_BINARY, "Se esperaba LEER_BINARIO")
        button_name = self._identifier("Se esperaba el nombre del grupo de botones")
        self._expect(TokenKind.AS, "Se esperaba COMO antes del nombre de variable")
        variable = self._identifier("Se esperaba el nombre de variable")
        self._expect_line_end()
        return ReadBinaryStatement(token.location, button_name, variable)

    def _parse_show_digit(self) -> ShowDigitStatement:
        token = self._expect(TokenKind.SHOW, "Se esperaba MOSTRAR")
        variable = self._identifier("Se esperaba una variable después de MOSTRAR")
        self._expect(TokenKind.IN, "Se esperaba EN antes del nombre del display")
        display_name = self._identifier("Se esperaba el nombre del display")
        self._expect_line_end()
        return ShowDigitStatement(token.location, variable, display_name)

    def _parse_clear_display(self) -> ClearDisplayStatement:
        token = self._expect(TokenKind.CLEAR, "Se esperaba LIMPIAR")
        display_name = self._identifier("Se esperaba el nombre del display después de LIMPIAR")
        self._expect_line_end()
        return ClearDisplayStatement(token.location, display_name)

    def _parse_led(self) -> LedStatement:
        token = self._expect(TokenKind.LED, "Se esperaba LED")
        pin = self._integer("Se esperaba el número de pin después de LED")
        action = self._current()
        if action.kind not in (TokenKind.ON, TokenKind.OFF):
            raise LumaError("Se esperaba ENCENDER o APAGAR después del pin", action.location)
        self._advance()
        self._expect_line_end()
        return LedStatement(token.location, pin, action.kind is TokenKind.ON)

    def _parse_wait(self) -> WaitStatement:
        token = self._expect(TokenKind.WAIT, "Se esperaba ESPERAR")
        milliseconds = self._integer("Se esperaba la duración en milisegundos")
        self._expect_line_end()
        return WaitStatement(token.location, milliseconds)

    def _integer(self, message: str) -> int:
        token = self._expect(TokenKind.NUMBER, message)
        try:
            return int(token.lexeme)
        except ValueError as error:
            raise LumaError("El número es demasiado grande", token.location) from error

    def _identifier(self, message: str) -> str:
        return self._expect(TokenKind.IDENTIFIER, message).lexeme

    def _expect_line_end(self) -> None:
        if self._current().kind is TokenKind.EOL:
            self._skip_eols()
            return
        if self._current().kind is TokenKind.EOF:
            return
        raise LumaError("Se esperaba el final de línea", self._current().location)

    def _skip_eols(self) -> None:
        while self._current().kind is TokenKind.EOL:
            self._advance()

    def _expect(self, kind: TokenKind, message: str) -> Token:
        token = self._current()
        if token.kind is not kind:
            raise LumaError(message, token.location)
        return self._advance()

    def _current(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self._current()
        if token.kind is not TokenKind.EOF:
            self.index += 1
        return token
